"""Centralized configuration for the IUU fishing detection system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class AppConfig:
    """Application-level paths."""

    project_root: Path
    data_root: Path
    output_dir: Path

    @classmethod
    def from_env(cls) -> AppConfig:
        root = Path(os.getenv("GEMASTIK_ROOT", str(Path(__file__).parent.parent.parent)))
        data = root / "data"
        return cls(project_root=root, data_root=data, output_dir=data / "processed")


@dataclass
class GFWConfig:
    """Global Fishing Watch API configuration."""

    api_base: str = "https://api.globalfishingwatch.org/v3"
    gateway_base: str = "https://gateway.api.globalfishingwatch.org/v3"
    token_file: str = str(Path.home() / ".openclaw" / ".gfw_token")
    default_dataset: str = "public-fishing-event"
    default_output: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.default_output is None:
            self.default_output = Path("data/raw/gfw")

    @classmethod
    def load_token(cls) -> Optional[str]:
        """Load API token from file."""
        p = Path(cls.token_file)
        return p.read_text().strip() if p.exists() else None


@dataclass
class BPSConfig:
    """BPS (Badan Pusat Statistik) configuration."""

    api_key_env: str = "BPS_API_KEY"
    api_base: str = "https://webapi.bps.go.id/v1/api/list/model/data"

    @classmethod
    def load_api_key(cls) -> Optional[str]:
        return os.getenv(cls.api_key_env)


@dataclass
class VIIRSConfig:
    """VIIRS VBD data configuration."""

    download_base: str = "https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/idn/final"
    monthly_base: str = "https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/idn/monthly"
    quality_flags: dict[int, str] = field(default_factory=lambda: {
        1: "Boat", 2: "Weak Detection", 3: "Blurry Detection",
        4: "Gas Flare", 7: "Glow", 8: "Recurring Light",
        10: "Weak and Blurry", 11: "Platform",
    })


@dataclass
class BMKGConfig:
    """BMKG weather API configuration."""

    api_base: str = "https://data.bmkg.go.id/DataMKG/MEWS/DigitalForecast/"


@dataclass
class MPAConfig:
    """Marine Protected Area data sources."""

    sources: list[str] = field(default_factory=lambda: [
        "https://www.protectedplanet.net/country/IDN",
        "https://old.mpatlas.org/data/download/",
    ])


@dataclass
class IndonesiaConfig:
    """Indonesia EEZ boundaries and fishing zones."""

    eez_bounds: dict[str, float] = field(default_factory=lambda: {
        "min_lon": 95.0, "max_lon": 141.0,
        "min_lat": -11.0, "max_lat": 6.0,
    })
    eez_region_id: int = 8371
    fishing_zones: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "Malacca Strait", "bounds": [98, 2, 104, 6], "fishing_density": 0.8},
        {"name": "South China Sea", "bounds": [105, -3, 117, 5], "fishing_density": 0.9},
        {"name": "Java Sea", "bounds": [105, -8, 117, -3], "fishing_density": 0.95},
        {"name": "Celebes Sea", "bounds": [117, -3, 125, 5], "fishing_density": 0.7},
        {"name": "Banda Sea", "bounds": [119, -8, 133, -3], "fishing_density": 0.65},
        {"name": "Arafura Sea", "bounds": [131, -11, 141, -5], "fishing_density": 0.85},
        {"name": "Indian Ocean (West)", "bounds": [95, -11, 105, -5], "fishing_density": 0.6},
    ])


@dataclass
class VesselConfig:
    """Vessel type definitions for synthetic data generation."""

    vessel_types: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "fishing": {"speed_max": 12, "speed_fishing": 2.5, "turn_rate": 0.3, "count": 500},
        "cargo": {"speed_max": 18, "speed_fishing": 14, "turn_rate": 0.05, "count": 200},
        "tanker": {"speed_max": 15, "speed_fishing": 12, "turn_rate": 0.05, "count": 100},
        "passenger": {"speed_max": 22, "speed_fishing": 18, "turn_rate": 0.08, "count": 50},
    })
    foreign_flags: list[str] = field(default_factory=lambda: [
        "CHN", "VNM", "PHL", "MYS", "THA", "PNG",
    ])


@dataclass
class SyntheticConfig:
    """Synthetic data generation defaults."""

    n_normal_vessels: int = 300
    n_iuu_vessels: int = 50
    ais_interval_minutes: int = 5
    seed: int = 42


# Global singletons
app_config = AppConfig.from_env()
gfw_config = GFWConfig()
bps_config = BPSConfig()
viirs_config = VIIRSConfig()
bmkg_config = BMKGConfig()
mpa_config = MPAConfig()
indonesia_config = IndonesiaConfig()
vessel_config = VesselConfig()
synthetic_config = SyntheticConfig()
