"""Tests for eval/preflight_config.py (stage-0 structural preflight).

Fixture strategy: a MINIMAL-but-valid config dict + frozen dict written under
tmp_path (never the real files), with every referenced file (weights bin,
parent .pt, data H5s) created as empty placeholders. Each mutation test
corrupts exactly one thing and asserts the RIGHT check fails (and that the
baseline passes cleanly). One end-to-end test runs the REAL config.txt +
campaign_frozen.json and expects exit 0 -- the deployed config must pass.
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preflight_config as pf


# ---------------------------------------------------------------------------
# Fixtures: minimal-but-valid config + frozen tuple
# ---------------------------------------------------------------------------

def make_config():
    """Minimal config that satisfies every preflight check."""
    ob_entry = {"self": [["Drone", 6], ["Engineer", 2]], "enemy": [], "buy": ["Drone", "Drone"]}
    return {
        "Opening Books": {
            "LiveOpeningBook2": [dict(ob_entry) for _ in range(50)],
            "DefaultOpeningBook": [dict(ob_entry) for _ in range(4)],
        },
        "Filters": {
            "IG_Only": {"default": False, "cards": ["Hotel", "Infusion Grid"]},
            "Ability_Filter_Live": {"default": False, "cards": ["Drake"]},
        },
        "Buy Limits": {
            "EconLimits": [["Engineer", 2]],
        },
        "Partial Players": {
            "DefenseSolver": {"type": "Defense_Solver"},
            "BreachGreedyKnapsack": {"type": "Breach_GreedyKnapsack"},
            "AbilityAttackDefaultLive": {"type": "ActionAbility_AttackDefault", "filter": "Ability_Filter_Live"},
            "BuyOpeningBook2": {"type": "ActionBuy_OpeningBook", "openingBook": "LiveOpeningBook2"},
            "BuyOpeningBook": {"type": "ActionBuy_OpeningBook", "openingBook": "DefaultOpeningBook"},
            "BuyEcon": {"type": "ActionBuy_Sequence", "buySequence": [["Drone", 3]], "buyLimits": "EconLimits"},
            # V5_CS2_NoIG reaches LiveOpeningBook2 transitively: -> V5_ACEasy2_NoIG -> BuyOpeningBook2
            "V5_ACEasy2_NoIG": {"type": "ActionAbility_Combination", "combination": ["AbilityAttackDefaultLive", "BuyOpeningBook2"]},
            "V5_CS2_NoIG": {"type": "ActionAbility_Combination", "combination": ["V5_ACEasy2_NoIG"]},
            "V5_CS_NoIG": {"type": "ActionAbility_Combination", "combination": ["BuyOpeningBook"]},
            "V5_CSNF_NoIG": {"type": "ActionAbility_Combination", "combination": ["BuyOpeningBook"]},
            "V5_CSClickNC_NoIG": {"type": "ActionAbility_Combination", "combination": ["BuyOpeningBook"]},
            "V5_CSClickNF_NoIG": {"type": "ActionAbility_Combination", "combination": ["BuyOpeningBook"]},
            "BuyEconTech": {"type": "ActionBuy_Combination", "combination": ["BuyEcon"]},
            "BuyTechEcon": {"type": "ActionBuy_Combination", "combination": ["BuyEcon"]},
            "BCGAttack_Root": {"type": "ActionBuy_Combination", "combination": ["BuyEcon"]},
            "BCGWill_Root": {"type": "ActionBuy_Combination", "combination": ["BuyEcon"]},
            "BCGDef_Root": {"type": "ActionBuy_Combination", "combination": ["BuyEcon"]},
        },
        "Move Iterators": {
            "HardIterator_5var_NoIG_Root": {
                "type": "PPPortfolio",
                "PartialPlayers": [
                    ["DefenseSolver"],
                    ["V5_CS2_NoIG", "V5_CS_NoIG", "V5_CSNF_NoIG", "V5_CSClickNC_NoIG", "V5_CSClickNF_NoIG"],
                    ["BuyEconTech", "BuyTechEcon", "BCGAttack_Root", "BCGWill_Root", "BCGDef_Root"],
                    ["BreachGreedyKnapsack"],
                ],
            },
            "HardIterator_5var_IGsubset_Root": {"type": "AbilitySubset", "include": "HardIterator_5var_NoIG_Root", "subsetFilter": "IG_Only"},
            "HardIterator_5var": {"type": "PPPortfolio", "PartialPlayers": [["DefenseSolver"], ["V5_CS_NoIG"], [], []]},
            "HardIterator_5var_Root": {"type": "PPPortfolio", "PartialPlayers": [["DefenseSolver"], ["V5_CS_NoIG"], [], []]},
        },
        "Players": {
            "Playout": {"type": "Player_PPSequence", "PartialPlayers": ["DefenseSolver", "V5_CS_NoIG", "BuyEconTech", "BreachGreedyKnapsack"]},
            "RL_SelfPlay": {
                "type": "Player_UCT", "TimeLimit": 0, "MaxChildren": 40, "MaxTraversals": 1000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
                "SelfPlaySampling": True, "TemperatureTau": 0.7, "TemperatureK": 12, "EpsilonUniform": 0.0,
                "EpsilonLate": 0.05,
            },
            "RL_Eval": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
            "RL_Eval_iter0": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
            "RL_Narrow": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
            # NOT parent-pinned -- the neutral player reference_graph mutations target so
            # parent_repin stays green (every RL_* player is now under parent_repin / N-2).
            "DSNN_Mixed35": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
        },
        "Benchmarks": [
            {"run": False, "type": "Tournament", "name": "RL_Step2_Smoke", "rounds": 21,
             "Threads": 8, "ForcedCards": ["Hotel"],
             "saveReplays": "asset/replays/rl_selfplay_forced",
             "players": [{"name": "RL_SelfPlay", "group": 1}, {"name": "RL_SelfPlay", "group": 2}]},
            {"run": False, "type": "Tournament", "name": "RL_SelfPlay_General", "rounds": 43,
             "Threads": 8,
             "saveReplays": "asset/replays/rl_selfplay_general",
             "players": [{"name": "RL_SelfPlay", "group": 1}, {"name": "RL_SelfPlay", "group": 2}]},
            {"run": False, "type": "Tournament", "name": "RL_Eval_iter0_general", "rounds": 64,
             "players": [{"name": "RL_Eval", "group": 1}, {"name": "RL_Eval", "group": 2}]},
        ],
    }


def make_frozen():
    return {
        "frozen_N": 1000,
        "TemperatureK": 12,
        "TemperatureTau": 0.7,
        "EpsilonUniform": 0.0,
        "EpsilonLate": 0.05,
        "UCTConstant": 0.3,
        "parent_bin": "neural_weights_mixed_v221.bin",
        "parent_pt": "training/models/deepsets_v221/swa_model.pt",
        "selfplay_threads": 8,
        "selfplay_mix": {"general_rounds": 43, "forced_rounds": 21, "forced_cards": ["Hotel"]},
    }


@pytest.fixture
def env(tmp_path):
    """Write fixture config + frozen + every referenced file; return paths + dicts.

    The config lives at <bin>/asset/config/config.txt, mirroring the real dave
    layout -- the use_dsnn_sentinel check (M-09) derives the engine bin dir from
    the config path, so the fixture must reproduce the nesting."""
    bin_dir = tmp_path / "bin"
    cfg_dir = bin_dir / "asset" / "config"
    cfg_dir.mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "training" / "models" / "deepsets_v221").mkdir(parents=True)
    (repo / "training" / "data").mkdir(parents=True)
    (repo / "training" / "models" / "deepsets_v221" / "swa_model.pt").write_bytes(b"pt")
    (repo / "training" / "data" / "human_val_1700_v2.h5").write_bytes(b"h5")
    (repo / "training" / "data" / "human_1800_v2.h5").write_bytes(b"h5")
    (cfg_dir / "neural_weights_mixed_v221.bin").write_bytes(b"DSN2")
    return {
        "config_path": cfg_dir / "config.txt",
        "frozen_path": tmp_path / "campaign_frozen.json",
        "repo": repo,
        "bin_dir": bin_dir,
        "cfg": make_config(),
        "frozen": make_frozen(),
    }


def run_main(env, capsys):
    """Serialize the (possibly mutated) dicts and run preflight main(). Returns (rc, out)."""
    env["config_path"].write_text(json.dumps(env["cfg"], indent=1), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"], indent=1), encoding="utf-8")
    rc = pf.main([
        "--config", str(env["config_path"]),
        "--frozen", str(env["frozen_path"]),
        "--repo-root", str(env["repo"]),
    ])
    out = capsys.readouterr().out
    return rc, out


def assert_only_fails(out, check_name):
    """All FAIL lines must belong to check_name (the mutation hit the RIGHT check)."""
    fail_lines = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    assert fail_lines, "expected at least one FAIL line:\n" + out
    for ln in fail_lines:
        assert ln.startswith("FAIL: %s:" % check_name), \
            "unexpected failure outside %s:\n%s" % (check_name, out)


# ---------------------------------------------------------------------------
# Baseline + real files
# ---------------------------------------------------------------------------

def test_baseline_fixture_passes(env, capsys):
    rc, out = run_main(env, capsys)
    assert rc == 0, out
    assert "FAIL" not in out


@pytest.mark.skipif(not os.path.exists(pf.DEFAULT_CONFIG), reason="dave-master config not on this machine")
def test_real_files_end_to_end(capsys):
    """The REAL deployed config.txt + campaign_frozen.json must pass preflight today."""
    rc = pf.main([])
    out = capsys.readouterr().out
    assert rc == 0, out


# ---------------------------------------------------------------------------
# Check 1: JSON / BOM
# ---------------------------------------------------------------------------

def test_bom_fails_json_bom(env, capsys):
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8-sig")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"])])
    out = capsys.readouterr().out
    assert rc == 1
    assert_only_fails(out, "json_bom")


def test_malformed_json_fails(env, capsys):
    env["config_path"].write_text("{ not json", encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"])])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL: json_bom:" in out


# ---------------------------------------------------------------------------
# Check 2: run:true
# ---------------------------------------------------------------------------

def test_run_true_block_fails(env, capsys):
    # Mutate the NON-self-play block: the two self-play blocks are also under the
    # frozen_tuple selfplay_mix run:false assertion, so only this one isolates run_true.
    env["cfg"]["Benchmarks"][2]["run"] = True
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "run_true")
    assert "RL_Eval_iter0_general" in out


def test_run_true_selfplay_block_fails_both_checks(env, capsys):
    """A run:true SELF-PLAY block trips run_true AND the frozen_tuple mix assertion."""
    env["cfg"]["Benchmarks"][0]["run"] = True
    rc, out = run_main(env, capsys)
    assert rc == 1
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    assert any(ln.startswith("FAIL: run_true:") for ln in fails), out
    assert any(ln.startswith("FAIL: frozen_tuple:") for ln in fails), out


# ---------------------------------------------------------------------------
# Check 3: iterator shape
# ---------------------------------------------------------------------------

def test_collapsed_noig_variants_fail_iterator_shape(env, capsys):
    """The crippled-iterator regression: 5 ActionAbility variants collapsed to 1."""
    env["cfg"]["Move Iterators"]["HardIterator_5var_NoIG_Root"]["PartialPlayers"][1] = ["V5_CS2_NoIG"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "iterator_shape")


def test_wrong_subset_filter_fails_iterator_shape(env, capsys):
    env["cfg"]["Move Iterators"]["HardIterator_5var_IGsubset_Root"]["subsetFilter"] = "Ability_Filter_Live"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "iterator_shape")


def test_ob_chain_break_fails_iterator_shape(env, capsys):
    """V5_CS2_NoIG must transitively reach LiveOpeningBook2."""
    env["cfg"]["Partial Players"]["V5_ACEasy2_NoIG"]["combination"] = ["AbilityAttackDefaultLive"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "iterator_shape")
    assert "LiveOpeningBook2" in out


# ---------------------------------------------------------------------------
# Check 4: book sizes
# ---------------------------------------------------------------------------

def test_book_49_entries_fails_book_sizes(env, capsys):
    env["cfg"]["Opening Books"]["LiveOpeningBook2"].pop()
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "book_sizes")
    assert "49" in out


# ---------------------------------------------------------------------------
# Check 5: reference graph
# ---------------------------------------------------------------------------

def test_unknown_filter_fails_reference_graph(env, capsys):
    env["cfg"]["Partial Players"]["AbilityAttackDefaultLive"]["filter"] = "No_Such_Filter"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "reference_graph")
    assert "No_Such_Filter" in out


def test_missing_weights_file_fails_reference_graph(env, capsys):
    # mutate the neutral non-RL player so parent_repin stays green -> isolates the check
    # (all four RL_* players are now under parent_repin / N-2)
    env["cfg"]["Players"]["DSNN_Mixed35"]["WeightsFile"] = "neural_weights_does_not_exist.bin"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "reference_graph")
    assert "neural_weights_does_not_exist.bin" in out


def test_unknown_partial_in_combination_fails_reference_graph(env, capsys):
    env["cfg"]["Partial Players"]["BuyEconTech"]["combination"] = ["No_Such_Partial"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "reference_graph")


def test_unknown_opening_book_fails_reference_graph(env, capsys):
    env["cfg"]["Partial Players"]["BuyOpeningBook"]["openingBook"] = "No_Such_Book"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "reference_graph")


def test_unknown_move_iterator_fails_reference_graph(env, capsys):
    env["cfg"]["Players"]["RL_SelfPlay"]["MoveIterator"] = "No_Such_Iterator"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "reference_graph")


# ---------------------------------------------------------------------------
# Check 6: frozen tuple
# ---------------------------------------------------------------------------

def test_tau_drift_fails_frozen_tuple(env, capsys):
    env["cfg"]["Players"]["RL_SelfPlay"]["TemperatureTau"] = 1.0
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "TemperatureTau" in out


def test_temperature_k_drift_fails_frozen_tuple(env, capsys):
    """Regime-v2 K drift: a config still on whole-game sampling (K=999) must fail."""
    env["cfg"]["Players"]["RL_SelfPlay"]["TemperatureK"] = 999
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "TemperatureK" in out


def test_epsilon_late_wrong_value_fails_frozen_tuple(env, capsys):
    """Regime v2: config EpsilonLate must EQUAL frozen (0.1 != 0.05)."""
    env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"] = 0.1
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "EpsilonLate" in out


def test_epsilon_late_absent_fails_frozen_tuple(env, capsys):
    """Regime v2: an ABSENT config key means 0.0 to the engine -- frozen 0.05 + absent
    would silently run pure-argmax past the opening window; must FAIL."""
    del env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "EpsilonLate" in out and "ABSENT" in out


def test_legacy_frozen_without_epsilon_late_absent_or_zero_ok(env, capsys):
    """Older frozen files (no EpsilonLate key) keep the absent-or-0 convention."""
    del env["frozen"]["EpsilonLate"]
    del env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"]
    rc, out = run_main(env, capsys)
    assert rc == 0, out
    env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"] = 0.0
    rc, out = run_main(env, capsys)
    assert rc == 0, out


def test_legacy_frozen_without_epsilon_late_nonzero_config_fails(env, capsys):
    """Older frozen files: a present NONZERO config key still fails (old rule)."""
    del env["frozen"]["EpsilonLate"]
    env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"] = 0.05
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "EpsilonLate" in out


def test_n_drift_fails_frozen_tuple(env, capsys):
    env["cfg"]["Players"]["RL_SelfPlay"]["MaxTraversals"] = 256
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "MaxTraversals" in out


def test_general_block_missing_fails_frozen_tuple(env, capsys):
    """selfplay_mix: the 2/3 general (unforced) block must exist. Since the
    2026-06-12 replay-archive contract, a missing block correctly fails BOTH
    frozen_tuple (selfplay_mix) and selfplay_replays (7b)."""
    env["cfg"]["Benchmarks"] = [b for b in env["cfg"]["Benchmarks"]
                                if b["name"] != "RL_SelfPlay_General"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert "FAIL: frozen_tuple" in out
    assert "FAIL: selfplay_replays" in out
    assert "RL_SelfPlay_General" in out


def test_general_block_with_forced_cards_fails_frozen_tuple(env, capsys):
    """selfplay_mix: ForcedCards on the GENERAL block would silently force 100% Hotel."""
    env["cfg"]["Benchmarks"][1]["ForcedCards"] = ["Hotel"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "RL_SelfPlay_General" in out and "ForcedCards" in out


def test_forced_rounds_mismatch_fails_frozen_tuple(env, capsys):
    """selfplay_mix: rounds drift on the forced block breaks the 2/3:1/3 mix."""
    env["cfg"]["Benchmarks"][0]["rounds"] = 64
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "forced_rounds" in out


def test_general_rounds_mismatch_fails_frozen_tuple(env, capsys):
    """selfplay_mix: rounds drift on the general block breaks the 2/3:1/3 mix."""
    env["cfg"]["Benchmarks"][1]["rounds"] = 10
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "general_rounds" in out


def test_forced_cards_drift_fails_frozen_tuple(env, capsys):
    """selfplay_mix: the forced block must force exactly the frozen forced_cards."""
    env["cfg"]["Benchmarks"][0]["ForcedCards"] = ["Drake"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "forced_cards" in out


def test_general_block_threads_drift_fails_frozen_tuple(env, capsys):
    """selfplay_threads now covers BOTH self-play blocks."""
    env["cfg"]["Benchmarks"][1]["Threads"] = 1
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "RL_SelfPlay_General.Threads" in out


def test_missing_save_replays_fails_selfplay_replays(env, capsys):
    """7b (2026-06-12): the per-iteration replay archive is part of the iteration
    contract — a dropped/drifted saveReplays key must fail at stage 0, not after
    the full self-play run (stage 1.5 would otherwise be the first to notice)."""
    del env["cfg"]["Benchmarks"][1]["saveReplays"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "selfplay_replays")
    assert "RL_SelfPlay_General.saveReplays" in out


def test_drifted_save_replays_dir_fails_selfplay_replays(env, capsys):
    env["cfg"]["Benchmarks"][0]["saveReplays"] = "asset/replays/somewhere_else"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "selfplay_replays")
    assert "RL_Step2_Smoke.saveReplays" in out


# ---------------------------------------------------------------------------
# Check 7: parent re-pin (F-07 + N-2: ALL FOUR parent-side players)
# ---------------------------------------------------------------------------

def _mispoint(env, player, bin_name="neural_weights_stale_parent.bin"):
    """Point one player at an existing-but-wrong bin (file EXISTS so reference_graph
    stays green and the mutation isolates parent_repin)."""
    (env["config_path"].parent / bin_name).write_bytes(b"DSN2")
    env["cfg"]["Players"][player]["WeightsFile"] = bin_name


def test_rl_eval_candidate_bin_fails_parent_repin(env, capsys):
    """A killed iteration that left RL_Eval on the candidate bin must be caught."""
    _mispoint(env, "RL_Eval", "neural_weights_rl_iter1.bin")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_Eval.WeightsFile" in out
    assert "neural_weights_rl_iter1.bin" in out


def test_rl_eval_iter0_mispointed_fails_parent_repin(env, capsys):
    """N-2: the VERDICT OPPONENT left on a grandparent net after a forgotten
    post-promotion repoint must be caught -- only parent_repin, naming the player."""
    _mispoint(env, "RL_Eval_iter0")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_Eval_iter0" in out and "neural_weights_stale_parent.bin" in out
    assert sum(1 for ln in out.splitlines() if ln.startswith("FAIL:")) == 1


def test_rl_selfplay_mispointed_fails_parent_repin(env, capsys):
    """N-2: the self-play DATA GENERATOR must carry the frozen parent net."""
    _mispoint(env, "RL_SelfPlay")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_SelfPlay" in out
    assert sum(1 for ln in out.splitlines() if ln.startswith("FAIL:")) == 1


def test_rl_narrow_mispointed_fails_parent_repin(env, capsys):
    """N-2: the iterator-only anchor's net must equal the parent's or it stops
    isolating the iterator variable."""
    _mispoint(env, "RL_Narrow")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_Narrow" in out
    assert sum(1 for ln in out.splitlines() if ln.startswith("FAIL:")) == 1


def test_missing_parent_pinned_player_fails_parent_repin(env, capsys):
    """A parent-pinned player missing entirely from the config is a parent_repin failure."""
    del env["cfg"]["Players"]["RL_Narrow"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_Narrow" in out


# ---------------------------------------------------------------------------
# Check 8: existences
# ---------------------------------------------------------------------------

def test_missing_parent_pt_fails_existences(env, capsys):
    (env["repo"] / "training" / "models" / "deepsets_v221" / "swa_model.pt").unlink()
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "existences")
    assert "swa_model.pt" in out


def test_missing_val_h5_fails_existences(env, capsys):
    (env["repo"] / "training" / "data" / "human_val_1700_v2.h5").unlink()
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "existences")


# ---------------------------------------------------------------------------
# Check 9: use_dsnn sentinel (M-09 contamination guard)
# ---------------------------------------------------------------------------

def test_use_dsnn_sentinel_fails(env, capsys):
    """Touching <bin>/use_dsnn.txt must fail ONLY the sentinel check -- the
    FORCE_DSNN drop-in silently swaps the net on every protocol-path engine
    call (query_move / tactical suite / coverage = stages 6/8)."""
    (env["bin_dir"] / "use_dsnn.txt").write_text("", encoding="utf-8")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "use_dsnn_sentinel")
    assert "use_dsnn.txt" in out
    assert "FORCE_DSNN" in out


def test_use_dsnn_sentinel_only_checks_bin_dir(env, capsys):
    """A use_dsnn.txt elsewhere (e.g. the config dir) must NOT trip the check --
    the engine only probes next to the exe."""
    (env["config_path"].parent / "use_dsnn.txt").write_text("", encoding="utf-8")
    rc, out = run_main(env, capsys)
    assert rc == 0, out


# ---------------------------------------------------------------------------
# --quiet
# ---------------------------------------------------------------------------

def test_quiet_suppresses_ok_lines(env, capsys):
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK:" not in out


def test_quiet_still_prints_failures(env, capsys):
    env["cfg"]["Benchmarks"][0]["run"] = True
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--quiet"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL: run_true:" in out
