"""
Spatiotemporal Graph Attention Network (ST-GAT) for IUU fishing detection.

Architecture overview:
- Spatial GAT layers with edge-type-specific attention
- Temporal attention over time-adjacent points
- Binary classification output (IUU vs. normal)

Placeholder for Phase 3 — will be replaced with full PyTorch Geometric implementation.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class STGATError(Exception):
    """Base exception for ST-GAT model errors."""


class GATLayer(nn.Module):
    """Graph Attention Layer (Velickovic et al., 2018).

    Args:
        in_features: Input feature dimension.
        out_features: Output feature dimension per head.
        num_heads: Number of attention heads.
        dropout: Dropout rate.
        concat: Concatenate heads if True, average if False.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        num_heads: int = 4,
        dropout: float = 0.3,
        concat: bool = True,
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.num_heads = num_heads
        self.concat = concat
        self.dropout_rate = dropout

        self.W = nn.Parameter(torch.zeros(in_features, out_features * num_heads))
        self.a = nn.Parameter(torch.zeros(2 * out_features * num_heads, 1))
        self.leakyrelu = nn.LeakyReLU(0.2)
        self._init_parameters()

    def _init_parameters(self) -> None:
        """Xavier-initialize learnable parameters."""
        nn.init.xavier_uniform_(self.W)
        nn.init.xavier_uniform_(self.a)

    def forward(
        self,
        h: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            h: Node features [num_nodes, in_features].
            edge_index: Edge indices [2, num_edges].
            edge_attr: Optional edge attributes.

        Returns:
            Updated node features.
        """
        Wh = torch.matmul(h, self.W)

        num_edges = edge_index.shape[1]
        if num_edges == 0:
            return F.elu(Wh)

        # Attention scores
        a_input = (Wh[edge_index[0]] * Wh[edge_index[1]]).sum(dim=-1).unsqueeze(-1)
        a_input = a_input.repeat(1, 2)
        e = self.leakyrelu(torch.matmul(a_input, self.a).squeeze(-1))

        if edge_attr is not None and edge_attr.numel() > 0:
            e = e * edge_attr.squeeze(-1)

        attention = F.softmax(e, dim=0)
        attention = F.dropout(attention, p=self.dropout_rate, training=self.training)

        h_prime = torch.zeros_like(Wh)
        for i in range(num_edges):
            src, dst = edge_index[:, i]
            h_prime[dst] += attention[i] * Wh[src]

        return F.elu(h_prime)


class STGAT(nn.Module):
    """Spatiotemporal Graph Attention Network for IUU fishing detection.

    Combines spatial GNN with temporal attention for anomaly detection.

    Args:
        input_dim: Input node feature dimension.
        hidden_dim: Hidden layer dimension.
        output_dim: Output embedding dimension.
        num_edge_types: Number of edge types (spatial, temporal, etc.).
        num_heads: Attention heads per layer.
        dropout: Dropout rate.
        use_temporal: Whether to include temporal attention.
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        output_dim: int = 32,
        num_edge_types: int = 2,
        num_heads: int = 4,
        dropout: float = 0.3,
        use_temporal: bool = True,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_edge_types = num_edge_types
        self.use_temporal = use_temporal

        # Spatial GAT layers per edge type
        self.spatial_gat = nn.ModuleList([
            nn.ModuleDict({
                "attention": GATLayer(
                    input_dim if i == 0 else hidden_dim,
                    hidden_dim, num_heads, dropout,
                ),
                "norm": nn.LayerNorm(hidden_dim),
            })
            for i in range(num_edge_types)
        ])

        # Temporal GAT layers
        if use_temporal:
            self.temporal_gat = nn.ModuleList([
                nn.ModuleDict({
                    "attention": GATLayer(
                        input_dim if i == 0 else hidden_dim,
                        hidden_dim, num_heads, dropout,
                    ),
                    "norm": nn.LayerNorm(hidden_dim),
                })
                for i in range(num_edge_types)
            ])

        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, output_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(output_dim, 1),
            nn.Sigmoid(),
        )

        logger.info(
            "ST-GAT initialized: input=%d, hidden=%d, heads=%d",
            input_dim, hidden_dim, num_heads,
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        temporal_edge_index: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Node features [num_nodes, input_dim].
            edge_index: Spatial edges [2, num_edges].
            edge_type: Edge type per edge [num_edges].
            temporal_edge_index: Temporal edges [2, num_temporal_edges].
            edge_attr: Edge attributes [num_edges, dim].

        Returns:
            Binary predictions [num_nodes, 1].
        """
        x_spatial = self._apply_attention(x, edge_index, edge_type, edge_attr, self.spatial_gat)

        if self.use_temporal and temporal_edge_index is not None:
            x_temporal = self._apply_attention(x, temporal_edge_index, edge_type, edge_attr, self.temporal_gat)
            x = x_spatial + x_temporal
        else:
            x = x_spatial

        return self.classifier(x)

    @staticmethod
    def _apply_attention(
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        edge_attr: Optional[torch.Tensor],
        layers: nn.ModuleList,
    ) -> torch.Tensor:
        """Apply edge-type-specific GAT layers."""
        out = x
        for layer in layers:
            attn = layer["attention"]
            norm = layer["norm"]
            out = norm(attn(out, edge_index, edge_attr))
        return out


class STGATClassifier(nn.Module):
    """Simple MLP classifier for vessel-level IUU prediction.

    Args:
        input_dim: Feature dimension.
        hidden_dim: Hidden layer dimension.
        output_dim: Output dimension (1 for binary).
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        output_dim: int = 1,
    ) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        self.classifier = nn.Linear(hidden_dim, output_dim)
        logger.info("STGATClassifier: input=%d, hidden=%d", input_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input features [batch, input_dim].

        Returns:
            Predictions [batch, output_dim].
        """
        return self.classifier(self.encoder(x))
