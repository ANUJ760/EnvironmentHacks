"""Export mapped OSM trees for the whole Zurich visualization, not tree estimates."""

import argparse
import json
from pathlib import Path

import osmium
from shapely.geometry import box, shape

from ecotwin.ingestion.municipal_trees import deduplicate_trees, parse_trees
from ecotwin.ingestion.municipal_trees import features as tree_features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--municipal", type=Path, help="Validated Zürich register GeoJSON; CC0")
    args = parser.parse_args()
    features = []

    class Trees(osmium.SimpleHandler):
        def node(self, node):
            if node.tags.get("natural") != "tree" or not node.location.valid():
                return
            if not (8.448 <= node.lon <= 8.625 and 47.320 <= node.lat <= 47.445):
                return
            features.append(
                {
                    "type": "Feature",
                    "id": node.id,
                    "properties": {
                        "category": "mapped_tree",
                        "source": "OpenStreetMap",
                        "name": node.tags.get("name", "Mapped tree"),
                        "species": node.tags.get("species"),
                        "genus": node.tags.get("genus"),
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(node.lon, 7), round(node.lat, 7)],
                    },
                }
            )

    Trees().apply_file(str(args.source))
    if args.municipal:
        municipal, rejected = parse_trees(
            json.loads(args.municipal.read_text()), box(8.448, 47.320, 8.625, 47.445)
        )
        if rejected:
            raise ValueError(f"Municipal register contains {rejected} rejected records")
        osm = [
            {
                "provider_feature_id": f"osm:node/{f['id']}",
                "tags": f["properties"],
                "geom": shape(f["geometry"]),
            }
            for f in features
        ]
        combined, suppressed = deduplicate_trees(municipal + osm)
        features = tree_features(combined)
        # Keep the browser worker asset compact. Full attributes and source bytes
        # remain in the backend revision; constant provenance is attached on click.
        for feature in features:
            tags = feature["properties"]
            feature["properties"] = {
                key: tags[key]
                for key in ("category", "species", "crown_diameter_m")
                if tags.get(key) is not None
            }
            if tags.get("register_id"):
                feature["properties"]["municipal"] = True
        print(
            f"Register {len(municipal)}; OSM {len(osm)}; suppressed cross-source matches within 2 m: {suppressed}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
    )
    print(f"Exported {len(features)} mapped trees to {args.output}")


if __name__ == "__main__":
    main()
