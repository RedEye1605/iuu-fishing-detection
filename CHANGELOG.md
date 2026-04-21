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
