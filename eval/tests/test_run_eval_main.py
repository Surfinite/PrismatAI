"""Unit tests for run_eval.build_manifest — orchestration, the REJECT/REVIEW/INCOMPLETE
verdict, incremental manifest writes, and active provenance.

VERDICT PHILOSOPHY (2026-06-10 audit): the old GO gate (d_rl >= +5pp AND forced ci_lower > 0.5)
was statistically incoherent at the configured 128 games — an observed +5pp needed 58.7% to fire,
so P(GO | true +5pp) ~ 13%. It is replaced by non-inferiority on the GENERAL pool (candidate vs
parent, unforced sets): REJECT iff Wilson ci_upper < 0.5 (proven worse), REVIEW otherwise
(human call), INCOMPLETE if the general anchor is missing/errored. d_rl/d_reg stay recorded as
information only.

build_manifest takes injectable runners (run_anchor / steam_fn) so all of this is verifiable
WITHOUT the C++ engine. run_anchor signature:
(dave_bin, block, player, weights_basename, parent_basename).
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import run_eval


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
        f'"Players" : {{ "{player}" : {{ "WeightsFile":"{weights_file}" }} }},',
        '"Benchmarks" : [',
        '{"run":false, "type":"Tournament", "name":"RL_Eval_iter0_forced",  "players":[]},',
        '{"run":false, "type":"Tournament", "name":"RL_Eval_iter0_general", "players":[]},',
        '{"run":false, "type":"Tournament", "name":"RL_Eval_narrow_forced",  "players":[]},',
        '{"run":false, "type":"Tournament", "name":"RL_Eval_narrow_general", "players":[]}',
        ']',
        '}',
    ]
    (cfgdir / "config.txt").write_text("\n".join(lines), encoding="utf-8")


def _args(tmp_path, pools=("forced", "general"), orig_present=False,
          config_weights="cand.bin"):
    cfgdir = tmp_path / "asset" / "config"
    cfgdir.mkdir(parents=True, exist_ok=True)
    (cfgdir / "cand.bin").write_bytes(b"\x00\x01\x02\x03")   # sha256() reads this
    _write_config(tmp_path, weights_file=config_weights)
    orig = tmp_path / "PrismataAI.exe.ORIG"
    if orig_present:
        orig.write_bytes(b"steam")
    return types.SimpleNamespace(
        iteration=3, weights="cand.bin", parent_weights="parent.bin",
        candidate_player="RL_Eval", candidate_label="RL_Eval",
        dave_bin=str(tmp_path), orig_exe=str(orig), steam_games=200, pools=list(pools))


def _anchor(block, wins, n=128, draws=0, confirmed=True, parent_confirmed=True):
    """A flat anchor result dict shaped like run_anchor_block()'s success return,
    with a REAL Wilson CI derived from wins/draws/n."""
    p = run_eval.win_rate(wins, draws, n)
    lo, hi = run_eval.wilson_ci(p, n)
    return {"block": block, "candidate": "RL_Eval", "wins": wins, "draws": draws,
            "games": n, "win_rate": p, "ci": [lo, hi], "engine_confirmed_load": confirmed,
            "engine_confirmed_parent_load": parent_confirmed}


ALL_BLOCKS = ("RL_Eval_iter0_forced", "RL_Eval_iter0_general",
              "RL_Eval_narrow_forced", "RL_Eval_narrow_general")


def _table_runner(table, calls=None):
    """run_anchor(dave_bin, block, player, weights_basename, parent_basename) -> pre-canned
    anchor dict."""
    def run_anchor(dave_bin, block, player, weights_basename, parent_basename):
        if calls is not None:
            calls.append(block)
        assert block in table, f"unexpected block {block}"
        v = table[block]
        if isinstance(v, Exception):
            raise v
        return v
    return run_anchor


def _full_table(general_anchor):
    """All four blocks at parity except the iter0/general gate cell."""
    t = {b: _anchor(b, 64) for b in ALL_BLOCKS}
    t["RL_Eval_iter0_general"] = general_anchor
    return t


# ---------------------------------------------------------------------------
# verdict semantics (REJECT / REVIEW / INCOMPLETE)
# ---------------------------------------------------------------------------

def test_reject_when_general_ci_upper_below_half(tmp_path):
    # 50/128 wins = 39.1% — Wilson 95% ci_upper ~ 0.477 < 0.5: proven worse than parent.
    table = _full_table(_anchor("RL_Eval_iter0_general", 50))
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["verdict"] == "REJECT"
    vi = m["verdict_inputs"]
    assert vi["general_ci_upper"] < 0.5
    # d_reg now carries a win-rate CI (audit: it was a bare point estimate). Keys are named
    # *_wr_ci because they bound the WIN RATE, not the -0.5-shifted delta.
    assert vi["d_reg_general"] == pytest.approx(50 / 128 - 0.5)
    assert vi["general_wr_ci"][0] < 50 / 128 < vi["general_wr_ci"][1]
    # d_rl stays recorded as information only.
    assert "d_rl_forced" in vi and "forced_wr_ci" in vi
    # The misleadingly-named delta-CI keys must not return (they held win-rate CIs).
    assert "d_rl_ci" not in vi and "d_reg_ci" not in vi
    assert m["decision"] == "(human call)"


def test_review_at_parity(tmp_path):
    # 64/128 = 50%: ci_upper >= 0.5 -> cannot prove harm -> human call.
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["verdict"] == "REVIEW"


def test_observed_plus5pp_is_review_not_reject(tmp_path):
    # 71/128 ~ 55.5% (the observed +5pp the OLD gate demanded but could never certify).
    # This INVERTS the old test at former line :96 (test_no_go_when_ci_straddles_half), which
    # encoded "+5pp observed but CI straddles 0.5 -> NO GO" as correct behavior. Under the new
    # detect-proven-harm semantics the same evidence is REVIEW — explicitly NOT a rejection — and
    # the promotion judgment belongs to the human.
    table = _full_table(_anchor("RL_Eval_iter0_general", 71))
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["verdict"] == "REVIEW"
    assert m["verdict"] != "REJECT"
    # the old gating booleans are gone — no automated GO/NO-GO survives.
    assert "go_signal" not in m


def test_incomplete_when_general_anchor_errored(tmp_path):
    err = {"block": "RL_Eval_iter0_general",
           "error": "no W/L/D for candidate 'RL_Eval' (degraded score-matrix fallback?)",
           "raw_players": []}
    table = _full_table(err)
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["verdict"] == "INCOMPLETE"


def test_incomplete_when_general_pool_not_run(tmp_path):
    table = {"RL_Eval_iter0_forced":  _anchor("RL_Eval_iter0_forced", 70),
             "RL_Eval_narrow_forced": _anchor("RL_Eval_narrow_forced", 64)}
    m = run_eval.build_manifest(_args(tmp_path, pools=("forced",)), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["verdict"] == "INCOMPLETE"


def test_general_only_pool_is_headline_and_verdict_pool(tmp_path):
    table = {"RL_Eval_iter0_general":  _anchor("RL_Eval_iter0_general", 68),
             "RL_Eval_narrow_general": _anchor("RL_Eval_narrow_general", 64)}
    m = run_eval.build_manifest(_args(tmp_path, pools=("general",)), steam_available=False,
                                run_anchor=_table_runner(table))
    # No forced pool requested -> headline falls back to general; verdict still computable.
    assert m["anchors"]["iter0"]["block"] == "RL_Eval_iter0_general"
    assert m["verdict"] == "REVIEW"


def test_dashboard_contract_headline_and_pools(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    table["RL_Eval_iter0_forced"] = _anchor("RL_Eval_iter0_forced", 77)  # 60.2%
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    # anchors[iter0] is FLAT (headline = forced pool) + has both pools nested.
    assert m["anchors"]["iter0"]["block"] == "RL_Eval_iter0_forced"
    assert set(m["anchors"]["iter0"]["pools"]) == {"forced", "general"}
    assert m["anchors"]["steam"]["status"].startswith("DEFERRED")
    assert m["candidate_net_sha256"]


# ---------------------------------------------------------------------------
# incremental manifest writes (a killed run must leave a readable manifest)
# ---------------------------------------------------------------------------

def test_incremental_manifest_survives_crash_after_first_anchor(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    table["RL_Eval_narrow_forced"] = RuntimeError("simulated kill during narrow anchor")
    mpath = str(tmp_path / "out" / "eval_iter_3.json")
    os.makedirs(os.path.dirname(mpath))
    with pytest.raises(RuntimeError, match="simulated kill"):
        run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table), manifest_path=mpath)
    # The Jun-8 failure mode (4h of tournaments, empty manifests dir) is gone:
    assert os.path.exists(mpath)
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["complete"] is False
    assert m["anchors_completed"] == ["iter0"]
    assert set(m["anchors"]["iter0"]["pools"]) == {"forced", "general"}
    assert m["verdict"] == "REVIEW"   # verdict already computable from the completed iter0


def test_steam_crash_preserves_earlier_anchors(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    mpath = str(tmp_path / "eval_iter_3.json")

    def exploding_steam(*a):
        raise RuntimeError("steam matchup crashed")

    with pytest.raises(RuntimeError, match="steam matchup crashed"):
        run_eval.build_manifest(_args(tmp_path, orig_present=True), steam_available=True,
                                run_anchor=_table_runner(table), steam_fn=exploding_steam,
                                manifest_path=mpath)
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["anchors_completed"] == ["iter0", "narrow"]
    assert m["verdict"] == "REVIEW"
    assert m["complete"] is False


def test_final_manifest_marked_complete(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    mpath = str(tmp_path / "eval_iter_3.json")
    run_eval.build_manifest(_args(tmp_path), steam_available=False,
                            run_anchor=_table_runner(table), manifest_path=mpath)
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["complete"] is True
    assert m["anchors_completed"] == ["iter0", "narrow"]   # steam DEFERRED -> never ran
    # no torn-write temp file left behind (atomic write via os.replace)
    assert not [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]


def test_steam_completion_recorded_in_anchors_completed(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    mpath = str(tmp_path / "eval_iter_3.json")
    m = run_eval.build_manifest(_args(tmp_path, orig_present=True), steam_available=True,
                                run_anchor=_table_runner(table),
                                steam_fn=lambda *a: (0.46, 200), manifest_path=mpath)
    assert m["anchors_completed"] == ["iter0", "narrow", "steam"]
    assert m["complete"] is True
    s = m["anchors"]["steam"]
    assert s["win_rate"] == pytest.approx(0.46) and s["games"] == 200
    assert s["ci"][0] <= 0.46 <= s["ci"][1]


def test_steam_unparsed_result_is_recorded_not_fatal(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    m = run_eval.build_manifest(_args(tmp_path, orig_present=True), steam_available=True,
                                run_anchor=_table_runner(table),
                                steam_fn=lambda *a: (None, 200))
    assert "error" in m["anchors"]["steam"] and m["anchors"]["steam"]["games"] == 200


def test_write_manifest_none_path_is_noop():
    run_eval.write_manifest({"k": 1}, None)   # must not raise


# ---------------------------------------------------------------------------
# active provenance
# ---------------------------------------------------------------------------

def test_config_weights_mismatch_aborts_before_any_tournament(tmp_path):
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    calls = []
    args = _args(tmp_path, config_weights="neural_weights_other.bin")  # config points elsewhere
    with pytest.raises(RuntimeError) as ei:
        run_eval.build_manifest(args, steam_available=False,
                                run_anchor=_table_runner(table, calls=calls))
    # hard abort names BOTH values, and NO tournament block was ever run
    assert "neural_weights_other.bin" in str(ei.value) and "cand.bin" in str(ei.value)
    assert calls == []


def test_config_missing_candidate_player_aborts(tmp_path):
    args = _args(tmp_path)
    args.candidate_player = "RL_Eval_NOT_THERE"
    with pytest.raises(RuntimeError, match="RL_Eval_NOT_THERE"):
        run_eval.build_manifest(args, steam_available=False,
                                run_anchor=_table_runner({}))


def test_engine_confirmed_load_parses_stderr():
    ok = ("Some noise\n"
          "AIParameters: created per-player NeuralNet from asset/config/cand.bin\n"
          "more noise\n")
    assert run_eval.engine_confirmed_load(ok, "cand.bin") is True
    assert run_eval.engine_confirmed_load(ok, "other.bin") is False
    assert run_eval.engine_confirmed_load("", "cand.bin") is False
    # the basename alone in unrelated stderr noise is NOT a confirmation
    assert run_eval.engine_confirmed_load("loading cand.bin somehow\n", "cand.bin") is False


def test_unconfirmed_load_hard_fails_and_is_recorded(tmp_path):
    # the iter0/general tournament COMPLETED but its stderr never confirmed the candidate net
    bad = _anchor("RL_Eval_iter0_general", 64, confirmed=False)
    table = _full_table(bad)
    mpath = str(tmp_path / "eval_iter_3.json")
    with pytest.raises(RuntimeError, match="engine_confirmed_load|never confirmed"):
        run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table), manifest_path=mpath)
    # ...but the untrusted result is still recorded for the post-mortem
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["anchors"]["iter0"]["pools"]["general"]["engine_confirmed_load"] is False
    assert m["complete"] is False


def test_run_anchor_block_stamps_engine_confirmed_load(tmp_path, monkeypatch):
    """End-to-end through run_anchor_block: stderr plumbing from run_cpp_tournament -> stamp."""
    _write_config(tmp_path)

    def fake_tournament(dave_bin, block_name, stderr_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", fake_tournament)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_Eval_iter0_general",
                                  "RL_Eval", weights_basename="cand.bin")
    assert a["engine_confirmed_load"] is True
    assert a["wins"] == 70 and a["draws"] == 2 and a["games"] == 128
    assert a["win_rate"] == pytest.approx((70 + 0.5 * 2) / 128)   # draw = half a win

    def silent_tournament(dave_bin, block_name, stderr_out=None):
        if stderr_out is not None:
            stderr_out.append("no load line here\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", silent_tournament)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_Eval_iter0_general",
                                  "RL_Eval", weights_basename="cand.bin")
    assert a["engine_confirmed_load"] is False


# ---------------------------------------------------------------------------
# active provenance — PARENT-net load (N-2: the verdict anchor's opponent)
# ---------------------------------------------------------------------------

def test_runner_receives_parent_basename(tmp_path):
    """build_manifest threads basename(--parent-weights) to the anchor runner (N-2)."""
    seen = []

    def run_anchor(dave_bin, block, player, weights_basename, parent_basename):
        seen.append((block, weights_basename, parent_basename))
        return _anchor(block, 64)

    run_eval.build_manifest(_args(tmp_path), steam_available=False, run_anchor=run_anchor)
    assert {b for b, _, _ in seen} == set(ALL_BLOCKS)
    assert all(w == "cand.bin" for _, w, _ in seen)
    assert all(p == "parent.bin" for _, _, p in seen)   # iter0 AND narrow opponents


def test_unconfirmed_parent_load_hard_fails_and_is_recorded(tmp_path):
    # the iter0/general (VERDICT) tournament COMPLETED but its stderr never confirmed
    # the PARENT net — the verdict would compare candidate vs the WRONG parent.
    bad = _anchor("RL_Eval_iter0_general", 64, parent_confirmed=False)
    table = _full_table(bad)
    mpath = str(tmp_path / "eval_iter_3.json")
    with pytest.raises(RuntimeError, match="engine_confirmed_parent_load|WRONG parent"):
        run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table), manifest_path=mpath)
    # ...but the untrusted result is still recorded for the post-mortem
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    assert m["anchors"]["iter0"]["pools"]["general"]["engine_confirmed_parent_load"] is False
    assert m["complete"] is False


def test_unconfirmed_parent_load_on_narrow_also_hard_fails(tmp_path):
    """RL_Narrow is parent-pinned too (non-gating, but same provenance contract)."""
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    table["RL_Eval_narrow_general"] = _anchor("RL_Eval_narrow_general", 64,
                                              parent_confirmed=False)
    with pytest.raises(RuntimeError, match="engine_confirmed_parent_load|WRONG parent"):
        run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))


def test_confirmed_parent_load_passes(tmp_path):
    """Both load lines present (the _anchor default) -> no provenance failure."""
    table = _full_table(_anchor("RL_Eval_iter0_general", 64))
    m = run_eval.build_manifest(_args(tmp_path), steam_available=False,
                                run_anchor=_table_runner(table))
    assert m["complete"] is True
    assert m["anchors"]["iter0"]["pools"]["general"]["engine_confirmed_parent_load"] is True


def test_run_anchor_block_stamps_engine_confirmed_parent_load(tmp_path, monkeypatch):
    """End-to-end through run_anchor_block: parent stderr line -> parent stamp."""
    _write_config(tmp_path)

    def both_loads(dave_bin, block_name, stderr_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin\n"
                "AIParameters: created per-player NeuralNet from asset/config/parent.bin\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", both_loads)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_Eval_iter0_general", "RL_Eval",
                                  weights_basename="cand.bin", parent_basename="parent.bin")
    assert a["engine_confirmed_load"] is True
    assert a["engine_confirmed_parent_load"] is True

    def candidate_only(dave_bin, block_name, stderr_out=None):
        if stderr_out is not None:
            stderr_out.append(
                "AIParameters: created per-player NeuralNet from asset/config/cand.bin\n")
        return {"RL_Eval": {"wins": 70, "draws": 2, "games": 128}}

    monkeypatch.setattr(run_eval, "run_cpp_tournament", candidate_only)
    a = run_eval.run_anchor_block(str(tmp_path), "RL_Eval_iter0_general", "RL_Eval",
                                  weights_basename="cand.bin", parent_basename="parent.bin")
    assert a["engine_confirmed_load"] is True
    assert a["engine_confirmed_parent_load"] is False

    # no parent_basename (ad-hoc use without --parent-weights) -> no parent stamp
    a = run_eval.run_anchor_block(str(tmp_path), "RL_Eval_iter0_general", "RL_Eval",
                                  weights_basename="cand.bin")
    assert "engine_confirmed_parent_load" not in a
