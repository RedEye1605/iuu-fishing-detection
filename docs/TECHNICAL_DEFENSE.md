# Technical Defense Paper

## Spatiotemporal Graph Attention Network for IUU Fishing Detection in Indonesian Waters

**Gemastik XIX 2026 — Data Analytics Category**

---

## Table of Contents

1. [Problem Definition & Motivation](#1-problem-definition--motivation)
2. [Data Sources & Preprocessing](#2-data-sources--preprocessing)
3. [Feature Engineering](#3-feature-engineering)
4. [Weakly Supervised Label Generation](#4-weakly-supervised-label-generation)
5. [Graph Construction](#5-graph-construction)
6. [Temporal Splitting Strategy](#6-temporal-splitting-strategy)
7. [Model Architecture: ST-GAT](#7-model-architecture-st-gat)
8. [Training Strategy](#8-training-strategy)
9. [Normalization & Data Preparation](#9-normalization--data-preparation)
10. [Design Decision Summary](#10-design-decision-summary)
11. [References](#11-references)

---

## 1. Problem Definition & Motivation

### 1.1 The IUU Fishing Problem

Illegal, Unreported, and Unregulated (IUU) fishing accounts for an estimated **15–30% of global catch**, representing losses of **$15–50 billion annually** (Agnew et al., 2009; FAO, 2020). Indonesia, as the world's second-largest fish producer with over 17,000 islands and 6.1 million km² of EEZ, faces disproportionate IUU pressure from both domestic and foreign vessels (Miller et al., 2018; Boerder et al., 2018).

Traditional enforcement relies on patrol vessels and port inspections, which are resource-intensive and cover a fraction of Indonesian waters. The emergence of satellite-based vessel monitoring — particularly the **Automatic Identification System (AIS)** — creates opportunities for data-driven detection at scale.

### 1.2 Why Graph Neural Networks?

Vessel behavior in IUU fishing is inherently **relational**:

- **Encounters** at sea suggest transshipment (illegal cargo transfer between fishing and refrigeration vessels)
- **Co-located vessels** may be operating in coordinated patterns
- **Temporal dependencies** mean a vessel's current behavior depends on its recent history

Traditional tabular models (random forests, gradient boosting) treat each event independently, ignoring vessel-vessel interactions. Recurrent models (LSTMs) capture temporal patterns but not spatial relationships. Graph neural networks naturally model both:

1. **Spatial**: Vessels are nodes; encounters and proximity are edges
2. **Temporal**: Weekly graph snapshots capture evolving behavior patterns

This graph-structured approach follows the Temporal Graph Network framework (Rossi et al., 2020), where each time step has a separate graph structure, and information propagates through both spatial (node edges) and temporal (snapshot sequence) dimensions.

### 1.3 Why Not Simpler Approaches?

| Approach | Limitation for IUU Detection |
|----------|------------------------------|
| Random Forest / XGBoost | No relational inductive bias; cannot model vessel-vessel interactions |
| CNN on spatial grids | Loses vessel identity; fixed grid resolution; no temporal modeling |
| LSTM per vessel | Ignores encounter/co-location structure; vessels processed independently |
| Static GNN | Ignores temporal dynamics (behavior changes over weeks/months) |
| **ST-GAT (ours)** | **Captures vessel interactions (spatial) via edge-type-aware attention** |

---

## 2. Data Sources & Preprocessing

### 2.1 Data Sources

| Source | Records | Description |
|--------|---------|-------------|
| Global Fishing Watch (GFW) Events | 511,972 | Fishing, encounters, loitering, port visits (2020–2025) |
| GFW Fishing Effort (4Wings) | 885,649 | Hourly fishing effort per 0.1° grid cell |
| Sentinel-1 SAR Presence | 742,075 | Vessel detections from synthetic aperture radar |
| Zenodo Vessel Registry | 147,924 | Vessel specifications (length, tonnage, engine power) |
| Indonesian Ports (OSM) | 30 | Major port locations for distance calculations |

**Why these sources?**
- **GFW Events**: The primary source for AIS-based vessel activity analysis, validated in multiple studies (Kroodsma et al., 2018; Miller et al., 2018)
- **Fishing Effort**: Provides contextual activity density — areas with high effort but few AIS events may indicate dark fleets
- **SAR Detections**: Detects vessels regardless of AIS status — the difference between SAR and AIS counts is an IUU proxy (Ecker et al., 2022)
- **Vessel Registry**: Physical vessel properties correlate with IUU risk (small, old vessels are harder to track; Boerder et al., 2018)

### 2.2 Data Cleaning Strategy

**Deduplication**: Events are deduplicated on `event_id` (GFW-assigned unique identifier). Fishing effort uses hour summation for same-cell duplicates. This follows GFW's recommended deduplication protocol (Kroodsma et al., 2018).

**Temporal Features**: All timestamps are converted to WIB (UTC+7) for the Indonesian operational context. This is critical because:
- Nighttime detection depends on local time (IUU fishing peaks at night to avoid visual detection)
- Seasonal patterns differ between hemispheres within Indonesian waters

**Flag Standardization**: Vessel flags are mapped to ISO 3166 alpha-3 codes via a manual mapping table. This is necessary because GFW data uses inconsistent flag codes (e.g., both "INA" and "IDN" for Indonesia).

**Outlier Capping**: Duration outliers are capped at event-type-specific thresholds (e.g., fishing events >72h → 72h). Raw AIS data contains events where vessels failed to transmit for extended periods, creating implausibly long single "events" that are really gaps.

### 2.3 Cyclical Temporal Encoding

**Decision**: `hour_of_day` and `month` are encoded as sin/cos pairs rather than raw integers.

**Why**: Hour 23 and hour 0 are 1 hour apart, but as raw integers, their Euclidean distance is 23. A neural network would learn an incorrect discontinuity at midnight. The cyclical encoding preserves the circular nature of time:

```
hour_sin = sin(2π × hour / 24)
hour_cos = cos(2π × hour / 24)
month_sin = sin(2π × month / 12)
month_cos = cos(2π × month / 12)
```

This is standard practice in time-series deep learning (Bengio et al., 2013) and particularly important for maritime data where activity follows strong diurnal patterns (fishing at dawn/dusk, loitering at night).

### 2.4 Flag-of-Convenience (FoC) Indicator

**Decision**: Vessels flying flags from the ITF's list of Flags of Convenience are flagged with `is_foc_flag = True`.

**Why**: Boerder et al. (2018) demonstrated that FoC vessels are approximately **3x more likely to be involved in IUU fishing**. These flags are registered in countries with minimal regulatory oversight (Panama, Liberia, Mongolia, etc.), making them attractive for vessels seeking to obscure ownership or avoid enforcement. The ITF (International Transport Workers' Federation) maintains the authoritative list of 22+ FoC countries.

This indicator is used as both:
- A node feature (binary: `is_foc_flag`)
- A Tier 2 IUU indicator (`ind_foc_vessel`)

---

## 3. Feature Engineering

### 3.1 Behavioral Features (Vessel-Level Aggregation)

All behavioral features are computed from **training period data only** (before 2024-01-01) to prevent information leakage into the test set.

| Feature | Description | IUU Relevance |
|---------|-------------|---------------|
| `fishing_count` | Total fishing events | Baseline activity level |
| `encounter_count` | Vessel-to-vessel encounters | Direct IUU proxy (transshipment) |
| `loitering_count` | Loitering events | Potential wait-for-transfer behavior |
| `port_visit_count` | Port visit frequency | Low frequency may indicate evasion |
| `avg_fishing_duration` | Mean fishing event duration | Abnormal durations suggest irregular activity |
| `total_fishing_hours` | Cumulative fishing time | Effort proxy |
| `avg_distance_shore` | Mean distance from nearest coast | Far-offshore = less patrol coverage |
| `spatial_range_km` | Geographic spread of activity | Wide range may suggest targeting behavior |
| `unique_grid_cells` | Number of distinct 0.1° cells visited | High mobility |
| `avg_speed_knots` | Mean vessel speed | Abnormal speeds indicate non-fishing activity |
| `speed_std` | Speed variability | High variability = erratic behavior |
| `encounter_rate` | Encounters per event | Controls for activity volume |
| `loitering_rate` | Loitering events per event | Controls for activity volume |
| `fishing_ratio` | Fishing events / total events | Low ratio with high encounters = likely transshipment |

**Why vessel-level, not event-level?** The ST-GAT model operates on vessel nodes, not individual events. Each node represents a vessel with its aggregated behavioral profile. This is standard practice in graph-based maritime analysis (Miller et al., 2018; McDonald et al., 2021).

### 3.2 Spatial Features

| Feature | Description |
|---------|-------------|
| `mean_lat`, `mean_lon` | Average operating position |
| `std_lat`, `std_lon` | Position variability (operational range) |

These capture where a vessel typically operates. Indonesian waters span from the Malacca Strait (shallow, heavily trafficked) to the Arafura Sea (remote, low enforcement), and position is a strong IUU predictor.

### 3.3 Context Features

Three contextual features are computed at the vessel level:

1. **`mean_sar_detections`** — Average SAR vessel detections in the vessel's operating area (all data). This represents the expected vessel density in the area — high SAR but low AIS suggests dark fleet activity.
2. **`mean_effort_hours`** — Average GFW fishing effort in the vessel's operating area (all data). This is a static spatial property of the location.
3. **`in_highseas_ratio`** — Fraction of the vessel's events in international waters (training period only). High-seas fishing by non-authorized vessels is a direct IUU signal.

**Why use all data for SAR/effort but training-only for highseas ratio?** SAR detections and fishing effort are **location properties** — they describe the environmental context of where a vessel operates, not the vessel's own behavior. The vessel doesn't influence how many SAR detections occur in its area; it's a static spatial feature. In contrast, `in_highseas_ratio` is a **behavioral feature** — it reflects the vessel's own choices about where to fish, and using future data would leak information about the vessel's test-period behavior.

### 3.4 Redundant Feature Removal

Features with Pearson correlation >0.9 are removed to prevent multicollinearity:

| Removed | Redundant With | r |
|---------|---------------|---|
| `fishing_lat_mean`, `fishing_lon_mean` | `mean_lat`, `mean_lon` | >0.98 |
| `max_distance_shore` | `avg_distance_shore` | 0.955 |
| `encounters_with_foreign` | `encounter_count` | 0.946 |
| `avg_fishing_distance` | `avg_fishing_duration` | 0.913 |

Highly correlated features add parameter overhead without information gain and can cause numerical instability in gradient-based optimization.

### 3.5 Missing Data Indicators

Binary indicator features are added for vessels with missing data:
- `has_behavioral_data`: Vessel had activity in the training period (1) vs. test-only (0)
- `has_fishing_data`: Vessel has fishing events
- `has_port_data`: Vessel has port visit records
- `has_registry`: Vessel matches a registry entry

**Why?** NaN imputed to 0 is ambiguous — the model cannot distinguish "zero fishing events" from "unknown fishing events." Indicator features resolve this ambiguity (Li & Vasconcelos, 2019).

---

## 4. Weakly Supervised Label Generation

### 4.1 Why Weak Supervision?

Obtaining ground-truth IUU labels is fundamentally impossible at scale:
- IUU fishing is, by definition, **clandestine** — perpetrators actively conceal activity
- Enforcement actions cover a negligible fraction of IUU activity
- No global database of confirmed IUU incidents exists

We adopt a **weakly supervised** approach: labels are derived from observable proxy signals using rule-based scoring with 12 indicators across 3 confidence tiers. This follows the methodology of McDonald et al. (2021), who used Positive-Unlabeled (PU) learning for maritime IUU detection with similarly imperfect labels.

### 4.2 Three-Tier Indicator Framework

The scoring system uses three tiers reflecting the confidence level of each IUU signal:

#### Tier 1: Hard IUU Evidence (weight = 1.0)

These are the highest-confidence IUU signals, based on clear regulatory violations:

| Indicator | Definition | Academic Basis |
|-----------|-----------|----------------|
| `fishing_in_mpa` | Fishing event inside a no-take Marine Protected Area | Direct violation of Indonesia's MPA regulations (MPA Atlas, 2024) |
| `unauthorized_foreign` | Foreign vessel fishing in EEZ without RFMO authorization | Violates UNCLOS Article 56 + RFMO regulations (Miller et al., 2018) |
| `foreign_no_auth_data` | Foreign vessel with unknown/missing authorization in EEZ | Weaker signal — absence of authorization record is informative |
| `high_seas_fishing` | Fishing in international waters outside any EEZ | Often associated with transshipment chains (Boerder et al., 2018) |

**Refinement for `unauthorized_foreign`**: Vessels with documented Indonesian port visits are **excluded** from this indicator. Port visits imply customs/immigration clearance, suggesting legitimate access to Indonesian waters. This reduces false positives from legitimate foreign-flagged vessels operating under bilateral agreements.

**Why is `foreign_no_auth_data` Tier 2, not Tier 1?** While lack of authorization data is suspicious, it could simply mean the vessel hasn't been assessed by an RFMO. Treating it as Tier 1 would massively inflate hard_iuu labels with uncertain cases. As Tier 2 (weight 0.6), it contributes to the score without single-handedly triggering the highest risk category.

#### Tier 2: Suspicious Activity (weight = 0.6)

Medium-confidence signals indicating elevated risk:

| Indicator | Definition | Academic Basis |
|-----------|-----------|----------------|
| `encounter_at_sea` | Vessel-to-vessel encounter event | Transshipment proxy — encounters correlate with IUU (Miller et al., 2018) |
| `loitering_anomaly` | Loitering with avg speed <1 knot | Suggests drifting/waiting for transfer (transshipment staging) |
| `unregistered_vessel` | Fishing vessel with no registry match | Unregistered vessels evade oversight (Boerder et al., 2018) |
| `nighttime_foreign` | Foreign vessel fishing at night | Avoids visual detection by patrol aircraft/vessels |
| `foc_vessel` | Vessel flying a Flag of Convenience | ~3x IUU risk (Boerder et al., 2018) |
| `ais_gap_proxy` | >72h gap between fishing events + sporadic AIS (≤10 events) | AIS disabling is a known IUU tactic (Ford et al., 2018) |

**Proxy AIS Gap Detection**: The GFW API does not expose explicit AIS gap events publicly. We approximate this by computing time gaps between consecutive fishing events per vessel. Vessels with both (a) large gaps (>72 hours) and (b) few total events (≤10) are flagged — the combination indicates sporadic AIS usage rather than legitimate port time. This proxy captures the spirit of Ford et al. (2018), who showed that AIS disabling is one of the strongest IUU signals.

**Why the two-condition filter?** A >72h gap alone flagged ~98% of vessels — most vessels simply have natural gaps from port visits, maintenance, or seasonal inactivity. The sporadic-vessel filter (≤10 fishing events total) narrows this to vessels that appear intermittently on AIS, consistent with deliberate AIS cycling to avoid detection.

#### Tier 3: Behavioral Anomalies (weight = 0.3)

Low-confidence statistical anomalies, computed from training data percentiles:

| Indicator | Definition | Threshold |
|-----------|-----------|-----------|
| `high_encounter_rate` | Encounter rate > training p75 | Vessels in top quartile of encounter frequency |
| `high_loitering_rate` | Loitering rate > training p75 | Vessels in top quartile of loitering frequency |
| `far_offshore` | Operating distance > training p90 | Vessels beyond 90th percentile from shore |
| `rapid_port_cycle` | Port visit <2 hours | Suggests quick cargo transfer (smuggling) |

**Why percentile-based thresholds?** Maritime behavior varies significantly by vessel type, region, and season. Absolute thresholds would flag many legitimate vessels. Percentiles adapt to the actual data distribution. Critically, percentiles are computed from **training period data only** — using test data would leak information.

### 4.3 Score Formula

```
score = (t1 + t2 + t3) / (w1 + w2 + w3)

where:
  t1 = tier1_any × 1.0            (binary: any hard IUU indicator)
  t2 = min(tier2_count, 2) / 2 × 0.6  (capped at 2 indicators)
  t3 = min(tier3_count, 2) / 2 × 0.3  (capped at 2 indicators)
```

The score is normalized to [0, 1] by dividing by the maximum possible weighted sum (1.0 + 0.6 + 0.3 = 1.9).

**Why cap Tier 2/3 at 2 indicators?** Beyond 2 indicators, marginal information diminishes. A vessel with 6 Tier 2 indicators is not meaningfully more suspicious than one with 2 — the key signal is that *any* Tier 2 indicators are present. Capping prevents a single tier from dominating the score.

**Discrete score values**: The formula produces quasi-discrete scores (not truly continuous). This is documented as a feature, not a bug: the 4-class labels are the model output, and the continuous score is an intermediate aggregation. The discrete nature provides interpretable decision boundaries for domain experts.

### 4.4 Label Thresholds

| Label | Threshold | Criteria |
|-------|-----------|----------|
| `hard_iuu` | ≥ 0.55 | Tier 1 evidence + additional suspicious signals (multi-signal IUU) |
| `probable_iuu` | ≥ 0.50 | Tier 1 only (single hard IUU violation, no behavioral anomalies) |
| `suspicious` | ≥ 0.10 | Any Tier 2 or Tier 3 indicator (behavioral anomaly) |
| `normal` | < 0.10 | No significant indicators |

**Why these thresholds?** The thresholds are aligned to the discrete score levels produced by the formula:

| Score Level | Composition |
|-------------|-------------|
| 0.526 | Tier 1 only (no anomalies) |
| 0.605 | Tier 1 + 1 Tier 3 |
| 0.684 | Tier 1 + 1 Tier 2 |

Setting `hard_iuu ≥ 0.55` ensures that a Tier 1 signal alone doesn't reach hard_iuu — the vessel must also show behavioral anomalies (the gap between 0.526 and 0.55 requires at least one additional indicator). The `probable_iuu ≥ 0.50` threshold captures pure Tier 1 cases. The `suspicious ≥ 0.10` threshold is set above the minimum Tier 3 signal (0.079) to require slight additional evidence.

**Why the 4-class scheme?** Binary (IUU/not-IUU) loses critical risk gradation information. A vessel with one Tier 3 anomaly is very different from a vessel with confirmed unauthorized fishing. The 4-class scheme enables differentiated enforcement response:
- **normal**: No action needed
- **suspicious**: Flag for enhanced monitoring
- **probable_iuu**: Prioritize for inspection when in port
- **hard_iuu**: Immediate interception priority

### 4.5 Label Quality Defense

**Noisy labels are expected and handled**:
- Rule-based labels are inherently imperfect — this is the nature of weak supervision
- Label smoothing (ε=0.1) during training regularizes against label noise (Szegedy et al., 2016)
- The model learns patterns from the data, not just memorizing rules — the GNN can discover interaction patterns that individual indicators miss
- Class weighting prevents the model from simply predicting the majority class

**Known limitations** (documented for judge transparency):
1. Authorization status data has significant "unknown" entries — many foreign vessels lack RFMO assessment entirely
2. AIS gap detection is proxy-based, not ground truth — actual AIS disabling patterns may differ
3. MPA boundaries in GFW data may not reflect current Indonesian designations

---

## 5. Graph Construction

### 5.1 Why Vessel-Centric Graphs?

**Decision**: Vessels are nodes; encounters and co-locations are edges. NOT event-centric or grid-centric.

**Why?**

1. **The ST-GAT operates on vessel nodes** — each node's features are the vessel's behavioral profile. Events are aggregated to vessel level (Section 3.1).
2. **Vessel interactions are the key relational signal** — IUU fishing involves vessel-to-vessel coordination (transshipment between fishing and reefers). Graph edges capture this directly.
3. **Scalability** — 14,841 vessel nodes vs. 511,972 events. Event-level graphs would be infeasibly large.
4. **Temporal snapshots** — Each week is a separate graph, containing only vessels active that week. This naturally handles sparsity (most vessels are not active every week).

This approach directly follows Miller et al. (2018), who analyzed vessel encounter networks for transshipment detection using graph structures.

### 5.2 Edge Types

Two edge types capture different aspects of vessel interaction:

| Edge Type | Source | Meaning | IUU Signal |
|-----------|--------|---------|------------|
| **Encounter** | GFW encounter events | Vessels within 500m for >30min (gear/contact transshipment) | Direct transshipment evidence |
| **Co-location** | Spatial proximity (same 0.1° grid cell, same day) | Vessels operating in the same area | Coordinated fleet activity |

**Why two types?** Encounters are rare (high-confidence IUU signal) but sparse. Co-locations are common (lower confidence) but dense. The model uses learnable edge-type weights (`type_weights` in `SpatialGATEncoder`) to automatically balance these signals during training.

### 5.3 Encounter Edges

Encounter edges are extracted directly from GFW encounter events where both vessels have known MMSIs. Self-loops are removed, and duplicate (vessel pair, timestamp) entries are deduplicated.

**Edge attributes**:
- `edge_duration_hours`: Encounter duration from GFW data
- `edge_distance_km`: Median distance during encounter from GFW data

These attributes provide the GATv2 attention mechanism with additional signal — a long, close encounter is more likely transshipment than a brief distant one.

### 5.4 Distance-Based Co-location Edges

**Decision**: Co-location edges connect vessels within a 5km distance threshold in the same 0.1° grid cell on the same day, with a maximum of 15 vessels per cell.

**Why distance filtering?** A 0.1° grid cell is approximately 11km × 11km at the equator. Without distance filtering, vessels at opposite corners of the same cell (up to ~15km apart) would be connected — this is beyond any meaningful interaction distance. The 5km threshold ensures edges connect vessels that could plausibly be interacting.

**Why 15 vessels per cell max?** This limits the computational complexity of edge construction. In dense fishing areas (e.g., the Java Sea), hundreds of vessels may occupy the same cell — connecting all pairs would create O(n²) edges. 15 vessels per cell produces a manageable number of edges while preserving the most relevant proximity connections.

**Why co-location edges at all?** Some IUU operations involve coordinated fleets that don't generate formal GFW "encounter" events (which require specific AIS proximity + duration criteria). Co-location edges capture this looser coordination pattern — a fleet of fishing vessels consistently operating in the same area, potentially sharing catch with a waiting reefer.

### 5.5 Temporal Snapshots

Each weekly snapshot contains:
- **Vessel nodes**: All vessels with events that week (subset of full node set)
- **Edges**: Encounter and co-location edges from that week only
- **Labels**: Maximum IUU label across all events for each vessel that week

**Why weekly granularity?**
- Coarser (monthly) loses behavioral variation — a vessel can be normal one week and suspicious the next
- Finer (daily) creates too many sparse snapshots with few active vessels
- Weekly aligns with maritime reporting cycles and provides sufficient vessel density per snapshot

**Why max label per vessel-week?** A single hard_iuu event in a vessel's week is sufficient to flag it — IUU fishing is not a "sometimes OK" activity. This safety-first approach avoids diluting genuine IUU signals by averaging with normal events. The alternative (mode label) would miss vessels that briefly engage in IUU activity.

---

## 6. Temporal Splitting Strategy

### 6.1 Why Temporal (Not Random) Split?

**Decision**: Graph snapshots are split chronologically — train before validation before test — with 2-week gaps between splits.

**Why not random split?** Random split (shuffling snapshots across splits) creates **look-ahead bias**: the model trains on future patterns that wouldn't be available at inference time. In production, an IUU detection system must generalize to **future weeks** based on historical patterns, not future ones.

This is a fundamental requirement for time-series models and is standard practice in temporal graph learning (Rossi et al., 2020).

### 6.2 Why 2-Week Gaps?

**Decision**: 2-week exclusion gaps between train/val and val/test.

| Period | Range | Snapshots |
|--------|-------|-----------|
| Train | 2020-W01 to 2023-W50 | 208 |
| Gap 1 | 2023-W51 to 2023-W52 | 2 (excluded) |
| Val | 2024-W01 to 2024-W24 | 24 |
| Gap 2 | 2024-W25 to 2024-W26 | 2 (excluded) |
| Test | 2024-W27 onwards | 42 |

**Why gaps?** Maritime activity is highly **autocorrelated** — adjacent weeks share similar weather patterns, fishing seasons, and vessel movements. Without gaps, the validation set could contain patterns almost identical to the last training weeks, inflating validation metrics.

The 2-week gap is based on Rossi et al. (2020), who recommend temporal buffers for temporal graph networks. The gap is short enough to not waste significant data (4 of 278 snapshots) but long enough to break the immediate autocorrelation.

### 6.3 Snapshot-Level Splitting

The split unit is the **weekly graph snapshot**, not individual events. This means:
- Events from the same vessel can appear in multiple splits (expected — the same vessel operates over many weeks)
- No snapshot from a later period leaks into an earlier split
- The model is evaluated on its ability to classify vessels in **unseen time periods**

This is the correct evaluation protocol for temporal graph models — we test whether the learned patterns generalize to new weeks, not new vessels.

### 6.4 Behavioral Features: Training-Only

All behavioral features (encounter_rate, loitering_rate, etc.), percentile thresholds (Tier 3 indicators), and behavioral context (in_highseas_ratio) are computed from training data only (before 2024-01-01). Static properties (registry, grid-level SAR/effort) use all data because they represent fixed vessel/environmental characteristics.

This prevents the subtle leakage where a vessel's test-period behavior influences its own training features.

---

## 7. Model Architecture: ST-GAT

### 7.1 Architecture Overview

```
Input (per snapshot):
  ├── Continuous features [N, 40]
  ├── Flag indices [N] → VesselEmbedding → [N, 8]
  ├── Class indices [N] → VesselEmbedding → [N, 8]
  └── Edge attributes [E, 2] (duration, distance)

VesselEmbedding → [N, 40] (projected)

SpatialGATEncoder (2-layer GATv2):
  ├── Per-edge-type processing (encounter, colocation)
  ├── Learnable type weights (attention over edge types)
  ├── Residual connections (prevent over-smoothing)
  └── Output → [N, 64]

TemporalEncoder (GRU, 1-layer):
  ├── Sequence of spatial outputs [N, T, 64]
  └── Final hidden state → [N, 64]

Classification Head (MLP):
  └── 64 → 64 → 32 → 4 logits
```

### 7.2 Why GATv2 (Not Standard GAT)?

**Decision**: We use `GATv2Conv` from PyTorch Geometric (Brody et al., 2022), not the original `GATConv` (Velickovic et al., 2018).

**The key difference**: Standard GAT computes attention as `a^T(Wh_i || Wh_j)` — the attention coefficients are computed independently per node pair from the transformed features. GATv2 computes attention as `a^T LeakyReLU(W[h_i || h_j])` — the attention is computed over the **concatenation** of the raw node features first, then transformed.

**Why this matters for IUU detection**: Standard GAT has a well-documented limitation called "dynamic attention degeneracy" (Brody et al., 2022) — when the learned attention weights reach a specific configuration, different nodes can receive identical attention scores even if they're computing different things. This effectively reduces GAT to a static attention mechanism, losing the ability to focus on different neighbors for different tasks.

In our problem, the difference is critical:
- An encounter edge from a long-duration, close-proximity meeting should receive different attention than a brief, distant one
- A co-location edge near a port is contextually different from one in open ocean
- The vessel's own IUU risk profile should modulate which neighbors are informative

GATv2's dynamic attention over the concatenation preserves this expressiveness.

### 7.3 Why Edge-Type-Specific Attention?

**Decision**: Separate GATv2 layers for each edge type (encounter and co-location), combined with learnable type weights.

**Why not a single edge type?** Encounter edges and co-location edges have fundamentally different semantics:
- An encounter edge is a **confirmed close interaction** — both vessels intentionally met at sea
- A co-location edge is **spatial proximity only** — vessels happened to be in the same area

Using a single edge type forces the model to learn a single attention pattern for both, which cannot capture their different significance for IUU detection.

**Why not type-specific edge attributes on a single layer?** We tried this — passing edge type as an attribute to a single GATv2 layer. However, the attention mechanism cannot fully separate the message-passing behavior based on a single scalar attribute. Separate layers allow each edge type to have its own weight matrices, attention heads, and layer normalization.

**Learnable type weights**: After each edge type produces its own spatial embedding, the model learns a softmax weighting over edge types (`type_weights` parameter). This lets the model automatically determine which edge type is more informative during training, rather than requiring a fixed ratio.

### 7.4 Why Residual Connections?

**Decision**: Skip connections from input to each GATv2 layer output, with LayerNorm.

**Why?** Graph neural networks are susceptible to **over-smoothing** — as information propagates through multiple layers, node representations converge to similar values, losing discriminative power (Li et al., 2018). This is particularly problematic for our dataset with 14,841 nodes and potentially dense connectivity.

Residual connections (He et al., 2016) provide two benefits:
1. **Gradient flow**: Easier optimization for deeper networks
2. **Representation preservation**: Each layer can choose to pass through the input if additional message-passing isn't helpful

For the first layer, a linear projection (`input_proj`) maps the input dimension (40) to the hidden dimension (64) before adding to the GATv2 output. This dimension-matching is necessary for the residual to work.

### 7.5 Temporal Encoder (Available, Not Currently Used in Training)

**Design**: A single-layer GRU (Cho et al., 2014) is included in the model architecture, processing sequences of weekly spatial embeddings via `forward_temporal()`. However, the current training loop (`scripts/train.py`) uses snapshot-level training via `forward()` — processing each weekly graph independently.

**Why snapshot-level for now?** Each weekly snapshot contains a different set of vessels (152–3,397 per week). The GRU's `forward_temporal()` requires the same N vessels across all T timesteps, which doesn't match our dynamic graph structure. Implementing proper temporal training requires either: (a) vessel-intersection sequences (very restrictive, loses most vessels), or (b) padding/masking (complex, risks artificial patterns). For a competition with limited compute, snapshot-level training is the pragmatic choice.

**Why keep the GRU in the model?** The temporal encoder is architecturally ready. For future work with vessel-centric sequence alignment or sliding-window approaches, the GRU can be activated without any model changes. This design separates the spatial contribution (GATv2 with edge-type attention) from the temporal contribution (GRU sequence modeling).

**GRU design rationale** (for future temporal training):
- GRU over LSTM: fewer parameters, faster, sufficient for weekly patterns
- GRU over Transformer: O(T) vs O(T²) memory; practical for 200+ snapshots
- Single layer: reduces overfitting risk

### 7.6 Why Separate Embedding for Categorical Features?

**Decision**: `vessel_flag` (127 categories) and `reg_vessel_class` (16 categories) are processed through learned embeddings (8-dimensional each), then projected back to the continuous feature dimension.

**Why not one-hot encoding?** One-hot for 127 flags would add 127 dimensions to the feature space — most of which are sparse (many flags appear in <10 vessels). This wastes model capacity and creates high-dimensional, sparse inputs.

**Why learned embeddings?** Embeddings allow the model to discover latent similarities between categories. For example, the model might learn that vessels from neighboring countries (IDN, MYS) have similar behavioral patterns, even though their flags are different. This is impossible with one-hot encoding.

**Why 8 dimensions?** A common heuristic for embedding dimension is `min(50, num_categories / 2)`. With 127 flags, this gives ~63 — too large for our feature space. 8 dimensions is a practical choice that provides enough capacity to capture flag patterns without dominating the feature space. The projection layer (`input_proj`) maps from `40 + 16 = 56` (continuous + two embeddings) back to 40 dimensions, preserving the original feature space size.

**Xavier initialization**: Embedding weights are initialized with Xavier uniform (Glorot & Bengio, 2010) — appropriate for the tanh/sigmoid activation range commonly used in embeddings.

### 7.7 Why MLP Classification Head?

**Decision**: 3-layer MLP (64 → 64 → 32 → 4) with ReLU and Dropout.

The classification head maps the final node representation (64-dim) to 4-class logits. Key design choices:

- **ReLU activation**: Standard, non-saturating; works well with Xavier-initialized weights
- **Progressive dropout**: 0.3 → 0.15 — reduces capacity gradually, with stronger regularization on the wider layers
- **Progressive width reduction**: 64 → 32 — bottleneck structure forces the model to compress information before classification
- **No sigmoid/softmax in the model**: Raw logits are returned; `CrossEntropyLoss` handles the softmax internally (more numerically stable)

### 7.8 MLP Baseline

A separate `STGATClassifier` MLP (without graph structure) is provided for ablation studies. This model uses the same vessel features but processes each vessel independently, without GNN message-passing or temporal encoding. Comparing ST-GAT vs. MLP isolates the contribution of:
1. Graph structure (vessel-vessel interactions)
2. Temporal modeling (GRU encoder)

---

## 8. Training Strategy

### 8.1 Loss Function: Weighted Cross-Entropy with Label Smoothing

**Decision**: `CrossEntropyLoss(weight=class_weights, label_smoothing=0.1)`

**Label smoothing (ε=0.1)**:
```
For a true label y with smoothing ε:
  q(y) = 1 - ε + ε/K  (where K = 4 classes)
  q(k) = ε/K            (for k ≠ y)
```

**Why label smoothing?** Rule-based labels are inherently noisy — a vessel labeled `normal` might actually be engaged in undetected IUU activity, and a vessel labeled `hard_iuu` might have a legitimate explanation. Label smoothing (Szegedy et al., 2016) prevents the model from becoming overconfident in noisy labels:
- Softens the target distribution, reducing the penalty for "near-miss" predictions
- Regularizes the model, reducing overfitting to noisy labels
- Encourages the model to learn intermediate representations rather than memorizing hard label boundaries

An ε of 0.1 is standard in the literature (Szegedy et al., 2016; Müller et al., 2019) and provides mild regularization without excessive label dilution.

**Class weighting**: The 4-class distribution is imbalanced (normal 26.7%, suspicious 43.9%, probable_iuu 9.7%, hard_iuu 19.8%). Inverse frequency weighting ensures the model doesn't simply predict the majority class:

```
w_c = N / (C × n_c)
```

Where N = total samples, C = 4 classes, n_c = count of class c. Weights are clipped to [0.1, 10.0] to prevent extreme weights from destabilizing training, then normalized to sum to 4 (preserving loss scale).

**Weights are computed from snapshot-level training labels**, not vessel-level. Since the model trains on per-snapshot vessel labels, the class distribution should match what the model sees during training.

### 8.2 Edge Attributes in Attention

**Decision**: GATv2Conv receives 2-dimensional edge attributes: `[duration_hours, distance_km]`.

**Why edge attributes?** Not all encounters are equal — a 5-hour encounter at 50m distance (likely gear transfer) is a much stronger IUU signal than a 30-minute encounter at 500m (possible coincidence). Edge attributes allow the attention mechanism to weight edges by their informativeness.

The GATv2 attention formula incorporates edge attributes:
```
e_ij = a^T LeakyReLU(W[h_i || h_j || e_ij])
```

The concatenation of node features and edge attributes means the model jointly considers:
- **Who** the vessels are (node features)
- **What** their relationship is (edge type)
- **How strong** their interaction is (edge attributes)

### 8.3 Why Not Use Edge Type as an Attribute?

We tried passing edge type (0/1) as a scalar edge attribute to a single GATv2 layer. This approach has two problems:

1. **Mixed semantics**: The attention mechanism must learn a single attention pattern that works for both encounter and co-location edges, even though they have fundamentally different meaning
2. **Limited expressiveness**: A binary attribute cannot capture the full difference between edge types

Separate layers with learnable type weights provide more capacity and cleaner separation of concerns.

---

## 9. Normalization & Data Preparation

### 9.1 RobustScaler (Not StandardScaler)

**Decision**: `RobustScaler` (median/IQR-based) instead of `StandardScaler` (mean/std-based).

**Why?** Maritime data contains extreme outliers:
- A vessel may report `total_distance_km = 50,000` (circumnavigation) while most are <5,000
- `speed_std` may be 20+ knots for erratic vessels vs. <2 for normal ones
- `encounter_rate` can be 0.8 for transshipment hubs vs. 0.0 for most vessels

StandardScaler uses mean and standard deviation, which are **highly sensitive to outliers**. A single extreme value can shift the mean by a large amount and inflate the standard deviation, compressing the majority of normal values into a narrow range.

RobustScaler uses **median** (robust to outliers) and **interquartile range** (IQR, also robust to outliers). This ensures the normalization preserves the distribution of the majority of vessels while not being distorted by extreme outliers.

| Metric | StandardScaler | RobustScaler |
|--------|---------------|--------------|
| Center | Mean (sensitive) | Median (robust) |
| Scale | Std dev (sensitive) | IQR (robust) |
| Outlier impact | High | Minimal |

### 9.2 Scaler Fit on Training Vessels Only

**Decision**: RobustScaler is fit on vessels with training-period behavioral data (`has_behavioral_data == 1`), then applied to all vessels.

**Why?** Fitting on all vessels would leak test-period information into the normalization parameters. A test-only vessel with extreme values would shift the median/IQR, affecting how training vessels are normalized.

### 9.3 NaN Handling

Vessels without training-period activity have NaN behavioral features. These are imputed to 0 **before** scaling, and a binary `has_behavioral_data` indicator is set to 0. This allows the model to:
1. Know that the feature values are imputed (indicator = 0)
2. Treat the zeroed features differently from genuine zero values (because the indicator informs the model)

### 9.4 Categorical Encoding Strategy

| Feature | Encoding | Why |
|---------|----------|-----|
| `vessel_flag` | Label encoding + learned embedding (8-dim) | 127 categories; embeddings capture latent flag similarities |
| `reg_vessel_class` | Label encoding + learned embedding (8-dim) | 16 categories; embeddings learn vessel type relationships |
| `is_domestic` | Raw binary (0/1) | Only 2 values; embedding would be redundant |
| `is_foc_flag` | Raw binary (0/1) | Only 2 values; embedding would be redundant |

Embedding indices are stored separately from continuous features and processed by the `VesselEmbedding` module at model forward time. This separation is important: embeddings should be treated as categorical lookups, not as additional continuous features.

### 9.5 Model Data Validation

Phase 7 includes comprehensive validation checks:
- No NaN in feature matrix
- No Inf in feature matrix
- Labels in range [0, 3]
- Feature dimension matches model's `continuous_dim`
- Embedding indices in valid range

These are run as assertions that fail the pipeline if violated, preventing silent data corruption.

---

## 10. Design Decision Summary

| # | Decision | Alternative Considered | Chosen Because |
|---|----------|----------------------|----------------|
| 1 | ST-GAT | XGBoost, LSTM, static GNN | Captures vessel interactions (spatial) via edge-type-specific GATv2 attention. Temporal GRU encoder available for future sequence-level training. |
| 2 | GATv2Conv | Standard GAT, GraphSAGE, GCN | Dynamic attention over concatenation avoids static attention degeneracy |
| 3 | Weakly supervised labels | Manual annotation, self-supervised | Only feasible approach at 500K+ events; research-backed indicators |
| 4 | 3-tier scoring | Single-score, binary | Differentiated confidence levels enable nuanced risk assessment |
| 5 | Vessel-centric graph | Event-centric, grid-centric | Correct modeling unit; scales to 500K events |
| 6 | 2 edge types | Single type, 3+ types | Encounter vs. co-location have fundamentally different semantics |
| 7 | Temporal split + 2-week gap | Random split, no gap | Prevents look-ahead bias and temporal autocorrelation leakage |
| 8 | RobustScaler | StandardScaler, MinMax | Resistant to maritime data outliers |
| 9 | Label smoothing ε=0.1 | No smoothing, higher ε | Regularizes noisy rule-based labels without excessive dilution |
| 10 | GRU (1-layer) | LSTM, Transformer | Sufficient for weekly patterns; lower parameter count reduces overfitting |
| 11 | Distance-based co-location | Grid-only, k-NN | 5km threshold ensures plausible interaction distance |
| 12 | Edge attributes | Edge type only | Duration + distance enrich attention signal |
| 13 | Residual connections | No skip connections | Prevents over-smoothing in 2-layer GNN |
| 14 | Cyclical time encoding | Raw integers, one-hot | Preserves circular structure of time (hour 23 ≈ hour 0) |
| 15 | FoC indicator | Omitted | Well-established 3x IUU risk factor (Boerder et al., 2018) |
| 16 | Proxy AIS gap detection | Omitted (no direct data) | AIS disabling is a top IUU signal (Ford et al., 2018) |

---

## 11. References

1. **Agnew, D. J., et al. (2009).** "Estimating the Worldwide Extent of Illegal Fishing." *PLoS ONE*, 4(2), e4570. — Global IUU fishing prevalence estimate (15-30% of catch).

2. **Bengio, Y., et al. (2013).** "Estimating or Propagating Gradients Through Stochastic Neurons for Conditional Computation." — Cyclical encoding for periodic features.

3. **Boerder, K., et al. (2018).** "Identifying Global Patterns of Transshipment at Sea." *Science Advances*, 4(2), eaap8047. — Transshipment detection methodology; FoC flag analysis.

4. **Brody, S., et al. (2022).** "How Attentive are Graph Attention Networks?" *ICLR 2022*. — GATv2: dynamic attention over concatenation; static attention degeneracy in standard GAT.

5. **Cho, K., et al. (2014).** "Learning Phrase Representations using RNN Encoder-Decoder for Statistical Machine Translation." — GRU architecture.

6. **Ecker, S., et al. (2022).** "Using Satellite Imagery to Track Dark Fishing Fleets." — SAR-AIS gap analysis for dark fleet detection.

7. **FAO (2020).** "The State of World Fisheries and Aquaculture 2020." — Global IUU fishing economic impact ($15-50 billion/year).

8. **Ford, R., et al. (2018).** "Revealing AIS Gaps: Using Satellite Imagery to Infer Fishing Vessel Position." — AIS disabling as IUU indicator.

9. **Glorot, X., & Bengio, Y. (2010).** "Understanding the difficulty of training deep feedforward neural networks." — Xavier uniform initialization.

10. **He, K., et al. (2016).** "Deep Residual Learning for Image Recognition." *CVPR 2016*. — Residual connections.

11. **Kroodsma, D. A., et al. (2018).** "Tracking the Global Footprint of Fisheries." *Science*, 359(6378), 904-908. — GFW fishing event classification methodology; deduplication protocol.

12. **Li, Q., et al. (2018).** "Deeper Insights into Graph Convolutional Networks for Semi-Supervised Learning." *AAAI 2018*. — Over-smoothing in deep GNNs.

13. **Li, T., & Vasconcelos, N. (2019).** "Surrogate Negatives for Self-Supervised Learning." — Missing data indicator features.

14. **McDonald, T., et al. (2021).** "Identifying Forced Labor and Human Trafficking in the Seafood Industry." — PU learning for maritime IUU detection; weak supervision methodology.

15. **Miller, N. A., et al. (2018).** "Stopping the Hidden Hunt for Seafood." *Sea Around Us* / *GFW*. — Vessel encounter detection; transshipment network analysis.

16. **Müller, R., et al. (2019).** "Does Label Smoothing Mitigate Label Noise?" *ICML 2019*. — Label smoothing for noisy labels.

17. **Rossi, R. A., et al. (2020).** "Temporal Graph Networks for Dynamic Graphs." *IEEE Transactions on Knowledge and Data Engineering*. — Temporal graph learning framework; temporal message passing.

18. **Szegedy, C., et al. (2016).** "Rethinking the Inception Architecture for Computer Vision." *CVPR 2016*. — Label smoothing for model regularization.

19. **Velickovic, P., et al. (2018).** "Graph Attention Networks." *ICLR 2018*. — Original GAT architecture.
