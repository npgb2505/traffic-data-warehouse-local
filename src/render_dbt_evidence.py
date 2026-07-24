from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "traffic_dbt" / "target" / "run_results.json"


def render() -> Path:
    payload = json.loads(RESULTS.read_text(encoding="utf-8"))
    results = payload["results"]
    passed = [result for result in results if result["status"] == "pass"]
    failed = [result for result in results if result["status"] not in {"pass", "success"}]
    rows = "".join(
        f"<tr><td>{html.escape(result['unique_id'].split('.')[-2].replace('_', ' '))}</td><td><span>PASS</span></td><td>{float(result['execution_time']):.3f}s</td></tr>"
        for result in passed
    )
    document = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    body{{font-family:Inter,Arial,sans-serif;background:#0d1c25;color:#eaf2f5;margin:0;padding:42px}}
    .shell{{max-width:1120px;margin:auto}}.badge{{display:inline-block;background:#173f35;color:#70e0b2;padding:7px 11px;border-radius:999px;font-size:11px;font-weight:750}}
    h1{{font-size:34px;margin:12px 0 5px}}.sub{{color:#91a8b4;margin-bottom:24px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
    .card,.panel{{background:#142a36;border:1px solid #254554;border-radius:14px;padding:19px}}.label{{font-size:11px;color:#8ca4b0;text-transform:uppercase;letter-spacing:.09em}}
    .value{{font-size:29px;font-weight:760;margin-top:9px}}.panel{{margin-top:14px}}h2{{font-size:16px;margin:0 0 14px}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}td,th{{padding:9px 5px;border-bottom:1px solid #254554;text-align:left}}td:last-child,th:last-child{{text-align:right}}
    td span{{display:inline-block;background:#173f35;color:#70e0b2;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:750}}
    </style></head><body><div class="shell"><span class="badge">ACTUAL DBT RUN RESULTS</span>
    <h1>Traffic Warehouse Quality Gate</h1><div class="sub">Data tests executed after all models were built</div>
    <section class="cards"><div class="card"><div class="label">Tests executed</div><div class="value">{len(results)}</div></div>
    <div class="card"><div class="label">Passed</div><div class="value">{len(passed)}</div></div>
    <div class="card"><div class="label">Failed</div><div class="value">{len(failed)}</div></div></section>
    <div class="panel"><h2>Test results</h2><table><tr><th>Test</th><th>Status</th><th>Duration</th></tr>{rows}</table></div>
    </div></body></html>"""
    output = ROOT / "artifacts" / "dbt-tests.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"Rendered {output} from {RESULTS}")
    return output


if __name__ == "__main__":
    render()
