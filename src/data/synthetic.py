"""
Synthetic AIS data generator for IUU fishing detection.

Generates realistic vessel tracking trajectories including:
- Normal fishing patterns across Indonesian fishing zones
- IUU patterns (AIS gaps, zone violations, rendezvous)
- Multi-vessel types (fishing, cargo, tanker, passenger)

Used for development and testing before real AIS data is available.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import indonesia_config, vessel_config

logger = logging.getLogger(__name__)

FISHING_ZONES = indonesia_config.fishing_zones
VESSEL_TYPES = vessel_config.vessel_types


def generate_mmsi() -> str:
    """Generate a fake Indonesian MMSI (starts with 525)."""
    return f"525{random.randint(100000, 999999)}"


def generate_vessel(vessel_type: str) -> dict[str, Any]:
    """Create vessel metadata with random attributes.

    Args:
        vessel_type: One of the keys in vessel_config.vessel_types.

    Returns:
        Dict with mmsi, vessel_type, length, tonnage, flag.
    """
    is_fishing = vessel_type == "fishing"
    return {
        "mmsi": generate_mmsi(),
        "vessel_type": vessel_type,
        "length": random.randint(10, 60) if is_fishing else random.randint(50, 300),
        "tonnage": random.randint(5, 500) if is_fishing else random.randint(500, 50000),
        "flag": "IDN" if random.random() > 0.15 else random.choice(vessel_config.foreign_flags),
    }


def generate_fishing_trajectory(
    vessel: dict[str, Any],
    zone: dict[str, Any],
    hours: int = 24,
    iuu: bool = False,
    interval_minutes: int = 5,
) -> list[dict[str, Any]]:
    """Generate a realistic vessel trajectory.

    Args:
        vessel: Vessel metadata dict.
        zone: Fishing zone dict with bounds and name.
        hours: Duration of the trajectory.
        iuu: Whether to inject IUU patterns.
        interval_minutes: AIS reporting interval.

    Returns:
        List of trajectory point dicts.
    """
    bounds = zone["bounds"]
    config = VESSEL_TYPES.get(vessel["vessel_type"], VESSEL_TYPES["fishing"])
    lon = random.uniform(bounds[0], bounds[2])
    lat = random.uniform(bounds[1], bounds[3])
    speed = config["speed_max"] * random.uniform(0.3, 0.7)
    heading = random.uniform(0, 360)
    t = datetime(2024, random.randint(1, 12), random.randint(1, 28))

    points: list[dict[str, Any]] = []
    for _ in range(int(hours * 60 / interval_minutes)):
        behavior = "fishing" if random.random() < 0.6 else "transiting"

        if behavior == "fishing":
            speed = config["speed_fishing"] * random.uniform(0.5, 1.5)
            heading += random.gauss(0, config["turn_rate"] * 30)
        else:
            speed = config["speed_max"] * random.uniform(0.4, 0.8)
            heading += random.gauss(0, config["turn_rate"] * 5)

        if iuu:
            # AIS gap (transponder off)
            if random.random() < 0.02:
                t += timedelta(hours=random.randint(2, 12))
                lon += random.uniform(-0.5, 0.5)
                lat += random.uniform(-0.3, 0.3)
            # Zone violation drift
            if random.random() < 0.005:
                lon += random.uniform(-0.1, 0.1)
                lat += random.uniform(-0.1, 0.1)
            # Rendezvous (near-stationary)
            if random.random() < 0.01:
                speed = 0.1

        rad = np.radians(heading)
        lon += speed * np.sin(rad) * interval_minutes / 3600 * 0.01
        lat += speed * np.cos(rad) * interval_minutes / 3600 * 0.01
        lon = np.clip(lon, bounds[0], bounds[2])
        lat = np.clip(lat, bounds[1], bounds[3])

        points.append({
            "mmsi": vessel["mmsi"],
            "timestamp": t.isoformat(),
            "lon": round(float(lon), 6),
            "lat": round(float(lat), 6),
            "speed": round(speed, 2),
            "heading": round(heading % 360, 2),
            "behavior": behavior,
            "zone": zone["name"],
            "is_iuu": iuu,
        })
        t += timedelta(minutes=interval_minutes)

    return points


def generate_dataset(
    n_normal: int = 300,
    n_iuu: int = 50,
    seed: int = 42,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Generate a full dataset of normal and IUU trajectories.

    Args:
        n_normal: Number of normal vessels (scaled by vessel type ratios).
        n_iuu: Number of IUU vessels.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (trajectory DataFrame, vessel metadata list).
    """
    np.random.seed(seed)
    random.seed(seed)

    all_points: list[dict[str, Any]] = []
    vessels: list[dict[str, Any]] = []

    for vtype, config in VESSEL_TYPES.items():
        count = int(config["count"] * n_normal / 500)
        for _ in range(count):
            vessel = generate_vessel(vtype)
            vessels.append(vessel)
            zone = random.choice(FISHING_ZONES)
            points = generate_fishing_trajectory(vessel, zone, random.randint(8, 48))
            all_points.extend(points)

    for _ in range(n_iuu):
        vessel = generate_vessel("fishing")
        vessel["flag"] = random.choice(["CHN", "VNM", "PHL", "MYS"])
        vessel["is_iuu"] = True
        vessels.append(vessel)
        zone = random.choice(FISHING_ZONES)
        points = generate_fishing_trajectory(vessel, zone, random.randint(12, 72), iuu=True)
        all_points.extend(points)

    return pd.DataFrame(all_points), vessels


def main() -> None:
    """CLI entry-point: generate and save synthetic dataset."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Generating synthetic AIS dataset...")
    df, vessels = generate_dataset()

    output_dir = Path("data/raw/omtad")
    output_dir.mkdir(parents=True, exist_ok=True)

    traj_path = output_dir / "synthetic_ais_trajectories.csv"
    df.to_csv(traj_path, index=False)
    logger.info("Trajectories saved: %s (%d points)", traj_path, len(df))

    vessels_path = output_dir / "synthetic_vessels.json"
    vessels_path.write_text(json.dumps(vessels, indent=2))
    logger.info("Vessels saved: %s (%d vessels)", vessels_path, len(vessels))

    iuu_count = sum(1 for v in vessels if v.get("is_iuu"))
    print(f"\nDataset: {len(df)} points, {len(vessels)} vessels ({iuu_count} IUU)")


if __name__ == "__main__":
    main()
