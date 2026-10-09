"""Bounded WGS84 inputs; metric calculations only in projected CRS."""

import json
import math
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from ecotwin.errors import TwinError


def geometry(document: dict[str, Any], polygon: bool = True) -> BaseGeometry:
    if len(json.dumps(document)) > 500_000:
        raise TwinError("INVALID_GEOMETRY", "Geometry exceeds size limit")
    try:
        geom = shape(document)
        if geom.is_empty or not geom.is_valid or geom.has_z:
            raise ValueError("Invalid topology or dimensions")
        if polygon and geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Polygon required")
        w, s, e, n = geom.bounds
        if not all(math.isfinite(v) for v in (w, s, e, n)) or not (
            -180 <= w <= e <= 180 and -90 <= s <= n <= 90
        ):
            raise ValueError("Coordinates outside WGS84")
        if e - w > 180:
            raise ValueError("Antimeridian crossing requires a split study area")
        from shapely import get_num_coordinates

        if get_num_coordinates(geom) > 10000:
            raise ValueError("Vertex limit exceeded")
        return geom
    except (ValueError, TypeError, KeyError) as exc:
        raise TwinError(
            "INVALID_GEOMETRY", "Valid bounded two-dimensional WGS84 geometry required"
        ) from exc


def analysis_srid(geom: BaseGeometry) -> int:
    lon, lat = geom.centroid.x, geom.centroid.y
    if not -80 <= lat <= 84:
        raise TwinError(
            "MODEL_INPUT_UNSUPPORTED", "Polar study areas require an analyst-selected CRS"
        )
    return (32600 if lat >= 0 else 32700) + min(60, int((lon + 180) // 6) + 1)


def project(geom: BaseGeometry, srid: int) -> BaseGeometry:
    crs = CRS.from_epsg(srid)
    if not crs.is_projected or any(axis.unit_name != "metre" for axis in crs.axis_info):
        raise TwinError("INVALID_GEOMETRY", "Analysis CRS must be projected in meters")
    return transform(Transformer.from_crs(4326, srid, always_xy=True).transform, geom)


def validate_area(geom: BaseGeometry, srid: int, maximum_km2: float = 25) -> float:
    area = project(geom, srid).area
    if not 0 < area <= maximum_km2 * 1e6:
        raise TwinError("INVALID_GEOMETRY", "Study area must be positive and at most 25 km²")
    return area


def bbox_geometry(value: str) -> BaseGeometry:
    try:
        w, s, e, n = map(float, value.split(","))
        if not w < e or not s < n:
            raise ValueError("Invalid extent")
        from shapely.geometry import mapping

        return geometry(dict(mapping(box(w, s, e, n))))
    except ValueError as exc:
        raise TwinError("INVALID_GEOMETRY", "bbox requires west,south,east,north") from exc
