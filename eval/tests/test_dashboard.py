"""render_dashboard must surface the v4 collapse/origin/masterbot shape, NOT the v3
verdict/iter0/narrow/steam shape. Tests are written FIRST (TDD) and should fail against the
v3 code; they pass once render_dashboard.py is rewritten to v4."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import render_dashboard


def _pool_cell(wins, n=96):
    from wilson import win_rate, wilson_ci
    p = win_rate(wins, 0, n)
    lo, hi = wilson_ci(p, n)
    return {"block": "b", "candidate": "RL_Eval", "wins": wins, "draws": 0,
            "games": n, "win_rate": p, "ci": [lo, hi]}


def _new_manifest(collapse=False, complete=True, include_anchors=True,
                  include_coverage=True):
    """Build a v4 manifest mirroring the REAL eval_iter_1.json schema."""
    origin_cell = _pool_cell(47, n=96)
    mb_cell     = _pool_cell(56, n=96)
    m = {
        "iteration": 1,
        "collapse": collapse,
        "complete": complete,
        "anchors_completed": ["origin", "masterbot"],
        "summary": {
            "origin_win_rate": origin_cell["win_rate"],
            "origin_wr_ci": origin_cell["ci"],
            "masterbot_win_rate": mb_cell["win_rate"],
            "masterbot_wr_ci": mb_cell["ci"],
        },
    }
    if include_anchors:
        m["anchors"] = {
            "origin":    {**origin_cell, "pools": {"general": origin_cell}},
            "masterbot": {**mb_cell,     "pools": {"general": mb_cell}},
        }
    if include_coverage:
        m["action_coverage"] = {
            "mean_ig_clicks_selfplay": 0.311,
            "mean_ig_clicks_argmax":   0.359,
        }
    return m


def _old_manifest():
    """Pre-v4 manifest: has go_signal / no collapse / no origin or masterbot anchor."""
    cell = _pool_cell(70, n=100)
    return {
        "iteration": 0,
        "anchors": {"iter0": {**cell, "pools": {"forced": cell, "general": cell}},
                    "narrow": cell,
                    "steam":  {"status": "DEFERRED"}},
        "go_signal": {"GO_suggested": False, "computable": True},
        "decision": "(human call)",
    }


# ---------------------------------------------------------------------------
# Header / column shape
# ---------------------------------------------------------------------------

def test_header_contains_collapse_origin_masterbot():
    out = render_dashboard.render([_new_manifest()])
    header = out.splitlines()[0]
    assert "collapse" in header
    assert "origin"   in header
    assert "masterbot" in header


def test_header_does_not_contain_v3_columns():
    out = render_dashboard.render([_new_manifest()])
    header = out.splitlines()[0]
    assert "verdict"  not in header
    assert "narrow"   not in header
    assert "steam"    not in header
    assert "parity"   not in header
    # "len" could appear as a substring of "masterbot"; check the column list instead
    assert render_dashboard.ANCHORS == ["origin", "masterbot"]


# ---------------------------------------------------------------------------
# collapse cell
# ---------------------------------------------------------------------------

def test_collapse_false_renders_ok():
    out = render_dashboard.render([_new_manifest(collapse=False)])
    assert "ok" in out


def test_collapse_true_renders_COLLAPSE():
    out = render_dashboard.render([_new_manifest(collapse=True)])
    assert "COLLAPSE" in out


def test_collapse_none_renders_dash():
    m = _new_manifest()
    m["collapse"] = None
    out = render_dashboard.render([m])
    # The collapse column for this row should be '-'
    data_row = out.splitlines()[2]
    # second token (after iter) should be '-'
    tokens = data_row.split()
    assert tokens[1] == "-"


def test_collapse_absent_renders_dash():
    m = _new_manifest()
    del m["collapse"]
    out = render_dashboard.render([m])
    data_row = out.splitlines()[2]
    tokens = data_row.split()
    assert tokens[1] == "-"


def test_partial_manifest_adds_star_marker_ok():
    out = render_dashboard.render([_new_manifest(collapse=False, complete=False)])
    assert "ok*" in out


def test_partial_manifest_adds_star_marker_collapse():
    out = render_dashboard.render([_new_manifest(collapse=True, complete=False)])
    assert "COLLAPSE*" in out


# ---------------------------------------------------------------------------
# origin / masterbot anchor cells
# ---------------------------------------------------------------------------

def test_origin_cell_shows_win_rate():
    out = render_dashboard.render([_new_manifest()])
    # 47/96 = 49.0% → pin the formatted origin cell (win-rate + n together)
    assert "49." in out and "n=96" in out


def test_masterbot_cell_shows_win_rate():
    out = render_dashboard.render([_new_manifest()])
    # 56/96 ≈ 58.33%
    assert "58." in out


def test_missing_anchors_renders_dashes_no_crash():
    m = _new_manifest(include_anchors=False)
    out = render_dashboard.render([m])
    assert "1" in out          # iteration row present
    # both origin and masterbot cells should degrade to '-'
    assert "-" in out


# ---------------------------------------------------------------------------
# action_coverage / IG telemetry
# ---------------------------------------------------------------------------

def test_ig_telemetry_present_when_coverage_included():
    out = render_dashboard.render([_new_manifest(include_coverage=True)])
    assert "0.31" in out or "0.311" in out


def test_ig_telemetry_absent_renders_dash():
    out = render_dashboard.render([_new_manifest(include_coverage=False)])
    # The ig column should fall back to '-/-'
    assert "-/-" in out


# ---------------------------------------------------------------------------
# Graceful degradation on old / pre-v4 manifests
# ---------------------------------------------------------------------------

def test_old_manifest_does_not_crash():
    out = render_dashboard.render([_old_manifest()])
    assert "0" in out          # renders the iteration row


def test_old_manifest_collapse_column_is_dash():
    out = render_dashboard.render([_old_manifest()])
    data_row = out.splitlines()[2]
    tokens = data_row.split()
    assert tokens[1] == "-"   # collapse column placeholder


def test_mixed_old_and_new_manifests():
    out = render_dashboard.render([_old_manifest(), _new_manifest(collapse=True)])
    assert "COLLAPSE" in out
    assert "0" in out


# ---------------------------------------------------------------------------
# FOOTER content
# ---------------------------------------------------------------------------

def test_footer_mentions_collapse_and_v221():
    f = render_dashboard.FOOTER
    assert "collapse" in f.lower()
    assert "v221" in f


def test_footer_mentions_masterbot():
    f = render_dashboard.FOOTER
    assert "masterbot" in f.lower() or "MasterBot" in f


def test_footer_mentions_human_call():
    f = render_dashboard.FOOTER
    assert "human" in f.lower()


def test_footer_does_not_contain_v3_terms():
    f = render_dashboard.FOOTER
    assert "verdict"        not in f
    assert "REJECT"         not in f
    assert "REVIEW"         not in f
    assert "narrow"         not in f.lower()
    assert "steam"          not in f.lower()
    assert "wide-untrained" not in f
