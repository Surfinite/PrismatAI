import os, sys, numpy as np
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)
from rl_data import select_replay_window, rehearsal_fraction_for_iter, colour_balance_weights

def test_window_keeps_last_w():
    paths = ['i1.h5','i2.h5','i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 3) == ['i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 0) == paths

def test_fraction_decays():
    assert abs(rehearsal_fraction_for_iter(1) - 0.30) < 1e-9
    assert rehearsal_fraction_for_iter(3) < rehearsal_fraction_for_iter(1)
    assert rehearsal_fraction_for_iter(99) == 0.10   # floored

def test_colour_weights_nonnegative_and_balanced():
    ap = np.array([0,1,1,1,0,0])
    w = colour_balance_weights(ap)
    assert (w >= 0).all()
    assert abs(w[ap==0].sum() - w[ap==1].sum()) < 1e-6

def test_colour_weights_single_colour_uniform():
    # All one colour: weights are uniform (0.5 each); sum is 0.5*len, not len.
    ap = np.array([0, 0, 0])
    w = colour_balance_weights(ap)
    assert (w >= 0).all()
    assert np.allclose(w, 0.5)
    assert abs(w.sum() - 0.5 * len(ap)) < 1e-6
