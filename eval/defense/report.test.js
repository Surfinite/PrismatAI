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
