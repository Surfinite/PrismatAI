#!/usr/bin/env python
"""Build the ELITE rehearsal set by SLICING human_1800_v2.h5 (C6, owner decision 2026-06-13).

Provenance design (see eval/campaign_log.md 2026-06-13 entry):
  - ELIGIBILITY is inherited wholesale from human_1800_v2.h5 — every record already passed
    the full exclusion pipeline (faithful JS-engine extraction, 30-field exact-match clean,
    balance validation). This script only SUBTRACTS. No DB is consulted for eligibility
    (the source set was built from replays.db + the ladder-site DB; ~1,558 of its 2000+
    games exist in NO local DB).
  - RATING filter: the H5's own per-record rating_p0/rating_p1 stamps (per-game min >= 2000).
  - TIME filter: the archived replay JSONs themselves (replays_archive/<urlencoded>.json.gz,
    present for every H5 code by construction — the JS-engine extraction consumed them):
    timeInfo.playerTime[*].increment >= 45 for BOTH players, OR timeInfo.correspondence
    (effectively untimed = maximal think time).
  - SAMPLE: seeded random sample of whole games for set/era diversity.

Also builds the capped tripwire val set (a seeded random row subsample of the held-out
human_val_1700_v2.h5) — the stage-4.5 tripwire only needs ~+/-0.4pp resolution against a
3pp threshold, and the full 413k-row val load was most of stage 3's RAM bill (training-04).

Outputs (next to the inputs in training/data/):
  human_elite_2000_45s_v2.h5            the elite rehearsal slice (same datasets + attrs)
  human_elite_2000_45s_v2.provenance.json   selected codes, filters, seed, pool counts
  human_val_1700_50k_v2.h5              capped tripwire val set (+ provenance attrs)
"""
import argparse
import gzip
import json
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import h5py
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_H5 = os.path.join(REPO, "training", "data", "human_1800_v2.h5")
VAL_H5 = os.path.join(REPO, "training", "data", "human_val_1700_v2.h5")
OUT_H5 = os.path.join(REPO, "training", "data", "human_elite_2000_45s_v2.h5")
OUT_VAL_H5 = os.path.join(REPO, "training", "data", "human_val_1700_50k_v2.h5")
ARCHIVE = r"c:\libraries\prismata-replay-parser\replays_archive"

MIN_RATING = 2000
MIN_INCREMENT = 45
TARGET_GAMES = 5000
VAL_TARGET_ROWS = 50000
SEED = 2026


def replay_path(code):
    """The archive holds MIXED filename conventions (measured 2026-06-13): older fetches
    stored URL-encoded names (%2B/%40), newer ones raw (+/@ are legal Windows filename
    chars). Try encoded first, fall back to raw."""
    enc = os.path.join(ARCHIVE, urllib.parse.quote(code, safe="-") + ".json.gz")
    if os.path.exists(enc):
        return enc
    return os.path.join(ARCHIVE, code + ".json.gz")


def read_time_ok(code):
    """True iff both players' increment >= MIN_INCREMENT, or correspondence."""
    try:
        with gzip.open(replay_path(code), "rt", encoding="utf-8") as f:
            rep = json.load(f)
        ti = rep.get("timeInfo") or {}
        if ti.get("correspondence"):
            return code, True
        pt = ti.get("playerTime") or []
        if len(pt) >= 2 and all(isinstance(p, dict) and p.get("increment", 0) >= MIN_INCREMENT for p in pt[:2]):
            return code, True
        return code, False
    except FileNotFoundError:
        return code, None      # should not happen (extraction consumed these files)
    except Exception as e:     # noqa: BLE001 - forensic: record, don't crash the build
        sys.stderr.write("WARN: %s: %s\n" % (code, e))
        return code, None


def slice_h5(src_path, dst_path, row_idx, extra_attrs):
    """Copy selected rows of every dataset (chunked fancy indexing), preserving attrs."""
    row_idx = np.sort(np.asarray(row_idx, dtype=np.int64))
    with h5py.File(src_path, "r") as src, h5py.File(dst_path, "w") as dst:
        for name in src:
            ds = src[name]
            # h5py fancy indexing wants increasing unique coords; chunk to bound RAM.
            parts = []
            CHUNK = 200000
            for s in range(0, len(row_idx), CHUNK):
                parts.append(ds[row_idx[s:s + CHUNK]])
            data = np.concatenate(parts, axis=0) if len(parts) > 1 else parts[0]
            if ds.dtype.kind == "O":  # variable-length strings
                dt = h5py.string_dtype(encoding="utf-8")
                dst.create_dataset(name, data=data.astype(object), dtype=dt)
            else:
                dst.create_dataset(name, data=data, compression="gzip", compression_opts=1)
        for k, v in src.attrs.items():
            dst.attrs[k] = v
        dst.attrs["num_records"] = len(row_idx)
        for k, v in extra_attrs.items():
            dst.attrs[k] = v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target-games", type=int, default=TARGET_GAMES)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--skip-val", action="store_true")
    args = p.parse_args()

    print("reading %s metadata columns..." % SRC_H5, flush=True)
    with h5py.File(SRC_H5, "r") as f:
        codes_raw = f["replay_codes"][:]
        r0 = f["rating_p0"][:]
        r1 = f["rating_p1"][:]
    codes = np.array([c.decode() if isinstance(c, bytes) else c for c in codes_raw], dtype=object)
    minr = np.minimum(r0, r1)

    # per-game grouping (records of one game are contiguous, but don't assume it)
    game_rows = {}
    for i, c in enumerate(codes):
        game_rows.setdefault(c, []).append(i)
    print("source: %d records, %d games" % (len(codes), len(game_rows)), flush=True)

    elite_rating = [c for c, rows in game_rows.items() if minr[rows[0]] >= MIN_RATING]
    print("games with min(rating) >= %d: %d" % (MIN_RATING, len(elite_rating)), flush=True)

    print("reading timeInfo from %d archived replays (threaded)..." % len(elite_rating), flush=True)
    tc_ok, tc_missing = [], []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for code, ok in ex.map(read_time_ok, elite_rating):
            if ok is True:
                tc_ok.append(code)
            elif ok is None:
                tc_missing.append(code)
    print("time filter (increment >= %ds both, or correspondence): %d pass, %d unreadable/missing"
          % (MIN_INCREMENT, len(tc_ok), len(tc_missing)), flush=True)

    rng = np.random.RandomState(args.seed)
    if len(tc_ok) > args.target_games:
        selected = sorted(rng.choice(np.array(sorted(tc_ok), dtype=object),
                                     size=args.target_games, replace=False).tolist())
    else:
        selected = sorted(tc_ok)
    rows = []
    for c in selected:
        rows.extend(game_rows[c])
    print("selected %d games -> %d records; writing %s" % (len(selected), len(rows), OUT_H5), flush=True)

    slice_h5(SRC_H5, OUT_H5, rows, {
        "elite_filter": "min_rating>=%d AND (increment>=%d both OR correspondence)" % (MIN_RATING, MIN_INCREMENT),
        "elite_source": os.path.basename(SRC_H5),
        "elite_sample_seed": args.seed,
        "elite_pool_games": len(tc_ok),
        "elite_selected_games": len(selected),
    })
    prov = {
        "source": os.path.basename(SRC_H5),
        "filters": {"min_rating_both": MIN_RATING, "min_increment_both": MIN_INCREMENT,
                    "correspondence_included": True},
        "pool": {"rating_pass_games": len(elite_rating), "time_pass_games": len(tc_ok),
                 "time_unreadable": len(tc_missing)},
        "sample": {"seed": args.seed, "target_games": args.target_games,
                   "selected_games": len(selected), "selected_records": len(rows)},
        "selected_codes": selected,
        "tc_missing_codes": sorted(tc_missing),
    }
    with open(OUT_H5.replace(".h5", ".provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=1)

    if not args.skip_val:
        print("building capped tripwire val set -> %s" % OUT_VAL_H5, flush=True)
        with h5py.File(VAL_H5, "r") as f:
            n_val = f.attrs["num_records"]
        val_rows = np.sort(rng.choice(n_val, size=min(VAL_TARGET_ROWS, int(n_val)), replace=False))
        slice_h5(VAL_H5, OUT_VAL_H5, val_rows, {
            "val_cap_source": os.path.basename(VAL_H5),
            "val_cap_seed": args.seed,
            "val_cap_rows": len(val_rows),
        })

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
