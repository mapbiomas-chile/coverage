"""Pick one representative band per cluster (unsupervised)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def select_central_representatives(
    corr_abs: np.ndarray,
    labels: np.ndarray,
) -> pd.DataFrame:
    """
    For each cluster, pick the band with highest mean |r| to other members.

    Tie-break: smallest band_index. Singletons: the only member (mean_abs_r = 1.0).
    """
    if corr_abs.shape[0] != corr_abs.shape[1]:
        raise ValueError("corr_abs must be square")
    if labels.shape[0] != corr_abs.shape[0]:
        raise ValueError("labels length must match n_bands")

    rows = []
    for cid in sorted(int(x) for x in np.unique(labels)):
        members = np.where(labels == cid)[0].astype(int)
        members = np.sort(members)
        size = int(members.size)
        if size == 1:
            rep = int(members[0])
            mean_r = 1.0
        else:
            sub = corr_abs[np.ix_(members, members)].astype(np.float64)
            # mean |r| to others: exclude self (diagonal = 1)
            mean_to_others = (sub.sum(axis=1) - 1.0) / (size - 1)
            best_val = float(mean_to_others.max())
            tied = members[np.isclose(mean_to_others, best_val)]
            rep = int(tied.min())  # tie-break: min band index
            mean_r = best_val
        rows.append(
            {
                "cluster_id": cid,
                "size": size,
                "representative": rep,
                "mean_abs_r_to_others": mean_r,
                "members": [int(x) for x in members.tolist()],
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["size", "cluster_id"], ascending=[False, True]).reset_index(drop=True)
    return df


def save_representatives(
    reps: pd.DataFrame,
    out_dir: str | Path,
    *,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reps_sorted = sorted(int(x) for x in reps["representative"].tolist())
    detail_path = out_dir / "representatives_detail.json"
    list_path = out_dir / "representatives.json"
    csv_path = out_dir / "representatives.csv"
    summary_path = out_dir / "representatives_summary.json"

    detail = reps.to_dict(orient="records")
    detail_path.write_text(json.dumps(detail, indent=2) + "\n")

    payload = {
        "method": "central_mean_abs_r",
        "tie_break": "min_band_index",
        "n_representatives": len(reps_sorted),
        "representatives": reps_sorted,
    }
    list_path.write_text(json.dumps(payload, indent=2) + "\n")

    reps.drop(columns=["members"]).assign(
        members=reps["members"].apply(lambda m: " ".join(str(x) for x in m))
    ).to_csv(csv_path, index=False)

    summary: dict[str, Any] = {
        "method": "central_mean_abs_r",
        "tie_break": "min_band_index",
        "n_clusters": int(len(reps)),
        "n_representatives": int(len(reps_sorted)),
        "n_singletons": int((reps["size"] == 1).sum()),
        "n_multi": int((reps["size"] > 1).sum()),
        "representatives": reps_sorted,
        "status": "PASS",
        "out_dir": str(out_dir),
        "representatives_json": str(list_path),
        "detail_json": str(detail_path),
        "csv": str(csv_path),
    }
    if extra_meta:
        summary["source"] = extra_meta
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    summary["summary_json"] = str(summary_path)
    return summary
