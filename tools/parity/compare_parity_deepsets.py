"""
DeepSets C++<->PyTorch value-parity, generation-agnostic.

Compares the C++ engine's --dump-features value/logit against the PyTorch model
and a numpy-over-.bin forward, for ANY DeepSets feature_revision (13/35/37-prop,
14/15-global). The architecture is INFERRED from the checkpoint's saved tensor
shapes (see _infer_config), so it does NOT depend on PrismataDeepSets() defaults
-- which track the latest schema (v2.2 = 37-prop / 15-global) and would otherwise
fail to load an older checkpoint. load_state_dict still raises on any real mismatch.

Defaults point at the 35-prop interim pair (14-global), but pass --pt/--bin for any model:
  PT  : training/models/deepsets_mixed_35prop/best_model.pt   (epoch 30)
  BIN : docs/scratch/deepsets_mixed_35prop.bin                (exported from that .pt, round-trip verified)

Usage:
  python compare_parity_deepsets.py <dump1.json> [dump2.json ...] [--pt PT] [--bin BIN]
"""

import json
import os
import sys

sys.path.insert(0, "C:/libraries/torch_pkg")
import numpy as np
import torch

TRAIN_DIR = "C:/libraries/PrismataAI/training"
sys.path.insert(0, TRAIN_DIR)
from model_deepsets import PrismataDeepSets
import export_weights_v2 as ew  # numpy_forward + load_binary

# 35-prop interim artifacts (epoch 30 of the crashed mixed run; .bin round-trip PASSED)
PT_PATH  = "C:/libraries/PrismataAI/training/models/deepsets_mixed_35prop/best_model.pt"
BIN_PATH = "C:/libraries/PrismataAI/docs/scratch/deepsets_mixed_35prop.bin"

VALUE_TOL = 1e-3


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def value_from_logit(logit):
    return 2.0 * sigmoid(logit) - 1.0


def _infer_config(sd):
    """Infer architecture dims from a checkpoint's state_dict, so the tool builds the
    RIGHT model for any DeepSets generation instead of relying on PrismataDeepSets()
    defaults (which track the latest schema). num_instance_features is fixed at 10 by
    design; load_state_dict raises if the inferred token/value dims don't match."""
    enc_h  = sd["instance_encoder.0.weight"].shape[0]
    sup_h  = sd["supply_encoder.0.weight"].shape[0]
    val_in = sd["value_head.0.weight"].shape[1]            # == COMBINED = 2*enc_h + sup_h + num_global
    return dict(
        num_units      = sd["unit_embedding.weight"].shape[0],
        d_embed        = sd["unit_embedding.weight"].shape[1],
        num_properties = sd["property_table"].shape[1],
        encoder_hidden = enc_h,
        supply_hidden  = sup_h,
        value_hidden   = sd["value_head.0.weight"].shape[0],
        num_global     = val_in - (2 * enc_h + sup_h),
    )


def load_model(pt_path):
    # weights_only=False: our own trusted checkpoint (carries optimizer state + dicts)
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    sd = ckpt["model_state_dict"]
    # Use an explicit model_config if the checkpoint carries one; otherwise infer the
    # architecture from the saved tensor shapes (robust across schema generations).
    cfg = ckpt.get("model_config") or _infer_config(sd)
    model = PrismataDeepSets(**cfg)
    model.load_state_dict(sd)
    model.eval()
    return model, cfg


def build_inputs(dump, num_units):
    insts = dump["instances"]
    N = len(insts)
    if N == 0:
        feats = np.zeros((1, 10), dtype=np.float32)
        ids = np.zeros((1,), dtype=np.int64)
        count = 0
    else:
        feats = np.array([i["instance"] for i in insts], dtype=np.float32).reshape(N, 10)
        ids = np.array([i["unit_index"] for i in insts], dtype=np.int64)
        count = N
    supply = np.zeros((num_units, 3), dtype=np.float32)
    for s in dump["supply"]:
        u = s["unit_index"]
        supply[u, 0] = s["p0"]
        supply[u, 1] = s["p1"]
        supply[u, 2] = 1.0
    globs = np.array(dump["globals"], dtype=np.float32)
    assert globs.shape[0] in (14, 15), f"expected 14 or 15 globals, got {globs.shape}"  # 15 = schema v2.2 (+under_attack)
    return feats, ids, count, supply, globs


def torch_logit(model, feats, ids, count, supply, globs):
    with torch.no_grad():
        ft = torch.from_numpy(feats).unsqueeze(0).float()
        it = torch.from_numpy(ids).unsqueeze(0)
        ct = torch.tensor([count], dtype=torch.long)
        st = torch.from_numpy(supply).unsqueeze(0).float()
        gt = torch.from_numpy(globs).unsqueeze(0).float()
        return model(ft, it, ct, st, gt)[0, 0].item()


def main():
    import argparse
    ap = argparse.ArgumentParser(description="35-prop C++<->PyTorch value parity")
    ap.add_argument("dumps", nargs="+", help="C++ --dump-features output JSON(s)")
    ap.add_argument("--pt", default=PT_PATH, help="PyTorch .pt reference (default: interim ep30)")
    ap.add_argument("--bin", default=BIN_PATH, help="DSN2 .bin (default: interim ep30)")
    a = ap.parse_args()
    dumps = a.dumps

    print(f"PyTorch reference .pt : {a.pt}")
    print(f"DSN2 .bin             : {a.bin}")
    model, cfg = load_model(a.pt)
    num_units = cfg.get("num_units", 116)
    hdr, bin_tensors = ew.load_binary(a.bin)
    print(f"loaded model (cfg num_units={num_units}) and .bin "
          f"(hdr num_units={hdr['num_units']}, num_properties={hdr.get('num_properties')}, "
          f"tensors={hdr['num_tensors']})")
    print()

    hdr_fmt = (f"{'state':30s} {'N':>3s} {'val_cpp':>10s} {'val_torch':>10s} "
               f"{'|dval|':>9s} {'logit_cpp':>10s} {'logit_torch':>11s} {'logit_np':>10s} "
               f"{'drop':>4s} {'verdict':>8s}")
    print(hdr_fmt)
    print("-" * len(hdr_fmt))

    worst_dval = 0.0
    any_fail = False
    any_drop = False

    for path in dumps:
        with open(path) as f:
            dump = json.load(f)
        feats, ids, count, supply, globs = build_inputs(dump, num_units)

        lt = torch_logit(model, feats, ids, count, supply, globs)
        ln = ew.numpy_forward(bin_tensors, feats, ids, count, supply, globs)

        vc = dump["value_p0"]
        lc = dump["logit_p0"]
        vt = value_from_logit(lt)
        dval = abs(vc - vt)
        drop = len(dump.get("dropped_instances", []))
        worst_dval = max(worst_dval, dval)
        if drop:
            any_drop = True
        ok = dval < VALUE_TOL and drop == 0
        if not ok:
            any_fail = True
        name = os.path.basename(path)
        print(f"{name:30s} {count:3d} {vc:10.6f} {vt:10.6f} {dval:9.2e} "
              f"{lc:10.5f} {lt:11.5f} {ln:10.5f} {drop:4d} {'PASS' if ok else 'FAIL':>8s}")

    print("-" * len(hdr_fmt))
    print(f"worst |value_cpp - value_torch| = {worst_dval:.2e}  (tol {VALUE_TOL:.0e})")
    print(f"overall: {'ALL PASS' if not any_fail else 'FAIL'}"
          + ("  [DROPPED INSTANCES PRESENT]" if any_drop else ""))
    sys.exit(0 if not any_fail else 1)


if __name__ == "__main__":
    main()
