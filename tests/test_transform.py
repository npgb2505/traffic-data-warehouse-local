import pandas as pd

from src.load_raw import transform_frame


def test_transform_quarantines_invalid_measurements() -> None:
    frame = pd.DataFrame(
        [
            {
                "holiday": None,
                "temp": 280.0,
                "rain_1h": 0.0,
                "snow_1h": 0.0,
                "clouds_all": 40,
                "weather_main": "Clouds",
                "weather_description": "scattered clouds",
                "date_time": "2018-01-01 08:00:00",
                "traffic_volume": 4200,
            },
            {
                "holiday": None,
                "temp": 280.0,
                "rain_1h": -1.0,
                "snow_1h": 0.0,
                "clouds_all": 40,
                "weather_main": "Rain",
                "weather_description": "light rain",
                "date_time": "2018-01-01 09:00:00",
                "traffic_volume": 3900,
            },
        ]
    )
    clean, rejected, summary = transform_frame(frame, "test")
    assert len(clean) == 1
    assert len(rejected) == 1
    assert summary["distinct_observations"] == 1
    assert rejected["rejection_reason"].item() == "invalid_measurement"
