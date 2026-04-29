#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    here = Path(__file__).resolve().parent
    profile_path = here / "test_profile.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile: {profile_path}")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    base = here.parent / "mosaico_reduce"
    runner = base / "run_pipeline.py"

    if not runner.exists():
        raise FileNotFoundError(f"Missing runner: {runner}")

    cmd = [
        sys.executable,
        str(runner),
        "--gpkg",
        str(profile.get("gpkg", "../../inputs/gpk/Muestra_Lagogpk.gpkg")),
        "--tile",
        str(profile.get("tile", "SJ-18-X-B")),
        "--project",
        str(profile.get("project", "mapbiomas-chile")),
        "--reduced",
        str(profile.get("reduced", "1")),
        "--export-tag",
        str(profile.get("export_tag", "github-test-001")),
    ]

    max_jobs = profile.get("max_jobs")
    if isinstance(max_jobs, int) and max_jobs > 0:
        cmd.extend(["--max-jobs", str(max_jobs)])

    if bool(profile.get("skip_task_guard", True)):
        cmd.append("--skip-task-guard")

    print("Executing test flow:")
    print(" ".join(cmd))
    completed = subprocess.run(cmd, check=False, cwd=str(base))
    sys.exit(completed.returncode)


if __name__ == "__main__":
    main()
