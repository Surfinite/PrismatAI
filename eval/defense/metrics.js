'use strict';

function sameAssignment(a, b) {
  if (!a || !b) return false;
  const norm = x => JSON.stringify({
    prime: x.prime || null,
    chumps: (x.chumps || []).slice().sort((p, q) => (p.isoKey > q.isoKey ? 1 : -1)),
  });
  return norm(a) === norm(b);
}

function computeMetrics({ board, incoming, human, aiOurs, aiCpp }) {
  const regret_ours = Math.max(0, human.humanLoss - aiOurs.loss);
  // §7.1 exact-match: human's assignment ∈ {ai's tied-min-loss assignments}.
  // When tiedAlts is empty/absent, fall back to the single chosen assignment
  // (an empty array is truthy, so `|| fallback` alone would short-circuit to []).
  const tiedAltsOurs = (aiOurs.tiedAlts && aiOurs.tiedAlts.length)
    ? aiOurs.tiedAlts
    : [{ assignment: aiOurs.assignment }];
  const exactMatch_ours = tiedAltsOurs
    .some(t => sameAssignment(human.assignment, t.assignment));
  const exactMatch_cpp = sameAssignment(human.assignment, aiCpp.assignment);
  const primeMatch_ours = (human.assignment.prime || null) === (aiOurs.assignment.prime || null);
  const primeMatch_cpp = (human.assignment.prime || null) === (aiCpp.assignment.prime || null);

  // per-unit chump divergence (iso-class symmetric difference)
  const humanChumps = new Set((human.assignment.chumps || []).flatMap(c => Array(c.count).fill(c.isoKey)));
  const aiChumps = new Set((aiOurs.assignment.chumps || []).flatMap(c => Array(c.count).fill(c.isoKey)));
  const aiOnly = [...aiChumps].filter(k => !humanChumps.has(k));
  const humanOnly = [...humanChumps].filter(k => !aiChumps.has(k));

  // tie-break contrast: when there are tied alternatives and human chose a tied one, log the prime-class contrast
  const tieBreakContrast = (aiOurs.tiedAlts && aiOurs.tiedAlts.length > 1)
    ? aiOurs.tiedAlts.map(t => t.assignment.prime).filter((v, i, a) => a.indexOf(v) === i)
    : [];

  return {
    id: { /* filled by compare.js: replay, turn, player */ },
    incomingAttack: incoming,
    available: board.map(b => b.isoKey).filter(Boolean),
    human: { assignment: human.assignment, loss_ours: human.humanLoss },
    ai_ours: { assignment: aiOurs.assignment, loss: aiOurs.loss, tiedAltsWithinEps: aiOurs.tiedAlts },
    ai_cpp: { assignment: aiCpp.assignment, loss: aiCpp.loss },
    metrics: { regret_ours, regret_cpp: Math.max(0, (human.humanLoss_cpp || 0) - aiCpp.loss), exactMatch_ours, exactMatch_cpp, primeMatch_ours, primeMatch_cpp },
    diag: { chumpDiff_ours: { aiOnly, humanOnly }, tieBreakContrast },
    tags: [],
  };
}

function aggregate(records) {
  const n = records.length || 1;
  const sum = (f) => records.reduce((a, r) => a + f(r), 0);
  const regrets = records.map(r => r.metrics.regret_ours);
  const perUnit = {}; // isoKey -> {aiChumpedMore, humanChumpedMore}
  for (const r of records) {
    for (const k of r.diag.chumpDiff_ours.aiOnly) (perUnit[k] = perUnit[k] || { aiOnly: 0, humanOnly: 0 }).aiOnly++;
    for (const k of r.diag.chumpDiff_ours.humanOnly) (perUnit[k] = perUnit[k] || { aiOnly: 0, humanOnly: 0 }).humanOnly++;
  }
  return {
    n: records.length,
    regret: {
      mean_ours: sum(r => r.metrics.regret_ours) / n,
      zeroRate_ours: sum(r => (r.metrics.regret_ours === 0 ? 1 : 0)) / n,
      mean_cpp: sum(r => r.metrics.regret_cpp) / n,
      zeroRate_cpp: sum(r => (r.metrics.regret_cpp === 0 ? 1 : 0)) / n,
    },
    exactMatch: { ours: sum(r => (r.metrics.exactMatch_ours ? 1 : 0)) / n, cpp: sum(r => (r.metrics.exactMatch_cpp ? 1 : 0)) / n },
    primeMatch: { ours: sum(r => (r.metrics.primeMatch_ours ? 1 : 0)) / n, cpp: sum(r => (r.metrics.primeMatch_cpp ? 1 : 0)) / n },
    perUnitDivergence: Object.entries(perUnit).map(([k, v]) => ({ isoKey: k, ...v }))
      .sort((a, b) => (b.aiOnly + b.humanOnly) - (a.aiOnly + a.humanOnly)),
    tieBreakSkew: buildTieBreakSkew(records),
  };
}

function buildTieBreakSkew(records) {
  // pair-level: when ours ties >=2 primes, count which the human chose
  const pairs = {}; // "P|Q" -> {P:count, Q:count}
  for (const r of records) {
    const contrast = r.diag.tieBreakContrast || [];
    if (contrast.length < 2) continue;
    const chosen = r.human.assignment.prime;
    for (const alt of contrast) {
      if (alt === chosen) continue;
      const key = [chosen, alt].sort().join('||');
      pairs[key] = pairs[key] || {};
      pairs[key][chosen] = (pairs[key][chosen] || 0) + 1;
    }
  }
  return Object.entries(pairs).map(([k, v]) => ({ pair: k, leans: v }))
    .sort((a, b) => Object.values(b.leans).reduce((x, y) => x + y, 0) - Object.values(a.leans).reduce((x, y) => x + y, 0));
}

module.exports = { computeMetrics, aggregate, sameAssignment };
