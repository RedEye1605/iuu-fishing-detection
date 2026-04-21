"""
Synthetic AIS Data Generator for IUU Fishing Detection.

Generates realistic synthetic AIS vessel tracking data for development
and testing of the ST-GAT model before real data is available.

Generates:
- Normal fishing trajectories in Indonesian waters
- Suspicious/IUU patterns (AIS gaps, zone violations, etc.)
- Multi-vessel interactions (encounters, transshipment)
"""

import logging
import json
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.utils.config import (
    indonesia_config,
    vessel_config,
    synthetic_config
)


# Configure logging
logger = logging.getLogger(__name__)


class SyntheticDataError(Exception):
    """Base exception for synthetic data errors."""
    pass


class AISDataGenerator:
    """Generator for synthetic AIS vessel tracking data."""

    def __init__(self, seed: int = 42):
        """
        Initialize AIS data generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def generate_mmsi(self) -> str:
        """
        Generate a fake Indonesian MMSI (starts with 525).

        Returns:
            MMSI string
        """
        return f"525{random.randint(100000, 999999)}"

    def generate_vessel(self, vessel_type: str):
        """
        Generate vessel metadata.

        Args:
            vessel_type: Type of vessel (fishing, cargo, tanker, passenger)

        Returns:
            Vessel metadata dict
        """
        config = vessel_config.vessel_types.get(vessel_type, vessel_config.vessel_types["fishing"])

        vessel = {
            "mmsi": self.generate_mmsi(),
            "vessel_type": vessel_type,
            "length": random.randint(10, 60) if vessel_type == "fishing" else random.randint(50, 300),
            "tonnage": random.randint(5, 500) if vessel_type == "fishing" else random.randint(500, 50000),
            "flag": "IDN" if random.random() > 0.15 else random.choice(vessel_config.foreign_flags),
        }
        return vessel

    def generate_fishing_trajectory(
        self,
        vessel: dict,
        zone: dict,
        hours: int = 24,
        iuu: bool = False
    ) -> list:
        """
        Generate a realistic fishing vessel trajectory.

        Args:
            vessel: Vessel metadata
            zone: Fishing zone bounds [min_lon, min_lat, max_lon, max_lat]
            hours: Duration of trajectory in hours
            iuu: Whether to generate IUU pattern

        Returns:
            List of trajectory points
        """
        bounds = zone["bounds"]
        start_lon = random.uniform(bounds[0], bounds[2])
        start_lat = random.uniform(bounds[1], bounds[3])

        config = vessel_config.vessel_types.get(
            vessel["vessel_type"],
            vessel_config.vessel_types["fishing"]
        )

        points = []
        t = datetime(2024, random.randint(1, 12), random.randint(1, 28), 0, 0, 0)
        lon, lat = start_lon, start_lat

        speed = config["speed_max"] * random.uniform(0.3, 0.7)
        heading = random.uniform(0, 360)
        interval_minutes = synthetic_config.ais_interval_minutes

        # Total steps
        total_steps = int(hours * 60 / interval_minutes)

        for i in range(total_steps):
            # Decide behavior: transiting, fishing, or drifting
            behavior = "fishing" if random.random() < 0.6 else "transiting"

            if behavior == "fishing":
                speed = config["speed_fishing"] * random.uniform(0.5, 1.5)
                heading += random.gauss(0, config["turn_rate"] * 30)
            else:
                speed = config["speed_max"] * random.uniform(0.4, 0.8)
                heading += random.gauss(0, config["turn_rate"] * 5)

            # IUU patterns
            if iuu:
                # Pattern 1: AIS gap (transponder off)
                if random.random() < 0.02:
                    gap_hours = random.randint(2, 12)
                    t += timedelta(hours=gap_hours)
                    # Jump position during gap
                    lon += random.uniform(-0.5, 0.5)
                    lat += random.uniform(-0.3, 0.3)

                # Pattern 2: Entering restricted area
                if random.random() < 0.005:
                    lon += random.uniform(-0.1, 0.1)
                    lat += random.uniform(-0.1, 0.1)

                # Pattern 3: Unusual speed changes (rendezvous)
                if random.random() < 0.01:
                    speed = 0.1  # Near-stationary

            # Update position using basic kinematics
            rad_heading = np.radians(heading)
            # Convert speed from knots to km/h then to degrees
            # 1 knot ≈ 1.852 km/h
            speed_kmh = speed * 1.852
            lon += speed_kmh * np.sin(rad_heading) * interval_minutes / 3600 * 0.01
            lat += speed_kmh * np.cos(rad_heading) * interval_minutes / 3600 * 0.01

            # Keep in bounds
            lon = np.clip(lon, bounds[0], bounds[2])
            lat = np.clip(lat, bounds[1], bounds[3])

            point = {
                "mmsi": vessel["mmsi"],
                "timestamp": t.isoformat(),
                "lon": round(float(lon), 6),
                "lat": round(float(lat), 6),
                "speed": round(speed, 2),
                "heading": round(heading % 360, 2),
                "behavior": behavior,
                "zone": zone["name"],
                "is_iuu": iuu
            }
            points.append(point)
            t += timedelta(minutes=interval_minutes)

        return points

    def generate_dataset(
        self,
        n_normal: int = None,
        n_iuu: int = None
    ) -> tuple:
        """
        Generate full dataset with normal and IUU trajectories.

        Args:
            n_normal: Number of normal vessels (default: from config)
            n_iuu: Number of IUU vessels (default: from config)

        Returns:
            DataFrame with trajectory points and vessels metadata
        """
        if n_normal is None:
            n_normal = synthetic_config.n_normal_vessels
        if n_iuu is None:
            n_iuu = synthetic_config.n_iuu_vessels

        all_points = []
        vessels = []

        # Generate normal vessels
        for vtype, config in vessel_config.vessel_types.items():
            count = int(config["count"] * n_normal / 500)
            for i in range(count):
                vessel = self.generate_vessel(vtype)
                vessels.append(vessel)

                zone = random.choice(indonesia_config.fishing_zones)
                hours = random.randint(8, 48)
                is_iuu = False
                points = self.generate_fishing_trajectory(vessel, zone, hours, iuu=is_iuu)
                all_points.extend(points)

        # Generate IUU vessels
        for i in range(n_iuu):
            vessel = self.generate_vessel("fishing")
            vessel["flag"] = random.choice(vessel_config.foreign_flags)  # Foreign flag = suspicious
            vessel["is_iuu"] = True
            vessels.append(vessel)

            zone = random.choice(indonesia_config.fishing_zones)
            hours = random.randint(12, 72)
            points = self.generate_fishing_trajectory(vessel, zone, hours, iuu=True)
            all_points.extend(points)

        # Create DataFrame
        df = pd.DataFrame(all_points)
        logger.info(f"Generated {len(df)} trajectory points from {len(vessels)} vessels")

        return df, vessels


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    generator = AISDataGenerator()
    df, vessels = generator.generate_dataset()

    print("\nDataset Statistics:")
    iuu_count = sum(1 for v in vessels if v.get("is_iuu"))
    print(f"  Total points: {len(df)}")
    print(f"  Total vessels: {len(vessels)}")
    print(f"  IUU vessels: {iuu_count}")
    print(f"  Normal vessels: {len(vessels) - iuu_count}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
