"""
Spatiotemporal Graph Attention Network (ST-GAT) for IUU fishing detection.

Architecture:
- Input: Per-vessel node features [N, F] + embedding indices
- Spatial encoder: 2-layer GATv2Conv with edge-type-specific attention
- Temporal encoder: GRU over snapshot sequence
- Classification head: MLP → 4-class logits (normal/suspicious/probable_iuu/hard_iuu)

Key design decisions (research-backed):
- GATv2Conv (Brody et al., 2022): dynamic attention over concatenation, more expressive
  than standard GAT for learning complex vessel-vessel interactions.
- Edge-type-aware: separate attention for encounter vs co-location edges
  (encounter = stronger IUU signal, co-location = proximity context).
- Residual connections: prevent over-smoothing in deeper GNN layers (Li et al., 2018).
- Label smoothing: handles noisy rule-based labels (Szegedy et al., 2016).
- Class weights: inverse frequency weighting for imbalanced IUU distribution.

References:
- Velickovic et al. (2018) "Graph Attention Networks" — original GAT
- Brody et al. (2022) "How Attentive are Graph Attention Networks?" — GATv2
- Rossi et al. (2020) "Temporal Graph Networks" — temporal message passing
- Miller et al. (2018) "Stopping the hidden hunt for seafood" — GFW encounter methodology
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv
from torch_geometric.utils import scatter

logger = logging.getLogger(__name__)

NUM_CLASSES = 4
LABEL_NAMES = ["normal", "suspicious", "probable_iuu", "hard_iuu"]


class VesselEmbedding(nn.Module):
    """Learned embeddings for categorical vessel attributes.

    Args:
        num_flags: Number of unique vessel flags.
        num_classes: Number of unique vessel classes.
        embed_dim: Embedding dimension.
        continuous_dim: Number of continuous input features.
        dropout: Dropout rate.
    """

    def __init__(
        self,
        num_flags: int = 128,
        num_classes: int = 17,
        embed_dim: int = 8,
        continuous_dim: int = 40,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.flag_embedding = nn.Embedding(num_flags, embed_dim)
        self.class_embedding = nn.Embedding(num_classes, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)
        self.input_proj = nn.Linear(continuous_dim + 2 * embed_dim, continuous_dim)
        self.output_dim = continuous_dim

    def forward(
        self,
        x_cont: torch.Tensor,
        flag_idx: Optional[torch.Tensor] = None,
        class_idx: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Combine continuous features with learned embeddings.

        Args:
            x_cont: Continuous features [N, continuous_dim].
            flag_idx: Vessel flag indices [N].
            class_idx: Vessel class indices [N].

        Returns:
            Fused feature matrix [N, output_dim].
        """
        embeds = []
        if flag_idx is not None:
            embeds.append(self.flag_embedding(flag_idx))
        if class_idx is not None:
            embeds.append(self.class_embedding(class_idx))

        if embeds:
            x_cat = torch.cat([x_cont] + embeds, dim=-1)
            x_cat = self.embed_dropout(x_cat)
            return self.input_proj(x_cat)
        return x_cont


class SpatialGATEncoder(nn.Module):
    """Multi-layer GATv2 spatial encoder with residual connections.

    Args:
        in_dim: Input feature dimension.
        hidden_dim: Hidden dimension.
        out_dim: Output dimension.
        num_heads: Attention heads.
        dropout: Dropout rate.
        edge_types: Number of edge types for type-specific processing.
        edge_dim: Edge attribute dimension (e.g., 2 for [duration, distance]).
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 64,
        out_dim: int = 64,
        num_heads: int = 4,
        dropout: float = 0.3,
        edge_types: int = 2,
        edge_dim: int = 2,
    ) -> None:
        super().__init__()

        self.edge_types = edge_types
        self.num_heads = num_heads
        self.hidden_dim = hidden_dim

        # Per edge-type GATv2 layers — first layer
        # GATv2Conv concat=True: output = heads * out_channels_per_head
        # We want total output = hidden_dim, so per_head = hidden_dim / heads
        self.conv1 = nn.ModuleList([
            GATv2Conv(
                in_dim, hidden_dim // num_heads, heads=num_heads,
                dropout=dropout, concat=True, add_self_loops=True,
                edge_dim=edge_dim,
            )
            for _ in range(edge_types)
        ])
        self.norm1 = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(edge_types)])
        self.dropout1 = nn.Dropout(dropout)

        # Input projection for first-layer residual (in_dim → hidden_dim)
        if in_dim != hidden_dim:
            self.input_proj = nn.Linear(in_dim, hidden_dim, bias=False)
        else:
            self.input_proj = None

        # Second layer (same dim → residual works)
        self.conv2 = nn.ModuleList([
            GATv2Conv(
                hidden_dim, hidden_dim // num_heads, heads=num_heads,
                dropout=dropout, concat=True, add_self_loops=True,
                edge_dim=edge_dim,
            )
            for _ in range(edge_types)
        ])
        self.norm2 = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(edge_types)])
        self.dropout2 = nn.Dropout(dropout)

        # Learnable type weights — attention over edge types
        self.type_weights = nn.Parameter(torch.zeros(edge_types))
        nn.init.zeros_(self.type_weights)

        # Project back to out_dim
        self.proj = nn.Linear(hidden_dim, out_dim)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Apply edge-type-specific GATv2 with residual connections.

        Args:
            x: Node features [N, in_dim].
            edge_index: Edge indices [2, E].
            edge_type: Edge type per edge [E] (0=encounter, 1=colocation).
            edge_attr: Optional edge attributes [E, d].

        Returns:
            Updated node features [N, out_dim].
        """
        type_weights = F.softmax(self.type_weights, dim=0)
        out = torch.zeros(x.size(0), self.hidden_dim, device=x.device)

        # Project input for residual connection
        x_proj = self.input_proj(x) if self.input_proj is not None else x

        for et in range(self.edge_types):
            mask = edge_type == et
            if mask.sum() == 0:
                continue

            et_edges = edge_index[:, mask]
            et_weight = type_weights[et]

            # Layer 1 with residual
            h = self.dropout1(x)
            h = F.elu(self.conv1[et](h, et_edges, edge_attr=et_edge_attr(edge_attr, mask)))
            h = self.norm1[et](h + x_proj)

            # Layer 2 with residual
            h2 = self.dropout2(h)
            h2 = F.elu(self.conv2[et](h2, et_edges, edge_attr=et_edge_attr(edge_attr, mask)))
            h2 = self.norm2[et](h2 + h)

            out = out + et_weight * h2

        return self.proj(out)


class TemporalEncoder(nn.Module):
    """GRU-based temporal encoder over snapshot sequence.

    Args:
        input_dim: Input feature dimension per snapshot.
        hidden_dim: GRU hidden dimension.
        num_layers: Number of GRU layers.
        dropout: Dropout between GRU layers.
    """

    def __init__(
        self,
        input_dim: int = 64,
        hidden_dim: int = 64,
        num_layers: int = 1,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.gru = nn.GRU(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(
        self,
        x_seq: torch.Tensor,
        h0: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode temporal sequence of snapshot features.

        Args:
            x_seq: Sequence of node features [N, T, input_dim].
            h0: Initial hidden state [num_layers, N, hidden_dim].

        Returns:
            Tuple of (final hidden [N, hidden_dim], all hidden states).
        """
        out, hn = self.gru(x_seq, h0)
        hn = self.norm(hn[-1])
        return hn, out


class STGAT(nn.Module):
    """Spatiotemporal Graph Attention Network for IUU fishing detection.

    Combines:
    1. Learned embeddings for categorical vessel attributes (flag, class)
    2. Spatial GATv2 encoder with edge-type-specific attention + residual connections
    3. Temporal GRU encoder over weekly snapshot sequence
    4. MLP classification head → 4-class logits

    Args:
        continuous_dim: Continuous feature dimension.
        num_flags: Number of unique vessel flags.
        num_vessel_classes: Number of unique vessel classes.
        embed_dim: Embedding dimension for categorical features.
        hidden_dim: Hidden dimension for GAT and GRU.
        num_heads: Attention heads per GAT layer.
        dropout: Dropout rate.
        num_edge_types: Number of edge types (default 2: encounter, colocation).
        label_smoothing: Smoothing factor for label noise (0.0 = disabled).
    """

    def __init__(
        self,
        continuous_dim: int = 40,
        num_flags: int = 128,
        num_vessel_classes: int = 17,
        embed_dim: int = 8,
        hidden_dim: int = 64,
        num_heads: int = 4,
        dropout: float = 0.3,
        num_edge_types: int = 2,
        label_smoothing: float = 0.1,
    ) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.label_smoothing = label_smoothing

        # Embedding layer for categorical features
        self.embedding = VesselEmbedding(
            num_flags=num_flags,
            num_classes=num_vessel_classes,
            embed_dim=embed_dim,
            continuous_dim=continuous_dim,
            dropout=dropout,
        )

        # Spatial GAT encoder
        self.spatial_encoder = SpatialGATEncoder(
            in_dim=continuous_dim,
            hidden_dim=hidden_dim,
            out_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            edge_types=num_edge_types,
        )

        # Temporal encoder
        self.temporal_encoder = TemporalEncoder(
            input_dim=hidden_dim,
            hidden_dim=hidden_dim,
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim // 2, NUM_CLASSES),
        )

        self._init_weights()

        total_params = sum(p.numel() for p in self.parameters())
        logger.info(
            "ST-GAT initialized: continuous_dim=%d, hidden=%d, heads=%d, "
            "edge_types=%d, label_smoothing=%.2f, params=%,d",
            continuous_dim, hidden_dim, num_heads, num_edge_types,
            label_smoothing, total_params,
        )

    def _init_weights(self) -> None:
        """Initialize weights with Xavier for linear layers."""
        for module in self.modules():
            if isinstance(module, nn.Linear) and module.weight.requires_grad:
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        x_cont: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        flag_idx: Optional[torch.Tensor] = None,
        class_idx: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass for single snapshot.

        Args:
            x_cont: Continuous node features [N, continuous_dim].
            edge_index: Edge indices [2, E].
            edge_type: Edge type per edge [E].
            flag_idx: Vessel flag embedding indices [N].
            class_idx: Vessel class embedding indices [N].
            edge_attr: Optional edge attributes [E, d].

        Returns:
            Class logits [N, 4].
        """
        # Embed categorical features
        x = self.embedding(x_cont, flag_idx, class_idx)

        # Spatial encoding
        h = self.spatial_encoder(x, edge_index, edge_type, edge_attr)

        # Classification
        return self.classifier(h)

    def forward_temporal(
        self,
        x_seq: torch.Tensor,
        edge_indices: list[torch.Tensor],
        edge_types: list[torch.Tensor],
        flag_idx: Optional[torch.Tensor] = None,
        class_idx: Optional[torch.Tensor] = None,
        edge_attrs: Optional[list[Optional[torch.Tensor]]] = None,
    ) -> torch.Tensor:
        """Forward pass over temporal sequence of snapshots.

        Args:
            x_seq: Node features over time [N, T, continuous_dim].
            edge_indices: List of edge_index tensors, one per timestep.
            edge_types: List of edge_type tensors, one per timestep.
            flag_idx: Vessel flag indices [N].
            class_idx: Vessel class indices [N].
            edge_attrs: Optional list of edge attribute tensors.

        Returns:
            Class logits [N, 4].
        """
        T = x_seq.size(1)
        spatial_outs = []

        for t in range(T):
            h = self.embedding(x_seq[:, t, :], flag_idx, class_idx)
            e_attr = edge_attrs[t] if edge_attrs else None
            h = self.spatial_encoder(h, edge_indices[t], edge_types[t], e_attr)
            spatial_outs.append(h)

        # Stack and run through temporal encoder
        spatial_seq = torch.stack(spatial_outs, dim=1)
        h_final, _ = self.temporal_encoder(spatial_seq)

        return self.classifier(h_final)

    def compute_loss(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        class_weights: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute weighted cross-entropy loss with optional label smoothing.

        Args:
            logits: Model output [N, 4].
            labels: Ground truth labels [N].
            class_weights: Optional class weight tensor [4].

        Returns:
            Scalar loss.
        """
        loss_fn = nn.CrossEntropyLoss(
            weight=class_weights,
            label_smoothing=self.label_smoothing,
        )
        return loss_fn(logits, labels)


class STGATClassifier(nn.Module):
    """MLP baseline classifier for vessel-level IUU prediction (no graph).

    Args:
        input_dim: Feature dimension.
        hidden_dim: Hidden dimension.
        output_dim: Output dimension (default 4 for 4-class).
        dropout: Dropout rate.
    """

    def __init__(
        self,
        input_dim: int = 40,
        hidden_dim: int = 128,
        output_dim: int = NUM_CLASSES,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout * 0.3),
        )
        self.classifier = nn.Linear(hidden_dim // 2, output_dim)
        logger.info("STGATClassifier: input=%d, hidden=%d, output=%d", input_dim, hidden_dim, output_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input features [batch, input_dim].

        Returns:
            Class logits [batch, output_dim].
        """
        return self.classifier(self.encoder(x))


def et_edge_attr(
    edge_attr: Optional[torch.Tensor],
    mask: torch.Tensor,
) -> Optional[torch.Tensor]:
    """Extract edge attributes for a specific edge type."""
    if edge_attr is None or edge_attr.numel() == 0:
        return None
    filtered = edge_attr[mask]
    return filtered if filtered.numel() > 0 else None
