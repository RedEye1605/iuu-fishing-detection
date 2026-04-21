"""
Shared constants for the IUU Fishing Detection pipeline.

Single source of truth for paths, bounding boxes, flag maps, and event types.
"""

from pathlib import Path

# ===== PATHS =====
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GFW_RAW_DIR = RAW_DIR / "gfw"
ZENODO_RAW_DIR = RAW_DIR / "zenodo"

# ===== INDONESIA BOUNDING BOX =====
INDONESIA_BBOX = {
    "lat_min": -11.5,
    "lat_max": 6.5,
    "lon_min": 95.0,
    "lon_max": 141.5,
}

# ===== FLAG MAP (ISO 3166 standardization) =====
FLAG_MAP = {
    "IDN": "IDN", "INA": "IDN",
    "CHN": "CHN", "CHINA": "CHN",
    "TWN": "TWN", "ROC": "TWN",
    "VNM": "VNM", "VIETNAM": "VNM",
    "MYS": "MYS", "MALAYSIA": "MYS",
    "PHL": "PHL", "PNG": "PNG",
    "THA": "THA", "KOR": "KOR",
    "SGP": "SGP", "LBR": "LBR",
    "PAN": "PAN", "AUS": "AUS",
    "JPN": "JPN", "IND": "IND",
    "SWE": "SWE", "BES": "BES",
    "HKG": "HKG", "KHM": "KHM",
    "MMR": "MMR",
}

# ===== EVENT FLAGS — flags commonly seen in Indonesian waters =====
EVENT_FLAGS = {
    "IDN", "MYS", "CHN", "PAN", "SGP", "SWE", "TWN", "LBR", "BES", "HKG",
    "KOR", "VNM", "THA", "PHL", "PNG", "AUS", "IND", "JPN", "MMR", "KHM",
}

# ===== INPUT FILENAMES =====
GFW_FISHING_FILE = "fishing_events_indonesia_2020-2025.json.gz"
GFW_ENCOUNTERS_FILE = "encounters_indonesia_2020-2024.json.gz"
GFW_LOITERING_FILE = "loitering_indonesia_2020-2025_corrected.json.gz"
GFW_PORT_VISITS_FILE = "port_visits_indonesia_2020-2025.json.gz"
GFW_SAR_FILE = "4wings_sar_presence_indonesia_corrected.json.gz"
GFW_EFFORT_FILE = "4wings_fishing_effort_indonesia_corrected.json.gz"
ZENODO_VESSELS_FILE = "fishing-vessels-v3.csv"
PORTS_FILE = "osm_indonesia_ports_manual.json"

# ===== OUTPUT FILENAMES =====
GFW_EVENTS_FLAT = "gfw_events_flat.parquet"
SAR_PRESENCE_FLAT = "sar_presence_flat.parquet"
FISHING_EFFORT_FLAT = "fishing_effort_flat.parquet"
VESSEL_REGISTRY = "vessel_registry.parquet"
ZENODO_EFFORT_FLAT = "zenodo_effort_flat.parquet"
PORTS_PARQUET = "ports.parquet"

GFW_EVENTS_DEDUP = "gfw_events_dedup.parquet"
SAR_PRESENCE_DEDUP = "sar_presence_dedup.parquet"
FISHING_EFFORT_DEDUP = "fishing_effort_dedup.parquet"
ZENODO_EFFORT_DEDUP = "zenodo_effort_dedup.parquet"
VESSEL_REGISTRY_DEDUP = "vessel_registry_dedup.parquet"

GFW_EVENTS_CLEAN = "gfw_events_clean.parquet"
SAR_PRESENCE_CLEAN = "sar_presence_clean.parquet"
FISHING_EFFORT_CLEAN = "fishing_effort_clean.parquet"
ZENODO_EFFORT_CLEAN = "zenodo_effort_clean.parquet"

GFW_EVENTS_ENRICHED = "gfw_events_enriched.parquet"
VESSEL_BEHAVIORAL = "vessel_behavioral_features.parquet"
GFW_EVENTS_FULL = "gfw_events_full.parquet"
