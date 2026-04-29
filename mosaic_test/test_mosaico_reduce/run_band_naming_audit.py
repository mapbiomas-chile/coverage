#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


EXPECTED_ORDER = [
    "blue",
    "green",
    "red",
    "nir",
    "swir1",
    "swir2",
]


def load_band_module(repo_root: Path):
    mod_path = repo_root / "mosaico_reduce" / "modules" / "BandNames.py"
    spec = importlib.util.spec_from_file_location("bandnames", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_product(key: str, new_names: list[str]) -> list[str]:
    issues: list[str] = []
    positions = {}
    for name in EXPECTED_ORDER:
        if name in new_names:
            positions[name] = new_names.index(name)
        else:
            issues.append(f"missing expected band '{name}'")

    if len(positions) == len(EXPECTED_ORDER):
        ordered = [positions[n] for n in EXPECTED_ORDER]
        if ordered != sorted(ordered):
            issues.append(
                "spectral order mismatch "
                f"(observed indices: {ordered}, expected monotonic for {EXPECTED_ORDER})"
            )

    if "pixel_qa" not in new_names:
        issues.append("missing quality band 'pixel_qa'")

    return issues


def main() -> None:
    here = Path(__file__).resolve().parent
    repo_root = here.parent
    band_mod = load_band_module(repo_root)
    band_names = band_mod.BAND_NAMES

    keys_to_check = sorted(
        [
            k
            for k in band_names.keys()
            if (
                "c2" in k
                or k in {"l5", "l7", "l8", "l5toa", "l7toa", "l8toa", "s2", "s2_harmonized"}
            )
        ]
    )

    print("Band naming audit")
    print(f"products_checked={len(keys_to_check)}")

    total_issues = 0
    for key in keys_to_check:
        entry = band_names[key]
        original = entry["bandNames"]
        new_names = entry["newNames"]
        issues = check_product(key, new_names)
        if len(original) != len(new_names):
            issues.append(
                f"length mismatch bandNames={len(original)} newNames={len(new_names)}"
            )

        if issues:
            total_issues += len(issues)
            print(f"[WARN] {key}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"[OK]   {key}")

    print(f"total_issues={total_issues}")
    if total_issues > 0:
        print("Result: review warnings above before publishing to GitHub.")
    else:
        print("Result: naming/spectral-order checks passed for audited products.")


if __name__ == "__main__":
    main()
