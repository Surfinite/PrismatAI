"""Unit tests for run_eval.build_manifest — the B1 orchestration + §3 decision logic.

build_manifest takes injectable runners (run_anchor / steam_fn) so the manifest assembly, the
dashboard-schema flat anchor cells, and the GO d_rl/d_reg booleans can be verified WITHOUT the
C++ engine (the real multi-hour campaign is deferred). Mirrors the dashboard's read contract
(render_dashboard._anchor_cell reads wins/draws/games or win_rate + ci per anchor).
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_eval


def _anchor(block, win_rate, n=100, ci=None):
    """A flat anchor result dict shaped like run_anchor_block()'s success return."""
    wins = round(win_rate * n)
    if ci is None:
        ci = run_eval.wilson_ci(win_rate, n)
    return {"block": block, "candidate": "RL_Eval", "wins": wins, "draws": 0,
            "games": n, "win_rate": win_rate, "ci": [ci[0], ci[1]]}


def _args(tmp_path, pools=("forced", "general"), orig_present=False):
    cfgdir = tmp_path / "asset" / "config"
    cfgdir.mkdir(parents=True)
    (cfgdir / "cand.bin").write_bytes(b"\x00\x01\x02\x03")   # sha256() reads this
    orig = tmp_path / "PrismataAI.exe.ORIG"
    if orig_present:
        orig.write_bytes(b"steam")
    return types.SimpleNamespace(
        iteration=3, weights="cand.bin", parent_weights="parent.bin",
        candidate_player="RL_Eval", candidate_label="RL_Eval",
        dave_bin=str(tmp_path), orig_exe=str(orig), steam_games=200, pools=list(pools))


def _table_runner(table):
    """run_anchor(dave_bin, block, player) -> the pre-canned anchor dict for that block."""
    def run_anchor(dave_bin, block, player):
        assert block in table, f"unexpected block {block}"
        return table[block]
    return run_anchor


# ---------------------------------------------------------------------------

def test_go_suggested_when_all_three_gates_pass(tmp_path):
    table = {
        # forced: 0.60, CI lower 0.51 > 0.5, d_rl = +0.10 >= E(0.05)
        "RL_Eval_iter0_forced":   _anchor("RL_Eval_iter0_forced",  0.60, ci=(0.51, 0.69)),
        # general: 0.52, d_reg = +0.02 >= -Y(-0.03)
        "RL_Eval_iter0_general":  _anchor("RL_Eval_iter0_general", 0.52, ci=(0.42, 0.61)),
        "RL_Eval_narrow_forced":  _anchor("RL_Eval_narrow_forced", 0.55),
        "RL_Eval_narrow_general": _anchor("RL_Eval_narrow_general", 0.50),
    }
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))

    # Dashboard contract: anchors[iter0] is FLAT (headline = forced pool) + has both pools nested.
    assert m["anchors"]["iter0"]["win_rate"] == 0.60
    assert m["anchors"]["iter0"]["block"] == "RL_Eval_iter0_forced"
    assert set(m["anchors"]["iter0"]["pools"]) == {"forced", "general"}
    assert m["anchors"]["narrow"]["win_rate"] == 0.55
    assert m["anchors"]["steam"]["status"].startswith("DEFERRED")

    go = m["go_signal"]
    assert go["ci_lower_gt_half"] is True
    assert go["d_rl_ge_E"] is True
    assert go["d_reg_ge_negY"] is True
    assert go["computable"] is True
    assert go["GO_suggested"] is True
    assert abs(go["d_rl_forced"] - 0.10) < 1e-9
    assert abs(go["d_reg_general"] - 0.02) < 1e-9
    assert m["decision"] == "(human call)"            # never auto-promotes
    assert m["candidate_net_sha256"]                  # sha256 of the temp .bin computed


def test_no_go_when_general_regresses(tmp_path):
    table = {
        "RL_Eval_iter0_forced":   _anchor("RL_Eval_iter0_forced",  0.62, ci=(0.53, 0.70)),
        # general 0.40 -> d_reg = -0.10 < -Y -> regression guard trips
        "RL_Eval_iter0_general":  _anchor("RL_Eval_iter0_general", 0.40, ci=(0.31, 0.49)),
        "RL_Eval_narrow_forced":  _anchor("RL_Eval_narrow_forced", 0.55),
        "RL_Eval_narrow_general": _anchor("RL_Eval_narrow_general", 0.48),
    }
    go = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                 run_anchor=_table_runner(table))["go_signal"]
    assert go["ci_lower_gt_half"] is True
    assert go["d_rl_ge_E"] is True
    assert go["d_reg_ge_negY"] is False               # the binding failure
    assert go["GO_suggested"] is False


def test_no_go_when_ci_straddles_half(tmp_path):
    # forced point estimate 0.55 (>= E) but CI lower 0.46 < 0.5 -> not decisive
    table = {
        "RL_Eval_iter0_forced":   _anchor("RL_Eval_iter0_forced",  0.55, ci=(0.46, 0.64)),
        "RL_Eval_iter0_general":  _anchor("RL_Eval_iter0_general", 0.51, ci=(0.41, 0.60)),
        "RL_Eval_narrow_forced":  _anchor("RL_Eval_narrow_forced", 0.52),
        "RL_Eval_narrow_general": _anchor("RL_Eval_narrow_general", 0.50),
    }
    go = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                 run_anchor=_table_runner(table))["go_signal"]
    assert go["ci_lower_gt_half"] is False
    assert go["GO_suggested"] is False


def test_steam_anchor_when_orig_present(tmp_path):
    table = {b: _anchor(b, 0.5) for b in (
        "RL_Eval_iter0_forced", "RL_Eval_iter0_general",
        "RL_Eval_narrow_forced", "RL_Eval_narrow_general")}

    seen = {}
    def fake_steam(orig, label, games, pool_args, think):
        seen.update(orig=orig, label=label, games=games, pool_args=pool_args, think=think)
        return (0.46, 200)

    m = run_eval.build_manifest(_args(tmp_path, orig_present=True), steam_available=True,
                                run_anchor=_table_runner(table), steam_fn=fake_steam)
    s = m["anchors"]["steam"]
    assert abs(s["win_rate"] - 0.46) < 1e-9 and s["games"] == 200
    assert s["ci"][0] <= 0.46 <= s["ci"][1]
    assert seen["pool_args"] == [] and seen["games"] == 200 and seen["think"] == 7000  # A8 fixed-N, general pool


def test_steam_unparsed_result_is_recorded_not_fatal(tmp_path):
    table = {b: _anchor(b, 0.5) for b in (
        "RL_Eval_iter0_forced", "RL_Eval_iter0_general",
        "RL_Eval_narrow_forced", "RL_Eval_narrow_general")}
    m = run_eval.build_manifest(_args(tmp_path, orig_present=True), steam_available=True,
                                run_anchor=_table_runner(table),
                                steam_fn=lambda *a: (None, 200))
    assert "error" in m["anchors"]["steam"] and m["anchors"]["steam"]["games"] == 200


def test_degraded_anchor_makes_go_uncomputable(tmp_path):
    # run_anchor returns the error shape (no W/L/D parsed) -> no win_rate -> GO not computable.
    err = {"block": "x", "error": "no W/L/D for candidate 'RL_Eval'", "raw_players": []}
    table = {b: err for b in (
        "RL_Eval_iter0_forced", "RL_Eval_iter0_general",
        "RL_Eval_narrow_forced", "RL_Eval_narrow_general")}
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    go = m["go_signal"]
    assert go["computable"] is False
    assert go["GO_suggested"] is False
    # iter0 headline cell carries no win_rate -> dashboard renders "-" (graceful degrade).
    assert "win_rate" not in m["anchors"]["iter0"]


def test_general_only_pool_uses_general_as_headline(tmp_path):
    table = {
        "RL_Eval_iter0_general":  _anchor("RL_Eval_iter0_general", 0.53),
        "RL_Eval_narrow_general": _anchor("RL_Eval_narrow_general", 0.50),
    }
    m = run_eval.build_manifest(_args(tmp_path, pools=("general",)), steam_available=False,
                                run_anchor=_table_runner(table))
    # No forced pool requested -> headline falls back to general; d_rl gate not computable.
    assert m["anchors"]["iter0"]["block"] == "RL_Eval_iter0_general"
    assert m["go_signal"]["computable"] is False
