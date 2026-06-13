#!/usr/bin/env python
"""a6_orientation_check.py — the END-TO-END value-orientation test (B1/A6, 2026-06-13).

THE SEAM: NeuralNet computes a P0-framed scalar; `evaluateValue` negates it when
maxPlayer != Player_One (NeuralNet.cpp), and UCTSearch consumes `(nnValue+1)/2`
(UCTSearch.cpp traverse). Every other automated gate is blind to a sign flip there:
stage 5's parity oracle always evaluates from Player_One (the negation branch never
executes), the 4.5 tripwire is PyTorch-side, and the three-way feature gate compares
features, not consumption. A flip inverts the net's advice for one or both seats while
ALL gates stay green — the E1 class of failure (gates green, 25.8% strength) one seam over.

THE CHECK: four near-final turn-start states from two DECIDED elite human games
(eval/a6_states/, provenance in meta.json), covering winner-to-move and loser-to-move
from BOTH seats. Each is driven through js_engine/query_move.js with EmitDiagnostics; the
engine's `airootwinrate` (the chosen root child's backed-up win rate, MOVER perspective)
must side with the recorded game outcome: HIGH when the mover went on to win, LOW when
the mover went on to lose. A sign flip inverts all four. This exercises
NN -> evaluateValue(maxPlayer) -> negation -> (nnValue+1)/2 -> UCT backup -> root value.

Run before any campaign run after touching the engine (it is on the §4 triage list and
the promotion checklist); seconds per state at the default budget. Exit 0 = oriented.

Usage:
  python eval/a6_orientation_check.py [--weights neural_weights_mixed_v221.bin]
      [--dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe]
      [--time-limit 2000] [--hi 0.7] [--lo 0.3]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUERY_MOVE = os.path.join(REPO, "js_engine", "query_move.js")
STATES_DIR = os.path.join(HERE, "a6_states")


def main():
    ap = argparse.ArgumentParser(description="A6 end-to-end value-orientation check.")
    ap.add_argument("--weights", default="neural_weights_mixed_v221.bin")
    ap.add_argument("--dave-exe", default=r"c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe")
    ap.add_argument("--player", default="RL_Eval")
    ap.add_argument("--time-limit", type=int, default=2000)
    ap.add_argument("--hi", type=float, default=0.7,
                    help="winner-to-move airootwinrate must exceed this")
    ap.add_argument("--lo", type=float, default=0.3,
                    help="loser-to-move airootwinrate must be below this")
    args = ap.parse_args()

    with open(os.path.join(STATES_DIR, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)["fixtures"]

    failures = []
    for name, info in sorted(meta.items()):
        req = os.path.join(STATES_DIR, name)
        out = subprocess.run(
            ["node", QUERY_MOVE, "--request", req, "--player", args.player,
             "--weights", args.weights, "--dave-exe", args.dave_exe,
             "--time-limit", str(args.time_limit)],
            capture_output=True, text=True, timeout=180)
        if out.returncode != 0:
            failures.append(f"{name}: query_move exited {out.returncode}: {out.stderr.strip()[-300:]}")
            continue
        resp = json.loads(out.stdout)
        wr = resp.get("airootwinrate")
        if wr is None:
            failures.append(f"{name}: response has no airootwinrate — engine predates the B1 "
                            "diagnostic (rebuild) or EmitDiagnostics was not injected")
            continue
        ok = (wr > args.hi) if info["expected"] == "high" else (wr < args.lo)
        print(f"  {name}: mover_seat={info['mover_seat']} expected={info['expected']:4s} "
              f"airootwinrate={wr:.3f} {'OK' if ok else '*** WRONG SIDE ***'}")
        if not ok:
            failures.append(f"{name}: airootwinrate={wr:.3f} on the WRONG SIDE "
                            f"(expected {info['expected']}, thresholds hi>{args.hi}/lo<{args.lo}) "
                            "— check the maxPlayer negation seam (NeuralNet.cpp evaluateValue "
                            "tail / UCTSearch.cpp value consumption)")

    if failures:
        print("\nA6 ORIENTATION CHECK FAILED:")
        for f_ in failures:
            print("  " + f_)
        return 1
    print("A6 orientation check PASSED (all four states side with the recorded outcome)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
