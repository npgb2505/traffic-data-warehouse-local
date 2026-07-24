from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "traffic_observations.csv"
DEFAULT_DSN = "postgresql://traffic:traffic@localhost:5544/traffic"
EXPECTED = {
    "observation_id",
    "observed_at",
    "location_id",
    "location_name",
    "district",
    "latitude",
    "longitude",
    "vehicle_type",
    "speed_kmh",
    "direction",
    "sensor_id",
}

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.traffic_observations (
    observation_id TEXT PRIMARY KEY,
    observed_at TIMESTAMP NOT NULL,
    location_id TEXT NOT NULL,
    location_name TEXT NOT NULL,
    district TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    vehicle_type TEXT NOT NULL,
    speed_kmh DOUBLE PRECISION NOT NULL,
    direction TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL,
    source_rows INTEGER NOT NULL,
    loaded_rows INTEGER NOT NULL,
    status TEXT NOT NULL
);
"""


def load_raw(path: Path, dsn: str) -> dict:
    frame = pd.read_csv(path)
    missing = sorted(EXPECTED - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], errors="coerce")
    invalid = (
        frame["observed_at"].isna()
        | frame["observation_id"].isna()
        | frame["location_id"].isna()
        | frame["speed_kmh"].lt(0)
        | frame["speed_kmh"].gt(180)
    )
    if invalid.any():
        raise ValueError(f"Source failed quality gate: {int(invalid.sum())} invalid rows")

    ingested_at = datetime.now(timezone.utc)
    rows = [
        (
            str(row.observation_id),
            row.observed_at.to_pydatetime(),
            str(row.location_id),
            str(row.location_name),
            str(row.district),
            float(row.latitude),
            float(row.longitude),
            str(row.vehicle_type),
            float(row.speed_kmh),
            str(row.direction),
            str(row.sensor_id),
            ingested_at,
        )
        for row in frame.itertuples()
    ]
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(DDL)
            cursor.executemany(
                """
                INSERT INTO raw.traffic_observations
                    (observation_id, observed_at, location_id, location_name, district,
                     latitude, longitude, vehicle_type, speed_kmh, direction, sensor_id, ingested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (observation_id) DO UPDATE
                SET observed_at=EXCLUDED.observed_at,
                    speed_kmh=EXCLUDED.speed_kmh,
                    ingested_at=EXCLUDED.ingested_at
                """,
                rows,
            )
            cursor.execute(
                "INSERT INTO raw.pipeline_runs (run_at, source_rows, loaded_rows, status) VALUES (%s, %s, %s, 'success')",
                (ingested_at, len(frame), len(rows)),
            )
            cursor.execute("SELECT COUNT(*) AS warehouse_raw_rows FROM raw.traffic_observations")
            count = cursor.fetchone()["warehouse_raw_rows"]
        connection.commit()

    result = {
        "status": "success",
        "source_rows": int(len(frame)),
        "loaded_rows": int(len(rows)),
        "warehouse_raw_rows": int(count),
        "run_at": ingested_at.isoformat(),
    }
    artifact_dir = ROOT / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    (artifact_dir / "load_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load raw traffic observations")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dsn", default=os.getenv("WAREHOUSE_DSN", DEFAULT_DSN))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    load_raw(args.input, args.dsn)

