import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wilson
from wilson import win_rate, wilson_ci


# ---- win-rate (draw = half a win) + iid Wilson CI ----

def test_win_rate_counts_draw_half():
    assert win_rate(wins=60, draws=20, n=100) == 0.70   # (60 + 0.5*20)/100


def test_win_rate_zero_n():
    assert win_rate(wins=0, draws=0, n=0) == 0.0


def test_wilson_brackets_point():
    lo, hi = wilson_ci(0.70, 100)
    assert lo < 0.70 < hi and 0.0 <= lo and hi <= 1.0


def test_wilson_clamps_to_unit_interval():
    lo, hi = wilson_ci(1.0, 5)
    assert 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0


def test_wilson_zero_n_is_vacuous():
    assert wilson_ci(0.5, 0) == (0.0, 1.0)


# ---- dead statistics machinery stays deleted (2026-06-10 audit) ----
# decisive / decisive_gate / clustered_ci had ZERO live callers and misled readers into
# thinking paired/sequential statistics were wired. They must not silently come back.

def test_dead_stats_helpers_removed():
    for name in ("decisive", "decisive_gate", "clustered_ci", "Z_POCOCK_3LOOK"):
        assert not hasattr(wilson, name), f"dead helper '{name}' has returned to wilson.py"
