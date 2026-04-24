# IUU Fishing Detection using ST-GAT

## Gemastik XIX 2026 — Data Analytics Category

> **Spatiotemporal Graph Attention Network for Illegal, Unreported, and Unregulated (IUU) Fishing Detection in Indonesian Waters**

---

## Overview

Deep learning system that detects IUU fishing in Indonesian waters by analyzing vessel tracking (AIS) and maritime contextual data through a **Spatiotemporal Graph Attention Network (ST-GAT)**. The system uses vessel-level node features, multi-type graph edges, and weekly temporal snapshots to classify vessels into four IUU risk categories.

### Core Approach
- **Weakly supervised labeling** — 3-tier rule-based scoring with 12 research-backed IUU indicators
- **Graph-based modeling** — 14,841 vessel nodes with encounter and co-location edges
- **Temporal attention** — GRU encoder over weekly graph snapshots
- **Multi-source fusion** — GFW events, SAR detections, fishing effort, vessel registry

---

## Team

- **Toni** — Data Engineering, GIS Analysis
- **Nafi** — Literature Review, Evaluation, Presentation
- **Rhendy** — ML Engineering, Graph Neural Networks, Model Architecture

---

## Project Structure

```
gemastik/
├── src/
│   ├── data/
│   │   ├── constants.py          # Shared constants, FOC flags, temporal boundaries
│   │   └── pipeline/
│   │       ├── extract.py         # Phase 1: Load & flatten raw data
│   │       ├── clean.py           # Phase 2: Dedup, validate, normalize
│   │       ├── features.py        # Phase 3: Vessel profiles, behavioral features
│   │       ├── labels.py          # Phase 4: IUU label generation (3-tier scoring)
│   │       ├── graph.py           # Phase 5: Graph construction (ST-GAT input)
│   │       ├── split.py           # Phase 6: Temporal train/val/test split
│       │       └── prepare.py        # Phase 7: Model data preparation (PyG tensors)
│   ├── models/
│   │   └── stgat.py             # ST-GAT model architecture
│   └── utils/
├── scripts/
│   └── run_pipeline.py          # Master pipeline runner
├── docs/
│   ├── TECHNICAL_DEFENSE.md      # Competition defense paper
│   ├── PIPELINE_SCHEMA.md        # Data schema documentation
│   └── PHASE1-RESEARCH-PLAN.md  # Original research plan
├── data/                         # Raw & processed data (gitignored)
└── pyproject.toml
```

---

## Setup

```bash
cd gemastik
uv venv .venv --python 3.12
source .venv/bin/activate
uv sync --extra ml
```

## Running the Pipeline

```bash
python scripts/run_pipeline.py              # Run all phases (1-8)
python scripts/run_pipeline.py --phase 4    # Run enrichment + labeling
python scripts/run_pipeline.py --step graph   # Run graph construction
python scripts/run_pipeline.py --phase 8    # Run model training
```

Total runtime: ~15-20 minutes (pipeline) + 20-60 min (training).

## Dataset

**511,972 events** across **14,841 vessels** in Indonesian waters (2020-2025).

| Metric | Value |
|--------|-------|
| Vessels | 14,841 |
| Events | 511,972 |
| Weekly snapshots | 274 (208 train / 24 val / 42 test) |
| Continuous features | 40 per vessel |
| Embedding indices | 2 (flag, class) |
| Edge types | 2 (encounter, colocation) |
| Edge attributes | 2 (duration_hours, distance_km) |

### Label Distribution

| Label | Events | % | Description |
|-------|--------|---|-------------|
| normal | 136,442 | 26.7% | Low-risk activity |
| suspicious | 224,675 | 43.9% | Behavioral anomalies |
| probable_iuu | 49,508 | 9.7% | Single IUU violation |
| hard_iuu | 101,347 | 19.8% | Multiple IUU violations |

## Model Architecture

**ST-GAT** with 4-class output, label smoothing, and class weighting. See `docs/TECHNICAL_DEFENSE.md` for full design rationale with academic references.

## Documentation

- [Technical Defense Paper](docs/TECHNICAL_DEFENSE.md) — Complete defense of every design decision
- [Pipeline Schema](docs/PIPELINE_SCHEMA.md) — Data schema documentation
- [Research Plan](docs/PHASE1-RESEARCH-PLAN.md) — Original research plan and data sources

## References

1. Velickovic et al. (2018) — Graph Attention Networks (GAT)
2. Brody et al. (2022) — How Attentive are Graph Attention Networks? (GATv2)
3. Miller et al. (2018) — Stopping the Hidden Hunt for Seafood (GFW encounters)
4. Boerder et al. (2018) — Identifying Global Patterns of Transshipment (FoC flags)
5. Kroodsma et al. (2018) — Tracking the Global Footprint of Fisheries (GFW fishing)
6. Ford et al. (2018) — Revealing AIS Gaps (AIS disabling detection)
7. McDonald et al. (2021) — Identifying Forced Labor (PU learning for maritime)
8. Rossi et al. (2020) — Temporal Graph Networks (temporal message passing)
9. Szegedy et al. (2016) — Rethinking the Inception Architecture (label smoothing)
10. Li et al. (2018) — Deeper Insights into Graph Convolutional Networks (over-smoothing)
