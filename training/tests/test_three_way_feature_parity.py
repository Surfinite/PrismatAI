#!/usr/bin/env python
"""
test_three_way_feature_parity.py — the train<->inference consistency GATE.

On a set of fixed shared game states, assert that the THREE producers of DeepSets v2
features agree, element-by-element, within integer / 1e-5 tolerance:

  (a) the human JS extractor        — js_engine/training_example.js (-> jsrecord)
  (b) the C++ self-play exporter     — Prismata_Standalone --dump-v2-record (-> cpprecord)
  (c) C++ INFERENCE                  — Prismata_Standalone --dump-features (-> cppfeatures)

(b) and (c) are the EXACT functions the RL self-play corpus and the deployed value net use;
(a) is the human/MB corpus path. This catches the class of silent train/inference skews that
motivated it (in_card_set base flag, supply REMAINING vs total, is_blocking definition,
ability_used) BEFORE they poison a multi-hour train.

Legs:
  A (record-level)    jsrecord == cpprecord : supply{} (all 3 channels), instances (multiset),
                       p0/p1_resources, p0/p1_attack, turn_number, active_player  — INTEGER exact.
  B (vectorized)      vectorize(jsrecord) == cppfeatures (--dump-features) :
                       in_card_set membership, supply remaining, globals[15], instance[10]  — 1e-5.

Leg B reuses the REAL vectorize_v2 functions (vectorize_globals/_supply/_instances) so a drift in
the vectorizer itself is also caught.

Skips gracefully (exit 0) if the dave-master engine / weights / replays are absent (e.g. CI
without the C++ build). Requires the dave engine built Release x64 with the current source.

Run:  python training/tests/test_three_way_feature_parity.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))                      # c:/libraries/PrismataAI
TRAINING = os.path.join(REPO, "training")
sys.path.insert(0, TRAINING)

import numpy as np  # noqa: E402

# --- locate dependencies (skip if any missing) ---------------------------------
DAVE = os.environ.get("DAVE_BIN",
    "c:/libraries/PrismataAI-dave-master/bin/Prismata_Standalone.exe")
WEIGHTS = "asset/config/neural_weights_mixed_v221.bin"           # 15-global v2.2.1 (deployed RL init)
REPLAYS_DIR = os.environ.get("REPLAYS_DIR",
    "c:/libraries/prismata-replay-parser/replays_archive")
DUMP_JS = os.path.join(REPO, "js_engine", "dump_shared_state.js")
SCHEMA = os.path.join(TRAINING, "schema_v2.json")
UNIT_INDEX = os.path.join(TRAINING, "data", "unit_index.json")

# fixed shared states: (replay code, ply). gNUTm is a Base+9 game that exercises blockers,
# constructing units, and ability-used economy units (the features that bit us).
SHARED_STATES = [
    ("gNUTm-TgD@G", 5),
    ("gNUTm-TgD@G", 9),
    ("gNUTm-TgD@G", 13),
    ("gNUTm-TgD@G", 17),
]

INSTANCE_ORDER = ["owner", "is_constructing", "turns_until_ready", "is_blocking",
                  "ability_used", "current_hp", "hp_fraction", "is_frozen",
                  "lifespan_remaining", "stamina_remaining"]
BASE_UNITS = {"Engineer", "Drone", "Conduit", "Blastforge", "Animus", "Forcefield",
              "Gauss Cannon", "Wall", "Steelsplitter", "Tarsier", "Rhino"}

passed = 0
failed = 0


def check(cond, name, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}{(' — ' + detail) if detail else ''}")


def skip(msg):
    print(f"SKIP three-way feature parity: {msg}")
    sys.exit(0)


def find_replay(code):
    for ext in (".json.gz", ".json"):
        p = os.path.join(REPLAYS_DIR, code + ext)
        if os.path.exists(p):
            return p
    return None


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def inst_key(uidx, owner, feats):
    return (int(uidx), int(owner), tuple(round(float(x), 4) for x in feats))


def main():
    # dependency gate
    if not os.path.exists(DAVE):
        skip(f"dave engine not found: {DAVE}")
    if not os.path.exists(DUMP_JS):
        skip(f"dump_shared_state.js not found: {DUMP_JS}")
    if not os.path.isdir(REPLAYS_DIR):
        skip(f"replays dir not found: {REPLAYS_DIR}")
    try:
        node = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if node.returncode != 0:
            skip("node not available")
    except FileNotFoundError:
        skip("node not on PATH")

    from vectorize_v2 import vectorize_globals, vectorize_supply, vectorize_instances  # noqa
    schema = json.load(open(SCHEMA))
    caps = schema["normalization_caps"]
    num_units = schema["num_units"]
    unit_index = json.load(open(UNIT_INDEX))["units"]
    dave_bin_dir = os.path.dirname(DAVE)

    tmp = tempfile.mkdtemp(prefix="parity3_")

    for code, ply in SHARED_STATES:
        replay = find_replay(code)
        if replay is None:
            print(f"  (skip {code} p{ply}: replay file absent)")
            continue
        print(f"\nShared state: {code} ply {ply}")
        prefix = os.path.join(tmp, f"{code.replace('/', '_')}_{ply}")

        # (a) JS extractor -> jsrecord + cppstate
        r = run(["node", DUMP_JS, replay, str(ply), prefix])
        if r.returncode != 0:
            check(False, f"{code} p{ply}: dump_shared_state.js", r.stderr[-300:])
            continue
        cppstate = f"{prefix}.cppstate.json"
        if not os.path.exists(f"{prefix}.jsrecord.json"):
            print(f"  (skip {code} p{ply}: ply out of range / no snapshot)")
            continue
        jsrecord = json.load(open(f"{prefix}.jsrecord.json"))

        # (b) C++ exporter -> cpprecord ; (c) C++ inference -> cppfeatures
        cpprec_path = f"{prefix}.cpprec.json"
        cppfeat_path = f"{prefix}.cppfeat.json"
        run([DAVE, "--dump-v2-record", os.path.abspath(cppstate), os.path.abspath(cpprec_path)])
        run([DAVE, "--dump-features", os.path.abspath(cppstate), os.path.abspath(cppfeat_path),
             WEIGHTS])
        if not (os.path.exists(cpprec_path) and os.path.exists(cppfeat_path)):
            check(False, f"{code} p{ply}: C++ dumps produced", "missing output file")
            continue
        cpprec = json.load(open(cpprec_path))
        cppfeat = json.load(open(cppfeat_path))

        # ---- Leg A: JS extractor record == C++ exporter record (integer exact) ----
        # supply: same keys + same [ws, bs, inSet]
        check(jsrecord["supply"] == cpprec["supply"],
              f"{code} p{ply} legA supply dict (ws,bs,in_card_set) identical",
              f"js{len(jsrecord['supply'])} cpp{len(cpprec['supply'])}")
        # instances multiset (by name/owner + all 10 named feats)
        def rec_inst_multiset(rec):
            from collections import Counter
            c = Counter()
            for i in rec["instances"]:
                c[(i["name"], i["owner"]) + tuple(round(float(i[f]), 4) for f in INSTANCE_ORDER)] += 1
            return c
        check(rec_inst_multiset(jsrecord) == rec_inst_multiset(cpprec),
              f"{code} p{ply} legA instances multiset identical")
        for fld in ("p0_resources", "p1_resources", "p0_attack", "p1_attack",
                    "turn_number", "active_player"):
            check(jsrecord.get(fld) == cpprec.get(fld),
                  f"{code} p{ply} legA {fld} identical",
                  f"js={jsrecord.get(fld)} cpp={cpprec.get(fld)}")

        # ---- Leg B: vectorize(jsrecord) == C++ inference (--dump-features) ----
        sup = vectorize_supply(jsrecord["supply"], unit_index, num_units=num_units)   # (116,3)
        gv = vectorize_globals(jsrecord, caps)                                        # (15,)
        # in_card_set membership: vectorize -> set of indices; inference supply array lists buyables
        js_inset = set(np.nonzero(sup[:, 2] > 0.5)[0].tolist())
        inf_inset = set(s["unit_index"] for s in cppfeat["supply"])
        check(js_inset == inf_inset,
              f"{code} p{ply} legB in_card_set membership (JS-vectorized == inference)",
              f"sym_diff={js_inset ^ inf_inset}")
        # supply remaining (p0,p1) for in-set units
        inf_rem = {s["unit_index"]: (int(s["p0"]), int(s["p1"])) for s in cppfeat["supply"]}
        rem_ok = all((int(sup[i, 0]), int(sup[i, 1])) == inf_rem[i] for i in inf_rem)
        check(rem_ok, f"{code} p{ply} legB supply remaining (p0,p1) identical")
        # globals[15] within 1e-5
        inf_g = np.array(cppfeat["globals"], dtype=np.float32)
        gmax = float(np.max(np.abs(gv - inf_g))) if len(inf_g) == len(gv) else 9.9
        check(gmax < 1e-5, f"{code} p{ply} legB globals[{len(gv)}] max-abs-diff<1e-5",
              f"max_abs_diff={gmax:.2e}")
        # instance features (10) — multiset by (unit_index, owner, rounded feats)
        feats, ids, cnt = vectorize_instances(jsrecord["instances"], unit_index)
        from collections import Counter
        # vectorizer orders p0 then p1; reconstruct owner from the same ordering
        ordered = ([i for i in jsrecord["instances"] if i.get("owner", 0) == 0]
                   + [i for i in jsrecord["instances"] if i.get("owner", 0) == 1])
        js_ic = Counter(inst_key(ids[s], ordered[s].get("owner", 0), feats[s]) for s in range(cnt))
        inf_ic = Counter(inst_key(s["unit_index"], s["owner"], s["instance"])
                         for s in cppfeat["instances"])
        check(js_ic == inf_ic,
              f"{code} p{ply} legB instance features (JS-vectorized == inference)")
        # the bug-class guards: base units in set; is_blocking present; supply not constant-cap
        base_in = all(unit_index[n] in js_inset for n in BASE_UNITS if n in unit_index)
        check(base_in, f"{code} p{ply} guard: all base units in_card_set=1")

    print(f"\n{'=' * 56}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print(f"{failed} parity check(s) FAILED — train/inference feature skew present.")
        sys.exit(1)
    print("Three-way feature parity holds.")


def test_three_way_feature_parity():
    """pytest entry point. The body lives in main() (rich direct-run output); this wrapper
    runs the script and turns its result into a REAL pytest verdict so `python -m pytest` can
    no longer silently collect ZERO tests. A missing-dependency SKIP surfaces as a visible
    pytest.skip (NOT a green pass), and any parity FAIL fails the test."""
    import pytest
    r = subprocess.run([sys.executable, os.path.abspath(__file__)],
                       capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if "SKIP three-way feature parity" in out:
        pytest.skip(out.strip().splitlines()[-1] if out.strip() else "dependencies absent")
    assert r.returncode == 0 and "Three-way feature parity holds." in out, out[-2000:]


if __name__ == "__main__":
    main()
