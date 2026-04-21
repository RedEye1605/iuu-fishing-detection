"""Tests for src.utils.config."""

from __future__ import annotations

from src.utils.config import (
    AppConfig,
    IndonesiaConfig,
    VesselConfig,
    app_config,
    indonesia_config,
    vessel_config,
)


class TestAppConfig:
    """AppConfig creation and paths."""

    def test_from_env_sets_paths(self) -> None:
        cfg = AppConfig.from_env()
        assert cfg.project_root.exists()
        assert cfg.data_root == cfg.project_root / "data"

    def test_singleton_has_data_root(self) -> None:
        assert app_config.data_root.name == "data"


class TestIndonesiaConfig:
    """Indonesia boundaries and zones."""

    def test_eez_bounds(self) -> None:
        b = indonesia_config.eez_bounds
        assert b["min_lon"] < b["max_lon"]
        assert b["min_lat"] < b["max_lat"]

    def test_fishing_zones_nonempty(self) -> None:
        assert len(indonesia_config.fishing_zones) >= 5
        for z in indonesia_config.fishing_zones:
            assert "name" in z and "bounds" in z


class TestVesselConfig:
    """Vessel type definitions."""

    def test_fishing_exists(self) -> None:
        assert "fishing" in vessel_config.vessel_types

    def test_foreign_flags_nonempty(self) -> None:
        assert len(vessel_config.foreign_flags) >= 3
