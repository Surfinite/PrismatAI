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

// isoKey field order: internal|owner|hp|chill|charge|delay|ctime|life|dead
const ISO_WALL3 = 'Wall|0|3|0|0|0|0|-1|0';
const ISO_HOUSE1 = 'House|0|1|0|0|0|0|-1|0';

test('aggregate: mean regret + zero-regret rate', () => {
  const recs = [
    { id: { replay: 'AAA', turnIndex: 1 }, ai_ours: { loss: 5 }, metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
    { id: { replay: 'BBB', turnIndex: 2 }, ai_ours: { loss: 9 }, metrics: { regret_ours: 4, exactMatch_ours: false, primeMatch_ours: false }, diag: { chumpDiff_ours: { aiOnly: [ISO_WALL3], humanOnly: [ISO_HOUSE1] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
  ];
  const agg = m.aggregate(recs);
  assert.equal(agg.regret.mean_ours, 2);
  assert.equal(agg.regret.zeroRate_ours, 0.5);
});

test('unitValueKey merges owner/chill/status; keeps hp/charge/lifespan', () => {
  // same Wall@3 differing only in owner (1 vs 0) and chill (2 vs 0) -> one unit-value-key
  assert.equal(m.unitValueKey('Wall|1|3|2|0|0|0|-1|0'), m.unitValueKey('Wall|0|3|0|0|0|0|-1|0'));
  // differing HP -> different keys
  assert.notEqual(m.unitValueKey('Wall|0|3|0|0|0|0|-1|0'), m.unitValueKey('Wall|0|2|0|0|0|0|-1|0'));
});

test('aggregate: perUnitDivergence aggregates by unit-value-key with attrs + citations', () => {
  const recs = [
    { id: { replay: 'C1', turnIndex: 3, step: 30 }, ai_ours: { loss: 4 }, metrics: { regret_ours: 1, exactMatch_ours: false, primeMatch_ours: false }, diag: { chumpDiff_ours: { aiOnly: [ISO_WALL3], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
    // owner-different Wall@3 must MERGE into the same row as ISO_WALL3
    { id: { replay: 'C2', turnIndex: 4, step: 40 }, ai_ours: { loss: 4 }, metrics: { regret_ours: 1, exactMatch_ours: false, primeMatch_ours: false }, diag: { chumpDiff_ours: { aiOnly: ['Wall|1|3|0|0|0|0|-1|0'], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
  ];
  const agg = m.aggregate(recs);
  assert.equal(agg.perUnitDivergence.length, 1);            // merged -> ONE row
  const row = agg.perUnitDivergence[0];
  assert.equal(row.internal, 'Wall');
  assert.equal(row.hp, 3);
  assert.equal(row.aiOnly, 2);
  // citations carry the begin-of-defense step (turn kept as fallback)
  assert.deepEqual(row.examplesAi, [{ replay: 'C1', step: 30, turn: 3 }, { replay: 'C2', step: 40, turn: 4 }]);
});

test('aggregate: tripwire flags suspicious negative min-loss', () => {
  const recs = [
    { id: { replay: 'D1', turnIndex: 1 }, ai_ours: { loss: -0.05 }, metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
    { id: { replay: 'D2', turnIndex: 2 }, ai_ours: { loss: -34.86 }, metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
  ];
  const agg = m.aggregate(recs);
  assert.equal(agg.tripwire.negMinLoss, 2);                 // both < -0.001
  assert.equal(agg.tripwire.suspicious.length, 1);          // only the suspicious one
  assert.equal(agg.tripwire.suspicious[0].replay, 'D2');
});

test('② FP-dust regret clamps to 0; a real small regret survives', () => {
  const dust = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 11 + 1e-12, assignment: { prime: 'A', chumps: [] } },
    aiOurs: { loss: 11, assignment: { prime: 'A', chumps: [] }, tiedAlts: [] },
    aiCpp: { loss: 11, assignment: { prime: 'A', chumps: [] } },
  });
  assert.equal(dust.metrics.regret_ours, 0);                // 1e-12 dust -> 0, not a phantom miss
  const real = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 11.05, assignment: { prime: 'A', chumps: [] } },
    aiOurs: { loss: 11, assignment: { prime: 'A', chumps: [] }, tiedAlts: [] },
    aiCpp: { loss: 11, assignment: { prime: 'A', chumps: [] } },
  });
  assert.ok(Math.abs(real.metrics.regret_ours - 0.05) < 1e-9);  // real regret unaffected
});

test('③ exact-match is symmetric: cpp uses its tied-min-loss set too', () => {
  const rec = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 11, humanLoss_cpp: 11, assignment: { prime: 'B', chumps: [] } },
    aiOurs: { loss: 11, assignment: { prime: 'A', chumps: [] }, tiedAlts: [] },
    // cpp chose A but B is a tied alternative -> symmetric metric must credit the match
    aiCpp: { loss: 11, assignment: { prime: 'A', chumps: [] },
      tiedAlts: [{ assignment: { prime: 'A', chumps: [] } }, { assignment: { prime: 'B', chumps: [] } }] },
  });
  assert.equal(rec.metrics.exactMatch_cpp, true);           // old single-chosen (A) would be false
});

test('④ divergence counts same-class excess (multiset, not set-diff)', () => {
  const rec = m.computeMetrics({
    board: [], incoming: 5,
    human: { humanLoss: 5, assignment: { prime: 'P', chumps: [{ isoKey: 'Eng', count: 2 }] } },
    aiOurs: { loss: 5, assignment: { prime: 'P', chumps: [{ isoKey: 'Eng', count: 5 }] }, tiedAlts: [] },
    aiCpp: { loss: 5, assignment: { prime: 'P', chumps: [] } },
  });
  // both chump Eng (AI 5, human 2) -> AI excess 3, formerly censored by the set-difference
  assert.equal(rec.diag.chumpDiff_ours.aiOnly.filter(k => k === 'Eng').length, 3);
  assert.equal(rec.diag.chumpDiff_ours.humanOnly.length, 0);
});

test('tripwire threshold -0.3: a -0.5 min-loss is suspicious, a -0.1 is not', () => {
  const recs = [
    { id: { replay: 'E1', turnIndex: 1 }, ai_ours: { loss: -0.1 }, metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
    { id: { replay: 'E2', turnIndex: 2 }, ai_ours: { loss: -0.5 }, metrics: { regret_ours: 0, exactMatch_ours: true, primeMatch_ours: true }, diag: { chumpDiff_ours: { aiOnly: [], humanOnly: [] }, tieBreakContrast: [] }, human: { assignment: {} }, tags: [] },
  ];
  const agg = m.aggregate(recs);
  assert.equal(agg.tripwire.negMinLoss, 2);
  assert.equal(agg.tripwire.suspicious.length, 1);
  assert.equal(agg.tripwire.suspicious[0].replay, 'E2');
});
