"""Tests for src.utils.geo_utils."""

from __future__ import annotations

import numpy as np
import pytest

from src.utils.geo_utils import (
    bbox_to_polygon,
    degrees_to_meters,
    distance_haversine,
    meters_to_degrees,
    polygon_to_bbox,
)


class TestBboxPolygon:
    """Round-trip bbox ↔ polygon conversions."""

    def test_bbox_to_polygon_roundtrip(self) -> None:
        bbox = (95.0, -11.0, 141.0, 6.0)
        poly = bbox_to_polygon(bbox)
        result = polygon_to_bbox(poly)
        assert result == pytest.approx(bbox)

    def test_polygon_coordinates_closed(self) -> None:
        poly = bbox_to_polygon((0, 0, 1, 1))
        coords = poly["coordinates"][0]
        assert coords[0] == coords[-1]


class TestHaversine:
    """Haversine distance calculations."""

    def test_same_point_is_zero(self) -> None:
        assert distance_haversine(106.0, -6.0, 106.0, -6.0) == pytest.approx(0.0)

    def test_known_distance(self) -> None:
        # Jakarta (106.8, -6.2) to Surabaya (112.8, -7.3) ~670 km
        d = distance_haversine(106.8, -6.2, 112.8, -7.3)
        assert 650 < d < 700

    def test_symmetry(self) -> None:
        d1 = distance_haversine(100, -5, 120, -5)
        d2 = distance_haversine(120, -5, 100, -5)
        assert d1 == pytest.approx(d2)


class TestDegreeConversions:
    """Meter ↔ degree conversions."""

    def test_meters_to_degrees_positive(self) -> None:
        deg = meters_to_degrees(111_000, 0)
        assert deg > 0

    def test_degrees_to_meters_positive(self) -> None:
        m = degrees_to_meters(1.0, 0)
        assert m > 100_000  # ~111km at equator
