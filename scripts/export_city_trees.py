"""Export mapped OSM trees for the whole Zurich visualization, not tree estimates."""

import argparse
import json
from pathlib import Path

import osmium


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
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
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(node.lon, 7), round(node.lat, 7)],
                    },
                }
            )

    Trees().apply_file(str(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
    )
    print(f"Exported {len(features)} mapped trees to {args.output}")


if __name__ == "__main__":
    main()
