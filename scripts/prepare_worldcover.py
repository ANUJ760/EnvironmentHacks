"""Offline bounded mosaic, retaining the original WorldCover category raster."""

import argparse
from contextlib import ExitStack
from pathlib import Path

import rasterio
from rasterio.merge import merge

from ecotwin.spatial.geometry import analysis_srid, bbox_geometry, validate_area

parser = argparse.ArgumentParser()
parser.add_argument("--bbox", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("tiles", nargs="+", type=Path)
args = parser.parse_args()
boundary = bbox_geometry(args.bbox)
validate_area(boundary, analysis_srid(boundary))
with ExitStack() as stack:
    sources = [stack.enter_context(rasterio.open(p)) for p in args.tiles]
    if any(str(source.crs) != "EPSG:4326" or source.count != 1 for source in sources):
        raise SystemExit("Expected native WorldCover WGS84 single-band tiles")
    mosaic, affine = merge(sources, bounds=boundary.bounds, nodata=0)
    if mosaic.size > 2_000_000:
        raise SystemExit("Bounded mosaic exceeds cell limit")
    profile = sources[0].profile
    profile.update(
        height=mosaic.shape[1], width=mosaic.shape[2], transform=affine, compress="deflate"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.output, "w", **profile) as destination:
        destination.write(mosaic)
print("Prepared native-resolution city crop; retain original tiles and licenses.")
