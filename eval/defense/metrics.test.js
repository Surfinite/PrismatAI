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
