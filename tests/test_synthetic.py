"""Tests for src.data.synthetic."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.synthetic import generate_dataset, generate_vessel


class TestGenerateVessel:
    """Vessel metadata generation."""

    def test_fishing_vessel(self) -> None:
        v = generate_vessel("fishing")
        assert v["vessel_type"] == "fishing"
        assert v["mmsi"].startswith("525")
        assert 10 <= v["length"] <= 60

    def test_cargo_vessel(self) -> None:
        v = generate_vessel("cargo")
        assert v["vessel_type"] == "cargo"
        assert 50 <= v["length"] <= 300


class TestGenerateDataset:
    """Full dataset generation."""

    def test_generates_data(self) -> None:
        df, vessels = generate_dataset(n_normal=5, n_iuu=2)
        assert isinstance(df, pd.DataFrame)
        assert len(vessels) > 0
        assert "mmsi" in df.columns
        assert "is_iuu" in df.columns

    def test_iuu_vessels_present(self) -> None:
        _, vessels = generate_dataset(n_normal=5, n_iuu=3)
        iuu = [v for v in vessels if v.get("is_iuu")]
        assert len(iuu) == 3
