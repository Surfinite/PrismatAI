"""Unit tests for run_eval.build_manifest — orchestration, the collapse-on-abort signal,
incremental manifest writes, and active provenance.

COLLAPSE PHILOSOPHY (v4 proof-of-life, 2026-06-15): the old REJECT/REVIEW/INCOMPLETE
non-inferiority verdict is replaced by a coarse point-estimate COLLAPSE signal against the
PERMANENT origin reference. compute_collapse(origin_general, threshold) returns True iff the
candidate's origin/general win_rate < threshold (drifted badly), False if >= threshold, None if
the origin anchor is missing/errored or has zero games. It is an ABORT signal, not a powered
gate — every WR/CI is still recorded as information.

v4 anchors (both GENERAL pool only):
  origin    -> candidate (RL_Eval) vs RL_Eval_origin (the PERMANENT v221 reference); block
               RL_PoL_origin; the relative-drift + collapse anchor.
  masterbot -> candidate (RL_Eval) vs MasterBot_SWF (an AB Playout player, NO NeuralNet); block
               RL_PoL_masterbot; the absolute-strength trend.

build_manifest takes an injectable runner (run_anchor) so all of this is verifiable WITHOUT the
C++ engine. run_anchor signature:
(dave_bin, block, player, weights_basename, opp_basename, opponent_player).
The masterbot opponent is no-NeuralNet -> its opponent-load check is SKIPPED (opp_basename=None,
no engine_confirmed_parent_load stamp).
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_eval


# ---------------------------------------------------------------------------
# collapse semantics (v4: point-estimate abort on origin-drift)
# ---------------------------------------------------------------------------

def test_collapse_flag_set_when_origin_below_threshold():
    from run_eval import compute_collapse
    assert compute_collapse({"win_rate": 0.30, "games": 96, "ci": [0.22, 0.39]}, threshold=0.35) is True
    assert compute_collapse({"win_rate": 0.52, "games": 96, "ci": [0.42, 0.62]}, threshold=0.35) is False
    assert compute_collapse(None, threshold=0.35) is None
    assert compute_collapse({"win_rate": 0.5, "games": 0, "ci": [0, 1]}, threshold=0.35) is None


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path, weights_file="cand.bin", player="RL_Eval"):
    """Minimal dave config.txt: Players.<player>.WeightsFile (provenance pre-flight) + the
    Tournament block lines set_block_run() flips (one block per line, like the real file)."""
    cfgdir = tmp_path / "asset" / "config"
    cfgdir.mkdir(parents=True, exist_ok=True)
    lines = [
        '{',
        f'"Players" : {{ "{player}" : {{ "WeightsFile":"{weights_file}", "TimeLimit":7000, "MaxTraversals":100000, "UCTConstant":0.3 }} }},',
        '"Benchmarks" : [',
        '{"run":false, "type":"Tournament", "name":"RL_PoL_origin",    "players":[]},',
        '{"run":false, "type":"Tournament", "name":"RL_PoL_masterbot", "players":[]}',
        ']',
        '}',
    ]
    (cfgdir / "config.txt").write_text("\n".join(lines), encoding="utf-8")


def _args(tmp_path, pools=("general",), config_weights="cand.bin",
          anchors=("origin", "masterbot"), origin_weights="origin.bin"):
    cfgdir = tmp_path / "asset" / "config"
    cfgdir.mkdir(parents=True, exist_ok=True)
    (cfgdir / "cand.bin").write_bytes(b"\x00\x01\x02\x03")   # sha256() reads this
    _write_config(tmp_path, weights_file=config_weights)
    return types.SimpleNamespace(
        iteration=3, weights="cand.bin",
        candidate_player="RL_Eval", candidate_label="RL_Eval",
        dave_bin=str(tmp_path), pools=list(pools),
        anchors=list(anchors), origin_weights=origin_weights,
        abort_winrate=0.35)


def _anchor(block, wins, n=128, draws=0, confirmed=True, parent_confirmed=True):
    """A flat anchor result dict shaped like run_anchor_block()'s success return,
    with a REAL Wilson CI derived from wins/draws/n. parent_confirmed=None omits the
    engine_confirmed_parent_load stamp entirely (the no-opponent-load masterbot case)."""
    p = run_eval.win_rate(wins, draws, n)
    lo, hi = run_eval.wilson_ci(p, n)
    out = {"block": block, "candidate": "RL_Eval", "wins": wins, "draws": draws,
           "games": n, "win_rate": p, "ci": [lo, hi], "engine_confirmed_load": confirmed}
    if parent_confirmed is not None:
        out["engine_confirmed_parent_load"] = parent_confirmed
    return out


ALL_BLOCKS = ("RL_PoL_origin", "RL_PoL_masterbot")


def _table_runner(table, calls=None):
    """run_anchor(dave_bin, block, player, weights_basename, opp_basename, opponent_player)
    -> pre-canned anchor dict."""
    def run_anchor(dave_bin, block, player, weights_basename, opp_basename,
                   opponent_player=None):
        if calls is not None:
            calls.append(block)
        assert block in table, f"unexpected block {block}"
        v = table[block]
        if isinstance(v, Exception):
            raise v
        return v
    return run_anchor


def _full_table(origin_anchor=None, masterbot_anchor=None):
    """Both v4 anchor blocks at parity unless an explicit cell is given. The masterbot opponent
    has NO NeuralNet, so its cell carries no parent-load stamp (parent_confirmed=None)."""
    origin = origin_anchor or _anchor("RL_PoL_origin", 64)
    if "block" not in origin:
        origin = dict(origin, block="RL_PoL_origin")
    else:
        origin = dict(origin); origin["block"] = "RL_PoL_origin"
    mb = masterbot_anchor or _anchor("RL_PoL_masterbot", 64, parent_confirmed=None)
    mb = dict(mb); mb["block"] = "RL_PoL_masterbot"
    return {"RL_PoL_origin": origin, "RL_PoL_masterbot": mb}


# ---------------------------------------------------------------------------
# collapse semantics in build_manifest (origin/general drives the flag)
# ---------------------------------------------------------------------------

def test_collapse_true_when_origin_general_below_threshold(tmp_path):
    # 38/128 = 29.7% < 0.35 -> collapse True.
    table = _full_table(origin_anchor=_anchor("RL_PoL_origin", 38))
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert m["collapse"] is True
    s = m["summary"]
    assert s["origin_win_rate"] == pytest.approx(38 / 128)
    assert s["origin_wr_ci"][0] < 38 / 128 < s["origin_wr_ci"][1]
    # the masterbot trend is recorded as information.
    assert "masterbot_win_rate" in s and "masterbot_wr_ci" in s
    # the old verdict machinery is gone.
    assert "verdict" not in m and "verdict_inputs" not in m and "decision" not in m


def test_collapse_false_at_parity(tmp_path):
    # 64/128 = 50% >= 0.35 -> collapse False.
    table = _full_table(origin_anchor=_anchor("RL_PoL_origin", 64))
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert m["collapse"] is False


def test_collapse_none_when_origin_anchor_errored(tmp_path):
    err = {"block": "RL_PoL_origin",
           "error": "no W/L/D for candidate 'RL_Eval' (degraded score-matrix fallback?)",
           "raw_players": []}
    table = _full_table(origin_anchor=err)
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert m["collapse"] is None


def test_collapse_none_when_origin_anchor_not_run(tmp_path):
    # masterbot only -> no origin general cell -> collapse cannot be decided.
    table = {"RL_PoL_masterbot": _anchor("RL_PoL_masterbot", 64, parent_confirmed=None)}
    m = run_eval.build_manifest(_args(tmp_path, anchors=("masterbot",)),
                                run_anchor=_table_runner(table))
    assert m["collapse"] is None


def test_custom_abort_winrate_threshold(tmp_path):
    # 60/128 = 46.9%: collapse False at the 0.35 default, True at a stricter 0.50 threshold.
    table = _full_table(origin_anchor=_anchor("RL_PoL_origin", 60))
    args = _args(tmp_path)
    args.abort_winrate = 0.50
    m = run_eval.build_manifest(args, run_anchor=_table_runner(table))
    assert m["collapse"] is True
    assert m["abort_winrate"] == 0.50


def test_no_gating_booleans_survive(tmp_path):
    table = _full_table()
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert "go_signal" not in m and "verdict" not in m


def test_dashboard_contract_headline_and_pools(tmp_path):
    table = _full_table(origin_anchor=_anchor("RL_PoL_origin", 77))  # 60.2%
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    # anchors[origin] is FLAT (general is the only/headline pool) + nests the general pool.
    assert m["anchors"]["origin"]["block"] == "RL_PoL_origin"
    assert set(m["anchors"]["origin"]["pools"]) == {"general"}
    assert set(m["anchors"]["masterbot"]["pools"]) == {"general"}
    assert m["candidate_net_sha256"]
    # no steam anchor in v4.
    assert "steam" not in m["anchors"]


def test_unknown_anchor_aborts(tmp_path):
    with pytest.raises(RuntimeError, match="unknown anchor"):
        run_eval.build_manifest(_args(tmp_path, anchors=("origin", "iter0")),
                                run_anchor=_table_runner({}))


# ---------------------------------------------------------------------------
# incremental manifest writes (a killed run must leave a readable manifest)
# ---------------------------------------------------------------------------

def test_incremental_manifest_survives_crash_after_first_anchor(tmp_path):
    table = _full_table()
    table["RL_PoL_masterbot"] = RuntimeError("simulated kill during masterbot anchor")
    mpath = str(tmp_path / "out" / "eval_iter_3.json")
    os.makedirs(os.path.dirname(mpath))
    with pytest.raises(RuntimeError, match="simulated kill"):
        run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table),
                                manifest_path=mpath)
    # The Jun-8 failure mode (4h of tournaments, empty manifests dir) is gone:
    assert os.path.exists(mpath)
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["complete"] is False
    assert m["anchors_completed"] == ["origin"]
    assert set(m["anchors"]["origin"]["pools"]) == {"general"}
    assert m["collapse"] is False   # collapse already computable from the completed origin


def test_final_manifest_marked_complete(tmp_path):
    table = _full_table()
    mpath = str(tmp_path / "eval_iter_3.json")
    run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table), manifest_path=mpath)
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["complete"] is True
    assert m["anchors_completed"] == ["origin", "masterbot"]
    # no torn-write temp file left behind (atomic write via os.replace)
    assert not [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]


def test_write_manifest_none_path_is_noop():
    run_eval.write_manifest({"k": 1}, None)   # must not raise


# ---------------------------------------------------------------------------
# active provenance — candidate net load
# ---------------------------------------------------------------------------

def test_config_weights_mismatch_aborts_before_any_tournament(tmp_path):
    table = _full_table()
    calls = []
    args = _args(tmp_path, config_weights="neural_weights_other.bin")  # config points elsewhere
    with pytest.raises(RuntimeError) as ei:
        run_eval.build_manifest(args, run_anchor=_table_runner(table, calls=calls))
    # hard abort names BOTH values, and NO tournament block was ever run
    assert "neural_weights_other.bin" in str(ei.value) and "cand.bin" in str(ei.value)
    assert calls == []


def test_config_missing_candidate_player_aborts(tmp_path):
    args = _args(tmp_path)
    args.candidate_player = "RL_Eval_NOT_THERE"
    with pytest.raises(RuntimeError, match="RL_Eval_NOT_THERE"):
        run_eval.build_manifest(args, run_anchor=_table_runner({}))


def test_self_match_origin_eval_aborts(tmp_path):
    # candidate == origin -> a vacuous self-match origin eval; must hard-abort.
    args = _args(tmp_path, origin_weights="cand.bin")
    with pytest.raises(RuntimeError, match="candidate-vs-itself"):
        run_eval.build_manifest(args, run_anchor=_table_runner({}))


def test_engine_confirmed_load_parses_stderr():
    ok = ("Some noise\n"
          "AIParameters: created per-player NeuralNet from asset/config/cand.bin\n"
          "more noise\n")
    assert run_eval.engine_confirmed_load(ok, "cand.bin") is True
    assert run_eval.engine_confirmed_load(ok, "other.bin") is False
    assert run_eval.engine_confirmed_load("", "cand.bin") is False
    # the basename alone in unrelated stderr noise is NOT a confirmation
    assert run_eval.engine_confirmed_load("loading cand.bin somehow\n", "cand.bin") is False


def test_engine_confirmed_load_player_level():
    """prov-06: with `player` given, the (player, basename) PAIR must share a line — many config
    players load the SAME reference bin, so a file-level match cannot tell WHICH player loaded it."""
    stderr = ("AIParameters: created per-player NeuralNet from asset/config/origin.bin for player 'RL_SelfPlay'\n"
              "AIParameters: created per-player NeuralNet from asset/config/cand.bin for player 'RL_Eval'\n")
    assert run_eval.engine_confirmed_load(stderr, "cand.bin", "RL_Eval") is True
    # origin.bin loaded — but NOT by the origin opponent: player-level says NO
    assert run_eval.engine_confirmed_load(stderr, "origin.bin", "RL_Eval_origin") is False
    assert run_eval.engine_confirmed_load(stderr, "origin.bin", "RL_SelfPlay") is True
    # pair must be on the SAME line (a name from one line + a file from another is no match)
    assert run_eval.engine_confirmed_load(stderr, "cand.bin", "RL_SelfPlay") is False


def test_unconfirmed_load_hard_fails_and_is_recorded(tmp_path):
    # the origin tournament COMPLETED but its stderr never confirmed the candidate net
    bad = _anchor("RL_PoL_origin", 64, confirmed=False)
    table = _full_table(origin_anchor=bad)
    mpath = str(tmp_path / "eval_iter_3.json")
    with pytest.raises(RuntimeError, match="engine_confirmed_load|never confirmed"):
        run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table),
                                manifest_path=mpath)
    # ...but the untrusted result is still recorded for the post-mortem
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["anchors"]["origin"]["pools"]["general"]["engine_confirmed_load"] is False
    assert m["complete"] is False


def test_run_anchor_block_stamps_engine_confirmed_load(tmp_path, monkeypatch):
    """End-to-end through run_anchor_block: stderr plumbing from run_cpp_tournament -> stamp."""
    _write_config(tmp_path)

    def fake_tournament(dave_bin, block_name, stderr_out=None, rounds_csv_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin for player 'RL_Eval'\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", fake_tournament)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_PoL_origin",
                                  "RL_Eval", weights_basename="cand.bin")
    assert a["engine_confirmed_load"] is True
    assert a["wins"] == 70 and a["draws"] == 2 and a["games"] == 128
    assert a["win_rate"] == pytest.approx((70 + 0.5 * 2) / 128)   # draw = half a win

    def silent_tournament(dave_bin, block_name, stderr_out=None, rounds_csv_out=None):
        if stderr_out is not None:
            stderr_out.append("no load line here\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", silent_tournament)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_PoL_origin",
                                  "RL_Eval", weights_basename="cand.bin")
    assert a["engine_confirmed_load"] is False


# ---------------------------------------------------------------------------
# active provenance — ORIGIN-opponent net load + the no-opponent masterbot case
# ---------------------------------------------------------------------------

def test_runner_receives_origin_basename_and_none_for_masterbot(tmp_path):
    """build_manifest threads basename(--origin-weights) to the origin anchor and None to the
    masterbot anchor (its AB-Playout opponent has no NeuralNet to confirm)."""
    seen = []

    def run_anchor(dave_bin, block, player, weights_basename, opp_basename,
                   opponent_player=None):
        seen.append((block, weights_basename, opp_basename, opponent_player))
        # mirror the no-parent-stamp shape for the masterbot opponent
        return _anchor(block, 64,
                       parent_confirmed=None if block == "RL_PoL_masterbot" else True)

    run_eval.build_manifest(_args(tmp_path), run_anchor=run_anchor)
    assert {b for b, _, _, _ in seen} == set(ALL_BLOCKS)
    assert all(w == "cand.bin" for _, w, _, _ in seen)
    opp = {b: (ob, op) for b, _, ob, op in seen}
    # origin anchor: opponent = RL_Eval_origin pinned to the origin bin
    assert opp["RL_PoL_origin"] == ("origin.bin", "RL_Eval_origin")
    # masterbot anchor: opponent = MasterBot_SWF, NO opponent-load basename (None)
    assert opp["RL_PoL_masterbot"] == (None, "MasterBot_SWF")


def test_unconfirmed_origin_load_hard_fails_and_is_recorded(tmp_path):
    # the origin tournament COMPLETED but its stderr never confirmed the ORIGIN net —
    # the drift comparison would be against the WRONG net.
    bad = _anchor("RL_PoL_origin", 64, parent_confirmed=False)
    table = _full_table(origin_anchor=bad)
    mpath = str(tmp_path / "eval_iter_3.json")
    with pytest.raises(RuntimeError, match="engine_confirmed_parent_load|WRONG net"):
        run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table),
                                manifest_path=mpath)
    # ...but the untrusted result is still recorded for the post-mortem
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["anchors"]["origin"]["pools"]["general"]["engine_confirmed_parent_load"] is False
    assert m["complete"] is False


def test_masterbot_missing_opponent_load_does_not_fail(tmp_path):
    """The masterbot opponent (MasterBot_SWF, AB Playout) has NO NeuralNet load line, so its
    anchor must NOT hard-fail for a missing opponent-load stamp — the run completes."""
    table = _full_table()  # masterbot cell carries no engine_confirmed_parent_load stamp
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert m["complete"] is True
    assert m["anchors_completed"] == ["origin", "masterbot"]
    # the masterbot pool has no parent-load stamp at all (no opponent net to confirm)
    assert "engine_confirmed_parent_load" not in m["anchors"]["masterbot"]["pools"]["general"]


def test_confirmed_origin_load_passes(tmp_path):
    """Both load lines present (the _anchor default) -> no provenance failure."""
    table = _full_table()
    m = run_eval.build_manifest(_args(tmp_path), run_anchor=_table_runner(table))
    assert m["complete"] is True
    assert m["anchors"]["origin"]["pools"]["general"]["engine_confirmed_parent_load"] is True


def test_run_anchor_block_stamps_engine_confirmed_parent_load(tmp_path, monkeypatch):
    """End-to-end through run_anchor_block: origin-opponent stderr line -> parent stamp."""
    _write_config(tmp_path)

    def both_loads(dave_bin, block_name, stderr_out=None, rounds_csv_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin for player 'RL_Eval'\n"
                "AIParameters: created per-player NeuralNet from asset/config/origin.bin for player 'RL_Eval_origin'\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", both_loads)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_PoL_origin", "RL_Eval",
                                  weights_basename="cand.bin", parent_basename="origin.bin",
                                  opponent_player="RL_Eval_origin")
    assert a["engine_confirmed_load"] is True
    assert a["engine_confirmed_parent_load"] is True

    def candidate_only(dave_bin, block_name, stderr_out=None, rounds_csv_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin for player 'RL_Eval'\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", candidate_only)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_PoL_origin", "RL_Eval",
                                  weights_basename="cand.bin", parent_basename="origin.bin",
                                  opponent_player="RL_Eval_origin")
    assert a["engine_confirmed_load"] is True
    assert a["engine_confirmed_parent_load"] is False

    # no parent_basename (the masterbot anchor: no opponent net) -> no parent stamp
    a = run_eval.run_anchor_block(str(tmp_path), "RL_PoL_masterbot", "RL_Eval",
                                  weights_basename="cand.bin")
    assert "engine_confirmed_parent_load" not in a
