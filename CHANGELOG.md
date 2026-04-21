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
