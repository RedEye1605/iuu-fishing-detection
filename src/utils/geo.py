"""
Geospatial utility functions for IUU fishing detection.
"""

import json
from typing import Optional, Tuple

import numpy as np


def bbox_to_polygon(bbox: Tuple[float, float, float, float]) -> dict:
    """
    Convert bounding box to GeoJSON Polygon.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat)

    Returns:
        GeoJSON Polygon as dict
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]]
    }


def polygon_to_bbox(polygon: dict) -> Tuple[float, float, float, float]:
    """
    Convert GeoJSON Polygon to bounding box.

    Args:
        polygon: GeoJSON Polygon with coordinates

    Returns:
        (min_lon, min_lat, max_lon, max_lat)
    """
    coords = polygon["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def distance_haversine(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    radius_km: float = 6371.0
) -> float:
    """
    Calculate great-circle distance between two points using Haversine formula.

    Args:
        lon1: Longitude of first point
        lat1: Latitude of first point
        lon2: Longitude of second point
        lat2: Latitude of second point
        radius_km: Earth radius in kilometers (default: 6371)

    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    distance_km = radius_km * c

    return distance_km


def point_in_polygon(
    lon: float,
    lat: float,
    polygon: dict,
    strict: bool = True
) -> bool:
    """
    Check if a point is inside a polygon.

    Args:
        lon: Longitude of point
        lat: Latitude of point
        polygon: GeoJSON Polygon
        strict: Use strict winding rule (default: True)

    Returns:
        True if point is inside polygon
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Point, shape
    except ImportError:
        raise ImportError("geopandas and shapely are required for point_in_polygon")

    geom = shape(polygon["geometry"])
    point = Point(lon, lat)

    if strict:
        return geom.contains(point)
    else:
        return geom.contains(point) or geom.touches(point)


def meters_to_degrees(meters: float, lat: float) -> float:
    """
    Convert meters to degrees (longitude) at a given latitude.

    Args:
        meters: Distance in meters
        lat: Latitude (in degrees)

    Returns:
        Approximate degrees of longitude
    """
    km_per_degree = 111.0 * np.cos(np.radians(lat))
    return meters / (km_per_degree * 1000)


def degrees_to_meters(degrees: float, lat: float) -> float:
    """
    Convert degrees (longitude) to meters at a given latitude.

    Args:
        degrees: Distance in degrees
        lat: Latitude (in degrees)

    Returns:
        Distance in meters
    """
    km_per_degree = 111.0 * np.cos(np.radians(lat))
    return degrees * km_per_degree * 1000


def load_polygon_from_json(path: str) -> dict:
    """
    Load a GeoJSON Polygon from file.

    Args:
        path: Path to GeoJSON file

    Returns:
        GeoJSON Polygon as dict
    """
    with open(path, "r") as f:
        data = json.load(f)
    return data


def save_polygon_to_json(polygon: dict, path: str) -> None:
    """
    Save a GeoJSON Polygon to file.

    Args:
        polygon: GeoJSON Polygon dict
        path: Output file path
    """
    output = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": polygon}
    ]}
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
