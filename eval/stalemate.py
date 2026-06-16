"""Stalemate (no-progress) detection oracle for the self-play/eval draw policy.

Mirrors the C++ StalemateTracker (PrismataAI-dave-master source/testing/StalemateTracker.h).
PRIMARY signal: the board (owner, cardType) multiset is unchanged across consecutive turn-start
states. The C++ engine MUST match this algorithm. This module is the executable spec + the
3-game calibration regression + a reusable analysis tool. Design:
docs/superpowers/specs/2026-06-16-selfplay-stalemate-draw-policy-design.md
"""
import gzip
import json


def population_multiset(table):
    """The (owner, cardName) multiset over ALIVE units in a replay state's `table`."""
    sig = {}
    for u in table:
        if u.get("deadness") == "alive":
            k = (u["owner"], u["cardName"])
            sig[k] = sig.get(k, 0) + 1
    return sig


class StalemateTracker:
    """Counts consecutive turn-start states with no population change; fires at `threshold` plies.

    threshold <= 0 disables firing (observe always returns False). last_progress_ply is the ply
    index of the most recent population change (the trim boundary for self-play).
    """

    def __init__(self, threshold):
        self.threshold = threshold
        self.no_change = 0
        self.last_progress_ply = 0
        self._prev = None

    def observe(self, sig, ply):
        """Feed one turn-start multiset at ply index `ply`. Returns True iff stalled."""
        if self._prev is None or sig != self._prev:
            self.no_change = 0
            self.last_progress_ply = ply
        else:
            self.no_change += 1
        self._prev = sig
        return self.threshold > 0 and self.no_change >= self.threshold


def turn_start_states(replay):
    """Turn-start state for ply p (C++ replay convention): states[p==0 ? 0 : turnBoundaries[p]-1]."""
    tb, states = replay["turnBoundaries"], replay["states"]
    return [states[0 if p == 0 else max(0, min(tb[p] - 1, len(states) - 1))]
            for p in range(len(tb))]


def scan_replay(replay, threshold):
    """Run the tracker over a replay's turn-start states. Returns (last_progress_ply, fire_ply|None)."""
    tr = StalemateTracker(threshold)
    for ply, state in enumerate(turn_start_states(replay)):
        if tr.observe(population_multiset(state["table"]), ply):
            return tr.last_progress_ply, ply
    return tr.last_progress_ply, None


def load_replay(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
