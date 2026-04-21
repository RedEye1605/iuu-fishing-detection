"""
MPA (Marine Protected Area) data setup for Indonesia.

Generates sample MPA boundary data for development. Real data available from:
- Protected Planet / WDPA: https://www.protectedplanet.net/country/IDN
- MPAtlas: https://mpatlas.org/
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

KNOWN_MPAS: list[dict[str, Any]] = [
    {"name": "Taman Nasional Komodo", "type": "National Park", "lon": 119.5, "lat": -8.55, "area_km2": 1733},
    {"name": "Taman Nasional Bunaken", "type": "National Park", "lon": 124.75, "lat": 1.62, "area_km2": 890},
    {"name": "Taman Nasional Wakatobi", "type": "National Park", "lon": 123.6, "lat": -5.3, "area_km2": 1390},
    {"name": "Taman Nasional Karimunjawa", "type": "National Park", "lon": 110.4, "lat": -5.85, "area_km2": 1116},
    {"name": "Taman Nasional Teluk Cenderawasih", "type": "National Park", "lon": 134.9, "lat": -2.7, "area_km2": 14535},
    {"name": "Taman Nasional Kepulauan Seribu", "type": "National Park", "lon": 106.5, "lat": -5.6, "area_km2": 1079},
    {"name": "Taman Nasional Ujung Kulon", "type": "National Park", "lon": 105.33, "lat": -6.75, "area_km2": 1206},
    {"name": "Cenderawasih Bay MPA", "type": "Marine Sanctuary", "lon": 135.5, "lat": -3.0, "area_km2": 5000},
    {"name": "Raja Ampat MPA Network", "type": "Marine Sanctuary", "lon": 130.5, "lat": -0.5, "area_km2": 46000},
    {"name": "Savu Sea MPA", "type": "Marine Sanctuary", "lon": 122.0, "lat": -9.0, "area_km2": 33597},
    {"name": "Banda Sea MPA", "type": "Marine Sanctuary", "lon": 129.0, "lat": -5.0, "area_km2": 50000},
    {"name": "Bird's Head Seascape", "type": "Marine Sanctuary", "lon": 131.0, "lat": -1.5, "area_km2": 36000},
]


def generate_sample_mpa_data(
    output_dir: Path,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate sample MPA boundaries with bounding boxes.

    Args:
        output_dir: Directory to write JSON/GeoJSON output.
        seed: Random seed for reproducibility.

    Returns:
        List of MPA dicts with added bbox and is_no_take fields.
    """
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    mpas: list[dict[str, Any]] = []
    for mpa in KNOWN_MPAS:
        size = np.sqrt(mpa["area_km2"]) / 111  # rough degree conversion
        bbox = [
            round(mpa["lon"] - size / 2, 4),
            round(mpa["lat"] - size / 2, 4),
            round(mpa["lon"] + size / 2, 4),
            round(mpa["lat"] + size / 2, 4),
        ]
        mpas.append({**mpa, "bbox": bbox, "is_no_take": random.random() < 0.3})

    # Save JSON
    json_path = output_dir / "indonesia_mpa_sample.json"
    json_path.write_text(json.dumps(mpas, indent=2))
    logger.info("Sample MPA data saved: %s (%d MPAs)", json_path, len(mpas))

    # Save GeoJSON
    features = [
        {
            "type": "Feature",
            "properties": {
                "name": m["name"],
                "type": m["type"],
                "area_km2": m["area_km2"],
                "is_no_take": m["is_no_take"],
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [m["bbox"][0], m["bbox"][1]],
                    [m["bbox"][2], m["bbox"][1]],
                    [m["bbox"][2], m["bbox"][3]],
                    [m["bbox"][0], m["bbox"][3]],
                    [m["bbox"][0], m["bbox"][1]],
                ]],
            },
        }
        for m in mpas
    ]
    geojson: dict[str, Any] = {"type": "FeatureCollection", "features": features}
    geojson_path = output_dir / "indonesia_mpa_sample.geojson"
    geojson_path.write_text(json.dumps(geojson, indent=2))
    logger.info("GeoJSON saved: %s", geojson_path)

    return mpas


def main() -> None:
    """CLI entry-point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_sample_mpa_data(Path("data/raw/gis"))


if __name__ == "__main__":
    main()
