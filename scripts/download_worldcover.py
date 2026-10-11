"""Download only native WorldCover pixels intersecting a bounded study area.

GeoTIFF HTTP range reads avoid downloading the entire regional tile. The output
retains the provider's original classes, CRS and resolution for normal ingestion.
"""

import argparse
import math
from contextlib import ExitStack
from pathlib import Path

import rasterio
from rasterio.merge import merge
from rasterio.windows import Window, from_bounds

from ecotwin.ingestion.worldcover import tile_urls
from ecotwin.spatial.geometry import analysis_srid, bbox_geometry, validate_area


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    boundary = bbox_geometry(args.bbox)
    validate_area(boundary, analysis_srid(boundary))
    urls = tile_urls(boundary)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(url)) for url in urls]
        # Align outward to native pixels so the crop covers the entire boundary.
        first = sources[0]
        raw = from_bounds(*boundary.bounds, transform=first.transform)
        left, top = math.floor(raw.col_off), math.floor(raw.row_off)
        right = math.ceil(raw.col_off + raw.width)
        bottom = math.ceil(raw.row_off + raw.height)
        if (right - left) * (bottom - top) > 2_000_000:
            raise SystemExit("Bounded crop exceeds the supported cell limit")
        bounds = rasterio.windows.bounds(
            Window(left, top, right - left, bottom - top), first.transform
        )
        mosaic, affine = merge(sources, bounds=bounds, nodata=0)
        profile = first.profile.copy()
        profile.update(
            height=mosaic.shape[1], width=mosaic.shape[2], transform=affine, compress="deflate"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(args.output, "w", **profile) as destination:
            destination.write(mosaic)
            destination.update_tags(
                source_urls=" ".join(urls),
                attribution="ESA WorldCover 2021 v200; CC BY 4.0",
            )
    print(f"Downloaded native-resolution WorldCover crop to {args.output}")
    print("Source: " + " ".join(urls))


if __name__ == "__main__":
    main()
