#!/usr/bin/env python
"""prediction_movement.py — the B5 null-update detector (stage 4.6, 2026-06-13).

Measures how much the CANDIDATE net's predictions moved relative to the PARENT net:
mean |P_cand - P_parent| and the winner-flip fraction over (a) a FIXED probe batch
(the frozen rehearsal H5's first rows — comparable across iterations) and (b) this
iteration's own self-play H5 (the current training distribution).

WHY: the loop's third audit (training-01/rl-design-01) found the frozen schedule could
produce updates ~2 orders of magnitude below eval resolution — a null iteration that
every downstream gate (tripwire, parity, eval) waves through. This probe costs seconds
and detects it BEFORE the multi-hour eval: a mean |dP| near 0 (≲1e-4) means stage 3
effectively did not train; record the value in the campaign log every iteration and
watch its trend. Informational — never gates (the human reads it at REVIEW time).

Usage:
  python eval/prediction_movement.py --candidate-pt <cand.pt> --parent-pt <parent.pt> \
      --fixed-h5 training/data/human_elite_2000_45s_v2.h5 \
      --selfplay-h5 training/data/rl_iter_K/selfplay_iter_K.h5 \
      [--max-records 2048] [--out probe.json]
"""
import argparse
import json
import os
import sys

import torch
from torch.utils.data import DataLoader, Subset

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "training"))
sys.path.insert(0, os.path.join(REPO, "eval"))

from train import H5DatasetV2, _forward_deepsets    # noqa: E402
from eval_deepsets_h5 import load_deepsets          # noqa: E402


@torch.no_grad()
def predictions(model, ds, device, max_records, batch_size=512):
    n = min(len(ds), max_records)
    loader = DataLoader(Subset(ds, range(n)), batch_size=batch_size,
                        shuffle=False, num_workers=0)
    out = []
    for batch in loader:
        logit, _label, _bs = _forward_deepsets(model, batch, device)
        out.append(torch.sigmoid(logit.float()).cpu())
    return torch.cat(out)


def movement(cand, parent, ds, device, max_records, tag):
    p_c = predictions(cand, ds, device, max_records)
    p_p = predictions(parent, ds, device, max_records)
    dp = (p_c - p_p).abs()
    flips = ((p_c >= 0.5) != (p_p >= 0.5)).float().mean().item()
    stats = {
        "n_records": int(dp.numel()),
        "mean_abs_dP": float(dp.mean()),
        "max_abs_dP": float(dp.max()),
        "winner_flip_frac": flips,
    }
    print("[%s] n=%d  mean|dP|=%.6f  max|dP|=%.4f  winner flips=%.3f%%"
          % (tag, stats["n_records"], stats["mean_abs_dP"], stats["max_abs_dP"],
             100.0 * stats["winner_flip_frac"]))
    return stats


def main():
    ap = argparse.ArgumentParser(description="B5 prediction-movement probe (candidate vs parent).")
    ap.add_argument("--candidate-pt", required=True)
    ap.add_argument("--parent-pt", required=True)
    ap.add_argument("--fixed-h5", required=True,
                    help="FIXED probe batch source (same file+rows every iteration)")
    ap.add_argument("--selfplay-h5", default=None,
                    help="this iteration's self-play H5 (current training distribution)")
    ap.add_argument("--max-records", type=int, default=2048)
    ap.add_argument("--property-table", default=os.path.join(REPO, "training", "property_table.json"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default=None, help="write the stats JSON here")
    a = ap.parse_args()

    device = torch.device(a.device)
    cand = load_deepsets(a.candidate_pt, a.property_table, device)
    parent = load_deepsets(a.parent_pt, a.property_table, device)

    result = {"candidate_pt": a.candidate_pt, "parent_pt": a.parent_pt,
              "max_records": a.max_records}
    result["fixed_probe"] = movement(cand, parent, H5DatasetV2(a.fixed_h5, label_strategy="A"),
                                     device, a.max_records, "fixed:" + os.path.basename(a.fixed_h5))
    if a.selfplay_h5 and os.path.isfile(a.selfplay_h5):
        result["selfplay_probe"] = movement(cand, parent,
                                            H5DatasetV2(a.selfplay_h5, label_strategy="A"),
                                            device, a.max_records,
                                            "selfplay:" + os.path.basename(a.selfplay_h5))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print("probe stats -> %s" % a.out)


if __name__ == "__main__":
    main()
