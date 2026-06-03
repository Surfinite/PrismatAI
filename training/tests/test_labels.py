"""Label-correctness tests for the V2 pipeline. Run: cd training && python -m pytest tests/test_labels.py -v

Perspective convention (guards the historical P0/P1 inversion bug):
label_A is exactly the P0-perspective outcome — compute_labels(o, ...)[0] == float(o),
with P0-win -> 1.0, draw -> 0.5, P0-loss -> 0.0. This matches the human-corpus label
convention; any P0/P1 swap would break the identity asserted below.
"""
import os, sys
import numpy as np
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)
from vectorize_v2 import compute_labels   # existing function

class TestOutcomeScale:
    def test_win_draw_loss_map_to_1_half_0(self):
        # Strategy A is the raw outcome_p0 in [0,1]. (P0-perspective: P0-win=1.0.)
        assert compute_labels(1.0, 10, 30, 1800, 1800)[0] == 1.0   # P0 win
        assert compute_labels(0.5, 10, 30, 1800, 1800)[0] == 0.5   # draw
        assert compute_labels(0.0, 10, 30, 1800, 1800)[0] == 0.0   # P0 loss

    def test_labels_in_unit_interval(self):
        for o in (0.0, 0.5, 1.0):
            a, bw, c, d = compute_labels(o, 5, 40, 1500, 2000)
            for v in (a, c, d):
                assert 0.0 <= v <= 1.0
            assert 0.0 <= bw <= 1.0

class TestInversion:
    def test_opposite_outcome_inverts(self):
        # The P0/P1 inversion bug would make a P0-win and a P0-loss collapse to the same label.
        assert compute_labels(1.0, 20, 40, 1800, 1800)[0] != compute_labels(0.0, 20, 40, 1800, 1800)[0]

    def test_label_A_is_p0_perspective_identity(self):
        # label_A is the P0-perspective outcome verbatim. Documents the convention the
        # historical inversion bug violated (P0-win must read 1.0, not 0.0).
        for o in (0.0, 0.5, 1.0):
            assert compute_labels(o, 12, 30, 1700, 1900)[0] == o

class TestColourBalanceHelper:
    def test_balance_weights_equalise_active_player(self):
        from rl_data import colour_balance_weights
        ap = np.array([0,0,0,1])          # 3 P0-to-move, 1 P1-to-move
        w = colour_balance_weights(ap)
        # expected total weight per colour equal
        assert abs(w[ap==0].sum() - w[ap==1].sum()) < 1e-6
