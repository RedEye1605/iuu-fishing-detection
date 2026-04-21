# GEMASTIK XIX 2026 — Divisi III: IUU Fishing Detection
## Phase 1: Deep Research + Data Acquisition Plan

> **Tim:** Toni, Nafi, Rhendy | **Universitas Brawijaya**
> **Date:** 2026-04-20 | **Status:** Research Phase Complete

---

## 1. PROBLEM DEFINITION

### 1.1 Core Research Question
**"Bagaimana mendeteksi aktivitas IUU (Illegal, Unreported, Unregulated) Fishing di perairan Indonesia menggunakan pendekatan Spatiotemporal Graph Neural Network pada data AIS/VMS?"**

### 1.2 Prediction Targets (Multi-Task)
| Target | Type | Description |
|--------|------|-------------|
| **IUU Risk Score** | Regression (0–1) | Probability of vessel engaging in IUU behavior |
| **Anomaly Classification** | Binary | Normal vs Anomalous vessel behavior |
| **Anomaly Type** | Multi-class | Type: dark fishing, transshipment, boundary straddling, loitering, gear mismatch |
| **Hotspot Prediction** | Spatial | Predicting IUU risk areas by grid cell |

### 1.3 Framing Strategy
Since **ground truth IUU labels are NOT publicly available**, we use a **weakly supervised + anomaly detection** approach:

1. **Proxy labels from GFW events**: AIS gaps, encounters, loitering → "suspicious" labels
2. **Rule-based labeling**: Vessels fishing in restricted areas, at night in prohibited zones, speed anomalies
3. **VIIRS cross-matching**: Vessels detected by VIIRS but not broadcasting AIS → "dark vessel" labels
4. **Official seizure records**: Small validation set from KKP published data

This creates a realistic and novel research framing — more impressive than simple classification.

### 1.4 Geographic Scope
**Primary:** Indonesian EEZ — focused on 2–3 WPP (Wilayah Pengelolaan Perikanan):
- WPP 711 (Laut Sulawesi / Celebes Sea) — high foreign vessel incursion
- WPP 715 (Laut Sulawesi / Makassar Strait) — high fishing activity
- WPP 718 (Laut Arafura) — documented IUU hotspots

**Rationale:** Keeps data manageable (~1-2M track points) while covering diverse IUU patterns.

### 1.5 Temporal Scope
**2022–2024** (3 years) — recent enough to be relevant, sufficient for temporal patterns.

---

## 2. DATA SOURCE INVENTORY

### 2.1 Primary Data Sources (CONFIRMED AVAILABLE)

#### A. Global Fishing Watch (GFW) — PRIMARY
| Dataset | Access | Format | Size (est.) | Cost |
|---------|--------|--------|-------------|------|
| **Apparent Fishing Effort v3** (2012–2024) | Data Download Portal | CSV (0.01° or 0.1° grid) | ~5-10 GB global; ~500 MB for Indonesia EEZ | FREE |
| **Vessel Events** (encounters, loitering, port visits, AIS gaps) | API v3 | JSON | Thousands of events | FREE |
| **Vessel Identity & Registry** | API v3 | JSON | ~200K vessels globally | FREE |
| **SAR Presence** (Sentinel-1 vessel detections) | API v3 | JSON | Moderate | FREE |
| **Indonesia VMS data** | Integrated in GFW map | Via API | Same as above | FREE |

**API Access:**
- Register at: https://globalfishingwatch.org/our-apis/
- Self-registration for non-commercial use (research qualifies)
- Bearer token authentication
- Rate limit: ~10 requests/min (free); can request higher for research
- **Python package:** `pip install globalfishingwatch` (new April 2025 release)
- **R package:** `gfwr`
- API v3 base: `https://gateway.api.globalfishingwatch.org/v3/`
- Key endpoints: `/vessels`, `/events`, `/4wings/report`, `/tracks`

**Zenodo dataset:** https://zenodo.org/records/14982712 (Fishing Effort v3.0, March 2025)

**What to download FIRST:**
1. Fishing effort data filtered to Indonesia EEZ (2022–2024, 0.1° resolution, daily)
2. All event data (encounters, loitering, port visits, AIS gaps) for Indonesia EEZ
3. Vessel identity data for vessels active in Indonesian waters

#### B. NOAA VIIRS Boat Detection (VBD) — DARK VESSEL DETECTION
| Dataset | Access | Format | Size | Cost |
|---------|--------|--------|------|------|
| **Nightly VBD data** | Colorado School of Mines EOG | CSV, KMZ | ~2 GB/year | FREE (CC-BY 4.0) |
| **Monthly summary grids** | EOG | GeoTIFF (15 arc-sec) | ~500 MB/year | FREE |
| **Annual composites** | EOG | GeoTIFF | Moderate | FREE |

**Access:** https://eogdata.mines.edu/products/vbd/
**URL pattern:** `https://eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/v23/[region]/[state]/[file]`
**Coverage:** Global nightly since April 2012 (SNPP) + January 2022 (NOAA-20)
**Indonesia-specific:** VBD data available per country EEZ (region code: IDN)

**Key use:** Cross-match VBD detections with AIS/VMS tracks to identify "dark vessels" — vessels operating without transponders.

#### C. BMKG Marine Data — OCEAN/WEATHER CONTEXT
| Dataset | Access | Format | Notes |
|---------|--------|--------|-------|
| **Wave height & direction** | API: `maritim.bmkg.go.id/pusmar/api23` | JSON | Wind sea + swell |
| **Ocean currents** | Same API | JSON | U/V components, multiple depths |
| **Marine weather forecasts** | BMKG OFS portal | JSON/XML | Forecast data |
| **Significant wave height** | OFS portal | Grid data | Model output |

**API format:** `https://maritim.bmkg.go.id/pusmar/api23/arr_req/inawaves/<baserun>/<dtime>/<param>`
**Parameters:** wind, dir, phs00 (wind sea height), phs01 (swell height), pdi00, pdi01, ptp00, ptp01
**Currents:** `https://maritim.bmkg.go.id/pusmar/api23/arr_req/inaflows/<baserun>/<dtime>/<depth>/cur`

**Key use:** Weather/ocean features for contextualizing vessel behavior (rough seas → different patterns).

#### D. BPS Fisheries Statistics — SOCIOECONOMIC CONTEXT
| Dataset | Access | Format | Notes |
|---------|--------|--------|-------|
| **Perikanan Tangkap by Province** | bps.go.id | HTML/Table/CSV | Volume + value by kabupaten |
| **Number of fishing vessels** | bps.go.id | Table | By province, size class |
| **Fisherman households** | bps.go.id | Table | By province |

**Key table:** Volume Produksi Perikanan Tangkap Menurut Provinsi (2024)
**URL:** https://www.bps.go.id/en/statistics-table/3/...

**Key use:** Fisheries production per WPP as context for expected fishing effort.

#### E. KKP Portal Data — OFFICIAL FISHERIES DATA
| Dataset | Access | Format | Notes |
|---------|--------|--------|-------|
| **Produksi Perikanan Tangkap** | portaldata.kkp.go.id | Dashboard/Table | By species, province, year |
| **JTB/Potensi/SDI WPP** | portaldata.kkp.go.id | Table | Per WPP fisheries potential |
| **Vessel registry** | portaldata.kkp.go.id | Table | Fishing vessel database |
| **Fisherman statistics** | portaldata.kkp.go.id | Table | Nelayan, RTP, jumlah kapal |

**Key URL:** https://portaldata.kkp.go.id/portals/data-statistik/layer1
**2024 data:** Produksi Perikanan Tangkap — 681,068 ton (tongkol), 549,553 ton (layang), etc.

**Key use:** Ground truth for expected fishing production; vessel registry for feature engineering.

### 2.2 Secondary/Supplementary Data Sources

#### F. EEZ & MPA Boundaries (GIS)
| Source | What | Format | Access |
|--------|------|--------|--------|
| **MarineRegions.org** | Global EEZ boundaries (v12) | Shapefile | FREE |
| **GFW EEZ dataset** | EEZ regions (via API) | JSON | FREE |
| **Protected Planet / WDPA** | MPA boundaries | Shapefile | FREE |
| **OSM** | Port locations, harbors | GeoJSON | FREE |

**Key use:** Distance-to-boundary features, spatial filtering, MPA violation detection.

#### G. OMTAD Dataset — ACADEMIC BENCHMARK
| Dataset | Access | Format | Notes |
|---------|--------|--------|-------|
| **OMTAD** | GitHub: shaoxiongji/OMTAD | CSV/JSON | AIS data with anomaly labels |
| **Extended OMTAD (NeurIPS 2025)** | arXiv: 2512.20086 | Benchmark | ST-GNN maritime anomaly |

**Key use:** Pre-labeled data for model validation; benchmark comparison.

#### H. GFW BigQuery Public Tables
| Dataset | Access | Format | Notes |
|---------|--------|--------|-------|
| **Fishing effort** | Google BigQuery (public) | SQL | Large-scale analysis |
| **Vessel identity** | Google BigQuery | SQL | Vessel registry matching |

**Cost:** Google Cloud free tier includes 1TB/month BigQuery queries.

### 2.3 Data NOT Directly Available (Gap Analysis)
| Data | Status | Workaround |
|------|--------|------------|
| Raw AIS messages | Commercial ($) | Use GFW processed data |
| Individual VMS raw tracks | Government only | Use GFW integrated data |
| Ground truth IUU labels | Not public | Construct proxy labels |
| Seizure/arrest records | Partial (KKP reports) | Manual collection from news/KKP |
| Real-time vessel positions | Commercial | Historical data sufficient for research |

---

## 3. DATA ACQUISITION PLAN

### 3.1 Priority Order (What to Pull First)

| Priority | Source | Data | Method | Est. Size | Timeline |
|----------|--------|------|--------|-----------|----------|
| **P0** | GFW API | Vessel events (encounters, loitering, gaps, port visits) | Python API client | ~50K events | Week 1 |
| **P0** | GFW Download | Fishing effort (Indonesia EEZ, 2022–2024) | CSV download | ~500 MB | Week 1 |
| **P0** | GFW API | Vessel identity for Indonesia-flagged vessels | Python API | ~10K vessels | Week 1 |
| **P1** | EOG VBD | VIIRS boat detections (Indonesia EEZ, 2022–2024) | CSV download | ~2 GB | Week 2 |
| **P1** | MarineRegions | EEZ shapefile, MPA boundaries | Shapefile download | ~50 MB | Week 2 |
| **P1** | OMTAD | Labeled AIS benchmark dataset | GitHub download | ~100 MB | Week 2 |
| **P2** | BMKG API | Wave height, ocean currents (2022–2024) | API scraping | ~1 GB | Week 3 |
| **P2** | BPS | Fisheries production statistics | Table download | ~10 MB | Week 3 |
| **P2** | KKP Portal | Vessel registry, production data | Manual/scrape | ~20 MB | Week 3 |
| **P3** | OSM | Port locations, harbors | Overpass API | ~5 MB | Week 4 |

### 3.2 GFW API Setup Steps
```python
# 1. Register for API key
# https://globalfishingwatch.org/our-apis/

# 2. Install Python client
pip install globalfishingwatch

# 3. Example: Get events for Indonesia EEZ
from globalfishingwatch import GFWClient

client = GFWClient(bearer_token="YOUR_TOKEN")

# Indonesia EEZ region ID (from GFW)
indonesia_eez_id = 8371  # Verify via API

# Get encounter events
events = client.get_events(
    datasets=["public-global-encounters-events:latest"],
    start_date="2022-01-01",
    end_date="2024-12-31",
    region={"dataset": "public-eez-areas", "id": indonesia_eez_id}
)

# Get fishing effort
effort = client.get_report(
    datasets=["public-global-fishing-effort:latest"],
    spatial_resolution="LOW",
    temporal_resolution="DAILY",
    start_date="2022-01-01",
    end_date="2024-12-31",
    region={"dataset": "public-eez-areas", "id": indonesia_eez_id},
    format="CSV"
)
```

### 3.3 Data Size Estimates (Final Dataset)
| Component | Raw Size | Processed Size |
|-----------|----------|----------------|
| AIS/VMS track points (filtered to Indonesia) | ~5-10 GB | ~2-4 GB |
| GFW events | ~500 MB | ~100 MB |
| Fishing effort grids | ~500 MB | ~200 MB |
| VIIRS boat detections | ~2 GB | ~500 MB |
| BMKG ocean data | ~1 GB | ~300 MB |
| GIS boundaries | ~50 MB | ~50 MB |
| BPS/KKP statistics | ~30 MB | ~10 MB |
| **TOTAL** | **~10-15 GB** | **~3-5 GB** |

---

## 4. FEATURE ENGINEERING PLAN

### 4.1 Feature Categories

#### Category 1: Kinematic Features (from AIS/VMS)
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Speed (SOG) | Direct from AIS | ★★★★★ |
| Course over ground (COG) | Direct from AIS | ★★★★★ |
| Heading | Direct from AIS | ★★★★ |
| Acceleration | Δspeed/Δtime | ★★★★ |
| Turn rate | Δcourse/Δtime | ★★★★ |
| Speed variance (window) | Rolling std | ★★★★ |
| Course variance (window) | Rolling std | ★★★★ |
| Distance traveled (window) | Sum of haversine | ★★★ |

#### Category 2: Spatial Context Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Distance to nearest port | Haversine from port DB | ★★★★ |
| Distance to EEZ boundary | Point-to-polygon | ★★★★★ |
| Distance to nearest MPA | Point-to-polygon | ★★★★★ |
| Distance to shore | Haversine from coastline | ★★★★ |
| Depth at location | Bathymetry lookup | ★★★ |
| WPP zone | Point-in-polygon | ★★★★ |
| Is in restricted area? | Boolean | ★★★★★ |

#### Category 3: Temporal Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Hour of day (sin/cos) | Cyclical encoding | ★★★★ |
| Day of week | One-hot | ★★★ |
| Month (sin/cos) | Cyclical encoding | ★★★★ |
| Is nighttime? | Boolean (sunset calc) | ★★★★★ |
| Is fishing moratorium period? | Boolean | ★★★★ |
| Time since last port visit | Hours | ★★★★ |

#### Category 4: Vessel Identity Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Vessel length | From registry | ★★★ |
| Gear type | From registry | ★★★★ |
| Flag state (encoded) | From registry | ★★★★★ |
| Gross tonnage | From registry | ★★★ |
| Engine power | From registry | ★★ |

#### Category 5: AIS Health / Transparency Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| AIS gap duration | Time between pings | ★★★★★ |
| AIS gap frequency | Count per week | ★★★★★ |
| Mean ping interval | Average | ★★★★ |
| Ping interval std | Variance | ★★★★ |
| Has the vessel gone dark? | Boolean | ★★★★★ |

#### Category 6: Interaction / Graph Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Number of nearby vessels (5 NM) | Spatial count | ★★★★ |
| Number of encounters (history) | From GFW events | ★★★★★ |
| Encounter duration | From GFW events | ★★★★★ |
| Loitering event count | From GFW events | ★★★★★ |
| Same-fleet co-occurrence | Pattern analysis | ★★★ |

#### Category 7: Environmental Features
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Sea surface temperature | BMKG / Copernicus | ★★★ |
| Wave height | BMKG API | ★★★ |
| Ocean current speed/direction | BMKG API | ★★★ |
| Chlorophyll-a | MODIS/Sentinel | ★★★ |
| Moon phase (affects VIIRS) | Astronomical calc | ★★★ |

#### Category 8: Socioeconomic Features (Area-level)
| Feature | Extraction | Importance |
|---------|-----------|------------|
| Expected fishing production (WPP) | BPS/KKP data | ★★★ |
| Number of licensed vessels (area) | KKP registry | ★★★ |
| Historical IUU incidents (area) | News/records | ★★★ |

### 4.2 Graph Construction Strategy

```
Node: Each unique vessel (MMSI/VMS ID) in observation window
Node Features: [kinematic_8 + spatial_7 + temporal_6 + identity_5 + AIS_health_5 + interaction_5 + environmental_5] = ~41 features

Edge Types (Multi-relational Graph):
  1. SPATIAL_PROXIMITY: vessels within 5 NM, same time window
  2. ENCOUNTER: from GFW encounter events (known encounters)
  3. SAME_FLEET: vessels with correlated trajectories (detected)
  4. SAME_FLAG: same flag state (weak signal)

Edge Features:
  - Distance between vessels
  - Duration of co-occurrence
  - Correlation of trajectories

Temporal Slicing:
  - Sliding windows of 6h, 12h, 24h
  - Each window = one graph snapshot
  - Sequence of snapshots = temporal graph input
```

---

## 5. MODEL APPROACH

### 5.1 Model Architecture: ST-GAT (Spatiotemporal Graph Attention Network)

```
INPUT: Sequence of graph snapshots G = {G_t1, G_t2, ..., G_tn}
  Each G_t = (V, E, X_t)  where X_t = node feature matrix [N × F]

Layer 1: SPATIAL ENCODER
  → Multi-head Graph Attention Network (GAT)
  → H_spatial = GATConv(X_t, edge_index, edge_attr)
  → 4-8 attention heads, 64-128 hidden dims
  → Captures vessel-vessel spatial interactions

Layer 2: TEMPORAL ENCODER  
  → GRU or LSTM over spatial embeddings
  → H_temporal = GRU([H_spatial_t1, ..., H_spatial_tn])
  → Captures temporal evolution of vessel states

Layer 3: ATTENTION FUSION
  → Multi-head attention on temporal outputs
  → weights = softmax(W · H_temporal)
  → H_fused = Σ(weights_i * H_temporal_i)

Layer 4: TASK HEAD
  → Anomaly Score: sigmoid(MLP(H_fused)) → [0, 1]
  → Anomaly Type: softmax(MLP(H_fused)) → multi-class

LOSS FUNCTION:
  → L = α · BCE(anomaly_score, label)
    + β · CE(anomaly_type, type_label)  
    + γ · L_graph_reg (edge prediction auxiliary)
    + δ · L_contrastive (contrastive learning on embeddings)
```

### 5.2 Baseline Models (For Comparison)

| Model | Type | Purpose |
|-------|------|---------|
| **XGBoost** | Gradient Boosting | Strong tabular baseline |
| **Random Forest** | Ensemble | Interpretable baseline |
| **Isolation Forest** | Unsupervised Anomaly | No-label baseline |
| **LSTM Autoencoder** | Self-supervised | Deep learning baseline (no graph) |
| **GAT-only** | Graph NN (no temporal) | Ablation: Is temporal modeling needed? |
| **LSTM-only** | Sequential (no graph) | Ablation: Is graph structure needed? |
| **ST-GAT (proposed)** | Full model | Our contribution |

### 5.3 Training Strategy

1. **Phase 1: Unsupervised Pre-training**
   - Train autoencoder on all vessel trajectories
   - Learn normal behavior representations
   
2. **Phase 2: Weakly Supervised Fine-tuning**
   - Use proxy labels from GFW events
   - Binary classification: suspicious vs normal
   
3. **Phase 3: Semi-supervised Refinement**
   - Add any confirmed IUU labels (from KKP records)
   - Pseudo-labeling: high-confidence predictions as additional labels

### 5.4 Evaluation Metrics
- **Primary:** F1-Score, AUC-ROC, AUC-PR
- **Secondary:** Top-K Precision (K=10, 20, 50), Detection Rate
- **Analysis:** Confusion matrix, per-WPP performance, temporal analysis
- **Visualization:** Anomaly heatmaps on map, vessel track plots, SHAP values

---

## 6. DELIVERABLES

### 6.1 Technical Report Structure (for GEMASTIK submission)
1. **Abstrak** — Problem, method, key results
2. **Pendahuluan** — IUU fishing in Indonesia, motivation, contributions
3. **Tinjauan Pustaka** — IUU detection, GNN, maritime anomaly
4. **Metodologi** — Data, preprocessing, feature engineering, model
5. **Hasil dan Pembahasan** — Experiments, results, comparison
6. **Kesimpulan** — Summary, impact, future work
7. **Daftar Pustaka** — References

### 6.2 Code & Reproducibility
- Complete pipeline in Jupyter notebooks
- Modular Python package (`src/`)
- Requirements.txt with all dependencies
- README.md with setup instructions
- Google Colab notebook for demo

### 6.3 Demo / Dashboard
- **Interactive map** (Folium/Kepler.gl) showing:
  - Vessel tracks colored by IUU risk score
  - Detected anomalies highlighted
  - Anomaly hotspots as heatmaps
  - Time slider for temporal exploration
- **Streamlit dashboard** for:
  - Real-time scoring of new vessel tracks
  - Model comparison metrics
  - Feature importance visualization

### 6.4 Presentation (for finals)
- 15-20 slides covering: Problem → Data → Method → Results → Impact → Demo
- Focus on: novelty (GNN for Indonesian IUU), impact ($3B loss), visual appeal

---

## 7. TIMELINE

### 7.1 GANTT Chart (12 Weeks: Apr 21 – Jul 13, 2026)

```
Week  | Phase                | Tasks
------|---------------------|--------------------------------------------------
1-2   | DATA COLLECTION     | GFW API setup, download fishing effort + events,
      |                     | VBD data, EEZ/MPA shapefiles, OMTAD dataset
      |                     | Deliverable: data/ folder with all raw data
------|---------------------|--------------------------------------------------
3-4   | PREPROCESSING       | Clean AIS data, interpolate gaps, segment tracks,
      |                     | feature extraction, graph construction
      |                     | Deliverable: processed datasets + feature store
------|---------------------|--------------------------------------------------
5-6   | BASELINE MODELS     | XGBoost, RF, Isolation Forest, LSTM-AE
      |                     | Establish benchmark performance
      |                     | Deliverable: baseline results + comparison table
------|---------------------|--------------------------------------------------
7-8   | ST-GNN (Core)       | Implement GAT + GRU architecture
      |                     | Train on processed data, hyperparameter tuning
      |                     | Deliverable: trained model + training logs
------|---------------------|--------------------------------------------------
9     | EVALUATION          | Full evaluation vs baselines, ablation studies,
      |                     | per-WPP analysis, error analysis
      |                     | Deliverable: evaluation report + visualizations
------|---------------------|--------------------------------------------------
10    | DASHBOARD + DEMO    | Build interactive map, Streamlit dashboard,
      |                     | anomaly heatmaps, prepare demo
      |                     | Deliverable: working demo
------|---------------------|--------------------------------------------------
11    | WRITE-UP            | Complete technical report, refine all sections,
      |                     | prepare presentation slides
      |                     | Deliverable: final report PDF
------|---------------------|--------------------------------------------------
12    | FINAL PREP          | Rehearse presentation, polish demo, backup plans
      |                     | Deliverable: competition-ready submission
```

### 7.2 Key Milestones
| Date | Milestone | Checkpoint |
|------|-----------|------------|
| **May 4** | All raw data downloaded | Can query GFW API successfully |
| **May 18** | Features extracted + graphs built | Can train baseline models |
| **Jun 1** | Baseline results established | XGBoost F1 > 0.5 |
| **Jun 15** | ST-GNN trained | ST-GNN outperforms baselines |
| **Jun 29** | Evaluation complete | Ablation + comparison tables done |
| **Jul 6** | Dashboard + report done | Demo runs end-to-end |
| **Jul 13** | Competition ready | Final submission package |

---

## 8. TEAM TASK ALLOCATION

### 8.1 Role Distribution

#### Rhendy (Team Lead + ML Engineer)
**Primary:** Model architecture, training, evaluation
- **Weeks 1-2:** GFW API integration, data pipeline architecture
- **Weeks 3-4:** Feature engineering pipeline, graph construction logic
- **Weeks 5-6:** Implement baseline models (XGBoost, RF, Isolation Forest)
- **Weeks 7-8:** ST-GNN implementation (PyTorch Geometric), training loop
- **Weeks 9-10:** Evaluation, ablation studies, comparison analysis
- **Weeks 11-12:** Technical report writing, presentation prep
- **Skills needed:** PyTorch, PyTorch Geometric, pandas, scikit-learn

#### Toni (Data Engineer + Domain Expert)
**Primary:** Data acquisition, preprocessing, GIS analysis
- **Weeks 1-2:** GFW registration + data download, VBD data, EEZ shapefiles
- **Weeks 3-4:** Data cleaning, AIS preprocessing, spatial feature computation
- **Weeks 5-6:** BMKG data collection, BPS/KKP statistics, VIIRS cross-matching
- **Weeks 7-8:** Feature store maintenance, data pipeline optimization
- **Weeks 9-10:** Visualization (Folium maps, Kepler.gl), anomaly heatmaps
- **Weeks 11-12:** Dashboard development (Streamlit), demo preparation
- **Skills needed:** pandas, geopandas, shapely, folium, APIs, GIS

#### Nafi (Research Assistant + Presenter)
**Primary:** Literature review, evaluation analysis, presentation
- **Weeks 1-2:** Literature review (20+ papers), dataset documentation
- **Weeks 3-4:** Label construction (proxy labels from GFW events), VIIRS cross-match
- **Weeks 5-6:** LSTM Autoencoder baseline, unsupervised methods
- **Weeks 7-8:** Hyperparameter tuning support, experiment tracking (W&B)
- **Weeks 9-10:** Error analysis, per-WPP evaluation, SHAP/interpretability
- **Weeks 11-12:** Presentation slides, rehearse presentation, report editing
- **Skills needed:** Literature analysis, Python, presentation skills, writing

### 8.2 Collaboration Setup
- **Git repo:** GitHub private repository
- **Notebooks:** Google Colab shared notebooks (free GPU)
- **Communication:** WhatsApp group + weekly sync (Sun/Mon)
- **Experiment tracking:** Weights & Biases (free academic tier)
- **Data storage:** Shared Google Drive or S3 bucket

---

## 9. COMPUTE REQUIREMENTS

| Resource | Requirement | Solution |
|----------|-------------|----------|
| **GPU** | Needed for GNN training (~4-8 hours) | Google Colab (T4 free) or Kaggle (P100 free) |
| **RAM** | 16GB+ for data processing | Laptops (all have 16GB+) |
| **Storage** | 20GB for raw + processed data | Local + Google Drive |
| **Python** | 3.10+ | Conda/venv |
| **Key libraries** | PyTorch 2.x, PyG, geopandas, folium | pip install |

### 9.1 Environment Setup (Week 1)
```bash
# Local environment
conda create -n gemastik python=3.10
conda activate gemastik
pip install torch torch-geometric
pip install pandas numpy geopandas shapely scikit-learn xgboost
pip install folium plotly streamlit
pip install globalfishingwatch  # GFW API client
pip install wandb  # Experiment tracking

# Google Colab (for GPU training)
# All above packages pre-installed or easily installable
```

---

## 10. RISK REGISTER

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| 1 | GFW API rate limits block data collection | Medium | High | Batch requests, use download portal for bulk, cache aggressively |
| 2 | No ground truth IUU labels | High | High | Frame as anomaly detection; construct proxy labels from GFW events |
| 3 | GNN too complex to implement in time | Medium | High | Fallback: GAT-only or XGBoost; start with simpler model first |
| 4 | Graph too large (OOM) | Medium | Medium | Subsample region (1 WPP), mini-batching, sparse tensors |
| 5 | AIS data quality poor | High | Medium | Robust preprocessing: outlier removal, interpolation, gap handling |
| 6 | Model doesn't outperform baselines | Low | High | Feature engineering focus; ensemble GNN + XGBoost |
| 7 | Team member unavailable | Medium | Medium | Cross-train skills; shared notebooks; weekly check-ins |
| 8 | Competition deadline pressure | Medium | Medium | 12-week plan with buffer; start with MVP early |

---

## 11. KEY REFERENCES

### Core Papers
1. **NeurIPS 2025** — "Spatio-Temporal Graphs Beyond Grids: Benchmark for Maritime Anomaly Detection" (arXiv: 2512.20086) — **CLOSEST TO OUR WORK**
2. **IEEE 2025** — "Spatio-Temporal Graph-based Vessel Behavior Anomaly Detection" — ST-GNN for vessel anomaly
3. **arXiv 2502.14197 (2025)** — Anomaly detection in multi-ship trajectories using sparse graphs
4. **ACM 2025** — "IUU Fishing Detection Based on Stacking Model and Multimodal ML Using AIS and SAR Data"
5. **Yang et al. (2024)** — Semi-supervised vessel trajectory feature engineering, *Ocean Engineering*
6. **Han et al. (2025)** — Fishing vessel behavioral features + ML, *Frontiers in Marine Science*
7. **Eng. Apps of AI (2026)** — Semi-supervised pipeline, RF+LSTM, F1 0.86 (local)
8. **Sánchez Pedroche et al. (2020)** — RF for fishing detection from AIS, *Sensors* (97% acc)
9. **Huang et al. (2018)** — XGBoost for gear classification from VMS, *PLOS ONE*
10. **Mandell (2020)** — FishNET: CNN on trajectory images, *ACM*

### Data Sources
11. GFW API: https://globalfishingwatch.org/our-apis/documentation
12. GFW Python Client: https://github.com/GlobalFishingWatch/gfw-api-python-client
13. GFW Fishing Effort Zenodo: https://zenodo.org/records/14982712
14. EOG VBD: https://eogdata.mines.edu/products/vbd/
15. OMTAD: https://github.com/shaoxiongji/OMTAD
16. MarineRegions EEZ: https://www.marineregions.org/
17. BMKG Marine API: https://maritim.bmkg.go.id/pusmar/api23/arr_req
18. KKP Portal Data: https://portaldata.kkp.go.id/
19. BPS Fisheries: https://www.bps.go.id/

---

## 12. NEXT STEPS (IMMEDIATE — This Week)

### Week 1 Action Items (Apr 21–27, 2026):

| Who | Task | Deadline |
|-----|------|----------|
| **Rhendy** | Register for GFW API key, test Python client | Apr 22 |
| **Rhendy** | Set up project structure, git repo, shared Colab | Apr 22 |
| **Toni** | Download EEZ shapefiles from MarineRegions | Apr 23 |
| **Toni** | Download GFW fishing effort data for Indonesia EEZ | Apr 24 |
| **Nafi** | Literature review: read 5 key papers (refs #1-5) | Apr 25 |
| **Nafi** | Document proxy label construction strategy | Apr 26 |
| **All** | Sync meeting: review data availability, adjust plan | Apr 27 |

### First Data Pull Checklist:
- [ ] GFW API key obtained
- [ ] Python client installed and tested
- [ ] Fishing effort CSV downloaded (Indonesia EEZ, 2022-2024)
- [ ] Event data pulled (encounters, loitering, AIS gaps)
- [ ] Vessel identity data retrieved
- [ ] VBD data downloaded from EOG
- [ ] EEZ shapefile downloaded
- [ ] MPA boundaries downloaded

---

## APPENDIX: GFW API v3 Key Endpoints

```
Base URL: https://gateway.api.globalfishingwatch.org/v3

Vessels:
  GET /vessels?query=<search>&datasets[0]=public-global-vessel-identity:latest

Events:
  POST /events
  Body: {
    "datasets": ["public-global-encounters-events:latest"],
    "startDate": "2022-01-01",
    "endDate": "2024-12-31",
    "region": {"dataset": "public-eez-areas", "id": 8371}
  }

Fishing Effort (4Wings):
  GET /4wings/report?spatial-resolution=LOW&temporal-resolution=DAILY
    &datasets[0]=public-global-fishing-effort:latest
    &date-range=2022-01-01,2024-12-31&format=CSV
  Body: {"region": {"dataset": "public-eez-areas", "id": 8371}}

Vessel Tracks:
  GET /tracks?datasets[0]=public-global-vessel-identity:latest
    &vessels[0]=[vessel_id]&date-range=2022-01-01,2022-01-31

SAR Presence:
  GET /4wings/report?datasets[0]=public-global-sar-presence:latest
    &date-range=2022-01-01,2022-12-31&format=JSON

Indonesia EEZ IDs in GFW:
  - Main EEZ: 8371 (verify via API)
  - Use region lookup: GET /regions?q=Indonesia&dataset=public-eez-areas
```

---

*Document prepared by: Rhendix (AI Assistant) | For: Gemastik XIX 2026 Team*
*Based on: Deep research from existing vault document + 8 web searches + literature review*
