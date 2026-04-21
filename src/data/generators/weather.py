"""
BMKG marine weather data client.

Generates synthetic maritime weather data for Indonesian waters based on
monsoon patterns. Real data available from:
- BMKG API: https://data.bmkg.go.id/ (free, no registration)
- BMKG Marine: https://maritim.bmkg.go.id/
"""

from __future__ import annotations

import csv
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

WEATHER_ZONES: list[dict[str, Any]] = [
    {"name": "Malacca Strait", "lon": 101, "lat": 3},
    {"name": "South China Sea", "lon": 110, "lat": 2},
    {"name": "Java Sea West", "lon": 108, "lat": -6},
    {"name": "Java Sea East", "lon": 115, "lat": -5},
    {"name": "Celebes Sea", "lon": 121, "lat": 2},
    {"name": "Banda Sea", "lon": 128, "lat": -5},
    {"name": "Arafura Sea", "lon": 136, "lat": -7},
    {"name": "Indian Ocean South", "lon": 100, "lat": -7},
]


def generate_sample_marine_weather(
    output_dir: Path,
    n_days: int = 365,
    start_date: str = "2024-01-01",
    seed: int = 42,
) -> Path:
    """Generate synthetic marine weather with seasonal monsoon variation.

    Args:
        output_dir: Directory to write output CSV.
        n_days: Number of days to generate.
        start_date: ISO date string for the first record.
        seed: Random seed for reproducibility.

    Returns:
        Path to the generated CSV file.
    """
    random.seed(seed)
    np.random.seed(seed)

    start = datetime.fromisoformat(start_date)
    records: list[dict[str, Any]] = []

    for day in range(n_days):
        date = start + timedelta(days=day)
        month = date.month

        for zone in WEATHER_ZONES:
            # Monsoon-based variation
            if month in (12, 1, 2):  # NW Monsoon
                wind_base = 15 + abs(zone["lat"]) * 0.3
                wave_base = 1.5 + random.uniform(0, 1.5)
            elif month in (6, 7, 8):  # SE Monsoon
                wind_base = 12 + random.uniform(0, 5)
                wave_base = 1.2 + random.uniform(0, 1.0)
            else:  # Transition
                wind_base = 8 + random.uniform(0, 4)
                wave_base = 0.8 + random.uniform(0, 0.8)

            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "zone": zone["name"],
                "lon": zone["lon"],
                "lat": zone["lat"],
                "wind_speed_knots": round(max(0, wind_base + random.gauss(0, 3)), 1),
                "wave_height_m": round(max(0.1, wave_base + random.gauss(0, 0.3)), 2),
                "sea_surface_temp_c": round(28 + random.uniform(-2, 2), 1),
                "visibility_km": round(max(1, 10 + random.gauss(0, 3)), 1),
                "precipitation_mm": round(max(0, random.gauss(5, 8)), 1),
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "marine_weather_2024.csv"

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    logger.info("Marine weather data saved: %s (%d records)", output_path, len(records))
    return output_path


def main() -> None:
    """CLI entry-point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_sample_marine_weather(Path("data/raw/bmkg"))


if __name__ == "__main__":
    main()
