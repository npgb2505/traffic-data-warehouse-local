from pathlib import Path

import pandas as pd

from src import generate_data


def test_generator_is_deterministic_and_valid(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "traffic.csv"
    monkeypatch.setattr(generate_data, "OUTPUT", output)
    generate_data.generate_observations(rows=20, seed=42)
    first = pd.read_csv(output)
    generate_data.generate_observations(rows=20, seed=42)
    second = pd.read_csv(output)
    pd.testing.assert_frame_equal(first, second)
    assert first["speed_kmh"].between(0, 180).all()
    assert first["observation_id"].is_unique

