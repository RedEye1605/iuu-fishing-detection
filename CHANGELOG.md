# Changelog

## v0.6.0 - Full Pipeline Re-run & Validation (2026-04-22)

### Re-run Results
All 9 pipeline steps re-executed from raw data with all fixes applied.

### Validation Results
- ✅ Zero column collisions (_x/_y artifacts eliminated)
- ✅ MMSI type consistent: `large_string` across ALL files
- ✅ vessel_registry MMSI now string (was int64) — 50.3% fill rate confirmed
- ✅ Zenodo spatially filtered: 707K rows (was 30M global) — all within Indonesia bbox
- ✅ No `__index_level_0__` leak in any file
- ✅ No duplicate event_ids
- ✅ All coordinates within Indonesia bbox
- ✅ 121 clean columns in gfw_events_full.parquet

### Final Dataset
- gfw_events_full.parquet: 512,247 rows × 121 cols × 80.7 MB
- 14,857 vessels profiled with behavioral features
- Weather: 100% enriched (8 zones)
- SAR density + Fishing effort density merged
- Column naming: clean, no suffixes, no duplicates

### Documentation
- Rewrote DATA_PIPELINE_IMPLEMENTATION_PLAN.md to match actual implementation
- Updated AUDIT_REPORT.md with post-fix validation results
- Updated PHASE1_AUDIT_FINDINGS.md with resolved issues
- Verified PIPELINE_SCHEMA.md against actual parquet schemas
- Updated README.md with final dataset description
- Created DATA_QUALITY_REPORT.md with ML readiness assessment

## v0.5.0 - Audit Fixes (2026-04-21)

### Critical Fixes
- **MMSI type mismatch fixed:** vessel_registry.parquet MMSI converted from int64 → string
- **VIIRS date parsing:** Fixed `date_gmt` (int64) → proper date via `pd.to_datetime(str, format="%Y%m%d")`
- **Column name collisions:** Fixed `_x/_y` suffix artifacts from behavioral merge
- **Zenodo spatial filter:** Applied bbox filter during loading, not just flag filter
- **Zenodo clean index leak:** Added `index=False` safeguard in step_2_7 ParquetWriter

### Performance Fixes
- **Vectorized sea_zone:** Replaced `df.apply()` with `np.select()` — 100x faster
- **unique_grid_cells bug:** Fixed using two-stage groupby instead of broken lambda
- **duration_category:** Cast from Categorical to string

### Code Quality
- **constants.py:** Created shared module with FLAG_MAP, INDONESIA_BBOX, paths
- **All print() → logger** calls
- **FLAG_MAP harmonized** across all scripts
- **MMSI string type** explicitly enforced everywhere

### Architecture
- **run_pipeline.py:** Master pipeline runner with `--phase` and `--step` args
- **Deleted:** __pycache__, .pyc files, intermediate parquets

## v0.4.0 - Phase 3: Feature Engineering (2026-04-21)

### Step 3.1: Vessel Profile Features
- Joined events with vessel registry (1,598 MMSIs matched, 50.3% fill rate)
- Added: vessel_class, length_m, engine_power_kw, tonnage_gt, size_category
- Added: is_fishing_vessel, tonnage_per_length
- Nearest port computed from 30 Indonesian ports
- Sea zone classification vectorized with np.select()

### Step 3.4: Behavioral Features
- 14,857 unique vessels profiled with 32 features
- Per-vessel: fishing patterns, spatial range, encounter/loitering rates
- Speed stats, port visit patterns

### Step 3.5: Cross-Source Enrichment
- Weather: enriched via zone-based matching (all 8 zones)
- VIIRS: date-corrected join (sample data, limited matches)
- SAR density: merged grid-cell/monthly detection counts
- Fishing effort density: merged grid-cell/monthly fishing hours
- Behavioral features merged per vessel

### Final Dataset
- gfw_events_full.parquet: 512,247 rows × 121 cols, 80.7 MB
- vessel_behavioral_features.parquet: 14,857 vessels × 32 cols

## v0.3.0 - Phase 2: Clean & Validate (2026-04-21)

### Step 2.1: Deduplication
- GFW Events: 512,272 → 512,247 (25 dupes removed)
- SAR Presence: 1,242,915 → 742,075 (dropped grid-only rows + dupes)
- Fishing Effort: 890,411 → 885,649 (summed hours for dupes)
- Zenodo Effort: 707,118 → no dupes
- Vessel Registry: 147,924 → no dupes

### Steps 2.2–2.6: Clean & Validate (GFW Events)
- Filled 58,097 missing vessel flags from registry
- All coordinates within Indonesia bbox
- Duration capping: fishing@72h, loitering@168h, encounters@48h
- Flag standardization via FLAG_MAP (ISO 3166 alpha-3)
- Added 12 derived columns (temporal, domestic, speed flags)
- Final: 512,247 rows × 66 cols

### Step 2.7: Clean Remaining
- SAR, Effort, Zenodo: flag standardized, dates parsed, temporal features added
- Memory-efficient chunked ParquetWriter for Zenodo

### Cleanup
- Removed intermediate (_flat, _dedup) parquet files

## v0.2.0 - Phase 1: Load & Flatten (2026-04-21)

- **loaders.py:** GFW events → gfw_events_flat.parquet (54 cols)
- **loaders_sar_effort.py:** SAR + effort → 2 parquets (13 cols each)
- **loaders_aux.py:** Registry, Zenodo, weather, VIIRS, ports → 5 parquets
- Fixed Zenodo 2021 corrupted zip (redownloaded)
- Updated .gitignore

## v0.1.0 - Initial Setup (2026-04-20)

- Project structure with `src/`, `scripts/`, `docs/`, `tests/`, `notebooks/`
- GFW API client for events, SAR, effort data
- Data download scripts for all sources
- ST-GAT model skeleton
- Graph builder skeleton
