#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    here = Path(__file__).resolve().parent
    base = here.parent / "mosaico_reduce"
    profile_path = here / "diagnosis_profile.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile: {profile_path}")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    suffix = str(profile.get("suffix", ""))
    plot_output = str(profile.get("plot_output", "../outputs/ndwi_muestra_lago_timeseries.png"))

    report_script = base / "ndwi_incongruence_report.py"
    plot_script = base / "plot_ndwi_gpkg.py"
    if not report_script.exists():
        raise FileNotFoundError(f"Missing script: {report_script}")
    if not plot_script.exists():
        raise FileNotFoundError(f"Missing script: {plot_script}")

    print("[1/2] Running numeric inconsistency report...")
    r1 = subprocess.run([sys.executable, str(report_script)], check=False, cwd=str(base))
    if r1.returncode != 0:
        sys.exit(r1.returncode)

    print("[2/2] Running NDWI plot for diagnosis...")
    r2 = subprocess.run(
        [
            sys.executable,
            str(plot_script),
            "--suffix",
            suffix,
            "--output",
            plot_output,
        ],
        check=False,
        cwd=str(base),
    )
    sys.exit(r2.returncode)


if __name__ == "__main__":
    main()
