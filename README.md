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
│   │   ├── constants.py           # Shared constants (paths, flags, bbox)
│   │   ├── loaders.py              # Phase 1 Step 1.1: GFW events loader
│   │   ├── loaders_sar_effort.py    # Phase 1 Step 1.2: SAR & fishing effort loader
│   │   ├── loaders_aux.py          # Phase 1 Steps 1.3-1.5: Auxiliary data loader
│   │   ├── step_2_1_dedup.py       # Phase 2 Step 2.1: Deduplication
│   │   ├── step_2_2_clean.py       # Phase 2 Steps 2.2-2.6: Clean & validate
│   │   ├── step_2_7_clean_rest.py  # Phase 2 Step 2.7: Clean remaining datasets
│   │   ├── step_3_1_vessel_features.py  # Phase 3 Step 3.1: Vessel features
│   │   ├── step_3_4_behavioral.py  # Phase 3 Step 3.4: Behavioral features
│   │   ├── step_3_5_enrichment.py  # Phase 3 Step 3.5: Cross-source enrichment
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
│   ├── run_pipeline.py          # Master pipeline runner (Phase 1-3)
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

### Pipeline Complete ✅ ALL PHASES DONE

Final output: `data/processed/gfw_events_full.parquet` (512K rows, 105+ cols)

**Run the pipeline:**
```bash
python scripts/run_pipeline.py          # Run all phases
python scripts/run_pipeline.py --phase 2  # Run only Phase 2
python scripts/run_pipeline.py --step 3.5 # Run specific step
```

#### Output Files

| File | Rows | Description |
|------|------|-------------|
| `gfw_events_full.parquet` | 512K | **Final enriched events** (105+ cols) |
| `vessel_behavioral_features.parquet` | 15K | Per-vessel behavioral profiles (32 cols) |
| `vessel_registry.parquet` | 148K | Vessel registry (MMSI as string) |
| `fishing_effort_clean.parquet` | 886K | Cleaned fishing effort |
| `sar_presence_clean.parquet` | 742K | Cleaned SAR presence |
| `zenodo_effort_clean.parquet` | 613K | Cleaned Zenodo effort |
| `weather.parquet` | 3K | BMKG marine weather |
| `viirs_detections.parquet` | 5K | VIIRS boat detections |
| `ports.parquet` | 30 | Indonesia port locations |

#### Pipeline Phases

1. **Phase 1: Load & Flatten** — Raw JSON/CSV → Parquet
2. **Phase 2: Clean & Validate** — Dedup, flag standardize, coordinate validation
3. **Phase 3: Feature Engineering** — Vessel profiles, behavioral features, cross-source enrichment

Full audit: [docs/AUDIT_REPORT.md](docs/AUDIT_REPORT.md)
Schema: [docs/PIPELINE_SCHEMA.md](docs/PIPELINE_SCHEMA.md)

---

## 📅 Timeline

### ✅ Week 1 — Data Acquisition (COMPLETE)
- [x] Project structure & configuration
- [x] GFW API integration (512K+ events)
- [x] Synthetic data generation
- [x] VIIRS / BMKG / BPS sample data
- [x] EEZ shapefiles & port data

### ✅ Week 2 — Preprocessing & EDA (COMPLETE)
- [x] Phase 1: Load & Flatten (all sources → Parquet)
- [x] Phase 2: Clean & Validate (dedup, flag standardize, outliers)
- [x] Phase 3: Feature Engineering (vessel profiles, behavioral, enrichment)
- [ ] Exploratory notebooks
- [ ] AIS trajectory cleaning & segmentation

### 🔄 Week 3 — Model Development
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
