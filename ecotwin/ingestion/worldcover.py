"""Clip native raster cells without treating counts as physical area."""

import math
from pathlib import Path

import rasterio
from pyproj import Transformer
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely.geometry import Polygon
from shapely.ops import transform, unary_union

from ecotwin.errors import TwinError
from ecotwin.models.landcover import CLASS_CODES
from ecotwin.spatial.geometry import project


def intersecting_tiles(boundary):
    w, s, e, n = boundary.bounds
    return [
        f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
        for lat in range(math.floor(s / 3) * 3, math.ceil(n / 3) * 3, 3)
        for lon in range(math.floor(w / 3) * 3, math.ceil(e / 3) * 3, 3)
    ]


def tile_urls(boundary):
    return [
        f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        for tile in intersecting_tiles(boundary)
    ]


def raster_cells(path: Path, boundary, srid, limit=2_000_000):
    cells = []
    unknown = 0.0
    with rasterio.open(path) as source:
        if not source.crs or source.count != 1:
            raise TwinError(
                "UPSTREAM_PAYLOAD_INVALID", "WorldCover requires a single classified band and CRS"
            )
        bounds = transform_bounds("EPSG:4326", source.crs, *boundary.bounds)
        try:
            window = (
                from_bounds(*bounds, transform=source.transform)
                .round_offsets()
                .round_lengths()
                .intersection(rasterio.windows.Window(0, 0, source.width, source.height))
            )
        except rasterio.errors.WindowError as exc:
            raise TwinError(
                "INSUFFICIENT_INPUT_DATA", "WorldCover tile does not intersect city"
            ) from exc
        if window.width * window.height > limit:
            raise TwinError("MODEL_INPUT_UNSUPPORTED", "Raster exceeds 2 million bounded cells")
        band = source.read(1, window=window, masked=True)
        transformer = Transformer.from_crs(source.crs, 4326, always_xy=True)
        affine = source.window_transform(window)
        coverage = []
        for row in range(band.shape[0]):
            for col in range(band.shape[1]):
                corners = [
                    affine * (col, row),
                    affine * (col + 1, row),
                    affine * (col + 1, row + 1),
                    affine * (col, row + 1),
                ]
                geom = transform(transformer.transform, Polygon(corners)).intersection(boundary)
                if geom.is_empty:
                    continue
                area = project(geom, srid).area
                if area <= 0:
                    continue
                value = band[row, col]
                if (
                    bool(band.mask[row, col])
                    if hasattr(band.mask, "shape") and band.mask.shape
                    else bool(band.mask)
                ):
                    unknown += area
                    continue
                code = int(value)
                if code not in CLASS_CODES:
                    raise TwinError("UPSTREAM_PAYLOAD_INVALID", "Unknown WorldCover class code")
                polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
                for part in polygons:
                    if part.geom_type != "Polygon" or part.is_empty:
                        continue
                    cells.append(
                        {
                            "cell_x": int(window.col_off) + col,
                            "cell_y": int(window.row_off) + row,
                            "class_code": code,
                            "area_m2": project(part, srid).area,
                            "geom": part,
                        }
                    )
                    coverage.append(part)
        if not cells:
            raise TwinError("INSUFFICIENT_INPUT_DATA", "Tile has no valid classified coverage")
        union = unary_union(coverage)
        total = sum(cell["area_m2"] for cell in cells)
        if not math.isclose(total, project(union, srid).area, rel_tol=0.005, abs_tol=0.01):
            raise TwinError(
                "UPSTREAM_PAYLOAD_INVALID", "WorldCover cells overlap or area closure failed"
            )
        return (
            cells,
            union,
            {
                "reference_year": 2021,
                "version": "v200",
                "nodata_area_m2": unknown,
                "valid_area_m2": total,
                "crs": str(source.crs),
            },
        )
