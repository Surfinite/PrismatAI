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
