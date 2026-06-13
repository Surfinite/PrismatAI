"""Action-coverage metrics for the Infusion-Grid (IG) click-COUNT axis -> merged into the eval
manifest.

Two signals:
  * self-play sampled IG-click-count distribution, read from the C++ exporter's per-record
    ig_present (0/1) + ig_click_count (int) stamps (REPLACES the old binary ig_legal/ig_fired);
    binned against ig_feasible_max = min(ready IGs, attainable red) when present
    (dave@6037382) — see selfplay_ig_rate for the pair/normalized views and old-record fallback;
  * argmax IG-click-COUNT distribution + root entropy, from query_move.js run over an IG battery
    with the widened HardIterator_5var_IGsubset_Root (the count metric is only selectable there).

Shares count_ig_clicks() with tactical_suite (DRY); query_move.js prints PRETTY (multi-line) JSON,
so we json.loads the whole stdout, never splitlines()[-1]."""
import argparse
import glob
import json
import math
import os
import subprocess
import sys

# Allow `from tactical_suite import ...` whether run as `python eval/action_coverage.py`
# (cwd=repo root) or from inside eval/ (mirrors run_eval.py's bare `from wilson import ...`).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tactical_suite import count_ig_clicks, parse_response

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUERY_MOVE = os.path.join(REPO, "js_engine", "query_move.js")
IGSUBSET_ROOT = "HardIterator_5var_IGsubset_Root"
IGSUBSET_MOVE = "HardIterator_5var"


def selfplay_ig_rate(jsonl_dir):
    """Self-play sampled IG-click-COUNT distribution from the C++ exporter stamps.

    Each self-play V2 record carries ig_present (0/1) and ig_click_count (int >= 0); records
    exported since dave@6037382 also carry ig_feasible_max = min(ready IGs, attainable red)
    evaluated at the mover's Action-phase entry (the meaningful denominator: a player with
    4 IGs but only RR can click at most 2). Among ig_present turns we report:
      * the raw mean / count distribution (always — backward compatible);
      * when the stamp is present, the (ig_click_count, ig_feasible_max) PAIR distribution
        and a normalized count/feasible view over feasible_max > 0 turns (feasible_max == 0
        turns are excluded from the normalized view — nothing was clickable);
      * how many ig_present records LACKED ig_feasible_max (old exporter records fall back
        to the raw-count view only) and how many violate count <= feasible (telemetry —
        should be 0 by construction).
    All new keys are additive; existing manifest keys keep their names and meanings."""
    present = 0
    counts = []   # ig_click_count over ig_present turns (raw view, always)
    pairs = []    # (ig_click_count, ig_feasible_max) over ig_present turns carrying the stamp
    missing_feasible = 0  # ig_present turns lacking ig_feasible_max (pre-stamp records)
    for f in glob.glob(os.path.join(jsonl_dir, "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ig_present"):
                    present += 1
                    k = int(r.get("ig_click_count", 0))
                    counts.append(k)
                    if "ig_feasible_max" in r:
                        pairs.append((k, int(r["ig_feasible_max"])))
                    else:
                        missing_feasible += 1
    dist = {}
    for c in counts:
        dist[c] = dist.get(c, 0) + 1

    pair_dist = {}
    for k, m in pairs:
        key = f"{k}/{m}"
        pair_dist[key] = pair_dist.get(key, 0) + 1
    norm = [k / m for k, m in pairs if m > 0]
    norm_dist = {}
    for v in norm:
        key = f"{v:.2f}"
        norm_dist[key] = norm_dist.get(key, 0) + 1
    violations = sum(1 for k, m in pairs if k > m)

    return {
        "ig_present_turns": present,
        "mean_ig_clicks_selfplay": (sum(counts) / len(counts)) if counts else None,
        # stringify keys so the dist round-trips cleanly through JSON
        "ig_click_dist_selfplay": {str(k): dist[k] for k in sorted(dist)},
        # --- feasible-max binning (additive keys; absent-field fallback is the raw view above) ---
        # (count/feasible) pair distribution, keys "k/m", sorted numerically by (k, m)
        "ig_feasible_pair_dist": {k: pair_dist[k]
                                  for k in sorted(pair_dist, key=lambda s: tuple(map(int, s.split("/"))))},
        "ig_feasible_turns": len(pairs),                 # ig_present turns carrying the stamp
        "ig_feasible_positive_turns": len(norm),         # of those, turns with feasible_max > 0
        "ig_click_norm_mean": (sum(norm) / len(norm)) if norm else None,
        "ig_click_norm_dist": {k: norm_dist[k] for k in sorted(norm_dist, key=float)},
        "ig_feasible_missing_records": missing_feasible, # old records lacking ig_feasible_max
        "ig_feasible_invariant_violations": violations,  # count > feasible (should be 0)
    }


def ig_contrast_pairs(jsonl_dir):
    """B6 (2026-06-13): the realized IG-counterfactual watch-stat — the count of colour-swap
    pairs whose IG-click-count decision sequences DIFFER.

    The exporter's shared per-game id makes selfplay_<2i>.jsonl / selfplay_<2i+1>.jsonl the two
    seat orderings of round i's card set (O1 pairing), so each pair is a natural matched
    counterfactual probe: same set, same nets, different realized IG choices = exactly the
    contrast a value-only net needs in its labels (rl-design-02). Per game we take the ply-
    ordered list of ig_click_count over records with ig_feasible_max > 0 (the LIVE IG
    decisions); a pair contrasts when the two lists differ. Expect ~ε_IG x IG-live-roots per
    game; if this reads ~0, the targeted exploration is not reaching the axis."""
    def game_id(path):
        stem = os.path.splitext(os.path.basename(path))[0]
        try:
            return int(stem.split("_")[-1])
        except ValueError:
            return None

    seqs = {}
    for f in glob.glob(os.path.join(jsonl_dir, "*.jsonl")):
        gid = game_id(f)
        if gid is None:
            continue
        seq = []
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if int(r.get("ig_feasible_max", 0) or 0) > 0:
                    seq.append((int(r.get("ply_index", -1)), int(r.get("ig_click_count", 0))))
        seqs[gid] = [c for _, c in sorted(seq)]
    pairs = contrasts = with_ig = 0
    for gid in sorted(seqs):
        if gid % 2 == 0 and (gid + 1) in seqs:
            pairs += 1
            a, b = seqs[gid], seqs[gid + 1]
            if a or b:
                with_ig += 1
                if a != b:
                    contrasts += 1
    return {"ig_contrast_pairs": contrasts,
            "ig_pairs_total": pairs,
            "ig_pairs_with_live_ig": with_ig}


def argmax_ig_rate(dave_exe, weights, battery="eval/ig_battery", player="RL_Eval"):
    """argmax IG-click-COUNT distribution + root entropy over an IG battery.

    For each battery position, run query_move.js under the widened IGsubset root iterator and
    count the IG self-sac clicks with count_ig_clicks (DRY with tactical_suite). Report the mean
    and distribution of argmax IG-click counts plus the mean root-visit entropy."""
    counts = []
    ents = []
    positions = 0
    for s in sorted(glob.glob(os.path.join(battery, "*.json"))):
        out = subprocess.run(
            ["node", QUERY_MOVE,
             "--request", s, "--player", player,
             "--weights", weights, "--dave-exe", dave_exe,
             "--root-iterator", IGSUBSET_ROOT, "--move-iterator", IGSUBSET_MOVE],
            capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            raise RuntimeError(f"query_move.js exited {out.returncode} on {s}: {out.stderr.strip()[-400:]}")
        resp = parse_response(out.stdout)
        positions += 1
        counts.append(count_ig_clicks(resp))
        v = resp.get("aivisits", [])
        if v:
            tot = float(sum(v))
            if tot > 0:
                ents.append(-sum((x / tot) * math.log(x / tot) for x in v if x > 0))
    dist = {}
    for c in counts:
        dist[c] = dist.get(c, 0) + 1
    return {
        "ig_battery_positions": positions,
        "mean_ig_clicks_argmax": (sum(counts) / len(counts)) if counts else None,
        "ig_click_dist_argmax": {str(k): dist[k] for k in sorted(dist)},
        "root_entropy_mean": (sum(ents) / len(ents)) if ents else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfplay-jsonl-dir", required=True, action="append",
                    help="self-play shard dir; repeatable (C8 2026-06-13: pass BOTH the forced "
                         "and general export dirs — the old single-dir invocation silently "
                         "computed 'self-play coverage' on the forced slice only)")
    ap.add_argument("--dave-exe", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--battery", default=os.path.join(HERE, "ig_battery"),
                    help="dir of IG-owning query_move request JSONs (default: eval/ig_battery)")
    a = ap.parse_args()

    # C3/ops-toctou-07: contamination guards at TIME OF USE (stage 0's check ran hours ago).
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - coverage contamination"
    sentinel = os.path.join(os.path.dirname(os.path.abspath(a.dave_exe)), "use_dsnn.txt")
    assert not os.path.exists(sentinel), f"use_dsnn.txt present ({sentinel}) - coverage contamination"

    with open(a.manifest) as f:
        m = json.load(f)
    # Per-slice stats (labelled by dir name) + a COMBINED view at the legacy top-level keys
    # (dashboard compatibility). NOTE on semantics (coverage-prov-01): the self-play stats
    # describe the GENERATOR's (= the parent net's) behaviour in this iteration's data, not
    # the candidate's; the candidate's behaviour is the argmax battery below.
    slices = {}
    for d in a.selfplay_jsonl_dir:
        label = "general" if "general" in os.path.basename(os.path.normpath(d)).lower() else "forced"
        slices[label] = {**selfplay_ig_rate(d), **ig_contrast_pairs(d)}
    combined = selfplay_ig_rate_multi(a.selfplay_jsonl_dir)
    m["action_coverage"] = {
        **combined,
        "slices": slices,
        "selfplay_stats_describe": "the GENERATOR (parent) net's behaviour in this iteration's "
                                   "self-play data (coverage-prov-01); argmax stats describe the "
                                   "CANDIDATE",
        **argmax_ig_rate(a.dave_exe, a.weights, a.battery),
    }
    with open(a.manifest, "w") as f:
        json.dump(m, f, indent=2)
    print("action_coverage ->", json.dumps(m["action_coverage"], indent=1)[:2000])


def selfplay_ig_rate_multi(dirs):
    """Combined selfplay_ig_rate over several shard dirs (sums the underlying records by
    concatenating per-dir scans — same math as one big dir)."""
    if len(dirs) == 1:
        return selfplay_ig_rate(dirs[0])
    agg = None
    for d in dirs:
        s = selfplay_ig_rate(d)
        if agg is None:
            agg = s
            continue
        # additive merges for counts/dicts; recompute means from merged dists
        for key in ("ig_present_turns", "ig_feasible_turns", "ig_feasible_positive_turns",
                    "ig_feasible_missing_records", "ig_feasible_invariant_violations"):
            agg[key] += s[key]
        for dkey in ("ig_click_dist_selfplay", "ig_feasible_pair_dist", "ig_click_norm_dist"):
            for k, v in s[dkey].items():
                agg[dkey][k] = agg[dkey].get(k, 0) + v
    total = sum(int(k) * v for k, v in agg["ig_click_dist_selfplay"].items())
    n = sum(agg["ig_click_dist_selfplay"].values())
    agg["mean_ig_clicks_selfplay"] = (total / n) if n else None
    norm_total = sum(float(k) * v for k, v in agg["ig_click_norm_dist"].items())
    norm_n = sum(agg["ig_click_norm_dist"].values())
    agg["ig_click_norm_mean"] = (norm_total / norm_n) if norm_n else None
    return agg


if __name__ == "__main__":
    main()
