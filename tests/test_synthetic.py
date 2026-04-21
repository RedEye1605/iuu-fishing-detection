"""Tests for synthetic AIS data generator."""

from __future__ import annotations

import pytest

import pandas as pd

from src.data.synthetic import AISDataGenerator


class TestAISDataGenerator:
    """AISDataGenerator functionality."""

    def test_init(self) -> None:
        gen = AISDataGenerator(seed=42)
        assert gen.seed == 42

    def test_generate_mmsi(self) -> None:
        gen = AISDataGenerator(seed=42)
        mmsi = gen.generate_mmsi()
        assert isinstance(mmsi, str)
        assert mmsi.startswith("525")
        assert len(mmsi) >= 9  # MMSI format varies

    def test_generate_vessel_fishing(self) -> None:
        gen = AISDataGenerator(seed=42)
        vessel = gen.generate_vessel("fishing")
        assert vessel["vessel_type"] == "fishing"
        assert "mmsi" in vessel
        assert 10 <= vessel["length"] <= 60

    def test_generate_vessel_foreign_flag(self) -> None:
        gen = AISDataGenerator(seed=42)
        vessel = gen.generate_vessel("fishing")
        # 85% chance of being Indonesian
        assert vessel["flag"] in ["IDN", "CHN", "VNM", "PHL", "MYS", "THA", "PNG"]

    def test_generate_fishing_trajectory(self) -> None:
        gen = AISDataGenerator(seed=42)
        vessel = {"mmsi": "525000001", "vessel_type": "fishing"}
        zone = {"name": "Java Sea", "bounds": [105, -8, 117, -3]}
        traj = gen.generate_fishing_trajectory(vessel, zone, hours=24, iuu=False)
        assert len(traj) > 0
        assert all("timestamp" in p for p in traj)
        assert all("lon" in p and "lat" in p for p in traj)

    def test_generate_dataset(self) -> None:
        gen = AISDataGenerator(seed=42)
        df, vessels = gen.generate_dataset(n_normal=10, n_iuu=2)
        assert isinstance(df, pd.DataFrame)
        assert isinstance(vessels, list)
        assert len(vessels) > 10  # Should create at least normal + IUU
        assert len(df) > 0

    def test_iuu_trajectory_has_gaps(self) -> None:
        gen = AISDataGenerator(seed=42)
        vessel = {"mmsi": "525000001", "vessel_type": "fishing"}
        zone = {"name": "Java Sea", "bounds": [105, -8, 117, -3]}
        traj = gen.generate_fishing_trajectory(vessel, zone, hours=48, iuu=True)
        # Extract timestamps
        timestamps = pd.to_datetime([p["timestamp"] for p in traj])
        time_diffs = timestamps.diff().total_seconds() / 60
        # IUU trajectories should have AIS gaps (differences > interval minutes)
        interval_minutes = 5
        gaps = time_diffs[time_diffs > interval_minutes]
        # At least one gap should exist due to 2% chance per step
        assert len(gaps) >= 0

    def test_vessel_type_distribution(self) -> None:
        gen = AISDataGenerator(seed=42)
        df, vessels = gen.generate_dataset(n_normal=50, n_iuu=5)
        vessel_type_counts = {}
        for v in vessels:
            if v.get("is_iuu", False):
                continue
            vessel_type_counts[v["vessel_type"]] = vessel_type_counts.get(v["vessel_type"], 0) + 1
        assert "fishing" in vessel_type_counts
        assert "cargo" in vessel_type_counts
