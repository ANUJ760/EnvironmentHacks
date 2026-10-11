"""Zürich CC0 tree register: locations/species, never measured crown or trunk size."""

import math

from shapely.geometry import Point, mapping, shape

from ecotwin.errors import TwinError

CATALOG = "https://data.stadt-zuerich.ch/dataset/geo_baumkataster"
URL = "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Baumkataster?SERVICE=WFS&REQUEST=GetFeature&VERSION=1.1.0&TYPENAME=baumkataster_baumstandorte&SRSNAME=EPSG:4326&OUTPUTFORMAT=application%2Fvnd.geo%2Bjson"
CROWN_NOTE = "Register crown estimate; may be the provider's 8 m fallback. Not a measurement."


def parse_trees(document, boundary):
    if (
        document.get("type") != "FeatureCollection"
        or not isinstance(document.get("features"), list)
        or len(document["features"]) > 150000
    ):
        raise TwinError(
            "UPSTREAM_PAYLOAD_INVALID", "Bounded municipal tree FeatureCollection required"
        )
    seen, rows, rejected = set(), [], 0
    for item in document["features"]:
        try:
            identifier = str(item["id"])
            if not identifier.startswith("baumkataster_baumstandorte.") or identifier in seen:
                raise ValueError("Unique municipal identifiers required")
            seen.add(identifier)
            geom = shape(item["geometry"])
            if (
                geom.geom_type != "Point"
                or not geom.is_valid
                or not (8.4 <= geom.x <= 8.7 and 47.2 <= geom.y <= 47.5)
            ):
                raise ValueError("WGS84 Zürich point required")
            if not boundary.covers(geom):
                continue
            p = item["properties"]
            crown = p.get("kronendurchmesser")
            crown = float(crown) if crown is not None and not isinstance(crown, bool) else None
            if crown is not None and (not math.isfinite(crown) or not 1 <= crown <= 30):
                crown = None
            rows.append(
                {
                    "provider_feature_id": identifier,
                    "category": "mapped_tree",
                    "geom": geom,
                    "tags": {
                        "category": "mapped_tree",
                        "source": "City of Zürich · CC0 tree register",
                        "source_url": CATALOG,
                        "name": p.get("baumnamedeu") or "Registered tree",
                        "species": p.get("baumnamelat"),
                        "genus": p.get("baumgattunglat"),
                        "planting_year": p.get("pflanzjahr"),
                        "position_quality": p.get("genauigkeit"),
                        "crown_diameter_m": crown,
                        "crown_note": CROWN_NOTE,
                        "natural": "tree",
                        "register_id": identifier,
                    },
                }
            )
        except (KeyError, TypeError, ValueError):
            rejected += 1
    return rows, rejected


def features(rows):
    return [
        {
            "type": "Feature",
            "id": row["provider_feature_id"],
            "geometry": mapping(row["geom"]),
            "properties": row["tags"],
        }
        for row in rows
    ]


def deduplicate_trees(rows, srid=32632, tolerance=2):
    """Prefer register records; suppress nearby OSM records only, not nearby register trees.

    This conservative cross-source matching heuristic is not a surveyed identity match.
    """
    from pyproj import Transformer

    from ecotwin.spatial.geometry import project

    project(Point(8.54, 47.38), srid)  # Validate a metric analysis CRS once.
    transformer = Transformer.from_crs(4326, srid, always_xy=True)

    def metric(geom):
        return Point(*transformer.transform(geom.x, geom.y))

    grid, result, suppressed = {}, [], 0
    for row in rows:
        if row["tags"].get("register_id"):
            p = metric(row["geom"])
            key = (math.floor(p.x / tolerance), math.floor(p.y / tolerance))
            grid.setdefault(key, []).append(p)
            result.append(row)
    for row in rows:
        if row["tags"].get("register_id"):
            continue
        p = metric(row["geom"])
        x, y = math.floor(p.x / tolerance), math.floor(p.y / tolerance)
        if any(
            p.distance(q) <= tolerance
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            for q in grid.get((x + dx, y + dy), [])
        ):
            suppressed += 1
        else:
            result.append(row)
    return result, suppressed
