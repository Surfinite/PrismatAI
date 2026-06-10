"""render_dashboard must render the new verdict prominently, surface the general-pool
(gate) WR+CI column, label narrow/steam as non-gating yardsticks, and NOT crash on
pre-verdict (old go_signal-era) manifests."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import render_dashboard


def _pool_cell(wins, n=128):
    from wilson import win_rate, wilson_ci
    p = win_rate(wins, 0, n)
    lo, hi = wilson_ci(p, n)
    return {"block": "b", "candidate": "RL_Eval", "wins": wins, "draws": 0,
            "games": n, "win_rate": p, "ci": [lo, hi]}


def _new_manifest(verdict="REVIEW", complete=True):
    general, forced = _pool_cell(64), _pool_cell(71)
    return {
        "iteration": 1, "verdict": verdict, "complete": complete,
        "anchors_completed": ["iter0", "narrow"],
        "anchors": {
            "iter0": {**forced, "pools": {"forced": forced, "general": general}},
            "narrow": _pool_cell(60),
            "steam": {"status": "DEFERRED -- PrismataAI.exe.ORIG absent"},
        },
        "decision": "(human call)",
    }


def _old_manifest():
    """Pre-2026-06-10 schema: go_signal, no verdict/complete keys."""
    cell = _pool_cell(70, n=100)
    return {
        "iteration": 0,
        "anchors": {"iter0": {**cell, "pools": {"forced": cell, "general": cell}},
                    "narrow": cell,
                    "steam": {"status": "DEFERRED"}},
        "go_signal": {"GO_suggested": False, "computable": True},
        "decision": "(human call)",
    }


def test_render_shows_verdict_and_general_gate_column():
    out = render_dashboard.render([_new_manifest()])
    header = out.splitlines()[0]
    assert "verdict" in header
    assert "general" in header          # the gate pool WR+CI column (audit L-12)
    assert "REVIEW" in out


def test_render_marks_partial_manifests():
    out = render_dashboard.render([_new_manifest(complete=False)])
    assert "REVIEW*" in out             # '*' = partial (crashed/in-flight) manifest


def test_render_does_not_crash_on_old_manifest():
    out = render_dashboard.render([_old_manifest()])
    assert "0" in out                   # renders the row; missing verdict degrades to '-'
    row = out.splitlines()[2]
    assert row.split()[1] == "-"        # verdict column placeholder


def test_render_mixed_old_and_new():
    out = render_dashboard.render([_old_manifest(), _new_manifest("REJECT")])
    assert "REJECT" in out


def test_footer_labels_are_honest():
    f = render_dashboard.FOOTER
    assert "non-gating" in f            # narrow + steam are yardsticks, not gates
    assert "parent" in f                # iter0 opponent = the parent promoted net (v221)...
    assert "wide-untrained" not in f    # ...NOT wide-untrained (old footer mislabel)
    assert "HUMAN" in f.upper()
