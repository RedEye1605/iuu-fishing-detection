# Pipeline Schema Reference

All output files are in `data/processed/`. Schemas verified from actual parquet files on 2026-04-22.

## Type Conventions
- **MMSI**: Always `large_string` (not int64) across all files
- **Timestamps**: `timestamp[us, tz=UTC]` for events, `timestamp[us]` for clean files
- **Coordinates**: `double`
- **Flags**: ISO 3166 alpha-3 uppercase (`IDN`, `CHN`, etc.)
- **Lists**: `list<element: string>` (e.g., eez_ids, mpa_ids)

---

## Final Output

### `gfw_events_labeled.parquet` (~512K rows × 130 cols) ← FINAL
The master labeled events table used for ML training.

All columns from `gfw_events_full.parquet` plus:

**IUU Indicators (12 booleans):**
- Tier 1: `ind_fishing_in_mpa`, `ind_unauthorized_foreign`, `ind_high_seas_fishing`, `ind_foreign_no_auth_data`
- Tier 2: `ind_encounter_at_sea`, `ind_loitering_anomaly`, `ind_unregistered_vessel`, `ind_nighttime_foreign`, `ind_foc_vessel`, `ind_ais_gap_proxy`
- Tier 3: `ind_high_encounter_rate`, `ind_high_loitering_rate`, `ind_far_offshore`, `ind_rapid_port_cycle`

**IUU Score & Label (2):** `iuu_score` (f64, range [0, 1]), `iuu_label` (str: normal|suspicious|probable_iuu|hard_iuu)

**FoC & Cyclical (5):** `is_foc_flag` (bool), `hour_sin` (f32), `hour_cos` (f32), `month_sin` (f32), `month_cos` (f32)

---

### `gfw_events_full.parquet` (~512K rows × 111 cols)
The master enriched events table used for modeling.

**Core (12):** `event_id` (str), `event_type` (str), `start_time` (ts UTC), `end_time` (ts UTC), `lat` (f64), `lon` (f64), `bbox_minlon` (f64), `bbox_minlat` (f64), `bbox_maxlon` (f64), `bbox_maxlat` (f64), `mmsi` (str), `duration_hours` (f64)

**Vessel (4):** `vessel_name` (str), `vessel_id` (str), `vessel_flag` (str), `vessel_type` (str)

**Regions (5):** `eez_ids` (list), `mpa_ids` (list), `rfmo` (list), `fao_zones` (list), `in_highseas` (bool)

**Distances (4):** `distance_shore_start_km` (i64), `distance_shore_end_km` (i64), `distance_port_start_km` (f64), `distance_port_end_km` (f64)

**Authorization (5):** `authorization_status` (str), `authorized_rfmos` (list), `potential_risk` (bool), `auth_match_status` (str), `encounter_v2_auth_status` (str)

**Movement (3):** `total_distance_km` (f64), `avg_speed_knots` (f64), `implied_speed_knots` (f64)

**Port visit specific (9):** `port_id` (str), `port_name` (str), `port_lat` (f64), `port_lon` (f64), `port_visit_duration_hours` (f64), `port_visit_confidence` (str), `port_country_flag` (str), `at_dock` (bool), `next_port` (str)

**Encounter specific (8):** `mmsi_2` (str), `vessel_name_2` (str), `vessel_type_2` (str), `vessel_flag_2` (str), `encounter_type` (str), `encounter_median_speed_knots` (f64), `encounter_median_distance_km` (f64), `encounter_potential_risk` (bool)

**Loitering specific (4):** `loitering_total_distance_km` (f64), `loitering_total_hours` (f64), `loitering_avg_speed_knots` (f64), `loitering_avg_distance_shore_km` (f64)

**MPA (1):** `in_mpa_notake` (bool)

**Speed flags (1):** `speed_outlier` (bool)

**Temporal (8):** `in_indonesia_bbox` (bool), `hour_of_day` (i32), `day_of_week` (i32), `month` (i32), `year` (i32), `is_nighttime` (bool), `is_weekend` (bool), `season` (str)

**Domestic (2):** `is_domestic` (bool), `is_foreign` (bool)

**Registry (9):** `reg_vessel_class` (str), `reg_length_m` (f64), `reg_engine_power_kw` (f64), `reg_tonnage_gt` (f64), `reg_self_reported_fishing` (bool), `reg_flag_ais` (str), `is_fishing_vessel` (bool), `size_category` (str), `tonnage_per_length` (f64)

**FoC (1):** `is_foc_flag` (bool) — ITF-listed Flag-of-Convenience indicator

**Temporal derived (2):** `duration_category` (str)

**Cyclical encoding (4):** `hour_sin` (f32), `hour_cos` (f32), `month_sin` (f32), `month_cos` (f32)

**Spatial (5):** `grid_lat` (f64), `grid_lon` (f64), `nearest_port_name` (str), `nearest_port_dist_km` (f64), `sea_zone` (str)

**SAR/Effort (4):** `sar_total_detections` (f64), `sar_unique_vessels` (i64), `effort_hours_in_cell` (f64), `effort_vessels_in_cell` (i64)

**Behavioral (25):** `total_events` (i64), `first_seen` (ts UTC), `last_seen` (ts UTC), `tracking_span_days` (f64), `fishing_count` (i64), `encounter_count` (i64), `loitering_count` (i64), `port_visit_count` (i64), `avg_fishing_duration` (f64), `total_fishing_hours` (f64), `avg_fishing_distance` (f64), `fishing_lat_mean` (f64), `fishing_lon_mean` (f64), `avg_distance_shore` (f64), `max_distance_shore` (i64), `spatial_range_km` (f64), `unique_grid_cells` (i64), `avg_speed_knots` (f64), `speed_std` (f64), `encounters_with_foreign` (i64), `total_loitering_hours` (f64), `avg_port_duration` (f64), `encounter_rate` (f64), `loitering_rate` (f64), `fishing_ratio` (f64)

---

## Intermediate Files

### `gfw_events_flat.parquet` (~512K rows × 54 cols)
Raw flattened GFW events before cleaning. Same core schema as above but without Phase 2/3 derived columns.

### `gfw_events_clean.parquet` (~512K rows × 66 cols)
After dedup + cleaning. Adds temporal features, cyclical encoding, flag standardization, FoC indicator, speed flags, domestic/foreign flags.

### `vessel_behavioral_features.parquet` (~14.8K rows × 28 cols)
Per-vessel aggregated features (training period only). Key: `mmsi` (string, unique).

`mmsi` (str), `total_events` (i64), `first_seen` (ts UTC), `last_seen` (ts UTC), `vessel_flag` (str), `is_domestic` (bool), `tracking_span_days` (f64), `fishing_count` (i64), `encounter_count` (i64), `loitering_count` (i64), `port_visit_count` (i64), `avg_fishing_duration` (f64), `total_fishing_hours` (f64), `avg_fishing_distance` (f64), `fishing_lat_mean` (f64), `fishing_lon_mean` (f64), `avg_distance_shore` (f64), `max_distance_shore` (i64), `spatial_range_km` (f64), `unique_grid_cells` (i64), `avg_speed_knots` (f64), `speed_std` (f64), `encounters_with_foreign` (i64), `total_loitering_hours` (f64), `avg_port_duration` (f64), `encounter_rate` (f64), `loitering_rate` (f64), `fishing_ratio` (f64)

### `vessel_registry.parquet` (147,924 rows × 12 cols)
Zenodo vessel registry. Key: `mmsi` (string).

`mmsi` (str), `year` (i64), `flag_ais` (str), `flag_registry` (str), `flag_gfw` (str), `vessel_class` (str), `length_m` (f64), `engine_power_kw` (f64), `tonnage_gt` (f64), `self_reported_fishing_vessel` (bool), `active_hours` (f64), `fishing_hours` (f64)

### `fishing_effort_clean.parquet` (885,649 rows × 18 cols)
`mmsi` (str), `date` (str), `lat` (f64), `lon` (f64), `fishing_hours` (f64), `flag` (str), `geartype` (str), `vessel_type` (str), `vessel_id` (str), `vessel_name` (str), `callsign` (str), `entry_timestamp` (str), `exit_timestamp` (str), `is_domestic` (bool), `date_parsed` (ts), `year` (i32), `month` (i32), `season` (str)

### `sar_presence_clean.parquet` (742,075 rows × 18 cols)
Same schema as fishing_effort_clean, with `detections` (i64) instead of `fishing_hours` (f64).

### `zenodo_effort_clean.parquet` (707,118 rows × 12 cols)
`date` (str), `year` (i64), `month` (i64), `cell_ll_lat` (f64), `cell_ll_lon` (f64), `flag` (str), `geartype` (str), `hours` (f64), `fishing_hours` (f64), `mmsi_present` (i64), `is_domestic` (bool), `season` (str)

### `ports.parquet` (30 rows × 3 cols)
`name` (str), `lat` (f64), `lon` (f64)

---

## Graph Output Files (Phase 5)

### `vessel_node_features.parquet` (~14.8K rows × 42 cols)
Per-vessel feature matrix for graph neural network. Features are **RobustScaler**-normalized (fit on training vessels only). Key: `mmsi` (string, unique).

**Spatial (4):** `mean_lat`, `mean_lon`, `std_lat`, `std_lon`

**Temporal (3):** `mean_hour`, `nighttime_ratio`, `weekend_ratio`

**Behavioral (17):** fishing_count, encounter_count, loitering_count, port_visit_count, avg_fishing_duration, total_fishing_hours, avg_distance_shore, spatial_range_km, unique_grid_cells, avg_speed_knots, speed_std, total_loitering_hours, avg_port_duration, encounter_rate, loitering_rate, fishing_ratio, total_events

**Identity (5):** `vessel_flag`, `is_domestic`, `tracking_span_days`, `first_seen`, `last_seen`

**Registry (4):** `reg_length_m`, `reg_tonnage_gt`, `reg_engine_power_kw`, `reg_vessel_class`

**Registry indicator (1):** `has_registry`

**Risk proxies (3):** `unauthorized_count`, `highseas_count`, `mpa_count`

**Context (3):** `mean_sar_detections` (all data), `mean_effort_hours` (all data), `in_highseas_ratio` (training period only)

**Label (1):** `vessel_iuu_label` (0=normal, 1=suspicious, 2=probable_iuu, 3=hard_iuu) — NOT normalized

**Data quality indicators (4):** `has_behavioral_data`, `has_fishing_data`, `has_port_data`, `is_foc_flag`

**Key (1):** `mmsi`

Total: 42 columns (35 numeric features normalized + 1 label + 2 key/identity + 4 binary indicators)

### `feature_scaler.pkl`
Pickled dict with `scaler` (RobustScaler) and `columns` (list of normalized column names). Use for inference-time normalization.

### `encounter_edges.parquet` (~46K rows)
Direct vessel-to-vessel encounter edges with attributes.

`mmsi_1` (str), `mmsi_2` (str), `timestamp` (ts UTC), `edge_type` (str), `edge_duration_hours` (f64), `edge_distance_km` (f64)

### `colocation_edges.parquet` (~478K rows)
Distance-filtered co-location edges (within 5km in same grid cell, max 15 vessels/cell).

`mmsi_1` (str), `mmsi_2` (str), `event_date` (date), `edge_type` (str: "colocation"), `edge_distance_km` (f64)

### `snapshot_metadata.parquet` (274 rows)
Weekly graph snapshot statistics (gap weeks excluded).

`week` (str), `n_vessels` (int), `n_edges` (int), `n_encounter` (int), `n_colocation` (int)

### `graph_snapshots.pkl`
Full serialized graph data including edge attributes (duration, distance). Gitignored — reconstructible via `python scripts/run_pipeline.py --step graph`.

Each snapshot dict contains:
- `vessel_indices`, `src`, `dst`, `labels`, `n_vessels`, `n_edges`
- `edge_types`: list of "encounter" / "colocation"
- `edge_durations`: list of float (hours, 0 for co-location)
- `edge_distances`: list of float (km)

---

## Phase 6: Temporal Split (`split.py`)

### `split/snapshot_split.json`
Mapping of weekly snapshot identifiers to train/val/test sets.

```json
{
  "train": ["2020_W01", ..., "2023_W50"],   // 208 snapshots
  "val":   ["2024_W01", ..., "2024_W24"],   // 24 snapshots
  "test":  ["2024_W27", ..., "2025_W16"]    // 42 snapshots
}
```

**2-week gaps excluded** (2023-W51 to 2023-W52, 2024-W25 to 2024-W26).

### `split/split_stats.json`
Per-split distribution statistics (events, vessels, edges, label/flag/event_type distributions).

### `split/{split}/snapshot_data.pkl`
Per-split snapshot data with int64 numpy arrays:
- `vessel_indices` — vessel node indices for each snapshot
- `src`, `dst` — edge source/destination indices
- `labels` — IUU label (0=normal, 1=suspicious, 2=probable_iuu, 3=hard_iuu)
- `n_vessels`, `n_edges`, `edge_types` — metadata

---

## Model Output Files (Phase 7)

All files in `data/processed/model/`. Direct consumption by PyG model.

### `node_features.npy`
(N, 40) float32 numpy array. All-numeric continuous node feature matrix.

**NO NaN, NO Inf, RobustScaler-normalized (median≈0, IQR≈1)**

### `node_labels.npy`
(N,) int64 numpy array. Vessel-level IUU labels (0=normal, 1=suspicious, 2=probable_iuu, 3=hard_iuu).

### `class_weights.npy`
(4,) float32 array. Inverse-frequency weights computed from snapshot-level training distribution.

### `vessel_flag_embed.npy`
(127, 8) float32 array. Xavier uniform initialization for flag embedding lookup.

### `vessel_class_embed.npy`
(17, 8) float32 array. Xavier uniform initialization for class embedding lookup.

### `feature_names.json`
Ordered list of continuous feature names.

### `encoders.pkl`
LabelEncoder objects + frequency maps for flag and class.

### `mmsi_index.json`
MMSI → global node index mapping.

### `vessel_flag_indices.npy`
(N,) int64 array. Flag embedding indices (separate from continuous features).

### `vessel_class_indices.npy`
(N,) int64 array. Class embedding indices (separate from continuous features).

### `snapshots/{split}_snapshots.pkl`
Consolidated snapshot data per split:
- `order`: ordered list of snapshot week IDs
- `data`: dict of week → snapshot tensors

Each snapshot contains:
- `vessel_indices` (V,) int64 — global node indices
- `edge_index` (2, E) int64 — source/destination
- `edge_type` (E,) int64 — 0=encounter, 1=colocation
- `edge_attr` (E, 2) float32 — [duration_hours, distance_km]
- `labels` (V,) int64 — vessel IUU labels

Model config: continuous_dim=40, num_flags=127, num_vessel_classes=17, embed_dim=8, hidden_dim=64, num_heads=4, num_edge_types=2, num_classes=4
