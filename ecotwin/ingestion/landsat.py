"""Optional offline Collection-2 Level-2 surface-temperature import.
Metadata is operator supplied from the downloaded product, including official
scale/offset, scene ID, acquisition time, license and QA_PIXEL raster path.
"""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

from ecotwin.errors import TwinError


def surface_temperature(scene_dir: Path, metadata: dict, boundary):
    required = {
        "scene_id",
        "acquired_at",
        "st_band",
        "qa_pixel_band",
        "scale_factor",
        "add_offset",
        "source_url",
        "source_license",
        "attribution",
    }
    if not required <= metadata.keys():
        raise TwinError(
            "INSUFFICIENT_INPUT_DATA",
            "Landsat scene metadata requires scale, offset, QA mask, capture time and license",
        )
    root = scene_dir.resolve()
    paths = [root / metadata["st_band"], root / metadata["qa_pixel_band"]]
    if any(not path.resolve().is_relative_to(root) or not path.is_file() for path in paths):
        raise TwinError(
            "LAYER_UNAVAILABLE", "Downloaded scene temperature and QA_PIXEL files are required"
        )
    with rasterio.open(paths[0]) as temperature, rasterio.open(paths[1]) as qa:
        if (
            temperature.crs != qa.crs
            or temperature.transform != qa.transform
            or temperature.shape != qa.shape
        ):
            raise TwinError(
                "UPSTREAM_PAYLOAD_INVALID", "Landsat temperature and QA grids must align"
            )
        from pyproj import Transformer
        from shapely import transform

        projected = transform(
            boundary,
            Transformer.from_crs(4326, temperature.crs, always_xy=True).transform,
            interleaved=False,
        )
        st, affine = mask(temperature, [mapping(projected)], crop=True, filled=False)
        quality, _ = mask(qa, [mapping(projected)], crop=True, filled=False)
        # Collection 2 QA_PIXEL: fill, dilated cloud, cirrus, cloud, cloud shadow, snow.
        invalid = (quality.data[0].astype("uint16") & 0b111111) != 0
        values = st[0].astype("float64") * float(metadata["scale_factor"]) + float(
            metadata["add_offset"]
        )
        values.mask = np.ma.getmaskarray(values) | invalid | (st.data[0] == 0)
        if values.count() == 0:
            raise TwinError("LAYER_UNAVAILABLE", "No cloud-free surface-temperature pixels")
        return values, affine, temperature.crs
