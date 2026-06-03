import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wilson import (
    win_rate, wilson_ci, decisive, decisive_gate, clustered_ci,
    Z95, Z_POCOCK_3LOOK,
)


# ---- Step 1: win-rate + Wilson CI + decisive (vs 0.5) ----

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


def test_decisive_when_ci_excludes_half():
    assert decisive(wins=400, draws=0, n=512) is True     # ~78% over 0.5
    assert decisive(wins=260, draws=0, n=512) is False    # ~51%, CI straddles 0.5


# ---- A3: group-sequential PROMOTION gate is STRICTER than decisive() ----

def test_decisive_gate_uses_pocock_z():
    # sanity: the Pocock constant is wider than the 95% z, so its CI is wider.
    assert Z_POCOCK_3LOOK > Z95


def _find_borderline_n():
    """Find a (wins, n) at an interim look where decisive()==True but
    decisive_gate(final_look=False)==False, proving the gate is stricter."""
    for n in (128, 256, 200, 150):
        for wins in range(n // 2 + 1, n + 1):
            if decisive(wins, 0, n) and not decisive_gate(wins, 0, n, final_look=False):
                return wins, n
    return None


def test_decisive_gate_stricter_at_interim_look():
    found = _find_borderline_n()
    assert found is not None, "expected a borderline n where gate is stricter than decisive"
    wins, n = found
    # decisive() (95% iid) says decisive; the Pocock interim gate does NOT.
    assert decisive(wins, 0, n) is True
    assert decisive_gate(wins, 0, n, final_look=False) is False
    # ...and at the FINAL look the gate relaxes to full 95% alpha and agrees with decisive().
    assert decisive_gate(wins, 0, n, final_look=True) == decisive(wins, 0, n)
    # A3 invariant made explicit: the relaxed final look IS True here (agrees with decisive()).
    assert decisive_gate(wins, 0, n, final_look=True) is True


# ---- A4: clustered (card-set-level) CI for the paired colour-swap design ----

def test_clustered_ci_zero_width_when_all_equal():
    m, lo, hi = clustered_ci([0.6, 0.6, 0.6, 0.6])
    assert m == 0.6 and lo == 0.6 and hi == 0.6


def test_clustered_ci_varied_brackets_mean():
    scores = [0.4, 0.55, 0.7, 0.5, 0.65]
    m, lo, hi = clustered_ci(scores)
    assert 0.0 <= lo < m < hi <= 1.0


def test_clustered_ci_empty_and_singleton():
    assert clustered_ci([]) == (0.0, 0.0, 1.0)
    m, lo, hi = clustered_ci([0.73])
    assert m == 0.73 and lo == 0.0 and hi == 1.0
