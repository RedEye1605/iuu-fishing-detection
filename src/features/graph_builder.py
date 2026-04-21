"""
Graph builder for Spatiotemporal Graph Attention Network (ST-GAT).

Constructs graphs from vessel trajectories with spatial and temporal edges.
Placeholder for Phase 2 implementation.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class GraphBuilderError(Exception):
    """Base exception for graph building errors."""


class GraphBuilder:
    """Builds ST-GAT graphs from vessel trajectories.

    Args:
        spatial_threshold_km: Maximum distance for spatial edges.
        time_window_hours: Maximum time difference for temporal edges.
    """

    def __init__(
        self,
        spatial_threshold_km: float = 50.0,
        time_window_hours: float = 24.0,
    ) -> None:
        self.spatial_threshold_km = spatial_threshold_km
        self.time_window_hours = time_window_hours

    def build_spatial_graph(
        self,
        points: list[dict[str, Any]],
        vessel_ids: list[str],
    ) -> dict[str, Any]:
        """Build spatial graph connecting nearby points (placeholder).

        Args:
            points: List of trajectory point dicts.
            vessel_ids: Vessel IDs corresponding to each point.

        Returns:
            Graph structure with edge_index, edge_attr, node_features.
        """
        n = len(points)
        logger.info("Building spatial graph with %d nodes...", n)
        return {
            "num_nodes": n,
            "edge_index": np.zeros((2, 0), dtype=np.int64),
            "edge_attr": np.zeros((0, 3), dtype=np.float32),
            "node_features": np.zeros((n, 5), dtype=np.float32),
            "node_types": ["unknown"] * n,
            "is_spatial": True,
        }

    def build_temporal_graph(
        self,
        points: list[dict[str, Any]],
        vessel_ids: list[str],
    ) -> dict[str, Any]:
        """Build temporal graph connecting time-adjacent points (placeholder).

        Args:
            points: List of trajectory point dicts.
            vessel_ids: Vessel IDs corresponding to each point.

        Returns:
            Graph structure with temporal edges.
        """
        n = len(points)
        logger.info("Building temporal graph with %d nodes...", n)
        return {
            "num_nodes": n,
            "edge_index": np.zeros((2, 0), dtype=np.int64),
            "edge_attr": np.zeros((0, 3), dtype=np.float32),
            "node_features": np.zeros((n, 5), dtype=np.float32),
            "node_types": ["unknown"] * n,
            "is_temporal": True,
        }

    def build_stgat_graph(
        self,
        points: list[dict[str, Any]],
        vessel_ids: list[str],
    ) -> dict[str, Any]:
        """Build complete ST-GAT graph combining spatial and temporal edges.

        Args:
            points: List of trajectory point dicts.
            vessel_ids: Vessel IDs corresponding to each point.

        Returns:
            Combined graph with edge_type indicators.
        """
        logger.info("Building complete ST-GAT graph...")
        spatial = self.build_spatial_graph(points, vessel_ids)
        return {
            **spatial,
            "edge_type": np.zeros((0,), dtype=np.int64),
            "num_edge_types": 2,
        }

    def build_graph_from_dataframe(
        self,
        df: pd.DataFrame,
        vessel_id_col: str = "mmsi",
        timestamp_col: str = "timestamp",
        lon_col: str = "lon",
        lat_col: str = "lat",
    ) -> dict[str, Any]:
        """Build graph directly from a DataFrame.

        Args:
            df: DataFrame with trajectory data.
            vessel_id_col: Column for vessel ID.
            timestamp_col: Column for timestamp.
            lon_col: Column for longitude.
            lat_col: Column for latitude.

        Returns:
            Graph structure.

        Raises:
            GraphBuilderError: If the DataFrame is empty.
        """
        if df.empty:
            raise GraphBuilderError("DataFrame is empty")
        points = df.to_dict("records")
        vessel_ids = df[vessel_id_col].tolist()
        return self.build_stgat_graph(points, vessel_ids)
