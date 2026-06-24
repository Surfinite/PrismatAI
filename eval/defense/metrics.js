'use strict';
const { decodeIso } = require('./defense_value');

// UNIT-VALUE-KEY: the value-relevant subset of an isoKey — internal|hp|charge|lifespan.
// MERGES owner + chill + (already-dropped) status, so each unit appears once per distinct
// (hp, charge, lifespan) tuple. These are exactly the attributes that change a blocker's
// defensive value; nothing else may split a unit onto multiple report rows.
function unitValueKey(isoKey) {
  const d = decodeIso(isoKey);
  return [d.internal, d.hp, d.charge, d.lifespan].join('|');
}

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

const MAX_EXAMPLES = 5;          // per perUnit-key / per tie-break pair
const MAX_SUSPICIOUS = 10;       // tripwire suspicious-list cap

// Push a {replay, turn} citation onto a side's example list, deduped, capped at MAX_EXAMPLES.
function pushExample(list, rec) {
  if (!rec || !rec.id) return;
  if (list.length >= MAX_EXAMPLES) return;
  const ref = { replay: rec.id.replay, turn: rec.id.turnIndex };
  if (list.some(e => e.replay === ref.replay && e.turn === ref.turn)) return;
  list.push(ref);
}

function aggregate(records) {
  const n = records.length || 1;
  const sum = (f) => records.reduce((a, r) => a + f(r), 0);
  // perUnit keyed by UNIT-VALUE-KEY (internal|hp|charge|lifespan) — owner/chill/status merged.
  const perUnit = {}; // uvk -> { internal, hp, charge, lifespan, aiOnly, humanOnly, examplesAi[], examplesHuman[] }
  for (const r of records) {
    for (const k of r.diag.chumpDiff_ours.aiOnly) {
      const uvk = unitValueKey(k);
      const d = decodeIso(k);
      const e = (perUnit[uvk] = perUnit[uvk] || { internal: d.internal, hp: d.hp, charge: d.charge, lifespan: d.lifespan, aiOnly: 0, humanOnly: 0, examplesAi: [], examplesHuman: [] });
      e.aiOnly++;
      pushExample(e.examplesAi, r);
    }
    for (const k of r.diag.chumpDiff_ours.humanOnly) {
      const uvk = unitValueKey(k);
      const d = decodeIso(k);
      const e = (perUnit[uvk] = perUnit[uvk] || { internal: d.internal, hp: d.hp, charge: d.charge, lifespan: d.lifespan, aiOnly: 0, humanOnly: 0, examplesAi: [], examplesHuman: [] });
      e.humanOnly++;
      pushExample(e.examplesHuman, r);
    }
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
    perUnitDivergence: Object.values(perUnit)
      .sort((a, b) => (b.aiOnly + b.humanOnly) - (a.aiOnly + a.humanOnly)),
    tieBreakSkew: buildTieBreakSkew(records),
    tripwire: buildTripwire(records),
  };
}

function buildTieBreakSkew(records) {
  // pair-level: when ours ties >=2 primes, count which UNIT-VALUE-KEY the human chose.
  // Primes are isoKeys; collapse to unit-value-keys so owner/chill/status don't split pairs.
  const pairs = {}; // "P||Q" (unit-value-keys) -> { leans:{uvk:count}, decode:{uvk:{...}}, examples[] }
  for (const r of records) {
    const contrast = r.diag.tieBreakContrast || [];
    if (contrast.length < 2) continue;
    const chosenIso = r.human.assignment.prime;
    if (!chosenIso) continue;
    const chosen = unitValueKey(chosenIso);
    for (const altIso of contrast) {
      if (!altIso) continue;
      const alt = unitValueKey(altIso);
      if (alt === chosen) continue;
      const key = [chosen, alt].sort().join('||');
      const p = (pairs[key] = pairs[key] || { leans: {}, decode: {}, examples: [] });
      p.leans[chosen] = (p.leans[chosen] || 0) + 1;
      p.decode[chosen] = p.decode[chosen] || decodeIso(chosenIso);
      p.decode[alt] = p.decode[alt] || decodeIso(altIso);
      pushExample(p.examples, r);
    }
  }
  return Object.entries(pairs).map(([k, v]) => ({ pair: k, leans: v.leans, decode: v.decode, examples: v.examples }))
    .sort((a, b) => Object.values(b.leans).reduce((x, y) => x + y, 0) - Object.values(a.leans).reduce((x, y) => x + y, 0));
}

// TRIPWIRE — value-sanity standing guard. A min-loss should never be meaningfully negative;
// the only legitimate negative is the tiny doomed-last-turn nudge (~-0.10). A loss < -1 means
// the value layer is producing wrong (e.g. NEGATIVE-valued) units (cf. the lifespan -1 bug that
// made Tia Thurnax value -34.86). This self-flags such regressions on every corpus run.
function buildTripwire(records) {
  let negMinLoss = 0;
  const suspicious = [];
  for (const r of records) {
    const loss = r.ai_ours && typeof r.ai_ours.loss === 'number' ? r.ai_ours.loss : 0;
    if (loss < -0.001) negMinLoss++;
    if (loss < -1 && suspicious.length < MAX_SUSPICIOUS) {
      suspicious.push({ replay: r.id ? r.id.replay : undefined, turn: r.id ? r.id.turnIndex : undefined, loss });
    }
  }
  return { negMinLoss, suspicious };
}

module.exports = { computeMetrics, aggregate, sameAssignment, unitValueKey };
