from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "Metro_Interstate_Traffic_Volume.csv"
DEFAULT_DSN = "postgresql://traffic:traffic@localhost:5544/traffic"
PIPELINE_NAME = "uci_metro_traffic_ingestion"
EXPECTED = {
    "holiday",
    "temp",
    "rain_1h",
    "snow_1h",
    "clouds_all",
    "weather_main",
    "weather_description",
    "date_time",
    "traffic_volume",
}


CONTROL_DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.pipeline_watermarks (
    pipeline_name TEXT PRIMARY KEY,
    last_event_at TIMESTAMP,
    last_batch_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL
);
"""


DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.traffic_observations (
    observation_id TEXT PRIMARY KEY,
    observed_at TIMESTAMP NOT NULL,
    holiday TEXT,
    temp_kelvin DOUBLE PRECISION NOT NULL,
    rain_1h DOUBLE PRECISION NOT NULL,
    snow_1h DOUBLE PRECISION NOT NULL,
    clouds_all INTEGER NOT NULL,
    weather_main TEXT NOT NULL,
    weather_description TEXT NOT NULL,
    traffic_volume INTEGER NOT NULL,
    source_row_number BIGINT NOT NULL,
    batch_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS traffic_observations_observed_at_idx
    ON raw.traffic_observations (observed_at);

CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
    batch_id TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    run_mode TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    source_rows INTEGER NOT NULL,
    window_rows INTEGER NOT NULL,
    accepted_rows INTEGER NOT NULL,
    rejected_rows INTEGER NOT NULL,
    rejection_rate NUMERIC(10,6) NOT NULL,
    start_at TIMESTAMP,
    end_at TIMESTAMP,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.data_quality_results (
    batch_id TEXT NOT NULL REFERENCES raw.pipeline_runs(batch_id),
    check_name TEXT NOT NULL,
    check_value NUMERIC(18,6) NOT NULL,
    threshold NUMERIC(18,6),
    passed BOOLEAN NOT NULL,
    PRIMARY KEY (batch_id, check_name)
);

CREATE TABLE IF NOT EXISTS raw.pipeline_watermarks (
    pipeline_name TEXT PRIMARY KEY,
    last_event_at TIMESTAMP,
    last_batch_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL
);
"""


def get_watermark(dsn: str) -> datetime | None:
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CONTROL_DDL)
            cursor.execute(
                "SELECT last_event_at FROM raw.pipeline_watermarks WHERE pipeline_name=%s",
                (PIPELINE_NAME,),
            )
            row = cursor.fetchone()
        connection.commit()
    return row["last_event_at"] if row else None


def transform_frame(
    frame: pd.DataFrame,
    batch_id: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    missing = sorted(EXPECTED - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    work = frame.copy()
    work["source_row_number"] = work.index.astype("int64")
    work["observed_at"] = pd.to_datetime(work["date_time"], errors="coerce")
    for column in ["temp", "rain_1h", "snow_1h", "clouds_all", "traffic_volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["holiday"] = work["holiday"].fillna("").astype(str).str.strip()
    work["weather_main"] = work["weather_main"].astype("string").str.strip()
    work["weather_description"] = work["weather_description"].astype("string").str.strip()

    if start_at is not None:
        work = work.loc[work["observed_at"] >= start_at]
    if end_at is not None:
        work = work.loc[work["observed_at"] <= end_at]
    window_rows = len(work)

    invalid_date = work["observed_at"].isna()
    invalid_weather = (
        work["weather_main"].isna()
        | work["weather_main"].eq("")
        | work["weather_description"].isna()
        | work["weather_description"].eq("")
    )
    invalid_measure = (
        work["temp"].isna()
        | ~work["temp"].between(0, 330)
        | work["rain_1h"].isna()
        | work["rain_1h"].lt(0)
        | work["snow_1h"].isna()
        | work["snow_1h"].lt(0)
        | work["clouds_all"].isna()
        | ~work["clouds_all"].between(0, 100)
        | work["traffic_volume"].isna()
        | ~work["traffic_volume"].between(0, 10000)
    )
    reject_mask = invalid_date | invalid_weather | invalid_measure
    rejected = work.loc[reject_mask].copy()
    rejected["rejection_reason"] = "invalid_measurement"
    rejected.loc[invalid_date, "rejection_reason"] = "invalid_observation_time"
    rejected.loc[invalid_weather, "rejection_reason"] = "missing_weather_classification"

    clean = work.loc[~reject_mask].copy()
    clean["clouds_all"] = clean["clouds_all"].astype("int64")
    clean["traffic_volume"] = clean["traffic_volume"].astype("int64")
    clean["batch_id"] = batch_id
    clean["ingested_at"] = datetime.now(timezone.utc)
    identity_fields = [
        "observed_at",
        "holiday",
        "temp",
        "rain_1h",
        "snow_1h",
        "clouds_all",
        "weather_main",
        "weather_description",
        "traffic_volume",
        "source_row_number",
    ]
    signatures = clean[identity_fields].astype("string").fillna("<null>").agg("|".join, axis=1)
    clean["observation_id"] = signatures.map(
        lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
    )
    rejected_rows = len(rejected)
    summary = {
        "source_rows": int(len(frame)),
        "window_rows": int(window_rows),
        "accepted_rows": int(len(clean)),
        "rejected_rows": int(rejected_rows),
        "rejection_rate": round(rejected_rows / max(window_rows, 1), 6),
        "distinct_observations": int(clean["observation_id"].nunique()),
        "min_observed_at": clean["observed_at"].min().isoformat() if len(clean) else None,
        "max_observed_at": clean["observed_at"].max().isoformat() if len(clean) else None,
    }
    return clean, rejected, summary


def _python_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        return value.item()
    return value


def load_to_postgres(
    clean: pd.DataFrame,
    dsn: str,
    summary: dict,
    batch_id: str,
    started_at: datetime,
    start_at: datetime | None,
    end_at: datetime | None,
    full_refresh: bool,
) -> dict:
    finished_at = datetime.now(timezone.utc)
    run_mode = "full_refresh" if full_refresh else "incremental"
    columns = [
        "observation_id",
        "observed_at",
        "holiday",
        "temp",
        "rain_1h",
        "snow_1h",
        "clouds_all",
        "weather_main",
        "weather_description",
        "traffic_volume",
        "source_row_number",
        "batch_id",
        "ingested_at",
    ]
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            cursor.execute(
                """
                CREATE TEMP TABLE stage_traffic_observations
                (LIKE raw.traffic_observations INCLUDING DEFAULTS)
                ON COMMIT DROP
                """
            )
            with cursor.copy(
                """
                COPY stage_traffic_observations
                    (observation_id, observed_at, holiday, temp_kelvin, rain_1h, snow_1h,
                     clouds_all, weather_main, weather_description, traffic_volume,
                     source_row_number, batch_id, ingested_at)
                FROM STDIN
                """
            ) as copy:
                for row in clean[columns].itertuples(index=False, name=None):
                    copy.write_row(tuple(_python_value(value) for value in row))

            if full_refresh:
                cursor.execute("TRUNCATE TABLE raw.traffic_observations")
            cursor.execute(
                """
                INSERT INTO raw.traffic_observations
                SELECT * FROM stage_traffic_observations
                ON CONFLICT (observation_id) DO UPDATE SET
                    observed_at=EXCLUDED.observed_at,
                    holiday=EXCLUDED.holiday,
                    temp_kelvin=EXCLUDED.temp_kelvin,
                    rain_1h=EXCLUDED.rain_1h,
                    snow_1h=EXCLUDED.snow_1h,
                    clouds_all=EXCLUDED.clouds_all,
                    weather_main=EXCLUDED.weather_main,
                    weather_description=EXCLUDED.weather_description,
                    traffic_volume=EXCLUDED.traffic_volume,
                    batch_id=EXCLUDED.batch_id,
                    ingested_at=EXCLUDED.ingested_at
                """
            )
            cursor.execute(
                """
                INSERT INTO raw.pipeline_runs
                    (batch_id, pipeline_name, run_mode, started_at, finished_at,
                     source_rows, window_rows, accepted_rows, rejected_rows,
                     rejection_rate, start_at, end_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'success')
                ON CONFLICT (batch_id) DO NOTHING
                """,
                (
                    batch_id,
                    PIPELINE_NAME,
                    run_mode,
                    started_at,
                    finished_at,
                    summary["source_rows"],
                    summary["window_rows"],
                    summary["accepted_rows"],
                    summary["rejected_rows"],
                    summary["rejection_rate"],
                    start_at,
                    end_at,
                ),
            )
            quality_results = [
                (
                    batch_id,
                    "rejection_rate_below_1_percent",
                    summary["rejection_rate"],
                    0.01,
                    summary["rejection_rate"] < 0.01,
                ),
                (
                    batch_id,
                    "accepted_rows_positive",
                    summary["accepted_rows"],
                    1,
                    summary["accepted_rows"] > 0,
                ),
                (
                    batch_id,
                    "observation_ids_are_unique",
                    summary["distinct_observations"],
                    summary["accepted_rows"],
                    summary["distinct_observations"] == summary["accepted_rows"],
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO raw.data_quality_results
                    (batch_id, check_name, check_value, threshold, passed)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (batch_id, check_name) DO UPDATE SET
                    check_value=EXCLUDED.check_value,
                    threshold=EXCLUDED.threshold,
                    passed=EXCLUDED.passed
                """,
                quality_results,
            )
            if not all(row[-1] for row in quality_results):
                raise ValueError("One or more source data quality checks failed")

            max_event_at = clean["observed_at"].max().to_pydatetime()
            cursor.execute(
                """
                INSERT INTO raw.pipeline_watermarks
                    (pipeline_name, last_event_at, last_batch_id, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (pipeline_name) DO UPDATE SET
                    last_event_at=GREATEST(
                        raw.pipeline_watermarks.last_event_at,
                        EXCLUDED.last_event_at
                    ),
                    last_batch_id=EXCLUDED.last_batch_id,
                    updated_at=EXCLUDED.updated_at
                """,
                (PIPELINE_NAME, max_event_at, batch_id, finished_at),
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS warehouse_raw_rows,
                       MIN(observed_at) AS warehouse_min_at,
                       MAX(observed_at) AS warehouse_max_at
                FROM raw.traffic_observations
                """
            )
            metrics = dict(cursor.fetchone())
        connection.commit()
    return metrics


def write_observability(result: dict) -> None:
    artifacts = ROOT / "artifacts"
    runs = artifacts / "runs"
    artifacts.mkdir(exist_ok=True)
    runs.mkdir(exist_ok=True)
    payload = json.dumps(result, indent=2, default=str)
    (artifacts / "load_summary.json").write_text(payload, encoding="utf-8")
    (runs / f"{result['batch_id']}.json").write_text(payload, encoding="utf-8")
    metrics = [
        "# HELP traffic_ingestion_rows Rows handled by the latest ingestion",
        "# TYPE traffic_ingestion_rows gauge",
        f'traffic_ingestion_rows{{state="source"}} {result["source_rows"]}',
        f'traffic_ingestion_rows{{state="accepted"}} {result["accepted_rows"]}',
        f'traffic_ingestion_rows{{state="rejected"}} {result["rejected_rows"]}',
        "# HELP traffic_ingestion_rejection_rate Rejected rows divided by processing-window rows",
        "# TYPE traffic_ingestion_rejection_rate gauge",
        f"traffic_ingestion_rejection_rate {result['rejection_rate']}",
        "# HELP traffic_warehouse_raw_rows Rows stored in the raw warehouse layer",
        "# TYPE traffic_warehouse_raw_rows gauge",
        f"traffic_warehouse_raw_rows {result['warehouse_raw_rows']}",
    ]
    (artifacts / "metrics.prom").write_text("\n".join(metrics) + "\n", encoding="utf-8")


def load_raw(
    path: Path,
    dsn: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    full_refresh: bool = False,
    lookback_hours: int = 24,
    batch_id: str | None = None,
) -> dict:
    started_at = datetime.now(timezone.utc)
    batch_id = batch_id or uuid.uuid4().hex
    watermark = None if full_refresh else get_watermark(dsn)
    effective_start = start_at
    if effective_start is None and watermark is not None:
        effective_start = watermark - timedelta(hours=lookback_hours)
    frame = pd.read_csv(path)
    clean, rejected, summary = transform_frame(frame, batch_id, effective_start, end_at)
    if summary["window_rows"] == 0 or summary["accepted_rows"] == 0:
        raise ValueError("No valid rows fall inside the requested processing window")

    rejected_dir = ROOT / "data" / "rejected" / f"batch_id={batch_id}"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    rejected_path = rejected_dir / "traffic_observations.csv"
    rejected.to_csv(rejected_path, index=False)

    warehouse = load_to_postgres(
        clean,
        dsn,
        summary,
        batch_id,
        started_at,
        effective_start,
        end_at,
        full_refresh,
    )
    result = {
        "status": "success",
        "pipeline_name": PIPELINE_NAME,
        "batch_id": batch_id,
        "run_mode": "full_refresh" if full_refresh else "incremental",
        "requested_start_at": start_at.isoformat() if start_at else None,
        "effective_start_at": effective_start.isoformat() if effective_start else None,
        "end_at": end_at.isoformat() if end_at else None,
        "watermark_before_run": watermark.isoformat() if watermark else None,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        **summary,
        **warehouse,
        "rejected_output": str(rejected_path),
    }
    write_observability(result)
    print(json.dumps(result, indent=2, default=str))
    return result


def parse_timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load the complete UCI traffic dataset")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dsn", default=os.getenv("WAREHOUSE_DSN", DEFAULT_DSN))
    parser.add_argument("--start-at", type=parse_timestamp)
    parser.add_argument("--end-at", type=parse_timestamp)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--batch-id")
    parser.add_argument("--full-refresh", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    load_raw(
        arguments.input,
        arguments.dsn,
        arguments.start_at,
        arguments.end_at,
        arguments.full_refresh,
        arguments.lookback_hours,
        arguments.batch_id,
    )
