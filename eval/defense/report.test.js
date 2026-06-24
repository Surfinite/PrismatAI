'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const { renderReport } = require('./report');

test('renderReport includes regret and divergence sections', () => {
  const md = renderReport({
    n: 100,
    regret: { mean_ours: 0.4, zeroRate_ours: 0.82, mean_cpp: 1.1, zeroRate_cpp: 0.6 },
    exactMatch: { ours: 0.55, cpp: 0.4 }, primeMatch: { ours: 0.7, cpp: 0.5 },
    perUnitDivergence: [{ internal: 'Hotel', hp: 4, charge: 0, lifespan: -1, aiOnly: 3, humanOnly: 12, examplesAi: [{ replay: 'AAA', turn: 5 }], examplesHuman: [{ replay: 'BBB', turn: 7 }] }],
    tieBreakSkew: [{ pair: 'Wall|3|0|-1||House|1|0|-1', leans: { 'Wall|3|0|-1': 20 }, decode: { 'Wall|3|0|-1': { internal: 'Wall', hp: 3, charge: 0, lifespan: -1 }, 'House|1|0|-1': { internal: 'House', hp: 1, charge: 0, lifespan: -1 } }, examples: [{ replay: 'CCC', turn: 9 }] }],
    tripwire: { negMinLoss: 0, suspicious: [] },
  });
  assert.match(md, /Regret/);
  assert.match(md, /zero-regret/i);
  assert.match(md, /Per-unit divergence/i);
  assert.match(md, /Tie-break skew/i);
  assert.match(md, /Tripwire/i);
  // display name (not codename) + citation rendered
  assert.match(md, /Infusion Grid/);
  assert.match(md, /AAA@t5/);
  assert.doesNotMatch(md, /\bHotel\b/);          // codename never shown
  assert.match(md, /0 suspicious \(clean\)/);
});
