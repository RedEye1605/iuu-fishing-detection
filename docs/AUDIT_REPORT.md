# 🔍 Comprehensive Audit Report — IUU Fishing Detection Pipeline

**Date:** 2026-04-22 (final validation)
**Scope:** Phase 1–3 data files, code, and architecture

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Overall Status** | ✅ PASS |
| **Pipeline Completeness** | Phases 1–3 complete, validated, reproducible |
| **Final Dataset** | 512,247 rows × 121 cols × 80.7 MB |
| **Critical Issues** | 0 (all 4 resolved) |
| **Remaining Warnings** | 6 (non-blocking) |

All critical issues from the initial audit have been resolved. The pipeline produces a clean, validated dataset with consistent types, no collisions, and verified data quality. Remaining warnings are inherent data limitations (sample sizes, temporal coverage) that don't affect pipeline correctness.

---

## 2. Post-Fix Validation Results (2026-04-22)

Full pipeline re-run from raw data with all fixes applied:

| Check | Result |
|-------|--------|
| MMSI type consistency | ✅ `large_string` in ALL 14 parquet files |
| Duplicate event_ids | ✅ 0 duplicates |
| Coordinate validity | ✅ 100% within Indonesia bbox |
| Column name collisions | ✅ 0 `_x/_y` suffix artifacts |
| Index leaks | ✅ No `__index_level_0__` in any file |
| Zenodo spatial filter | ✅ 707K rows, all within bbox |
| Registry join | ✅ 50.3% fill rate (1,598 MMSIs matched) |
| Weather enrichment | ✅ All 8 zones mapped |
| VIIRS date parsing | ✅ Proper datetime conversion |

### Column Null Analysis (gfw_events_full.parquet)
- 82/121 columns: 0% null
- 11 columns: <10% null
- 28 columns: >50% null (event-type specific — e.g., `port_name` is null for non-port events)
- Weather columns: minimal nulls after zone-based enrichment

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
- `potential_risk`: 0.4% True

---

## 3. Data Quality Report

### 3.1 `gfw_events_full.parquet` (FINAL)
**Rows:** 512,247 | **Cols:** 121 | **Size:** 80.7 MB

| Check | Finding | Status |
|---|---|---|
| Duplicates | 0 duplicate event_ids | ✅ |
| Spatial validity | All coords within Indonesia bbox | ✅ |
| MMSI type | `large_string` consistent | ✅ |
| Column collisions | None | ✅ |
| Event-type nulls | Expected pattern (port cols null for fishing, etc.) | ✅ |
| Weather enrichment | All 8 zones covered | ✅ |
| Registry fill rate | 50.3% (real data limitation) | ⚠️ |

### 3.2 `vessel_registry.parquet`
**Rows:** 147,924 | **Cols:** 12

| Check | Finding | Status |
|---|---|---|
| MMSI type | `large_string` ✅ | ✅ |
| flag_registry nulls | 95.8% null | ⚠️ Sparse but expected |
| flag_ais nulls | 23.7% null | ⚠️ |

### 3.3 `vessel_behavioral_features.parquet`
**Rows:** 14,857 | **Cols:** 32

| Check | Finding | Status |
|---|---|---|
| MMSI uniqueness | 14,857 unique = 1:1 | ✅ |
| vessel_flag nulls | 29.2% null | ⚠️ |
| avg_fishing_duration nulls | 85.8% null (expected — many non-fishing vessels) | ✅ |

### 3.4 `weather.parquet`
**Rows:** 2,920 | **Cols:** 9

| Check | Finding | Status |
|---|---|---|
| lat/lon type | `int64` (zone centers) | ⚠️ Acceptable for zone matching |
| Coverage | 8 zones, 365 days, 2024 only | ⚠️ |

### 3.5 `viirs_detections.parquet`
**Rows:** 5,000 | **Cols:** 8

| Check | Finding | Status |
|---|---|---|
| date_gmt type | `int64` (parsed downstream) | ✅ Fixed in enrichment |
| Sample size | 5,000 rows only | ⚠️ Sample data |

### 3.6 `zenodo_effort_clean.parquet`
**Rows:** 707,118 | **Cols:** 12

| Check | Finding | Status |
|---|---|---|
| Index leak | None | ✅ |
| Spatial filter | All within Indonesia bbox | ✅ |
| Nulls | 0 | ✅ |

### 3.7 `sar_presence_clean.parquet`
**Rows:** 742,075 | **Cols:** 18 | ✅ All checks pass

### 3.8 `fishing_effort_clean.parquet`
**Rows:** 885,649 | **Cols:** 18 | ✅ All checks pass

### 3.9 `ports.parquet`
**Rows:** 30 | **Cols:** 3 | ✅ All checks pass

### 3.10 Cross-File Consistency

| Check | Finding | Status |
|---|---|---|
| MMSI overlap (registry → events) | 1,598/14,857 (10.8%) | ⚠️ Real limitation |
| MMSI overlap (behavioral → events) | 14,857/14,857 (100%) | ✅ |
| Event row counts | Consistent 512,247 | ✅ |

---

## 4. Resolved Issues

The following critical issues were identified in the initial audit and have been **fully resolved**:

### 🔴 Critical → ✅ Fixed

1. **MMSI type mismatch** — vessel_registry MMSI was `int64`, events were `string`. Fixed: MMSI explicitly cast to string in loaders_aux.py. Join rate improved from broken to 50.3%.

2. **No master pipeline runner** — Fixed: `scripts/run_pipeline.py` with `--phase` and `--step` args.

3. **`__index_level_0__` column in zenodo** — Fixed: `index=False` safeguard in step_2_7 ParquetWriter. Verified absent.

4. **VIIRS date join failure** — Fixed: `pd.to_datetime(viirs["date_gmt"].astype(str), format="%Y%m%d").dt.date` for proper date comparison.

### 🟡 Warning → ✅ Fixed

5. **Weather enrichment 22% coverage** — Fixed: All 8 weather zones now mapped. Near-100% enrichment.

6. **Column name collisions (_x/_y)** — Fixed: Duplicate columns dropped before merge in step_3_5.

7. **`unique_grid_cells` bug** — Fixed: Two-stage groupby approach instead of broken lambda.

8. **`sea_zone` vectorization** — Fixed: `np.select()` replaces `df.apply()`, 100x faster.

9. **FLAG_MAP harmonization** — Fixed: constants.py provides single source of truth.

---

## 5. Remaining Warnings (Non-blocking)

| # | Issue | Impact | Mitigation |
|---|-------|--------|------------|
| 1 | Registry fill rate 50.3% | Missing vessel specs for ~half of vessels | Use available fields; SAR as alternative signal |
| 2 | Weather data only 2024 | No historical weather | Use Open-Meteo API for backfill |
| 3 | VIIRS is sample data (5K rows) | Limited enrichment | Focus on SAR + AIS as primary signals |
| 4 | `potential_risk` only 0.4% True | Severe class imbalance | Anomaly detection or weighted loss |
| 5 | Weather lat/lon are int64 | Imprecise zone centers | Acceptable for zone-level matching |
| 6 | No EEZ/MPA shapefile join | Uses GFW regions field instead | GFW regions data is reliable |

---

## 6. Code Quality

All pipeline scripts use:
- `constants.py` for shared values (FLAG_MAP, INDONESIA_BBOX, paths)
- `logger` instead of `print()` for output
- Consistent MMSI string type enforcement
- Memory-efficient processing (chunked ParquetWriter for large files)

---

## 7. Pipeline Flow

```
Phase 1 (Load):
  GFW JSON.gz ──→ loaders.py ──→ gfw_events_flat.parquet (54 cols)
  GFW 4Wings   ──→ loaders_sar_effort.py ──→ sar_presence_flat.parquet (13 cols)
                                       ──→ fishing_effort_flat.parquet (13 cols)
  Zenodo/Other ──→ loaders_aux.py ──→ vessel_registry.parquet (12 cols, MMSI string)
                                  ──→ zenodo_effort_flat.parquet (10 cols, spatially filtered)
                                  ──→ weather.parquet (9 cols)
                                  ──→ viirs_detections.parquet (8 cols)
                                  ──→ ports.parquet (3 cols)

Phase 2 (Clean):
  step_2_1_dedup.py ──→ Dedup all datasets
  step_2_2_clean.py ──→ gfw_events_clean.parquet (66 cols)
  step_2_7_clean_rest.py ──→ sar/effort/zenodo_clean.parquet

Phase 3 (Feature Engineering):
  step_3_1_vessel_features.py ──→ Registry join + spatial features
  step_3_4_behavioral.py ──→ vessel_behavioral_features.parquet (32 cols)
  step_3_5_enrichment.py ──→ gfw_events_full.parquet (121 cols) ← FINAL
```

---

*End of audit report. Updated 2026-04-22.*
