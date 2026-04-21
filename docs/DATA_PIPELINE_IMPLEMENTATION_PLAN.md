# 📋 Implementation Plan: Data Cleaning & Feature Engineering Pipeline

## IUU Fishing Detection — From Raw Data to Training-Ready

> **Goal:** Transform all raw data sources into a unified, clean, feature-rich dataset ready for ST-GAT model training.
> **Status:** Phases 1–3 complete and validated (2026-04-22). Phases 4–6 are TODO.
> **Output:** `data/processed/` with 14 Parquet files; final: `gfw_events_full.parquet` (512K rows, 121 cols)

---

## 📊 Data Inventory (Actual)

### Source Files

| # | Source | File | Records | Format |
|---|--------|------|---------|--------|
| 1 | GFW Fishing Events | `gfw/fishing_events_indonesia_2020-2025.json.gz` | 285,226 | JSON array |
| 2 | GFW Encounters | `gfw/encounters_indonesia_2020-2024.json.gz` | 46,264 | JSON array |
| 3 | GFW Loitering | `gfw/loitering_indonesia_2020-2025_corrected.json.gz` | 127,484 | JSON array |
| 4 | GFW Port Visits | `gfw/port_visits_indonesia_2020-2025.json.gz` | 53,298 | JSON array |
| 5 | GFW SAR Presence | `gfw/4wings_sar_presence_indonesia_corrected.json.gz` | 1,242,915 | JSON (nested) |
| 6 | GFW Fishing Effort | `gfw/4wings_fishing_effort_indonesia_corrected.json.gz` | 890,411 | JSON (nested) |
| 7 | Zenodo Vessel Registry | `zenodo/fishing-vessels-v3.csv` | ~2M+ | CSV |
| 8 | Zenodo Monthly Effort | `zenodo/fleet-monthly-csvs-10-v3-{year}.zip` | ~607 MB | CSV (zipped) |
| 9 | BMKG Weather | `bmkg/marine_weather_2024.csv` | 2,921 | CSV |
| 10 | VIIRS Detections | `viirs/sample_vbd_detections_2024.csv` | 5,001 | CSV |
| 11 | Indonesia Ports | `gfw/osm_indonesia_ports_manual.json` | 30 | JSON |

**Note:** EEZ shapefiles (`gis/eez_v12_lowres.gpkg`) and MPA boundaries (`gis/indonesia_mpa_sample.geojson`) exist but were **not used** in the pipeline. No spatial join was performed — EEZ/MPA info comes from GFW's `regions` field directly.

---

## 🏗️ Pipeline Architecture

```
Phase 1: Load & Flatten          Phase 2: Clean & Validate         Phase 3: Feature Engineering
┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
│ GFW Events JSON  │──────┐      │ Deduplication    │──────┐      │ Vessel Features │
│ GFW SAR JSON     │──────┤      │ Null handling    │──────┤      │ Spatial Features│
│ GFW Effort JSON  │──────┼────► │ Type casting     │──────┼────► │ Temporal Features│
│ Zenodo CSV       │──────┤      │ Coordinate valid.│──────┤      │ Behavioral Flags│
│ Weather CSV      │──────┤      │ Date normalization│──────┤      │ Cross-source    │
│ VIIRS CSV        │──────┤      │ Flag standardize │──────┤      │ Enrichment      │
│ Ports JSON       │──────┘      │ Outlier capping  │──────┘      │                 │
└─────────────────┘              └─────────────────┘              └─────────────────┘
       ↓                                ↓                                ↓
  *_flat.parquet                 *_clean.parquet              gfw_events_full.parquet
```

---

## Phase 1: Load & Flatten ✅ COMPLETE

### Step 1.1: GFW Events → Unified Events Table ✅

**Script:** `src/data/pipeline/extract.py`
**Input:** 4 GFW event JSON.gz files
**Output:** `data/processed/gfw_events_flat.parquet` (512,272 rows × 54 cols)

**Key implementation details:**
- `vessel.ssvid` is the MMSI field in GFW data (not `vessel.mmsi`)
- Encounter events have 2 vessels: primary in `vessel`, secondary in `encounter.vessel` → mapped to `mmsi` + `mmsi_2`
- EEZ/MPA/RFMO/FAO data extracted from GFW `regions` field (no shapefile join needed)
- `potential_risk` and `authorization_status` captured from GFW's `publicAuthorizations` fields
- Event-type specific fields (port_name, encounter_median_speed, loitering_total_hours, etc.) are null for other event types — expected

**Actual schema:** See `docs/PIPELINE_SCHEMA.md` → `gfw_events_flat.parquet`

**Validation:**
- 512,272 events across 4 types
- MMSI: `large_string` type ✅
- All timestamps: `datetime64[ns, UTC]` ✅

### Step 1.2: GFW SAR & Effort → Grid Tables ✅

**Script:** `src/data/pipeline/extract.py`
**Input:** SAR presence JSON, fishing effort JSON
**Output:**
- `sar_presence_flat.parquet` (1,242,915 rows × 13 cols) — includes ~40% grid-only rows (no MMSI)
- `fishing_effort_flat.parquet` (890,411 rows × 13 cols)

**Key implementation details:**
- SAR data has ~40% rows with no MMSI (grid-level detections only) — these are dropped in Phase 2
- Both use `vessel.ssvid` → `mmsi` mapping
- `detections` (int64) for SAR, `fishing_hours` (double) for effort

### Step 1.3: Zenodo Vessel Registry ✅

**Script:** `src/data/pipeline/extract.py`
**Input:** `zenodo/fishing-vessels-v3.csv`
**Output:** `vessel_registry.parquet` (147,924 rows × 12 cols)

**Key implementation details:**
- MMSI explicitly cast to `string` at load time (was int64 in CSV)
- Filtered to relevant flags (IDN + neighboring countries)
- All 12 columns: mmsi (str), year, flag_ais, flag_registry, flag_gfw, vessel_class, length_m, engine_power_kw, tonnage_gt, self_reported_fishing_vessel, active_hours, fishing_hours

### Step 1.4: Zenodo Monthly Effort ✅

**Script:** `src/data/pipeline/extract.py`
**Input:** 5 zip files (2020–2024)
**Output:** `zenodo_effort_flat.parquet` (707,118 rows × 10 cols)

**Key implementation details:**
- **Spatially filtered** to Indonesia bbox (lat -11.5 to 6.5, lon 95 to 141.5) during load — NOT flag-only filter
- Original global data was ~30M rows; spatial filter reduced to 707K
- Grid-level data: `mmsi_present` (int64 count) but no individual MMSI identifiers

**Difference from original plan:** Plan said "filter to Indonesia-related records (flag=IDN or coordinates in Indonesian EEZ)". Actual implementation filters by bbox only, which is more correct — captures foreign vessels in Indonesian waters.

### Step 1.5: Weather, VIIRS, Ports ✅

**Script:** `src/data/pipeline/extract.py`
**Output:**
- `weather.parquet` (2,920 rows × 9 cols) — lat/lon are int64 (zone centers)
- `viirs_detections.parquet` (5,000 rows × 8 cols) — `date_gmt` is int64 (parsed later)
- `ports.parquet` (30 rows × 3 cols)

**Validation:** All files load cleanly, types match schema.

---

## Phase 2: Clean & Validate ✅ COMPLETE

### Step 2.1: Deduplication ✅

**Script:** `src/data/pipeline/clean.py`

| Dataset | Input | Output | Duplicates |
|---------|-------|--------|------------|
| GFW Events | 512,272 | 512,247 | 25 event_id dupes |
| SAR Presence | 1,242,915 | 742,075 | ~500K grid-only (no MMSI) + 432 dupes |
| Fishing Effort | 890,411 | 885,649 | 4,762 dupes (hours summed) |
| Zenodo Effort | 707,118 | 707,118 | 0 dupes (spatially filtered) |
| Vessel Registry | 147,924 | 147,924 | 0 dupes |

**Key:** SAR grid-only rows (40%, no MMSI) dropped — cannot track vessels without ID.

### Steps 2.2–2.6: Clean & Validate GFW Events ✅

**Script:** `src/data/pipeline/clean.py`
**Output:** `gfw_events_clean.parquet` (512,247 rows × 66 cols)

**Actions performed:**
- Filled 58,097 missing vessel flags from registry
- Coordinate validation: all within Indonesia bbox (±2° buffer)
- Duration capping: 673 fishing @72h, 1,025 loitering @168h, 2,564 encounters @48h
- 0 speed outliers (>30 knots)
- Flag standardization via `FLAG_MAP` (constants.py) — ISO 3166 alpha-3
- Added: `is_domestic`, `is_foreign`, `in_indonesia_bbox`, `hour_of_day`, `day_of_week`, `month`, `year`, `is_nighttime`, `is_weekend`, `season`, `duration_hours`, `implied_speed_knots`, `speed_outlier`

### Step 2.7: Clean SAR/Effort/Zenodo ✅

**Script:** `src/data/pipeline/clean.py`
**Output:**
- `sar_presence_clean.parquet` (742,075 rows × 18 cols)
- `fishing_effort_clean.parquet` (885,649 rows × 18 cols)
- `zenodo_effort_clean.parquet` (707,118 rows × 12 cols)

**Actions performed:** Flag standardization, date parsing, temporal features (year, month, season), is_domestic flag. Memory-efficient chunked ParquetWriter for Zenodo.

---

## Phase 3: Feature Engineering ✅ COMPLETE

### Step 3.1: Vessel Profile + Spatial Features ✅

**Script:** `src/data/pipeline/features.py`

**Actions performed:**
- Registry join on `mmsi` (string): 1,598/14,857 MMSIs matched (50.3% fill rate)
- Added: `reg_vessel_class`, `reg_length_m`, `reg_engine_power_kw`, `reg_tonnage_gt`, `reg_flag_ais`, `is_fishing_vessel`, `size_category`, `tonnage_per_length`
- Duration category: short (<2h), medium (2-8h), long (>8h) — cast to string (not Categorical)
- Grid cell: 0.1° resolution (~11km) for spatial aggregation
- Nearest port: computed from 30 Indonesian ports (vectorized)
- Sea zone: vectorized with `np.select()` (Java Sea, Malacca Strait, Celebes Sea, etc.)

**Registry fill rate:** 50.3% — this is the real data. Many fishing vessels in Indonesian waters (especially foreign) are not in the Zenodo registry.

### Step 3.4: Per-Vessel Behavioral Features ✅

**Script:** `src/data/pipeline/features.py`
**Output:** `vessel_behavioral_features.parquet` (14,857 rows × 32 cols)

**Actions performed:**
- Per-vessel aggregation: total events, fishing/encounter/loitering/port counts
- Spatial range (max distance between any two events)
- Unique grid cells via two-stage groupby (dedup grid → count per vessel)
- Speed statistics, encounter/loitering rates, port visit patterns
- Key: `mmsi` (string), 1:1 with unique vessels

**Note:** Temporal features (hour_of_day, day_of_week, season, is_nighttime) are added during Phase 2 cleaning in `pipeline/clean.py`. Phase 3 focuses on vessel, spatial, and behavioral features.

### Step 3.5: Cross-Source Enrichment ✅

**Script:** `src/data/pipeline/enrich.py`
**Output:** `gfw_events_full.parquet` (512,247 rows × 121 cols, 80.7 MB)

**Actions performed:**
- **Weather:** Enriched via zone-based matching (all 8 weather zones). Weather columns prefixed `weather_`: lon, lat, wind_speed_knots, wave_height_m, sea_surface_temp_c, visibility_km, precipitation_mm
- **VIIRS:** Date-corrected join (`pd.to_datetime(str, format="%Y%m%d")`). Low match rate — VIIRS is sample data (5K rows, 2024 only)
- **SAR density:** Grid-cell/monthly detection counts → `sar_total_detections`, `sar_unique_vessels`
- **Fishing effort density:** Grid-cell/monthly fishing hours → `effort_hours_in_cell`, `effort_vessels_in_cell`
- **Behavioral features:** Merged per vessel from step 3.4
- **Column collisions eliminated:** No `_x/_y` suffixes in final output

**Difference from original plan:** Plan described weather as "nearest-neighbor join on (date, nearest grid cell)". Actual uses zone-based monthly averages (8 zones × 365 days). VIIRS date parsing was fixed from broken int64 comparison to proper `pd.to_datetime()` conversion.

---

## Final Dataset Summary

### `gfw_events_full.parquet` — 512,247 rows × 121 cols

| Category | Columns | Count |
|----------|---------|-------|
| Core (id, type, time, coords) | event_id through duration_hours | ~12 |
| Event-type specific | port_name, encounter_*, loitering_* | ~20 |
| Temporal | hour_of_day, day_of_week, month, year, season, etc. | ~8 |
| Flag/Domestic | is_domestic, is_foreign | 2 |
| Speed | avg_speed_knots, implied_speed_knots, speed_outlier | 3 |
| Registry | reg_vessel_class through tonnage_per_length | ~9 |
| Spatial | grid_lat, grid_lon, sea_zone, nearest_port_* | ~6 |
| Weather | weather_lon through weather_precipitation_mm | 7 |
| VIIRS | viirs_count, viirs_avg_radiance, viirs_detection_nearby | 3 |
| SAR/Effort density | sar_total_detections, effort_hours_in_cell | 4 |
| Behavioral | total_events through avg_fishing_hours_per_trip | ~32 |

### Validation Results (2026-04-22)
- ✅ 100% coordinates within Indonesia bbox
- ✅ 0 duplicate event_ids
- ✅ MMSI `large_string` type consistent across all files
- ✅ 82/121 columns have 0% null
- ✅ 28 columns >50% null (event-type specific — expected)
- ✅ 0 column name collisions (_x/_y eliminated)
- ✅ No `__index_level_0__` index leak

### Class Distribution
| Event Type | Count | % |
|-----------|-------|---|
| Fishing | ~287K | 56% |
| Loitering | ~128K | 25% |
| Port Visit | ~51K | 10% |
| Encounter | ~46K | 9% |

### Flag Distribution
- Domestic (IDN): 47%
- Foreign: 53%
- `potential_risk`: 0.4% True (very imbalanced — needs SMOTE/weighted loss)

### ML Encoding Needed
- 27 `large_string` columns → label/one-hot encoding
- 8 `object` (list) columns → multi-hot or drop (eez_ids, mpa_ids, rfmo, fao_zones, authorized_rfmos)
- bool columns → int (0/1)

---

## Phase 4: Label Generation — TODO

Not yet implemented. Original plan:

### Step 4.1: IUU Label Definition
Multi-signal IUU scoring:
- **Tier 1 (Hard IUU):** Fishing in MPA, foreign vessel in EEZ, AIS gap + SAR detection
- **Tier 2 (Probable IUU):** Encounter at sea + transshipment, repeated AIS gaps, unregistered vessel
- **Tier 3 (Suspicious):** Nighttime fishing + near border, unusual patterns

### Step 4.2: SAR-AIS Cross-Matching
Detect "dark vessels" by comparing SAR detections against AIS data within ±6h and ±5km.

**Blocker:** `potential_risk` flag is only 0.4% True — class imbalance will be severe. May need anomaly detection approach instead of supervised classification.

---

## Phase 5: Graph Construction — TODO

### Step 5.1: Vessel Trajectory Graph
- Nodes: vessel-time points with feature vectors
- Spatial edges: vessels within 20km proximity
- Temporal edges: same vessel across time snapshots
- ST-GAT architecture: temporal attention connects snapshots

### Step 5.2: Graph Feature Matrix
~25 normalized features per node (spatial, temporal, vessel, behavioral, contextual).

**Current state:** `src/features/graph_builder.py` exists as placeholder only.

---

## Phase 6: Dataset Split & Export — TODO

### Step 6.1: Temporal Train/Val/Test Split
- Train: 2020–2023 (80%)
- Val: 2024-H1 (10%)
- Test: 2024-H2 to 2025 (10%)
- Stratified by IUU label, vessel flag, event type

---

## ⚠️ Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Registry fill rate 50.3% | Missing vessel characteristics for ~half of vessels | Use SAR cross-matching as alternative signal |
| Weather data only 2024 | Historical events lack weather enrichment | Use Open-Meteo historical API for backfill |
| VIIRS is sample data (5K) | Limited VIIRS enrichment, low match rate | Focus on SAR + AIS as primary signals |
| No EEZ/MPA spatial join | Uses GFW's region fields instead of shapefile join | GFW regions data is reliable for Indonesia |
| `potential_risk` only 0.4% | Severe class imbalance for supervised learning | Consider anomaly detection or semi-supervised approach |
| 30 ports only | Limited nearest-port coverage for all of Indonesia | Add more ports from OSM/GFW |
| Zenodo 2021 zip was corrupted | Had to re-download | Fixed, data verified |

---

## 🔧 Implementation Scripts (Actual)

```
src/data/
├── constants.py              # Shared: FLAG_MAP, INDONESIA_BBOX, paths, filenames
├── pipeline/
│   ├── extract.py            # Phase 1: Load & flatten all raw data
│   ├── clean.py              # Phase 2: Dedup, validate, normalize
│   ├── features.py           # Phase 3a: Vessel profile + behavioral features
│   └── enrich.py             # Phase 3b: Cross-source enrichment
└── clients/
    └── gfw.py                # GFW API client

scripts/
└── run_pipeline.py           # Master runner: --phase/--step args
```

---

## Deviations from Original Plan

| Planned | Actual | Reason |
|---------|--------|--------|
| MMSI as int in registry | MMSI as string everywhere | GFW uses string ssvid; join compatibility |
| Zenodo filtered by flag | Zenodo filtered by bbox | 30M global rows; flag filter missed foreign vessels in IDN waters |
| 4 weather zones | 8 weather zones | BMKG data has 8 zones; mapping was too coarse |
| EEZ/MPA spatial join | GFW regions field | No usable shapefiles available at time of implementation |
| VIIRS date as datetime | VIIRS date_gmt as int64, parsed manually | Raw data format; `pd.to_datetime(str, format="%Y%m%d")` |
| `df.apply()` for sea_zone | `np.select()` vectorized | 100x faster on 512K rows |
| Lambda for unique_grid_cells | Two-stage groupby | Original lambda was buggy |
| Steps 3.2-3.3 separate | Already done in Phase 2 | Temporal features added during cleaning |
| 124 columns (audit) | 121 columns (final) | 3 columns removed/merged during collision fix |

---

*Updated: 2026-04-22*
*Project: IUU Fishing Detection — Gemastik XIX 2026*
*Team: Toni, Nafi, Rhendy*
