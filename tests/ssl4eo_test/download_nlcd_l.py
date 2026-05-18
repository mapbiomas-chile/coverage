#!/usr/bin/env python3
"""
Download NLCD-L benchmark (SSL4EO-L evaluation set): Landsat oli_sr + NLCD masks.

Downloads two archives (~9.4 GB compressed) via TorchGeo:
  - ssl4eo_l_oli_sr_benchmark.tar.gz   (~9.0 GB)
  - ssl4eo_l_oli_nlcd.tar.gz           (~336 MB)

Usage:
    ./venv/bin/python download_nlcd_l.py
    ./venv/bin/python download_nlcd_l.py --root data/ssl4eo_nlcd --verify-samples 3
    ./venv/bin/python download_nlcd_l.py --checksum   # slower, verifies MD5

After download, extracted layout under --root:
    ssl4eo_l_oli_sr_benchmark/.../all_bands.tif
    ssl4eo_l_oli_nlcd/.../nlcd_2019.tif
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from torchgeo.datasets import SSL4EOLBenchmark


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download NLCD-L (oli_sr) via TorchGeo")
    p.add_argument(
        "--root",
        type=Path,
        default=Path("data/ssl4eo_nlcd"),
        help="Directory for tarballs and extracted tiles (default: data/ssl4eo_nlcd)",
    )
    p.add_argument(
        "--sensor",
        default="oli_sr",
        choices=SSL4EOLBenchmark.valid_sensors,
        help="Landsat product (default: oli_sr = L8/L9 SR, 7 bands)",
    )
    p.add_argument(
        "--product",
        default="nlcd",
        choices=SSL4EOLBenchmark.valid_products,
        help="Label product (default: nlcd)",
    )
    p.add_argument(
        "--checksum",
        action="store_true",
        help="Verify MD5 after download (slower)",
    )
    p.add_argument(
        "--verify-samples",
        type=int,
        default=3,
        metavar="N",
        help="Load N train samples after download to print shapes/stats (0=skip)",
    )
    return p.parse_args()


def download_split(
    root: Path,
    sensor: str,
    product: str,
    split: str,
    checksum: bool,
) -> SSL4EOLBenchmark:
    """Trigger download/extract on first access; return dataset for split."""
    print(f"[download] split={split}  sensor={sensor}  product={product}  root={root}")
    return SSL4EOLBenchmark(
        root=str(root),
        sensor=sensor,
        product=product,
        split=split,
        download=True,
        checksum=checksum,
    )


def verify_samples(ds: SSL4EOLBenchmark, n: int) -> None:
    print(f"\n[verify] dataset length (this split): {len(ds)}")
    print(f"[verify] RGB band indices for plot: {ds.rgb_indices[ds.sensor]}")
    n = min(n, len(ds))
    for i in range(n):
        sample = ds[i]
        img, mask = sample["image"], sample["mask"]
        uniq = torch.unique(mask)
        print(
            f"  sample[{i}]  image={tuple(img.shape)}  mask={tuple(mask.shape)}  "
            f"dtype img={img.dtype} mask={mask.dtype}  "
            f"classes in mask (ordinal): {uniq.tolist()}  "
            f"min/max band0: {img[0].min():.1f}/{img[0].max():.1f}"
        )


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    print("=== NLCD-L download (TorchGeo SSL4EOLBenchmark) ===")
    print(f"Target folder: {root}")
    print("Expected download size (oli_sr + nlcd): ~9.4 GB compressed")
    print("Disk after extract: ~10-12 GB (keep or delete .tar.gz to save space)\n")

    # First call downloads both image + mask archives and extracts them.
    train_ds = download_split(
        root, args.sensor, args.product, "train", args.checksum
    )

    # Val/test only build index; data already on disk.
    val_ds = SSL4EOLBenchmark(
        root=str(root),
        sensor=args.sensor,
        product=args.product,
        split="val",
        download=False,
    )
    test_ds = SSL4EOLBenchmark(
        root=str(root),
        sensor=args.sensor,
        product=args.product,
        split="test",
        download=False,
    )

    print("\n[info] splits:")
    print(f"  train: {len(train_ds)}")
    print(f"  val:   {len(val_ds)}")
    print(f"  test:  {len(test_ds)}")

    tarballs = list(root.glob("*.tar.gz"))
    if tarballs:
        print("\n[info] archives in root:")
        for t in sorted(tarballs):
            print(f"  {t.name}  ({t.stat().st_size / 1e9:.2f} GB)")

    if args.verify_samples > 0:
        verify_samples(train_ds, args.verify_samples)

    print("\n=== Done ===")
    print("Fine-tune / explore with:")
    print(f"  from torchgeo.datasets import SSL4EOLBenchmark")
    print(f"  ds = SSL4EOLBenchmark(root='{root}', sensor='{args.sensor}', "
          f"product='{args.product}', split='train')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
