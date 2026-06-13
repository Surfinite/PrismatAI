import math
import os, sys, numpy as np
import pytest
import torch
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)
from rl_data import (select_replay_window, rehearsal_fraction_for_iter,
                     colour_balance_weights, build_rl_sampler)


class FakeDS(torch.utils.data.Dataset):
    """Minimal stand-in for H5DatasetV2: __len__/__getitem__ + a .globals array
    whose column 13 is active_player (what _active_player_of reads)."""
    def __init__(self, n, active_player=0):
        self.n = n
        g = np.zeros((n, 15), dtype=np.float32)
        g[:, 13] = active_player
        self.globals = g

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        return i

def test_window_keeps_last_w():
    paths = ['i1.h5','i2.h5','i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 3) == ['i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 0) == paths

def test_fraction_flat_floor():
    # J1 re-freeze (2026-06-13): flat 0.10 — the 0.30 start defended a measured-absent risk
    # at this step size (training-03); raises happen via the tripwire/B8 path, not a schedule.
    assert abs(rehearsal_fraction_for_iter(1) - 0.10) < 1e-9
    assert rehearsal_fraction_for_iter(3) == rehearsal_fraction_for_iter(1)
    assert rehearsal_fraction_for_iter(99) == 0.10   # floored
    # the schedule machinery still works when explicitly parameterized (the raise path)
    assert abs(rehearsal_fraction_for_iter(1, start=0.30, decay_per_iter=0.07) - 0.30) < 1e-9
    assert rehearsal_fraction_for_iter(99, start=0.30, decay_per_iter=0.07) == 0.10

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


# --- M-04: epoch sized to self-play volume, not the rehearsal corpus -----------------

def test_epoch_draws_formula():
    # Iteration-1 real numbers: 4,720 self-play records, frac 0.30
    # -> draws per epoch = ceil(4720 / 0.7) = 6743, NOT len(sp)+len(human).
    sp = [FakeDS(4720, active_player=0)]
    human = FakeDS(10_000, active_player=1)
    loader, combined = build_rl_sampler(sp, human, 0.30, batch_size=64, num_workers=0)
    assert loader.sampler.num_samples == math.ceil(4720 / 0.7) == 6743
    assert len(combined) == 4720 + 10_000   # combined dataset itself is unchanged


def test_epoch_draws_multiple_selfplay_files():
    sp = [FakeDS(100), FakeDS(250), FakeDS(50)]
    human = FakeDS(5_000)
    loader, _ = build_rl_sampler(sp, human, 0.25, batch_size=16, num_workers=0)
    assert loader.sampler.num_samples == math.ceil(400 / 0.75)


def test_rehearsal_fraction_of_draws_matches_frac():
    # The frac->weights mapping must be unchanged: human share of DRAWS ~= frac.
    frac = 0.30
    sp_n, hu_n = 7_000, 20_000
    sp = [FakeDS(sp_n, active_player=0)]
    human = FakeDS(hu_n, active_player=1)
    loader, _ = build_rl_sampler(sp, human, frac, batch_size=64, num_workers=0)
    torch.manual_seed(1234)
    idxs = np.fromiter(iter(loader.sampler), dtype=np.int64)
    assert len(idxs) == math.ceil(sp_n / (1.0 - frac))
    human_share = float((idxs >= sp_n).mean())
    # n=10000 draws, sigma ~= sqrt(.3*.7/10000) ~= 0.0046; 0.02 is > 4 sigma
    assert abs(human_share - frac) < 0.02, f"human share {human_share} vs frac {frac}"
    # ...and expected self-play draws ~= one pass over the self-play window
    sp_draws = int((idxs < sp_n).sum())
    assert abs(sp_draws - sp_n) < 0.05 * sp_n


def test_no_human_dataset_epoch_is_selfplay_total():
    sp = [FakeDS(123), FakeDS(77)]
    loader, combined = build_rl_sampler(sp, None, 0.30, batch_size=8, num_workers=0)
    assert loader.sampler.num_samples == 200
    assert len(combined) == 200


def test_zero_selfplay_raises():
    with pytest.raises(ValueError, match="self-play"):
        build_rl_sampler([], FakeDS(1000), 0.30, batch_size=8, num_workers=0)
    with pytest.raises(ValueError, match="self-play"):
        build_rl_sampler([FakeDS(0)], FakeDS(1000), 0.30, batch_size=8, num_workers=0)


def test_frac_out_of_range_raises():
    sp = [FakeDS(100)]
    human = FakeDS(1000)
    with pytest.raises(ValueError, match="human_fraction"):
        build_rl_sampler(sp, human, 1.0, batch_size=8, num_workers=0)
    with pytest.raises(ValueError, match="human_fraction"):
        build_rl_sampler(sp, human, 1.5, batch_size=8, num_workers=0)
    with pytest.raises(ValueError, match="human_fraction"):
        build_rl_sampler(sp, human, -0.1, batch_size=8, num_workers=0)
    # frac just under 1 is legal (huge but finite epoch)
    loader, _ = build_rl_sampler(sp, human, 0.99, batch_size=8, num_workers=0)
    assert loader.sampler.num_samples == math.ceil(100 / 0.01)


def test_frac_zero_draws_only_selfplay():
    sp = [FakeDS(500, active_player=0)]
    human = FakeDS(2_000, active_player=1)
    loader, _ = build_rl_sampler(sp, human, 0.0, batch_size=8, num_workers=0)
    assert loader.sampler.num_samples == 500
    torch.manual_seed(7)
    idxs = np.fromiter(iter(loader.sampler), dtype=np.int64)
    assert (idxs < 500).all()
