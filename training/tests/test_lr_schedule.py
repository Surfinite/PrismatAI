"""
Tests for the LR schedule (N-1 audit fix: warmup floor on short RL runs).

N-1: train.py's WarmupCosineScheduler does linear warmup over --warmup-steps
(argparse default 1000) then cosine decay to min_lr=1e-6. After the M-04 epoch
fix, a campaign-scale RL iteration has only ~78 TOTAL optimizer steps
(steps_per_epoch * 6 epochs), so warmup never completes and
lr = max(1e-6, 1e-5*(step+1)/1000) == 1e-6 for the ENTIRE run — the peak LR
ever reached is exactly the floor, candidate ~= parent, null iterations.
Additionally SWALR(swa_lr=args.lr*0.1) = 1e-6 at the RL fine-tune's lr=1e-5,
freezing the SWA phase (epochs 3-6, half the run) at the floor too.

Fixes under test:
  - resolve_warmup(warmup_steps, total_steps): rescales warmup to
    max(1, total_steps // 10) when warmup can't complete; legacy big-corpus
    runs (warmup < total_steps) are untouched.
  - resolve_swa_lr(swa_lr_arg, lr): explicit --swa-lr, else legacy lr*0.1.
  - run_iteration.ps1 stage 3 passes --swa-lr 5e-6.

Run: cd c:/libraries/PrismataAI && python -m pytest training/tests/test_lr_schedule.py -v
"""

import os
import subprocess
import sys

import pytest
import torch

# Add training/ to path so we can import train
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)

from train import WarmupCosineScheduler, resolve_warmup, resolve_swa_lr

TRAIN_PY = os.path.join(TRAINING_DIR, "train.py")
RUN_ITERATION_PS1 = os.path.join(
    os.path.dirname(TRAINING_DIR), "eval", "run_iteration.ps1")

# The RL fine-tune's actual shape (run_iteration.ps1 stage 3, post M-04):
RL_LR = 1e-5
RL_TOTAL_STEPS = 78
LEGACY_TOTAL_STEPS = 19200
DEFAULT_WARMUP = 1000
MIN_LR = 1e-6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def lr_trajectory(lr, warmup_steps, total_steps, n_steps=None):
    """Simulate the per-step LR actually applied over a run."""
    param = torch.nn.Parameter(torch.zeros(1))
    opt = torch.optim.SGD([param], lr=lr)
    sched = WarmupCosineScheduler(
        opt, warmup_steps=warmup_steps, total_steps=total_steps, min_lr=MIN_LR)
    lrs = []
    for _ in range(n_steps if n_steps is not None else total_steps):
        lrs.append(opt.param_groups[0]["lr"])  # LR applied at this step
        opt.step()
        sched.step()
    return lrs


# ---------------------------------------------------------------------------
# resolve_warmup (pure function)
# ---------------------------------------------------------------------------

class TestResolveWarmup:
    def test_short_rl_run_rescales_to_tenth(self, capsys):
        eff = resolve_warmup(DEFAULT_WARMUP, RL_TOTAL_STEPS)
        assert eff == 7  # 78 // 10
        out = capsys.readouterr().out
        assert "[lr]" in out and "rescal" in out  # the LOUD print

    def test_legacy_run_unchanged_and_silent(self, capsys):
        eff = resolve_warmup(DEFAULT_WARMUP, LEGACY_TOTAL_STEPS)
        assert eff == DEFAULT_WARMUP
        assert capsys.readouterr().out == ""  # legacy path byte-identical

    def test_tiny_run_floors_at_one(self):
        assert resolve_warmup(DEFAULT_WARMUP, 5) == 1
        assert resolve_warmup(DEFAULT_WARMUP, 1) == 1

    def test_boundary_equal_rescales(self):
        # warmup == total_steps means warmup completes only ON the last step:
        # the run would end before any cosine phase. Rescale.
        assert resolve_warmup(100, 100) == 10


# ---------------------------------------------------------------------------
# (a) the broken case is fixed — RL-shape trajectory
# ---------------------------------------------------------------------------

class TestRLTrajectory:
    def test_broken_case_pinned_peak_lr_was_the_floor(self):
        """Pre-fix behavior pin: warmup 1000 over 78 steps -> LR == 1e-6 ALWAYS."""
        lrs = lr_trajectory(RL_LR, DEFAULT_WARMUP, RL_TOTAL_STEPS)
        assert max(lrs) == pytest.approx(MIN_LR)
        assert min(lrs) == pytest.approx(MIN_LR)

    def test_fixed_case_reaches_peak_lr(self):
        """Post-fix: effective warmup 7 -> peak LR actually reaches ~lr."""
        eff = resolve_warmup(DEFAULT_WARMUP, RL_TOTAL_STEPS)
        lrs = lr_trajectory(RL_LR, eff, RL_TOTAL_STEPS)
        assert max(lrs) >= 0.9 * RL_LR

    def test_fixed_case_cosine_tail_decays_to_min_lr(self):
        eff = resolve_warmup(DEFAULT_WARMUP, RL_TOTAL_STEPS)
        lrs = lr_trajectory(RL_LR, eff, RL_TOTAL_STEPS)
        peak_i = lrs.index(max(lrs))
        # Monotone non-increasing after the peak (cosine decay)
        for a, b in zip(lrs[peak_i:], lrs[peak_i + 1:]):
            assert b <= a + 1e-12
        # Final LR lands on the floor
        assert lrs[-1] == pytest.approx(MIN_LR, rel=0.5)
        assert lrs[-1] < 0.25 * max(lrs)


# ---------------------------------------------------------------------------
# (b) legacy case — schedule unchanged
# ---------------------------------------------------------------------------

class TestLegacyTrajectory:
    def test_legacy_warmup_completes_at_step_1000(self):
        lr = 3e-4
        eff = resolve_warmup(DEFAULT_WARMUP, LEGACY_TOTAL_STEPS)
        assert eff == DEFAULT_WARMUP
        lrs = lr_trajectory(lr, eff, LEGACY_TOTAL_STEPS, n_steps=1100)
        # LR at step 1000 (first cosine step, progress=0) == base lr exactly
        assert lrs[1000] == pytest.approx(lr, rel=1e-6)
        # Warmup is linear: mid-warmup LR is ~half
        assert lrs[499] == pytest.approx(lr * 500 / 1000, rel=1e-6)


# ---------------------------------------------------------------------------
# (c) --swa-lr resolution
# ---------------------------------------------------------------------------

class TestResolveSwaLr:
    def test_default_none_falls_back_to_lr_tenth(self):
        assert resolve_swa_lr(None, 3e-4) == pytest.approx(3e-5)
        # ... which at the RL fine-tune's lr=1e-5 IS the 1e-6 floor (the bug
        # this arg exists to escape):
        assert resolve_swa_lr(None, RL_LR) == pytest.approx(MIN_LR)

    def test_explicit_value_wins(self):
        assert resolve_swa_lr(5e-6, RL_LR) == pytest.approx(5e-6)

    def test_argparse_exposes_swa_lr(self):
        out = subprocess.run(
            [sys.executable, TRAIN_PY, "--help"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert out.returncode == 0
        assert "--swa-lr" in out.stdout


# ---------------------------------------------------------------------------
# run_iteration.ps1 stage 3 pins the RL value
# ---------------------------------------------------------------------------

class TestRunIterationArgv:
    def test_stage3_disables_swa_and_pins_seed(self):
        # J1 re-freeze (2026-06-13): SWA is DISABLED for RL fine-tunes (training-02: 4
        # near-collinear snapshots diluted the update ~20% for nothing); the candidate is
        # final_model.pt. The old "--swa-lr 5e-6" pin (N-1) is therefore gone from the
        # driver — resolve_swa_lr keeps protecting non-RL invocations (tests above).
        with open(RUN_ITERATION_PS1, encoding="utf-8") as f:
            text = f.read()
        assert "--no-swa" in text
        assert "final_model.pt" in text
        assert "--swa-lr" not in text
        # training-06: the training seed is pinned (reproducible candidates)
        assert "--seed" in text
        assert "--num-workers 0" in text
