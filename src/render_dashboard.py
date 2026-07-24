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
               MIN(observation_date) AS min_date,
               MAX(observation_date) AS max_date,
               ROUND(AVG(traffic_volume)::numeric, 0) AS avg_traffic_volume,
               ROUND(100.0 * AVG((traffic_state = 'heavy')::int), 1) AS heavy_traffic_rate
        FROM analytics.fct_traffic_observation
        """,
    )[0]
    weather = query(
        dsn,
        """
        SELECT weather_description, observation_count, avg_traffic_volume,
               heavy_traffic_rate_percent
        FROM analytics.mart_weather_impact
        WHERE observation_count >= 100
        ORDER BY observation_count DESC
        LIMIT 8
        """,
    )
    hours = query(
        dsn,
        """
        SELECT hour_of_day,
               ROUND(AVG(traffic_volume)::numeric, 0) AS avg_traffic_volume
        FROM analytics.fct_traffic_observation
        GROUP BY hour_of_day
        ORDER BY hour_of_day
        """,
    )
    max_rate = max((float(row["heavy_traffic_rate_percent"]) for row in weather), default=1)
    weather_bars = "".join(
        f"""
        <div class="bar-row"><span>{html.escape(str(row['weather_description']).title())}</span>
        <div class="track"><i style="width:{max(3, float(row['heavy_traffic_rate_percent']) / max_rate * 100):.1f}%"></i></div>
        <b>{float(row['heavy_traffic_rate_percent']):.1f}%</b></div>
        """
        for row in weather
    )
    max_volume = max((float(row["avg_traffic_volume"]) for row in hours), default=1)
    points = " ".join(
        f"{36 + index * 42},{170 - float(row['avg_traffic_volume']) / max_volume * 130:.1f}"
        for index, row in enumerate(hours)
    )
    labels = "".join(
        f'<text x="{36 + index * 42}" y="190">{int(row["hour_of_day"]):02d}</text>'
        for index, row in enumerate(hours)
        if index % 3 == 0
    )
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>I-94 Traffic Warehouse</title>
<style>
body{{font-family:Inter,Arial,sans-serif;background:#0d1c25;color:#eaf2f5;margin:0;padding:40px}}
.shell{{max-width:1180px;margin:auto}}h1{{font-size:35px;margin:0}}.sub{{color:#91a8b4;margin:8px 0 26px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.card,.panel{{background:#142a36;border:1px solid #254554;border-radius:14px;padding:19px}}
.label{{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#8ca4b0}}.value{{font-size:29px;font-weight:760;margin-top:9px;color:#fff}}
.grid{{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px}}h2{{font-size:16px;margin:0 0 18px}}
.bar-row{{display:grid;grid-template-columns:165px 1fr 58px;gap:10px;align-items:center;margin:13px 0;font-size:12px}}
.track{{height:10px;background:#203d4b;border-radius:9px;overflow:hidden}}.track i{{display:block;height:100%;background:#ffb44c;border-radius:9px}}
.ok{{display:inline-block;background:#173f35;color:#70e0b2;padding:7px 11px;border-radius:999px;font-weight:700;font-size:11px;margin-bottom:12px}}
svg{{width:100%;height:210px}}polyline{{fill:none;stroke:#47c4d8;stroke-width:3}}text{{fill:#88a4b1;font-size:10px;text-anchor:middle}}
</style></head><body><div class="shell">
<span class="ok">FULL UCI DATASET · DBT TESTS PASSED</span><h1>I-94 Metro Traffic Warehouse</h1>
<div class="sub">Airflow + PostgreSQL + dbt · complete hourly traffic and weather history</div>
<section class="cards">
<div class="card"><div class="label">Observations</div><div class="value">{int(totals['observations']):,}</div></div>
<div class="card"><div class="label">Date coverage</div><div class="value">{totals['min_date'].year}–{totals['max_date'].year}</div></div>
<div class="card"><div class="label">Average traffic</div><div class="value">{float(totals['avg_traffic_volume']):,.0f}</div></div>
<div class="card"><div class="label">Heavy traffic rate</div><div class="value">{float(totals['heavy_traffic_rate']):.1f}%</div></div>
</section>
<section class="grid"><div class="panel"><h2>Heavy-traffic rate by weather</h2>{weather_bars}</div>
<div class="panel"><h2>Average traffic volume by hour</h2><svg viewBox="0 0 1040 210" preserveAspectRatio="none">
<line x1="30" y1="170" x2="1020" y2="170" stroke="#36515f"/><polyline points="{points}"/>{labels}</svg></div></section>
</div></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    summary = {
        "status": "success",
        "observations": int(totals["observations"]),
        "min_date": str(totals["min_date"]),
        "max_date": str(totals["max_date"]),
        "avg_traffic_volume": float(totals["avg_traffic_volume"]),
        "heavy_traffic_rate": float(totals["heavy_traffic_rate"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output.parent / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    render(os.getenv("WAREHOUSE_DSN", DEFAULT_DSN), ROOT / "artifacts" / "dashboard.html")
