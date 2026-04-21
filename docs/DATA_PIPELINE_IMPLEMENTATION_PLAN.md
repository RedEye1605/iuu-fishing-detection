# 📋 Implementation Plan: Data Cleaning & Feature Engineering Pipeline

## IUU Fishing Detection — From Raw Data to Training-Ready

> **Goal:** Transform all raw data sources into a unified, clean, feature-rich dataset ready for ST-GAT model training.
> **Timeline:** Week 2 of Gemastik XIX 2026
> **Output:** `data/processed/` with training-ready Parquet files + graph objects

---

## 📊 Data Inventory

### Source Files & Schemas

| # | Source | File | Records | Format | Key Fields |
|---|--------|------|---------|--------|------------|
| 1 | GFW Fishing Events | `gfw/fishing_events_indonesia_2020-2025.json.gz` | 285,226 | JSON array | id, start, end, lat, lon, vessel.mmsi, vessel.geartype, vessel.flag, regions, distances |
| 2 | GFW Encounters | `gfw/encounters_indonesia_2020-2024.json.gz` | 46,264 | JSON array | id, start, end, lat, lon, vessel (×2), regions |
| 3 | GFW Loitering | `gfw/loitering_indonesia_2020-2025_corrected.json.gz` | 127,484 | JSON array | id, start, end, lat, lon, vessel, regions, distances |
| 4 | GFW Port Visits | `gfw/port_visits_indonesia_2020-2025.json.gz` | 53,298 | JSON array | id, start, end, lat, lon, vessel, port.name, regions |
| 5 | GWR SAR Presence | `gfw/4wings_sar_presence_indonesia_corrected.json.gz` | 1,242,915 | JSON (nested) | mmsi, date, lat, lon, detections, flag, geartype |
| 6 | GFW Fishing Effort | `gfw/4wings_fishing_effort_indonesia_corrected.json.gz` | 890,411 | JSON (nested) | mmsi, date, lat, lon, hours, flag, geartype |
| 7 | Zenodo Vessel Registry | `zenodo/fishing-vessels-v3.csv` | ~2M+ | CSV | mmsi, year, flag_ais, vessel_class, length_m, engine_power_kw, tonnage_gt |
| 8 | Zenodo Monthly Effort | `zenodo/fleet-monthly-csvs-10-v3-{year}.zip` | ~607 MB | CSV (zipped) | mmsi, date, lat, lon, hours, flag, geartype |
| 9 | EEZ Boundaries | `gis/eez_v12_lowres.gpkg` | Global | GeoPackage | ISO_TER1, geometry (polygons) |
| 10 | MPA Boundaries | `gis/indonesia_mpa_sample.geojson` | 12 areas | GeoJSON | name, geometry |
| 11 | BMKG Weather | `bmkg/marine_weather_2024.csv` | 2,921 | CSV | date, zone, lon, lat, wind_speed, wave_height, temp, visibility, precipitation |
| 12 | VIIRS Detections | `viirs/sample_vbd_detections_2024.csv` | 5,001 | CSV | date_gmt, time_gmt, lon, lat, quality_flag, radiance |
| 13 | Indonesia Ports | `gfw/osm_indonesia_ports_manual.json` | 30 | JSON | name, lat, lon |

**Total raw records: ~2.6M+**

---

## 🏗️ Pipeline Architecture

```
Phase 1: Load & Flatten          Phase 2: Clean & Validate         Phase 3: Feature Engineering
┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
│ GFW Events JSON  │──────┐      │ Deduplication    │──────┐      │ Vessel Features │
│ GFW SAR JSON     │──────┤      │ Null handling    │──────┤      │ Spatial Features│
│ GFW Effort JSON  │──────┼────► │ Type casting     │──────┼────► │ Temporal Features│
│ Zenodo CSV       │──────┤      │ Coordinate valid.│──────┤      │ Behavioral Flags│
│ Weather CSV      │──────┤      │ Date normalization│──────┤      │ Graph Features  │
│ VIIRS CSV        │──────┤      │ Flag standardize │──────┤      │ Labels          │
│ GIS Shapefiles   │──────┘      │ Outlier removal  │──────┘      │ Enrichment      │
└─────────────────┘              └─────────────────┘              └─────────────────┘
       ↓                                ↓                                ↓
  Parquet files                   Cleaned Parquet                 Training Dataset
  (intermediate)                  (validated)                     (graph + features)
```

---

## Phase 1: Load & Flatten (Day 1) ✅ COMPLETE (2026-04-21)

> **Status:** All 8 Parquet files generated. See `docs/PHASE1_AUDIT_FINDINGS.md` for detailed audit results.

### Step 1.1: GFW Events → Unified Events Table ✅

**Input:** 4 GFW event files (fishing, encounters, loitering, port visits)
**Output:** `data/processed/gfw_events_flat.parquet`

```python
# Target schema for unified events
gfw_events_flat = pd.DataFrame({
    "event_id": str,          # Unique event ID
    "event_type": str,        # fishing | encounter | loitering | port_visit
    "start_time": datetime64,
    "end_time": datetime64,
    "duration_hours": float,
    "lat": float,
    "lon": float,
    "bbox_minlon": float,
    "bbox_minlat": float,
    "bbox_maxlon": float,
    "bbox_maxlat": float,
    "mmsi": str,              # Primary vessel
    "mmsi_2": str,            # Secondary vessel (encounters only)
    "vessel_name": str,
    "vessel_flag": str,
    "vessel_geartype": str,
    "vessel_length": float,
    "vessel_tonnage": float,
    "eez_id": str,
    "in_mpa": bool,
    "mpa_ids": list[str],
    "in_highseas": bool,
    "fao_zone": str,
    "rfmo": list[str],
    "distance_shore_km": float,
    "distance_port_km": float,
    "port_name": str,          # Port visits only
})
```

**Actions:**
- Parse each JSON.gz file
- Flatten nested `position`, `regions`, `distances`, `vessel` dicts
- Handle encounters (2 vessels per event → `mmsi` + `mmsi_2`)
- Extract EEZ code, check `regions.eez` for Indonesia code `8492`
- Concatenate all 4 event types with `event_type` label
- Save as Parquet with Snappy compression

### Step 1.2: GFW SAR & Effort → Grid Tables

**Input:** SAR presence JSON, fishing effort JSON
**Output:** `data/processed/sar_presence_flat.parquet`, `data/processed/fishing_effort_flat.parquet`

```python
# SAR schema
sar_flat = pd.DataFrame({
    "mmsi": str,
    "date": str,              # "2020-08" monthly
    "lat": float,
    "lon": float,
    "detections": int,
    "flag": str,
    "geartype": str,
    "entry_timestamp": datetime64,
    "exit_timestamp": datetime64,
})

# Effort schema
effort_flat = pd.DataFrame({
    "mmsi": str,
    "date": str,              # "2020-12" monthly
    "lat": float,
    "lon": float,
    "fishing_hours": float,
    "flag": str,
    "geartype": str,
    "vessel_name": str,
})
```

**Actions:**
- Parse nested JSON structure (metadata + entries → array of records)
- Extract from `public-global-sar-presence:v4.0` and `public-global-fishing-effort:v4.0` sub-objects
- Flatten to one row per (mmsi, date, lat, lon) observation

### Step 1.3: Zenodo Vessel Registry

**Input:** `fishing-vessels-v3.csv`
**Output:** `data/processed/vessel_registry.parquet`

```python
vessel_registry = pd.DataFrame({
    "mmsi": str,
    "year": int,
    "flag_ais": str,
    "flag_registry": str,
    "flag_gfw": str,
    "vessel_class": str,        # Best available (inferred > gfw > registry)
    "length_m": float,          # Best available
    "engine_power_kw": float,
    "tonnage_gt": float,
    "self_reported_fishing": bool,
})
```

**Actions:**
- Read CSV (110MB, ~2M+ rows)
- Filter to vessels that appear in Indonesian waters (flag contains IDN, OR appear in GFW events with Indonesian EEZ)
- Resolve multiple flag/class sources: prioritize `inferred` > `gfw` > `registry`
- Keep latest year record per MMSI as the "current" vessel profile

### Step 1.4: Zenodo Monthly Effort

**Input:** 5 zip files (2020–2024)
**Output:** `data/processed/zenodo_effort_flat.parquet`

**Actions:**
- Extract CSV from each zip
- Filter to Indonesia-related records (flag=IDN or coordinates in Indonesian EEZ)
- Concatenate all years
- Schema matches GFW effort (mmsi, date, lat, lon, hours, flag, geartype)

### Step 1.5: Weather, VIIRS, GIS, Ports

**Input:** Various CSV/GeoJSON files
**Output:** Individual Parquet/GeoParquet files

```python
# Weather → data/processed/weather.parquet
# Already clean CSV, just type-cast and parse dates

# VIIRS → data/processed/viirs_detections.parquet
# Already clean CSV, parse dates, validate coordinates

# Ports → data/processed/ports.parquet
# 30 ports, simple lat/lon/name

# EEZ → load GeoPackage, filter ISO_TER1=="IDN", save as GeoParquet
# MPA → load GeoJSON, save as GeoParquet
```

---

## Phase 2: Clean & Validate (Day 2) ✅ COMPLETE (2026-04-21)

### Step 2.1: Deduplication

| Dataset | Strategy |
|---------|----------|
| GFW Events | Dedup on `event_id` (unique) |
| SAR Presence | Dedup on `(mmsi, date, lat, lon)` |
| Fishing Effort | Dedup on `(mmsi, date, lat, lon)`, sum `hours` if duplicate |
| Vessel Registry | Keep latest year per MMSI |
| Zenodo Effort | Dedup on `(mmsi, date, lat, lon)`, sum `hours` |

### Step 2.2: Null Handling

| Field | Strategy |
|-------|----------|
| `mmsi` | **DROP rows without MMSI** — cannot track vessels without ID |
| `lat/lon` | **DROP rows** — cannot do spatial analysis without coordinates |
| `vessel_flag` | Fill from vessel registry (Zenodo) if available, else "UNKNOWN" |
| `vessel_geartype` | Fill from vessel registry, else "UNKNOWN" |
| `vessel_length/tonnage` | Fill with median by `geartype` |
| `distance_shore/port` | Recalculate from coordinates if missing |
| `eez_id` | Spatial join with EEZ shapefile |
| `fishing_hours` | Fill 0 for non-fishing events |

### Step 2.3: Coordinate Validation

```python
# Indonesia bounding box (generous)
LAT_RANGE = (-11.5, 6.5)    # Sumatra tip to Sulawesi north
LON_RANGE = (95.0, 141.5)   # Aceh to Papua

# Filter rules:
# 1. lat must be in [-90, 90], lon in [-180, 180]
# 2. Keep events within OR near Indonesian EEZ (buffer 50km)
# 3. Flag events on land (distance_to_shore == 0 AND not port_visit) as suspicious
```

### Step 2.4: Date Normalization

```python
# All timestamps → UTC datetime
# SAR/Effort dates are monthly strings "2020-08" → first day of month
# Event timestamps are ISO 8601 → parse directly
# Add derived columns:
#   - hour_of_day (0-23)
#   - day_of_week (0-6)
#   - month (1-12)
#   - year
#   - is_nighttime (based on local hour ~18:00-06:00 WIB)
```

### Step 2.5: Flag Standardization

```python
# Normalize country flags to ISO 3166-1 alpha-3
# Common mappings:
FLAG_MAP = {
    "IDN": "IDN", "INA": "IDN",        # Indonesia
    "CHN": "CHN", "CHINA": "CHN",      # China
    "TWN": "TWN", "ROC": "TWN",        # Taiwan
    "VNM": "VNM", "VIETNAM": "VNM",    # Vietnam
    "MYS": "MYS", "MALAYSIA": "MYS",   # Malaysia
    "PHL": "PHL", "PNG": "PNG",        # Philippines, PNG
    "THA": "THA", "KOR": "KOR",        # Thailand, South Korea
}

# Add column: is_domestic (flag == "IDN")
# Add column: is_foreign (flag != "IDN")
```

### Step 2.6: Outlier Removal

| Check | Rule | Action |
|-------|------|--------|
| Duration outliers | Events > 72 hours (fishing), > 168 hours (loitering) | Cap at 99th percentile |
| Speed outliers | implied speed > 30 knots (from event distance/duration) | Flag, don't remove |
| Coordinate outliers | Outside Indonesian EEZ + 100km buffer | Remove |
| Duplicate vessels | Same MMSI, same timestamp, different positions | Keep most recent |
| Unrealistic tonnage | vessel tonnage > 100,000 GT | Flag, investigate |

### Step 2.7: Spatial Validation

```python
# For each event:
# 1. Verify EEZ assignment via spatial join with eez_v12_lowres.gpkg
# 2. Check MPA membership via spatial join with MPA polygons
# 3. Recalculate distance_to_shore if missing or suspicious
# 4. Add nearest port (from ports table)
# 5. Add sea zone name (Java Sea, Celebes Sea, etc.)
```

**Output:** `data/processed/gfw_events_clean.parquet`

---

## Phase 3: Feature Engineering (Day 3–4)

### Step 3.1: Vessel Profile Features

Join events with vessel registry on `mmsi`:

```python
vessel_features = {
    "vessel_length_m": float,        # From registry
    "vessel_tonnage_gt": float,
    "vessel_engine_kw": float,
    "vessel_class": str,             # trawler, purse_seine, longline, etc.
    "is_fishing_vessel": bool,
    "vessel_age_years": int,         # Current year - build year (if available)
    "size_category": str,            # small (<12m), medium (12-24m), large (>24m)
    "tonnage_per_length": float,     # Density proxy
}
```

### Step 3.2: Spatial Features

```python
spatial_features = {
    # Location context
    "lat": float,
    "lon": float,
    "in_indonesian_eez": bool,
    "in_mpa": bool,
    "mpa_name": str,                 # Which MPA
    "distance_to_shore_km": float,
    "distance_to_port_km": float,
    "nearest_port_name": str,
    "sea_zone": str,                 # Java Sea, Celebes Sea, etc.
    "fao_zone": str,
    
    # Risk zones
    "in_high_risk_area": bool,       # Known IUU hotspots
    "near_border": bool,             # Within 20km of EEZ boundary
    "near_mpa_boundary": bool,       # Within 5km of MPA edge
    
    # Grid cell (0.1° ≈ 11km resolution for aggregation)
    "grid_lat": float,               # Rounded to 0.1°
    "grid_lon": float,
}
```

### Step 3.3: Temporal Features

```python
temporal_features = {
    "timestamp": datetime64,
    "hour_of_day": int,              # 0-23
    "day_of_week": int,              # 0-6
    "month": int,                    # 1-12
    "year": int,
    "is_nighttime": bool,            # 18:00-06:00 local
    "is_weekend": bool,
    "season": str,                   # wet (Nov-Mar), dry (Apr-Oct)
    "duration_hours": float,
    "duration_category": str,        # short (<2h), medium (2-8h), long (>8h)
}
```

### Step 3.4: Behavioral Features (per vessel)

```python
# Compute per-vessel behavioral profile (rolling windows)
behavioral_features = {
    "mmsi": str,
    
    # Fishing patterns
    "avg_fishing_hours_per_trip": float,
    "total_fishing_days_30d": int,
    "total_fishing_hours_30d": float,
    "fishing_frequency_7d": int,       # How many fishing events in last 7 days
    
    # Spatial patterns
    "avg_distance_from_shore": float,
    "max_distance_from_shore": float,
    "spatial_range_km": float,         # Max distance between any two events
    "unique_grid_cells_30d": int,      # How many different areas fished
    
    # Port behavior
    "port_visits_30d": int,
    "avg_time_in_port_hours": float,
    "time_since_last_port": float,     # Hours since last port visit
    
    # Encounter patterns
    "encounters_30d": int,
    "encounters_with_foreign_30d": int,
    
    # Loitering patterns
    "loitering_events_30d": int,
    "total_loitering_hours_30d": float,
    
    # AIS gaps (potential transponder off)
    "ais_gap_events_30d": int,         # Periods with no AIS data
    "longest_ais_gap_hours": float,
    
    # Route complexity
    "avg_speed_knots": float,
    "speed_variance": float,           # High variance = erratic behavior
    "heading_changes_per_hour": float, # Frequent heading changes
}
```

### Step 3.5: Cross-Source Enrichment

```python
# For each GFW event, enrich with:

# 1. Weather at event location/time
weather_enrichment = {
    "wind_speed_knots": float,
    "wave_height_m": float,
    "sea_surface_temp": float,
    "visibility_km": float,
    "precipitation_mm": float,
}
# Strategy: Nearest-neighbor join on (date, nearest grid cell)

# 2. VIIRS detection proximity
viirs_enrichment = {
    "viirs_detection_within_24h": bool,    # Any VIIRS detection within 24h & 10km
    "viirs_detection_count_nearby": int,    # Count within 48h & 20km
    "viirs_avg_radiance_nearby": float,
}
# Strategy: Spatial-temporal join (event lat/lon ± 0.1°, event date ± 1 day)

# 3. SAR presence in same grid cell
sar_enrichment = {
    "sar_detections_same_cell_month": int,
    "sar_vessels_same_cell_month": int,    # Unique MMSI count
}
# Strategy: Match on (grid_lat, grid_lon, month)

# 4. Fishing effort density in area
effort_enrichment = {
    "effort_hours_same_cell_month": float,  # Total fishing hours in this grid cell/month
    "effort_vessels_same_cell_month": int,  # Unique vessels fishing here
    "effort_density_percentile": float,     # Where does this cell rank
}
```

---

## Phase 4: Label Generation (Day 4)

### Step 4.1: IUU Label Definition

This is the **most critical step** — defining what constitutes IUU fishing.

```python
# IUU scoring approach (multi-signal)
iuu_indicators = {
    # Direct IUU signals (high confidence)
    "fishing_in_mpa": bool,                # Fishing event inside Marine Protected Area
    "fishing_without_license": bool,        # Foreign vessel in Indonesian EEZ (no bilateral agreement)
    "transponder_off_during_fishing": bool,  # AIS gap detected near fishing activity
    "encounter_at_sea": bool,               # Met another vessel at sea (potential transshipment)
    "loitering_near_fishing_ground": bool,   # Loitering behavior near known fishing areas
    
    # Indirect IUU signals (medium confidence)
    "nighttime_fishing": bool,              # Fishing primarily at night
    "near_border_fishing": bool,            # Fishing near EEZ boundary
    "repeated_ais_gaps": bool,              # Multiple AIS gaps in short period
    "unregistered_vessel": bool,            # MMSI not in any vessel registry
    "flag_mismatch": bool,                  # AIS flag differs from registry flag
    
    # Behavioral anomalies (lower confidence)
    "unusual_fishing_hours": bool,          # Far more/less hours than typical for gear type
    "unusual_location": bool,               # Fishing in atypical area for vessel type
    "rapid_port_entry_exit": bool,          # Quick port visits (smuggling indicator)
}
```

### Step 4.2: Label Assignment Strategy

```
┌─────────────────────────────────────────────────────┐
│              IUU Label Assignment                    │
│                                                      │
│  Tier 1 (Hard IUU):                                  │
│  - Fishing inside MPA                                │
│  - Foreign vessel fishing in EEZ                     │
│  - AIS gap + SAR detection (transponder off)         │
│  → Label: IUU = 1                                    │
│                                                      │
│  Tier 2 (Probable IUU):                              │
│  - Encounter at sea + transshipment pattern           │
│  - Repeated AIS gaps + loitering                      │
│  - Unregistered vessel                               │
│  → Label: IUU = 1 (if 2+ indicators)                 │
│                                                      │
│  Tier 3 (Suspicious):                                │
│  - Nighttime fishing + near border                    │
│  - Unusual patterns for vessel type                   │
│  → Label: IUU = 0.5 (soft label / anomaly score)     │
│                                                      │
│  Normal:                                              │
│  - Registered domestic vessel                        │
│  - Fishing in permitted areas                        │
│  - Consistent AIS transmission                       │
│  → Label: IUU = 0                                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Step 4.3: SAR-AIS Cross-Matching (Key IUU Detection Signal)

```python
"""
SAR detects vessels by satellite — including those with AIS turned off.
If SAR detects a vessel at a location/time but NO AIS data exists nearby,
this is a strong IUU signal (transponder deliberately disabled).

Algorithm:
1. For each SAR detection (lat, lon, date):
   a. Search AIS events within ±6 hours and ±5km
   b. If NO AIS match found → "dark vessel" detection
   c. Count dark vessel detections per grid cell/month
2. For each AIS-equipped vessel:
   a. Check if SAR detected OTHER vessels nearby during their fishing events
   b. This indicates potential illegal transshipment or buddy boats
"""
```

---

## Phase 5: Graph Construction (Day 5)

### Step 5.1: Vessel Trajectory Graph

```python
"""
Graph structure for ST-GAT:

NODES: Vessel-time points
  - Each vessel observation (event or track point) is a node
  - Node features: [lat, lon, speed, heading, vessel_features, behavioral_features]

EDGES: Two types
  1. Spatial edges: Connect vessels within proximity_threshold (e.g., 20km)
     - Edge features: distance_km, relative_bearing
  2. Temporal edges: Connect same vessel across time
     - Edge features: time_delta_hours, distance_traveled_km

TEMPORAL SNAPSHOTS:
  - Divide data into time windows (e.g., 6-hour or daily snapshots)
  - Each snapshot is a separate graph
  - Temporal attention connects snapshots
"""
```

### Step 5.2: Graph Feature Matrix

```python
# Node feature matrix (per vessel-time point)
node_features = [
    # Normalized spatial (0-1)
    "lat_norm", "lon_norm",
    
    # Temporal (cyclical encoding)
    "hour_sin", "hour_cos",       # sin/cos of hour for cyclical
    "month_sin", "month_cos",
    
    # Vessel characteristics (normalized)
    "length_norm", "tonnage_norm", "engine_norm",
    "is_domestic",
    "geartype_encoded",           # One-hot or label encoded
    
    # Behavioral (normalized)
    "fishing_hours_7d_norm",
    "port_visits_7d_norm",
    "encounters_7d_norm",
    "loitering_7d_norm",
    "distance_shore_norm",
    "speed_norm",
    
    # Contextual
    "in_mpa", "in_high_risk",
    "weather_conditions_norm",
    "sar_detections_nearby_norm",
    
    # Label
    "iuu_label",                  # 0, 0.5, or 1
]
```

---

## Phase 6: Dataset Split & Export (Day 5)

### Step 6.1: Train/Val/Test Split

```
Temporal split (no data leakage):
├── Train: 2020-01 to 2023-12   (80%)
├── Val:   2024-01 to 2024-06  (10%)
└── Test:  2024-07 to 2025-03  (10%)

Stratified by:
- IUU label ratio (maintain class balance)
- Vessel flag (domestic vs foreign)
- Event type (fishing, loitering, encounter)
```

### Step 6.2: Output Files

```
data/processed/
├── gfw_events_flat.parquet          # Phase 1: Raw flattened
├── gfw_events_clean.parquet         # Phase 2: Cleaned & validated
├── vessel_registry_clean.parquet    # Phase 2: Cleaned vessel data
├── sar_presence_flat.parquet        # Phase 1: Flattened SAR
├── fishing_effort_flat.parquet      # Phase 1: Flattened effort
├── zenodo_effort_flat.parquet       # Phase 1: Zenodo effort
├── weather_clean.parquet            # Phase 2: Cleaned weather
├── viirs_clean.parquet              # Phase 2: Cleaned VIIRS
├── ports_clean.parquet              # Phase 2: Cleaned ports
├── gfw_events_enriched.parquet      # Phase 3: All features joined
├── vessel_profiles.parquet          # Phase 3: Per-vessel behavioral profiles
├── iuu_labels.parquet               # Phase 4: IUU labels + indicators
├── graph_data/
│   ├── nodes.parquet                # Phase 5: Node features
│   ├── edges_spatial.parquet        # Phase 5: Spatial edges
│   ├── edges_temporal.parquet       # Phase 5: Temporal edges
│   └── graph_metadata.json          # Phase 5: Graph config
├── train/
│   ├── nodes.parquet
│   ├── edges_spatial.parquet
│   └── edges_temporal.parquet
├── val/
│   └── ...
└── test/
    └── ...
```

---

## 🔧 Implementation Scripts

### New files to create in `src/`:

```
src/
├── data/
│   ├── loaders.py              # All Phase 1 loaders (GFW, SAR, Zenodo, etc.)
│   └── validators.py           # Phase 2 validation functions
├── features/
│   ├── vessel_features.py      # Step 3.1: Vessel profile features
│   ├── spatial_features.py     # Step 3.2: Spatial features + GIS joins
│   ├── temporal_features.py    # Step 3.3: Temporal features
│   ├── behavioral_features.py  # Step 3.4: Per-vessel behavioral profiles
│   └── enrichment.py           # Step 3.5: Cross-source enrichment
├── labeling/
│   ├── iuu_rules.py            # Step 4.1-4.2: IUU label assignment
│   └── sar_ais_match.py        # Step 4.3: SAR-AIS cross-matching
├── graph/
│   ├── build_graphs.py         # Step 5: Graph construction
│   └── split_dataset.py        # Step 6: Train/val/test split
└── pipeline.py                 # Orchestrator: run full pipeline
```

### Master Pipeline Script

```python
# python -m src.pipeline --phase all --output data/processed/

# Or individual phases:
# python -m src.pipeline --phase load      # Phase 1 only
# python -m src.pipeline --phase clean     # Phase 2 only
# python -m src.pipeline --phase features  # Phase 3 only
# python -m src.pipeline --phase label     # Phase 4 only
# python -m src.pipeline --phase graph     # Phase 5 only
# python -m src.pipeline --phase split     # Phase 6 only
```

---

## ⚠️ Known Challenges & Mitigations

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| **Class imbalance** (few IUU vs many normal) | Model bias toward normal | SMOTE/oversampling, weighted loss, anomaly detection approach |
| **Missing vessel registry data** | Can't identify unregistered vessels | Use SAR cross-matching as alternative signal |
| **Weather data only 2024** | Can't enrich historical events | Use Open-Meteo historical API for backfill |
| **VIIRS is sample data** | Limited VIIRS enrichment | Focus on SAR + AIS as primary IUU signals |
| **BPS data incomplete** | No ground truth on legal catch | Use as supplementary feature only |
| **Zenodo effort only 2020-2021** | Gaps in 2022-2024 effort | Use GFW 4Wings effort (already have) |
| **MPA boundaries are sample** | Incomplete MPA coverage | Download full WDPA dataset |
| **SAR is gridded (0.1°)** | Not precise vessel positions | Use as area-level signal, not point-level |
| **No ground truth labels** | IUU labels are heuristic | Use multi-tier approach with confidence scores |

---

## 📅 Daily Schedule

| Day | Phase | Tasks | Estimated Time |
|-----|-------|-------|----------------|
| **Day 1** | Phase 1 | Load & flatten all sources → Parquet | 4-6 hours |
| **Day 2** | Phase 2 | Clean, validate, dedup, spatial joins | 4-6 hours |
| **Day 3** | Phase 3.1-3.3 | Vessel, spatial, temporal features | 4-5 hours |
| **Day 4** | Phase 3.4-3.5 | Behavioral features, cross-source enrichment | 5-6 hours |
| **Day 4** | Phase 4 | IUU labeling + SAR-AIS matching | 3-4 hours |
| **Day 5** | Phase 5-6 | Graph construction + dataset split | 4-6 hours |

**Total estimated: 24-33 hours of focused work**

---

## ✅ Validation Checkpoints

After each phase, validate:

- [ ] **Phase 1:** Row counts match expected (±5%), no data loss
- [ ] **Phase 2:** No nulls in critical fields (mmsi, lat, lon, timestamp)
- [ ] **Phase 3:** Feature distributions look reasonable (no infinity, no negative distances)
- [ ] **Phase 4:** IUU label distribution: expect 5-15% positive (if too high/low, review rules)
- [ ] **Phase 5:** Graph connectivity: average degree ≥ 2, no disconnected components > 50%
- [ ] **Phase 6:** Train/val/test have similar label distribution (±2%)

---

*Generated: 2026-04-21*
*Project: IUU Fishing Detection — Gemastik XIX 2026*
*Team: Toni, Nafi, Rhendy*
