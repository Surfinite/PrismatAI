"""Per-iteration RL dashboard (spec §5) — a thin reader of eval/manifests/*.json.

Not a gate: just tabulates each iteration's eval manifest so a human can judge it. Renders the
run_eval.py REJECT/REVIEW/INCOMPLETE verdict prominently, the gating general pool (candidate vs
parent, unforced sets — its WR+CI is the d_reg evidence) next to the forced pool (d_rl info),
and the non-gating narrow/steam yardsticks. Reads the EXACT manifest schema written by
eval/run_eval.py + eval/action_coverage.py (see those for the key names); pre-verdict
(go_signal-era) manifests render gracefully with '-' placeholders. Empty manifests dir -> a
friendly message.
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

FOOTER = (
    "verdict: REJECT iff general pool (candidate vs PARENT, unforced sets) Wilson ci_upper<0.5 "
    "(proven worse); REVIEW = human call on the numbers; INCOMPLETE = general anchor missing/"
    "errored; '*' = partial manifest (run died mid-eval).\n"
    "iter0 opponent = the parent promoted net (v221) — general=gate pool (d_reg = WR-0.5), "
    "forced=IG-widened axis (d_rl, information only).\n"
    "narrow=DSNN_Mixed35_5var | steam=STEAMAI/.ORIG — both are non-gating trajectory yardsticks "
    "(marked †). IG=mean IG-click count (self-play/argmax). Promotion is a HUMAN call."
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
        return "-"  # degraded (stdout score-matrix fallback: no W/L/D) or anchor error/deferred
    lo, hi = a.get("ci", (None, None))
    if lo is None and n:
        lo, hi = wilson_ci(p, n)
    ci = f"[{lo:.2f}-{hi:.2f}]" if lo is not None else ""
    return f"{p * 100:4.1f}% {ci} n={n}"


def _pool_cell(m, pool):
    """The iter0 anchor's per-pool cell (general = gate pool, forced = d_rl info)."""
    iter0 = (m.get("anchors") or {}).get("iter0") or {}
    pools = iter0.get("pools") or {}
    return _anchor_cell(pools.get(pool))


def _verdict_cell(m):
    """REJECT/REVIEW/INCOMPLETE; '*' marks a partial (killed-run) manifest; '-' for
    pre-verdict (go_signal-era) manifests."""
    v = m.get("verdict")
    if v is None:
        return "-"
    return f"{v}*" if m.get("complete") is False else str(v)


def render(manifests):
    cols = ["iter", "verdict", "general(gate)", "forced(d_rl)", "narrow†", "steam†",
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
            _verdict_cell(m),
            _pool_cell(m, "general"),
            _pool_cell(m, "forced"),
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
    print("\n" + FOOTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
