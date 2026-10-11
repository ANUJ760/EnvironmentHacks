import json
from pathlib import Path

import httpx
import pytest

from ecotwin.storage.local import LocalObjectStore
from scripts import bootstrap_data
from scripts.aws_deploy import task_request
from scripts.dataset_bundle import bundle_files, publish, restore


def spec():
    return {
        "id": "paper",
        "path": "raw/research/paper.pdf",
        "url": "https://www.nrcs.usda.gov/paper.pdf",
        "format": "pdf",
        "max_bytes": 1024,
        "license": "Test fixture",
    }


def test_download_is_atomic_validated_and_checkpointed(tmp_path):
    calls = []

    def serve(request):
        calls.append(request.url)
        return httpx.Response(200, content=b"%PDF-fixture")

    client = httpx.Client(transport=httpx.MockTransport(serve))
    receipt = {}
    target = bootstrap_data.download(spec(), tmp_path, receipt, client=client)
    assert target.read_bytes() == b"%PDF-fixture"
    assert len(receipt["paper"]["sha256"]) == 64
    bootstrap_data.download(spec(), tmp_path, receipt, client=client)
    assert len(calls) == 1
    target.write_bytes(b"%PDF-tampered")
    with pytest.raises(ValueError, match="receipt"):
        bootstrap_data.download(spec(), tmp_path, receipt, client=client)


@pytest.mark.parametrize("content", [b"<html>not a PDF</html>", b"%PDF-" + b"a" * 1024])
def test_invalid_payload_never_replaces_an_existing_download(tmp_path, content):
    target = tmp_path / spec()["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF-existing")
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content))
    )
    with pytest.raises(ValueError):
        bootstrap_data.download(
            spec(), tmp_path, {}, refresh=True, client=client, sleep=lambda _: None
        )
    assert target.read_bytes() == b"%PDF-existing"
    assert not list(tmp_path.rglob("*.part*"))


def test_urls_and_paths_are_constrained(tmp_path):
    unsafe = {**spec(), "url": "http://169.254.169.254/metadata"}
    with pytest.raises(ValueError):
        bootstrap_data.download(unsafe, tmp_path, {})
    unsafe = {**spec(), "path": "raw/../../.env"}
    with pytest.raises(Exception):
        bootstrap_data.download(unsafe, tmp_path, {})


def test_private_bundle_preserves_pinned_keys_and_restores_without_overwriting(tmp_path):
    data, maps = tmp_path / "data", tmp_path / "maps"
    maps.mkdir()
    (maps / "zurich-trees.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    source = data / "raw/osm/source.pbf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fixture-source")
    (data / ".env").write_text("secret-not-for-upload")
    document = bundle_files(data, maps)
    assert len(document["files"]) == 2
    assert all(".env" not in entry["local_path"] for entry in document["files"])
    store = LocalObjectStore(tmp_path / "objects")
    index = publish(store, document, data, maps)
    restored, restored_maps = tmp_path / "restored", tmp_path / "restored-maps"
    assert restore(store, index, restored, restored_maps) == 2
    assert (restored / "raw/osm/source.pbf").read_bytes() == source.read_bytes()
    assert restore(store, index, restored, restored_maps) == 2
    (restored / "raw/osm/source.pbf").write_bytes(b"changed")
    with pytest.raises(Exception):
        restore(store, index, restored, restored_maps)


def test_ecs_bootstrap_uses_private_network_and_verified_bundle():
    outputs = {
        "ecs_cluster_name": "test",
        "ingest_task_definition_arn": "ingest",
        "migration_task_definition_arn": "migrate",
        "private_subnet_ids": ["private"],
        "ingestion_security_group_id": "ingest-sg",
        "migration_security_group_id": "migration-sg",
    }
    index = "manifests/bundles/" + "a" * 64 + ".json"
    request = task_request(outputs, "bootstrap", index)
    assert request["networkConfiguration"]["awsvpcConfiguration"]["assignPublicIp"] == "DISABLED"
    assert request["overrides"]["containerOverrides"][0]["command"][-2:] == [
        "--bundle-index",
        index,
    ]
    with pytest.raises(ValueError):
        task_request(outputs, "bootstrap", "../../.env")


def test_recipe_covers_primary_data_and_declares_conditional_inputs():
    recipe = json.loads(
        (Path(__file__).resolve().parents[2] / "config/datasets/zurich.json").read_text()
    )
    assert {"osm", "municipal_trees", "nrcs", "jenkins", "ipcc", "nrcs_forest", "map_manifest"} <= {
        item["id"] for item in recipe["downloads"]
    }
    assert {"aerial", "vector_tiles", "glyphs"} == {item["id"] for item in recipe["streamed"]}
    assert {"openaq", "waste_facilities", "landsat", "ollama"} == {
        item["id"] for item in recipe["optional"]
    }
