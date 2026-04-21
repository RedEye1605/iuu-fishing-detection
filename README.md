# 🐟 IUU Fishing Detection using ST-GAT

## Gemastik XIX 2026 — Data Analytics Category

> **Spatiotemporal Graph Attention Network for Illegal, Unreported, and Unregulated (IUU) Fishing Detection in Indonesian Waters**

---

## 🎯 Overview

Deep learning system to detect IUU fishing in Indonesian waters by analyzing vessel tracking (AIS), satellite detections (VIIRS/SAR), and maritime contextual data using a **Spatiotemporal Graph Attention Network (ST-GAT)**.

### Key Innovation
- **Graph-based modeling** — Vessels as nodes, spatial proximity as edges
- **Temporal attention** — Capture behavioral patterns over time
- **Multi-source fusion** — AIS + SAR + VIIRS + weather + zone boundaries
- **Explainability** — Identify *why* a vessel is flagged as IUU

---

## 👥 Team

- **Toni**
- **Nafi**
- **Rhendy**

---

## 📁 Project Structure

```
gemastik/
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loaders.py              # Phase 1: GFW events loader
│   │   ├── loaders_sar_effort.py    # Phase 1: SAR & fishing effort loader
│   │   ├── loaders_aux.py          # Phase 1: Auxiliary data loader (weather, VIIRS, ports, registry)
│   │   ├── gfw_client.py        # GFW API client (events, SAR, effort)
│   │   ├── bps_client.py        # BPS fisheries statistics
│   │   ├── synthetic.py         # Synthetic AIS data generator
│   │   ├── viirs_setup.py       # VIIRS boat detection setup
│   │   ├── mpa_setup.py         # Marine Protected Area boundaries
│   │   └── weather_client.py    # BMKG marine weather data
│   ├── features/
│   │   └── graph_builder.py     # ST-GAT graph construction (Phase 2)
│   ├── models/
│   │   └── stgat.py             # ST-GAT model architecture (Phase 3)
│   └── utils/
│       ├── config.py            # Centralized configuration
│       └── geo_utils.py         # Geospatial utility functions
├── scripts/
│   ├── pull_sar_data.py         # GFW 4Wings SAR data puller
│   └── download_large_data.sh   # Zenodo data download helper
├── archive/                     # Deprecated script versions
├── notebooks/                   # Jupyter exploration notebooks
├── tests/                       # Unit tests
├── docs/                        # Research plan & data source docs
├── data/                        # Raw & processed data (gitignored)
├── .env.example                 # Environment variable template
├── pyproject.toml               # Package metadata & dependencies
└── README.md
```

---

## 🚀 Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation
```bash
cd gemastik
uv venv .venv --python 3.12
source .venv/bin/activate

# Core dependencies
uv pip install -e ".[dev]"

# ML pipeline (Phase 2/3)
uv pip install -e ".[ml]"
```

### Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Download Large Datasets (>100MB)

Zenodo historical effort files are distributed via [GitHub Release](https://github.com/RedEye1605/iuu-fishing-detection/releases/tag/v1.0-data).

```bash
# Option 1: Setup script (requires gh CLI)
./scripts/download_large_data.sh

# Option 2: Manual download from the release page → data/raw/zenodo/
```

---

## 📊 Data Status

| Dataset | Records | Coverage |
|---------|---------|----------|
| GFW Events | 512,272 | 2016–2025 |
| GFW SAR Presence | 1,242,915 | 2020–2025 |
| GFW Fishing Effort | 890,411 | 2020–2025 |
| EEZ Shapefiles | v12 | Global |
| Indonesia Ports | 30 ports | — |
| BMKG Weather | 2,921 rows | 2024 |
| VIIRS Sample | 5,001 | — |

Full report: [DATA_COMPLETENESS_REPORT.md](DATA_COMPLETENESS_REPORT.md)

### Phase 1: Load & Flatten ✅ COMPLETE
8 Parquet files in `data/processed/` ready for Phase 2 cleaning:

| File | Size | Rows | Description |
|------|------|------|-------------|
| `gfw_events_flat.parquet` | 64MB | 512K | All GFW events (fishing, encounters, loitering, port visits) |
| `sar_presence_flat.parquet` | 41MB | 1.2M | SAR-derived vessel presence |
| `fishing_effort_flat.parquet` | 17MB | 890K | AIS fishing effort estimates |
| `vessel_registry.parquet` | 6MB | 148K | Zenodo vessel registry (IDN) |
| `zenodo_effort_flat.parquet` | 237MB | 30M | Grid-level fishing effort |
| `weather.parquet` | — | 3K | BMKG marine weather |
| `viirs_detections.parquet` | — | 5K | VIIRS boat detections |
| `ports.parquet` | — | 30 | Indonesia port locations |

Audit findings: [docs/PHASE1_AUDIT_FINDINGS.md](docs/PHASE1_AUDIT_FINDINGS.md)

---

## 📅 Timeline

### ✅ Week 1 — Data Acquisition (COMPLETE)
- [x] Project structure & configuration
- [x] GFW API integration (512K+ events)
- [x] Synthetic data generation
- [x] VIIRS / BMKG / BPS sample data
- [x] EEZ shapefiles & port data

### 🔄 Week 2 — Preprocessing & EDA
- [x] Phase 1: Load & Flatten (all sources → Parquet)
- [ ] Phase 2: Clean & Validate
- [ ] AIS trajectory cleaning & segmentation
- [ ] Feature engineering (speed, heading, zone crossings)
- [ ] Spatial joins with EEZ/MPA boundaries
- [ ] Exploratory notebooks

### 📅 Week 3 — Model Development
- [ ] ST-GAT architecture implementation
- [ ] Graph construction pipeline
- [ ] Training & hyperparameter tuning

### 📅 Week 4 — Evaluation & Polish
- [ ] Model evaluation (precision, recall, F1, AUC)
- [ ] Explainability analysis
- [ ] Visualization dashboard
- [ ] Paper & presentation

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 📖 References

1. Velickovic et al. (2018) — Graph Attention Networks
2. Yu et al. (2018) — Spatio-Temporal Graph Convolutional Networks
3. Global Fishing Watch — https://globalfishingwatch.org/
4. Elvidge et al. — VIIRS Boat Detection, EOG
5. NOAA — Cross-matching VMS with VIIRS for IUU detection

---

*Last updated: 2026-04-21*
