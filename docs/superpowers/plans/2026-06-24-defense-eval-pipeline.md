# Defense-Eval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline harness that grades our functional defense heuristic (and the current C++ heuristic) against how elite humans defend, across ~25k defense positions, emitting tuner-ready statistics.

**Architecture:** A small CommonJS toolset under `eval/defense/`. We extract two states per defense turn from elite replays (begin-of-defense = AI input; committed pre-swoosh = human truth) via the existing faithful JS engine, run a JS port of the C++ one-prime block-assignment search with a pluggable per-unit value function (a current-C++ replica AND our functional model), and compare the picks with a regret-centred metric stack. A one-time validation gate proves the JS sim reproduces the real C++ engine.

**Tech Stack:** Node.js (CommonJS, matching the repo); the repo's faithful JS engine (`js_engine/Analyzer.js`, `replay_exporter.js`); tests via the built-in `node:test` runner; the functional value model in `docs/scratch/gen_our_numbers_v2.js`.

## Global Constraints

- **Module system: CommonJS** (`require`/`module.exports`), matching `gen_our_numbers_v2.js` and the rest of the repo. No ESM.
- **Tests: built-in `node:test` + `node:assert`** (Node ≥18). Run a test file with `node --test <file>`; run all with `node --test eval/defense/`.
- **The defense mechanic is ONE-PRIME** (spec §2): chumps are full-killed (take ≥ their HP); exactly one prime takes partial (non-lethal) damage and survives; all other available units take 0 damage and survive untouched. The sim, the State-B reader, and every test must honor this.
- **The objective** (spec §4.1): minimize `Σ over ALL available units [ V(unit@HP_before) − V(unit@HP_after) ]`; untouched units contribute 0. Lineup-awareness lives entirely in the per-unit loss; the search structure is identical for both value modes.
- **Two value modes:** `"cpp"` = faithful `DamageLoss_WillCost` replica **including its bugs** (so the validation gate matches the engine bit-for-bit); `"ours"` = the functional model with the bugs fixed (current/max HP, not startingHealth).
- **Iso, not instId:** all matching/grouping is by isomorphism class (spec §4.5 fields), never instId.
- **Card library (live):** `c:/libraries/PrismataAI-dave-master/bin/asset/config/cardLibrary.jso` (keyed by INTERNAL name; `UIName` is display). Internal↔UI examples: Husk=House, Wall=Wall, Energy Matrix=Golem, Xaetron=Xaetron, Infusion Grid=Hotel, Bombarder=Bombarder, Steelsplitter=Treant.
- **All paths are absolute or repo-relative from `c:/libraries/PrismataAI/`.**
- **Reference spec:** `docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md`. Read it before starting; this plan implements it.

---

## File Structure

| Path | Responsibility |
|---|---|
| `docs/scratch/gen_our_numbers_v2.js` | MODIFY — make its value logic `require`-able; apply the §4.4 fixes. Still runs standalone. |
| `eval/defense/value_model.js` | (no new file — we require the refactored `gen_our_numbers_v2.js`) |
| `eval/defense/defense_value.js` | NEW — `unitView`, `V`, `body`, `loss(unit,damage,mode)`, `isIsomorphic`, `isoKey`. The per-unit value/loss layer. |
| `eval/defense/defense_sim.js` | NEW — `solveDefense(board, incoming, mode, eps)`: the one-prime min-loss search. |
| `eval/replay_to_request.js` | MODIFY — add `--defense-only` predicate (State-A emitter). |
| `eval/defense/state_b_capture.js` | NEW — `captureCommittedDefenses(replay)`: the undo-robust committed-defense reader. |
| `eval/defense/metrics.js` | NEW — `computeMetrics`, `aggregate`: regret, exact-match-iso, prime-match, tie-break-skew, per-unit divergence. |
| `eval/defense/compare.js` | NEW — CLI harness: pair State A/B per position → sim (both modes) → metrics → JSONL records. |
| `eval/defense/report.js` | NEW — `renderReport(aggregates)`: the markdown aggregate report. |
| `eval/defense/validate_gate.js` | NEW — CLI: cpp-replica sim vs `query_move` on 100 games; report mismatches. |
| `eval/defense/*.test.js` | NEW — `node:test` files alongside each module. |

---

### Task 1: Make the functional value model require-able

Refactor `docs/scratch/gen_our_numbers_v2.js` so its value logic can be imported with **no behavior change** and no side effects on require. Today the file builds the table and writes `our_numbers_v2.md` at module load; we guard that behind `require.main === module` and export the core functions.

**Files:**
- Modify: `docs/scratch/gen_our_numbers_v2.js`
- Test: `eval/defense/value_model.test.js`

**Interfaces:**
- Produces (module.exports): `ours(c, stateOverride?)`, `parseCost(s)`, `costWill(s)`, `attackOf(s)`, `geom(n)`, `geomPerp(period)`, `lib`, and `CONSTANTS` = `{BV, ATK, R, RES, THREAT, OPT_SELFSAC_ATK, OPT_SELFSAC_TOKEN, CHILL_COEFF, UNDEF_PER_HP, FRAGILE_PEN}`.
  - `ours(c, stateOverride?)` returns `{v, block, atk, type, flags, rule}` (unchanged shape). `stateOverride` is optional and ignored in this task (added in Task 3).

- [ ] **Step 1: Write the failing test**

Create `eval/defense/value_model.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const vm = require('../../docs/scratch/gen_our_numbers_v2.js');

test('exports the core value API', () => {
  for (const fn of ['ours', 'parseCost', 'costWill', 'attackOf', 'geom', 'geomPerp']) {
    assert.equal(typeof vm[fn], 'function', `missing export: ${fn}`);
  }
  assert.equal(typeof vm.lib, 'object');
  assert.equal(vm.CONSTANTS.BV, 2.2);
});

test('regression: known table values are unchanged', () => {
  const round = x => Math.round(x * 100) / 100;
  // Wall (internal "Wall"): pure block 3HP -> 6.6
  assert.equal(round(vm.ours(vm.lib['Wall']).v), 6.6);
  // Energy Matrix (internal "Golem"): 5HP non-fragile -> 11
  assert.equal(round(vm.ours(vm.lib['Golem']).v), 11);
  // Husk (internal "House"): 1HP -> 2.2
  assert.equal(round(vm.ours(vm.lib['House']).v), 2.2);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test eval/defense/value_model.test.js`
Expected: FAIL — `vm.ours` is undefined (the script does not export yet) or the require triggers a file write / throws.

- [ ] **Step 3: Refactor the script to export + guard side effects**

In `docs/scratch/gen_our_numbers_v2.js`:
1. Find the line `const lib = JSON.parse(fs.readFileSync(LIB, 'utf8'));` — keep it.
2. Locate the `// ---- build ----` comment (the section that builds `inscope`/`deferred`, sorts, builds the `md` string, and calls `fs.writeFileSync(OUT, md)` + the final `console.log`). Wrap that entire build-and-write block in a guard so it only runs when the file is executed directly:
```js
if (require.main === module) {
  // ---- build ----
  ...all the existing build + writeFileSync + console.log code, unchanged...
}
```
3. At the very end of the file (after the guard), add the exports:
```js
module.exports = {
  ours, parseCost, costWill, attackOf, geom, geomPerp, lib,
  CONSTANTS: { BV, ATK, R, RES, THREAT, OPT_SELFSAC_ATK, OPT_SELFSAC_TOKEN, CHILL_COEFF, UNDEF_PER_HP, FRAGILE_PEN },
};
```
Do not change any value logic. (`OPT_SELFSAC_ATK`, `OPT_SELFSAC_TOKEN`, `CHILL_COEFF`, `UNDEF_PER_HP`, `FRAGILE_PEN` already exist as `const`s near the top.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test eval/defense/value_model.test.js`
Expected: PASS (both tests).

- [ ] **Step 5: Verify the standalone path still works**

Run: `node docs/scratch/gen_our_numbers_v2.js`
Expected: prints `wrote .../our_numbers_v2.md: 54 in-scope, 0 deferred` (unchanged behavior).

- [ ] **Step 6: Commit**

```bash
git add docs/scratch/gen_our_numbers_v2.js eval/defense/value_model.test.js
git commit -m "refactor(value-model): make gen_our_numbers_v2 require-able (no behavior change)"
```

---

### Task 2: Apply the §4.4 value-fn fixes

Three agreed corrections to the value model (spec §4.4), each with a test pinning the new behavior.

**Files:**
- Modify: `docs/scratch/gen_our_numbers_v2.js`
- Modify: `eval/defense/value_model.test.js` (add fix tests; update any regression value the fixes change)

**Interfaces:**
- Produces: a `DOOMED_NUDGE = 0.1` constant added to `CONSTANTS`. `ours()` value output changes for: Infusion Grid (opt 0.5→0.1), Photonic Fibroid / Nitrocybe / Protoplasm (attack-selfsac opt 1.0→0.2), and doomed `lifespan ≥ 2` units (small nudge).

- [ ] **Step 1: Write the failing tests**

Append to `eval/defense/value_model.test.js`:
```js
test('§4.4 fix: Infusion Grid optionality is a 0.1 tie-break', () => {
  // Infusion Grid internal = "Hotel": self-sac convert -> body 8.8 dominates, opt 0.1
  const v = vm.ours(vm.lib['Hotel']).v;
  assert.ok(Math.abs(v - 8.9) < 0.01, `IG expected ~8.9, got ${v}`);
});

test('§4.4 fix: attack-selfsac opt shrinks (Photonic Fibroid)', () => {
  // Photonic Fibroid: 2HP, begin-selfsac 2A -> max(4.4, 4.0) + 0.2 = 4.6
  const v = vm.ours(vm.lib['Photonic Fibroid']).v;
  assert.ok(Math.abs(v - 4.6) < 0.01, `Photonic expected ~4.6, got ${v}`);
});

test('§4.4 fix: doomed nudge puts a fresh Doomed Wall just below ch0-Bombarder', () => {
  // Doomed Wall is a doomed pure-block (lifespan ~3); ch0-Bombarder = body 8.8.
  const dw = vm.ours(vm.lib['Doomed Wall']).v;
  const bomb0 = vm.ours(vm.lib['Bombarder'], { charge: 0 }).v; // stateOverride added in Task 3; here charge 0 == body 8.8
  assert.ok(dw < bomb0, `Doomed Wall (${dw}) must be < ch0-Bombarder (${bomb0})`);
  assert.ok(dw > 8.0, `Doomed Wall (${dw}) should still be near body, not heavily discounted`);
});
```
Note: the third test uses `{ charge: 0 }` which `ours` ignores until Task 3 — at this point `ours(lib['Bombarder'])` returns the FULL-charge value (19.3), so `dw < 19.3` still holds; the test stays valid. (It tightens in Task 3.)

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `node --test eval/defense/value_model.test.js`
Expected: the IG and Photonic tests FAIL (current values 9.3 and 5.4); the doomed test passes trivially.

- [ ] **Step 3: Apply the fixes in gen_our_numbers_v2.js**

1. **Constants:** add near the other constants: `const DOOMED_NUDGE = 0.1; // small per-step doomed keep-value haircut`. Change `OPT_SELFSAC_ATK` from `1.0` to `0.2`, and `OPT_SELFSAC_TOKEN` from `0.5` to `0.1`. Add `DOOMED_NUDGE` to the `module.exports.CONSTANTS` object.
2. **Doomed nudge** in `ours()`: find where a doomed unit's value is finalized. The block-floor `body` is computed near the top of `ours`. After `body` is computed and before it is used, insert the nudge for non-terminal doomed units:
```js
// doomed keep-value nudge: lifespan==1 stays 0 (handled elsewhere); lifespan>=2 gets a small haircut
const _maxLife = c.lifespan;          // nominal/max lifespan from the card
const _remLife = c.lifespan;          // current == nominal in table mode (Task 3 overrides)
if (_maxLife !== undefined && _remLife >= 2) {
  body -= DOOMED_NUDGE * (1 + _maxLife - _remLife);
}
```
   (Place it where `body` is a mutable `let`; if `body` is `const`, change it to `let`.)
3. **IG relabel:** in the self-sac branch, where the token-burst rule is labeled `"burst"`, rename it to `"convert"` in the `type`/`rule` string (cosmetic, keeps the model's language honest).

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test eval/defense/value_model.test.js`
Expected: PASS. (If the Task-1 regression test for any unit now differs, that unit was affected by a fix — update its expected value and note why in the test comment. Wall/Energy Matrix/Husk are not doomed/self-sac, so they are unchanged.)

- [ ] **Step 5: Regenerate the table and eyeball**

Run: `node docs/scratch/gen_our_numbers_v2.js`
Expected: writes the md; Infusion Grid ≈ 8.9, Photonic ≈ 4.6, Doomed Wall dips just below ch0-Bombarder, others ~unchanged.

- [ ] **Step 6: Commit**

```bash
git add docs/scratch/gen_our_numbers_v2.js docs/scratch/our_numbers_v2.md eval/defense/value_model.test.js
git commit -m "feat(value-model): apply §4.4 fixes (doomed nudge 0.1, IG opt 0.1, attack-selfsac opt 0.2)"
```

---

### Task 3: `defense_value.js` — `unitView`, `body`, `V` (HP-parameterized, current state)

Build the layer that values a unit at its CURRENT game-state HP/charge/lifespan (not the card's nominal state). Extend `ours()` to accept a `stateOverride`.

**Files:**
- Create: `eval/defense/defense_value.js`
- Modify: `docs/scratch/gen_our_numbers_v2.js` (teach `ours` the `stateOverride`)
- Test: `eval/defense/defense_value.test.js`

**Interfaces:**
- Consumes: `value_model.ours(c, stateOverride)`, `value_model.lib`, `value_model.CONSTANTS`.
- Produces:
  - `unitView(stateUnit)` → `{ internal, ui, owner, hp, charge, life, fragile, heal, max, ct }` where `ct` is the card-type def; `internal` is the library key resolved from the game-state unit's `cardName`/`cardType`/`name`.
  - `body(view)` → number (effective-soak-HP·BV with the doomed nudge + fragile/undef haircuts).
  - `V(view)` → number (full functional value at current state = `ours(cardView).v`).
  - exported as `module.exports = { unitView, body, V, ... }` (loss/iso added in later tasks).

- [ ] **Step 1: Teach `ours` the stateOverride (in gen_our_numbers_v2.js)**

Change `function ours(c, chargeOverride) {` to `function ours(c, stateOverride) {` and, at the very top of the body, normalize:
```js
const _ov = (typeof stateOverride === 'number') ? { charge: stateOverride } : (stateOverride || {});
const _hp   = _ov.hp   !== undefined ? _ov.hp   : c.toughness;
const _chg  = _ov.charge!== undefined ? _ov.charge: c.charge;
const _rem  = _ov.life !== undefined ? _ov.life : c.lifespan;
```
Then replace internal uses for the picker:
- body HP: use `_hp` instead of `c.toughness` in the `soakHP`/`body` computation.
- charge: use `_chg` where `c.charge`/`chargeOverride` was used.
- doomed nudge (Task 2): set `_remLife = _rem` and keep `_maxLife = c.lifespan`.
Keep the `(typeof stateOverride === 'number')` shim so any existing `ours(c, 2)` charge-override callers still work.

- [ ] **Step 2: Write the failing test**

Create `eval/defense/defense_value.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const dv = require('./defense_value');
const near = (a, b, eps = 0.02) => Math.abs(a - b) < eps;

function mk(name, over = {}) { // build a minimal game-state unit
  return Object.assign({ cardName: name, owner: 0, health: undefined, charge: undefined, lifespan: undefined }, over);
}

test('unitView resolves internal name + current state', () => {
  const v = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(v.internal, 'Wall');
  assert.equal(v.hp, 3);
  assert.equal(v.fragile, false);
});

test('body uses CURRENT hp and heal-aware effective soak', () => {
  // Xaetron: heal 4, max 12, fragile. At HP 8: effective soak min(8+4,12)=12 -> 12*2.2 - 0.1 fragile = 26.3
  const x8 = dv.body(dv.unitView(mk('Xaetron', { health: 8 })));
  assert.ok(near(x8, 26.3), `Xaetron@8 body expected ~26.3, got ${x8}`);
  // At HP 5: min(5+4,12)=9 -> 9*2.2 - 0.1 = 19.7
  const x5 = dv.body(dv.unitView(mk('Xaetron', { health: 5 })));
  assert.ok(near(x5, 19.7), `Xaetron@5 body expected ~19.7, got ${x5}`);
});

test('V(Energy Matrix@5) == 11', () => {
  const em = dv.V(dv.unitView(mk('Golem', { health: 5 })));
  assert.ok(near(em, 11), `EM expected 11, got ${em}`);
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test eval/defense/defense_value.test.js`
Expected: FAIL — `./defense_value` does not exist.

- [ ] **Step 4: Implement `defense_value.js` (unitView/body/V)**

```js
'use strict';
const vm = require('../../docs/scratch/gen_our_numbers_v2.js');
const { ours, lib, CONSTANTS } = vm;
const { BV, UNDEF_PER_HP, FRAGILE_PEN } = CONSTANTS;
const DOOMED_NUDGE = CONSTANTS.DOOMED_NUDGE !== undefined ? CONSTANTS.DOOMED_NUDGE : 0.1;

// Resolve a game-state unit (table[] entry) to its card-library key + current state.
function resolveInternal(stateUnit) {
  const nm = stateUnit.cardName || stateUnit.cardType || stateUnit.name;
  if (lib[nm]) return nm;                       // already an internal key
  // else search by UIName
  for (const k of Object.keys(lib)) if ((lib[k].UIName || k) === nm) return k;
  return null;
}

function unitView(stateUnit) {
  const internal = resolveInternal(stateUnit);
  const ct = internal ? lib[internal] : null;
  return {
    internal, ui: ct ? (ct.UIName || internal) : (stateUnit.cardName),
    owner: stateUnit.owner,
    instId: stateUnit.instId,
    hp: stateUnit.health !== undefined ? stateUnit.health : (ct ? ct.toughness : 0),
    charge: stateUnit.charge,
    life: stateUnit.lifespan,
    fragile: !!(ct && ct.fragile),
    heal: ct ? (ct.HPGained || 0) : 0,
    max: ct ? (ct.HPMax !== undefined ? ct.HPMax : ct.toughness) : 0,
    ct,
  };
}

// Full functional value at current state (ours mode), via the value model with overrides.
function V(view) {
  if (!view.ct) return 0;
  return ours(view.ct, { hp: view.hp, charge: view.charge, life: view.life }).v;
}

// Block floor only (effective-soak HP * BV, doomed nudge, fragile/undef haircuts) — exposed for tests/diagnostics.
function body(view) {
  if (!view.ct) return 0;
  const r = ours(view.ct, { hp: view.hp, charge: view.charge, life: view.life });
  return r.block;   // ours() returns block/atk split; block carries the heal-aware floor + nudge + haircuts
}

module.exports = { unitView, V, body, resolveInternal };
```
Note: `ours()` already splits value into `{block, atk}` where `block` = the heal-aware floor with the doomed nudge and fragile/undef haircuts applied, and `block + atk = v`. So `body(view)` = `r.block` and `V(view)` = `r.v`. (Verified against the table: Energy Matrix block 11, atk 0; Xaetron@8 block 26.3.)

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 6: Tighten the Task-2 doomed test now that overrides work**

In `eval/defense/value_model.test.js`, the Doomed-Wall test's `ours(vm.lib['Bombarder'], { charge: 0 })` now returns the ch0 body (8.8). Update the assertion to `assert.ok(dw < 8.8 && dw > 8.0, ...)`. Run `node --test eval/defense/value_model.test.js` → PASS.

- [ ] **Step 7: Commit**

```bash
git add eval/defense/defense_value.js eval/defense/defense_value.test.js docs/scratch/gen_our_numbers_v2.js eval/defense/value_model.test.js
git commit -m "feat(defense-value): HP-parameterized unitView/body/V via ours() stateOverride"
```

---

### Task 4: `defense_value.js` — `loss(view, damage, 'ours')`

The per-unit functional loss (spec §4.3, ours mode): chump → full V; non-fragile survivor → 0; fragile survivor → `body(before) − body(after)`.

**Files:**
- Modify: `eval/defense/defense_value.js`
- Modify: `eval/defense/defense_value.test.js`

**Interfaces:**
- Produces: `loss(view, damage, mode)` (this task implements `mode === 'ours'`). `damage` = the damage applied to this unit. Survive iff `damage < view.hp`.

- [ ] **Step 1: Write the failing tests (the spec's worked examples)**

Append to `eval/defense/defense_value.test.js`:
```js
test('loss ours: chump = full V', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.ok(near(dv.loss(wall, 3, 'ours'), 6.6)); // damage>=hp -> dies -> full value
});

test('loss ours: non-fragile survivor = 0', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.loss(wall, 2, 'ours'), 0);     // survives (2<3), non-fragile -> 0
});

test('loss ours: fragile healer survivor = body delta (Xaetron@3 absorbs 2)', () => {
  const x = dv.unitView(mk('Xaetron', { health: 3 }));
  // body(@3)=min(3+4,12)*2.2-0.1=15.3 ; body(@1)=min(1+4,12)*2.2-0.1=10.9 ; delta=4.4
  assert.ok(near(dv.loss(x, 2, 'ours'), 4.4), `got ${dv.loss(x, 2, 'ours')}`);
});

test('loss ours: heal headroom makes absorption free (Xaetron@10 absorbs 2)', () => {
  const x = dv.unitView(mk('Xaetron', { health: 10 }));
  // body(@10)=min(14,12)=12 ; body(@8)=min(12,12)=12 ; delta 0
  assert.ok(near(dv.loss(x, 2, 'ours'), 0), `got ${dv.loss(x, 2, 'ours')}`);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test eval/defense/defense_value.test.js`
Expected: FAIL — `dv.loss` is not a function.

- [ ] **Step 3: Implement `loss` (ours branch)**

Add to `defense_value.js` (and export it):
```js
function loss(view, damage, mode) {
  if (mode === 'ours') return lossOurs(view, damage);
  if (mode === 'cpp')  return lossCpp(view, damage);   // implemented in Task 5
  throw new Error('unknown mode: ' + mode);
}

function lossOurs(view, damage) {
  if (!view.ct) return 0;
  const dies = damage >= view.hp;
  if (dies) return V(view);                       // chump: full value lost
  if (!view.fragile) return 0;                    // non-fragile survivor: repairs, free
  // fragile survivor: body(before) - body(after); body() already projects one heal
  const after = Object.assign({}, view, { hp: view.hp - damage });
  return body(view) - body(after);
}
```
Update `module.exports` to include `loss`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/defense_value.js eval/defense/defense_value.test.js
git commit -m "feat(defense-value): loss() ours-mode survivor-delta"
```

---

### Task 5: `defense_value.js` — `loss(view, damage, 'cpp')` (DamageLoss_WillCost replica)

A faithful JS port of `Heuristics::DamageLoss_WillCost` (`PrismataAI-dave-master/source/ai/Heuristics.cpp:158-242`), **bugs included**, so the validation gate (Task 12) matches the real engine. Read that C++ function before implementing.

**Files:**
- Modify: `eval/defense/defense_value.js`
- Modify: `eval/defense/defense_value.test.js`

**Interfaces:**
- Produces: `lossCpp(view, damage)` used by `loss(view, damage, 'cpp')`.

WillScore weights (Heuristics.cpp:7-14, `CalculateBuyManaCost`): gold 1.00, blue 1.50, green 1.20, red 0.90, energy 0.50, attack 2.25. Construction-time inflation `WILL_VALUE_CONSTR = 1.28^buildtime` (bt 0 → 1/1.13). These already exist in `gen_our_numbers_v2.js` as `willScoreCpp()`, `inflCpp()`, `resolveBT()`, `buySac()`, `cpp()` — **export and reuse them** rather than re-deriving.

- [ ] **Step 1: Export the existing cpp helpers from the value model**

In `gen_our_numbers_v2.js` `module.exports`, add `willScoreCpp, inflCpp, resolveBT, buySac`. (They are already defined in the file for the reference column.)

- [ ] **Step 2: Write the failing tests**

Append to `eval/defense/defense_value.test.js`:
```js
test('loss cpp: non-fragile survivor = 0 (Wall absorbs 2)', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.loss(wall, 2, 'cpp'), 0);
});

test('loss cpp: 1HP block-only special-case = 1.875', () => {
  const husk = dv.unitView(mk('House', { health: 1 }));
  assert.ok(near(dv.loss(husk, 1, 'cpp'), 1.875), `got ${dv.loss(husk, 1, 'cpp')}`);
});

test('loss cpp: lifespan==1 -> 0', () => {
  // Barrier internal "Sound Barrier": lifespan 1
  const b = dv.unitView(mk('Sound Barrier', { health: 1, lifespan: 1 }));
  assert.equal(dv.loss(b, 1, 'cpp'), 0);
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `node --test eval/defense/defense_value.test.js`
Expected: FAIL — `lossCpp` returns undefined / throws.

- [ ] **Step 4: Implement `lossCpp` (faithful, bugs included)**

Port Heuristics.cpp:158-242 exactly. Add to `defense_value.js`:
```js
const { willScoreCpp, inflCpp, resolveBT } = vm;
// Inflated mana/total cost values (Heuristics.cpp uses precomputed tables; replicate inline).
function inflatedManaValue(ct)  { return willScoreCpp(ct.buyCost) * inflCpp(resolveBT(ct)); }
function inflatedTotalValue(ct) { // mana + buySac cost, inflated (Heuristics.cpp GetInflatedTotalCostValue)
  return (willScoreCpp(ct.buyCost) + (vm.buySac ? vm.buySac(ct) : 0)) * inflCpp(resolveBT(ct));
}
function canBlockOnly(ct) { return !ct.abilityScript && !ct.targetAction; }
function isFragileCpp(ct) { return !!ct.fragile; } // CardType.cpp isFragile = canBlock(false) && constructionTime==0; live units in defense are built, so == ct.fragile

function lossCpp(view, damage) {
  const ct = view.ct; if (!ct) return 0;
  const remLife = view.life !== undefined ? view.life : ct.lifespan;
  if (remLife === 1 || damage === 0) return 0;                        // Heuristics.cpp:161
  const eps = 0.001;
  const usesCharges = !!ct.charge;
  const curCharge = view.charge !== undefined ? view.charge : (ct.charge || 0);
  const chargeLoss = usesCharges ? (1 / (1 + curCharge)) * eps : 0;
  const lifespanLoss = (remLife > 0) ? (1 / remLife) * eps : 0;       // remLife undefined -> 0 contribution
  const exhaustLoss = 0;                                              // delay==0 for ready blockers
  const tieBreakLoss = chargeLoss + (remLife > 0 ? lifespanLoss : 0) + exhaustLoss;
  const linearHealthValue = canBlockOnly(ct) || !!ct.isAbilityHealthUserOnly; // approximation; see note
  const resonate = 0;                                                // resonators ignored for v1 (rare in defense)
  if (canBlockOnly(ct) && view.hp === 1) return 1.875 + resonate;    // Heuristics.cpp:181
  const manaVal = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedManaValue(ct);
  const totalVal = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedTotalValue(ct);
  if ((view.ui || '') === 'Forcefield') { /* Heuristics.cpp:102 pin */ }
  if (isFragileCpp(ct)) {                                             // Heuristics.cpp:191
    const damageTaken = Math.min(damage, view.hp);
    const startHP = ct.toughness;                                    // BUG replicated: startingHealth, not current/max
    const ratio = damageTaken / startHP;
    if (linearHealthValue) {
      let cardValue = manaVal - tieBreakLoss;
      let dmgValue = ratio * cardValue;
      if (damageTaken < view.hp) dmgValue -= eps;                    // survives -> favor alive
      if (view.hp === 1) dmgValue += 2 * eps;
      return damageTaken >= view.hp ? (dmgValue + resonate) : dmgValue;
    } else {
      let cardValue = totalVal - tieBreakLoss - tieBreakLoss;        // BUG replicated: double subtract (:219/:221)
      const dmgValue = ratio * cardValue;
      return damageTaken >= view.hp ? (cardValue + resonate) : (dmgValue * eps);
    }
  } else {                                                           // non-fragile (Heuristics.cpp:229)
    if (damage >= view.hp) return (linearHealthValue ? manaVal : totalVal) - tieBreakLoss + resonate;
    return 0;
  }
}
```
Note on `isAbilityHealthUserOnly`: the C++ flag is not in `cardLibrary.jso`; approximate as `false` unless a unit defines `HPUsed` (`linearHealthValue = canBlockOnly(ct) || ct.HPUsed !== undefined`). The validation gate (Task 12) will reveal any unit where this approximation diverges from the engine; fix those by name then. If the Forcefield 3.75 pin is needed, add `if (view.ui === 'Forcefield') return forcefieldLoss(...)` once the gate flags it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add eval/defense/defense_value.js eval/defense/defense_value.test.js docs/scratch/gen_our_numbers_v2.js
git commit -m "feat(defense-value): loss() cpp-mode DamageLoss_WillCost replica (bugs intact)"
```

---

### Task 6: `defense_value.js` — `isIsomorphic` + `isoKey`

Group blockers into isomorphism classes (spec §4.5), mirroring `Card::isIsomorphic` (`PrismataAI-dave-master/source/engine/Card.cpp:862-874`).

**Files:**
- Modify: `eval/defense/defense_value.js`
- Modify: `eval/defense/defense_value.test.js`

**Interfaces:**
- Produces: `isIsomorphic(a, b)` (a,b are `unitView`s) → bool; `isoKey(view)` → stable string. Fields: internal type, owner, current HP, current chill, charges, delay, constructionTime, lifespan, dead, status.

- [ ] **Step 1: Write the failing test**

Append to `eval/defense/defense_value.test.js`:
```js
test('isIsomorphic: two same-HP Husks match; different HP do not', () => {
  const a = dv.unitView(mk('House', { health: 1 }));
  const b = dv.unitView(mk('House', { health: 1 }));
  const c = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.isIsomorphic(a, b), true);
  assert.equal(dv.isIsomorphic(a, c), false);
  assert.equal(dv.isoKey(a), dv.isoKey(b));
  assert.notEqual(dv.isoKey(a), dv.isoKey(c));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test eval/defense/defense_value.test.js`
Expected: FAIL — `isIsomorphic` undefined.

- [ ] **Step 3: Implement isoKey/isIsomorphic**

Add to `defense_value.js` (and export). The game-state `table[]` entry carries `cardName, owner, health, charge, lifespan, constructionTime, delay, disruptDamage (chill), deadness, role/status, blocking`:
```js
function isoKey(view, raw) {
  // raw = the original stateUnit for fields not on the view (chill/delay/construction/status)
  const r = raw || {};
  return [
    view.internal, view.owner, view.hp,
    r.disruptDamage | 0,          // current chill
    view.charge | 0,
    r.delay | 0,
    r.constructionTime | 0,
    view.life === undefined ? -1 : view.life,
    r.deadness && r.deadness !== 'alive' ? 1 : 0,
    r.role || r.status || 'default',
  ].join('|');
}
function isIsomorphic(a, b, ra, rb) { return isoKey(a, ra) === isoKey(b, rb); }
```
Carry the `raw` stateUnit alongside the view where iso-grouping happens (the sim and the State-B reader keep both). Update `unitView` to stash `view.raw = stateUnit;` so callers can pass `view.raw`:
```js
// in unitView, before return: add `raw: stateUnit` to the returned object, and make isoKey default raw to view.raw
function isoKey(view) { const r = view.raw || {}; /* ...same body using r... */ }
function isIsomorphic(a, b) { return isoKey(a) === isoKey(b); }
```
Use the second form (raw stashed on the view) for simplicity. Export `isoKey, isIsomorphic`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/defense_value.js eval/defense/defense_value.test.js
git commit -m "feat(defense-value): isIsomorphic + isoKey (iso-class grouping)"
```

---

### Task 7: `defense_sim.js` — the one-prime min-loss search

Port the C++ `BlockIterator` (`BlockIterator.cpp:50-118`): chump full-HP units; one "last blocker" (prime) absorbs the remainder and survives. Minimize `Σ loss(unit, damage, mode)`. Same structure for both modes. Return the chosen assignment + near-tied alternatives.

**Files:**
- Create: `eval/defense/defense_sim.js`
- Test: `eval/defense/defense_sim.test.js`

**Interfaces:**
- Consumes: `defense_value.{unitView, loss, isoKey}`.
- Produces: `solveDefense(stateUnits, incoming, mode, eps=0.001)` → `{ assignment, loss, tiedAlts }`.
  - `stateUnits` = array of available blocker `table[]` entries (already filtered to the active player's blockable units).
  - `assignment` = `{ chumps: [{isoKey, count}], prime: isoKey|null, untouched: [{isoKey, count}], perUnit: {instId: damage} }`.
  - `tiedAlts` = array of `{assignment, loss}` for assignments within `eps` of the min (for the tie-break diagnostic).

- [ ] **Step 1: Write the failing tests (the spec's worked examples)**

Create `eval/defense/defense_sim.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const sim = require('./defense_sim');
function mk(name, over = {}) { return Object.assign({ cardName: name, owner: 0 }, over); }

test('Wall vs Xaetron@3, 2 dmg -> keep Wall as prime, Xaetron untouched', () => {
  const board = [mk('Wall', { health: 3, instId: 1 }), mk('Xaetron', { health: 3, instId: 2 })];
  const r = sim.solveDefense(board, 2, 'ours');
  // Wall (non-fragile) absorbs 2 free; Xaetron untouched heals. Wall is the prime.
  assert.equal(r.perUnit[2] || 0, 0, 'Xaetron must be untouched');
  assert.ok((r.perUnit[1] || 0) > 0, 'Wall must absorb');
  assert.ok(r.loss < 0.01, `loss expected ~0, got ${r.loss}`);
});

test('5 Husk + Wall + Xaetron@8, 7 dmg -> chump husks, keep Xaetron (loss ~11)', () => {
  const board = [
    mk('Xaetron', { health: 8, instId: 1 }),
    mk('Wall', { health: 3, instId: 2 }),
    ...[3,4,5,6,7].map(i => mk('House', { health: 1, instId: i })),
  ];
  const r = sim.solveDefense(board, 7, 'ours');
  assert.equal(r.perUnit[1] || 0, 0, 'Xaetron stays untouched (heals to fortress)');
  assert.ok(near(r.loss, 11, 0.6), `expected ~11 (5 husks), got ${r.loss}`);
});
function near(a, b, e) { return Math.abs(a - b) < e; }

test('forced single feasible set is tagged via tiedAlts length 1', () => {
  const board = [mk('Wall', { health: 3, instId: 1 })];
  const r = sim.solveDefense(board, 2, 'ours'); // only one unit can be prime
  assert.equal(r.tiedAlts.length <= 1, true);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test eval/defense/defense_sim.test.js`
Expected: FAIL — `./defense_sim` does not exist.

- [ ] **Step 3: Implement the one-prime search**

```js
'use strict';
const dv = require('./defense_value');

// Enumerate one-prime block assignments and return the min-loss one + near-ties.
// Strategy mirrors BlockIterator: group by iso-class; for each class try {0..count} units as chumps;
// for the remainder choose a single prime from any class whose unit HP > remaining (survives).
function solveDefense(stateUnits, incoming, mode, eps = 0.001) {
  const views = stateUnits.map(u => dv.unitView(u));
  // group iso-classes
  const groups = [];
  const byKey = new Map();
  views.forEach(v => {
    const k = dv.isoKey(v);
    let g = byKey.get(k);
    if (!g) { g = { key: k, view: v, hp: v.hp, units: [] }; byKey.set(k, g); groups.push(g); }
    g.units.push(v);
  });

  const solutions = []; // {loss, chumpCounts: Map(key->n), primeKey, perUnit}
  // recursive: pick chump counts per group, then a prime for the remainder
  function recurse(gi, remaining, lossSoFar, chumpCounts) {
    // try to finish: any group with a spare unit whose hp > remaining can be the prime (survives)
    for (const g of groups) {
      const usedChumps = chumpCounts.get(g.key) || 0;
      if (usedChumps >= g.units.length) continue;     // no spare unit
      if (g.hp > remaining) {                          // can solo-absorb remainder and live
        const primeLoss = dv.loss(g.view, remaining, mode);
        solutions.push({ loss: lossSoFar + primeLoss, chumpCounts: new Map(chumpCounts), primeKey: g.key, primeDmg: remaining });
      }
    }
    if (gi >= groups.length) return;
    const g = groups[gi];
    const avail = g.units.length - (chumpCounts.get(g.key) || 0);
    // chump 0..avail of this class, each chump absorbs its full hp (dies)
    let added = 0;
    for (let n = 0; n <= avail; n++) {
      if (n > 0) {
        if (g.hp >= remaining) break;                  // chumping this would over-absorb; stop (n-1 was last useful)
        added += 1;
        chumpCounts.set(g.key, (chumpCounts.get(g.key) || 0) + 1);
        lossSoFar += dv.loss(g.view, g.hp, mode);       // dies -> full value
        remaining -= g.hp;
      }
      recurse(gi + 1, remaining, lossSoFar, chumpCounts);
    }
    // unwind this group's chumps
    chumpCounts.set(g.key, (chumpCounts.get(g.key) || 0) - added);
  }
  recurse(0, incoming, 0, new Map());

  if (!solutions.length) return { assignment: null, loss: Infinity, tiedAlts: [] }; // breach (skip upstream)
  solutions.sort((a, b) => a.loss - b.loss);
  const best = solutions[0];
  const tiedAlts = solutions.filter(s => s.loss <= best.loss + eps);

  const toAssignment = (s) => {
    const chumps = [], untouched = [], perUnit = {};
    for (const g of groups) {
      const nc = s.chumpCounts.get(g.key) || 0;
      const isPrime = (g.key === s.primeKey) ? 1 : 0;
      if (nc) chumps.push({ isoKey: g.key, count: nc });
      const untouchedN = g.units.length - nc - isPrime;
      if (untouchedN > 0) untouched.push({ isoKey: g.key, count: untouchedN });
      // assign damage to specific instIds: first nc units are chumps (full hp), then prime gets primeDmg
      g.units.forEach((u, i) => {
        if (i < nc) perUnit[u.instId] = g.hp;
        else if (isPrime && i === nc) perUnit[u.instId] = s.primeDmg;
        else perUnit[u.instId] = 0;
      });
    }
    return { chumps, prime: s.primeKey, untouched, perUnit };
  };

  return {
    assignment: toAssignment(best),
    loss: best.loss,
    tiedAlts: tiedAlts.map(s => ({ assignment: toAssignment(s), loss: s.loss })),
  };
}

module.exports = { solveDefense };
```
Note: this enumerates chump-count combinations and a single prime — the one-prime model. The recursion is bounded (few iso-classes, small counts) so it is fast. If a position has no feasible prime (incoming ≥ every unit's HP after all chumps), `solutions` is empty → caller treats it as breach (skip per spec §9).

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test eval/defense/defense_sim.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/defense_sim.js eval/defense/defense_sim.test.js
git commit -m "feat(defense-sim): one-prime min-loss block-assignment search"
```

---

### Task 8: `replay_to_request.js` — `--defense-only` (State-A emitter)

Add the State-A predicate so the emitter writes only begin-of-defense states with incoming attack (spec §6, §9).

**Files:**
- Modify: `eval/replay_to_request.js`
- Test: `eval/defense/state_a.test.js`

**Interfaces:**
- Produces: a `--defense-only` CLI flag; emitted State-A files keep `{mergedDeck, gameState, aiParameters}` (unchanged shape) only where `gameState.phase==='defense' && incomingAttack>0`.

- [ ] **Step 1: Confirm the incoming-attack field name**

Read `js_engine/replay_exporter.js` around the `incomingAttack` emission (the eval-pipeline handoff cites line 227). Confirm the exact key on the exported `gameState` (e.g. `incomingAttack`). Use that key in the predicate below.

- [ ] **Step 2: Write the failing test**

Create `eval/defense/state_a.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const { execFileSync } = require('node:child_process');
const fs = require('fs'); const os = require('os'); const path = require('path');

const REPLAY = 'c:/libraries/prismata-replay-parser/replays_archive'; // pick a known elite code below
test('--defense-only emits only defense-phase states with incoming>0', () => {
  // Use a known local replay code that has defense phases; FIm28-4p1PP is validated in the handoff.
  const code = 'FIm28-4p1PP';
  const fp = require('./_find_replay').find(REPLAY, code); // tiny helper, or inline the archive filename logic
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'defstateA_'));
  execFileSync('node', ['eval/replay_to_request.js', fp, '--all', out, '--defense-only'], { cwd: process.cwd() });
  const files = fs.readdirSync(out).filter(f => f.endsWith('.json'));
  assert.ok(files.length > 0, 'should emit some defense states');
  for (const f of files) {
    const gs = JSON.parse(fs.readFileSync(path.join(out, f))).gameState;
    assert.equal(gs.phase, 'defense');
    assert.ok((gs.incomingAttack | 0) > 0, `expected incoming>0, got ${gs.incomingAttack}`);
  }
});
```
(If a `_find_replay` helper does not exist, inline the archive lookup: try `${code}.json.gz`, then URL-encoded `+`→`%2B`/`@`→`%40`, matching `oracle_diff.js findFile`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test eval/defense/state_a.test.js`
Expected: FAIL — `--defense-only` is ignored, so action-phase files leak in (or the flag has no effect).

- [ ] **Step 4: Add the predicate + flag to replay_to_request.js**

Mirror `igDecidable` (lines 60-77). Add near it:
```js
function defenseDecidable(gs) {
  return gs.phase === 'defense' && ((gs.incomingAttack | 0) > 0);
}
```
In `main()`: add `const defenseOnly = argv.includes('--defense-only');` next to `igOnly`. In the emit loop (line 110 area), change the filter:
```js
if (igOnly && !igDecidable(gameState)) continue;
if (defenseOnly && !defenseDecidable(gameState)) continue;
```
Update the usage string + the JSON summary to include `defenseOnly`.

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test eval/defense/state_a.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add eval/replay_to_request.js eval/defense/state_a.test.js
git commit -m "feat(state-a): --defense-only predicate for the defense-eval emitter"
```

---

### Task 9: `state_b_capture.js` — committed-defense reader (undo-robust)

Capture, per defense turn, the human's committed just-before-swoosh board (spec §6; handoff §5). Use the `recordClick` monkeypatch (pattern from `oracle_diff.js:52-59`), last-write-wins keyed by `turnIndex`.

**Files:**
- Create: `eval/defense/state_b_capture.js`
- Test: `eval/defense/state_b_capture.test.js`

**Interfaces:**
- Consumes: `js_engine/Analyzer.js`, `js_engine/replay_exporter.js`, the replay loader from `replay_to_request.js` (reuse `buildInitInfo` + `loadJSON` — export them from `replay_to_request.js`).
- Produces: `captureCommittedDefenses(replay)` → `[{ turnIndex, player, gameState }]` where `gameState` is `stateToCppJSON` of the committed pre-swoosh board (only for turns that had a defense phase).

- [ ] **Step 1: Export the loader helpers from replay_to_request.js**

At the bottom of `eval/replay_to_request.js`, before `main();`, change to:
```js
module.exports = { loadJSON, buildInitInfo };
if (require.main === module) main();
```

- [ ] **Step 2: Write the failing test**

Create `eval/defense/state_b_capture.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const cap = require('./state_b_capture');
const { loadJSON } = require('../replay_to_request');

test('captures one committed defense per attacked turn, undo-collapsed', () => {
  const code = 'FIm28-4p1PP';
  const fp = require('./_find_replay').find('c:/libraries/prismata-replay-parser/replays_archive', code);
  const replay = loadJSON(fp);
  const defenses = cap.captureCommittedDefenses(replay);
  assert.ok(Array.isArray(defenses));
  assert.ok(defenses.length > 0, 'should capture at least one committed defense');
  for (const d of defenses) {
    assert.equal(typeof d.turnIndex, 'number');
    assert.ok(d.player === 0 || d.player === 1);
    assert.ok(d.gameState && Array.isArray(d.gameState.table));
  }
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test eval/defense/state_b_capture.test.js`
Expected: FAIL — `./state_b_capture` does not exist.

- [ ] **Step 4: Implement the capturer**

```js
'use strict';
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { buildInitInfo } = require('../replay_to_request');

function captureCommittedDefenses(replay) {
  const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
  const orig = analyzer.recordClick.bind(analyzer);
  const candidate = new Map();   // turnIndex -> { turnIndex, player, raw }  (last-write-wins)
  const committed = [];          // finalized at turn boundary

  analyzer.recordClick = function (u, d, type, id, params) {
    const prevPhase = analyzer.gameState.phase;
    const prevTurnIndex = analyzer.turnIndex;
    // capture by VALUE before the click mutates the live state (swoosh clears damage)
    let preSnap = null;
    try { preSnap = JSON.parse(analyzer.gameState.toString()); } catch (e) {}
    const r = orig(u, d, type, id, params);
    if (r && r.canClick) {
      // DEFENSE -> ACTION within the same turn = the swoosh; record/overwrite this turn's candidate
      if (preSnap && prevPhase === 'defense' && analyzer.gameState.phase === 'action'
          && analyzer.turnIndex === prevTurnIndex) {
        candidate.set(prevTurnIndex, { turnIndex: prevTurnIndex, player: (preSnap.turn % 2), raw: preSnap });
      }
      // turn boundary advanced -> the surviving candidate for prevTurnIndex is the committed defense
      if (analyzer.turnIndex !== prevTurnIndex && candidate.has(prevTurnIndex)) {
        committed.push(candidate.get(prevTurnIndex));
        candidate.delete(prevTurnIndex);
      }
    }
    return r;
  };

  try { analyzer.loaderInit(); } catch (e) { /* faithful-failure replays: skip, see corpus_scan */ }

  // flush any candidate that survived to game end (last turn never advances the index)
  for (const v of candidate.values()) committed.push(v);

  // Re-serialize each committed pre-swoosh raw state through the exporter so it matches State-A shape.
  return committed.map(c => ({
    turnIndex: c.turnIndex,
    player: c.player,
    gameState: c.raw,   // raw is already stateToCppJSON-equivalent (toString of the cpp gameState); keep as-is
  }));
}

module.exports = { captureCommittedDefenses };
```
Note: `analyzer.gameState.toString()` already yields the cpp-shaped gameState JSON (the same `oracle_diff.js` relies on). If a downstream consumer needs `replay_exporter.stateToCppJSON` instead, swap `c.raw` accordingly after confirming the shapes match against an `oracle_diff` run. The `endDefenses`/`inEndDefense` engine fields (Analyzer.js:347-355) are an alternative source — if this monkeypatch proves fragile, switch to reading `analyzer.endDefenses` (it already pops/re-pushes on re-defend).

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test eval/defense/state_b_capture.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add eval/defense/state_b_capture.js eval/defense/state_b_capture.test.js eval/replay_to_request.js
git commit -m "feat(state-b): undo-robust committed-defense capturer"
```

---

### Task 10: `metrics.js` — the metric stack + aggregation

Compute the per-position metrics (spec §7.1) and aggregate them (spec §7.3).

**Files:**
- Create: `eval/defense/metrics.js`
- Test: `eval/defense/metrics.test.js`

**Interfaces:**
- Consumes: nothing engine-specific (pure functions over assignments + losses).
- Produces:
  - `humanAssignmentFromStateB(committedGameState, activePlayer)` → `{ perUnit:{instId:damage}, chumps:[isoKey], prime:isoKey, untouched:[isoKey] }` (reads each available unit's `damageTaken`/dead from State B; classify chump/prime/untouched).
  - `loadHumanLoss(humanAssignment, board, mode)` → number (Σ loss over the human's per-unit damage).
  - `computeMetrics({ board, incoming, human, aiOurs, aiCpp })` → the per-position record (spec §7.2 shape).
  - `aggregate(records)` → `{ regret, exactMatch, primeMatch, perUnitDivergence, tieBreakSkew }` (spec §7.3).

- [ ] **Step 1: Write the failing tests**

Create `eval/defense/metrics.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const m = require('./metrics');

test('regret is 0 when human == ai min-loss assignment', () => {
  const rec = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 11, assignment: { prime: 'A', chumps: [{ isoKey: 'B', count: 5 }] } },
    aiOurs: { loss: 11, assignment: { prime: 'A', chumps: [{ isoKey: 'B', count: 5 }] }, tiedAlts: [] },
    aiCpp: { loss: 12, assignment: { prime: 'A', chumps: [] } },
  });
  assert.equal(rec.metrics.regret_ours, 0);
  assert.equal(rec.metrics.exactMatch_ours, true);
});

test('regret is positive when human play costs more under ours', () => {
  const rec = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 15, assignment: { prime: 'A', chumps: [] } },
    aiOurs: { loss: 11, assignment: { prime: 'B', chumps: [] }, tiedAlts: [] },
    aiCpp: { loss: 11, assignment: { prime: 'B', chumps: [] } },
  });
  assert.equal(rec.metrics.regret_ours, 4);
  assert.equal(rec.metrics.exactMatch_ours, false);
});

test('aggregate: mean regret + zero-regret rate', () => {
  const recs = [
    { metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] } }, tags: [] },
    { metrics: { regret_ours: 4, exactMatch_ours: false, primeMatch_ours: false }, diag: { chumpDiff_ours: { aiOnly: ['X'], humanOnly: ['Y'] } }, tags: [] },
  ];
  const agg = m.aggregate(recs);
  assert.equal(agg.regret.mean_ours, 2);
  assert.equal(agg.regret.zeroRate_ours, 0.5);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test eval/defense/metrics.test.js`
Expected: FAIL — `./metrics` does not exist.

- [ ] **Step 3: Implement metrics.js**

```js
'use strict';

function sameAssignment(a, b) {
  if (!a || !b) return false;
  const norm = x => JSON.stringify({
    prime: x.prime || null,
    chumps: (x.chumps || []).slice().sort((p, q) => (p.isoKey > q.isoKey ? 1 : -1)),
  });
  return norm(a) === norm(b);
}

function computeMetrics({ board, incoming, human, aiOurs, aiCpp }) {
  const regret_ours = Math.max(0, human.humanLoss - aiOurs.loss);
  const exactMatch_ours = (aiOurs.tiedAlts || [{ assignment: aiOurs.assignment }])
    .some(t => sameAssignment(human.assignment, t.assignment));
  const exactMatch_cpp = sameAssignment(human.assignment, aiCpp.assignment);
  const primeMatch_ours = (human.assignment.prime || null) === (aiOurs.assignment.prime || null);
  const primeMatch_cpp = (human.assignment.prime || null) === (aiCpp.assignment.prime || null);

  // per-unit chump divergence (iso-class symmetric difference)
  const humanChumps = new Set((human.assignment.chumps || []).flatMap(c => Array(c.count).fill(c.isoKey)));
  const aiChumps = new Set((aiOurs.assignment.chumps || []).flatMap(c => Array(c.count).fill(c.isoKey)));
  const aiOnly = [...aiChumps].filter(k => !humanChumps.has(k));
  const humanOnly = [...humanChumps].filter(k => !aiChumps.has(k));

  // tie-break contrast: when there are tied alternatives and human chose a tied one, log the prime-class contrast
  const tieBreakContrast = (aiOurs.tiedAlts && aiOurs.tiedAlts.length > 1)
    ? aiOurs.tiedAlts.map(t => t.assignment.prime).filter((v, i, a) => a.indexOf(v) === i)
    : [];

  return {
    id: { /* filled by compare.js: replay, turn, player */ },
    incomingAttack: incoming,
    available: board.map(b => b.isoKey).filter(Boolean),
    human: { assignment: human.assignment, loss_ours: human.humanLoss },
    ai_ours: { assignment: aiOurs.assignment, loss: aiOurs.loss, tiedAltsWithinEps: aiOurs.tiedAlts },
    ai_cpp: { assignment: aiCpp.assignment, loss: aiCpp.loss },
    metrics: { regret_ours, regret_cpp: Math.max(0, (human.humanLoss_cpp || 0) - aiCpp.loss), exactMatch_ours, exactMatch_cpp, primeMatch_ours, primeMatch_cpp },
    diag: { chumpDiff_ours: { aiOnly, humanOnly }, tieBreakContrast },
    tags: [],
  };
}

function aggregate(records) {
  const n = records.length || 1;
  const sum = (f) => records.reduce((a, r) => a + f(r), 0);
  const regrets = records.map(r => r.metrics.regret_ours);
  const perUnit = {}; // isoKey -> {aiChumpedMore, humanChumpedMore}
  for (const r of records) {
    for (const k of r.diag.chumpDiff_ours.aiOnly) (perUnit[k] = perUnit[k] || { aiOnly: 0, humanOnly: 0 }).aiOnly++;
    for (const k of r.diag.chumpDiff_ours.humanOnly) (perUnit[k] = perUnit[k] || { aiOnly: 0, humanOnly: 0 }).humanOnly++;
  }
  return {
    n: records.length,
    regret: {
      mean_ours: sum(r => r.metrics.regret_ours) / n,
      zeroRate_ours: sum(r => (r.metrics.regret_ours === 0 ? 1 : 0)) / n,
      mean_cpp: sum(r => r.metrics.regret_cpp) / n,
      zeroRate_cpp: sum(r => (r.metrics.regret_cpp === 0 ? 1 : 0)) / n,
    },
    exactMatch: { ours: sum(r => (r.metrics.exactMatch_ours ? 1 : 0)) / n, cpp: sum(r => (r.metrics.exactMatch_cpp ? 1 : 0)) / n },
    primeMatch: { ours: sum(r => (r.metrics.primeMatch_ours ? 1 : 0)) / n, cpp: sum(r => (r.metrics.primeMatch_cpp ? 1 : 0)) / n },
    perUnitDivergence: Object.entries(perUnit).map(([k, v]) => ({ isoKey: k, ...v }))
      .sort((a, b) => (b.aiOnly + b.humanOnly) - (a.aiOnly + a.humanOnly)),
    tieBreakSkew: buildTieBreakSkew(records),
  };
}

function buildTieBreakSkew(records) {
  // pair-level: when ours ties >=2 primes, count which the human chose
  const pairs = {}; // "P|Q" -> {P:count, Q:count}
  for (const r of records) {
    const contrast = r.diag.tieBreakContrast || [];
    if (contrast.length < 2) continue;
    const chosen = r.human.assignment.prime;
    for (const alt of contrast) {
      if (alt === chosen) continue;
      const key = [chosen, alt].sort().join('||');
      pairs[key] = pairs[key] || {};
      pairs[key][chosen] = (pairs[key][chosen] || 0) + 1;
    }
  }
  return Object.entries(pairs).map(([k, v]) => ({ pair: k, leans: v }))
    .sort((a, b) => Object.values(b.leans).reduce((x, y) => x + y, 0) - Object.values(a.leans).reduce((x, y) => x + y, 0));
}

module.exports = { computeMetrics, aggregate, sameAssignment };
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test eval/defense/metrics.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/metrics.js eval/defense/metrics.test.js
git commit -m "feat(metrics): regret, exact/prime-match, tie-break-skew, per-unit divergence + aggregate"
```

---

### Task 11: `compare.js` (harness) + `report.js`

Wire it together: for each replay, extract State A (defense-only) and State B (committed), pair them per turn, run the sim in both modes, compute metrics, write JSONL records; then render the aggregate markdown report.

**Files:**
- Create: `eval/defense/compare.js`
- Create: `eval/defense/report.js`
- Test: `eval/defense/report.test.js` (report rendering is pure; compare is integration, smoke-run on the dev corpus)

**Interfaces:**
- Consumes: `state_b_capture`, `metrics`, `defense_sim`, `defense_value`, `replay_to_request` (loader), `Analyzer` (for State-A extraction in-process), the card library.
- Produces:
  - `compare.js` CLI: `node eval/defense/compare.js <codesFile> <outDir>` → writes `<outDir>/records.jsonl` + `<outDir>/report.md`.
  - `report.js`: `renderReport(aggregates)` → markdown string.

- [ ] **Step 1: Write the failing test (report rendering)**

Create `eval/defense/report.test.js`:
```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const { renderReport } = require('./report');

test('renderReport includes regret and divergence sections', () => {
  const md = renderReport({
    n: 100,
    regret: { mean_ours: 0.4, zeroRate_ours: 0.82, mean_cpp: 1.1, zeroRate_cpp: 0.6 },
    exactMatch: { ours: 0.55, cpp: 0.4 }, primeMatch: { ours: 0.7, cpp: 0.5 },
    perUnitDivergence: [{ isoKey: 'Xaetron|0|5|...', aiOnly: 3, humanOnly: 12 }],
    tieBreakSkew: [{ pair: 'A||B', leans: { A: 20, B: 2 } }],
  });
  assert.match(md, /Regret/);
  assert.match(md, /zero-regret/i);
  assert.match(md, /Per-unit divergence/i);
  assert.match(md, /Tie-break skew/i);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test eval/defense/report.test.js`
Expected: FAIL — `./report` does not exist.

- [ ] **Step 3: Implement report.js**

```js
'use strict';
function pct(x) { return (100 * x).toFixed(1) + '%'; }
function renderReport(a) {
  let md = `# Defense-Eval Report\n\n**Positions:** ${a.n}\n\n`;
  md += `## Regret (primary)\n`;
  md += `| | mean | zero-regret |\n|---|--:|--:|\n`;
  md += `| ours | ${a.regret.mean_ours.toFixed(3)} | ${pct(a.regret.zeroRate_ours)} |\n`;
  md += `| current C++ | ${a.regret.mean_cpp.toFixed(3)} | ${pct(a.regret.zeroRate_cpp)} |\n\n`;
  md += `## Exact-match-iso / Prime-match\n`;
  md += `| | exact-match | prime-match |\n|---|--:|--:|\n`;
  md += `| ours | ${pct(a.exactMatch.ours)} | ${pct(a.primeMatch.ours)} |\n`;
  md += `| current C++ | ${pct(a.exactMatch.cpp)} | ${pct(a.primeMatch.cpp)} |\n\n`;
  md += `## Per-unit divergence (AI chumps/saves differently than humans)\n`;
  md += `| iso-class | ai-only chumped | human-only chumped |\n|---|--:|--:|\n`;
  for (const d of a.perUnitDivergence.slice(0, 30)) md += `| ${d.isoKey} | ${d.aiOnly} | ${d.humanOnly} |\n`;
  md += `\n## Tie-break skew (corrective-term candidates)\n`;
  md += `| iso-class pair | human lean |\n|---|---|\n`;
  for (const s of a.tieBreakSkew.slice(0, 30)) md += `| ${s.pair} | ${JSON.stringify(s.leans)} |\n`;
  return md;
}
module.exports = { renderReport };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test eval/defense/report.test.js`
Expected: PASS.

- [ ] **Step 5: Implement compare.js (the integration harness)**

```js
'use strict';
const fs = require('fs'); const path = require('path');
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { loadJSON, buildInitInfo } = require('../replay_to_request');
const cap = require('./state_b_capture');
const sim = require('./defense_sim');
const dv = require('./defense_value');
const metrics = require('./metrics');
const { renderReport } = require('./report');
const { find } = require('./_find_replay'); // tiny archive lookup helper (Task 8)

const ARCHIVE = 'c:/libraries/prismata-replay-parser/replays_archive';

// State-A: begin-of-defense states keyed by turnIndex (the AI input).
function stateAByTurn(replay) {
  const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
  analyzer.loaderInit();
  const out = new Map(); // turnIndex -> gameState
  analyzer.beginTurnHistory.forEach((st, i) => {
    const gs = replay_exporter.stateToCppJSON(st);
    if (gs.phase === 'defense' && ((gs.incomingAttack | 0) > 0)) out.set(i, gs);
  });
  return out;
}

// active player's available (blockable) units from a gameState.
function availableBlockers(gs, player) {
  return (gs.table || []).filter(u =>
    u.owner === player && (u.deadness === undefined || u.deadness === 'alive')
    && (u.constructionTime | 0) === 0 && !((u.delay | 0) > 0));
}

function humanAssignment(committedGS, player, board) {
  const perUnit = {}; const chumps = []; let prime = null; const untouched = [];
  const byId = new Map(board.map(b => [b.instId, b]));
  for (const u of (committedGS.table || [])) {
    if (u.owner !== player) continue;
    const taken = (u.damageTaken | 0);
    const view = byId.get(u.instId); if (!view) continue;
    perUnit[u.instId] = taken;
    const k = dv.isoKey(view);
    if (taken >= view.hp || (u.deadness && u.deadness !== 'alive')) chumps.push(k);
    else if (taken > 0) prime = k;          // the single partial-damage survivor
    else untouched.push(k);
  }
  // collapse chumps/untouched into {isoKey,count}
  const tally = arr => Object.entries(arr.reduce((m, k) => ((m[k] = (m[k] || 0) + 1), m), {})).map(([isoKey, count]) => ({ isoKey, count }));
  return { perUnit, chumps: tally(chumps), prime, untouched: tally(untouched) };
}

function main() {
  const [codesFile, outDir] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const codes = fs.readFileSync(codesFile, 'utf-8').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const records = [];
  const recStream = fs.createWriteStream(path.join(outDir, 'records.jsonl'));

  for (const code of codes) {
    let replay; try { replay = loadJSON(find(ARCHIVE, code)); } catch (e) { process.stderr.write(`skip ${code}: ${e.message}\n`); continue; }
    const stateA = stateAByTurn(replay);
    const committed = cap.captureCommittedDefenses(replay);
    for (const c of committed) {
      const gsA = stateA.get(c.turnIndex); if (!gsA) continue;   // only attacked turns
      const player = c.player;
      const incoming = gsA.incomingAttack | 0;
      const blockers = availableBlockers(gsA, player).map(u => dv.unitView(u));
      const rawBlockers = availableBlockers(gsA, player);
      if (!blockers.length) continue;

      const aiOurs = sim.solveDefense(rawBlockers, incoming, 'ours');
      const aiCpp = sim.solveDefense(rawBlockers, incoming, 'cpp');
      if (!aiOurs.assignment || !aiCpp.assignment) continue;      // breach -> skip (spec §9)

      const human = humanAssignment(c.gameState, player, blockers);
      // human loss under each mode = Σ loss over the human's per-unit damage
      const humanLossOurs = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'ours'), 0);
      const humanLossCpp = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'cpp'), 0);

      const rec = metrics.computeMetrics({
        board: blockers, incoming,
        human: { assignment: human, humanLoss: humanLossOurs, humanLoss_cpp: humanLossCpp },
        aiOurs, aiCpp,
      });
      rec.id = { replay: code, turnIndex: c.turnIndex, player };
      rec.tags = [];
      if ((gsA.table || []).some(u => (u.disruptDamage | 0) > 0)) rec.tags.push('chillPresent');
      if (aiOurs.tiedAlts.length <= 1 && blockers.length <= 2) rec.tags.push('forced');
      records.push(rec);
      recStream.write(JSON.stringify(rec) + '\n');
    }
  }
  recStream.end();
  const agg = metrics.aggregate(records);
  fs.writeFileSync(path.join(outDir, 'report.md'), renderReport(agg));
  process.stdout.write(`wrote ${records.length} records + report.md to ${outDir}\n`);
}
main();
```

- [ ] **Step 6: Smoke-run on the dev corpus**

Create `eval/defense/dev_codes.txt` with ~20 elite codes (from `c:/libraries/prismata-replay-parser/final_training_codes_1800.txt`, picking high-rating games that exist in the archive). Run:
```bash
node eval/defense/compare.js eval/defense/dev_codes.txt eval/defense/_dev_out
```
Expected: prints `wrote N records + report.md`; `records.jsonl` is non-empty; `report.md` renders. Eyeball a few records for sanity (defense positions with sensible assignments, regret ≥ 0).

- [ ] **Step 7: Commit**

```bash
git add eval/defense/compare.js eval/defense/report.js eval/defense/report.test.js eval/defense/dev_codes.txt
git commit -m "feat(defense-eval): comparison harness + aggregate report"
```

---

### Task 12: `validate_gate.js` — cpp-replica vs the real engine (100 games)

Prove the JS sim in `cpp` mode reproduces the real engine's defense picks (spec §8). This gates trusting the sim for the `ours` runs.

**Files:**
- Create: `eval/defense/validate_gate.js`

**Interfaces:**
- Consumes: `defense_sim` (cpp mode), `js_engine/query_move.js` (real engine), the State-A extractor.
- Produces: a CLI `node eval/defense/validate_gate.js <codesFile>` that, per defense position, compares `solveDefense(..., 'cpp')` to the engine's defense clicks and reports the mismatch count.

- [ ] **Step 1: Confirm the query_move defense-clicks interface**

Read `js_engine/query_move.js` to confirm: how it is invoked (it consumes a `{mergedDeck, gameState, aiParameters}` request file and the `--dave-exe` flag; CLAUDE.md documents `node js_engine/query_move.js <reqFile> --dave-exe <exe>`), and the shape of its output (the `clicks`/`aiclicks` array with block assignments). Note the exact output field for "defense clicks" (the `inst clicked` / ASSIGN_BLOCKER entries). The steam bundle to drive: `C:/libraries/DSNN_steam_bundles/v221_rl_iter8/` with `use_dsnn.txt` setting `think_time=0`, `max_traversals=1` (owner-verified).

- [ ] **Step 2: Implement validate_gate.js**

```js
'use strict';
const fs = require('fs'); const os = require('os'); const path = require('path');
const { execFileSync } = require('node:child_process');
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { loadJSON, buildInitInfo } = require('../replay_to_request');
const sim = require('./defense_sim');
const dv = require('./defense_value');
const { find } = require('./_find_replay');

const ARCHIVE = 'c:/libraries/prismata-replay-parser/replays_archive';
const BUNDLE = 'C:/libraries/DSNN_steam_bundles/v221_rl_iter8';
const AIPARAMS = 'docs/scratch/ktink_t9_action_request.json';

// Run the real engine on a State-A request; return the set of instIds it assigned as blockers (chumps+prime).
function engineDefenseInstIds(gs, mergedDeck) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'vg_'));
  const reqPath = path.join(tmp, 'req.json');
  const aiParameters = loadJSON(AIPARAMS).aiParameters;
  fs.writeFileSync(reqPath, JSON.stringify({ mergedDeck, gameState: gs, aiParameters }));
  // Drive query_move against the bundle exe (resolve the exe path from use_dsnn.txt / the bundle README).
  const out = execFileSync('node', ['js_engine/query_move.js', reqPath, '--dave-exe', BUNDLE + '/PrismataAI.exe'],
    { cwd: process.cwd(), encoding: 'utf-8' });
  const res = JSON.parse(out);
  // collect block-assignment clicks (confirm the exact type string in Step 1; ASSIGN_BLOCKER / 'inst clicked' in defense)
  const ids = (res.clicks || res.aiclicks || []).filter(c => c._phase === 'defense' || c._type === 'inst clicked').map(c => c._id);
  return new Set(ids);
}

function main() {
  const codesFile = process.argv[2];
  const codes = fs.readFileSync(codesFile, 'utf-8').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  let total = 0, mismatch = 0;
  for (const code of codes) {
    let replay; try { replay = loadJSON(find(ARCHIVE, code)); } catch (e) { continue; }
    const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
    analyzer.loaderInit();
    analyzer.beginTurnHistory.forEach(st => {
      const gs = replay_exporter.stateToCppJSON(st);
      if (gs.phase !== 'defense' || (gs.incomingAttack | 0) <= 0) return;
      const player = gs.turn % 2;
      const blockers = (gs.table || []).filter(u => u.owner === player && (u.deadness === undefined || u.deadness === 'alive') && (u.constructionTime | 0) === 0);
      if (!blockers.length) return;
      const ours = sim.solveDefense(blockers, gs.incomingAttack | 0, 'cpp');
      if (!ours.assignment) return; // breach -> skip
      const simIds = new Set(Object.entries(ours.assignment.perUnit).filter(([, d]) => d > 0).map(([id]) => Number(id)));
      const engineIds = engineDefenseInstIds(gs, replay.deckInfo.mergedDeck);
      total++;
      const same = simIds.size === engineIds.size && [...simIds].every(id => engineIds.has(id));
      if (!same) { mismatch++; process.stderr.write(`MISMATCH ${code} turn=${gs.turn}: sim=${[...simIds]} engine=${[...engineIds]}\n`); }
    });
  }
  process.stdout.write(`validation gate: ${total - mismatch}/${total} positions match (${mismatch} mismatches)\n`);
  process.exit(mismatch === 0 ? 0 : 1);
}
main();
```

- [ ] **Step 3: Build the 100-game validation codes list**

Create `eval/defense/validate_codes.txt` with 100 elite codes present in the archive (from `final_training_codes_1800.txt`, filtered to existing files). 

- [ ] **Step 4: Run the gate**

```bash
node eval/defense/validate_gate.js eval/defense/validate_codes.txt
```
Expected: `validation gate: N/N positions match (0 mismatches)`. If mismatches appear, inspect the printed cases — most likely causes (in order): the `query_move` defense-click field name (fix Step 1's filter), the `isAbilityHealthUserOnly`/Forcefield approximations in `lossCpp` (Task 5 — fix the named unit), or a tie-break ordering difference (the engine's first-min-loss vs the sim's sort — make the sim's sort stable and match the iso-class discovery order). Iterate until 0 mismatches.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/validate_gate.js eval/defense/validate_codes.txt
git commit -m "feat(defense-eval): cpp-replica validation gate vs real engine (100 games)"
```

---

## Self-Review (completed by plan author)

**Spec coverage:** §2 mechanic → Tasks 7/9 (one-prime, State-B reading). §4 value/loss → Tasks 1–6. §4.4 fixes → Task 2. §5 sim → Task 7. §6 State A/B → Tasks 8/9. §7 metrics/record → Task 10. §8 validation gate → Task 12. §9 scope rules → Tasks 8 (defense-only), 11 (breach-skip, tags). §10 corpus/outputs → Task 11. §11 out-of-scope/known-limitations → not built (correct; deferred). Build order §12 → Tasks ordered to match.

**Open follow-ups left for execution (legitimately data-driven, not placeholders):** the `_find_replay` helper (a ~10-line archive lookup mirroring `oracle_diff.js findFile`) is referenced by Tasks 8/11/12 — create it in Task 8 Step 2 as `eval/defense/_find_replay.js` exporting `find(archiveDir, code)`. The `query_move` defense-click field name and the `lossCpp` `isAbilityHealthUserOnly`/Forcefield approximations are explicitly resolved by the validation gate (Task 12 Step 4), which is the correct place — the gate fails loudly until they are exact.

**Type consistency:** `solveDefense → {assignment:{chumps,prime,untouched,perUnit}, loss, tiedAlts}` is consumed identically in metrics/compare. `unitView` fields (`internal, hp, fragile, heal, max, raw, instId`) are used consistently. `loss(view, damage, mode)` signature is stable across value/sim/metrics/compare.

---

## Execution Handoff

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.

Choose when ready to build.
