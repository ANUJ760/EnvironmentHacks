from shapely.ops import unary_union

from ecotwin.errors import TwinError
from ecotwin.models.landcover import apply_edits
from ecotwin.spatial.geometry import geometry


def validate_edits(boundary, srid, pieces, edits, buildings=None):
    solar = []
    for edit in edits:
        key = (
            "polygon_geojson"
            if edit["edit_type"] == "LAND_COVER_RECLASSIFY"
            else "footprint_geojson"
        )
        if edit["edit_type"] == "WASTE_ROUTING_OVERRIDE":
            continue
        target = geometry(edit[key])
        if not boundary.covers(target):
            raise TwinError(
                "OUTSIDE_STUDY_BOUNDARY", "Edit target must be inside the city boundary"
            )
        if edit["edit_type"] == "SOLAR_PV_INSTALL":
            if edit["panel_tilt_deg"] != 0:
                raise TwinError(
                    "MODEL_INPUT_UNSUPPORTED", "Only horizontal unshaded PV screening is supported"
                )
            if any(target.intersection(other).area > 0 for other in solar):
                raise TwinError("MODEL_INPUT_UNSUPPORTED", "PV footprints may not overlap")
            if not buildings or not unary_union(buildings).covers(target):
                raise TwinError(
                    "INSUFFICIENT_INPUT_DATA",
                    "PV footprint must be covered by mapped building geometry",
                )
            solar.append(target)
    apply_edits(pieces, edits, srid)
