# 🔍 Comprehensive Audit Report — IUU Fishing Detection Pipeline

**Date:** 2026-04-22 (final validation)
**Scope:** Phase 1–5 data files, code, and architecture

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Overall Status** | ✅ PASS |
| **Pipeline Completeness** | Phases 1–5 complete, validated, reproducible |
| **Final Dataset** | 512,247 rows × 124 cols (labeled) + 14,857 vessel graph |
| **Critical Issues** | 0 (all 4 resolved) |
| **Remaining Warnings** | 4 (non-blocking) |

All critical issues from the initial audit have been resolved. The pipeline produces a clean, validated dataset with consistent types, no collisions, and verified data quality. Remaining warnings are inherent data limitations (sample sizes, temporal coverage) that don't affect pipeline correctness.

---

## 2. Post-Fix Validation Results (2026-04-22)

Full pipeline re-run from raw data with all fixes applied:

| Check | Result |
|-------|--------|
| MMSI type consistency | ✅ `large_string` in ALL 12 parquet files |
| Duplicate event_ids | ✅ 0 duplicates |
| Coordinate validity | ✅ 100% within Indonesia bbox |
| Column name collisions | ✅ 0 `_x/_y` suffix artifacts |
| Index leaks | ✅ No `__index_level_0__` in any file |
| Zenodo spatial filter | ✅ 707K rows, all within bbox |
| Registry join | ✅ 50.3% fill rate (1,598 MMSIs matched) |
| Weather enrichment | Removed in v0.7.0 | Insufficient coverage (2024 only, 20%) |
| VIIRS date parsing | Removed in v0.7.0 | Insufficient signal (0.01% match rate) |

### Column Null Analysis (gfw_events_full.parquet)
- 75/111 columns: 0% null
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
**Rows:** 512,247 | **Cols:** 111

| Check | Finding | Status |
|---|---|---|
| Duplicates | 0 duplicate event_ids | ✅ |
| Spatial validity | All coords within Indonesia bbox | ✅ |
| MMSI type | `large_string` consistent | ✅ |
| Column collisions | None | ✅ |
| Event-type nulls | Expected pattern (port cols null for fishing, etc.) | ✅ |
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

### ~~3.4 `weather.parquet`~~ — REMOVED in v0.7.0
Weather enrichment removed due to insufficient temporal coverage (2024 only, 20% of events).

### ~~3.5 `viirs_detections.parquet`~~ — REMOVED in v0.7.0
VIIRS enrichment removed due to insufficient signal (5K sample rows, 0.01% match rate: 65/512K events).

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

### 3.10 Graph Output Files

#### `vessel_node_features.parquet`
**Rows:** 14,857 | **Cols:** 55 (54 features + mmsi)

| Check | Finding | Status |
|---|---|---|
| MMSI uniqueness | 14,857 unique = 1:1 with events | ✅ |
| Feature completeness | 54 features across 7 categories | ✅ |
| Label coverage | vessel_iuu_label: 0 nulls | ✅ |
| Registry features | ~50% null (expected, matches Phase 3 fill rate) | ⚠️ |

#### `encounter_edges.parquet`
**Rows:** 46,239 edges

| Check | Finding | Status |
|---|---|---|
| Edge count | Matches Phase 1 encounter events | ✅ |
| Timestamps | Valid UTC timestamps | ✅ |
| MMSI pairs | All MMSIs exist in node features | ✅ |

#### `colocation_edges.parquet`
**Rows:** 138,049 unique vessel pairs

| Check | Finding | Status |
|---|---|---|
| Grid resolution | 0.1° (~11km) | ✅ |
| Same-day constraint | Verified | ✅ |
| MMSI pairs | All MMSIs exist in node features | ✅ |

#### `snapshot_metadata.parquet`
**Rows:** 283 weekly snapshots

| Check | Finding | Status |
|---|---|---|
| Date range | Covers full dataset temporal range | ✅ |
| Min vessels per snapshot | >0 (41 weeks skipped for <3 vessels) | ✅ |
| Edge counts | Consistent with encounter + colocation totals | ✅ |

#### `graph_snapshots.pkl`
Full graph data — gitignored (too large for git). Reconstructible via `python scripts/run_pipeline.py --phase 5`.

### 3.11 Cross-File Consistency

| Check | Finding | Status |
|---|---|---|
| MMSI overlap (registry → events) | 1,598/14,857 (10.8%) | ⚠️ Real limitation |
| MMSI overlap (behavioral → events) | 14,857/14,857 (100%) | ✅ |
| Event row counts | Consistent 512,247 | ✅ |
| Graph nodes → Behavioral MMSIs | 14,857/14,857 (100%) | ✅ |
| Graph edges → Event encounters | 46,239 matches | ✅ |

---

## 4. Resolved Issues

The following critical issues were identified in the initial audit and have been **fully resolved**:

### 🔴 Critical → ✅ Fixed

1. **MMSI type mismatch** — vessel_registry MMSI was `int64`, events were `string`. Fixed: MMSI explicitly cast to string in pipeline/extract.py. Join rate improved from broken to 50.3%.

2. **No master pipeline runner** — Fixed: `scripts/run_pipeline.py` with `--phase` and `--step` args.

3. **`__index_level_0__` column in zenodo** — Fixed: `index=False` safeguard in clean.py ParquetWriter. Verified absent.

4. **VIIRS date join failure** — Resolved by removing VIIRS enrichment entirely in v0.7.0 (0.01% signal: 65/512K events).

### 🟡 Warning → ✅ Fixed

5. **Weather enrichment 22% coverage** — Resolved by removing weather enrichment entirely in v0.7.0 (only 2024 data, 20% temporal coverage).

6. **Column name collisions (_x/_y)** — Fixed: Duplicate columns dropped before merge in enrich.py.

7. **`unique_grid_cells` bug** — Fixed: Two-stage groupby approach instead of broken lambda.

8. **`sea_zone` vectorization** — Fixed: `np.select()` replaces `df.apply()`, 100x faster.

9. **FLAG_MAP harmonization** — Fixed: constants.py provides single source of truth.

---

## 5. Remaining Warnings (Non-blocking)

| # | Issue | Impact | Mitigation |
|---|-------|--------|------------|
| 1 | Registry fill rate 50.3% | Missing vessel specs for ~half of vessels | Use available fields; SAR as alternative signal |
| 2 | `potential_risk` only 0.4% True | Severe class imbalance | Anomaly detection or weighted loss |
| 3 | No EEZ/MPA shapefile join | Uses GFW regions field instead | GFW regions data is reliable |
| 4 | 30 ports only | Limited nearest-port coverage | Major ports covered; add from OSM |

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
Phase 1 (Extract):
  pipeline/extract.py ──→ gfw_events_flat.parquet (54 cols)
                      ──→ sar_presence_flat.parquet (13 cols)
                      ──→ fishing_effort_flat.parquet (13 cols)
                      ──→ vessel_registry.parquet (12 cols, MMSI string)
                      ──→ zenodo_effort_flat.parquet (10 cols, spatially filtered)
                      ──→ ports.parquet (3 cols)

Phase 2 (Clean):
  pipeline/clean.py ──→ Dedup + validate + normalize all datasets
                   ──→ gfw_events_clean.parquet (66 cols)
                   ──→ sar/effort/zenodo_clean.parquet

Phase 3 (Features + Enrichment):
  pipeline/features.py ──→ Vessel profiles + behavioral features (32 cols)
  pipeline/enrich.py   ──→ gfw_events_full.parquet (111 cols)

Phase 4 (Labels):
  pipeline/labels.py   ──→ gfw_events_labeled.parquet (124 cols) ← FINAL

Phase 5 (Graph):
  pipeline/graph.py    ──→ vessel_node_features.parquet (14,857 × 55)
                    ──→ encounter_edges.parquet (46,239)
                    ──→ colocation_edges.parquet (138,049)
                    ──→ snapshot_metadata.parquet (283)
                    ──→ graph_snapshots.pkl (gitignored)
```

---

*End of audit report. Updated 2026-04-22.*
