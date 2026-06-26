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

test('forced single feasible set is tagged via tiedAlts length 1', () => {
  const board = [mk('Wall', { health: 3, instId: 1 })];
  const r = sim.solveDefense(board, 2, 'ours'); // only one unit can be prime
  assert.equal(r.tiedAlts.length <= 1, true);
});

test('exact-absorb boundary: 2x Husk@1 vs 2 -> both chump, prime null (no survivor)', () => {
  // House (internal "Husk") @1 hp each, 2 incoming. Both die exactly absorbing the
  // incoming; no unit survives partial damage, so prime MUST be null and both are chumps.
  const board = [mk('House', { health: 1, instId: 1 }), mk('House', { health: 1, instId: 2 })];
  const r = sim.solveDefense(board, 2, 'ours');
  assert.equal(r.assignment.prime, null, 'no surviving partial-damage unit -> prime must be null');
  const chumpTotal = r.assignment.chumps.reduce((n, c) => n + c.count, 0);
  assert.equal(chumpTotal, 2, 'both husks must be classified as chumps');
  assert.equal(r.perUnit[1], 1, 'husk 1 took its full 1 hp (dead)');
  assert.equal(r.perUnit[2], 1, 'husk 2 took its full 1 hp (dead)');
});

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
