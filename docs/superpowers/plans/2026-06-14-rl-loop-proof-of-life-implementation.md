# RL Loop Proof-of-Life Reframe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the RL self-play loop from an IG-axis measurement campaign into a runnable "proof-of-life" pipeline, reaching a fixed-generator end-to-end smoke as early as possible, then the promoting overnight loop.

**Architecture:** Config-only candidate/baseline changes in the dave-master engine (NoIG interior iterator; `MasterBot_SWF` = the existing AB `LiveHardestAI`; one general self-play block); a new frozen tuple (`campaign_frozen.json` v4); preflight + `run_eval.py` + `run_iteration.ps1` updated to the new tuple, anchor set (origin + masterbot), and proof-of-life gates (no REJECT/REVIEW verdict; abort-on-collapse); pre-launch safety automation (a6 + three-way + exe-sha in preflight); docs rewritten to v4.

**Tech Stack:** dave-master C++ engine (config JSON, prebuilt exes — NO rebuild), Python 3 (pytest; preflight_config.py, run_eval.py, vectorize/train), PowerShell (run_iteration.ps1, promote_candidate.ps1, run_checkpoint.ps1).

**Spec:** `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`. **Audit:** `docs/superpowers/plans/2026-06-13-rl-loop-deep-audit-FINDINGS.md`.

**Recon facts this plan is built on (verified 2026-06-14, read-only):**
- dave config `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt`.
- Candidate players: `RL_SelfPlay` (L261, generator, `MaxTraversals:1000`, `SelfPlaySampling:true`, `EpsilonLate:0.0`, `EpsilonIG:0.25`), `RL_Eval` (L262), `RL_Eval_iter0` (L264), `RL_Eval_origin` (L265) — all `RootMoveIterator:HardIterator_5var_IGsubset_Root`, `MoveIterator:HardIterator_5var` (auto-fires IG interior), `UCTConstant:0.3`, `WeightsFile:neural_weights_mixed_v221.bin`.
- Interior NoIG building blocks already exist: `V5_CS_NoIG` (L117), `AbilityActivateUtilityNoIG` (L100), `Ability_Filter_Live_NoIG` (L67, includes Hotel+Infusion Grid), `BaseIterator` (L205).
- `LiveHardestAI` (L259) = `Player_StackAlphaBeta`, 7000ms, `HardIterator_5var_Root`/`HardIterator_5var`, Playout, SWF buy tree + `LiveOpeningBook2`(50)+`DefaultOpeningBook`(4) + `Ability_Filter_Live` (incl. Odin) — the faithful AB MasterBot.
- Self-play blocks: `RL_SelfPlay_General` (L313, rounds 344, Seed 5600) + `RL_Step2_Smoke` (L312, rounds 172, ForcedCards Hotel, Seed 5500).
- Root vs interior iterator chosen by the player's `RootMoveIterator`/`MoveIterator` keys, not by `_Root` naming (`UCTNode.cpp:37-44`). AB vs UCT chosen by the player `"type"` (`AIParameters.cpp:919/955`); AB ignores `UCTConstant`/`MaxTraversals`.
- Loop docs/code: `eval/campaign_frozen.json`, `eval/preflight_config.py`, `eval/run_eval.py`, `eval/run_iteration.ps1`, `eval/promote_candidate.ps1`, `eval/run_checkpoint.ps1`, tests in `eval/tests/`.

**Working rules:** all config edits to `config.txt` must keep it strict-JSON, **no BOM** (utf-8 no BOM). After each config edit, re-parse it. Never run a full multi-hour self-play during build tasks; the Phase-0 smoke (Task 6.x) is the first real run and is gated behind a tiny `rounds` override. Commit after every task.

---

## Phase 0 — Critical path to a runnable fixed-generator smoke

### Task 1: Add the interior NoIG iterator + repoint candidate MoveIterators (config)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt` (Move Iterators section near L212; Players `RL_SelfPlay` L261, `RL_Eval` L262, `RL_Eval_iter0` L264, `RL_Eval_origin` L265)

- [ ] **Step 1: Add the new Move Iterator.** In the "Move Iterators" object, immediately after the `HardIterator_5var` entry, add:

```json
"HardIterator_5var_NoIG" : { "type":"PPPortfolio", "include":"BaseIterator", "PartialPlayers": [ [], ["V5_CS_NoIG"], [], [] ] },
```

- [ ] **Step 2: Repoint the candidate players' interior iterator.** On `RL_SelfPlay`, `RL_Eval`, `RL_Eval_iter0`, `RL_Eval_origin`, change `"MoveIterator":"HardIterator_5var"` to `"MoveIterator":"HardIterator_5var_NoIG"`. Leave each `RootMoveIterator` = `HardIterator_5var_IGsubset_Root` unchanged. **Do NOT touch `RL_Narrow`** (it stays the deployed/narrow baseline) or `LiveHardestAI`.

- [ ] **Step 3: Verify strict JSON + the edits landed.**

Run:
```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); mi=c['Move Iterators']; assert mi['HardIterator_5var_NoIG']['PartialPlayers']==[[],['V5_CS_NoIG'],[],[]]; p=c['Players']; assert all(p[n]['MoveIterator']=='HardIterator_5var_NoIG' for n in ['RL_SelfPlay','RL_Eval','RL_Eval_iter0','RL_Eval_origin']); assert all(p[n]['RootMoveIterator']=='HardIterator_5var_IGsubset_Root' for n in ['RL_SelfPlay','RL_Eval','RL_Eval_origin']); print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Verify the engine resolves the new iterator (no rebuild — just construction).** Probe one IG-live state through the candidate to confirm it loads and the interior NoIG iterator constructs without a FATAL:

Run:
```bash
node c:/libraries/PrismataAI/js_engine/query_move.js c:/libraries/PrismataAI/eval/ig_battery/$(ls c:/libraries/PrismataAI/eval/ig_battery | head -1) --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe --root-iterator HardIterator_5var_IGsubset_Root 2>&1 | tail -20
```
Expected: a move is returned (a JSON with clicks / IG count), no `FATAL:` line. (If `query_move.js` needs a different invocation, fall back to confirming via the Task-5 preflight, which asserts the iterator shape.)

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): NoIG interior iterator for candidate players (never auto-fire IG in lookahead)"
```

---

### Task 2: Add the `MasterBot_SWF` baseline alias (config)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt` (Players section, near `LiveHardestAI` L259)

- [ ] **Step 1: Add the alias.** In the "Players" object, after `LiveHardestAI`, add a verbatim-body alias:

```json
"MasterBot_SWF" : { "type":"Player_StackAlphaBeta", "TimeLimit":7000, "MaxChildren":40, "RootMoveIterator":"HardIterator_5var_Root", "MoveIterator":"HardIterator_5var", "Eval":"Playout", "PlayoutPlayer":"Playout" },
```

- [ ] **Step 2: Verify JSON + faithfulness fields.**

Run:
```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); m=c['Players']['MasterBot_SWF']; assert m['type']=='Player_StackAlphaBeta' and m['Eval']=='Playout' and m['RootMoveIterator']=='HardIterator_5var_Root' and 'UCTConstant' not in m; books=c['Opening Books']; assert len(books['LiveOpeningBook2'])==50 and len(books['DefaultOpeningBook'])==4; assert 'Odin' in c['Filters']['Ability_Filter_Live']['cards']; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): add MasterBot_SWF (AB SWF-faithful MasterBot alias of LiveHardestAI)"
```

---

### Task 3: Collapse self-play to one general block; set v4 exploration knobs (config)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt` (`RL_SelfPlay` L261; `RL_SelfPlay_General` L313)

- [ ] **Step 1: Set the generator's exploration knobs to v4.** On `RL_SelfPlay`, change `"EpsilonIG":0.25` → `"EpsilonIG":0.0` and `"EpsilonLate":0.0` → `"EpsilonLate":0.05`. Leave `TemperatureTau:0.7`, `TemperatureK:12`, `EpsilonUniform:0.0`, `MaxTraversals:1000`, `UCTConstant:0.3`, `SelfPlaySampling:true` unchanged.

- [ ] **Step 2: Bump the general block volume.** On `RL_SelfPlay_General`, change `"rounds":344` → `"rounds":516` (= 1032 games, preserving the training dose now that the forced block is dropped). Leave `Seed:5600`, `Threads:8`, `RandomCards:8`, `run:false` unchanged.

- [ ] **Step 3: Leave `RL_Step2_Smoke` in the file but unused.** Do NOT delete it (keeps git diff small and the block available for a future IG axis); the v4 frozen tuple + driver simply never reference/flip it. Confirm it still rests `"run":false`.

- [ ] **Step 4: Verify.**

Run:
```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); sp=c['Players']['RL_SelfPlay']; assert sp['EpsilonIG']==0.0 and sp['EpsilonLate']==0.05; b={x['name']:x for x in c['Benchmarks']}; assert b['RL_SelfPlay_General']['rounds']==516 and b['RL_SelfPlay_General'].get('run')!=True; assert b['RL_Step2_Smoke'].get('run')!=True; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): v4 self-play — general-only (516 rounds), EpsilonIG off, EpsilonLate 0.05"
```

---

### Task 4: Add the origin + masterbot eval tournament blocks (config)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt` (Benchmarks section)

The proof-of-life eval needs two C++ tournament blocks: candidate (`RL_Eval`) vs `RL_Eval_origin` (relative), and candidate vs `MasterBot_SWF` (absolute). Both `run:false` at rest; the driver flips them.

- [ ] **Step 1: Add the two blocks** in the "Benchmarks" array:

```json
{ "run":false, "type":"Tournament", "name":"RL_PoL_origin", "rounds":48, "Seed":2026, "UpdateIntervalSec":5, "Threads":8, "RandomCards":8, "players":[{"name":"RL_Eval","group":1},{"name":"RL_Eval_origin","group":2}] },
{ "run":false, "type":"Tournament", "name":"RL_PoL_masterbot", "rounds":48, "Seed":2026, "UpdateIntervalSec":5, "Threads":8, "RandomCards":8, "players":[{"name":"RL_Eval","group":1},{"name":"MasterBot_SWF","group":2}] },
```
(rounds 48 = 96 games each after colour-swap, per spec §6.)

- [ ] **Step 2: Verify JSON + both blocks present, run:false.**

Run:
```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); b={x['name']:x for x in c['Benchmarks']}; assert b['RL_PoL_origin']['rounds']==48 and b['RL_PoL_masterbot']['players'][1]['name']=='MasterBot_SWF'; assert b['RL_PoL_origin'].get('run')!=True and b['RL_PoL_masterbot'].get('run')!=True; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): add RL_PoL_origin + RL_PoL_masterbot eval blocks (proof-of-life anchors)"
```

---

### Task 5: Write `campaign_frozen.json` v4

**Files:**
- Create/replace: `c:/libraries/PrismataAI/eval/campaign_frozen.json` (snapshot the old one first)

- [ ] **Step 1: Snapshot the v3 tuple for reference.**

```bash
cp c:/libraries/PrismataAI/eval/campaign_frozen.json c:/libraries/PrismataAI/eval/campaign_frozen_ig_v3.json
```

- [ ] **Step 2: Capture the engine exe sha (for the M4 pin).**

Run:
```bash
python -c "import hashlib;print(hashlib.sha256(open(r'c:/libraries/PrismataAI-dave-master/bin/Prismata_Testing.exe','rb').read()).hexdigest())"
```
Record the value as `<TESTING_EXE_SHA>` for Step 3. (Also note `PrismataAI.exe`'s sha the same way as `<PRISMATAAI_EXE_SHA>`.)

- [ ] **Step 3: Write the v4 tuple.** Replace `eval/campaign_frozen.json` with (substitute the two sha values from Step 2):

```json
{
  "tuple_version": 4,
  "regime": "proof-of-life (2026-06-14): systems pipeline validation, no axis under test",
  "frozen_N": 1000,
  "TemperatureK": 12,
  "TemperatureTau": 0.7,
  "EpsilonUniform": 0.0,
  "EpsilonLate": 0.05,
  "EpsilonIG": 0.0,
  "UCTConstant": 0.3,
  "parent_bin": "neural_weights_mixed_v221.bin",
  "parent_bin_sha256": "22cc647ee7b7427e79bde539f331979ce5d95eec309d69495a1ba2fc88c57e97",
  "parent_pt": "training/models/deepsets_v221/swa_model.pt",
  "parent_val_acc_pct": 71.8,
  "origin_bin": "neural_weights_mixed_v221.bin",
  "origin_val_acc_pct": 71.8,
  "engine_testing_exe_sha256": "<TESTING_EXE_SHA>",
  "engine_prismataai_exe_sha256": "<PRISMATAAI_EXE_SHA>",
  "selfplay_threads": 8,
  "selfplay_block": "RL_SelfPlay_General",
  "selfplay_rounds": 516,
  "selfplay_seed_base": 5600,
  "candidate_interior_iterator": "HardIterator_5var_NoIG",
  "candidate_root_iterator": "HardIterator_5var_IGsubset_Root",
  "eval_budget": { "TimeLimit": 7000, "MaxTraversals": 100000, "UCTConstant": 0.3 },
  "anchor_blocks": {
    "RL_PoL_origin":    { "rounds": 48, "Seed": 2026, "Threads": 8 },
    "RL_PoL_masterbot": { "rounds": 48, "Seed": 2026, "Threads": 8 }
  },
  "abort_winrate_vs_origin": 0.35,
  "replay_window": 2,
  "train_schedule": { "epochs": 6, "lr": 1e-05, "swa": false, "rehearsal_start": 0.10, "rehearsal_floor": 0.10, "rehearsal_decay": 0.0 },
  "rehearsal_file": "training/data/human_elite_2000_45s_v2.h5",
  "tripwire_val_file": "training/data/human_val_1700_50k_v2.h5",
  "prediction_movement_floor": null,
  "game_length_band": null,
  "promotion_policy": "promote-unless-collapse: Phase 0 = no promotion (fixed generator). Phase 1 = promote every candidate UNLESS the run aborted (crash / val-acc collapse / winrate-vs-origin < abort_winrate_vs_origin / degenerate self-play).",
  "tiers": {
    "hp": ["frozen_N","TemperatureK","TemperatureTau","EpsilonUniform","EpsilonLate","EpsilonIG","UCTConstant","eval_budget","train_schedule","rehearsal_file","tripwire_val_file","promotion_policy","candidate_interior_iterator","candidate_root_iterator"],
    "scale": ["selfplay_threads","selfplay_rounds","selfplay_seed_base","anchor_blocks","replay_window","abort_winrate_vs_origin"],
    "rule": "changing an 'hp' key = a NEW campaign; a 'scale' key = re-anchor + a campaign_log entry. parent_* via promote_candidate.ps1 only; origin_bin never changes."
  },
  "frozen_date": "2026-06-14"
}
```
Note: `prediction_movement_floor` and `game_length_band` are intentionally `null` here and get filled from the Phase-0 smoke (spec §9), then committed before Phase 1.

- [ ] **Step 4: Verify it parses + key fields.**

Run:
```bash
python -c "import json; f=json.load(open(r'c:/libraries/PrismataAI/eval/campaign_frozen.json',encoding='utf-8-sig')); assert f['tuple_version']==4 and f['EpsilonIG']==0.0 and f['EpsilonLate']==0.05 and f['selfplay_rounds']==516 and f['replay_window']==2 and f['candidate_interior_iterator']=='HardIterator_5var_NoIG'; assert set(f['anchor_blocks'])=={'RL_PoL_origin','RL_PoL_masterbot'}; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/campaign_frozen.json eval/campaign_frozen_ig_v3.json && git commit -m "eval(rl): campaign_frozen v4 (proof-of-life tuple); archive v3"
```

---

### Task 6: Rewrite `preflight_config.py` for the v4 tuple

`preflight_config.py` is structured around the v3 two-block mix, four parent pins, and iter0/narrow anchors. Rewrite the campaign-specific checks for v4: one self-play block, the NoIG interior iterator shape, the new anchors, EpsilonLate=0.05/EpsilonIG=0, and the candidate-side parent pins (`RL_SelfPlay`/`RL_Eval`/`RL_Eval_origin`; drop `RL_Narrow`/`RL_Eval_iter0` from the required set). Keep the generic checks (json_bom, run_true, book_sizes, reference_graph, use_dsnn_sentinel, unit_index, existences, parent_sha, origin_pin, eval_budget). TDD against `eval/tests/test_preflight.py`.

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/preflight_config.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_preflight.py`

- [ ] **Step 1: Update the module constants** at the top of `preflight_config.py`:

```python
RL_ROOT_ITERATOR     = "HardIterator_5var_IGsubset_Root"
RL_WRAPPED_ITERATOR  = "HardIterator_5var_NoIG_Root"
RL_INTERIOR_ITERATOR = "HardIterator_5var_NoIG"          # v4: interior never auto-fires IG
RL_SUBSET_FILTER     = "IG_Only"
RL_PORTFOLIO_DIMS    = [1, 5, 5, 1]
RL_ABILITY_VARIANTS  = {"V5_CS2_NoIG", "V5_CS_NoIG", "V5_CSNF_NoIG",
                        "V5_CSClickNC_NoIG", "V5_CSClickNF_NoIG"}
RL_OB_VARIANT        = "V5_CS2_NoIG"
RL_OB_BOOK           = "LiveOpeningBook2"
BOOK_SIZES           = {"LiveOpeningBook2": 50, "DefaultOpeningBook": 4}
EVAL_BUDGET_PLAYERS  = ("RL_Eval", "RL_Eval_origin")     # v4: iter0/narrow dropped from the gate set
PARENT_PINNED_PLAYERS = (
    ("RL_Eval", "the eval candidate pin"),
    ("RL_SelfPlay", "the self-play DATA GENERATOR"),
)
SELFPLAY_INTERIOR_PLAYERS = ("RL_SelfPlay", "RL_Eval", "RL_Eval_origin")
```

- [ ] **Step 2: Write a failing test for the interior-iterator check.** Add to `eval/tests/test_preflight.py`:

```python
def test_interior_noig_iterator_required(minimal_cfg):
    # minimal_cfg is a dict fixture with the v4 shape; flip the interior iterator back to the IG one
    minimal_cfg["Players"]["RL_SelfPlay"]["MoveIterator"] = "HardIterator_5var"
    from preflight_config import check_iterator_shape
    fails = check_iterator_shape(minimal_cfg)
    assert any("HardIterator_5var_NoIG" in f for f in fails)
```
(If `test_preflight.py` has no `minimal_cfg` fixture, add one that loads the live config via `load_config` and deep-copies it, or build the smallest dict the checks read.)

- [ ] **Step 3: Run it — expect FAIL** (the current `check_iterator_shape` doesn't assert the interior iterator).

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py::test_interior_noig_iterator_required -v`
Expected: FAIL

- [ ] **Step 4: Extend `check_iterator_shape`** to assert each `SELFPLAY_INTERIOR_PLAYERS` player has `MoveIterator == RL_INTERIOR_ITERATOR`, and that `RL_INTERIOR_ITERATOR` exists as a `PPPortfolio` whose `PartialPlayers` == `[[], ["V5_CS_NoIG"], [], []]`. Add after the existing root-iterator checks:

```python
    interior = iterators.get(RL_INTERIOR_ITERATOR)
    if not isinstance(interior, dict):
        failures.append("Move Iterator '%s' not found (v4 interior NoIG iterator)" % RL_INTERIOR_ITERATOR)
    elif interior.get("type") != "PPPortfolio" or interior.get("PartialPlayers") != [[], ["V5_CS_NoIG"], [], []]:
        failures.append("%s must be PPPortfolio with PartialPlayers [[],['V5_CS_NoIG'],[],[]] (got %s / %s)"
                        % (RL_INTERIOR_ITERATOR, interior.get("type"), interior.get("PartialPlayers")))
    players = cfg.get("Players", {})
    for pname in SELFPLAY_INTERIOR_PLAYERS:
        node = players.get(pname)
        if isinstance(node, dict) and node.get("MoveIterator") != RL_INTERIOR_ITERATOR:
            failures.append("%s.MoveIterator is %r, expected %r (v4: interior must never auto-fire IG)"
                            % (pname, node.get("MoveIterator"), RL_INTERIOR_ITERATOR))
```

- [ ] **Step 5: Run it — expect PASS.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py::test_interior_noig_iterator_required -v`
Expected: PASS

- [ ] **Step 6: Replace `check_frozen_tuple`'s self-play-mix logic** with a single-block version. Remove the two-block `selfplay_mix`/`ForcedCards`/seed-base-dict handling; replace with a read of the v4 scalar keys. The numeric tuple (`MaxTraversals/TemperatureK/TemperatureTau/EpsilonUniform/UCTConstant`) check stays; the EpsilonLate/EpsilonIG exact-match checks stay (now frozen 0.05 / 0.0). Add:

```python
    block_name = frozen.get("selfplay_block", "RL_SelfPlay_General")
    blocks = {b.get("name"): b for b in cfg.get("Benchmarks", []) if isinstance(b, dict)}
    blk = blocks.get(block_name)
    if blk is None:
        failures.append("self-play block '%s' not found in Benchmarks" % block_name)
    else:
        if "selfplay_rounds" in frozen and int(blk.get("rounds", -1)) != int(frozen["selfplay_rounds"]):
            failures.append("%s.rounds is %s but frozen selfplay_rounds is %s" % (block_name, blk.get("rounds"), frozen["selfplay_rounds"]))
        if "selfplay_seed_base" in frozen and int(blk.get("Seed", -1)) != int(frozen["selfplay_seed_base"]):
            failures.append("%s.Seed is %s at rest but frozen selfplay_seed_base is %s (driver sets base+K transiently)" % (block_name, blk.get("Seed"), frozen["selfplay_seed_base"]))
        if "selfplay_threads" in frozen and int(blk.get("Threads", 1)) != int(frozen["selfplay_threads"]):
            failures.append("%s.Threads is %s but frozen selfplay_threads is %s" % (block_name, blk.get("Threads"), frozen["selfplay_threads"]))
        if "ForcedCards" in blk:
            failures.append("%s must have NO ForcedCards in v4 (general-only)" % block_name)
        if blk.get("run") is True:
            failures.append("%s must rest run:false" % block_name)
```

- [ ] **Step 7: Update `check_anchor_blocks`** — it already reads `frozen['anchor_blocks']` generically, so it now validates `RL_PoL_origin`/`RL_PoL_masterbot`. Remove any hardcoded `RL_Eval_iter0_*`/`RL_Eval_narrow_*` names if present. Confirm `check_origin_pin` still targets `RL_Eval_origin`.

- [ ] **Step 8: Run the full preflight test file.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py -v`
Expected: PASS (update any v3-shape assertions in the test file that reference the two-block mix / iter0 / narrow to the v4 shape).

- [ ] **Step 9: Run preflight against the LIVE config — expect PASS.**

Run: `cd c:/libraries/PrismataAI && python eval/preflight_config.py --config c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt --frozen eval/campaign_frozen.json`
Expected: `preflight PASSED`. Fix any FAIL line by reconciling config↔frozen (NOT by loosening a check) until green.

- [ ] **Step 10: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/preflight_config.py eval/tests/test_preflight.py && git commit -m "eval(rl): preflight v4 — one self-play block, NoIG interior iterator, PoL anchors"
```

---

### Task 7: Rewrite `run_eval.py` anchors + drop the verdict (proof-of-life eval)

Replace the iter0/narrow/steam anchor machinery + REJECT/REVIEW verdict with the two PoL anchors (`origin`, `masterbot`) and an abort-on-collapse signal. Keep the engine-load provenance, incremental atomic manifest, Wilson CI, and HTML statsTable parsing (all sound per the audit). TDD against `eval/tests/test_run_eval_main.py`.

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/run_eval.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_run_eval_main.py`

- [ ] **Step 1: Replace the anchor registry.** Set:

```python
ANCHOR_BLOCKS = {
    "origin":    {"general": ["RL_PoL_origin"]},
    "masterbot": {"general": ["RL_PoL_masterbot"]},
}
ANCHOR_OPPONENTS = {
    "origin":    ("RL_Eval_origin", "origin"),
    "masterbot": ("MasterBot_SWF", None),   # AB Playout opponent: no NeuralNet load line to confirm
}
```

- [ ] **Step 2: Write a failing test for the collapse signal.** Add to `test_run_eval_main.py`:

```python
def test_collapse_flag_set_when_origin_below_threshold():
    from run_eval import compute_collapse
    cell = {"win_rate": 0.30, "games": 96, "ci": [0.22, 0.39]}
    assert compute_collapse(cell, threshold=0.35) is True
    cell2 = {"win_rate": 0.52, "games": 96, "ci": [0.42, 0.62]}
    assert compute_collapse(cell2, threshold=0.35) is False
    assert compute_collapse(None, threshold=0.35) is None   # incomplete -> unknown, not collapse
```

- [ ] **Step 2b: Run it — expect FAIL** (`compute_collapse` undefined).

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_run_eval_main.py::test_collapse_flag_set_when_origin_below_threshold -v`
Expected: FAIL

- [ ] **Step 3: Add `compute_collapse`** and replace `compute_verdict`/`_refresh_verdict`'s verdict logic. `compute_collapse` returns `True` if the origin cell completed and `win_rate < threshold` (using the point estimate — this is a coarse abort, not a powered gate), `False` if it completed at/above threshold, `None` if missing/0-games:

```python
def compute_collapse(origin_cell, threshold):
    if not (isinstance(origin_cell, dict) and "win_rate" in origin_cell and origin_cell.get("games")):
        return None
    return origin_cell["win_rate"] < threshold
```
In `_refresh_verdict` (rename to `_refresh_summary`), set `manifest["collapse"] = compute_collapse(origin_general_cell, threshold)` and record both anchors' win-rate + CI as information; drop `verdict`/`verdict_inputs`/`decision`. Read `threshold` from a new `--abort-winrate` arg (default 0.35).

- [ ] **Step 4: Run it — expect PASS.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_run_eval_main.py::test_collapse_flag_set_when_origin_below_threshold -v`
Expected: PASS

- [ ] **Step 5: Update `main()` / `build_manifest()`** — default `--anchors` to `["origin", "masterbot"]`, pools to `["general"]`; thread `--origin-weights` (required for the origin opponent provenance) and `--abort-winrate`; remove the steam-anchor block and the `--parent-weights` self-match guard's verdict coupling (keep the sha stamps). For the `masterbot` anchor, opponent is AB/Playout so skip `engine_confirmed_parent_load` (the marker only exists for NeuralNet players) — only the candidate's own load is confirmed.

- [ ] **Step 6: Run the whole eval test file.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/ -v`
Expected: PASS (update v3-verdict assertions in the tests to the collapse/summary shape).

- [ ] **Step 7: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/run_eval.py eval/tests/test_run_eval_main.py && git commit -m "eval(rl): PoL eval — origin+masterbot anchors, collapse-on-abort (no REJECT/REVIEW verdict)"
```

---

### Task 8: Update `run_iteration.ps1` — one self-play block, drop tactical, new eval call

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/run_iteration.ps1`

- [ ] **Step 1: Stage 1 — single general block.** Remove the forced-block path: drop `$selfplayDir` (rl_step2_v2) handling, the `RL_Step2_Smoke` seed/run flips, and the forced parity/replay dirs. Keep only `RL_SelfPlay_General` (`$selfplayDirGen`, `$parityLiveGen`, `asset/replays/rl_selfplay_general`). Set its Seed = `selfplay_seed_base + K` from frozen, flip `run:true`, run the engine, restore in `finally`. Update the stage-2 concat to use the single general shard dir.

- [ ] **Step 2: Stage 6 — remove the tactical suite call** entirely (IG-specific; spec §7).

- [ ] **Step 3: Stage 7 — new eval invocation.** Replace the `run_eval.py --anchors iter0 --pools forced general` call with:

```powershell
python "$eval/run_eval.py" --iteration $K `
    --weights $candBin --parent-weights $parentBin --origin-weights $($frozen.origin_bin) `
    --dave-bin $bin `
    --anchors origin masterbot --pools general --abort-winrate $($frozen.abort_winrate_vs_origin) `
    --out "$eval/manifests"
```
After it returns, read `manifest.collapse`; if `$true`, write a loud `*** COLLAPSE: winrate vs origin below abort threshold ***` line and set the iteration result to ABORTED (Phase 1 will refuse promotion on it).

- [ ] **Step 4: Stage 8 / closing message** — drop IG-coverage-specific output; keep the dashboard. Update the closing PROMOTE guidance to the v4 policy (see Task 12): "Phase 0: do NOT promote. Phase 1: promote unless collapse / val-acc tripwire / degenerate."

- [ ] **Step 5: Dry-run the driver to stage 0 only** (preflight) to confirm it wires up without launching self-play. Temporarily invoke with a guard or read-through; at minimum confirm PowerShell parses the script:

Run: `pwsh -NoProfile -Command "& { . c:/libraries/PrismataAI/eval/run_iteration.ps1 -K 999 -ResumeFrom 8 } " 2>&1 | head -30`
Expected: it reaches stage 0 preflight (or errors only on the missing K=999 artifacts at the resume guard), with no PowerShell parse error. (Use a throwaway K and `-ResumeFrom` so no real run starts.)

- [ ] **Step 6: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/run_iteration.ps1 && git commit -m "driver(rl): v4 — single general self-play block, drop tactical, origin+masterbot eval + collapse abort"
```

---

### Task 9: Phase-0 fixed-generator smoke (FIRST REAL RUN — tiny)

Validate the whole pipeline end-to-end with v221 as a fixed generator, at a tiny round count, WITHOUT promotion. This is the milestone the whole phase targets.

**Files:**
- Temporary config override (revert after): `config.txt` `RL_SelfPlay_General.rounds`

- [ ] **Step 1: Temporarily shrink the self-play volume** for the smoke. In `config.txt`, set `RL_SelfPlay_General.rounds` to `4` (8 games) and update `eval/campaign_frozen.json` `selfplay_rounds` to `4` so preflight stays green. (This is a temporary smoke override; Task 9 Step 8 restores 516.)

- [ ] **Step 2: Run one iteration, no promotion.**

Run: `pwsh -NoProfile -File c:/libraries/PrismataAI/eval/run_iteration.ps1 -K 1`
Expected: stages 0→8 complete; a manifest at `eval/manifests/eval_iter_1.json`; NO promotion step runs.

- [ ] **Step 3: Confirm the pipeline produced each artifact.**

Run:
```bash
python -c "import json,glob,os; m=json.load(open(r'c:/libraries/PrismataAI/eval/manifests/eval_iter_1.json')); print('collapse',m.get('collapse')); print('anchors',list(m.get('anchors',{}))); pm=json.load(open(r'c:/libraries/PrismataAI/training/data/rl_iter_1/prediction_movement.json')); print('pred-move',pm); print('h5', os.path.exists(r'c:/libraries/PrismataAI/training/data/rl_iter_1/selfplay_iter_1.h5'))"
```
Expected: a `collapse` value (True/False/None), both anchors present, a prediction-movement number, the H5 exists.

- [ ] **Step 4: Record the calibration numbers.** From the smoke, read the actual game-length distribution (from the H5 / replays) and the prediction-movement value. These become the v4 `game_length_band` and `prediction_movement_floor` (spec §9). Compute a band (e.g. human-baseline median ± 2σ) and a floor (e.g. an order of magnitude below the observed fixed-probe |dP|).

- [ ] **Step 5: Run the second smoke iteration** to exercise the replay-window mechanics.

Run: `pwsh -NoProfile -File c:/libraries/PrismataAI/eval/run_iteration.ps1 -K 2`
Expected: completes; stage 3 trains over the W=2 window (iters 1+2).

- [ ] **Step 6: Self-play non-degeneracy check.** Confirm per-seat win-rate ∈ [0.35,0.65] and not-all-draws on the smoke data.

Run:
```bash
python -c "import h5py,numpy as np; f=h5py.File(r'c:/libraries/PrismataAI/training/data/rl_iter_1/selfplay_iter_1.h5','r'); g=f['globals'][:] if 'globals' in f else None; lab=f['labels'][:] if 'labels' in f else f['outcome_p0'][:]; print('n',len(lab),'mean_label',float(np.mean(lab)),'draws',int(np.sum(lab==0.5)))"
```
Expected: a sane mean (≈0.45–0.55) and not 100% draws. (Adjust dataset keys to the actual H5 schema.)

- [ ] **Step 7: Fill the calibrated thresholds into the frozen tuple.** Set `prediction_movement_floor` and `game_length_band` in `eval/campaign_frozen.json` to the Step-4 values.

- [ ] **Step 8: Restore the real self-play volume.** Set `config.txt` `RL_SelfPlay_General.rounds` back to `516` and `campaign_frozen.json` `selfplay_rounds` back to `516`. Re-run preflight → PASS.

- [ ] **Step 9: Commit the calibration + restore.**

```bash
cd c:/libraries/PrismataAI && git add eval/campaign_frozen.json && git commit -m "eval(rl): Phase-0 smoke calibration (pred-movement floor + game-length band); restore 516 rounds"
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): restore self-play rounds to 516 after Phase-0 smoke"
```

**>>> MILESTONE: the loop runs end-to-end (fixed generator). Phases 1-2 below harden it for the unattended overnight (Phase-1) run.**

---

## Phase 1 — Pre-launch safety automation (the must-dos before an unattended night)

### Task 10: Automate a6 orientation + three-way feature parity + exe-sha pin in preflight

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/preflight_config.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_preflight.py`

- [ ] **Step 1: Add an engine-exe sha check.** New function:

```python
def check_engine_sha(frozen, dave_bin):
    failures = []
    for key, exe in (("engine_testing_exe_sha256", "Prismata_Testing.exe"),
                     ("engine_prismataai_exe_sha256", "PrismataAI.exe")):
        want = frozen.get(key)
        if not want:
            continue
        path = os.path.join(dave_bin, exe)
        if not os.path.isfile(path):
            failures.append("engine exe not found for sha check: %s" % path); continue
        got = _sha256(path)
        if got.lower() != str(want).lower():
            failures.append("%s sha256 mismatch: %s = %s but frozen %s = %s -- the engine was rebuilt; "
                            "re-run a6 + three-way and re-pin (an unrecorded rebuild can silently flip the "
                            "value sign or a feature)" % (exe, exe, got, key, want))
    return failures
```
Wire it into `run_checks` (needs the dave bin dir — derive from `--config` like `check_use_dsnn_sentinel` does).

- [ ] **Step 2: Add a6 + three-way as subprocess gate checks.** New function that shells out and fails on nonzero exit:

```python
import subprocess
def check_correctness_gates(repo_root):
    failures = []
    a6 = subprocess.run([sys.executable, os.path.join(repo_root, "eval", "a6_orientation_check.py")],
                        capture_output=True, text=True)
    if a6.returncode != 0:
        failures.append("a6 orientation check FAILED (value sign-flip guard): %s" % (a6.stdout[-400:] + a6.stderr[-400:]))
    tw = subprocess.run([sys.executable, "-m", "pytest",
                         os.path.join(repo_root, "training", "tests", "test_three_way_feature_parity.py"), "-q"],
                        capture_output=True, text=True, cwd=repo_root)
    if tw.returncode != 0:
        failures.append("three-way feature parity gate FAILED: %s" % (tw.stdout[-400:]))
    return failures
```
Add a `--skip-slow-gates` flag so unit tests of preflight don't shell out; wire the real checks into `run_checks` when not skipped.

- [ ] **Step 3: Test (mock-free, fast): assert the sha mismatch fires.** Add to `test_preflight.py`:

```python
def test_engine_sha_mismatch_fires(tmp_path):
    from preflight_config import check_engine_sha
    exe = tmp_path / "Prismata_Testing.exe"; exe.write_bytes(b"x")
    fails = check_engine_sha({"engine_testing_exe_sha256": "deadbeef"}, str(tmp_path))
    assert any("sha256 mismatch" in f for f in fails)
```

- [ ] **Step 4: Run preflight tests.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py -v`
Expected: PASS

- [ ] **Step 5: Run full preflight with gates against the live config.**

Run: `cd c:/libraries/PrismataAI && python eval/preflight_config.py --config c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt --frozen eval/campaign_frozen.json`
Expected: `preflight PASSED` (a6 prints its 4 decisive values; three-way prints its pass count).

- [ ] **Step 6: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/preflight_config.py eval/tests/test_preflight.py && git commit -m "eval(rl): preflight auto-runs a6 + three-way gate + engine-exe sha pin (M4/M5)"
```

---

### Task 11: Preflight M2 check — self-play block uses RL_SelfPlay + SelfPlaySampling + IG-subset root

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/preflight_config.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_preflight.py`

- [ ] **Step 1: Failing test.**

```python
def test_selfplay_block_must_use_rl_selfplay(minimal_cfg):
    from preflight_config import check_selfplay_player
    b = next(x for x in minimal_cfg["Benchmarks"] if x["name"] == "RL_SelfPlay_General")
    b["players"] = [{"name": "RL_SelfPlay_N100", "group": 1}, {"name": "RL_SelfPlay_N100", "group": 2}]
    fails = check_selfplay_player(minimal_cfg, {"selfplay_block": "RL_SelfPlay_General"})
    assert any("RL_SelfPlay" in f for f in fails)
```

- [ ] **Step 2: Run — expect FAIL.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py::test_selfplay_block_must_use_rl_selfplay -v`
Expected: FAIL

- [ ] **Step 3: Implement `check_selfplay_player`** — assert both group slots of the frozen `selfplay_block` reference `RL_SelfPlay`, and that `Players.RL_SelfPlay` has `SelfPlaySampling==true` and `RootMoveIterator==RL_ROOT_ITERATOR`:

```python
def check_selfplay_player(cfg, frozen):
    failures = []
    bname = frozen.get("selfplay_block", "RL_SelfPlay_General")
    blk = next((b for b in cfg.get("Benchmarks", []) if isinstance(b, dict) and b.get("name") == bname), None)
    if blk is None:
        return ["self-play block '%s' not found" % bname]
    names = [p.get("name") for p in blk.get("players", []) if isinstance(p, dict)]
    if names != ["RL_SelfPlay", "RL_SelfPlay"]:
        failures.append("%s.players reference %s, expected RL_SelfPlay in both groups (the frozen-tuple "
                        "knobs are meaningless if a different player generates the data)" % (bname, names))
    sp = cfg.get("Players", {}).get("RL_SelfPlay", {})
    if sp.get("SelfPlaySampling") is not True:
        failures.append("RL_SelfPlay.SelfPlaySampling must be true (else Temperature/Epsilon are inert)")
    if sp.get("RootMoveIterator") != RL_ROOT_ITERATOR:
        failures.append("RL_SelfPlay.RootMoveIterator is %r, expected %r" % (sp.get("RootMoveIterator"), RL_ROOT_ITERATOR))
    return failures
```
Wire into `run_checks`.

- [ ] **Step 4: Run — expect PASS; then full preflight green.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py -v && cd c:/libraries/PrismataAI && python eval/preflight_config.py --config c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt --frozen eval/campaign_frozen.json`
Expected: tests PASS; `preflight PASSED`

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/preflight_config.py eval/tests/test_preflight.py && git commit -m "eval(rl): preflight M2 — self-play block must use RL_SelfPlay + sampling + IG-subset root"
```

---

### Task 12: Unattended-robustness fixes (host-kill + lockfile PID)

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/run_iteration.ps1`

- [ ] **Step 1: Lockfile PID-liveness.** Replace the unconditional throw on an existing lock with: parse `pid=` from the lock; if `Get-Process -Id $pid` finds no live process, log + reclaim the lock; otherwise refuse.

```powershell
if (Test-Path $lockFile) {
    $content = Get-Content -Raw $lockFile -ErrorAction SilentlyContinue
    $pidMatch = [regex]::Match($content, 'pid=(\d+)')
    $alive = $false
    if ($pidMatch.Success) { $alive = [bool](Get-Process -Id ([int]$pidMatch.Groups[1].Value) -ErrorAction SilentlyContinue) }
    if ($alive) { throw "another iteration is running (lock $lockFile, contents: $content)." }
    Write-Host "stale lock from a dead PID — reclaiming ($content)"
    Remove-Item $lockFile -ErrorAction SilentlyContinue
}
```

- [ ] **Step 2: Self-heal run/seed drift at stage 0.** Before preflight, if the config has the self-play block `run:true` or its Seed != base (a killed prior run), reset them via the existing `Edit-Config` helper and log it (preflight would otherwise hard-fail a recoverable, self-inflicted drift).

- [ ] **Step 3: Verify the script still parses + a stale-lock path reclaims.**

Run: `pwsh -NoProfile -Command "Set-Content -Path c:/libraries/PrismataAI/eval/.iteration.lock 'K=1 pid=999999 started=x'; & { try { . c:/libraries/PrismataAI/eval/run_iteration.ps1 -K 999 -ResumeFrom 8 } catch { Write-Host \"reached: $($_.Exception.Message)\" } }" 2>&1 | head -20`
Expected: a "reclaiming" log line (PID 999999 is dead), then it proceeds past the lock (erroring later only on the missing K=999 resume artifacts). Clean up the lock after.

- [ ] **Step 4: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/run_iteration.ps1 && git commit -m "driver(rl): lockfile PID-liveness + stage-0 run/seed self-heal (unattended robustness)"
```

---

## Phase 2 — Phase-1 promoting loop wiring

### Task 13: `promote_candidate.ps1` + `run_checkpoint.ps1` for promote-unless-collapse

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/promote_candidate.ps1`, `c:/libraries/PrismataAI/eval/run_checkpoint.ps1`

- [ ] **Step 1: promote gate → collapse.** In `promote_candidate.ps1`, replace the `verdict -ne 'REVIEW'` gate with: read `manifest.collapse`; refuse (without `-Force`) if `collapse -eq $true`, or if the 4.5 val-acc tripwire fired, or a reproduced tactical regression (tactical is dropped, so just collapse + tripwire). Keep the sha-verified lineage re-export and the parent-pin repoint, but update the pinned set to the v4 players (`RL_Eval`, `RL_SelfPlay`, `RL_Eval_origin` — NOT iter0/narrow); never repoint `RL_Eval_origin`'s weights.

- [ ] **Step 2: Fix the narrow-anchor manifest clobber.** Remove the narrow-anchor re-run from `promote_candidate.ps1` (narrow is dropped in v4), so the promotion no longer overwrites `eval_iter_$K.json`.

- [ ] **Step 3: run_checkpoint → origin + masterbot powered eval.** Update `run_checkpoint.ps1` to run `run_eval.py --anchors origin masterbot --pools general` at a higher round count (e.g. `RL_PoL_origin`/`RL_PoL_masterbot` temporarily bumped to rounds 192 = 384 games) for the periodic powered read; keep the B8 val-acc forgetting guard. Drop the steam (2016-binary cross-path) call.

- [ ] **Step 4: Verify both scripts parse.**

Run: `pwsh -NoProfile -Command "$null = [System.Management.Automation.Language.Parser]::ParseFile('c:/libraries/PrismataAI/eval/promote_candidate.ps1',[ref]$null,[ref]$null); $null = [System.Management.Automation.Language.Parser]::ParseFile('c:/libraries/PrismataAI/eval/run_checkpoint.ps1',[ref]$null,[ref]$null); Write-Host PARSE-OK"`
Expected: `PARSE-OK`

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/promote_candidate.ps1 eval/run_checkpoint.ps1 && git commit -m "eval(rl): promote-unless-collapse + origin/masterbot checkpoint (v4); drop narrow clobber"
```

---

## Phase 3 — Documentation

### Task 14: Rewrite the living docs to v4

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/rl_campaign.md`, `eval/rl_runbook.md`, `eval/README.md`, `eval/campaign_log.md`

- [ ] **Step 1: `rl_campaign.md`** — rewrite §1 (frozen tuple) to v4 (one general block, EpsilonLate 0.05, EpsilonIG 0, NoIG interior, W=2, anchors origin+masterbot, abort 0.35, promote-unless-collapse). Move the IG-specific reasoning (EpsilonIG, forced-Hotel, tau-probe, IG watch-stats, A2) into a new appendix **"IG axis — worked example (regime v3, archived)"**. Update §3 to the collapse/abort policy (no REJECT/REVIEW verdict). State the systems-milestone framing (spec §1) at the top.

- [ ] **Step 2: `rl_runbook.md`** — rewrite the stage table: stage 1 one block; drop stage 6 tactical; stage 7 = origin+masterbot, abort-on-collapse; preflight now N checks incl. a6/three-way/exe-sha/M2; the two-phase run (fixed-generator smoke → promoting loop).

- [ ] **Step 3: `README.md`** — replace the regime-v2/v3 anchor table and the REJECT/REVIEW verdict section with the v4 anchors (origin + masterbot, same-path absolute) and the collapse signal; note steam (2016 cross-path binary) is retired in favour of the same-path AB `MasterBot_SWF`.

- [ ] **Step 4: `campaign_log.md`** — append a dated decision row: "2026-06-14 — REFRAME to proof-of-life (tuple v4): drop IG-measurement (EpsilonIG/forced-Hotel), NoIG interior, MasterBot_SWF same-path AB anchor, promote-unless-collapse, two-phase run. IG over-click logged as fixed-by-action-space-widening (audit C1)." Add the F-SKEW-1-retracted note to the limitations register.

- [ ] **Step 5: Verify no stale v3 tuple remains in the living docs.**

Run: `cd c:/libraries/PrismataAI && grep -rn "EpsilonIG.*0.25\|forced-Hotel\|REJECT/REVIEW\|regime v3" eval/rl_campaign.md eval/rl_runbook.md eval/README.md | grep -vi "archived\|worked example\|appendix" | head`
Expected: no live (non-appendix) references to the v3 tuple/verdict. Fix any that print.

- [ ] **Step 6: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/rl_campaign.md eval/rl_runbook.md eval/README.md eval/campaign_log.md && git commit -m "docs(rl): rewrite living docs to v4 proof-of-life regime; IG axis archived as worked example"
```

---

## Self-review notes (coverage vs spec)

- Spec §3 two-phase run → Tasks 9 (Phase 0 smoke) + 13 (Phase 1 wiring). §4 tuple → Task 5. §5 candidate config (NoIG interior, knobs, one block) → Tasks 1, 3. §6 MasterBot_SWF + anchors → Tasks 2, 4, 7. §7 gate changes → Tasks 6, 7, 8. §8 pre-launch must-dos → Tasks 10, 11, 12. §9 success/abort + calibration → Tasks 7 (collapse), 9 (calibration). §10 policy-head → out of scope (documented in spec). §11 docs → Task 14. §12 verification items → resolved in the recon preamble (all config-only). §13 disposition / §14 risks → reflected in task choices.
- Phase-0 smoke (Task 9) is reachable after Tasks 1-8 (all config + Python/PowerShell edits, no engine rebuild) — the earliest possible end-to-end run, per the planning constraint.
- No placeholders: every config edit has exact JSON + a verify command; every Python change has the function body + a pytest; every script change has a parse/dry-run check.
