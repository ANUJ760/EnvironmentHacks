"""Plan/upload or restore a verified dataset bundle in private S3. No secrets or DB dump."""

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from ecotwin.storage.base import file_digest, safe_key, verify
from ecotwin.storage.s3 import S3ObjectStore

ROOT = Path(__file__).resolve().parents[1]


def bundle_files(data, maps):
    entries = []
    for family in ("raw", "processed", "manifests", "bootstrap"):
        for source in sorted((data / family).rglob("*")):
            if not source.is_file() or source.name == ".gitkeep" or source.name.endswith(".part"):
                continue
            if source.is_symlink() or not source.resolve().is_relative_to(data.resolve()):
                raise ValueError("Bundle cannot include symlinks outside its dataset root")
            relative = source.relative_to(data).as_posix()
            digest = file_digest(source)
            # Preserve DB-pinned content-addressed keys. Other seed/source files
            # also become immutable content-addressed objects, not mutable latest files.
            pinned = family in {"raw", "processed"} and any(
                re.fullmatch("[a-f0-9]{64}", part) for part in source.relative_to(data).parts
            )
            key = (
                relative
                if pinned or family == "manifests"
                else f"raw/bootstrap/{digest}/{relative}"
            )
            entries.append(
                {
                    "local_path": relative,
                    "key": safe_key(key),
                    "sha256": digest,
                    "bytes": source.stat().st_size,
                    "target": "data",
                }
            )
    tree = maps / "zurich-trees.geojson"
    if not tree.is_file():
        raise ValueError("Generate the tree asset with bootstrap_data.py before creating a bundle")
    digest = file_digest(tree)
    entries.append(
        {
            "local_path": "zurich-trees.geojson",
            "key": f"processed/visualization/{digest}/zurich-trees.geojson",
            "sha256": digest,
            "bytes": tree.stat().st_size,
            "target": "maps",
        }
    )
    return {
        "schema_version": 1,
        "files": entries,
        "note": "Private source bundle only. Restore PostGIS through ingestion or a separately authorized database backup.",
    }


def publish(store, document, data, maps):
    for entry in document["files"]:
        source = (data if entry["target"] == "data" else maps) / entry["local_path"]
        store.put_file(entry["key"], source, entry["sha256"])
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "bundle.json"
        path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))
        digest = file_digest(path)
        key = f"manifests/bundles/{digest}.json"
        store.put_file(key, path, digest)
    return key


def restore(store, index, data, maps):
    if not re.fullmatch(r"manifests/bundles/[a-f0-9]{64}\.json", index):
        raise ValueError("Supply an immutable bundle index key printed by upload")
    path = store.materialize(index, Path(index).stem)
    document = json.loads(path.read_text())
    if document.get("schema_version") != 1 or not 1 <= len(document.get("files", [])) <= 100000:
        raise ValueError("Invalid bounded dataset bundle")
    for entry in document["files"]:
        key = safe_key(entry["key"])
        family = entry["target"]
        if family not in ("data", "maps"):
            raise ValueError("Unsupported bundle target")
        base = data if family == "data" else maps
        relative = entry["local_path"]
        if family == "maps" and relative != "zurich-trees.geojson":
            raise ValueError("Only the generated tree asset can target maps")
        if family == "data" and relative.split("/")[0] not in (
            "raw",
            "processed",
            "manifests",
            "bootstrap",
        ):
            raise ValueError("Only datasets can target the data directory")
        if (
            "\\" in relative
            or relative.startswith("/")
            or any(part in ("", ".", "..") for part in relative.split("/"))
        ):
            raise ValueError("Unsafe bundle path")
        target = base / relative
        if not target.resolve().is_relative_to(base.resolve()):
            raise ValueError("Bundle target escapes its root")
        if target.exists():
            verify(target, entry["sha256"])
            continue
        cached = store.materialize(key, entry["sha256"])
        if cached.stat().st_size != entry["bytes"]:
            raise ValueError("Bundle size mismatch")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=target.parent, suffix=".part")
        try:
            with os.fdopen(fd, "wb") as file, cached.open("rb") as source:
                shutil.copyfileobj(source, file)
            verify(Path(name), entry["sha256"])
            os.link(name, target)  # Never overwrite a user's existing local dataset.
        finally:
            Path(name).unlink(missing_ok=True)
    return len(document["files"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["upload", "restore"])
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--prefix", default="ecotwin/")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--maps-dir", type=Path, default=ROOT / "frontend/public/maps")
    parser.add_argument("--index")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly perform S3 writes or local restoration; otherwise print the plan",
    )
    args = parser.parse_args()
    if args.action == "upload":
        document = bundle_files(args.data_dir, args.maps_dir)
        if not args.apply:
            print(
                json.dumps(
                    {
                        "action": "upload",
                        "bucket": args.bucket,
                        "objects": len(document["files"]),
                        "bytes": sum(entry["bytes"] for entry in document["files"]),
                        "writes_performed": False,
                    }
                )
            )
            return
    elif not args.index:
        parser.error("restore requires --index")
    elif not args.apply:
        print(json.dumps({"action": "restore", "index": args.index, "writes_performed": False}))
        return
    with tempfile.TemporaryDirectory(prefix="ecotwin-bundle-") as cache:
        store = S3ObjectStore(args.bucket, args.region, Path(cache), prefix=args.prefix)
        if args.action == "upload":
            print(
                json.dumps({"bundle_index": publish(store, document, args.data_dir, args.maps_dir)})
            )
        else:
            print(
                json.dumps(
                    {"restored_files": restore(store, args.index, args.data_dir, args.maps_dir)}
                )
            )


if __name__ == "__main__":
    main()
