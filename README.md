# 🐟 IUU Fishing Detection using ST-GAT

## Gemastik XIX 2026 — Data Analytics Category

> **Spatiotemporal Graph Attention Network for Illegal, Unreported, and Unregulated (IUU) Fishing Detection in Indonesian Waters**

---

## 🎯 Overview

Deep learning system to detect IUU fishing activities in Indonesian waters by analyzing vessel tracking data (AIS), satellite boat detections (VIIRS/SAR), and maritime contextual data using a **Spatiotemporal Graph Attention Network (ST-GAT)**.

### Key Innovation
- **Graph-based modeling** — Vessels as nodes, spatial proximity as edges
- **Temporal attention** — Capture behavioral patterns over time
- **Multi-source fusion** — AIS + SAR + VIIRS + weather + zone boundaries
- **Explainability** — Identify *why* a vessel is flagged as IUU

### Target Outputs
1. Binary classification: IUU vs. normal fishing activity
2. Anomaly scoring: Risk level per vessel trajectory
3. Interactive visualization dashboard

---

## 👥 Team

- **Toni**
- **Nafi**
- **Rhendy**

---

## 📊 Data Status — COMPLETE ✅

### Core Data (Ready for Model Development)

| Dataset | Records | Coverage | Size |
|---------|---------|----------|------|
| **GFW Events** (fishing, encounters, loitering, port visits) | 512,272 | 2016–2025 | — |
| **GFW SAR Presence** (satellite vessel detections) | 1,242,915 | 2020–2025 | 73 MB |
| **GFW 4Wings Fishing Effort** | 890,411 | 2020–2025 | 69 MB |
| **GFW Static Effort** (Zenodo) | 2/5 years | 2020–2021 | 607 MB |
| **EEZ Shapefiles** | v12 | Global | 27 MB |
| **Indonesia Ports** | 30 ports | — | — |
| **BMKG Maritime Weather** | 2,921 rows | 2024 | — |
| **VIIRS Boat Detection** | 5,001 samples | — | — |

### Data Sources

- **[Global Fishing Watch API](https://globalfishingwatch.org/our-apis/)** — Vessel events, SAR presence, fishing effort
- **[Zenodo](https://zenodo.org/)** — Historical fishing effort (GFW 4Wings static)
- **[EEZ World v12](https://www.marineregions.org/)** — Exclusive Economic Zone boundaries
- **[BMKG](https://www.bmkg.go.id/)** — Maritime weather data
- **[VIIRS VBD](https://eogdata.mines.edu/)** — Satellite boat detection
- **[BPS](https://www.bps.go.id/)** — Indonesian fisheries statistics
- **[WDPA](https://www.protectedplanet.net/)** — Marine Protected Areas

---

## 📁 Project Structure

```
gemastik/
├── data/
│   ├── raw/
│   │   ├── gfw/              # GFW API data (events, SAR, effort)
│   │   ├── zenodo/           # Historical static effort data
│   │   ├── viirs/            # VIIRS boat detection data
│   │   ├── bmkg/             # Marine weather data
│   │   ├── bps/              # Fisheries statistics
│   │   └── gis/              # EEZ/MPA shapefiles
│   └── processed/            # Cleaned, feature-engineered data
├── docs/                     # Research plan, data sources
├── src/
│   ├── gfw_api_setup.py      # GFW API integration
│   ├── bps_data.py           # BPS fisheries data collection
│   ├── generate_synthetic_ais.py  # Synthetic AIS data generator
│   ├── viirs_data_setup.py   # VIIRS VBD data setup
│   ├── mpa_data_setup.py     # MPA boundaries setup
│   └── bmkg_weather_data.py  # Marine weather data
├── notebooks/                # Jupyter notebooks for exploration
├── pull_sar_data*.py         # SAR data acquisition scripts
└── README.md
```

---

## 🚀 Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Installation
```bash
cd gemastik

uv venv .venv --python 3.12
source .venv/bin/activate

# Data pipeline
uv pip install geopandas shapely folium requests beautifulsoup4 pyogrio

# ML pipeline (Phase 2)
uv pip install torch torch_geometric scikit-learn matplotlib seaborn
```

---

## 📅 Timeline (Gemastik XIX 2026)

### ✅ Week 1 — Data Acquisition (COMPLETE)
- [x] Project structure setup
- [x] EEZ shapefile download (v12)
- [x] GFW API integration (512K+ events, 1.2M+ SAR, 890K+ effort)
- [x] Synthetic data generation for development
- [x] VIIRS VBD sample data
- [x] BMKG maritime weather data
- [x] Indonesia port data
- [x] Zenodo static effort data (607MB)

### 🔄 Week 2 — Data Preprocessing & EDA
- [ ] AIS trajectory cleaning & segmentation
- [ ] Feature engineering (speed, heading changes, zone crossings)
- [ ] Spatial joins with EEZ/MPA boundaries
- [ ] VIIRS-AIS cross-matching
- [ ] Exploratory notebooks

### 📅 Week 3 — Model Development
- [ ] ST-GAT architecture implementation
- [ ] Graph construction (spatial edges + temporal sequences)
- [ ] Training pipeline
- [ ] Hyperparameter tuning

### 📅 Week 4 — Evaluation & Polish
- [ ] Model evaluation (precision, recall, F1, AUC)
- [ ] Explainability analysis
- [ ] Visualization dashboard
- [ ] Paper & presentation

---

## 📖 References

1. Velickovic et al. (2018) — Graph Attention Networks (GAT)
2. Yu et al. (2018) — Spatio-Temporal Graph Convolutional Networks
3. Global Fishing Watch — https://globalfishingwatch.org/
4. Elvidge et al. — VIIRS Boat Detection, EOG, Colorado School of Mines
5. NOAA Technical Report — Cross-matching VMS with VIIRS for IUU detection

---

*Last updated: 2026-04-21*
*Data completeness report: DATA_COMPLETENESS_REPORT.md*
*Phase 1 research plan: docs/PHASE1-RESEARCH-PLAN.md*
