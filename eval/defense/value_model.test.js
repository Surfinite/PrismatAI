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
  // NOTE: the library is keyed by INTERNAL names (cf. the regression test above using
  // 'Wall'/'Golem'/'House'); the Doomed Wall unit's internal key is 'Doomwall'
  // (UIName "Doomed Wall"). The brief's display-name key 'Doomed Wall' is not a lib key.
  const dw = vm.ours(vm.lib['Doomwall']).v;
  // ch0-Bombarder body == 8.8 (via the Task-3 stateOverride { charge: 0 }); a fresh Doomed Wall
  // sits just below it, still near its own body floor (not heavily discounted).
  assert.ok(dw < 8.8 && dw > 8.0, `Doomed Wall (${dw}) should be just below ch0-Bombarder body 8.8 and near its own body floor`);
});

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

test('§3a multi-turn heal climb (discounted, capped at max)', () => {
  const near = (a, b) => Math.abs(a - b) < 0.02;
  // Xaetron heal 4 max 12, fragile (-0.1 haircut). @5: 5 + 4*.75 + 3*.5625 = 9.6875 -> *2.2 - 0.1 = 21.21
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 5 }).block, 21.21), `@5 got ${vm.ours(vm.lib['Xaetron'], { hp: 5 }).block}`);
  // @2: 2 + 4*.75 + 4*.5625 + 2*.4219 = 8.06 -> 17.71
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 2 }).block, 17.71), `@2 got ${vm.ours(vm.lib['Xaetron'], { hp: 2 }).block}`);
  // @8 (room 4 = one full heal then capped): 8 + 4*.75 = 11 -> 24.1
  assert.ok(near(vm.ours(vm.lib['Xaetron'], { hp: 8 }).block, 24.1), `@8 got ${vm.ours(vm.lib['Xaetron'], { hp: 8 }).block}`);
});
