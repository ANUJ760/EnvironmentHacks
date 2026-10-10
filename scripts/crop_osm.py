"""Crop a regional PBF while retaining complete way and relation references."""

import argparse
from pathlib import Path

import osmium

from ecotwin.spatial.geometry import analysis_srid, bbox_geometry, validate_area


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    boundary = bbox_geometry(args.bbox)
    validate_area(boundary, analysis_srid(boundary))
    west, south, east, north = boundary.bounds
    selected_ways = set()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with osmium.BackReferenceWriter(args.output, args.source, relation_depth=3) as writer:
        for obj in osmium.FileProcessor(args.source).with_locations():
            if obj.is_node():
                if west <= obj.lon <= east and south <= obj.lat <= north:
                    writer.add(obj)
            elif obj.is_way():
                points = [(node.lon, node.lat) for node in obj.nodes if node.location.valid()]
                if points and (
                    min(point[0] for point in points) <= east
                    and max(point[0] for point in points) >= west
                    and min(point[1] for point in points) <= north
                    and max(point[1] for point in points) >= south
                ):
                    selected_ways.add(obj.id)
                    writer.add(obj)
            elif obj.is_relation() and obj.tags.get("type") == "multipolygon":
                if any(
                    member.type == "w" and member.ref in selected_ways for member in obj.members
                ):
                    writer.add(obj)
    print(f"Prepared reference-complete study-area PBF at {args.output}")


if __name__ == "__main__":
    main()
