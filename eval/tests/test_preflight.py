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
            # v4: the interior (response/rollout) iterator -- NoIG single-variant portfolio.
            "HardIterator_5var_NoIG": {"type": "PPPortfolio", "PartialPlayers": [[], ["V5_CS_NoIG"], [], []]},
            "HardIterator_5var": {"type": "PPPortfolio", "PartialPlayers": [["DefenseSolver"], ["V5_CS_NoIG"], [], []]},
            "HardIterator_5var_Root": {"type": "PPPortfolio", "PartialPlayers": [["DefenseSolver"], ["V5_CS_NoIG"], [], []]},
        },
        "Players": {
            "Playout": {"type": "Player_PPSequence", "PartialPlayers": ["DefenseSolver", "V5_CS_NoIG", "BuyEconTech", "BreachGreedyKnapsack"]},
            "RL_SelfPlay": {
                "type": "Player_UCT", "TimeLimit": 0, "MaxChildren": 40, "MaxTraversals": 1000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var_NoIG",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
                "SelfPlaySampling": True, "TemperatureTau": 0.7, "TemperatureK": 12, "EpsilonUniform": 0.0,
                "EpsilonLate": 0.05, "EpsilonIG": 0.0,
            },
            "RL_Eval": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var_NoIG",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
            "RL_Eval_origin": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var_NoIG",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
            # NOT parent-pinned / NOT interior-checked -- the neutral player reference_graph
            # mutations target so parent_repin / iterator_shape stay green (it isolates the
            # mutated check). v4 parent_repin set = {RL_Eval, RL_SelfPlay}.
            "DSNN_Mixed35": {
                "type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
                "RootMoveIterator": "HardIterator_5var_IGsubset_Root", "MoveIterator": "HardIterator_5var",
                "Eval": "NeuralNet", "WeightsFile": "neural_weights_mixed_v221.bin", "UCTConstant": 0.3,
            },
        },
        "Benchmarks": [
            # v4 self-play = ONE general block; check 7b validates only it. (The real
            # config keeps a dead RL_Step2_Smoke block, but 7b no longer requires it, so
            # the fixture omits it.)
            {"run": False, "type": "Tournament", "name": "RL_SelfPlay_General", "rounds": 516,
             "Seed": 5600, "Threads": 8,
             "saveReplays": "asset/replays/rl_selfplay_general",
             "players": [{"name": "RL_SelfPlay", "group": 1}, {"name": "RL_SelfPlay", "group": 2}]},
            {"run": False, "type": "Tournament", "name": "RL_PoL_origin", "rounds": 48,
             "Seed": 2026, "Threads": 8,
             "players": [{"name": "RL_Eval", "group": 1}, {"name": "RL_Eval_origin", "group": 2}]},
            {"run": False, "type": "Tournament", "name": "RL_PoL_masterbot", "rounds": 48,
             "Seed": 2026, "Threads": 8,
             "players": [{"name": "RL_Eval", "group": 1}, {"name": "RL_Eval", "group": 2}]},
            # A neutral legacy run:false block (not self-play, not an anchor) so the
            # run_true mutation test can isolate check 2 alone.
            {"run": False, "type": "Tournament", "name": "Legacy_Smoke", "rounds": 4,
             "players": [{"name": "RL_Eval", "group": 1}, {"name": "RL_Eval", "group": 2}]},
        ],
    }


def make_frozen():
    return {
        "tuple_version": 4,
        "frozen_N": 1000,
        "TemperatureK": 12,
        "TemperatureTau": 0.7,
        "EpsilonUniform": 0.0,
        "EpsilonLate": 0.05,
        "EpsilonIG": 0.0,
        "UCTConstant": 0.3,
        "parent_bin": "neural_weights_mixed_v221.bin",
        "parent_pt": "training/models/deepsets_v221/swa_model.pt",
        "origin_bin": "neural_weights_mixed_v221.bin",
        "selfplay_threads": 8,
        "selfplay_block": "RL_SelfPlay_General",
        "selfplay_rounds": 516,
        "selfplay_seed_base": 5600,
        "candidate_interior_iterator": "HardIterator_5var_NoIG",
        "eval_budget": {"TimeLimit": 7000, "MaxTraversals": 100000, "UCTConstant": 0.3},
        "anchor_blocks": {
            "RL_PoL_origin": {"rounds": 48, "Seed": 2026, "Threads": 8},
            "RL_PoL_masterbot": {"rounds": 48, "Seed": 2026, "Threads": 8},
        },
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
    # 2026-06-13: the unit_index check (impl-unitindex-05) requires the canonical 116-unit
    # index next to the config.
    (cfg_dir / "unit_index.json").write_text(json.dumps({"count": 116, "units": {}}),
                                             encoding="utf-8")
    return {
        "config_path": cfg_dir / "config.txt",
        "frozen_path": tmp_path / "campaign_frozen.json",
        "repo": repo,
        "bin_dir": bin_dir,
        "cfg": make_config(),
        "frozen": make_frozen(),
    }


def run_main(env, capsys):
    """Serialize the (possibly mutated) dicts and run preflight main(). Returns (rc, out).

    Passes --skip-slow-gates: the a6 + three-way correctness gates shell out to the
    engine + pytest (~30-60s each) and need the real dave-master engine; unit tests
    of the config/frozen checks must not depend on them. The engine-exe sha pin is
    fast and still runs (these tmp fixtures carry no engine exes, so the frozen
    engine_*_exe_sha256 keys are omitted from make_frozen())."""
    env["config_path"].write_text(json.dumps(env["cfg"], indent=1), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"], indent=1), encoding="utf-8")
    rc = pf.main([
        "--config", str(env["config_path"]),
        "--frozen", str(env["frozen_path"]),
        "--repo-root", str(env["repo"]),
        "--skip-slow-gates",
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
    """The REAL deployed config.txt + campaign_frozen.json must pass preflight today.

    Runs --skip-slow-gates so the unit suite stays fast + engine-independent: this
    exercises the structural checks + the fast engine-exe sha pin against the real
    frozen tuple. The a6 + three-way correctness gates are exercised by the FULL
    live preflight (run standalone, NOT via this unit suite)."""
    rc = pf.main(["--skip-slow-gates"])
    out = capsys.readouterr().out
    assert rc == 0, out


# ---------------------------------------------------------------------------
# Check 1: JSON / BOM
# ---------------------------------------------------------------------------

def test_bom_fails_json_bom(env, capsys):
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8-sig")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--skip-slow-gates"])
    out = capsys.readouterr().out
    assert rc == 1
    assert_only_fails(out, "json_bom")


def test_malformed_json_fails(env, capsys):
    env["config_path"].write_text("{ not json", encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--skip-slow-gates"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL: json_bom:" in out


# ---------------------------------------------------------------------------
# Check 2: run:true
# ---------------------------------------------------------------------------

def test_run_true_block_fails(env, capsys):
    # Mutate the neutral legacy block: the self-play block (frozen_tuple run:false)
    # and the anchor blocks (anchor_blocks run:false) trip a second check, so only
    # the legacy block isolates run_true. Index by name to stay robust to reordering.
    legacy = next(b for b in env["cfg"]["Benchmarks"] if b["name"] == "Legacy_Smoke")
    legacy["run"] = True
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "run_true")
    assert "Legacy_Smoke" in out


def test_run_true_selfplay_block_fails_both_checks(env, capsys):
    """A run:true SELF-PLAY block trips run_true AND the frozen_tuple block assertion."""
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


def test_interior_iterator_reverted_fails_iterator_shape(env, capsys):
    """v4: a candidate's INTERIOR MoveIterator must be HardIterator_5var_NoIG.
    Flipping RL_Eval back to the legacy HardIterator_5var (which auto-fires IG
    below root) must fail iterator_shape and name the expected NoIG iterator."""
    env["cfg"]["Players"]["RL_Eval"]["MoveIterator"] = "HardIterator_5var"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "iterator_shape")
    assert "HardIterator_5var_NoIG" in out


def test_interior_iterator_wrong_portfolio_fails_iterator_shape(env, capsys):
    """v4: HardIterator_5var_NoIG must be the [[], ['V5_CS_NoIG'], [], []] portfolio."""
    env["cfg"]["Move Iterators"]["HardIterator_5var_NoIG"]["PartialPlayers"] = \
        [["DefenseSolver"], ["V5_CS_NoIG"], [], []]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "iterator_shape")
    assert "HardIterator_5var_NoIG" in out


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
    # mutate the neutral non-RL player: the candidate-side players' MoveIterator is now
    # also under the v4 iterator_shape interior check, so only DSNN_Mixed35 isolates this.
    env["cfg"]["Players"]["DSNN_Mixed35"]["MoveIterator"] = "No_Such_Iterator"
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


def test_selfplay_block_missing_fails_frozen_tuple(env, capsys):
    """v4: the ONE self-play block (frozen selfplay_block) must exist. Removing it
    fails BOTH frozen_tuple (the block lookup) and selfplay_replays (7b)."""
    env["cfg"]["Benchmarks"] = [b for b in env["cfg"]["Benchmarks"]
                                if b["name"] != "RL_SelfPlay_General"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert "FAIL: frozen_tuple" in out
    assert "FAIL: selfplay_replays" in out
    assert "RL_SelfPlay_General" in out


def test_selfplay_block_with_forced_cards_fails_frozen_tuple(env, capsys):
    """v4: the self-play block must have NO ForcedCards (proof-of-life is unforced)."""
    env["cfg"]["Benchmarks"][0]["ForcedCards"] = ["Hotel"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "RL_SelfPlay_General" in out and "ForcedCards" in out


def test_selfplay_rounds_mismatch_fails_frozen_tuple(env, capsys):
    """v4: rounds drift on the self-play block must fail against frozen selfplay_rounds."""
    env["cfg"]["Benchmarks"][0]["rounds"] = 64
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "selfplay_rounds" in out


def test_selfplay_seed_drift_fails_frozen_tuple(env, capsys):
    """v4: the self-play block must REST at frozen selfplay_seed_base (the driver
    sets base+K transiently and restores it; a killed run mustn't leave a drift)."""
    env["cfg"]["Benchmarks"][0]["Seed"] = 5601
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "selfplay_seed_base" in out


def test_selfplay_block_threads_drift_fails_frozen_tuple(env, capsys):
    """v4: selfplay_threads covers the single self-play block."""
    env["cfg"]["Benchmarks"][0]["Threads"] = 1
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "frozen_tuple")
    assert "RL_SelfPlay_General.Threads" in out


def test_missing_save_replays_fails_selfplay_replays(env, capsys):
    """7b (2026-06-12): the per-iteration replay archive is part of the iteration
    contract — a dropped/drifted saveReplays key must fail at stage 0, not after
    the full self-play run (stage 1.5 would otherwise be the first to notice)."""
    del env["cfg"]["Benchmarks"][0]["saveReplays"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "selfplay_replays")
    assert "RL_SelfPlay_General.saveReplays" in out


def test_drifted_save_replays_dir_fails_selfplay_replays(env, capsys):
    # A present-but-wrong saveReplays dir on the v4 self-play block must also fail 7b.
    env["cfg"]["Benchmarks"][0]["saveReplays"] = "asset/replays/somewhere_else"
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "selfplay_replays")
    assert "RL_SelfPlay_General.saveReplays" in out


# ---------------------------------------------------------------------------
# Check 7: parent re-pin (F-07 + N-2; v4 set = RL_Eval + RL_SelfPlay)
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


def test_rl_selfplay_mispointed_fails_parent_repin(env, capsys):
    """N-2: the self-play DATA GENERATOR must carry the frozen parent net."""
    _mispoint(env, "RL_SelfPlay")
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "parent_repin")
    assert "RL_SelfPlay" in out
    assert sum(1 for ln in out.splitlines() if ln.startswith("FAIL:")) == 1


def test_missing_parent_pinned_player_fails_parent_repin(env, capsys):
    """A parent-pinned player missing entirely from the config is a parent_repin failure.

    Deleting RL_SelfPlay also trips the interior + frozen-tuple checks, so assert that
    parent_repin is among the failures and names RL_SelfPlay (rather than assert_only_fails)."""
    del env["cfg"]["Players"]["RL_SelfPlay"]
    rc, out = run_main(env, capsys)
    assert rc == 1
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    assert any(ln.startswith("FAIL: parent_repin:") and "RL_SelfPlay" in ln for ln in fails), out


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
# Check 10: engine-exe sha pin (Task 5/10) -- guards against an unrecorded
# rebuild silently flipping the value sign or a feature. Tested directly (the
# tmp fixtures carry no engine exes, so make_frozen() omits the sha keys and the
# end-to-end fixture path exercises only the no-op branch).
# ---------------------------------------------------------------------------

def test_engine_sha_mismatch_fires(tmp_path):
    """A pinned sha that does not match the on-disk exe must surface a failure."""
    exe = tmp_path / "Prismata_Testing.exe"
    exe.write_bytes(b"some engine bytes")
    failures = pf.check_engine_sha({"engine_testing_exe_sha256": "deadbeef"}, str(tmp_path))
    assert failures, "expected a failure for the mismatched sha"
    assert any("sha256 mismatch" in f for f in failures), failures
    assert any("Prismata_Testing.exe" in f for f in failures), failures


def test_engine_sha_match_passes(tmp_path):
    """The matching sha (and the absent-key no-op) must produce no failures."""
    exe = tmp_path / "PrismataAI.exe"
    content = b"matching engine bytes"
    exe.write_bytes(content)
    want = pf._sha256(str(exe))
    # exact match -> clean; mixed case in the pin still matches (.lower() both sides)
    assert pf.check_engine_sha({"engine_prismataai_exe_sha256": want.upper()}, str(tmp_path)) == []
    # absent key -> no-op (older frozen files without the pin)
    assert pf.check_engine_sha({}, str(tmp_path)) == []


def test_engine_sha_missing_exe_fires(tmp_path):
    """A pinned exe that is not on disk must fail (not silently pass)."""
    failures = pf.check_engine_sha({"engine_testing_exe_sha256": "deadbeef"}, str(tmp_path))
    assert failures
    assert any("engine exe not found" in f for f in failures), failures


def test_engine_sha_mismatch_via_run_checks(env, capsys, tmp_path):
    """run_checks wires engine_sha when frozen carries a pin: a mismatched pin +
    an on-disk exe (the fixture bin dir) must surface a FAIL: engine_sha line.
    --skip-slow-gates keeps the correctness gates out of this unit test."""
    (env["bin_dir"] / "Prismata_Testing.exe").write_bytes(b"fixture engine bytes")
    env["frozen"]["engine_testing_exe_sha256"] = "deadbeef"
    rc, out = run_main(env, capsys)
    assert rc == 1
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL:")]
    assert any(ln.startswith("FAIL: engine_sha:") and "sha256 mismatch" in ln for ln in fails), out


# ---------------------------------------------------------------------------
# Check 11: correctness gates -- skip-slow-gates semantics. The gates shell out
# to the engine + pytest, so the unit suite asserts the SKIP path omits them and
# the wiring path includes a correctness_gates result (called directly so the
# engine is never launched here).
# ---------------------------------------------------------------------------

def test_skip_slow_gates_omits_correctness_gates(env, capsys):
    """With --skip-slow-gates the correctness_gates check must not appear at all
    (it would otherwise shell out to the engine + pytest)."""
    rc, out = run_main(env, capsys)  # run_main passes --skip-slow-gates
    assert rc == 0, out
    assert "correctness_gates" not in out


# ---------------------------------------------------------------------------
# Check M2: selfplay_player — self-play block uses RL_SelfPlay + SelfPlaySampling
#           + IG-subset root iterator
# ---------------------------------------------------------------------------

def test_selfplay_block_must_use_rl_selfplay(env):
    """Both group slots of the frozen self-play block must reference RL_SelfPlay.
    Swapping them to a different player name must surface a selfplay_player failure."""
    b = next(x for x in env["cfg"]["Benchmarks"] if x["name"] == "RL_SelfPlay_General")
    b["players"] = [{"name": "RL_SelfPlay_N100", "group": 1}, {"name": "RL_SelfPlay_N100", "group": 2}]
    # minimal frozen -- only selfplay_block matters for this check (isolates the block-lookup path)
    fails = pf.check_selfplay_player(env["cfg"], {"selfplay_block": "RL_SelfPlay_General"})
    assert any("RL_SelfPlay" in f for f in fails)


def test_selfplay_player_missing_sampling_fails(env):
    """SelfPlaySampling must be True; absent or False means Temperature/Epsilon are inert."""
    env["cfg"]["Players"]["RL_SelfPlay"]["SelfPlaySampling"] = False
    fails = pf.check_selfplay_player(env["cfg"], env["frozen"])
    assert any("SelfPlaySampling" in f for f in fails)


def test_selfplay_player_wrong_root_iterator_fails(env):
    """RootMoveIterator on RL_SelfPlay must be the IG-subset root."""
    env["cfg"]["Players"]["RL_SelfPlay"]["RootMoveIterator"] = "HardIterator_5var_Root"
    fails = pf.check_selfplay_player(env["cfg"], env["frozen"])
    assert any(pf.RL_ROOT_ITERATOR in f for f in fails)


def test_selfplay_player_missing_block_fails(env):
    """A selfplay_block name that does not exist in Benchmarks must fail cleanly."""
    fails = pf.check_selfplay_player(env["cfg"], {"selfplay_block": "No_Such_Block"})
    assert any("No_Such_Block" in f for f in fails)


def test_selfplay_player_end_to_end_fails(env, capsys):
    """Wiring check: mutate both group slots to a non-RL_SelfPlay player and confirm
    the selfplay_player check is the ONLY check that fires (end-to-end via run_main)."""
    b = next(x for x in env["cfg"]["Benchmarks"] if x["name"] == "RL_SelfPlay_General")
    b["players"] = [{"name": "RL_SelfPlay_N100", "group": 1}, {"name": "RL_SelfPlay_N100", "group": 2}]
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "selfplay_player")


# ---------------------------------------------------------------------------
# --quiet
# ---------------------------------------------------------------------------

def test_quiet_suppresses_ok_lines(env, capsys):
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--quiet", "--skip-slow-gates"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK:" not in out


def test_quiet_still_prints_failures(env, capsys):
    env["cfg"]["Benchmarks"][0]["run"] = True
    env["config_path"].write_text(json.dumps(env["cfg"]), encoding="utf-8")
    env["frozen_path"].write_text(json.dumps(env["frozen"]), encoding="utf-8")
    rc = pf.main(["--config", str(env["config_path"]), "--frozen", str(env["frozen_path"]),
                  "--repo-root", str(env["repo"]), "--quiet", "--skip-slow-gates"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL: run_true:" in out
