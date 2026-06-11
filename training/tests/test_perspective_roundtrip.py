"""A6 perspective round-trip gate (verification finding N-6).

Pins the P0/P1 perspective-inversion bug class (the E1-pattern doc-says/code-doesn't gap:
eval/rl_campaign.md declared A6 a REQUIRED pre-iter-1 gate with nothing implementing it).

Convention being pinned (read from the actual pipeline, not assumed):
  * V2 JSONL records are ABSOLUTE-perspective: `outcome_p0` = P(player 0 / first / white wins)
    and is stamped game-level (js_engine/extract_training_jsengine.js outcomeP0()), so it is
    CONSTANT across all records of one game while `active_player` toggles per ply.
  * The opposite-perspective twin of a record is produced by vectorize_v2.mirror_record()
    (P0<->P1 augmentation): its label must be COMPLEMENTARY (1 - outcome; draws 0.5 -> 0.5)
    and its features must swap coherently with the label flip.
  * The net's scalar output (model_deepsets.PrismataDeepSets forward) is the logit of
    P(P0 wins) for the record's (absolute P0) perspective.

Two surfaces:
  (a) data-side label/perspective consistency — pure python on vectorize_v2 functions plus a
      bounded scan of the real human corpus (training/data/human_1800_v2.jsonl, local-only,
      17 GB — only the first SCAN_LINES lines are read; corpus tests skip if absent).
      The JSONL carries no separate winner field (outcome_p0 IS the stamped winner label),
      so winner-match is pinned structurally: constancy within game + complementarity under
      mirror + the inference-side orientation check in (b).
      NOTE: a P0-game-win-rate bound has NO inversion-detection power on this corpus — the
      1800+ human games are seat-balanced (measured P0 WR = 0.508 over 778 games), and the
      statistic is inversion-symmetric. It is kept only as a loose corruption sanity band;
      ORIENTATION is carried by surface (b).
  (b) inference-side decided-position sanity — load the v221 SWA checkpoint, evaluate the
      LAST turn-start record of each player from >= 50 decided games and assert the value
      tracks the actual winner. Measured on 60 games / 120 records (2026-06-11, v221 SWA):
      mean prob | P0 won = 0.952, mean prob | P0 lost = 0.025, 97.5% sided correctly.
      Gate thresholds are set with headroom BELOW the measured values (0.80 / 0.20 / 85%):
      the gate's job is catching an INVERSION (which would score ~0.05 / ~0.95 / ~2.5%),
      not grading the net.

The C++ side of the round-trip is additionally pinned by the export-parity gate
(run_iteration.ps1 stage 5 -> tools/parity/dump_value_batch.py): it compares
value = 2*sigmoid(logit)-1 (P0-perspective) between C++ inference and PyTorch on ~1000 real
states at tol 1e-3, so a C++-side perspective flip reads value_cpp ~= -value_torch and blows
the gate on any non-neutral state. The one seam parity does NOT cover is the explicit
maxPlayer negation downstream of the scalar (dave-master NeuralNet.cpp evaluateValue tail +
UCTSearch.cpp (nnValue+1)/2 consumption) — a single code-visible negation.

Run: python -m pytest training/tests/test_perspective_roundtrip.py -v
"""
import json
import os
import re
import sys

import numpy as np
import pytest

TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(TRAINING_DIR)
sys.path.insert(0, TRAINING_DIR)

from vectorize_v2 import (  # noqa: E402
    compute_labels,
    load_schema,
    load_unit_index,
    mirror_record,
    vectorize_globals,
    vectorize_instances,
    vectorize_supply,
)

JSONL_PATH = os.path.join(TRAINING_DIR, "data", "human_1800_v2.jsonl")
SWA_PATH = os.path.join(TRAINING_DIR, "models", "deepsets_v221", "swa_model.pt")
SCHEMA_PATH = os.path.join(TRAINING_DIR, "schema_v2.json")
UNIT_INDEX_PATH = os.path.join(TRAINING_DIR, "data", "unit_index.json")
PROPERTY_TABLE_PATH = os.path.join(TRAINING_DIR, "property_table.json")

# Runtime caps: 5000 lines ~= 50 MB ~= 2 s scan, ~190 games (avg ~25.6 plies/game measured).
SCAN_LINES = 5000
N_SAMPLE_FULL = 5          # real records full-parsed for the mirror tests
B_GAMES_TARGET = 60        # decided complete games used by surface (b)
B_GAMES_MIN = 50           # spec floor for surface (b)

HAVE_CORPUS = os.path.isfile(JSONL_PATH)
HAVE_SWA = os.path.isfile(SWA_PATH)


# ---------------------------------------------------------------------------
# Shared corpus scan (regex field extraction — full json.loads only where needed)
# ---------------------------------------------------------------------------

_RE_CODE = re.compile(r'"replay_code":"([^"]*)"')
_RE_OUT = re.compile(r'"outcome_p0":([0-9.]+)')
_RE_PLY = re.compile(r'"ply_index":([0-9]+)')
_RE_AP = re.compile(r'"active_player":([0-9]+)')
_RE_TP = re.compile(r'"total_plies":([0-9]+)')


@pytest.fixture(scope="module")
def corpus_scan():
    """Scan the first SCAN_LINES lines of the human V2 JSONL.

    Returns dict with:
      games:        {code: {"outcomes": set, "n_records": int, "bad_ap": int,
                            "tp": int, "max_ply": int, "lines": {ply: raw_line}}}
      order:        game codes in file order
      sample_lines: first N_SAMPLE_FULL raw lines (for full-parse mirror tests)
    Per game only the TWO highest-ply raw lines are retained (surface (b) input).
    """
    if not HAVE_CORPUS:
        pytest.skip(f"local corpus not present: {JSONL_PATH}")

    games = {}
    order = []
    sample_lines = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for n_lines, line in enumerate(f, start=1):
            if len(sample_lines) < N_SAMPLE_FULL:
                sample_lines.append(line)
            m = _RE_CODE.search(line)
            code = m.group(1) if m else "?"
            out = float(_RE_OUT.search(line).group(1))
            ply = int(_RE_PLY.search(line).group(1))
            ap = int(_RE_AP.search(line).group(1))
            tp = int(_RE_TP.search(line).group(1))
            g = games.get(code)
            if g is None:
                g = {"outcomes": set(), "n_records": 0, "bad_ap": 0,
                     "tp": tp, "max_ply": -1, "lines": {}}
                games[code] = g
                order.append(code)
            g["outcomes"].add(out)
            g["n_records"] += 1
            g["max_ply"] = max(g["max_ply"], ply)
            if ap != ply % 2:
                g["bad_ap"] += 1
            g["lines"][ply] = line
            if len(g["lines"]) > 2:
                del g["lines"][min(g["lines"])]
            if n_lines >= SCAN_LINES:
                break

    return {"games": games, "order": order, "sample_lines": sample_lines}


def _complete_decided_games(scan):
    """Game codes (file order) whose every ply 0..total_plies-1 was scanned and
    whose outcome is decided (0.0 or 1.0)."""
    out = []
    for code in scan["order"]:
        g = scan["games"][code]
        if (g["max_ply"] == g["tp"] - 1 and g["n_records"] == g["tp"]
                and g["outcomes"] in ({0.0}, {1.0})):
            out.append(code)
    return out


# ---------------------------------------------------------------------------
# Surface (a) part 1 — mirror_record perspective round-trip (pure functions)
# ---------------------------------------------------------------------------

def _synthetic_record():
    """Minimal asymmetric V2 record (distinct units/resources/attack per side so a
    perspective swap is observable in every feature block)."""
    def inst(name, owner, blocking, hp):
        return {"name": name, "owner": owner, "is_constructing": 0,
                "turns_until_ready": 0, "is_blocking": blocking, "ability_used": 0,
                "current_hp": hp, "hp_fraction": 1.0, "is_frozen": 0,
                "lifespan_remaining": 0, "stamina_remaining": 0}
    return {
        "schema_version": "v2",
        "ply_index": 4,
        "card_set": ["Tarsier"],
        "instances": [
            inst("Drone", 0, 1, 1),
            inst("Drone", 0, 1, 1),
            inst("Engineer", 0, 1, 1),
            inst("Tarsier", 1, 0, 2),
            inst("Drone", 1, 1, 1),
        ],
        "supply": {"Drone": [14, 13, 1], "Engineer": [18, 20, 1], "Tarsier": [4, 5, 1]},
        "p0_resources": {"gold": 5, "blue": 0, "red": 0, "green": 1, "energy": 0},
        "p1_resources": {"gold": 3, "blue": 1, "red": 0, "green": 0, "energy": 2},
        "p0_attack": 0,
        "p1_attack": 2,
        "turn_number": 5,
        "active_player": 0,
        "outcome_p0": 1.0,
    }


@pytest.fixture(scope="module")
def schema():
    return load_schema(SCHEMA_PATH)


@pytest.fixture(scope="module")
def unit_index():
    return load_unit_index(UNIT_INDEX_PATH)


@pytest.fixture(scope="module")
def mirror_test_records():
    """Synthetic record + (when the local corpus exists) a few real records."""
    recs = [_synthetic_record()]
    if HAVE_CORPUS:
        with open(JSONL_PATH, "r", encoding="utf-8") as f:
            for _ in range(N_SAMPLE_FULL):
                line = f.readline()
                if not line:
                    break
                recs.append(json.loads(line))
    return recs


class TestMirrorPerspectiveRoundTrip:
    """The opposite-perspective record (mirror_record) must flip the label and the
    features COHERENTLY — an inversion anywhere (label flipped without features, or a
    feature block swapped without the label) breaks one of these."""

    def test_mirror_flips_label_and_active_player(self, mirror_test_records):
        for rec in mirror_test_records:
            m = mirror_record(rec)
            assert m["outcome_p0"] == 1 - rec["outcome_p0"]   # draws: 1 - 0.5 == 0.5
            assert m["active_player"] == 1 - rec["active_player"]

    def test_double_mirror_is_identity(self, mirror_test_records):
        # The literal perspective ROUND-TRIP: mirror twice == original, exactly.
        for rec in mirror_test_records:
            assert mirror_record(mirror_record(rec)) == rec

    def test_mirror_globals_swap_coherently(self, mirror_test_records, schema):
        caps = schema["normalization_caps"]
        for rec in mirror_test_records:
            g = vectorize_globals(rec, caps)
            gm = vectorize_globals(mirror_record(rec), caps)
            # p0 block <-> p1 block (gold,blue,red,green,energy,attack)
            assert np.allclose(gm[0:6], g[6:12])
            assert np.allclose(gm[6:12], g[0:6])
            assert gm[12] == g[12]                    # turn_number unchanged
            assert gm[13] == 1.0 - g[13]              # active_player flipped
            assert gm[14] == g[14]                    # under_attack is active-relative -> invariant

    def test_mirror_supply_swaps_columns(self, mirror_test_records, unit_index, schema):
        for rec in mirror_test_records:
            s = vectorize_supply(rec["supply"], unit_index, schema["num_units"])
            sm = vectorize_supply(mirror_record(rec)["supply"], unit_index, schema["num_units"])
            assert np.array_equal(sm[:, 0], s[:, 1])
            assert np.array_equal(sm[:, 1], s[:, 0])
            assert np.array_equal(sm[:, 2], s[:, 2])  # in_card_set unchanged

    def test_mirror_instances_flip_owner_only(self, mirror_test_records, unit_index, schema):
        max_inst = schema["max_instances"]
        for rec in mirror_test_records:
            f0, i0, n0 = vectorize_instances(rec["instances"], unit_index, max_inst)
            f1, i1, n1 = vectorize_instances(mirror_record(rec)["instances"], unit_index, max_inst)
            assert n0 == n1
            # vectorize_instances reorders P0-first, so compare as multisets:
            # each original token with owner flipped must appear once in the mirror.
            def toks(feats, ids, n, flip_owner):
                out = []
                for k in range(n):
                    t = feats[k].copy()
                    if flip_owner:
                        t[0] = 1.0 - t[0]
                    out.append((int(ids[k]),) + tuple(np.round(t, 6)))
                return sorted(out)
            assert toks(f0, i0, n0, flip_owner=True) == toks(f1, i1, n1, flip_owner=False)

    def test_complement_composes_through_compute_labels(self):
        # label_A of the mirrored outcome is the complement of label_A of the original
        # (test_labels.py pins label_A == outcome; this pins the complement composition).
        for o in (0.0, 0.5, 1.0):
            la = compute_labels(o, 12, 30, 1700, 1900)[0]
            la_m = compute_labels(1 - o, 12, 30, 1900, 1700)[0]
            assert la_m == 1 - la


# ---------------------------------------------------------------------------
# Surface (a) part 2 — real-corpus label/perspective invariants
# ---------------------------------------------------------------------------

class TestCorpusLabelPerspective:
    def test_outcome_constant_within_game(self, corpus_scan):
        # outcome_p0 is game-level (absolute P0 perspective): any record whose label
        # varied with active_player / ply would be exactly the inversion bug class.
        bad = [c for c in corpus_scan["order"]
               if len(corpus_scan["games"][c]["outcomes"]) > 1]
        assert bad == [], f"games with non-constant outcome_p0: {bad[:5]}"

    def test_outcome_domain(self, corpus_scan):
        # 0.0 / 1.0 decided, 0.5 draw (2.0 = legacy draw code, mapped to 0.5 by vectorize).
        seen = set()
        for c in corpus_scan["order"]:
            seen |= corpus_scan["games"][c]["outcomes"]
        assert seen <= {0.0, 0.5, 1.0, 2.0}, f"unexpected outcome values: {sorted(seen)}"

    def test_active_player_alternates_with_ply(self, corpus_scan):
        # Turn-start records alternate strictly: active_player == ply_index % 2
        # (white/P0 moves first). An extractor-side active_player inversion breaks this.
        bad = sum(corpus_scan["games"][c]["bad_ap"] for c in corpus_scan["order"])
        assert bad == 0, f"{bad} records with active_player != ply_index % 2"

    def test_p0_winrate_sanity_band(self, corpus_scan):
        # NOT an orientation check (inversion-symmetric on this seat-balanced corpus:
        # measured P0 WR = 0.508) — only a loose corruption guard. Orientation is
        # pinned by TestInferenceOrientation below.
        decided = [c for c in corpus_scan["order"]
                   if corpus_scan["games"][c]["outcomes"] in ({0.0}, {1.0})]
        assert len(decided) >= 100, f"too few decided games scanned: {len(decided)}"
        wr = sum(1 for c in decided
                 if corpus_scan["games"][c]["outcomes"] == {1.0}) / len(decided)
        assert 0.40 <= wr <= 0.60, f"P0 game-win rate {wr:.3f} outside sanity band"


# ---------------------------------------------------------------------------
# Surface (b) — inference-side decided-position orientation (v221 SWA)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def decided_endgame_probs(corpus_scan, unit_index, schema):
    """Sigmoid value of the v221 SWA net on the last two turn-start records (one per
    player) of B_GAMES_TARGET decided complete games. Returns (probs, outcomes, n_games)."""
    torch = pytest.importorskip("torch")
    if not HAVE_SWA:
        pytest.skip(f"v221 SWA checkpoint not present: {SWA_PATH}")

    from model_deepsets import PrismataDeepSets

    caps = schema["normalization_caps"]
    feats, ids, counts, sups, globs, outs = [], [], [], [], [], []
    n_games = 0
    for code in _complete_decided_games(corpus_scan):
        if n_games >= B_GAMES_TARGET:
            break
        lines = corpus_scan["games"][code]["lines"]
        if len(lines) < 2:
            continue
        for ply in sorted(lines):
            rec = json.loads(lines[ply])
            f_, i_, n_ = vectorize_instances(rec["instances"], unit_index,
                                             schema["max_instances"])
            s_ = vectorize_supply(rec["supply"], unit_index, schema["num_units"])
            feats.append(f_)
            ids.append(i_)
            counts.append(n_)
            sups.append(s_)
            globs.append(vectorize_globals(rec, caps))
            outs.append(float(rec["outcome_p0"]))
        n_games += 1

    assert n_games >= B_GAMES_MIN, \
        f"only {n_games} decided complete games in the first {SCAN_LINES} lines"

    # Same loader pattern as eval/eval_deepsets_h5.py::load_deepsets (SWA 'module.' strip).
    model = PrismataDeepSets(num_units=schema["num_units"], num_properties=37, dropout=0.0)
    model.load_property_table(PROPERTY_TABLE_PATH)
    ck = torch.load(SWA_PATH, map_location="cpu", weights_only=False)
    sd = ck.get("model_state_dict", ck) if isinstance(ck, dict) else ck
    if any(k.startswith("module.") for k in sd):
        sd = {k[len("module."):]: v for k, v in sd.items() if k != "n_averaged"}
    model.load_state_dict(sd)
    model.eval()

    with torch.no_grad():
        logits = model(
            torch.from_numpy(np.asarray(feats, dtype=np.float32)),
            torch.from_numpy(np.asarray(ids).astype(np.int64)),
            torch.from_numpy(np.asarray(counts).astype(np.int64)),
            torch.from_numpy(np.asarray(sups, dtype=np.float32)),
            torch.from_numpy(np.asarray(globs, dtype=np.float32)),
        ).squeeze(-1)
        probs = torch.sigmoid(logits).numpy()

    return probs, np.asarray(outs), n_games


class TestInferenceOrientation:
    """The net's scalar means P(record-perspective P0 wins): near game end it must track
    the actual winner. An inversion scores ~0.05 / ~0.95 / ~2.5% against these gates
    (measured v221 SWA, 60 games / 120 records: 0.952 / 0.025 / 97.5%)."""

    def test_winner_perspective_values_high(self, decided_endgame_probs):
        probs, outs, _ = decided_endgame_probs
        win = probs[outs == 1.0]
        assert len(win) > 0
        print(f"\n[A6-b] mean prob | P0 eventually WON  ({len(win)} recs): {win.mean():.3f}")
        assert win.mean() > 0.80, f"winner-perspective mean {win.mean():.3f} <= 0.80"

    def test_loser_perspective_values_low(self, decided_endgame_probs):
        probs, outs, _ = decided_endgame_probs
        lose = probs[outs == 0.0]
        assert len(lose) > 0
        print(f"\n[A6-b] mean prob | P0 eventually LOST ({len(lose)} recs): {lose.mean():.3f}")
        assert lose.mean() < 0.20, f"loser-perspective mean {lose.mean():.3f} >= 0.20"

    def test_decided_positions_sided_correctly(self, decided_endgame_probs):
        probs, outs, n_games = decided_endgame_probs
        sided = ((probs > 0.5) == (outs == 1.0)).mean()
        print(f"\n[A6-b] sided correctly: {sided * 100:.1f}% "
              f"({len(probs)} records, {n_games} games)")
        assert sided >= 0.85, f"only {sided * 100:.1f}% of last-ply records sided correctly"
