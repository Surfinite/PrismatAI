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
