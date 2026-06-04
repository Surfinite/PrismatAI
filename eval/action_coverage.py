"""Action-coverage metrics for the Infusion-Grid (IG) click-COUNT axis -> merged into the eval
manifest.

Two signals:
  * self-play sampled IG-click-count distribution, read from the C++ exporter's per-record
    ig_present (0/1) + ig_click_count (int) stamps (REPLACES the old binary ig_legal/ig_fired);
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

    Each self-play V2 record now carries ig_present (0/1) and ig_click_count (int >= 0). Among
    turns where IG was present, report the mean IG-click count and the count distribution."""
    present = 0
    counts = []  # ig_click_count over ig_present turns
    for f in glob.glob(os.path.join(jsonl_dir, "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("ig_present"):
                    present += 1
                    counts.append(int(r.get("ig_click_count", 0)))
    dist = {}
    for c in counts:
        dist[c] = dist.get(c, 0) + 1
    return {
        "ig_present_turns": present,
        "mean_ig_clicks_selfplay": (sum(counts) / len(counts)) if counts else None,
        # stringify keys so the dist round-trips cleanly through JSON
        "ig_click_dist_selfplay": {str(k): dist[k] for k in sorted(dist)},
    }


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
    ap.add_argument("--selfplay-jsonl-dir", required=True)
    ap.add_argument("--dave-exe", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--battery", default="eval/ig_battery")
    a = ap.parse_args()
    with open(a.manifest) as f:
        m = json.load(f)
    m["action_coverage"] = {**selfplay_ig_rate(a.selfplay_jsonl_dir),
                            **argmax_ig_rate(a.dave_exe, a.weights, a.battery)}
    with open(a.manifest, "w") as f:
        json.dump(m, f, indent=2)
    print("action_coverage ->", m["action_coverage"])


if __name__ == "__main__":
    main()
