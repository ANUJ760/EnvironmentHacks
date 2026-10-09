"""Release coverage gates apply to new backend modules; legacy code stays intact."""

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json").read_text())
new_dirs = (
    "ecotwin/api/",
    "ecotwin/auth/",
    "ecotwin/db/",
    "ecotwin/ingestion/",
    "ecotwin/jobs/",
    "ecotwin/models/",
    "ecotwin/simulation/",
    "ecotwin/spatial/",
    "ecotwin/storage/",
    "ecotwin/telemetry/",
)
files = report["files"]


def percentage(names):
    selected = [files[name]["summary"] for name in names]
    covered = sum(item["covered_lines"] + item["covered_branches"] for item in selected)
    total = sum(item["num_statements"] + item["num_branches"] for item in selected)
    return covered / total * 100 if total else 100


new = [
    name
    for name in files
    if name.startswith(new_dirs) or name in {"ecotwin/config.py", "ecotwin/errors.py"}
]
core = [name for name in files if name.startswith(("ecotwin/models/", "ecotwin/auth/"))]
values = {
    "new_backend_statement_and_branch_percent": percentage(new),
    "scientific_and_auth_statement_and_branch_percent": percentage(core),
}
print(json.dumps(values, sort_keys=True))
if (
    values["new_backend_statement_and_branch_percent"] < 85
    or values["scientific_and_auth_statement_and_branch_percent"] < 95
):
    raise SystemExit("Release coverage gate failed")
