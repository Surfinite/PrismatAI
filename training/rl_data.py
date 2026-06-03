"""RL data assembly: sliding replay buffer (last W self-play H5) + human-only rehearsal at a
named fraction + colour balancing. Operates on schema_v2 H5DatasetV2 datasets from train.py."""
import numpy as np
import torch
from torch.utils.data import ConcatDataset, WeightedRandomSampler, DataLoader

ACTIVE_PLAYER_GLOBAL_IDX = 13   # globals[...,13] = active_player (schema_v2.json global_features)

def colour_balance_weights(active_player):
    """Per-sample weights so total weight of active_player==0 equals that of ==1.
    active_player: int array in {0,1}. Returns a float array. With both colours present
    it sums to len(active_player); if only one colour is present it sums to
    0.5*len(active_player). (Only relative weights matter to WeightedRandomSampler, so
    this is harmless.)"""
    ap = np.asarray(active_player).astype(np.int64)
    w = np.ones(len(ap), dtype=np.float64)
    for c in (0, 1):
        n = int((ap == c).sum())
        if n > 0:
            w[ap == c] = 0.5 * len(ap) / n
    return w

def _active_player_of(ds):
    """Extract per-sample active_player (the colour-to-move) from a V2 dataset's globals."""
    g = ds.globals if hasattr(ds, "globals") else None
    if g is None:
        return np.zeros(len(ds), dtype=np.int64)
    return (np.asarray(g[:, ACTIVE_PLAYER_GLOBAL_IDX]) > 0.5).astype(np.int64)

def build_rl_sampler(selfplay_datasets, human_dataset, human_fraction, batch_size,
                     num_workers=2):
    """Combine the last-W self-play datasets + human rehearsal into one weighted-sampling loader.
       - Expected human share per draw == human_fraction.
       - Within each source, colours (active_player) are balanced.
    Returns (loader, combined_dataset)."""
    parts = list(selfplay_datasets) + ([human_dataset] if human_dataset is not None else [])
    combined = ConcatDataset(parts)

    weights = np.empty(len(combined), dtype=np.float64)
    offset = 0
    sp_total = sum(len(d) for d in selfplay_datasets) or 1
    hu_total = len(human_dataset) if human_dataset is not None else 0
    for d in selfplay_datasets:
        n = len(d)
        cb = colour_balance_weights(_active_player_of(d))
        # self-play mass = (1 - human_fraction), split across all self-play samples
        weights[offset:offset + n] = cb * ((1.0 - human_fraction) / sp_total)
        offset += n
    if human_dataset is not None and hu_total > 0:
        n = len(human_dataset)
        cb = colour_balance_weights(_active_player_of(human_dataset))
        weights[offset:offset + n] = cb * (human_fraction / hu_total)
        offset += n

    sampler = WeightedRandomSampler(torch.as_tensor(weights, dtype=torch.double),
                                    num_samples=len(combined), replacement=True)
    loader = DataLoader(combined, batch_size=batch_size, sampler=sampler,
                        num_workers=num_workers, drop_last=True)
    return loader, combined

def rehearsal_fraction_for_iter(iteration, start=0.30, floor=0.10, decay_per_iter=0.07):
    """Named-fraction schedule: ~30% human at iter-1, decaying to ~10-15% by iter-3.

    Confidence schedule, NOT an accumulation argument: the fixed W=5 sliding window keeps
    self-play *volume* roughly constant after iteration W, so we are not lowering the human
    share because self-play data piles up. We lower it because we trust self-play more as it
    strengthens across iterations and thus need less human anchoring over time.
    """
    return max(floor, start - decay_per_iter * max(0, iteration - 1))

def select_replay_window(selfplay_h5_paths, window):
    """Keep only the last `window` per-iteration self-play H5 files (sliding buffer)."""
    return list(selfplay_h5_paths)[-window:] if window and window > 0 else list(selfplay_h5_paths)
