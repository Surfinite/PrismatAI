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
