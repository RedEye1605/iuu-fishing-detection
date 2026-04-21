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
│   │   ├── constants.py              # Shared constants (paths, flags, bbox)
│   │   ├── pipeline/                 # Data processing pipeline
│   │   │   ├── extract.py            # Phase 1: Load & flatten raw data
│   │   │   ├── clean.py              # Phase 2: Dedup, validate, normalize
│   │   │   ├── features.py           # Phase 3a: Vessel + behavioral features
│   │   │   └── enrich.py             # Phase 3b: Cross-source enrichment
│   │   └── clients/                  # API clients
│   │       ├── gfw.py                # GFW API client (events, SAR, effort)
│   │       └── __init__.py
│   ├── features/
│   │   └── graph_builder.py          # ST-GAT graph construction (Phase 5)
│   ├── models/
│   │   └── stgat.py                  # ST-GAT model architecture (Phase 6)
│   └── utils/
│       └── __init__.py
├── scripts/
│   ├── run_pipeline.py               # Master pipeline runner (Phase 1-3)
│   ├── pull_sar_data.py              # GFW 4Wings SAR data puller
│   └── download_large_data.sh        # Zenodo data download helper
├── docs/                             # Documentation
├── notebooks/                        # Jupyter exploration notebooks
├── tests/                            # Unit tests
├── data/                             # Raw & processed data (gitignored)
├── pyproject.toml                    # Package metadata & dependencies
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

## 🚀 Running the Pipeline

```bash
python scripts/run_pipeline.py              # Run all phases (1-3)
python scripts/run_pipeline.py --phase 1    # Run only Phase 1
python scripts/run_pipeline.py --phase 2    # Run only Phase 2
python scripts/run_pipeline.py --phase 3    # Run only Phase 3
python scripts/run_pipeline.py --step 3.5   # Run specific step
```

The pipeline reads from `data/raw/` and writes to `data/processed/`. Total runtime: ~15-20 minutes depending on I/O.

---

## 📊 Final Dataset

### `data/processed/gfw_events_full.parquet`
- **Rows:** 512,247 events
- **Columns:** 121
- **Size:** 80.7 MB
- **Coverage:** Indonesian waters, 2020–2025
- **Event types:** Fishing (56%), Loitering (25%), Port Visit (10%), Encounter (9%)
- **Vessel flags:** 47% domestic, 53% foreign

### All Output Files

| File | Rows | Cols | Description |
|------|------|------|-------------|
| `gfw_events_full.parquet` | 512,247 | 121 | **Final enriched events** |
| `gfw_events_clean.parquet` | 512,247 | 66 | Cleaned events (pre-enrichment) |
| `gfw_events_flat.parquet` | 512,272 | 54 | Raw flattened events |
| `vessel_behavioral_features.parquet` | 14,857 | 32 | Per-vessel behavioral profiles |
| `vessel_registry.parquet` | 147,924 | 12 | Zenodo vessel registry |
| `fishing_effort_clean.parquet` | 885,649 | 18 | Cleaned GFW fishing effort |
| `sar_presence_clean.parquet` | 742,075 | 18 | Cleaned SAR presence |
| `zenodo_effort_clean.parquet` | 707,118 | 12 | Cleaned Zenodo effort (spatially filtered) |
| `weather.parquet` | 2,920 | 9 | BMKG marine weather |
| `viirs_detections.parquet` | 5,000 | 8 | VIIRS boat detections (sample) |
| `ports.parquet` | 30 | 3 | Indonesia port locations |

### Feature Categories (121 columns)

| Category | Columns | Description |
|----------|---------|-------------|
| Core | 12 | ID, type, timestamps, coordinates |
| Vessel | 4 | Name, ID, flag, type |
| Regions | 5 | EEZ, MPA, RFMO, FAO zones |
| Authorization | 5 | Auth status, risk flags |
| Event-specific | 20 | Port, encounter, loitering details |
| Temporal | 8 | Hour, day, month, season, etc. |
| Registry | 9 | Vessel class, length, engine, tonnage |
| Spatial | 5 | Grid cell, sea zone, nearest port |
| Weather | 7 | Wind, wave, temp, visibility |
| VIIRS | 3 | Detection count, radiance, nearby flag |
| SAR/Effort | 4 | Detection density, effort density |
| Behavioral | 22 | Per-vessel fishing/encounter/loitering patterns |

---

## ⚠️ Known Limitations

| Limitation | Impact | Notes |
|-----------|--------|-------|
| Registry fill rate 50.3% | Missing vessel specs for ~half of vessels | 1,598/14,857 MMSIs matched in Zenodo registry |
| VIIRS is sample data (5K rows) | Limited VIIRS enrichment | Focus on SAR + AIS as primary signals |
| Weather data only 2024 | No historical weather enrichment | Consider Open-Meteo API for backfill |
| No EEZ/MPA shapefile spatial join | Uses GFW regions field instead | GFW regions data is reliable for Indonesia |
| `potential_risk` only 0.4% True | Severe class imbalance | May need anomaly detection approach |
| 30 ports only | Limited port coverage | Major ports covered; add from OSM for more |

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
- [x] Full pipeline audit and bug fixes
- [x] Documentation updated to match implementation

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

## 📖 Documentation

- [Pipeline Implementation Plan](docs/DATA_PIPELINE_IMPLEMENTATION_PLAN.md) — Full pipeline details
- [Pipeline Schema](docs/PIPELINE_SCHEMA.md) — All parquet file schemas
- [Audit Report](docs/AUDIT_REPORT.md) — Data quality audit
- [Data Quality Report](docs/DATA_QUALITY_REPORT.md) — ML readiness assessment
- [Phase 1 Findings](docs/PHASE1_AUDIT_FINDINGS.md) — Initial data audit
- [CHANGELOG.md](CHANGELOG.md) — Version history

---

## 📖 References

1. Velickovic et al. (2018) — Graph Attention Networks
2. Yu et al. (2018) — Spatio-Temporal Graph Convolutional Networks
3. Global Fishing Watch — https://globalfishingwatch.org/
4. Elvidge et al. — VIIRS Boat Detection, EOG
5. NOAA — Cross-matching VMS with VIIRS for IUU detection

---

*Last updated: 2026-04-22*
