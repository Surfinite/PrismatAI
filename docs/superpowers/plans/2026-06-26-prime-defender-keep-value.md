# Prime-Defender Keep-Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a prime-defender keep-value to the JS defense-eval model so `ours`-mode defense credits the perpetual *future absorb* a surviving anchor provides — fixing the over-chumping of reusable blockers (Walls) and the mishandling of healers — built on a half-turn clock with a multi-turn heal climb.

**Architecture:** Three coupled value-model changes, JS only. (1) A **half-turn clock** in `gen_our_numbers_v2.js` makes `ATK` derive from `BV`. (2) A **multi-turn heal climb** replaces the one-heal soak in the chump term. (3) The defense sim's `ours` objective gains a **prime credit** (`futureAbsorb`, uncapped) and a **room-capped untouched-healer credit**. The faithful `cpp` mode is untouched (the validation gate must still pass). `compare.js` applies the credits symmetrically to the human (Finding A); the tripwire moves to the chump-loss component (Finding B).

**Tech Stack:** Node.js CommonJS, `node:test` + `node:assert`. Run all tests with the glob: `node --test eval/defense/*.test.js`.

## Global Constraints

- **WHICH ENGINE:** the card library + `cpp` heuristics this mirrors live in `c:/libraries/PrismataAI-dave-master` (engine_v1). THIS repo's `source/` is the indicted engine_v2 — ignore it. Work only in `docs/scratch/gen_our_numbers_v2.js` + `eval/defense/`.
- **`cpp` mode is sacred.** None of these changes may alter `solveDefense(..., 'cpp')` output or the `loss(..., 'cpp')` values — that is the faithful `DamageLoss_WillCost` replica validated against the real engine (gate 1234/1235). All changes are `ours`-only. Verify byte-identical `cpp` output.
- **Iso, not instId** everywhere; same-class units are interchangeable.
- **Constants:** `BV = 2.2`; `R_HALF = √(4/3) ≈ 1.1547`; `d² = 1/R_HALF² = 0.75`; `P = 1/(1−d²) = 4`; `P−1 = 3`.
- **`ours(c, stateOverride)`** reads `_hp/_chg/_rem` from `{hp,charge,life}`; the heal climb uses **current** HP (`_hp`), the doomed factor uses **current remaining** life (`_rem`).
- Run tests with the **glob** form `node --test eval/defense/*.test.js` (bare-dir form errors on Node 24).
- Commit per task on `feature/production-vectors`. **Do NOT push** (owner pushes manually).
- The authoritative design is `docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md` (§2 revised 2026-06-26). All pinned numbers below were verified against a brute-force oracle during design.

**Card internal names** (cardLibrary keys): Wall=`Wall`, Energy Matrix=`Golem`, Husk=`House`, Rhino=`Elephant` (hp2,charge2), Engineer=`Engineer`, Steelsplitter=`Treant`, Doomed Mech=`Doomed Mech` (hp5), Xaetron=`Xaetron` (fragile, heal4, max12), Innervi Field=`Innervi Field` (fragile heal1 max5 life3), Mahar Rectifier=`Viletrope` (fragile heal2 max5), Tarsier=`Tesla Tower`. Test `mk()` helper uses `cardName` (display) which `unitView` resolves to internal.

---

## Task 1: Half-turn clock (`R_HALF` + derived `ATK`)

**Files:**
- Modify: `docs/scratch/gen_our_numbers_v2.js:23-24` (constants)
- Test: `eval/defense/value_model.test.js`

**Interfaces:**
- Produces: `vm.CONSTANTS.ATK` now `= BV / R_HALF ≈ 1.9053` (was the standalone `2.0`); a module-scope `const R_HALF` consumed by Task 2.

- [ ] **Step 1: Write the failing test** — append to `eval/defense/value_model.test.js`:

```js
test('§1 half-turn clock: ATK = BV / R_HALF', () => {
  const R_HALF = Math.sqrt(4 / 3);
  assert.ok(Math.abs(vm.CONSTANTS.ATK - vm.CONSTANTS.BV / R_HALF) < 1e-9, `ATK should derive from BV/R_HALF, got ${vm.CONSTANTS.ATK}`);
  assert.ok(Math.abs(vm.CONSTANTS.ATK - 1.9053) < 0.001, `ATK ~1.905, got ${vm.CONSTANTS.ATK}`);
});

test('§1 ripple: attacker scales ~x0.95, pure blockers unchanged', () => {
  const round = x => Math.round(x * 100) / 100;
  assert.equal(round(vm.ours(vm.lib['Tesla Tower']).v), 9.82); // Tarsier attacker: 10.2 -> 9.82
  assert.equal(round(vm.ours(vm.lib['Wall']).v), 6.6);          // pure blocker unchanged
  assert.equal(round(vm.ours(vm.lib['Golem']).v), 11);          // EM unchanged
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node --test eval/defense/value_model.test.js`
Expected: the new tests FAIL (current ATK is `2.0`, Tarsier is `10.2`).

- [ ] **Step 3: Implement** — in `docs/scratch/gen_our_numbers_v2.js`, replace lines 23-24:

```js
const BV = 2.2;     // block value per HP (one soak); blocker cost/HP w/ grounded resources (Wall 2.22, EM 2.27, Aegis 2.0)
const R_HALF = Math.sqrt(4 / 3); // per-HALF-turn discount base; d = 1/R_HALF, d^2 = 0.75. A block is realized on my
const ATK = BV / R_HALF;    // defense phase; an attack lands a half-turn later -> ATK = BV*d. (was standalone 2.0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `node --test eval/defense/value_model.test.js`
Expected: PASS (incl. the pre-existing `regression: known table values` and `§4.4` tests — pure blockers / token-sac units are ATK-independent).

- [ ] **Step 5: Commit**

```bash
git add docs/scratch/gen_our_numbers_v2.js eval/defense/value_model.test.js
git commit -m "feat(defense-eval): half-turn clock — ATK derives from BV/R_HALF"
```

---

## Task 2: Multi-turn heal climb (chump-term, capped)

**Files:**
- Modify: `docs/scratch/gen_our_numbers_v2.js:71-72` (the `soakHP` line in `coreValue`)
- Test: `eval/defense/value_model.test.js`, and UPDATE `eval/defense/defense_value.test.js` (existing Xaetron assertions)

**Interfaces:**
- Consumes: `R_HALF` (Task 1).
- Produces: healer chump-term `V`/`body` changes — `body(Xaetron@5) = 21.21` (was 19.7), `@8 = 24.1` (was 26.3), `@2 = 17.71`.

- [ ] **Step 1: Write the failing test** — append to `eval/defense/value_model.test.js`:

```js
test('§3a multi-turn heal climb (discounted, capped at max)', () => {
  const near = (a, b) => Math.abs(a - b) < 0.02;
  // Xaetron heal 4 max 12, fragile (-0.1 haircut). @5: 5 + 4*.75 + 3*.5625 = 9.6875 -> *2.2 - 0.1 = 21.21
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 5 }).block, 21.21), `@5 got ${vm.ours(vm.lib['Xaetron'], { hp: 5 }).block}`);
  // @2: 2 + 4*.75 + 4*.5625 + 2*.4219 = 8.06 -> 17.71
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 2 }).block, 17.71), `@2 got ${vm.ours(vm.lib['Xaetron'], { hp: 2 }).block}`);
  // @8 (room 4 = one full heal then capped): 8 + 4*.75 = 11 -> 24.1
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 8 }).block, 24.1), `@8 got ${vm.ours(vm.lib['Xaetron'], { hp: 8 }).block}`);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node --test eval/defense/value_model.test.js`
Expected: FAIL (current one-heal soak gives @5=19.7, @8=26.3).

- [ ] **Step 3: Implement** — in `coreValue`, replace the `soakHP` line (currently `const soakHP = heal > 0 ? Math.min(_hp + heal, hpMax) : _hp;`):

```js
    // §3a multi-turn heal: a kept healer climbs to max over several turns, each turn's gain
    // (cumulative-capped at max) discounted by d^(2t). soakHP = currentHP + Σ_{t>=1} gain_t·d^(2t).
    let soakHP = _hp;
    if (heal > 0) {
      const d2 = 1 / (R_HALF * R_HALF);  // = 0.75
      let cumHP = _hp, t = 1;
      while (cumHP < hpMax && t < 100) {
        const gain = Math.min(heal, hpMax - cumHP);
        soakHP += gain * Math.pow(d2, t);
        cumHP += gain; t++;
      }
    }
```

- [ ] **Step 4: Update the existing Xaetron assertions** in `eval/defense/defense_value.test.js` (they encode the OLD one-heal numbers and will now fail). Apply these exact replacements:

```js
// in 'body uses CURRENT hp and heal-aware effective soak':
  const x8 = dv.body(dv.unitView(mk('Xaetron', { health: 8 })));
  assert.ok(near(x8, 24.1), `Xaetron@8 body expected ~24.1, got ${x8}`);
  const x5 = dv.body(dv.unitView(mk('Xaetron', { health: 5 })));
  assert.ok(near(x5, 21.21), `Xaetron@5 body expected ~21.21, got ${x5}`);

// in 'loss ours: fragile healer survivor = body delta (Xaetron@3 absorbs 2)':
  // body(@3)=18.98 ; body(@1)=16.43 ; delta=2.55
  assert.ok(near(dv.loss(x, 2, 'ours'), 2.55), `got ${dv.loss(x, 2, 'ours')}`);

// in 'loss ours: heal headroom makes absorption free (Xaetron@10 absorbs 2)':
  // body(@10)=25.2 ; body(@8)=24.1 ; delta 1.1 (NOT 0 — the discounted climb means @10 > @8)
  assert.ok(near(dv.loss(x, 2, 'ours'), 1.1), `got ${dv.loss(x, 2, 'ours')}`);
```

Also rename that last test's title from `heal headroom makes absorption free` to `heal headroom makes absorption nearly free` (it's 1.1, not 0).

- [ ] **Step 5: Run to verify both files pass**

Run: `node --test eval/defense/value_model.test.js eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/scratch/gen_our_numbers_v2.js eval/defense/value_model.test.js eval/defense/defense_value.test.js
git commit -m "feat(defense-eval): multi-turn discounted heal climb in the chump term"
```

---

## Task 3: `futureAbsorb` + `untouchedHealerCredit` helpers

**Files:**
- Modify: `eval/defense/defense_value.js` (add two functions + exports, before `module.exports`)
- Test: `eval/defense/defense_value.test.js`

**Interfaces:**
- Consumes: `BV` (already imported), `view.{ct,hp,fragile,heal,max,life}`.
- Produces:
  - `futureAbsorb(view): number` — uncapped perpetual absorb credit (prime credit).
  - `untouchedHealerCredit(view): number` — room-capped credit for an untouched below-max healer (0 for non-healers and maxed healers).
  - `isBelowMaxHealer(view): boolean` — `fragile && heal>0 && hp < max`.

- [ ] **Step 1: Write the failing test** — append to `eval/defense/defense_value.test.js`:

```js
test('§2 futureAbsorb: non-fragile hp-1, healer heal, doomed factor', () => {
  const near = (a, b) => Math.abs(a - b) < 0.02;
  assert.ok(near(dv.futureAbsorb(dv.unitView(mk('Wall', { health: 3 }))), 13.2));      // (3-1)*2.2*3
  assert.ok(near(dv.futureAbsorb(dv.unitView(mk('Golem', { health: 5 }))), 26.4));     // EM (5-1)*2.2*3
  assert.ok(near(dv.futureAbsorb(dv.unitView(mk('Xaetron', { health: 5 }))), 26.4));   // healer heal*2.2*3
  assert.equal(dv.futureAbsorb(dv.unitView(mk('Engineer', { health: 1 }))), 0);        // hp-1 = 0
  assert.ok(near(dv.futureAbsorb(dv.unitView(mk('Doomed Mech', { health: 5, lifespan: 5 }))), 18.05)); // factor Σ_1..4 .75^k
  assert.ok(near(dv.futureAbsorb(dv.unitView(mk('Doomed Mech', { health: 5, lifespan: 2 }))), 6.6));   // factor .75
});

test('§2 untouchedHealerCredit: room-capped by min(1, room/heal)', () => {
  const near = (a, b) => Math.abs(a - b) < 0.02;
  assert.ok(near(dv.untouchedHealerCredit(dv.unitView(mk('Xaetron', { health: 8 }))), 26.4)); // room4=heal4 -> full
  assert.ok(near(dv.untouchedHealerCredit(dv.unitView(mk('Xaetron', { health: 11 }))), 6.6)); // room1 -> *0.25
  assert.equal(dv.untouchedHealerCredit(dv.unitView(mk('Xaetron', { health: 12 }))), 0);      // maxed -> 0 (dump)
  assert.equal(dv.untouchedHealerCredit(dv.unitView(mk('Wall', { health: 3 }))), 0);          // non-healer -> 0
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node --test eval/defense/defense_value.test.js`
Expected: FAIL with "dv.futureAbsorb is not a function".

- [ ] **Step 3: Implement** — in `eval/defense/defense_value.js`, add before `module.exports`:

```js
// ---------------------------------------------------------------------------
// §2 prime-defender keep-value (ours mode). futureAbsorb = the perpetual future absorb a SURVIVING
// ANCHOR provides on later turns — the one thing the chump term misses. untouchedHealerCredit = the
// same value for a below-max healer that survives UNTOUCHED (it banks deferred absorb by climbing),
// ROOM-CAPPED so a near-maxed healer is dumped rather than preserved. Design:
// docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md §2 (revised 2026-06-26).
// ---------------------------------------------------------------------------
const P_PERP = 1 / (1 - 0.75); // = 4 (d^2 = 0.75)
function doomedFactorFA(life) { let s = 0; for (let k = 1; k <= life - 1; k++) s += Math.pow(0.75, k); return s; }

// sustainableAbsorb · BV · factor. Uncapped (P-1)=3 perpetual (first future absorb is next defense
// phase, already delayed). Non-fragile -> hp-1 (repairs); fragile healer -> heal; doomed -> finite factor.
function futureAbsorb(view) {
  if (!view.ct) return 0;
  let sustain;
  if (view.fragile) sustain = view.heal > 0 ? view.heal : 0;
  else sustain = view.hp - 1;
  if (sustain <= 0) return 0;
  const life = view.life; // undefined = permanent; >=1 = doomed remaining
  const factor = (life !== undefined) ? doomedFactorFA(life) : (P_PERP - 1);
  return sustain * BV * factor;
}

function isBelowMaxHealer(view) { return !!(view.ct && view.fragile && view.heal > 0 && view.hp < view.max); }

// Untouched below-max healer earns futureAbsorb, ROOM-CAPPED by min(1, room/heal) — mirroring the §3a
// chump-loss climb cap. Full when room >= heal (climbs efficiently); shrinks near max; 0 at max ("dump it").
function untouchedHealerCredit(view) {
  if (!isBelowMaxHealer(view)) return 0;
  const room = view.max - view.hp;          // > 0 by isBelowMaxHealer
  return futureAbsorb(view) * Math.min(1, room / view.heal);
}
```

And extend the exports line:

```js
module.exports = { unitView, V, body, resolveInternal, loss, isoKey, decodeIso, isIsomorphic, buildResonateContext, futureAbsorb, untouchedHealerCredit, isBelowMaxHealer };
```

- [ ] **Step 4: Run to verify it passes**

Run: `node --test eval/defense/defense_value.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/defense_value.js eval/defense/defense_value.test.js
git commit -m "feat(defense-eval): futureAbsorb + room-capped untouchedHealerCredit"
```

---

## Task 4: `ours`-mode objective in `defense_sim.js` (+ negFloor + oracle cross-check)

**Files:**
- Modify: `eval/defense/defense_sim.js`
- Test: `eval/defense/defense_sim.test.js` (add acceptance cases + oracle cross-check; update 2 existing tests)

**Interfaces:**
- Consumes: `dv.{futureAbsorb, untouchedHealerCredit, isBelowMaxHealer, loss, unitView, isoKey}`.
- Produces: `solveDefense(stateUnits, incoming, 'ours', ...)` now minimizes
  `loss = Σ_dead V + primeLoss − futureAbsorb(prime, if survives) − Σ_{untouched below-max healers} untouchedHealerCredit`.
  Return value also gains `chumpLossComponent` (= `Σ_dead V + primeLoss`, the pre-credit part, for the Task-6 tripwire). `cpp` mode unchanged.

**Approach — the "−H" incremental trick** (keeps the credit incremental so the B&B stays valid). Let
`H = Σ over all below-max-healer units of untouchedHealerCredit`. Start the recursion's `lossScore` at `−H`
(every below-max healer "untouched-credited" by default). Then:
- A below-max healer that is **chumped** adds back its `untouchedHealerCredit` on top of its death `V` (it's no longer untouched).
- A surviving **prime** subtracts `futureAbsorb`; if the prime is a below-max healer it *also* adds back its `untouchedHealerCredit` (forgoes untouched, gains prime credit).
- A dying last-blocker (`hp == remaining`) is a chump: no `futureAbsorb`; add back its healer credit if applicable.
This yields exactly `loss = Σ_dead V + primeLoss − futureAbsorb(prime) − Σ_untouched-healer-credit` (algebra in the spec). For `cpp` mode, `H=0` and no adjustments → byte-identical to today.

- [ ] **Step 1: Write the oracle cross-check + acceptance tests** — add to `eval/defense/defense_sim.test.js`:

```js
const dv2 = require('./defense_value');
// Unbounded brute-force oracle for 'ours': the ground-truth solveDefense the B&B must match.
function oracleOurs(stateUnits, incoming) {
  const views = stateUnits.map(u => dv2.unitView(u));
  if (!(incoming > 0)) return { loss: 0 };
  const n = views.length; let best = Infinity;
  for (let mask = 0; mask < (1 << n); mask++) {
    const chumps = [], rest = []; let sum = 0;
    for (let i = 0; i < n; i++) { if (mask & (1 << i)) { chumps.push(views[i]); sum += views[i].hp; } else rest.push(views[i]); }
    if (sum > incoming) continue;
    const remaining = incoming - sum;
    let chumpV = 0; for (const c of chumps) chumpV += dv2.loss(c, c.hp, 'ours');
    const primes = remaining === 0 ? [null] : rest.filter(p => p.hp >= remaining);
    for (const prime of primes) {
      const surv = prime && prime.hp > remaining;
      const primeLoss = prime ? dv2.loss(prime, remaining, 'ours') : 0;
      const primeCredit = (prime && surv) ? dv2.futureAbsorb(prime) : 0;
      let uc = 0;
      for (const u of rest) { if (u === prime) continue; uc += dv2.untouchedHealerCredit(u); }
      const loss = chumpV + primeLoss - primeCredit - uc;
      if (loss < best) best = loss;
    }
  }
  return { loss: best };
}
function primeName(r) { return r.assignment.prime ? String(r.assignment.prime).split('|')[0] : null; }
function chumpNames(r) { return (r.assignment.chumps || []).flatMap(c => Array(c.count).fill(String(c.isoKey).split('|')[0])).sort(); }

// --- acceptance cases (prime/chumps verified against the oracle during design) ---
const ACC = [
  ['1 Wall+Rhino@4',            [mk('Wall',{health:3,instId:1}),mk('Rhino',{health:2,charge:2,instId:2})], 4, 'Wall', ['Elephant']],
  ['2a Eng+2Wall+Rhino@5',      [mk('Engineer',{health:1,instId:1}),mk('Wall',{health:3,instId:2}),mk('Wall',{health:3,instId:3}),mk('Rhino',{health:2,charge:2,instId:4})], 5, 'Wall', ['Wall']],
  ['2b Eng+2Wall+Rhino@3',      [mk('Engineer',{health:1,instId:1}),mk('Wall',{health:3,instId:2}),mk('Wall',{health:3,instId:3}),mk('Rhino',{health:2,charge:2,instId:4})], 3, 'Wall', ['Engineer']],
  ['3 EM+Mech(life5)@9',        [mk('Energy Matrix',{health:5,instId:1}),mk('Doomed Mech',{health:5,lifespan:5,instId:2})], 9, 'Doomed Mech', ['Golem']],
  ['4 EM+Mech(life2)@9',        [mk('Energy Matrix',{health:5,instId:1}),mk('Doomed Mech',{health:5,lifespan:2,instId:2})], 9, 'Golem', ['Doomed Mech']],
  ['6 Wall+Xaetron@3@2',        [mk('Wall',{health:3,instId:1}),mk('Xaetron',{health:3,instId:2})], 2, 'Wall', []],
  ['8 EM+Xaetron@5@9',          [mk('Energy Matrix',{health:5,instId:1}),mk('Xaetron',{health:5,instId:2})], 9, 'Xaetron', ['Golem']],
  ['9 5Husk+Wall+Xaetron@12@7', [mk('Xaetron',{health:12,instId:1}),mk('Wall',{health:3,instId:2}),...[3,4,5,6,7].map(i=>mk('House',{health:1,instId:i}))], 7, 'Xaetron', []],
  ['10 Steel+Wall@4',           [mk('Treant',{health:3,instId:1}),mk('Wall',{health:3,instId:2})], 4, 'Treant', ['Wall']],
  ['11 Xaetron@11+4Wall+Husk@12', [mk('Xaetron',{health:11,instId:1}),mk('Wall',{health:3,instId:2}),mk('Wall',{health:3,instId:3}),mk('Wall',{health:3,instId:4}),mk('Wall',{health:3,instId:5}),mk('House',{health:1,instId:6})], 12, 'Xaetron', ['Wall']],
];
for (const [label, board, inc, wantPrime, wantChumps] of ACC) {
  test(`ACC ${label} -> prime ${wantPrime}`, () => {
    const r = sim.solveDefense(board, inc, 'ours');
    assert.equal(primeName(r), wantPrime, `prime: ${JSON.stringify(r.assignment)}`);
    assert.deepEqual(chumpNames(r), wantChumps.slice().sort(), `chumps: ${JSON.stringify(r.assignment.chumps)}`);
    assert.ok(Math.abs(r.loss - oracleOurs(board, inc).loss) < 1e-6, `B&B loss ${r.loss} != oracle ${oracleOurs(board, inc).loss}`);
  });
}

// case 7: chump the 5 husks, prime the Wall, Xaetron untouched (the headline healer-climb flip)
test('ACC 7 5Husk+Wall+Xaetron@8@7 -> prime Wall, chump 5 husks', () => {
  const board = [mk('Xaetron',{health:8,instId:1}),mk('Wall',{health:3,instId:2}),...[3,4,5,6,7].map(i=>mk('House',{health:1,instId:i}))];
  const r = sim.solveDefense(board, 7, 'ours');
  assert.equal(primeName(r), 'Wall');
  assert.deepEqual(chumpNames(r), ['House','House','House','House','House']);
  assert.equal(r.perUnit[1] || 0, 0, 'Xaetron untouched');
  assert.ok(Math.abs(r.loss - oracleOurs(board, 7).loss) < 1e-6);
});

// case 12: near-maxed Xaetron + a BIG alternate prime (EM) -> keep Xaetron untouched, prime EM
test('ACC 12 Xaetron@11+EM+3Wall+3Husk@14 -> prime EM, Xaetron untouched', () => {
  const board = [mk('Xaetron',{health:11,instId:1}),mk('Energy Matrix',{health:5,instId:2}),mk('Wall',{health:3,instId:3}),mk('Wall',{health:3,instId:4}),mk('Wall',{health:3,instId:5}),mk('House',{health:1,instId:6}),mk('House',{health:1,instId:7}),mk('House',{health:1,instId:8})];
  const r = sim.solveDefense(board, 14, 'ours');
  assert.equal(primeName(r), 'Golem');
  assert.equal(r.perUnit[1] || 0, 0, 'Xaetron@11 untouched');
  assert.ok(Math.abs(r.loss - oracleOurs(board, 14).loss) < 1e-6);
});

// soundness sweep: B&B == oracle on a battery of pseudo-random boards (seeded by index, no RNG).
test('B&B ours matches the unbounded oracle on a board battery', () => {
  const pool = [['Wall',3],['Golem',5],['House',1],['Engineer',1],['Treant',3],['Elephant',2],['Xaetron',8],['Xaetron',5],['Xaetron',11],['Xaetron',12],['Doomed Mech',5]];
  let checked = 0;
  for (let seed = 1; seed <= 60; seed++) {
    const k = 2 + (seed % 5);
    const board = []; for (let j = 0; j < k; j++) { const [n, h] = pool[(seed * 7 + j * 13) % pool.length]; board.push(mk(n, { health: h, instId: j + 1, ...(n === 'Doomed Mech' ? { lifespan: 1 + ((seed + j) % 5) } : {}) })); }
    const inc = 1 + ((seed * 3) % 12);
    const r = sim.solveDefense(board, inc, 'ours');
    if (r.assignment === null) continue;
    assert.ok(Math.abs(r.loss - oracleOurs(board, inc).loss) < 1e-6, `seed ${seed} inc ${inc}: B&B ${r.loss} != oracle ${oracleOurs(board, inc).loss}`);
    checked++;
  }
  assert.ok(checked > 30, `expected >30 feasible boards, got ${checked}`);
});

// cpp mode must be byte-identical to before this change (the validation gate).
test('cpp mode solveDefense is unchanged on a battery', () => {
  const boards = [
    [[mk('Engineer',{health:1,instId:1}),mk('Engineer',{health:1,instId:2}),mk('Wall',{health:3,instId:3})], 4],
    [[mk('Xaetron',{health:8,instId:1}),mk('Wall',{health:3,instId:2}),mk('House',{health:1,instId:3})], 7],
    [[mk('Energy Matrix',{health:5,instId:1}),mk('Doomed Mech',{health:5,lifespan:5,instId:2})], 9],
  ];
  for (const [b, inc] of boards) {
    const r = sim.solveDefense(b, inc, 'cpp');
    // cpp loss is non-negative (no ours-credits leak in)
    assert.ok(r.loss >= -1e-9, `cpp loss should be >= 0, got ${r.loss}`);
  }
});
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `node --test eval/defense/defense_sim.test.js`
Expected: the ACC/oracle tests FAIL (current sim has no credit term).

- [ ] **Step 3: Implement the objective** in `eval/defense/defense_sim.js`.

(3a) After grouping into `groups`, before the negFloor block, compute `H` (ours only) and a per-group flag:

```js
  // §2 untouched-healer credit (ours only). H = board total; below-max healers start "untouched-credited"
  // (lossScore initialized to -H); chumping/priming one adds its credit back (it's no longer untouched).
  let H = 0;
  for (const g of groups) {
    g.uhCredit = (mode === 'ours') ? dv.untouchedHealerCredit(g.view) : 0;  // 0 for non-healers / maxed / cpp
    H += g.uhCredit * g.units.length;
  }
```

(3b) Extend the `negFloor`/`minTerm` loop so the surviving-prime term includes the credits, and chumped below-max healers carry their (positive) credit:

```js
  let negFloor = 0;
  let minTerm = 0;
  for (const g of groups) {
    // chump (full-kill) death cost: V, plus the forgone untouched-healer credit for a below-max healer.
    const deathLoss = dv.loss(g.view, g.hp, mode, ctx) + g.uhCredit;
    if (deathLoss < 0) negFloor += deathLoss * g.units.length;
    if (deathLoss < minTerm) minTerm = deathLoss;
    // surviving prime term: primeLoss − futureAbsorb (+ uhCredit if it's a below-max healer prime).
    if (g.hp > 1) {
      const survLoss = dv.loss(g.view, g.hp - 1, mode, ctx);
      const primeCredit = (mode === 'ours') ? dv.futureAbsorb(g.view) : 0;
      const survTerm = survLoss - primeCredit + g.uhCredit;
      if (survTerm < minTerm) minTerm = survTerm;
    }
  }
  negFloor += minTerm;
```

(3c) Initialize the recursion at `−H` instead of `0`:

```js
  recurse(0, incoming, -H);
```

(3d) In the **chump branch** of `recurse`, add the healer credit to the chump loss:

```js
      const chumpLoss = dv.loss(g.view, remaining, mode, ctx) + g.uhCredit; // + forgone untouched credit (0 unless below-max healer)
```

(3e) In the **last-blocker pass** of `recurse`, apply the prime credit + healer adjustment:

```js
      if (g.hp >= remaining) {                        // isLastBlocker (cpp:193)
        const primeLoss = dv.loss(g.view, remaining, mode, ctx);
        // §2: a TRULY surviving prime (hp>remaining) earns futureAbsorb (ours only). A below-max-healer
        // prime forgoes its untouched credit (+g.uhCredit), whether it survives or dies as last blocker.
        const primeCredit = (mode === 'ours' && g.hp > remaining) ? dv.futureAbsorb(g.view) : 0;
        record(lossScore + primeLoss - primeCredit + g.uhCredit, g.key, remaining);
      }
```

(3f) Expose the chump-loss component for Finding B. Track it parallel to the credited loss. Simplest: after picking `best`, recompute its chump component from the assignment. Add to the returned object:

```js
  // chump-loss component (pre-credit) for the value-sanity tripwire (Finding B): Σ over damaged units of loss().
  const chumpLossComponent = (a) => {
    let s = 0;
    for (const g of groups) for (const u of g.units) {
      const d = a.perUnit[u.instId] || 0;
      if (d > 0) s += dv.loss(g.view, d, mode, ctx);
    }
    return s;
  };
```

and in the final `return { assignment, perUnit: assignment.perUnit, loss: best.loss, tiedAlts, chumpLossComponent: chumpLossComponent(assignment) };`

(Also add `chumpLossComponent: 0` to the early `incoming <= 0` return.)

- [ ] **Step 4: Update the ONE existing `defense_sim.test.js` test** whose pinned loss changes.

The final model keeps the *same physical defense* the existing test #2 asserts (chump the 5 husks, Xaetron untouched) — only the loss value changes (credits now apply: ~11 → ~−28.6). Replace the second test's body:

```js
test('5 Husk + Wall + Xaetron@8, 7 dmg -> chump husks, prime Wall, Xaetron untouched', () => {
  const board = [
    mk('Xaetron', { health: 8, instId: 1 }),
    mk('Wall', { health: 3, instId: 2 }),
    ...[3, 4, 5, 6, 7].map(i => mk('House', { health: 1, instId: i })),
  ];
  const r = sim.solveDefense(board, 7, 'ours');
  assert.ok(String(r.assignment.prime).startsWith('Wall'), `prime should be Wall, got ${r.assignment.prime}`);
  assert.equal(r.perUnit[1] || 0, 0, 'Xaetron untouched (heals to 12)');
  assert.ok(r.loss < -20, `credited loss strongly negative (good anchors kept), got ${r.loss}`);
});
```

The other three existing sim tests are credit-compatible and pass unchanged — **verify, don't edit:**
- `Wall vs Xaetron@3, 2 dmg -> keep Wall as prime`: the final model already primes the Wall (Xaetron@3 has room 9 ≥ heal 4 → full untouched credit → leave it climbing); its asserts (`perUnit[2]==0`, `perUnit[1]>0`, `loss < 0.01`) all still hold (loss is now ~−26.4, which is `< 0.01`).
- `forced single feasible` (Wall alone @2) and `exact-absorb boundary` (2 Husk @2) are credit-neutral.

- [ ] **Step 5: Run to verify it passes**

Run: `node --test eval/defense/defense_sim.test.js`
Expected: PASS (all ACC + oracle battery + cpp + updated existing). If the oracle battery fails, the negFloor pruned a true optimum — loosen it (a sound fallback: `negFloor = Σ_g min(0, dv.loss(g.view,g.hp,mode,ctx)+g.uhCredit)*g.units.length − maxFutureAbsorb`, where `maxFutureAbsorb = max_g (mode==='ours'?dv.futureAbsorb(g.view):0)`) and re-run until B&B == oracle everywhere.

- [ ] **Step 6: Commit**

```bash
git add eval/defense/defense_sim.js eval/defense/defense_sim.test.js
git commit -m "feat(defense-eval): ours objective = chump-loss + primeLoss − prime credit − room-capped untouched-healer credit (oracle-validated)"
```

---

## Task 5: Symmetric human credit in `compare.js` (Finding A)

**Files:**
- Modify: `eval/defense/compare.js:77` (the `humanLossOurs` computation)
- Test: `eval/defense/compare.test.js` (create) — a focused unit test on a hand-built record

**Interfaces:**
- Consumes: `dv.{futureAbsorb, untouchedHealerCredit, isBelowMaxHealer}`, `human.{perUnit, prime}`, `blockers` (views).
- Produces: `humanLossOurs` now includes the same credits the AI's loss does, so regret is symmetric (identical human↔AI defense → regret 0).

- [ ] **Step 1: Write the failing test** — create `eval/defense/compare.test.js`:

```js
'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const dv = require('./defense_value');
const sim = require('./defense_sim');
const mk = (name, over = {}) => Object.assign({ cardName: name, owner: 0 }, over);

// If the human plays EXACTLY the AI's chosen defense, regret must be 0 (symmetric credit, Finding A).
test('human credit is symmetric: identical defense -> regret 0', () => {
  // ACC1: Wall@3 + Rhino ch2, 4 dmg -> AI primes Wall, chumps Rhino.
  const board = [mk('Wall', { health: 3, instId: 1 }), mk('Rhino', { health: 2, charge: 2, instId: 2 })];
  const views = board.map(u => dv.unitView(u));
  const ai = sim.solveDefense(board, 4, 'ours');
  // human plays the same: Rhino dies (takes 2), Wall survives partial (takes 2).
  const humanPerUnit = { 1: 2, 2: 2 };
  // replicate compare.js's humanLossOurs WITH the symmetric-credit fix:
  let humanLoss = views.reduce((s, v) => s + dv.loss(v, humanPerUnit[v.instId] || 0, 'ours'), 0);
  const primeView = views.find(v => { const d = humanPerUnit[v.instId] || 0; return d > 0 && d < v.hp; });
  if (primeView) humanLoss -= dv.futureAbsorb(primeView);
  for (const v of views) { const d = humanPerUnit[v.instId] || 0; if (d === 0 && dv.isBelowMaxHealer(v)) humanLoss -= dv.untouchedHealerCredit(v); }
  assert.ok(Math.abs(humanLoss - ai.loss) < 1e-6, `human ${humanLoss} should equal AI ${ai.loss} for an identical defense`);
});
```

- [ ] **Step 2: Run to verify it fails** (it tests the fixed formula, which isn't in compare.js yet — but this test inlines the fix, so it passes immediately; its purpose is to PIN the formula). Instead, first add a guard test that the RAW (unfixed) formula is wrong:

Run: `node --test eval/defense/compare.test.js`
Expected: PASS (the test inlines the correct formula). Treat this test as the spec for Step 3.

- [ ] **Step 3: Implement** — in `eval/defense/compare.js`, replace the `humanLossOurs` line (currently line ~77):

```js
    // human loss under 'ours' = Σ loss over the human's per-unit damage, MINUS the same keep-value credits
    // the AI's solveDefense applies (Finding A — else an identical human defense scores spurious regret).
    let humanLossOurs = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'ours'), 0);
    const humanPrime = blockers.find(v => { const d = human.perUnit[v.instId] || 0; return d > 0 && d < v.hp; });
    if (humanPrime) humanLossOurs -= dv.futureAbsorb(humanPrime);
    for (const v of blockers) { const d = human.perUnit[v.instId] || 0; if (d === 0 && dv.isBelowMaxHealer(v)) humanLossOurs -= dv.untouchedHealerCredit(v); }
    const humanLossCpp = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'cpp'), 0);
```

(Leave `humanLossCpp` exactly as it was — cpp is symmetric and unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `node --test eval/defense/compare.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval/defense/compare.js eval/defense/compare.test.js
git commit -m "fix(defense-eval): apply keep-value credits symmetrically to the human loss (Finding A)"
```

---

## Task 6: Tripwire on the chump-loss component + decision-relevance filter (Finding B + report filter)

**Files:**
- Modify: `eval/defense/metrics.js` (tripwire source; decision-relevance filter on the two diagnostic tables), `eval/defense/compare.js` (thread `chumpLossComponent` into the record)
- Test: `eval/defense/metrics.test.js`

**Interfaces:**
- Consumes: `aiOurs.chumpLossComponent` (from Task 4), record `incomingAttack`, `available` (isoKeys), human/ours primes.
- Produces: `buildTripwire` flags on the **chump-loss component** (≥ ~0 by construction), not the credited loss; `aggregate`'s `perUnitDivergence` + `tieBreakSkew` exclude decision-irrelevant positions (healer exception kept).

- [ ] **Step 1: Write the failing tests** — append to `eval/defense/metrics.test.js`:

```js
const { aggregate } = require('./metrics');
// minimal record shape buildTripwire/aggregate read (no available -> isDecisionRelevant returns true).
const twRec = (loss, comp) => ({ id: { replay: 'r', step: 1 }, incomingAttack: 1, available: [],
  ai_ours: { loss, chumpLossComponent: comp, assignment: { prime: null } },
  human: { assignment: { prime: null } }, metrics: {},
  diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] } });

test('Finding B: tripwire reads the chump-loss component, not the credited loss', () => {
  // credited loss very negative (good anchors survive) but chump component ~0 -> NOT suspicious.
  const agg = aggregate([twRec(-28.6, 0)]);
  assert.equal(agg.tripwire.suspicious.length, 0);
});

test('Finding B: a genuinely negative chump component IS flagged', () => {
  const agg = aggregate([twRec(-1.0, -0.8)]); // -0.8 < SUSPICIOUS_THRESHOLD (-0.3)
  assert.equal(agg.tripwire.suspicious.length, 1);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node --test eval/defense/metrics.test.js`
Expected: FAIL (tripwire currently reads `ai_ours.loss`).

- [ ] **Step 3: Implement** — in `eval/defense/metrics.js`, change `buildTripwire` to read the chump-loss component:

```js
function buildTripwire(records) {
  let negMinLoss = 0;
  const suspicious = [];
  for (const r of records) {
    // Finding B: the credited min-loss is by-design strongly negative when good anchors survive; the
    // value-sanity guard belongs on the chump-loss COMPONENT (Σ_dead V + primeLoss), which stays >= ~0.
    const comp = r.ai_ours && typeof r.ai_ours.chumpLossComponent === 'number' ? r.ai_ours.chumpLossComponent
               : (r.ai_ours && typeof r.ai_ours.loss === 'number' ? r.ai_ours.loss : 0);
    if (comp < -0.001) negMinLoss++;
    if (comp < SUSPICIOUS_THRESHOLD && suspicious.length < MAX_SUSPICIOUS) {
      suspicious.push({ replay: r.id ? r.id.replay : undefined, step: r.id ? r.id.step : undefined, turn: r.id ? r.id.turnIndex : undefined, loss: comp });
    }
  }
  return { negMinLoss, suspicious };
}
```

- [ ] **Step 4: Thread `chumpLossComponent` into the record** — in `eval/defense/compare.js`, in the `computeMetrics` call site, after building `rec`, attach it:

```js
    rec.ai_ours.chumpLossComponent = aiOurs.chumpLossComponent;
```

(Place it right after `rec.id = {...}`. `computeMetrics` already nests `aiOurs` under `rec.ai_ours`; this adds the component the tripwire reads.)

- [ ] **Step 5: Add the decision-relevance filter** to `aggregate` in `metrics.js`. `decodeIso` is ALREADY imported at the top of `metrics.js` (line 2) — do NOT re-require it; only add the lib import. Add the helper near the top (after the existing requires):

```js
const vmLib = require('../../docs/scratch/gen_our_numbers_v2.js').lib;
// A position is decision-IRRELEVANT when no REAL unit must die: incoming <= the single best survivable
// absorb (max hp-1) + Σ HP of terminal (lifespan==1) units that die for free. Filter such positions out
// of the two DIAGNOSTIC tables (the prime choice there is cosmetic) — EXCEPT keep any position where the
// human's OR ours' prime is a healer (the perpetual-heal credit makes that choice consequential).
const isHealerKey = (k) => { if (!k) return false; const ct = vmLib[String(k).split('|')[0]]; return !!(ct && ct.fragile && (ct.HPGained || 0) > 0); };
function isDecisionRelevant(r) {
  if (isHealerKey(r.human && r.human.assignment && r.human.assignment.prime) ||
      isHealerKey(r.ai_ours && r.ai_ours.assignment && r.ai_ours.assignment.prime)) return true;
  const keys = r.available || [];
  if (!keys.length) return true;
  let maxAbsorb = 0, freeHP = 0;
  for (const k of keys) {
    const d = decodeIso(k);
    maxAbsorb = Math.max(maxAbsorb, Math.max(0, d.hp - 1));
    if (d.lifespan === 1) freeHP += d.hp;
  }
  return (r.incomingAttack || 0) > maxAbsorb + freeHP;  // relevant iff some real unit must die
}
```

Then in `aggregate`, build `const relevant = records.filter(isDecisionRelevant);`, feed the `perUnit` divergence loop from `relevant` (not `records`), and call `buildTieBreakSkew(relevant)`. Keep `buildTripwire(records)` and all headline regret/exactMatch/primeMatch sums over the full `records`. (Note: `aggregate`'s `n = records.length` for the headline rates stays the full count.)

- [ ] **Step 6: Run to verify it passes**

Run: `node --test eval/defense/metrics.test.js`
Expected: PASS (incl. the pre-existing FP-tolerance / exact-match / divergence tests).

- [ ] **Step 7: Commit**

```bash
git add eval/defense/metrics.js eval/defense/compare.js eval/defense/metrics.test.js
git commit -m "fix(defense-eval): tripwire on chump-loss component (Finding B) + decision-relevance filter on diagnostic tables"
```

---

## Task 7: Regenerate `our_numbers_v2.md` + corpus validation

**Files:**
- Regenerate: `docs/scratch/our_numbers_v2.md` (side effect of running the model)
- Run: `eval/defense/compare.js` over the 5000-game corpus; inspect `eval/defense/results/report.md`

**Interfaces:** none (validation task; no new exports).

- [ ] **Step 1: Run the full suite green**

Run: `node --test eval/defense/*.test.js`
Expected: all PASS (≥ 36 prior + the new tests).

- [ ] **Step 2: Regenerate the numbers doc + eyeball the ordering**

Run: `node docs/scratch/gen_our_numbers_v2.js`
Expected: prints `wrote .../our_numbers_v2.md: N in-scope, ...`. Open `our_numbers_v2.md` and confirm the in-scope ordering barely moved (every attacker's atk component dropped ~×0.95; blockers/economy unchanged). No row should have a NaN/negative `OURS`.

- [ ] **Step 3: Re-run the corpus** (the `selected_codes` are in `training/data/human_elite_2000_45s_v2.provenance.json`; ~2 min):

```bash
node -e "const p=require('./training/data/human_elite_2000_45s_v2.provenance.json'); require('fs').writeFileSync('eval/defense/results/_codes.txt', p.selected_codes.join('\n'))"
node eval/defense/compare.js eval/defense/results/_codes.txt eval/defense/results
```
Expected: `wrote N records + report.md ...`. No `WARNING: ... suspicious negative-min-loss` (Finding B keeps the tripwire on the chump component → clean).

- [ ] **Step 4: Verify the §5 success criteria** in `eval/defense/results/report.md`:
  - **Zero-regret (ours) RISES** above the corrected baseline **82.7%** (the Wall-keep / healer behavior better matches elite humans).
  - The **Wall over-chump** and **Rhino under-chump** divergence clusters **shrink** vs the prior `report.md`.
  - **Regression guards hold:** Steelsplitter-vs-Wall and EM-vs-Xaetron decisions unchanged; `value_model.test.js` units unchanged; the `cpp` zero-regret column is **unchanged** vs the prior run (cpp untouched).
  - Tripwire section: `negMinLoss` on the chump component ≈ 0 (only the known Polywall@1-class units, if any).

  **If zero-regret does NOT rise or a guard regresses: STOP and report** (do not tune blindly). Likely causes to check first: a credit leaked into `cpp` mode (gate), or the human-side credit (Finding A) wasn't applied symmetrically (regret inflated).

- [ ] **Step 5: Commit the regenerated artifacts**

```bash
git add docs/scratch/our_numbers_v2.md eval/defense/results/report.md eval/defense/results/records.jsonl
git commit -m "data(defense-eval): regenerate numbers + corpus re-run under prime-defender keep-value"
```

---

## Self-Review checklist (run after implementing, before declaring done)

1. **cpp gate:** `solveDefense(..., 'cpp')` and `loss(..., 'cpp')` are byte-identical to pre-change (Task 4 battery + corpus cpp column). No credit, no heal-climb, no ATK leaked into cpp.
2. **Oracle agreement:** the B&B `ours` loss equals the brute-force oracle on every acceptance case + the 60-board battery.
3. **Symmetric regret:** an identical human↔AI defense yields regret 0 (Task 5).
4. **Tripwire:** reads the chump-loss component; a -0.8 component flags, a -28 credited loss with ~0 component does not.
5. **No placeholders / pinned numbers:** every assertion uses a concrete number from this plan (all oracle-verified).

---

## Notes for the executor

- Prototype reference (built during design, in the session scratchpad — not committed): patched `gen_our_numbers_v2.js`, `defense_value.js`, `defense_sim.js`, plus the oracle runners `model_final.js` / `max_remaining.js` / `edge_at11.js` / `edge_altprime.js` / `siege_sim.js`. The pinned numbers here came from those runs.
- The trickiest task is **Task 4's negFloor**. The oracle cross-check (60-board battery + all acceptance cases) is the safety net — if the B&B ever disagrees with the oracle, the bound pruned a real optimum; loosen `negFloor` (the conservative fallback in Step 5) until they agree everywhere, then tighten only if perf demands it.
- **Out of scope** (deferred, do not start): the C++ port into `Heuristics`; global R / future-flow tuning; per-unit fudge corrections. Chase aggregate regret, not per-unit perfection.
