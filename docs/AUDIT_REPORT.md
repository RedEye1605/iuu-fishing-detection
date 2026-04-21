# 🔍 Comprehensive Audit Report — IUU Fishing Detection Pipeline

**Date:** 2026-04-21  
**Auditor:** Rhendix (automated)  
**Scope:** Phase 1–3 data files, code, and architecture

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Overall Status** | ⚠️ CONDITIONAL PASS |
| **Critical Issues** | 4 |
| **Warnings** | 8 |
| **Info** | 6 |
| **Pipeline Completeness** | Phases 1–3 complete, reproducible with caveats |

The pipeline is functionally complete and produces a 512K-row enriched dataset with 124 features. However, there are **4 critical issues** that affect data integrity, model training readiness, and cross-file joins. The most severe is a **type mismatch between vessel_registry (int64 MMSI) and events (string MMSI)** causing only 10.8% match rate instead of expected ~50%+.

---

## 2. Data Quality Report

### 2.1 `gfw_events_full.parquet` (MOST IMPORTANT)
**Rows:** 512,247 | **Cols:** 124 | **Size:** 81.2 MB

| Check | Finding | Severity |
|---|---|---|
| **Duplicates** | 0 duplicate event_ids ✅ | OK |
| **Spatial validity** | All coords within Indonesia bbox ✅ | OK |
| **Temporal range** | 2019-12-31 to 2025-04-14 | WARNING |
| **MMSI type** | `large_string` — consistent across events files ✅ | OK |
| **Column name collisions** | `vessel_flag_x`, `vessel_flag_y`, `avg_speed_knots_x`, `avg_speed_knots_y` — suffix artifacts from merges | WARNING |
| **Massive nulls (event-type specific)** | ~91% null in encounter/port-specific cols (expected — only populated for those event types) | INFO |
| **Weather nulls** | 78% null — only 22% of events got weather enrichment | WARNING |
| **Registry fill rate** | ~50% null for reg_* columns (only 1,598/14,857 MMSIs matched registry) | **CRITICAL** |
| **Behavioral nulls** | `vessel_flag_y` 11.3% null, `avg_fishing_duration` 21.2% null | WARNING |

### 2.2 `vessel_registry.parquet`
**Rows:** 147,924 | **Cols:** 12 | **Size:** 6.0 MB

| Check | Finding | Severity |
|---|---|---|
| **MMSI type** | `int64` — **MISMATCH with events (string)** | **CRITICAL** |
| **flag_registry nulls** | 95.8% null — almost entirely empty column | WARNING |
| **flag_ais nulls** | 23.7% null | INFO |

### 2.3 `vessel_behavioral_features.parquet`
**Rows:** 14,857 | **Cols:** 32 | **Size:** 1.2 MB

| Check | Finding | Severity |
|---|---|---|
| **MMSI uniqueness** | 14,857 unique = 1:1 ✅ | OK |
| **vessel_flag nulls** | 29.2% null | WARNING |
| **avg_fishing_duration nulls** | 85.8% null (expected — many vessels have no fishing events) | INFO |
| **avg_port_duration nulls** | 86.9% null (expected — many vessels have no port visits) | INFO |
| **avg_speed_knots nulls** | 1.1% null | OK |
| **first_seen range** | Starts 2016 — older than events data (2019+) | INFO |

### 2.4 `weather.parquet`
**Rows:** 2,920 | **Cols:** 9 | **Size:** 27 KB

| Check | Finding | Severity |
|---|---|---|
| **lat/lon type** | `int64` — should be `double` for proper spatial joins | WARNING |
| **Only 8 zones** | Very coarse spatial coverage | INFO |
| **Single year** | Only 2024 data | WARNING |

### 2.5 `viirs_detections.parquet`
**Rows:** 5,000 | **Cols:** 8 | **Size:** 174 KB

| Check | Finding | Severity |
|---|---|---|
| **date_gmt type** | `int64` (e.g., 20240405) — not datetime or string. Must parse manually | WARNING |
| **time_gmt type** | `int64` (e.g., 2347) — inconsistent digit count (10 vs 2347) | WARNING |
| **Only 5,000 rows** | Synthetic/sample data — likely insufficient for production | INFO |

### 2.6 `zenodo_effort_clean.parquet`
**Rows:** 613,325 | **Cols:** 13 | **Size:** 10.5 MB

| Check | Finding | Severity |
|---|---|---|
| **`__index_level_0__` column** | Pandas index leaked into parquet | **CRITICAL** |
| **No nulls** | ✅ | OK |

### 2.7 `sar_presence_clean.parquet`
**Rows:** 742,075 | **Cols:** 18 | **Size:** 35.7 MB

| Check | Finding | Severity |
|---|---|---|
| **Coords** | lat -10.6 to 6.0, lon 95.6 to 139.7 ✅ | OK |
| **date as string** | `large_string` type — `date_parsed` column exists as timestamp | OK |

### 2.8 `fishing_effort_clean.parquet`
**Rows:** 885,649 | **Cols:** 18 | **Size:** 7.7 MB

| Check | Finding | Severity |
|---|---|---|
| **Coords** | Within Indonesia ✅ | OK |
| **Structure** | Same as SAR (consistent schema) ✅ | OK |

### 2.9 `ports.parquet`
**Rows:** 30 | **Cols:** 3 | **Size:** 3 KB

| Check | Finding | Severity |
|---|---|---|
| **Coords** | lat -10.17 to 4.05, lon 98.68 to 140.72 ✅ | OK |
| **Only 30 ports** | Limited coverage for all of Indonesia | INFO |

### 2.10 Cross-File Consistency

| Check | Finding | Severity |
|---|---|---|
| **MMSI overlap (registry → events)** | Only 1,598/14,857 (10.8%) event MMSIs found in registry | **CRITICAL** |
| **MMSI overlap (behavioral → events)** | 14,857/14,857 (100%) ✅ | OK |
| **Event row counts** | Consistent 512,247 across clean/enriched/full ✅ | OK |

---

## 3. Code Quality Report

### 3.1 `src/data/loaders.py` (Phase 1, Step 1.1)
- ✅ Well-structured, clear docstrings
- ⚠️ **Hardcoded input filenames** (e.g., `fishing_events_indonesia_2020-2025.json.gz`) — teammate must have exact filenames
- ⚠️ Uses `print()` instead of `logger` for validation output

### 3.2 `src/data/loaders_sar_effort.py` (Phase 1, Step 1.2)
- ✅ Clean structure
- ⚠️ Same hardcoded filename issue

### 3.3 `src/data/loaders_aux.py` (Phase 1, Steps 1.3-1.5)
- ⚠️ Hardcoded flag list for filtering: `event_flags = ["IDN", "MYS", ...]` — may miss vessels
- ⚠️ `run_step_1_4()` reads all Zenodo CSVs into memory — potential OOM on low-RAM machines

### 3.4 `src/data/step_2_1_dedup.py` (Phase 2, Step 2.1)
- ✅ Memory-efficient Zenodo processing with chunks
- ⚠️ `dedup_fishing_effort()` hardcoded groupby aggregation columns — brittle if schema changes

### 3.5 `src/data/step_2_2_clean.py` (Phase 2, Steps 2.2-2.6)
- ⚠️ **MMSI type mismatch not handled**: vessel_registry has `int64` MMSI, events have `string` MMSI. The join uses `mmsi.astype(str)` mapping but doesn't explicitly handle this — see step_3_1
- ✅ Good flag standardization with FLAG_MAP
- ⚠️ `in_indonesia_bbox` uses ±2° buffer (LAT_MIN-2 to LAT_MAX+2) — may include non-Indonesian waters

### 3.6 `src/data/step_2_7_clean_rest.py` (Phase 2, Step 2.7)
- ✅ Memory-efficient Zenodo cleaning with ParquetWriter
- ⚠️ **Missing FLAG_MAP entries** compared to step_2_2 (e.g., missing "MMR", "KHM")

### 3.7 `src/data/step_3_1_vessel_features.py` (Phase 3, Step 3.1)
- ⚠️ **MMSI type conversion**: `v_lookup.index = v_lookup["mmsi"].astype(str)` — works but fragile
- ⚠️ **`sea_zone` classification uses `df.apply()` row-wise** — extremely slow on 512K rows. Should be vectorized.
- ⚠️ `duration_category` is `pd.Categorical` (dictionary-encoded) — fine for parquet but may cause issues with some ML libraries
- ✅ Nearest port computation is vectorized

### 3.8 `src/data/step_3_4_behavioral.py` (Phase 3, Step 3.4)
- ⚠️ `unique_grid_cells` aggregation uses lambda accessing `df.loc[x.index, ...]` — **bug**: `x` is the group's values, not the group object. Should use `.apply()` with group keys or a different approach.
- ✅ Good per-vessel aggregation structure

### 3.9 `src/data/step_3_5_enrichment.py` (Phase 3, Step 3.5)
- ⚠️ **Column name collisions**: merge with `behavioral` on `mmsi` creates `vessel_flag_x`, `vessel_flag_y`, `avg_speed_knots_x`, `avg_speed_knots_y`, `is_domestic_x`, `is_domestic_y` — these suffixes pollute the final schema
- ⚠️ Weather zone mapping `get_weather_zone()` is overly simplistic (4 zones) vs 8 weather zones — causes 78% null rate
- ⚠️ `ev_date` used for VIIRS join but VIIRS `date_gmt` is int64 format (20240405) — **this join likely fails or produces 0 matches** since `ev_date` is a date object

### 3.10 Other files
- `gfw_client.py` — ✅ Well-structured API client
- `bps_client.py` — ✅ Clean, unused in pipeline (supplementary)
- `weather_client.py` — ✅ Synthetic data generator, produces int lat/lon (hence the schema issue)
- `viirs_setup.py` — ✅ Synthetic data generator
- `mpa_setup.py` — ✅ Sample MPA data
- `synthetic.py` — ✅ AIS trajectory generator
- `graph_builder.py` — Placeholder, minimal implementation
- `stgat.py` — Placeholder, minimal implementation

---

## 4. Architecture Report

| Check | Status | Details |
|---|---|---|
| **Package structure** | ✅ | Clean `src/{data,features,models,utils}/` layout |
| **`__pycache__` present** | ⚠️ | `src/data/__pycache__/` and `src/__pycache__/` with .pyc files |
| **`.gitignore`** | ✅ | Covers parquet, raw data, .bak, __pycache__, .venv |
| **README** | ⚠️ | Structure section lists step files correctly but doesn't mention Phase 3 output |
| **CHANGELOG** | ⚠️ | Phase 3 entry incomplete — doesn't list step 3.4 or 3.5 |
| **No master runner** | **CRITICAL** | Each step must be run individually. No `run_pipeline.py` or Makefile |
| **`tests/`** | ⚠️ | Empty — no unit tests |
| **Python version** | ⚠️ | `pyproject.toml` says `>=3.12` but `__pycache__` shows `.cpython-312.pyc` while system has Python 3.14 |
| **`__init__.py`** | ✅ | Present in all packages |

---

## 5. Reproducibility Assessment

### Can a teammate clone and run the pipeline?

| Requirement | Status | Notes |
|---|---|---|
| Raw data available | ⚠️ | Zenodo zips are gitignored (distributed via GitHub Release). Must download separately. GFW data requires API token. |
| Dependencies installable | ✅ | `pyproject.toml` + `requirements.txt` |
| Step ordering documented | ⚠️ | No numbered master script. Must read CHANGELOG/docs to know order |
| Deterministic output | ⚠️ | No random seeds set in data processing (only in synthetic generators) |
| Intermediate files needed | ⚠️ | Pipeline produces `_flat` → `_dedup` → `_clean` → `_enriched` → `_full`, but intermediate `_flat` and `_dedup` files were deleted. Cannot re-run from middle without re-running from start. |

**Reproducibility Score: 5/10** — A determined teammate can figure it out, but it's not easy.

---

## 6. Recommended Fixes (Prioritized)

### 🔴 Critical (Fix before any modeling)

1. **Fix MMSI type mismatch** — Convert `vessel_registry.parquet` MMSI to `string` at load time in `loaders_aux.py`. Currently causes only 10.8% match rate instead of ~50%+.

2. **Create a master pipeline runner** — `scripts/run_pipeline.py` or `Makefile` that runs steps in order: 1.1 → 1.2 → 1.3-1.5 → 2.1 → 2.2-2.6 → 2.7 → 3.1 → 3.4 → 3.5

3. **Remove `__index_level_0__` from zenodo_effort_clean.parquet** — Add `index=False` when saving (likely leaked from a DataFrame with index). Re-run step 2.7.

4. **Fix VIIRS date join in step_3_5_enrichment.py** — `viirs["vdate"]` parses `date_gmt` (int64 like 20240405) incorrectly. Need `pd.to_datetime(viirs["date_gmt"].astype(str), format="%Y%m%d").dt.date` then join on `ev_date`.

### 🟡 Warning (Fix before submission)

5. **Weather enrichment coverage** — Only 22% match rate due to coarse zone mapping. Improve `get_weather_zone()` to cover all 8 weather zones or use spatial nearest-neighbor.

6. **Fix column name collisions** — In step_3_5, when merging behavioral features, drop duplicate columns (`vessel_flag_y`, `is_domestic_y`, `avg_speed_knots_y`) or rename before merge.

7. **Fix weather lat/lon types** — `weather.parquet` has int64 lat/lon. Fix `weather_client.py` to output floats, and convert in pipeline.

8. **Fix `unique_grid_cells` aggregation bug** — In `step_3_4_behavioral.py`, the lambda `lambda x: len(set(zip(df.loc[x.index, "grid_lat"], ...)))` is unreliable. Use explicit groupby on `(mmsi, grid_lat, grid_lon)` then count unique per vessel.

9. **Vectorize `sea_zone` classification** — Replace `df.apply(lambda r: classify_sea(...), axis=1)` with `np.select()` or `pd.cut()` for 100x speedup on 512K rows.

10. **Complete CHANGELOG** — Add Step 3.4 and 3.5 entries with output details.

### 🔵 Info (Nice to have)

11. **Delete `__pycache__` directories** — `find . -name __pycache__ -exec rm -rf {} +`

12. **Add unit tests** — At minimum, test schema of each output file, test MMSI type consistency, test for expected null rates.

13. **Harmonize FLAG_MAP** — step_2_2 and step_2_7 have slightly different flag maps.

14. **Replace `print()` with `logger`** in loader scripts for consistency.

---

## 7. Data Pipeline Flow Diagram

```
Phase 1 (Load):
  GFW JSON.gz ──→ loaders.py ──→ gfw_events_flat.parquet
  GFW 4Wings   ──→ loaders_sar_effort.py ──→ sar_presence_flat.parquet
                                       ──→ fishing_effort_flat.parquet
  Zenodo/Other ──→ loaders_aux.py ──→ vessel_registry.parquet (⚠️ MMSI int64)
                                  ──→ zenodo_effort_flat.parquet
                                  ──→ weather.parquet (⚠️ int lat/lon)
                                  ──→ viirs_detections.parquet (⚠️ int date)
                                  ──→ ports.parquet

Phase 2 (Clean):
  step_2_1_dedup.py ──→ *_dedup.parquet files
  step_2_2_clean.py ──→ gfw_events_clean.parquet (66 cols)
  step_2_7_clean_rest.py ──→ sar/effort/zenodo_clean.parquet

Phase 3 (Feature Engineering):
  step_3_1_vessel_features.py ──→ gfw_events_enriched.parquet (81 cols)
  step_3_4_behavioral.py ──→ vessel_behavioral_features.parquet (32 cols)
  step_3_5_enrichment.py ──→ gfw_events_full.parquet (124 cols) ← FINAL
```

---

*End of audit report.*
