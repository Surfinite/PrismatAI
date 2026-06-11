"""
Tests for --init-weights warm-start in train.py (E1 audit fix) and the
export verification exit code in export_weights_v2.py (M-10 audit fix).

E1: `train.py --rl-mode` used to train every RL iteration from RANDOM init
because no flag could express a weights-only warm start (--resume restores
optimizer/scheduler/SWA/epoch counters and runs zero epochs when resuming an
epoch-100 checkpoint under --epochs 6). The fix:
  - load_weights_only(): loads ONLY model_state_dict from any of our three
    checkpoint formats (raw sd / {"model_state_dict": sd} / SWA AveragedModel sd)
  - a hard-fail guard: --rl-mode without --init-weights/--resume refuses to run
  - mutual exclusion: --init-weights + --resume together is an error

Run: cd c:/libraries/PrismataAI && python -m pytest training/tests/test_init_weights.py -v
"""

import os
import subprocess
import sys

import pytest
import torch
from torch.optim.swa_utils import AveragedModel

# Add training/ to path so we can import train + model_deepsets
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)

from model_deepsets import PrismataDeepSets
from train import load_weights_only

PROPERTY_TABLE = os.path.join(TRAINING_DIR, "property_table.json")
TRAIN_PY = os.path.join(TRAINING_DIR, "train.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_model(seed):
    """Build a PrismataDeepSets with a deterministic random init."""
    torch.manual_seed(seed)
    model = PrismataDeepSets()
    model.load_property_table(PROPERTY_TABLE)
    return model


def assert_models_equal(src, dst):
    sd_src, sd_dst = src.state_dict(), dst.state_dict()
    assert sd_src.keys() == sd_dst.keys()
    for k in sd_src:
        assert torch.equal(sd_src[k], sd_dst[k]), f"tensor mismatch after load: {k}"


def assert_params_differ(src, dst):
    """Sanity: two different random inits must differ BEFORE loading.

    Compares parameters only — buffers (the property table) are loaded from the
    same file in both models and are legitimately identical.
    """
    src_params = dict(src.named_parameters())
    assert any(not torch.equal(p, src_params[n]) for n, p in dst.named_parameters()), \
        "test is vacuous: target model already equals source before load"


def save_raw_sd(model, path):
    torch.save(model.state_dict(), path)


def save_checkpoint(model, path):
    # best_model.pt-style: model_state_dict plus training state we must IGNORE
    torch.save({"model_state_dict": model.state_dict(),
                "epoch": 100,
                "optimizer_state_dict": {"dummy": True}}, path)


def save_swa(model, path):
    # Real AveragedModel state dict: "module."-prefixed keys + "n_averaged"
    swa = AveragedModel(model)
    sd = swa.state_dict()
    assert "n_averaged" in sd and any(k.startswith("module.") for k in sd)
    torch.save(sd, path)


# ---------------------------------------------------------------------------
# 1. load_weights_only: all three checkpoint formats
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("saver", [save_raw_sd, save_checkpoint, save_swa],
                         ids=["raw_sd", "model_state_dict", "swa_averaged"])
def test_load_weights_only_formats(tmp_path, saver):
    src = make_model(seed=1)
    pt_path = str(tmp_path / "ck.pt")
    saver(src, pt_path)

    dst = make_model(seed=2)
    assert_params_differ(src, dst)

    load_weights_only(dst, pt_path, torch.device("cpu"))
    assert_models_equal(src, dst)


def test_load_weights_only_returns_normalized_sd(tmp_path):
    src = make_model(seed=1)
    pt_path = str(tmp_path / "swa.pt")
    save_swa(src, pt_path)

    dst = make_model(seed=2)
    sd = load_weights_only(dst, pt_path, torch.device("cpu"))
    assert "n_averaged" not in sd
    assert not any(k.startswith("module.") for k in sd)


# ---------------------------------------------------------------------------
# 2. CLI guards (subprocess; guards must fire BEFORE any data loading)
# ---------------------------------------------------------------------------

def run_train(extra_args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, TRAIN_PY] + extra_args,
        capture_output=True, text=True, env=env, timeout=180)


def test_rl_mode_without_init_weights_refused():
    # Nonexistent data files: if the guard did NOT fire first, we'd see a
    # FileNotFoundError traceback / "Loading data..." instead of the guard text.
    r = run_train(["--rl-mode",
                   "--train-file", "C:/nonexistent/train_v2.h5",
                   "--val-file", "C:/nonexistent/val_v2.h5"])
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "--rl-mode requires --init-weights" in combined
    # Guard fired before seed print / lock file / data loading
    assert "Random seed:" not in r.stdout
    assert "Loading data" not in r.stdout
    assert "Traceback" not in combined


def test_init_weights_and_resume_mutually_exclusive():
    r = run_train(["--train-file", "C:/nonexistent/train_v2.h5",
                   "--val-file", "C:/nonexistent/val_v2.h5",
                   "--init-weights", "C:/nonexistent/a.pt",
                   "--resume", "C:/nonexistent/b.pt"])
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "mutually exclusive" in combined
    assert "Random seed:" not in r.stdout
    assert "Traceback" not in combined


def test_init_weights_nonexistent_path_fails_fast():
    # A typo'd --init-weights path must die at CLI validation (parser.error),
    # not minutes later at torch.load with a raw traceback.
    r = run_train(["--rl-mode",
                   "--train-file", "C:/nonexistent/train_v2.h5",
                   "--val-file", "C:/nonexistent/val_v2.h5",
                   "--init-weights", "C:/nonexistent/parent_weights.pt"])
    assert r.returncode != 0
    combined = r.stdout + r.stderr
    assert "--init-weights path does not exist" in combined
    # Guard fired before seed print / lock file / data loading
    assert "Random seed:" not in r.stdout
    assert "Loading data" not in r.stdout
    assert "Traceback" not in combined


def test_help_lists_init_weights():
    r = run_train(["--help"])
    assert r.returncode == 0
    assert "--init-weights" in r.stdout


# ---------------------------------------------------------------------------
# 3. P-1: RL window lineage stamps (rl_lineage_metadata -> run_metadata["data"])
# ---------------------------------------------------------------------------

def test_rl_lineage_metadata_keys_and_hashes(tmp_path):
    """The provenance dict must carry path/bytes/sha256 per resolved self-play
    file plus the human rehearsal H5 (P-1: window lineage in run_metadata)."""
    import hashlib
    from train import rl_lineage_metadata

    sp1 = tmp_path / "selfplay_iter1_v2.h5"
    sp1.write_bytes(b"shard-one")
    sp2 = tmp_path / "selfplay_iter2_v2.h5"
    sp2.write_bytes(b"shard-two-bytes")
    human = tmp_path / "human_1800_v2.h5"
    human.write_bytes(b"rehearsal")

    md = rl_lineage_metadata([str(sp1), str(sp2)], str(human))
    assert set(md) == {"rl_selfplay_files", "rl_human_file"}

    names = [os.path.basename(e["path"]) for e in md["rl_selfplay_files"]]
    assert names == ["selfplay_iter1_v2.h5", "selfplay_iter2_v2.h5"]  # order preserved
    for entry, raw in zip(md["rl_selfplay_files"],
                          [b"shard-one", b"shard-two-bytes"]):
        assert entry["bytes"] == len(raw)
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest()

    assert os.path.basename(md["rl_human_file"]["path"]) == "human_1800_v2.h5"
    assert md["rl_human_file"]["sha256"] == hashlib.sha256(b"rehearsal").hexdigest()


def test_rl_lineage_metadata_without_human_file(tmp_path):
    from train import rl_lineage_metadata
    md = rl_lineage_metadata([], None)
    assert md["rl_selfplay_files"] == []
    assert md["rl_human_file"] is None


# ---------------------------------------------------------------------------
# 4. M-10: export_weights_v2.main() must exit 1 when verify_export fails
# ---------------------------------------------------------------------------

def test_export_verify_failure_exits_nonzero(tmp_path, monkeypatch):
    import export_weights_v2
    out_path = str(tmp_path / "weights.bin")
    monkeypatch.setattr(sys, "argv", ["export_weights_v2.py", "random", out_path,
                                      "--property-table", PROPERTY_TABLE])
    monkeypatch.setattr(export_weights_v2, "verify_export", lambda *a, **k: False)
    with pytest.raises(SystemExit) as exc_info:
        export_weights_v2.main()
    assert exc_info.value.code == 1
