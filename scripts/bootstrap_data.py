"""Download, validate, import and publish the real Zürich baseline. Rerunnable, no fake data."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from shapely.geometry import box

from ecotwin.ingestion.air_forecast import fetch_air_forecast, parse_air_forecast
from ecotwin.ingestion.downloader import ProviderClient
from ecotwin.ingestion.municipal_trees import parse_trees
from ecotwin.ingestion.open_meteo import fetch_weather, parse_weather
from ecotwin.storage.base import file_digest, safe_key

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {
    "download.bbbike.org",
    "www.ogd.stadt-zuerich.ch",
    "www.nrcs.usda.gov",
    "research.fs.usda.gov",
    "www.ipcc-nggip.iges.or.jp",
    "directives.nrcs.usda.gov",
    "tiles.openfreemap.org",
}


def atomic_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(document, file, allow_nan=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def validate(path, kind):
    if kind == "pdf":
        with path.open("rb") as file:
            if not file.read(5) == b"%PDF-":
                raise ValueError("Research download is not a PDF")
    elif kind == "pbf":
        import osmium

        reader = osmium.io.Reader(str(path))
        try:
            reader.header()  # Validate the PBF header without a full second parse.
        finally:
            reader.close()
    elif kind == "trees":
        rows, rejected = parse_trees(
            json.loads(path.read_text()), box(8.448, 47.320, 8.625, 47.445)
        )
        if not rows or rejected:
            raise ValueError("Municipal tree register has missing or rejected records")
    elif kind == "tilejson":
        document = json.loads(path.read_text())
        if not document.get("tiles") or any(
            urlsplit(url).hostname != "tiles.openfreemap.org" for url in document["tiles"]
        ):
            raise ValueError("Invalid map tile descriptor")


def download(spec, root, receipt, refresh=False, client=None, sleep=time.sleep):
    target = root / safe_key(spec["path"])
    url = spec["url"]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Download provider is not allowlisted")
    previous = receipt.get(spec["id"])
    if target.is_file() and not refresh:
        digest = file_digest(target)
        if previous and (previous["sha256"] != digest or previous["url"] != url):
            raise ValueError(
                f"Cached {spec['id']} differs from receipt; explicitly use --refresh-static to replace it"
            )
        validate(target, spec["format"])
        print(f"Verified existing {spec['id']}: {target}", flush=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            fd, name = tempfile.mkstemp(dir=target.parent, suffix=".part" + target.suffix)
            temporary = Path(name)
            try:
                with os.fdopen(fd, "wb") as file:
                    owned = client is None
                    transport = client or httpx.Client(
                        timeout=httpx.Timeout(60, connect=10), follow_redirects=False
                    )
                    try:
                        with transport.stream("GET", url) as response:
                            response.raise_for_status()
                            if response.status_code != 200:
                                raise ValueError(
                                    "Download must return full bytes, not a redirect or partial payload"
                                )
                            size = 0
                            for chunk in response.iter_bytes(1024 * 1024):
                                size += len(chunk)
                                if size > spec["max_bytes"]:
                                    raise ValueError("Download exceeds its bounded size")
                                file.write(chunk)
                    finally:
                        if owned:
                            transport.close()
                validate(temporary, spec["format"])
                os.replace(temporary, target)
                break
            except (httpx.HTTPError, ValueError):
                if attempt == 2:
                    raise
                sleep(2**attempt)
            finally:
                temporary.unlink(missing_ok=True)
        digest = file_digest(target)
        print(f"Downloaded {spec['id']}: {target}", flush=True)
    receipt[spec["id"]] = {
        "url": url,
        "path": spec["path"],
        "sha256": digest,
        "bytes": target.stat().st_size,
        "license": spec["license"],
        "verified_at": datetime.now(UTC).isoformat(),
    }
    return target


def forecast(root, city, kind, offline=False):
    path = root / "raw" / ("weather" if kind == "weather" else "air") / f"{city['slug']}.json"
    validator = (
        parse_air_forecast
        if kind == "air_forecast"
        else lambda d: parse_weather(d, datetime.fromisoformat(d["_ecotwin_issued_at"]))
    )
    if path.is_file():
        document = json.loads(path.read_text())
        validator(document)
        acquired = datetime.fromisoformat(document["_ecotwin_issued_at"])
        if offline or datetime.now(UTC) - acquired < timedelta(hours=3):
            print(f"Using cached {kind}: {path}", flush=True)
            return path
    if offline:
        raise ValueError(f"Offline bootstrap requires a cached {kind}")
    west, south, east, north = map(float, city["bbox"].split(","))
    client = ProviderClient()
    try:
        document = (
            fetch_weather(client, (south + north) / 2, (west + east) / 2, 72)
            if kind == "weather"
            else fetch_air_forecast(client, (south + north) / 2, (west + east) / 2)
        )
    finally:
        client.close()
    document["_ecotwin_issued_at"] = datetime.now(UTC).isoformat()
    validator(document)
    atomic_json(path, document)
    print(f"Downloaded {kind}: {path}", flush=True)
    return path


def run_script(name, *arguments):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *map(str, arguments)], check=True, cwd=ROOT
    )


def cli(*arguments):
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from ecotwin.ingestion.cli import main; main()",
            *map(str, arguments),
        ],
        check=True,
        cwd=ROOT,
    )


def bootstrap(args):
    recipe = json.loads(args.recipe.read_text())
    city = recipe["city"]
    root = args.data_dir.resolve()
    if args.bundle_index:
        from ecotwin.config import get_settings
        from ecotwin.storage.factory import object_store
        from scripts.dataset_bundle import restore

        restore(object_store(get_settings()), args.bundle_index, root, args.maps_dir.resolve())
    receipt_path = root / "bootstrap" / "downloads.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
    for spec in recipe["downloads"]:
        if args.offline and not (root / safe_key(spec["path"])).is_file():
            raise ValueError(f"Offline bootstrap requires {spec['path']}")
        download(spec, root, receipt, refresh=args.refresh_static and not args.offline)
        atomic_json(receipt_path, receipt)  # Checkpoint successful downloads for retries.
    pbf = root / "raw/osm/Zuerich.osm.pbf"
    cropped = root / "raw/osm" / f"{city['slug']}.osm.pbf"
    stamp_path = root / "bootstrap" / "processed.json"
    stamp = json.loads(stamp_path.read_text()) if stamp_path.exists() else {}
    source_hash = file_digest(pbf)
    if not cropped.exists() or stamp.get("osm") != {"sha256": source_hash, "bbox": city["bbox"]}:
        fd, name = tempfile.mkstemp(dir=cropped.parent, suffix=".osm.pbf")
        os.close(fd)
        Path(name).unlink()  # osmium requires a new destination, not an empty file.
        try:
            run_script("crop_osm.py", "--bbox", city["bbox"], "--output", name, pbf)
            os.replace(name, cropped)
        finally:
            Path(name).unlink(missing_ok=True)
        stamp["osm"] = {"sha256": source_hash, "bbox": city["bbox"]}
    cover = root / "raw/worldcover" / f"{city['slug']}.tif"
    if not cover.exists() or stamp.get("worldcover") != city["bbox"]:
        if args.offline and not cover.exists():
            raise ValueError("Offline bootstrap needs the WorldCover crop")
        if not args.offline:
            run_script("download_worldcover.py", "--bbox", city["bbox"], "--output", cover)
        stamp["worldcover"] = city["bbox"]
    import numpy as np
    import rasterio

    from ecotwin.models.landcover import CLASS_CODES

    with rasterio.open(cover) as raster:
        if (
            not raster.crs
            or raster.count != 1
            or not set(np.unique(raster.read(1, masked=True).compressed())) <= set(CLASS_CODES)
        ):
            raise ValueError("Invalid classified WorldCover crop")
    atomic_json(stamp_path, stamp)
    weather = forecast(root, city, "weather", args.offline)
    air = forecast(root, city, "air_forecast", args.offline)
    maps = args.maps_dir.resolve()
    maps.mkdir(parents=True, exist_ok=True)
    tree_asset = maps / "zurich-trees.geojson"
    tree_signature = {
        "osm": source_hash,
        "register": receipt["municipal_trees"]["sha256"],
        "exporter": file_digest(ROOT / "scripts/export_city_trees.py"),
    }
    if not tree_asset.exists() or stamp.get("trees") != tree_signature:
        run_script(
            "export_city_trees.py",
            pbf,
            "--municipal",
            root / "raw/zurich-municipal-trees.geojson",
            "--output",
            tree_asset,
        )
        stamp["trees"] = tree_signature
        atomic_json(stamp_path, stamp)
    receipt["weather"] = {
        "path": str(weather.relative_to(root)),
        "sha256": file_digest(weather),
        "url": "https://api.open-meteo.com/v1/forecast",
        "license": "Open-Meteo terms; review commercial use",
    }
    receipt["air_forecast"] = {
        "path": str(air.relative_to(root)),
        "sha256": file_digest(air),
        "url": "https://air-quality-api.open-meteo.com/v1/air-quality",
        "license": "CAMS / Open-Meteo provider terms",
    }
    receipt["worldcover"] = {
        "path": str(cover.relative_to(root)),
        "sha256": file_digest(cover),
        "url": "https://esa-worldcover.org/en/data-access",
        "license": "CC-BY-4.0; ESA WorldCover 2021 v200",
    }
    atomic_json(receipt_path, receipt)
    if args.download_only:
        print("Downloads and visualization asset ready. Database import was not requested.")
        return
    cli(
        "city",
        "create",
        "--city-id",
        city["slug"],
        "--name",
        city["name"],
        "--bbox",
        city["bbox"],
        "--timezone",
        city["timezone"],
    )
    for kind, path in [
        ("osm", cropped),
        ("worldcover", cover),
        ("municipal-trees", root / "raw/zurich-municipal-trees.geojson"),
        ("weather", weather),
        ("air-forecast", air),
    ]:
        from sqlalchemy import select

        from ecotwin.db.models import City, DatasetRevision
        from ecotwin.db.session import session_factory

        with session_factory()() as session:
            imported = session.scalar(
                select(DatasetRevision.id)
                .join(City)
                .where(
                    City.slug == city["slug"],
                    DatasetRevision.kind == kind.replace("-", "_"),
                    DatasetRevision.sha256 == file_digest(path),
                    DatasetRevision.status == "READY",
                )
            )
        if imported:
            print(f"Already imported {kind}; preserving immutable revision {imported}")
        else:
            cli("ingest", kind, "--city", city["slug"], "--file", path)
    if args.with_openaq:
        cli("ingest", "air", "--city", city["slug"])
    cli("datasets", "verify", "--city", city["slug"])
    cli("city", "snapshot", "--city", city["slug"])
    print("Real-data snapshot published. Build/start the frontend after this step.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=ROOT / "config/datasets/zurich.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--maps-dir", type=Path, default=ROOT / "frontend/public/maps")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument(
        "--bundle-index",
        help="Restore an immutable S3 seed bundle before importing; requires S3 runtime configuration",
    )
    parser.add_argument(
        "--refresh-static",
        action="store_true",
        help="Explicitly replace static downloads with current provider data",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cached source bytes only; does not fabricate missing or fresh forecasts",
    )
    parser.add_argument(
        "--with-openaq", action="store_true", help="Requires operator-supplied OPENAQ_API_KEY"
    )
    bootstrap(parser.parse_args())


if __name__ == "__main__":
    main()
