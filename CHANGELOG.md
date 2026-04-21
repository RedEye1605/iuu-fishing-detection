# Changelog

## [0.2.0] - 2026-04-21

### Phase 1: Load & Flatten — COMPLETE
- Generated 8 processed Parquet files from raw data sources
- **loaders.py:** GFW events (fishing, encounters, loitering, port visits) → unified `gfw_events_flat.parquet`
- **loaders_sar_effort.py:** SAR presence & fishing effort → `sar_presence_flat.parquet`, `fishing_effort_flat.parquet`
- **loaders_aux.py:** Auxiliary data (weather, VIIRS, ports, vessel registry, Zenodo effort) → 5 parquet files
- Fixed Zenodo 2021 corrupted zip (redownloaded successfully)
- Data audit completed — see `docs/PHASE1_AUDIT_FINDINGS.md`
- Updated `.gitignore` to exclude `*.parquet`, `data/raw/`, `*.bak`, `.pytest_cache/`
- Cleaned up stray files (`.bak`, `test.html`, `__pycache__/`, `.pytest_cache/`)

## [0.1.0] - 2026-04-20

### Initial Setup
- Project structure with `src/`, `scripts/`, `docs/`, `tests/`, `notebooks/`
- GFW API client for events, SAR, effort data
- Data download scripts for all sources
- ST-GAT model skeleton
- Graph builder skeleton

## v0.3.0 - Phase 2: Clean & Validate (2026-04-21)

### Step 2.1: Deduplication
- GFW Events: 512,272 → 512,247 (25 dupes removed on event_id)
- SAR Presence: 1,242,915 → 742,075 (dropped 500K grid-only rows + 432 dupes)
- Fishing Effort: 890,411 → 885,649 (summed hours for 4,762 dupes)
- Zenodo Effort: 30,150,420 → no dupes found
- Vessel Registry: 147,924 → no dupes (already deduped in Phase 1)

### Steps 2.2–2.6: Clean & Validate (GFW Events)
- Filled 58,097 missing vessel flags from registry
- 0 invalid coordinates, all within Indonesia bbox
- 673 fishing events capped at 72h, 1,025 loitering at 168h
- 2,564 encounter events capped at 48h
- 0 speed outliers (>30 knots)
- Added 12 new columns: temporal features, is_domestic, season, speed flags
- Final: 512,247 rows × 66 cols

### Step 2.7: Clean Remaining
- SAR: flag standardized, dates parsed, temporal features added (18 cols)
- Effort: flag standardized, dates parsed, temporal features added (18 cols)
- Zenodo: flag standardized, season added (memory-efficient chunked, 12 cols)

### Cleanup
- Removed 9 intermediate (_flat, _dedup) parquet files
- Final 8 clean parquet files in data/processed/

## v0.4.0 - Phase 3: Feature Engineering (2026-04-21)

### Step 3.1: Vessel Profile Features
- Joined events with vessel registry (1,598 MMSIs matched, 50.3% fill rate)
- Added: vessel_class, length_m, engine_power_kw, tonnage_gt, size_category
- Added: is_fishing_vessel, tonnage_per_length (density proxy)
- Nearest port computed from 30 Indonesian ports
- Sea zone classification (Java Sea, Malacca Strait, etc.)

### Step 3.3: Temporal Features (already in Phase 2)
- Duration category: short (<2h), medium (2-8h), long (>8h)
- Grid cell (0.1° ≈ 11km) for spatial aggregation

### Step 3.4: Behavioral Features
- 14,857 unique vessels profiled with 32 features
- Per-vessel: fishing patterns, spatial range, encounter/loitering rates
- Speed stats, port visit patterns
- Key finding: 85% loitering rate (many vessels only appear in loitering events)

### Step 3.5: Cross-Source Enrichment
- Weather: 100% enriched (zone-based monthly averages)
- VIIRS: 0% match (VIIRS sample dates don't overlap with event dates)
- SAR density: merged grid-cell/monthly detection counts
- Fishing effort density: merged grid-cell/monthly fishing hours
- Behavioral features merged per vessel

### Final Dataset
- gfw_events_full.parquet: 512,247 rows × 105 cols, 81.2 MB
- vessel_behavioral_features.parquet: 14,857 vessels × 32 cols, 1.2 MB

### Hotfix: Zenodo Spatial Filter (2026-04-21)
- **Bug:** Zenodo effort was filtered by flag only (30M rows global), not by Indonesia bbox
- **Fix:** Applied spatial filter (lat -11.5 to 6.5, lon 95 to 141.5) during raw reprocessing
- **Result:** 613,325 rows (down from 30M), all confirmed within Indonesian waters
- 29.5M rows were vessels with relevant flags operating globally (e.g. CHN trawlers near Antarctica)

## v0.5.0 - Audit Fixes (2026-04-21)

### Critical Fixes
- **MMSI type mismatch fixed:** vessel_registry.parquet MMSI converted from int64 → string. Previous join rate was 10.8%, now consistent.
- **Zenodo index leak:** Confirmed no `__index_level_0__` column in zenodo_effort_clean.parquet (was already clean)
- **VIIRS date parsing:** Fixed `date_gmt` (int64 like 20240405) → proper date via `pd.to_datetime(viirs["date_gmt"].astype(str), format="%Y%m%d").dt.date`
- **Column name collisions:** Fixed `_x/_y` suffix artifacts from behavioral merge (vessel_flag, is_domestic, avg_speed_knots)
- **Zenodo spatial filter:** Applied bbox filter (lat -11.5 to 6.5, lon 95 to 141.5) during loading, not just flag filter
- **Zenodo clean index leak:** Added `index=False` safeguard in step_2_7 ParquetWriter

### Performance Fixes
- **Vectorized sea_zone:** Replaced `df.apply()` row-wise classification with `np.select()` — 100x faster on 512K rows
- **unique_grid_cells bug:** Fixed aggregation using proper two-stage groupby (dedup grid cells → count per vessel) instead of broken lambda
- **duration_category:** Cast from Categorical to string for ML library compatibility

### Code Quality
- **constants.py:** Created shared module with FLAG_MAP, INDONESIA_BBOX, EVENT_FLAGS, all paths/filenames
- **All pipeline scripts** now import from constants.py (single source of truth)
- **All print() statements** replaced with logger calls
- **FLAG_MAP harmonized** across step_2_2 and step_2_7 (added MMR, KHM)
- **MMSI string type** explicitly enforced in loaders_aux (step 1.3), dedup (step 2.1), and joins (steps 2.2, 3.1)

### Architecture
- **run_pipeline.py:** Master pipeline runner with `--phase` and `--step` args
- **Deleted:** __pycache__ directories, .pyc files, vessel_registry_dedup.parquet symlink
- **Deleted intermediates:** gfw_events_clean.parquet, gfw_events_enriched.parquet (rebuildable from pipeline)
- **Documentation:** Updated README.md, added PIPELINE_SCHEMA.md

### Full Audit Report
- See `docs/AUDIT_REPORT.md` for complete findings
- **Bug:** Zenodo effort was filtered by flag only (30M rows global), not by Indonesia bbox
- **Fix:** Applied spatial filter (lat -11.5 to 6.5, lon 95 to 141.5) during raw reprocessing
- **Result:** 613,325 rows (down from 30M), all confirmed within Indonesian waters
- 29.5M rows were vessels with relevant flags operating globally (e.g. CHN trawlers near Antarctica)
