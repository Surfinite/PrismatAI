"""Per-iteration RL dashboard (v4, regime v3) — a thin reader of eval/manifests/*.json.

Not a gate: just tabulates each iteration's eval manifest so a human can judge campaign
trajectory. Renders the collapse signal (abort threshold vs the PERMANENT v221 origin),
the two eval anchors (origin = relative-drift + collapse signal; masterbot = absolute-
strength trend), and the IG-click telemetry. Reads the EXACT manifest schema written by
eval/run_eval.py + eval/action_coverage.py (see those for the key names); pre-v4
manifests missing collapse/anchors/action_coverage render gracefully with '-' placeholders.
Empty manifests dir -> a friendly message.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wilson import win_rate, wilson_ci  # noqa: E402

MANIFEST_DIR = os.path.join(HERE, "manifests")
ANCHORS = ["origin", "masterbot"]  # run_eval.py anchor keys

FOOTER = (
    "collapse: 'ok' iff the origin general win-rate >= the frozen abort_winrate vs the "
    "PERMANENT v221 origin; 'COLLAPSE' iff below (run aborted / do not promote); "
    "'-' = collapse key absent or eval incomplete; '*' = partial/killed-run manifest.\n"
    "origin  = candidate vs RL_Eval_origin (PERMANENTLY v221) — the relative-drift "
    "anchor + collapse signal (d_reg = WR - 0.5); non-trivially powered only at the "
    "checkpoint cadence (K=3-5).\n"
    "masterbot = candidate vs MasterBot_SWF (AB Playout, SWF-faithful) — absolute-"
    "strength TREND (non-gating; use for trajectory, not per-iter decisions).\n"
    "ig = mean IG-click count: self-play generator / candidate argmax — telemetry only.\n"
    "Promotion is a HUMAN call (promote-unless-collapse). See eval/rl_runbook.md."
)


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
        return "-"  # degraded (no W/L/D and no precomputed rate) or anchor error/deferred
    lo, hi = a.get("ci", (None, None))
    if lo is None and n:
        lo, hi = wilson_ci(p, n)
    ci = f"[{lo:.2f}-{hi:.2f}]" if lo is not None else ""
    return f"{p * 100:4.1f}% {ci} n={n}"


def _anchor_pool_cell(m, anchor_name):
    """Pull anchors.<name>.pools.general and format via _anchor_cell."""
    anchors = (m.get("anchors") or {})
    anchor  = anchors.get(anchor_name) or {}
    pools   = anchor.get("pools") or {}
    return _anchor_cell(pools.get("general"))


def _collapse_cell(m):
    """'ok'/'COLLAPSE'/'-'; '*' marks a partial (killed-run) manifest."""
    c = m.get("collapse")
    if c is True:
        label = "COLLAPSE"
    elif c is False:
        label = "ok"
    else:
        label = "-"
    if label != "-" and m.get("complete") is False:
        label = label + "*"
    return label


def render(manifests):
    cols = ["iter", "collapse", "origin(vs v221)", "masterbot(vs SWF-AB)", "ig(sp/argmax)"]
    rows = []
    for m in manifests:
        cov = m.get("action_coverage", {}) or {}
        sp  = cov.get("mean_ig_clicks_selfplay")
        am  = cov.get("mean_ig_clicks_argmax")
        sp_s = f"{sp:.3f}" if sp is not None else "-"
        am_s = f"{am:.3f}" if am is not None else "-"
        ig  = f"{sp_s}/{am_s}"
        rows.append([
            str(m.get("iteration", "?")),
            _collapse_cell(m),
            _anchor_pool_cell(m, ANCHORS[0]),
            _anchor_pool_cell(m, ANCHORS[1]),
            ig,
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
    print("\n" + FOOTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
