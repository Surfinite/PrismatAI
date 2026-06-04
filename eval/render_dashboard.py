"""Per-iteration RL dashboard (spec §5) — a thin reader of eval/manifests/*.json.

Not a gate: just tabulates each iteration's eval manifest (anchors' win-rate + Wilson CI, the
IG-click-count metric, game length if present, export-parity status, outcome/decision) so a human
can apply the §12 decision rule. Reads the EXACT manifest schema written by eval/run_eval.py +
eval/action_coverage.py (see those for the key names). Empty manifests dir -> a friendly message.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wilson import win_rate, wilson_ci  # noqa: E402

MANIFEST_DIR = os.path.join(HERE, "manifests")
ANCHORS = ["iter0", "narrow", "steam"]  # run_eval.py anchor keys


def _anchor_cell(a):
    """Format one anchor as 'wr% [lo-hi] n=N'. Tolerates wins/draws/games or a precomputed rate."""
    if not isinstance(a, dict):
        return "-"
    n = a.get("games") or a.get("n")
    w, d = a.get("wins"), a.get("draws")
    if w is not None and n:
        p = win_rate(w, d or 0, n)
    elif a.get("win_rate") is not None:
        p = a["win_rate"]
    else:
        return "-"  # degraded (stdout score-matrix fallback: no W/L/D)
    lo, hi = a.get("ci", (None, None))
    if lo is None and n:
        lo, hi = wilson_ci(p, n)
    ci = f"[{lo:.2f}-{hi:.2f}]" if lo is not None else ""
    return f"{p * 100:4.1f}% {ci} n={n}"


def render(manifests):
    cols = ["iter", "iter0", "narrow", "steam",
            "mean_IG(sp/argmax)", "len", "parity", "decision"]
    rows = []
    for m in manifests:
        anchors = m.get("anchors", {}) or {}
        cov = m.get("action_coverage", {}) or {}
        sp = cov.get("mean_ig_clicks_selfplay")
        am = cov.get("mean_ig_clicks_argmax")
        ig = f"{sp if sp is not None else '-'}/{am if am is not None else '-'}"
        length = m.get("mean_total_plies") or m.get("game_length") or cov.get("ig_present_turns") or "-"
        parity = m.get("export_parity", m.get("parity_status", "-"))
        decision = m.get("decision", m.get("outcome", "(human call)"))
        rows.append([
            str(m.get("iteration", "?")),
            _anchor_cell(anchors.get("iter0")),
            _anchor_cell(anchors.get("narrow")),
            _anchor_cell(anchors.get("steam")),
            ig, str(length), str(parity), str(decision),
        ])
    if not rows:
        # manifests dir had files but none parsed (the empty-DIR case is handled in main()).
        # Guard the width calc: max(len(cols[i]), *(... for r in [])) unpacks an empty
        # generator -> max(<int>) -> TypeError: 'int' object is not iterable.
        return "no readable manifests (all manifest files failed to parse)"
    widths = [max(len(cols[i]), *(len(r[i]) for r in rows)) for i in range(len(cols))]
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    out = [fmt.format(*cols), fmt.format(*["-" * w for w in widths])]
    out += [fmt.format(*r) for r in rows]
    return "\n".join(out)


def main():
    paths = sorted(glob.glob(os.path.join(MANIFEST_DIR, "eval_iter_*.json")))
    if not paths:
        print("no manifests yet (eval/manifests/ is empty) — run eval/run_iteration.ps1 first")
        return 0
    manifests = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                manifests.append(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            print(f"skipping unreadable manifest {os.path.basename(p)}: {e}", file=sys.stderr)
    manifests.sort(key=lambda m: m.get("iteration", 0))
    print(f"RL campaign dashboard — {len(manifests)} iteration(s)\n")
    print(render(manifests))
    print("\nanchors: iter0=wide-untrained (regression ref, A1) | narrow=DSNN_Mixed35_5var | "
          "steam=STEAMAI/.ORIG.  IG=mean IG-click count (self-play/argmax). Decision is a HUMAN call.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
