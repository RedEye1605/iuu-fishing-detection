# Pipeline Schema Reference

All output files are in `data/processed/`.

## Final Output

### `gfw_events_full.parquet` (512,247 rows × 105+ cols)
The master enriched events table used for modeling.

**Core columns:** `event_id`, `event_type`, `mmsi`, `start_time`, `end_time`, `lat`, `lon`, `duration_hours`

**Vessel:** `vessel_flag`, `vessel_name`, `vessel_type`, `is_domestic`, `is_foreign`

**Registry joins:** `reg_vessel_class`, `reg_length_m`, `reg_engine_power_kw`, `reg_tonnage_gt`, `reg_flag_ais`, `is_fishing_vessel`, `size_category`, `tonnage_per_length`

**Temporal:** `hour_of_day`, `day_of_week`, `month`, `year`, `is_nighttime`, `is_weekend`, `season`, `duration_category`

**Spatial:** `grid_lat`, `grid_lon`, `sea_zone`, `nearest_port_name`, `nearest_port_dist_km`, `in_indonesia_bbox`

**Behavioral (from vessel_behavioral_features):** `total_events`, `fishing_count`, `encounter_count`, `loitering_count`, `port_visit_count`, `encounter_rate`, `loitering_rate`, `fishing_ratio`, `avg_speed_knots`, `speed_std`, `unique_grid_cells`, `spatial_range_km`, etc.

**Cross-source:** `weather_*`, `viirs_count`, `viirs_detection_nearby`, `viirs_avg_radiance`, `sar_total_detections`, `sar_unique_vessels`, `effort_hours_in_cell`, `effort_vessels_in_cell`

## Intermediate Files

### `vessel_behavioral_features.parquet` (14,857 rows × 32 cols)
Per-vessel aggregated features. Key: `mmsi` (string).

Columns: `mmsi`, `total_events`, `first_seen`, `last_seen`, `vessel_flag`, `is_domestic`, `tracking_span_days`, `fishing_count`, `encounter_count`, `loitering_count`, `port_visit_count`, `avg_fishing_duration`, `total_fishing_hours`, `avg_fishing_distance`, `fishing_lat_mean`, `fishing_lon_mean`, `avg_distance_shore`, `max_distance_shore`, `spatial_range_km`, `unique_grid_cells`, `avg_speed_knots`, `speed_std`, `encounters_total`, `encounters_with_foreign`, `loitering_events`, `total_loitering_hours`, `port_visits`, `avg_port_duration`, `encounter_rate`, `loitering_rate`, `fishing_ratio`, `avg_fishing_hours_per_trip`

### `vessel_registry.parquet` (147,924 rows × 12 cols)
Zenodo vessel registry filtered to relevant flags. Key: `mmsi` (string).

Columns: `mmsi` (str), `year`, `flag_ais`, `flag_registry`, `flag_gfw`, `vessel_class`, `length_m`, `engine_power_kw`, `tonnage_gt`, `self_reported_fishing_vessel`, `active_hours`, `fishing_hours`

### `fishing_effort_clean.parquet` (885,649 rows × 18 cols)
Columns: `mmsi`, `date`, `lat`, `lon`, `fishing_hours`, `flag`, `geartype`, `vessel_type`, `vessel_id`, `vessel_name`, `callsign`, `entry_timestamp`, `exit_timestamp`, `is_domestic`, `date_parsed`, `year`, `month`, `season`

### `sar_presence_clean.parquet` (742,075 rows × 18 cols)
Same schema as fishing_effort_clean, with `detections` instead of `fishing_hours`.

### `zenodo_effort_clean.parquet` (613,325 rows × 12 cols)
Columns: `date`, `cell_ll_lat`, `cell_ll_lon`, `flag`, `geartype`, `hours`, `fishing_hours`, `mmsi_present`, `year`, `month`, `is_domestic`, `season`

### `weather.parquet` (2,920 rows × 9 cols)
Columns: `date`, `zone`, `wave_height_m`, `wind_speed_knots`, `wind_direction_deg`, `sea_surface_temp_c`, `visibility_km`, `weather_condition`, `weather_risk`

### `viirs_detections.parquet` (5,000 rows × 8 cols)
Columns: `id`, `lat`, `lon`, `date_gmt` (int64), `time_gmt`, `radiance`, `confidence`, `vessel_type`

### `ports.parquet` (30 rows × 3 cols)
Columns: `name`, `lat`, `lon`

## Type Conventions
- **MMSI**: Always `string` (not int64) across all files
- **Timestamps**: `datetime64[ns, UTC]` or string
- **Coordinates**: `float64`
- **Flags**: ISO 3166 alpha-3 uppercase (`IDN`, `CHN`, etc.)
