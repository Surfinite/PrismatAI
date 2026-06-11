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
                "SelfPlaySampling": True, "TemperatureTau": 0.7, "TemperatureK": 999, "EpsilonUniform": 0.0,
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
            {"run": False, "type": "Tournament", "name": "RL_Step2_Smoke", "rounds": 64,
             "players": [{"name": "RL_SelfPlay", "group": 1}, {"name": "RL_SelfPlay", "group": 2}]},
            {"run": False, "type": "Tournament", "name": "RL_Eval_iter0_general", "rounds": 64,
             "players": [{"name": "RL_Eval", "group": 1}, {"name": "RL_Eval", "group": 2}]},
        ],
    }


def make_frozen():
    return {
        "frozen_N": 1000,
        "TemperatureK": 999,
        "TemperatureTau": 0.7,
        "EpsilonUniform": 0.0,
        "EpsilonLate": 0.0,
        "UCTConstant": 0.3,
        "parent_bin": "neural_weights_mixed_v221.bin",
        "parent_pt": "training/models/deepsets_v221/swa_model.pt",
    }


@pytest.fixture
def env(tmp_path):
    """Write fixture config + frozen + every referenced file; return paths + dicts."""
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
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
    env["cfg"]["Benchmarks"][0]["run"] = True
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "run_true")
    assert "RL_Step2_Smoke" in out


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


def test_epsilon_late_present_fails_frozen_tuple(env, capsys):
    """The unguarded-drift review nit: EpsilonLate must be absent (or 0)."""
    env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"] = 0.1
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "EpsilonLate" in out


def test_epsilon_late_zero_is_ok(env, capsys):
    """Explicit 0 is tolerated (frozen json says 0.0; config convention is key-absent)."""
    env["cfg"]["Players"]["RL_SelfPlay"]["EpsilonLate"] = 0.0
    rc, out = run_main(env, capsys)
    assert rc == 0, out


def test_n_drift_fails_frozen_tuple(env, capsys):
    env["cfg"]["Players"]["RL_SelfPlay"]["MaxTraversals"] = 256
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "MaxTraversals" in out


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
