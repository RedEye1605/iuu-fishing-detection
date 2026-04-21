"""
VIIRS Boat Detection (VBD) data setup.

Generates synthetic VBD detections for development and provides download
instructions for real EOG data.

Register at: https://eogdata.mines.edu/ for free access to VIIRS products.
"""

from __future__ import annotations

import csv
import json
import logging
import random
from pathlib import Path
from typing import Any

import numpy as np

from src.utils.config import viirs_config

logger = logging.getLogger(__name__)

HOTSPOTS: list[dict[str, Any]] = [
    {"name": "Java Sea", "lon_range": (108, 115), "lat_range": (-7, -4), "weight": 0.3},
    {"name": "Malacca Strait", "lon_range": (100, 104), "lat_range": (1, 4), "weight": 0.2},
    {"name": "Celebes Sea", "lon_range": (119, 124), "lat_range": (-2, 4), "weight": 0.15},
    {"name": "Arafura Sea", "lon_range": (133, 140), "lat_range": (-9, -5), "weight": 0.15},
    {"name": "South China Sea", "lon_range": (108, 117), "lat_range": (-3, 3), "weight": 0.1},
    {"name": "Indian Ocean", "lon_range": (97, 105), "lat_range": (-9, -4), "weight": 0.1},
]

DOWNLOAD_INSTRUCTIONS = """
VIIRS VBD DATA DOWNLOAD INSTRUCTIONS
======================================
1. Register at https://eogdata.mines.edu/ (free account)
2. Navigate to: https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/
3. For Indonesia data: /idn/final/ (nightly CSV) or /idn/monthly/ (GeoTIFF)
4. Download files matching: VBD_npp_d2024*_idn_noaa_ops_v23.csv
5. Place downloaded files in data/raw/viirs/
"""


def generate_sample_vbd_data(
    output_dir: Path,
    n_detections: int = 5000,
    seed: int = 42,
) -> Path:
    """Generate synthetic VBD detections for development.

    Args:
        output_dir: Directory to write output files.
        n_detections: Number of detections to generate.
        seed: Random seed for reproducibility.

    Returns:
        Path to the generated CSV file.
    """
    random.seed(seed)
    np.random.seed(seed)

    detections: list[dict[str, Any]] = []
    for i in range(n_detections):
        zone = random.choices(HOTSPOTS, weights=[h["weight"] for h in HOTSPOTS])[0]
        lon = random.uniform(*zone["lon_range"])
        lat = random.uniform(*zone["lat_range"])
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        qf = random.choices([1, 2, 3, 8, 10], weights=[0.5, 0.2, 0.1, 0.15, 0.05])[0]

        detections.append({
            "id": i + 1,
            "date_gmt": f"2024{month:02d}{day:02d}",
            "time_gmt": f"{hour:02d}{random.randint(0, 59):02d}",
            "lon": round(lon, 4),
            "lat": round(lat, 4),
            "quality_flag": qf,
            "radiance": round(random.uniform(0.5, 50.0), 3),
            "zone": zone["name"],
        })

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "sample_vbd_detections_2024.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detections[0].keys())
        writer.writeheader()
        writer.writerows(detections)
    logger.info("Generated %d VBD detections → %s", n_detections, csv_path)

    ref_path = output_dir / "fishing_hotspots.json"
    ref_path.write_text(json.dumps(HOTSPOTS, indent=2))

    return csv_path


def main() -> None:
    """CLI entry-point: generate sample data and instructions."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    output_dir = Path("data/raw/viirs")
    generate_sample_vbd_data(output_dir)

    instructions_path = output_dir / "DOWNLOAD_INSTRUCTIONS.txt"
    instructions_path.write_text(DOWNLOAD_INSTRUCTIONS)
    logger.info("Download instructions saved.")


if __name__ == "__main__":
    main()
