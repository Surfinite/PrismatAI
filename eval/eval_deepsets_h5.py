#!/usr/bin/env python
"""
eval_deepsets_h5.py — evaluate a trained DeepSets value net on a V2 H5 (offline metrics).

Reuses train.py's eval_epoch + H5DatasetV2 + model_deepsets.PrismataDeepSets so the numbers
match training-time validation exactly. Use it for the SECONDARY MB-val number (the plan switches
the SELECTION val to the human val, so the MB-val comparison to a prior run needs a separate pass).

Usage:
  python eval/eval_deepsets_h5.py --model training/models/deepsets_v221/best_model.pt \
      --val-file training/data/local_mbvmb_v2.h5 --property-table training/property_table.json
  # SWA checkpoint (AveragedModel state dict) handled automatically.

Runs on CPU by default so it won't contend with an XPU training run.
"""
import argparse
import json
import os
import sys

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "training"))

from train import eval_epoch, H5DatasetV2           # noqa: E402  (training-time evaluator + dataset)
from model_deepsets import PrismataDeepSets          # noqa: E402


def load_deepsets(pt_path, property_table, device):
    with open(property_table, encoding="utf-8") as f:
        num_properties = json.load(f).get("num_properties", 37)
    model = PrismataDeepSets(num_units=116, num_properties=num_properties, dropout=0.0).to(device)
    model.load_property_table(property_table)
    ck = torch.load(pt_path, map_location=device, weights_only=False)
    sd = ck.get("model_state_dict", ck) if isinstance(ck, dict) else ck
    # SWA checkpoints are AveragedModel state dicts: keys prefixed "module.", plus "n_averaged".
    if any(k.startswith("module.") for k in sd):
        sd = {k[len("module."):]: v for k, v in sd.items() if k != "n_averaged"}
    model.load_state_dict(sd)
    model.eval()
    return model


def main():
    ap = argparse.ArgumentParser(description="Evaluate a DeepSets value net on a V2 H5.")
    ap.add_argument("--model", required=True, help="best_model.pt or swa_model.pt")
    ap.add_argument("--val-file", required=True, help="V2 H5 to evaluate on")
    ap.add_argument("--property-table", default=os.path.join(REPO, "training", "property_table.json"))
    ap.add_argument("--label-strategy", default="A")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--batch-size", type=int, default=512)
    a = ap.parse_args()

    device = torch.device(a.device)
    model = load_deepsets(a.model, a.property_table, device)
    ds = H5DatasetV2(a.val_file, label_strategy=a.label_strategy)
    loader = DataLoader(ds, batch_size=a.batch_size, shuffle=False, num_workers=0)
    m = eval_epoch(model, loader, device, nn.BCEWithLogitsLoss(), model_type="deepsets")

    print(f"model    : {a.model}")
    print(f"val-file : {a.val_file}  ({len(ds):,} records, label {a.label_strategy})")
    print(f"  val_loss = {m['val_value_loss']:.4f}")
    print(f"  val_acc  = {m['val_value_acc'] * 100:.1f}%")
    print(f"  brier    = {m['val_brier']:.4f}")


if __name__ == "__main__":
    main()
