"""Clone-to-run harness; Python stdlib + Docker Compose v2 only. No host ML install."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "download", "refresh", "down", "status"])
    parser.add_argument(
        "--with-ollama",
        action="store_true",
        help="Explicitly download the optional ~1 GB Qwen model",
    )
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    env["ECOTWIN_BOOTSTRAP_UID"] = str(os.getuid() if hasattr(os, "getuid") else 10001)
    env["ECOTWIN_BOOTSTRAP_GID"] = str(os.getgid() if hasattr(os, "getgid") else 10001)

    def run(*command):
        print("+ " + " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)

    run(sys.executable, str(ROOT / "scripts/setup_local.py"))
    data = (ROOT / env.get("ECOTWIN_DATA_PATH", "data")).resolve()
    maps = (ROOT / env.get("ECOTWIN_MAPS_PATH", "frontend/public/maps")).resolve()
    for path in [data, maps, data / "cache/maps"]:
        path.mkdir(parents=True, exist_ok=True)
    (data / "cache/maps").chmod(
        0o777
    )  # Public disposable cache; frontend UID differs from host UID.
    compose = ["docker", "compose"]
    if args.action == "down":
        run(*compose, "--profile", "ai", "down")  # Never --volumes; data/models stay recoverable.
        return
    if args.action == "status":
        run(*compose, "--profile", "ai", "ps")
        return
    run(*compose, "--profile", "setup", "build", "bootstrap")
    if args.action != "download":
        run(*compose, "up", "-d", "db")
    extra = ["--offline"] if args.offline else []
    if args.action == "refresh":
        extra += ["--refresh-static"]
    if args.action == "download":
        # No DB is required to obtain all automatically available primary datasets.
        run(
            *compose,
            "--profile",
            "setup",
            "run",
            "--rm",
            "--no-deps",
            "bootstrap",
            "python",
            "scripts/bootstrap_data.py",
            "--download-only",
            "--data-dir",
            "/app/data",
            "--maps-dir",
            "/app/frontend/public/maps",
            *extra,
        )
        return
    run(
        *compose,
        "--profile",
        "setup",
        "run",
        "--rm",
        "bootstrap",
        "python",
        "scripts/bootstrap_data.py",
        "--data-dir",
        "/app/data",
        "--maps-dir",
        "/app/frontend/public/maps",
        *extra,
    )
    if args.with_ollama:
        run(*compose, "--profile", "ai", "up", "-d", "ollama")
        run(*compose, "--profile", "ai", "run", "--rm", "ollama-pull")
    # The ignored tree asset must exist before the standalone frontend is built.
    run(*compose, "build", "frontend")
    run(*compose, "up", "-d", "--wait", "api", "worker", "frontend")
    print("Planner ready at http://localhost:" + env.get("ECOTWIN_FRONTEND_PORT", "3000"))


if __name__ == "__main__":
    main()
