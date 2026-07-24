from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "raw" / "traffic_observations.csv"

LOCATIONS = [
    ("DN-01", "Dragon Bridge", "Hai Chau", 16.0611, 108.2273, 0.82),
    ("DN-02", "Han River Bridge", "Hai Chau", 16.0718, 108.2268, 0.72),
    ("DN-03", "Nguyen Van Linh", "Hai Chau", 16.0595, 108.2115, 0.91),
    ("DN-04", "Dien Bien Phu", "Thanh Khe", 16.0666, 108.1912, 0.88),
    ("DN-05", "2 September Street", "Hai Chau", 16.0481, 108.2230, 0.77),
    ("DN-06", "Ngo Quyen", "Son Tra", 16.0644, 108.2358, 0.68),
]


def generate_observations(rows: int = 3_600, seed: int = 2026) -> Path:
    rng = random.Random(seed)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1)
    fieldnames = [
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
    ]

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(1, rows + 1):
            location_id, name, district, lat, lon, pressure = rng.choice(LOCATIONS)
            timestamp = start + timedelta(minutes=rng.randrange(0, 60 * 24 * 90))
            hour = timestamp.hour
            peak = 1.0 if 7 <= hour <= 9 or 16 <= hour <= 19 else 0.0
            baseline = 46 - pressure * 12 - peak * pressure * 20
            speed = max(4.0, min(65.0, rng.gauss(baseline, 7)))
            # Small seasonal signal makes hourly marts non-trivial.
            speed += 2.5 * math.sin(timestamp.weekday() / 7 * math.pi * 2)
            writer.writerow(
                {
                    "observation_id": f"OBS-{index:07d}",
                    "observed_at": timestamp.isoformat(sep=" "),
                    "location_id": location_id,
                    "location_name": name,
                    "district": district,
                    "latitude": lat,
                    "longitude": lon,
                    "vehicle_type": rng.choices(
                        ["motorbike", "car", "bus", "truck"], weights=[58, 31, 6, 5], k=1
                    )[0],
                    "speed_kmh": round(speed, 1),
                    "direction": rng.choice(["N", "S", "E", "W"]),
                    "sensor_id": f"CAM-{location_id[-2:]}-{rng.randint(1, 3)}",
                }
            )

    print(f"Generated {rows} deterministic traffic observations at {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    generate_observations()

