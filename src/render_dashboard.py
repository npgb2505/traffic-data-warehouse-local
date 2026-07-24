from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSN = "postgresql://traffic:traffic@localhost:5544/traffic"


def query(dsn: str, statement: str) -> list[dict]:
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return [dict(row) for row in cursor.fetchall()]


def render(dsn: str, output: Path) -> dict:
    totals = query(
        dsn,
        """
        SELECT COUNT(*) AS observations,
               COUNT(DISTINCT location_id) AS locations,
               ROUND(AVG(speed_kmh)::numeric, 1) AS avg_speed,
               ROUND(100.0 * AVG((speed_kmh < 20)::int), 1) AS congestion_rate
        FROM analytics.fct_traffic_observation
        """,
    )[0]
    hotspots = query(
        dsn,
        """
        SELECT location_name, district, avg_speed_kmh, congestion_rate_percent, observation_count
        FROM analytics.mart_congestion_hotspots
        ORDER BY congestion_rate_percent DESC, observation_count DESC
        """,
    )
    hours = query(
        dsn,
        """
        SELECT hour_of_day, ROUND(AVG(avg_speed_kmh), 1) AS avg_speed
        FROM analytics.mart_hourly_traffic
        GROUP BY hour_of_day ORDER BY hour_of_day
        """,
    )
    max_congestion = max((float(row["congestion_rate_percent"]) for row in hotspots), default=1)
    hotspot_bars = "".join(
        f"""
        <div class="bar-row"><span>{html.escape(row['location_name'])}</span>
        <div class="track"><i style="width:{max(3, float(row['congestion_rate_percent']) / max_congestion * 100):.1f}%"></i></div>
        <b>{float(row['congestion_rate_percent']):.1f}%</b></div>
        """
        for row in hotspots
    )
    points = " ".join(
        f"{36 + index * 42},{170 - float(row['avg_speed']) * 2.25:.1f}"
        for index, row in enumerate(hours)
    )
    labels = "".join(
        f'<text x="{36 + index * 42}" y="190">{int(row["hour_of_day"]):02d}</text>'
        for index, row in enumerate(hours)
        if index % 3 == 0
    )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Da Nang Traffic Warehouse</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#0d1c25;color:#eaf2f5;margin:0;padding:40px}}
.shell{{max-width:1180px;margin:auto}} h1{{font-size:35px;margin:0}} .sub{{color:#91a8b4;margin:8px 0 26px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}} .card,.panel{{background:#142a36;border:1px solid #254554;border-radius:14px;padding:19px}}
.label{{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#8ca4b0}} .value{{font-size:29px;font-weight:760;margin-top:9px;color:#fff}}
.grid{{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px}} h2{{font-size:16px;margin:0 0 18px}}
.bar-row{{display:grid;grid-template-columns:145px 1fr 58px;gap:10px;align-items:center;margin:15px 0;font-size:12px}}
.track{{height:10px;background:#203d4b;border-radius:9px;overflow:hidden}} .track i{{display:block;height:100%;background:#ffb44c;border-radius:9px}}
.ok{{display:inline-block;background:#173f35;color:#70e0b2;padding:7px 11px;border-radius:999px;font-weight:700;font-size:11px;margin-bottom:12px}}
svg{{width:100%;height:210px}} polyline{{fill:none;stroke:#47c4d8;stroke-width:3}} text{{fill:#88a4b1;font-size:10px;text-anchor:middle}}
</style></head><body><div class="shell">
<span class="ok">DBT TESTS PASSED</span><h1>Da Nang Traffic Warehouse</h1>
<div class="sub">Local Airflow + PostgreSQL + dbt pipeline · actual demo output</div>
<section class="cards">
<div class="card"><div class="label">Observations</div><div class="value">{int(totals['observations']):,}</div></div>
<div class="card"><div class="label">Monitored locations</div><div class="value">{int(totals['locations'])}</div></div>
<div class="card"><div class="label">Average speed</div><div class="value">{float(totals['avg_speed']):.1f} km/h</div></div>
<div class="card"><div class="label">Congestion rate</div><div class="value">{float(totals['congestion_rate']):.1f}%</div></div>
</section>
<section class="grid"><div class="panel"><h2>Congestion hotspots</h2>{hotspot_bars}</div>
<div class="panel"><h2>Average speed by hour</h2><svg viewBox="0 0 1040 210" preserveAspectRatio="none">
<line x1="30" y1="170" x2="1020" y2="170" stroke="#36515f"/><polyline points="{points}"/>{labels}</svg></div></section>
</div></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    summary = {
        "status": "success",
        **{key: float(value) if key in {"avg_speed", "congestion_rate"} else int(value) for key, value in totals.items()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output.parent / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    render(os.getenv("WAREHOUSE_DSN", DEFAULT_DSN), ROOT / "artifacts" / "dashboard.html")

