"""Tests for eval/stalemate.py — the stalemate-detection oracle + the 3-game calibration."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stalemate import StalemateTracker, scan_replay, load_replay  # noqa: E402

REPLAY_DIR = r"C:/libraries/PrismataAI/training/data/rl_iter_1/replays/general"
# (last_progress_ply, fire_ply) at threshold=40, measured during the brainstorm calibration.
GAMES = {"game_0171": (59, 99), "game_0383": (50, 90), "game_0818": (54, 94)}


def test_frozen_run_fires_at_threshold():
    tr = StalemateTracker(threshold=3)
    a = {(0, "Drone"): 1}
    fired = [tr.observe(a, p) for p in range(5)]
    assert fired == [False, False, False, True, True]   # ply0 baseline, 3 unchanged -> fire ply3
    assert tr.last_progress_ply == 0


def test_change_resets_counter():
    tr = StalemateTracker(threshold=2)
    seq = [{(0, "Drone"): 1}, {(0, "Drone"): 1}, {(0, "Drone"): 2},
           {(0, "Drone"): 2}, {(0, "Drone"): 2}]
    fired = [tr.observe(s, p) for p, s in enumerate(seq)]
    assert fired == [False, False, False, False, True]   # change at ply2 -> fire ply4
    assert tr.last_progress_ply == 2


def test_cross_type_buy_sac_resets():
    # buy Engineer + sac Drone on one ply -> multiset changes -> counter resets (not frozen)
    tr = StalemateTracker(threshold=2)
    a = {(0, "Drone"): 5}
    b = {(0, "Drone"): 4, (0, "Engineer"): 1}
    assert [tr.observe(s, p) for p, s in enumerate([a, a, b])] == [False, False, False]
    assert tr.last_progress_ply == 2


def test_same_type_netzero_is_documented_blind_spot():
    # same-owner same-type buy+sac net-zero leaves the multiset unchanged -> treated as frozen.
    # This is the accepted residual (spec 3.1); the test pins the behaviour.
    tr = StalemateTracker(threshold=2)
    a = {(0, "Drone"): 5}
    assert [tr.observe(a, p) for p in range(3)] == [False, False, True]


@pytest.mark.parametrize("name,expected", GAMES.items())
def test_calibration_regression(name, expected):
    path = os.path.join(REPLAY_DIR, name + ".json.gz")
    if not os.path.exists(path):
        pytest.skip("calibration replay not present: " + path)
    assert scan_replay(load_replay(path), threshold=40) == expected
