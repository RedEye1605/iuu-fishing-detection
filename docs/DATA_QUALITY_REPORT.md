# Data Quality Report

**Date:** 2026-04-22
**Pipeline Version:** v0.9.0
**Scope:** All `data/processed/` parquet files including graph outputs

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Total files | 18 parquet files + 1 pickle |
| Total rows | ~4.5M across all files |
| Final dataset | 512,247 rows × 124 cols |
| Graph dataset | 14,857 vessel nodes, 184,188 edges, 283 snapshots |
| IUU labels | 4 classes (normal 24.8%, suspicious 40.1%, probable_iuu 5.3%, hard_iuu 29.8%) |
| MMSI type consistency | ✅ `large_string` everywhere |
| Coordinate validity | ✅ 100% within Indonesia bbox |
| Duplicate event_ids | ✅ 0 |
| Column collisions | ✅ 0 |
| Index leaks | ✅ 0 |
| ML readiness | ⚠️ Needs encoding (27 string + 8 list cols) |

---

## 2. Per-File Quality Metrics

### `gfw_events_full.parquet` — FINAL OUTPUT
- **Rows:** 512,247 | **Cols:** 111
- **Duplicates:** 0 event_id duplicates ✅
- **Coordinates:** 100% within Indonesia bbox (lat -11.5 to 6.5, lon 95 to 141.5) ✅
- **MMSI:** All `large_string`, 0 nulls in mmsi column ✅
- **Timestamps:** `timestamp[us, tz=UTC]`, no nulls ✅

### `gfw_events_clean.parquet`
- **Rows:** 512,247 | **Cols:** 66
- All quality checks pass (subset of full)

### `gfw_events_flat.parquet`
- **Rows:** 512,272 | **Cols:** 54
- Pre-dedup: 25 extra rows (removed in Phase 2)

### `vessel_behavioral_features.parquet`
- **Rows:** 14,857 | **Cols:** 32
- MMSI: 14,857 unique (1:1) ✅
- vessel_flag: 29.2% null (vessels with unknown flag)
- avg_fishing_duration: 85.8% null (expected — many non-fishing vessels)
- avg_port_duration: 86.9% null (expected — many vessels have no port visits)

### `vessel_registry.parquet`
- **Rows:** 147,924 | **Cols:** 12
- MMSI: `large_string` ✅
- flag_registry: 95.8% null (column exists but sparsely populated in Zenodo)
- flag_ais: 23.7% null

### `fishing_effort_clean.parquet`
- **Rows:** 885,649 | **Cols:** 18
- Coordinates valid ✅
- MMSI: `large_string` ✅

### `sar_presence_clean.parquet`
- **Rows:** 742,075 | **Cols:** 18
- Grid-only rows (no MMSI) removed in Phase 2 ✅
- Coordinates valid ✅

### `zenodo_effort_clean.parquet`
- **Rows:** 707,118 | **Cols:** 12
- Spatially filtered to Indonesia bbox ✅
- 0 nulls ✅
- No index leak ✅

### ~~`weather.parquet`~~ — REMOVED in v0.7.0
Weather enrichment removed due to insufficient temporal coverage (2024 only, 20% of events).

### ~~`viirs_detections.parquet`~~ — REMOVED in v0.7.0
VIIRS enrichment removed due to insufficient signal (5K sample rows, 0.01% match rate: 65/512K events).

### `ports.parquet`
- **Rows:** 30 | **Cols:** 3
- No issues

---

## 3. Null Analysis (gfw_events_full.parquet)

### Columns with 0% null (75 columns)
All core columns: event_id, event_type, start_time, end_time, lat, lon, mmsi, duration_hours, vessel_name, vessel_flag, vessel_type, in_highseas, potential_risk, avg_speed_knots, is_domestic, is_foreign, hour_of_day, day_of_week, month, year, is_nighttime, is_weekend, season, grid_lat, grid_lon, sea_zone, in_indonesia_bbox, implied_speed_knots, speed_outlier, total_events, tracking_span_days, fishing_count, encounter_count, loitering_count, port_visit_count, spatial_range_km, unique_grid_cells, encounters_total, loitering_events, port_visits, encounter_rate, loitering_rate, fishing_ratio, sar_total_detections, effort_hours_in_cell, sar_unique_vessels, effort_vessels_in_cell, plus all bbox, distance, and boolean columns.

### Columns with >50% null (28 columns)
These are **event-type specific** — null for event types that don't use them:

| Column | Null % | Reason |
|--------|--------|--------|
| port_name | ~90% | Only for port visits (10%) |
| port_lat/port_lon | ~90% | Only for port visits |
| port_visit_duration_hours | ~90% | Only for port visits |
| port_visit_confidence | ~90% | Only for port visits |
| port_country_flag | ~90% | Only for port visits |
| at_dock | ~90% | Only for port visits |
| next_port | ~90% | Only for port visits |
| mmsi_2 | ~91% | Only for encounters (9%) |
| vessel_name_2/vessel_type_2/vessel_flag_2 | ~91% | Only for encounters |
| encounter_type | ~91% | Only for encounters |
| encounter_median_speed_knots | ~91% | Only for encounters |
| encounter_median_distance_km | ~91% | Only for encounters |
| encounter_potential_risk | ~91% | Only for encounters |
| encounter_v2_auth_status | ~91% | Only for encounters |
| loitering_total_distance_km | ~75% | Only for loitering (25%) |
| loitering_total_hours | ~75% | Only for loitering |
| loitering_avg_speed_knots | ~75% | Only for loitering |
| loitering_avg_distance_shore_km | ~75% | Only for loitering |
| reg_vessel_class | ~50% | Registry fill rate 50.3% |
| reg_length_m/reg_engine_power_kw/reg_tonnage_gt | ~50% | Registry fill rate |
| reg_flag_ais | ~50% | Registry fill rate |
| reg_self_reported_fishing | ~50% | Registry fill rate |
| is_fishing_vessel | ~50% | Registry fill rate |
| size_category | ~50% | Registry fill rate |
| tonnage_per_length | ~50% | Registry fill rate |
| avg_fishing_duration | ~21% | Many vessels have no fishing events |
| vessel_flag (behavioral) | ~11% | Behavioral merge artifact |
| viirs_detection_nearby | varies | ~~Removed in v0.7.0~~ |

---

## 4. Cross-File Consistency

| Check | Result | Status |
|-------|--------|--------|
| MMSI type | `large_string` in all 12 files | ✅ |
| Registry → Events MMSI overlap | 1,598/14,857 (10.8% of event MMSIs) | ⚠️ |
| Behavioral → Events MMSI overlap | 14,857/14,857 (100%) | ✅ |
| Event row count (clean vs full) | Both 512,247 | ✅ |
| SAR coords within bbox | ✅ | ✅ |
| Effort coords within bbox | ✅ | ✅ |
| Zenodo coords within bbox | ✅ | ✅ |

### Registry Overlap Explanation
The 10.8% overlap (1,598 MMSIs) means only ~11% of vessels in the events data appear in the Zenodo vessel registry. This is because:
1. The Zenodo registry covers vessels that self-reported or were tracked by GFW's ML models
2. Many foreign fishing vessels in Indonesian waters are not in the registry
3. Some MMSIs may be temporary or spoofed

The **50.3% fill rate** reported in the pipeline refers to the percentage of events that get registry data after the join (since many events share MMSIs, 1,598 unique MMSIs can cover ~50% of events).

---

## 5. Class Distribution

### By Event Type
| Type | Count | % |
|------|-------|---|
| Fishing | ~287K | 56% |
| Loitering | ~128K | 25% |
| Port Visit | ~51K | 10% |
| Encounter | ~46K | 9% |

### By Flag
| Category | % |
|----------|---|
| Domestic (IDN) | 47% |
| Foreign | 53% |

### By Risk
| Category | % |
|----------|---|
| potential_risk = False | 99.6% |
| potential_risk = True | 0.4% |

**⚠️ Severe class imbalance in `potential_risk`.** This will require:
- Weighted loss functions
- SMOTE or oversampling
- Consider anomaly detection approach instead of binary classification
- Stratified sampling during train/test split

---

## 6. IUU Label Quality

### `gfw_events_labeled.parquet` — FINAL OUTPUT
- **Rows:** 512,247 | **Cols:** 124
- **New columns:** 11 `ind_*` booleans + `iuu_score` (f64) + `iuu_label` (str)

### Label Distribution

| Label | Count | % | Threshold |
|-------|-------|---|---------- |
| normal | 127,268 | 24.8% | score < 0.15 |
| suspicious | 205,301 | 40.1% | 0.15 ≤ score < 0.3 |
| probable_iuu | 26,978 | 5.3% | 0.3 ≤ score < 0.5 |
| hard_iuu | 152,700 | 29.8% | score ≥ 0.5 |

### Indicator Prevalence

| Indicator | Events | % | Tier |
|-----------|--------|---|------|
| ind_fishing_in_mpa | 287 | 0.06% | 1 |
| ind_unauthorized_foreign | 140,912 | 27.5% | 1 |
| ind_high_seas_fishing | 11,768 | 2.3% | 1 |
| ind_encounter_at_sea | 46,239 | 9.0% | 2 |
| ind_loitering_anomaly | 87,661 | 17.1% | 2 |
| ind_unregistered_vessel | 98,823 | 19.3% | 2 |
| ind_nighttime_foreign | 70,217 | 13.7% | 2 |
| ind_high_encounter_rate | 127,639 | 24.9% | 3 |
| ind_high_loitering_rate | 128,019 | 25.0% | 3 |
| ind_far_offshore | 50,684 | 9.9% | 3 |
| ind_rapid_port_cycle | 2,904 | 0.6% | 3 |

### Key Observations
- Tier 1 dominated by `unauthorized_foreign` (92.3% of hard_iuu)
- Labels are defensible: hard_iuu = fisheries law violations, probable_iuu = transshipment indicators
- Class distribution is workable for multi-class classification (no single class dominates)
- IUU score is continuous — can be used for regression or threshold tuning

---

## 7. ML Readiness Assessment

### Features Ready for ML (as-is)
- 82 columns with 0% null — directly usable after encoding
- Numeric columns: lat, lon, duration_hours, distance_*, speed_*, temporal features, grid cells
- Boolean columns: is_domestic, is_foreign, in_indonesia_bbox, is_nighttime, is_weekend, speed_outlier, etc.

### Requires Encoding Before ML

**String columns (27):** Need label encoding or one-hot encoding
- event_type, vessel_name, vessel_id, vessel_flag, vessel_type, authorization_status, auth_match_status, port_id, port_name, port_visit_confidence, port_country_flag, encounter_type, next_port, vessel_flag_2, vessel_name_2, vessel_type_2, encounter_v2_auth_status, season, reg_vessel_class, reg_flag_ais, size_category, duration_category, nearest_port_name, sea_zone

**List columns (8):** Need multi-hot encoding or feature extraction
- eez_ids, mpa_ids, rfmo, fao_zones, authorized_rfmos, plus any other list-type columns

**Boolean columns:** Convert to int (0/1)

### Recommended Preprocessing for Model Training

1. **Drop list columns** or extract count-based features (num_eez_ids, num_mpa_ids, etc.)
2. **Label encode** vessel_flag, sea_zone, season, event_type, size_category
3. **One-hot encode** low-cardinality strings (is_fishing_vessel, at_dock)
4. **Drop or impute** event-type specific columns with >75% null (port_*, encounter_*, loitering_*)
5. **Normalize/standardize** numeric features (lat, lon, distances, speeds, durations)
6. **Handle registry nulls:** Fill reg_length_m, reg_tonnage_gt with median by vessel_type, or add `has_registry` indicator
7. **Temporal split:** Train on 2020-2023, validate on 2024-H1, test on 2024-H2 to 2025
8. **Address class imbalance** for potential_risk (0.4% positive)

### Recommended Feature Set for ST-GAT

**Node features (~25 normalized):**
- Spatial: lat_norm, lon_norm, grid_lat, grid_lon
- Temporal: hour_sin, hour_cos, month_sin, month_cos, is_nighttime, is_weekend
- Vessel: is_domestic, vessel_type_encoded, reg_length_m_norm, is_fishing_vessel
- Behavioral: fishing_ratio, encounter_rate, loitering_rate, spatial_range_km_norm, unique_grid_cells_norm, avg_speed_knots_norm
- Context: sea_zone_encoded, nearest_port_dist_km_norm, in_highseas

---

## 8. Graph Data Quality

### `vessel_node_features.parquet`
- **Rows:** 14,857 | **Cols:** 55 (54 features + mmsi)
- **MMSI:** 14,857 unique, 1:1 with behavioral features ✅
- **Feature categories:** Spatial (4), Temporal (3), Behavioral (31), Registry (4), Risk (5), Context (4), Label (1)
- **Label distribution:** normal 15.5%, suspicious 61.7%, probable_iuu 15.9%, hard_iuu 6.9%
- **Registry nulls:** ~50% (consistent with Phase 3 fill rate) ⚠️

### `encounter_edges.parquet`
- **Edges:** 46,239 (direct transshipment evidence)
- **All MMSI pairs present in node features** ✅

### `colocation_edges.parquet`
- **Edges:** 138,049 unique vessel pairs
- **Grid:** 0.1° (~11km) same-day proximity
- **All MMSI pairs present in node features** ✅

### `snapshot_metadata.parquet`
- **Snapshots:** 283 weekly graphs
- **Mean vessels/snapshot:** 469, max 3,397
- **Mean edges/snapshot:** 6,531, max 30,637
- **Empty snapshots:** 1 (0 edges), 41 weeks skipped (< 3 vessels)

### `graph_snapshots.pkl`
- Full temporal graph data for ST-GAT training
- Gitignored (reconstructible via pipeline)

## 9. Known Issues & Mitigations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Registry 50% fill | Missing vessel specs | Add `has_registry` flag; impute by vessel_type median |
| Raw weather/VIIRS excluded | BMKG (2024 only) and VIIRS (5K sample) removed in v0.7.0 | Focus on SAR + AIS as primary signals |
| potential_risk 0.4% | Class imbalance | Weighted loss, SMOTE, or anomaly detection |
| 30 ports | Limited coverage | Major ports covered; sufficient for nearest-port feature |
| No EEZ shapefile join | Less precise EEZ assignment | GFW regions data is reliable |
| Event-type specific nulls | Sparse feature matrix | Drop or separate models per event type |

---

## 10. Data Lineage

```
Raw Data → Phase 1 (Load) → Phase 2 (Clean) → Phase 3 (Features) → Final
~2.6M rows    14 flat files     8 clean files     1 enriched file    1 master file
                                                    1 behavioral file
```

All steps are deterministic and reproducible via `python scripts/run_pipeline.py`.

---

*Report generated: 2026-04-22*
*Pipeline version: v0.8.0*
