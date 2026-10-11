"""Check exported manifests without exposing source bytes or credentials."""

import sys
from pathlib import Path

from ecotwin.storage.manifest import DatasetManifest

failed = []
for path in Path(sys.argv[1] if len(sys.argv) > 1 else "data/manifests").glob("*.json"):
    if path.name.endswith(".schema.json"):
        continue
    try:
        DatasetManifest.model_validate_json(path.read_text())
    except Exception:
        failed.append(str(path))
if failed:
    raise SystemExit("Invalid source provenance: " + ", ".join(failed))
print("Manifest license/schema checks passed; operator must verify redistribution rights.")
