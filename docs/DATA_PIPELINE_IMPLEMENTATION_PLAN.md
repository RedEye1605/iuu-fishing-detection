# 📋 Implementation Plan: Data Cleaning & Feature Engineering Pipeline

## IUU Fishing Detection — From Raw Data to Training-Ready

> **Goal:** Transform all raw data sources into a unified, clean, feature-rich dataset ready for ST-GAT model training.
> **Status:** Phases 1–5 complete and validated (2026-04-22). Phase 6 is TODO.
> **Output:** `data/processed/` with 13 Parquet files; final: `gfw_events_labeled.parquet` (512K rows, 124 cols)

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

> **Note:** BMKG weather and VIIRS detection raw files exist in `data/raw/` but were **removed from the pipeline** in v0.7.0 due to insufficient coverage and signal. They are listed here for historical reference.

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
│ Ports JSON       │──────┘      │ Date normalization│──────┤      │ Cross-source    │
└─────────────────┘              │ Flag standardize │──────┤      │ Enrichment      │
                                 │ Outlier capping  │──────┘      │                 │
                                 └─────────────────┘              └─────────────────┘
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

### Step 1.5: Ports ✅

**Script:** `src/data/pipeline/extract.py`
**Output:**
- `ports.parquet` (30 rows × 3 cols)

`extract_auxiliary()` has been renamed to `extract_ports()` — it only loads port data now. Weather and VIIRS loading was removed in v0.7.0.

**Validation:** File loads cleanly, types match schema.

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
**Output:** `gfw_events_full.parquet` (512,247 rows × 111 cols)

**Actions performed:**
- **SAR density:** Grid-cell/monthly detection counts → `sar_total_detections`, `sar_unique_vessels`
- **Fishing effort density:** Grid-cell/monthly fishing hours → `effort_hours_in_cell`, `effort_vessels_in_cell`
- **Behavioral features:** Merged per vessel from step 3.4
- **Column collisions eliminated:** No `_x/_y` suffixes in final output

**Removed in v0.7.0:** Weather enrichment (7 cols) and VIIRS enrichment (3 cols) were removed due to insufficient coverage and signal.

---

## Final Dataset Summary

### `gfw_events_full.parquet` — 512,247 rows × 111 cols (pre-label)

### `gfw_events_labeled.parquet` — 512,247 rows × 124 cols (FINAL)

Same as `gfw_events_full.parquet` plus 13 new columns:
- 11 indicator booleans: `ind_fishing_in_mpa`, `ind_unauthorized_foreign`, `ind_high_seas_fishing`, `ind_encounter_at_sea`, `ind_loitering_anomaly`, `ind_unregistered_vessel`, `ind_nighttime_foreign`, `ind_high_encounter_rate`, `ind_high_loitering_rate`, `ind_far_offshore`, `ind_rapid_port_cycle`
- `iuu_score` (f64): Continuous score [0, 1]
- `iuu_label` (str): Categorical — normal / suspicious / probable_iuu / hard_iuu

| Category | Columns | Count |
|----------|---------|-------|
| Core (id, type, time, coords) | event_id through duration_hours | ~12 |
| Event-type specific | port_name, encounter_*, loitering_* | ~20 |
| Temporal | hour_of_day, day_of_week, month, year, season, etc. | ~8 |
| Flag/Domestic | is_domestic, is_foreign | 2 |
| Speed | avg_speed_knots, implied_speed_knots, speed_outlier | 3 |
| Registry | reg_vessel_class through tonnage_per_length | ~9 |
| Spatial | grid_lat, grid_lon, sea_zone, nearest_port_* | ~6 |
| SAR/Effort density | sar_total_detections, effort_hours_in_cell | 4 |
| Behavioral | total_events through avg_fishing_hours_per_trip | ~32 |

### Validation Results (2026-04-22)
- ✅ 100% coordinates within Indonesia bbox
- ✅ 0 duplicate event_ids
- ✅ MMSI `large_string` type consistent across all files
- ✅ 75/111 columns have 0% null
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

## Phase 4: IUU Label Generation ✅ COMPLETE

**Script:** `src/data/pipeline/labels.py`
**Input:** `gfw_events_full.parquet` (512,247 rows × 111 cols)
**Output:** `gfw_events_labeled.parquet` (512,247 rows × 124 cols)

### Step 4.1: 11 IUU Indicators across 3 Tiers ✅

**Tier 1 — Hard IUU (weight 1.0):**
- `ind_fishing_in_mpa`: Fishing inside no-take MPA (287 events, 0.06%)
- `ind_unauthorized_foreign`: Foreign vessel fishing in EEZ without authorization (140,912 events, 27.5%)
- `ind_high_seas_fishing`: Fishing outside any EEZ (11,768 events, 2.3%)

**Tier 2 — Suspicious Activity (weight 0.6):**
- `ind_encounter_at_sea`: Vessel-to-vessel encounter (46,239 events, 9.0%)
- `ind_loitering_anomaly`: Loitering with avg speed < 1 knot (87,661 events, 17.1%)
- `ind_unregistered_vessel`: Fishing vessel with no registry match (98,823 events, 19.3%)
- `ind_nighttime_foreign`: Foreign vessel fishing at night (70,217 events, 13.7%)

**Tier 3 — Behavioral Anomaly (weight 0.3):**
- `ind_high_encounter_rate`: Vessel encounter rate > p75 (127,639 events)
- `ind_high_loitering_rate`: Vessel loitering rate > p75 (128,019 events)
- `ind_far_offshore`: Operating > p90 distance from shore (50,684 events)
- `ind_rapid_port_cycle`: Port visit < 2 hours (2,904 events)

### Step 4.2: Scoring Formula ✅

Score = (tier1_any × 1.0 + tier2_count/2 × 0.6 + tier3_count/2 × 0.3) / 1.9

Normalized to [0, 1]. Division by 1.9 is the theoretical maximum.

### Step 4.3: Label Assignment ✅

| Label | Threshold | Count | % |
|-------|-----------|-------|---|
| normal | score < 0.15 | 127,268 | 24.8% |
| suspicious | 0.15–0.3 | 205,301 | 40.1% |
| probable_iuu | 0.3–0.5 | 26,978 | 5.3% |
| hard_iuu | ≥ 0.5 | 152,700 | 29.8% |

### Key Design Decisions

- **Dropped SAR-AIS cross-match:** SAR data only has AIS-equipped vessels — cannot detect "dark vessels" (original plan assumption was wrong)
- **Dropped AIS gap indicators:** No AIS gap data available in GFW datasets
- **Used `authorization_status` from GFW** as primary signal for Tier 1 (unauthorized foreign)
- **Tier 1 dominated by `unauthorized_foreign`** (92.3% of hard_iuu labels)
- **Every label is defensible:** hard_iuu = violations of fisheries law, probable_iuu = extreme loitering (transshipment), suspicious = unregistered vessels + encounters

### Constants Added
- `GFW_EVENTS_LABELED = "gfw_events_labeled.parquet"` in `constants.py`

---

## Phase 5: Graph Construction ✅ COMPLETE

**Script:** `src/data/pipeline/graph.py`

### ⚠️ Plan Revision: Event-Centric → Vessel-Centric

Original plan used event-level nodes (512K nodes). This would require ~244GB for the adjacency matrix — infeasible. Revised to **vessel-centric** graph: 14,857 nodes with manageable adjacency.

### Step 5.1: Vessel-Centric Graph ✅

**Nodes:** 14,857 vessels × 54 features
- **Spatial (4):** mean_lat, mean_lon, std_lat, std_lon
- **Temporal (3):** mean_hour, nighttime_ratio, weekend_ratio
- **Behavioral (31):** From vessel_behavioral_features (fishing_count, loitering_rate, encounter_rate, etc.)
- **Registry (4):** reg_length_m, reg_tonnage_gt, reg_engine_power_kw, reg_vessel_class
- **Risk (5):** max_iuu_score, unauthorized_count, encounter_count_ind, highseas_count, mpa_count
- **Context (4):** mean_sar_detections, mean_effort_hours, mean_distance_shore, in_highseas_ratio
- **Label (1):** vessel_iuu_label (0=normal, 1=suspicious, 2=probable_iuu, 3=hard_iuu)
- **Key:** mmsi (string)

**Edges:** Two types, 184,188 total across all snapshots
- **Encounter edges (46,239):** Direct transshipment evidence from encounter events
- **Co-location edges (138,049):** Vessels in same 0.1° grid cell (~11km) on same day

### Step 5.2: Temporal Snapshots ✅

**283 weekly graph snapshots:**
- Mean 469 vessels per snapshot, max 3,397
- Mean 6,531 edges per snapshot, max 30,637
- Only 1 snapshot has 0 edges
- 41 weeks skipped (< 3 vessels)

### Output Files

| File | Rows | Cols | Description |
|------|------|------|-------------|
| `vessel_node_features.parquet` | 14,857 | 55 | 54 features + mmsi |
| `encounter_edges.parquet` | 46,239 | — | Encounter edges with timestamps |
| `colocation_edges.parquet` | 138,049 | — | Co-location vessel pairs |
| `snapshot_metadata.parquet` | 283 | — | Weekly snapshot statistics |
| `graph_snapshots.pkl` | — | — | Full graph data (gitignored) |

### Vessel Label Distribution (max across events)

| Label | Count | % |
|-------|-------|---|
| normal | 2,303 | 15.5% |
| suspicious | 9,163 | 61.7% |
| probable_iuu | 2,361 | 15.9% |
| hard_iuu | 1,030 | 6.9% |

### Key Design Decisions
- **Vessel-centric NOT event-centric:** 512K nodes → 244GB adjacency (impossible)
- **No heading data:** Not available in the dataset
- **No rolling 7-day windows:** Used pre-computed behavioral features instead
- **Weather removed:** Already dropped in Phase 3
- **Co-location threshold:** 0.1° grid (~11km) same-day proximity
- **Weekly snapshots over daily:** Better graph density per snapshot

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
| No EEZ/MPA spatial join | Uses GFW's region fields instead of shapefile join | GFW regions data is reliable for Indonesia |
| `potential_risk` only 0.4% | Severe class imbalance for supervised learning | Consider anomaly detection or semi-supervised approach |
| 30 ports only | Limited nearest-port coverage for all of Indonesia | Add more ports from OSM/GFW |
| Raw weather/VIIRS data excluded | BMKG (2024 only, 20% coverage) and VIIRS (5K sample, 0.01% signal) removed in v0.7.0 | Focus on SAR + AIS as primary signals |
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
│   ├── enrich.py             # Phase 3b: Cross-source enrichment
│   ├── labels.py             # Phase 4: IUU indicator + label generation
│   └── graph.py              # Phase 5: Graph construction (vessel-centric)
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
| EEZ/MPA spatial join | GFW regions field | No usable shapefiles available at time of implementation |
| `df.apply()` for sea_zone | `np.select()` vectorized | 100x faster on 512K rows |
| Lambda for unique_grid_cells | Two-stage groupby | Original lambda was buggy |
| Steps 3.2-3.3 separate | Already done in Phase 2 | Temporal features added during cleaning |
| 124 columns (audit) | 111 columns (final) | Weather (7) + VIIRS (3) removed in v0.7.0; 3 cols removed during collision fix. Phase 4 adds 13 cols → 124 final |
| Event-level graph nodes | Vessel-level graph nodes | 512K event nodes → 244GB adjacency; vessel-level (14,857) is feasible |
| Rolling 7-day windows | Pre-computed behavioral features | Weekly snapshots with behavioral features from Phase 3 |
| Heading data in graph | Not available | Heading data not present in GFW datasets |

---

*Updated: 2026-04-22*
*Project: IUU Fishing Detection — Gemastik XIX 2026*
*Team: Toni, Nafi, Rhendy*
