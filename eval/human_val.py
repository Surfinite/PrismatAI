"""6s and 12s human-relevant-think-time validation vs STEAMAI/.ORIG (forgetting/strength diagnostic).

Reuses run_eval.run_steam (A7 seat-independent identity parsing) + wilson for CIs. FIXED games
per think-time (not sequential) — this is a trajectory yardstick, it gates nothing.

DEFERRED LIVE RUN: requires PrismataAI.exe.ORIG (the 2016 STEAMAI baseline, currently absent)
AND the A12 standalone-loads-config prerequisite (so the candidate runs OUR deployment iterator,
not the SWF's narrow one) before the numbers are meaningful. Until then this is import/parse-checked
infrastructure; Task 14 runs it live.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wilson import wilson_ci
from run_eval import run_steam   # A7 seat-independent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig-exe", required=True, help="PrismataAI.exe.ORIG (STEAMAI 2016 baseline)")
    ap.add_argument("--candidate-label", default="RL_Eval",
                    help="candidate identity label as it appears in matchup_clean.js output")
    ap.add_argument("--games", type=int, default=128)
    a = ap.parse_args()
    for t in (6000, 12000):
        # run_steam(orig_exe, candidate_label, games, pool_args, think_ms) -> (win_rate p in [0,1] or None, n).
        # General (random) pool: empty pool_args. A7 seat-independent parse via parse_matchup_seatindep.
        p, n = run_steam(a.orig_exe, a.candidate_label, a.games, [], think_ms=t)
        if p is None:
            print(f"think={t}ms  (no seat-independent result parsed — check --player-switch / labels)")
            continue
        lo, hi = wilson_ci(p, n)
        print(f"think={t}ms  WR={p:.3f}  CI=[{lo:.3f},{hi:.3f}]  (n={n})")


if __name__ == "__main__":
    main()
