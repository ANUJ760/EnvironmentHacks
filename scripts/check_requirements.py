"""Ensure the pip runtime export matches the authoritative frozen uv lock."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized(text):
    return "\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


if __name__ == "__main__":
    exported = subprocess.check_output(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
        ],
        cwd=ROOT,
        text=True,
    )
    if normalized(exported) != normalized((ROOT / "requirements.txt").read_text()):
        raise SystemExit(
            "requirements.txt is stale: regenerate with uv export --frozen --no-dev --no-emit-project"
        )
    print("requirements.txt matches uv.lock")
