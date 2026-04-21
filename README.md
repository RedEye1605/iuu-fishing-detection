# IUU Fishing Detection using ST-GAT
## Gemastik XIX 2026 — Data Analytics Category

> **Spatiotemporal Graph Attention Network for Illegal, Unreported, and Unregulated (IUU) Fishing Detection in Indonesian Waters**

---

## 🎯 Project Overview

This project develops a deep learning system to detect IUU fishing activities in Indonesian waters by analyzing vessel tracking data (AIS), satellite boat detections (VIIRS), and maritime contextual data using a **Spatiotemporal Graph Attention Network (ST-GAT)**.

### Key Innovation
- **Graph-based modeling**: Vessels as nodes, spatial proximity as edges
- **Temporal attention**: Capture behavioral patterns over time
- **Multi-source fusion**: AIS + VIIRS + weather + zone boundaries
- **Explainability**: Identify *why* a vessel is flagged as IUU

### Target Outputs
1. Binary classification: IUU vs. normal fishing activity
2. Anomaly scoring: Risk level per vessel trajectory
3. Interactive visualization dashboard

---

## 👥 Team

| Member | Role | Responsibilities |
|--------|------|-----------------|
| **Rhendy** (ML Lead) | Architecture, model training, pipeline | ST-GAT implementation, data pipeline, evaluation |
| **Toni** | Data engineering | Data collection, preprocessing, feature engineering |
| **Nafi** | Research & documentation | Literature review, paper writing, presentation |

---

## 📁 Project Structure

```
~/gemastik/
├── data/
│   ├── raw/
│   │   ├── gfw/              # Global Fishing Watch API data
│   │   ├── viirs/            # VIIRS boat detection data
│   │   ├── bmkg/             # Marine weather data
│   │   ├── bps/              # Fisheries statistics
│   │   ├── gis/              # EEZ/MPA shapefiles
│   │   └── omtad/            # AIS trajectory datasets
│   └── processed/            # Cleaned, feature-engineered data
├── docs/                     # Research plan, papers, notes
├── src/
│   ├── gfw_api_setup.py      # GFW API integration
│   ├── bps_data.py           # BPS fisheries data collection
│   ├── generate_synthetic_ais.py  # Synthetic AIS data generator
│   ├── viirs_data_setup.py   # VIIRS VBD data setup
│   ├── mpa_data_setup.py     # MPA boundaries setup
│   └── bmkg_weather_data.py  # Marine weather data
├── notebooks/                # Jupyter notebooks for exploration
├── .venv/                    # Python virtual environment
└── README.md                 # This file
```

---

## 📊 Data Sources Checklist

### ✅ Downloaded & Ready

| Source | Status | Size | Description |
|--------|--------|------|-------------|
| **EEZ World v12** | ✅ Downloaded | 26.7 MB | Global EEZ boundaries (shapefile + GeoPackage) |
| **Synthetic AIS** | ✅ Generated | ~20 MB | 197K trajectory points, 560 vessels (50 IUU) |
| **Sample VBD** | ✅ Generated | ~0.5 MB | 5000 synthetic VIIRS boat detections |
| **Sample MPA** | ✅ Generated | ~15 KB | 12 Indonesian MPA boundaries (GeoJSON) |
| **Sample Weather** | ✅ Generated | ~0.3 MB | 2920 daily marine weather records (2024) |
| **BPS Template** | ✅ Created | ~2 KB | Template for manual BPS data entry |

### ⏳ Pending (Manual Action Required)

| Source | Status | Action Needed |
|--------|--------|---------------|
| **GFW API Data** | ⏳ Pending API key | Register at https://globalfishingwatch.org/our-apis/ |
| **VIIRS VBD Real** | ⏳ Pending login | Register at https://eogdata.mines.edu/ |
| **WDPA MPA** | ⏳ Pending login | Download from https://www.protectedplanet.net/country/IDN |
| **BPS Fisheries** | ⏳ Manual | Fill template from https://www.bps.go.id/ |
| **Real AIS Data** | ⏳ Options | Ushant AIS (figshare) or NOAA AIS or GFW |

### 📋 Data Pipeline (for when real data arrives)

1. **GFW API**: `python src/gfw_api_setup.py test` → `python src/gfw_api_setup.py download 2024`
2. **VIIRS**: Login → download IDN CSVs → place in `data/raw/viirs/`
3. **MPA**: Download WDPA shapefile → filter IDN → place in `data/raw/gis/`
4. **BPS**: Fill template from web table → save as CSV in `data/raw/bps/`

---

## 🚀 Setup

### Prerequisites
- Python 3.12+
- uv (Python package manager)

### Installation
```bash
cd ~/gemastik

# Create virtual environment (already done)
uv venv .venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install geopandas shapely folium requests beautifulsoup4 pyogrio

# For ML pipeline (Phase 2)
uv pip install torch torch_geometric scikit-learn matplotlib seaborn
```

### Generate Synthetic Data (for development)
```bash
source .venv/bin/activate
python src/generate_synthetic_ais.py   # AIS trajectories
python src/viirs_data_setup.py         # VBD detections
python src/mpa_data_setup.py           # MPA boundaries
python src/bmkg_weather_data.py        # Marine weather
python src/bps_data.py sample          # BPS sample data
```

### Verify EEZ Data
```bash
source .venv/bin/activate
python -c "
import geopandas as gpd
gdf = gpd.read_file('data/raw/gis/eez_v12_lowres.gpkg')
idn = gdf[gdf['ISO_TER1'] == 'IDN']
print(f'Indonesia EEZ: {len(idn)} polygon(s)')
print(f'Total EEZs worldwide: {len(gdf)}')
"
```

---

## 📅 Timeline (Gemastik XIX 2026)

### Week 1 (Current) — Data Acquisition
- [x] Project structure setup
- [x] EEZ shapefile download
- [x] Synthetic data generation for development
- [x] GFW API setup script
- [ ] GFW API key registration (Sir)
- [ ] VIIRS VBD account & download
- [ ] WDPA MPA download
- [ ] BPS data manual entry

### Week 2 — Data Preprocessing & EDA
- [ ] AIS trajectory cleaning & segmentation
- [ ] Feature engineering (speed, heading changes, zone crossings)
- [ ] Spatial joins with EEZ/MPA boundaries
- [ ] VIIRS-AIS cross-matching
- [ ] Exploratory notebooks

### Week 3 — Model Development
- [ ] ST-GAT architecture implementation
- [ ] Graph construction (spatial edges + temporal sequences)
- [ ] Training pipeline
- [ ] Hyperparameter tuning

### Week 4 — Evaluation & Polish
- [ ] Model evaluation (precision, recall, F1, AUC)
- [ ] Explainability analysis
- [ ] Visualization dashboard
- [ ] Paper & presentation

---

## 📖 Key References

1. **Velickovic et al. (2018)** - Graph Attention Networks (GAT)
2. **Yu et al. (2018)** - Spatio-Temporal Graph Convolutional Networks
3. **Global Fishing Watch** - https://globalfishingwatch.org/
4. **VIIRS Boat Detection** - Elvidge et al., EOG, Colorado School of Mines
5. **IUU Fishing in Indonesia** - NOAA Technical Report on cross-matching VMS with VIIRS

---

## 🔑 Environment Variables

```bash
# GFW API (when available)
export GFW_API_TOKEN="your_gfw_api_token"

# BPS API (when available)  
export BPS_API_KEY="your_bps_api_key"
```

---

*Last updated: 2026-04-21*
*Phase 1 Research Plan: docs/PHASE1-RESEARCH-PLAN.md*
