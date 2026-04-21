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

### `gfw_events_full.parquet` (512,247 rows × 111 cols)
The master enriched events table used for modeling.

**Core (12):** `event_id` (str), `event_type` (str), `start_time` (ts UTC), `end_time` (ts UTC), `lat` (f64), `lon` (f64), `bbox_minlon` (f64), `bbox_minlat` (f64), `bbox_maxlon` (f64), `bbox_maxlat` (f64), `mmsi` (str), `duration_hours` (f64)

**Vessel (4):** `vessel_name` (str), `vessel_id` (str), `vessel_flag` (str), `vessel_type` (str)

**Regions (5):** `eez_ids` (list), `mpa_ids` (list), `rfmo` (list), `fao_zones` (list), `in_highseas` (bool)

**Distances (4):** `distance_shore_start_km` (i64), `distance_shore_end_km` (i64), `distance_port_start_km` (f64), `distance_port_end_km` (f64)

**Authorization (5):** `authorization_status` (str), `authorized_rfmos` (list), `potential_risk` (bool), `auth_match_status` (str), `encounter_v2_auth_status` (str)

**Movement (3):** `total_distance_km` (f64), `avg_speed_knots` (f64), `implied_speed_knots` (f64)

**Port visit specific (6):** `port_id` (str), `port_name` (str), `port_lat` (f64), `port_lon` (f64), `port_visit_duration_hours` (f64), `port_visit_confidence` (str), `port_country_flag` (str), `at_dock` (bool), `next_port` (str)

**Encounter specific (6):** `mmsi_2` (str), `vessel_name_2` (str), `vessel_type_2` (str), `vessel_flag_2` (str), `encounter_type` (str), `encounter_median_speed_knots` (f64), `encounter_median_distance_km` (f64), `encounter_potential_risk` (bool)

**Loitering specific (3):** `loitering_total_distance_km` (f64), `loitering_total_hours` (f64), `loitering_avg_speed_knots` (f64), `loitering_avg_distance_shore_km` (f64)

**MPA (1):** `in_mpa_notake` (bool)

**Speed flags (1):** `speed_outlier` (bool)

**Temporal (8):** `in_indonesia_bbox` (bool), `hour_of_day` (i32), `day_of_week` (i32), `month` (i32), `year` (i32), `is_nighttime` (bool), `is_weekend` (bool), `season` (str)

**Domestic (2):** `is_domestic` (bool), `is_foreign` (bool)

**Registry (9):** `reg_vessel_class` (str), `reg_length_m` (f64), `reg_engine_power_kw` (f64), `reg_tonnage_gt` (f64), `reg_self_reported_fishing` (bool), `reg_flag_ais` (str), `is_fishing_vessel` (bool), `size_category` (str), `tonnage_per_length` (f64)

**Temporal derived (2):** `duration_category` (str)

**Spatial (5):** `grid_lat` (f64), `grid_lon` (f64), `nearest_port_name` (str), `nearest_port_dist_km` (f64), `sea_zone` (str)

**SAR/Effort (4):** `sar_total_detections` (f64), `sar_unique_vessels` (i64), `effort_hours_in_cell` (f64), `effort_vessels_in_cell` (i64)

**Behavioral (22):** `total_events` (i64), `first_seen` (ts UTC), `last_seen` (ts UTC), `tracking_span_days` (f64), `fishing_count` (i64), `encounter_count` (i64), `loitering_count` (i64), `port_visit_count` (i64), `avg_fishing_duration` (f64), `total_fishing_hours` (f64), `avg_fishing_distance` (f64), `fishing_lat_mean` (f64), `fishing_lon_mean` (f64), `avg_distance_shore` (f64), `max_distance_shore` (i64), `spatial_range_km` (f64), `unique_grid_cells` (i64), `speed_std` (f64), `encounters_total` (i64), `encounters_with_foreign` (i64), `loitering_events` (i64), `total_loitering_hours` (f64), `port_visits` (i64), `avg_port_duration` (f64), `encounter_rate` (f64), `loitering_rate` (f64), `fishing_ratio` (f64), `avg_fishing_hours_per_trip` (f64)

---

## Intermediate Files

### `gfw_events_flat.parquet` (512,272 rows × 54 cols)
Raw flattened GFW events before cleaning. Same core schema as above but without Phase 2/3 derived columns.

### `gfw_events_clean.parquet` (512,247 rows × 66 cols)
After dedup + cleaning. Adds temporal features, flag standardization, speed flags, domestic/foreign flags.

### `vessel_behavioral_features.parquet` (14,857 rows × 32 cols)
Per-vessel aggregated features. Key: `mmsi` (string, unique).

`mmsi` (str), `total_events` (i64), `first_seen` (ts UTC), `last_seen` (ts UTC), `vessel_flag` (str), `is_domestic` (bool), `tracking_span_days` (f64), `fishing_count` (i64), `encounter_count` (i64), `loitering_count` (i64), `port_visit_count` (i64), `avg_fishing_duration` (f64), `total_fishing_hours` (f64), `avg_fishing_distance` (f64), `fishing_lat_mean` (f64), `fishing_lon_mean` (f64), `avg_distance_shore` (f64), `max_distance_shore` (i64), `spatial_range_km` (f64), `unique_grid_cells` (i64), `avg_speed_knots` (f64), `speed_std` (f64), `encounters_total` (i64), `encounters_with_foreign` (i64), `loitering_events` (i64), `total_loitering_hours` (f64), `port_visits` (i64), `avg_port_duration` (f64), `encounter_rate` (f64), `loitering_rate` (f64), `fishing_ratio` (f64), `avg_fishing_hours_per_trip` (f64)

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

### `fishing_effort_flat.parquet` (890,411 rows × 13 cols)
Pre-clean. `mmsi` (str), `date` (str), `lat` (f64), `lon` (f64), `fishing_hours` (f64), `flag` (str), `geartype` (str), `vessel_type` (str), `vessel_id` (str), `vessel_name` (str), `callsign` (str), `entry_timestamp` (str), `exit_timestamp` (str)

### `sar_presence_flat.parquet` (1,242,915 rows × 13 cols)
Pre-clean. Same as fishing_effort_flat with `detections` (i64) instead of `fishing_hours`.

### `zenodo_effort_flat.parquet` (707,118 rows × 10 cols)
Pre-clean. `date` (str), `year` (i64), `month` (i64), `cell_ll_lat` (f64), `cell_ll_lon` (f64), `flag` (str), `geartype` (str), `hours` (f64), `fishing_hours` (f64), `mmsi_present` (i64)
