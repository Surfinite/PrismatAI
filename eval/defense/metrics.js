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

// ② FP-dust band. The human loss is summed (instId order) and the sim sums the IDENTICAL physical
// assignment (DFS order); FP non-associativity makes a true 0-regret differ in the last ULP. Clamp
// sub-1e-9 regret to 0 so an exact physical match isn't counted as a phantom miss (this is well
// above FP dust ~1e-13 and far below any real regret, which is >= ~0.1).
const REGRET_EPS = 1e-9;
const clampRegret = (x) => (x < REGRET_EPS ? 0 : x);

// Tied-min-loss set for an AI solve, falling back to its single chosen assignment when tiedAlts is
// empty/absent (an empty array is truthy, so `|| fallback` alone short-circuits to []).
const tiedOrChosen = (ai) => (ai.tiedAlts && ai.tiedAlts.length) ? ai.tiedAlts : [{ assignment: ai.assignment }];

// per-iso-class chump counts (multiset) for an assignment.
function chumpCounts(assignment) {
  const m = new Map();
  for (const c of (assignment.chumps || [])) m.set(c.isoKey, (m.get(c.isoKey) || 0) + c.count);
  return m;
}

function computeMetrics({ board, incoming, human, aiOurs, aiCpp }) {
  // ② FP-tolerant regret (both modes).
  const regret_ours = clampRegret(Math.max(0, human.humanLoss - aiOurs.loss));
  const regret_cpp = clampRegret(Math.max(0, (human.humanLoss_cpp || 0) - aiCpp.loss));

  // ③ SYMMETRIC exact-match: human's assignment ∈ the tied-min-loss set, for BOTH modes. cpp's tied
  // set is produced by its own solveDefense; previously only ours used the tied set while cpp used
  // its single chosen assignment — crediting ours matches the cpp metric structurally could not earn.
  const exactMatch_ours = tiedOrChosen(aiOurs).some(t => sameAssignment(human.assignment, t.assignment));
  const exactMatch_cpp = tiedOrChosen(aiCpp).some(t => sameAssignment(human.assignment, t.assignment));
  const primeMatch_ours = (human.assignment.prime || null) === (aiOurs.assignment.prime || null);
  const primeMatch_cpp = (human.assignment.prime || null) === (aiCpp.assignment.prime || null);

  // ④ MULTISET-aware divergence: per iso-class, the EXCESS each side chumps over the other (NOT a
  // set-difference, which censored any class both sides chump at different counts — e.g. AI 5
  // Engineers vs human 2 was invisible to both sides). aiOnly/humanOnly carry the excess with
  // multiplicity so the aggregate sums true magnitudes.
  const hC = chumpCounts(human.assignment), aC = chumpCounts(aiOurs.assignment);
  const aiOnly = [], humanOnly = [];
  for (const k of new Set([...hC.keys(), ...aC.keys()])) {
    const a = aC.get(k) || 0, h = hC.get(k) || 0;
    for (let i = 0; i < a - h; i++) aiOnly.push(k);     // a-h<=0 -> no iterations
    for (let i = 0; i < h - a; i++) humanOnly.push(k);
  }

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
    ai_cpp: { assignment: aiCpp.assignment, loss: aiCpp.loss, tiedAltsWithinEps: aiCpp.tiedAlts },
    metrics: { regret_ours, regret_cpp, exactMatch_ours, exactMatch_cpp, primeMatch_ours, primeMatch_cpp },
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
// the only legitimate negatives are tiny doomed-nudge effects (~-0.10 band). A loss < -0.3 means
// the value layer is producing wrong (e.g. NEGATIVE-valued) units (cf. the lifespan -1 bug that
// made Tia Thurnax value -34.86). Threshold tightened from -1 to -0.3 (clear of the legitimate
// ~-0.1 doomed-nudge band) so future value-layer regressions surface. NOTE: a Polywall@1 chump
// (~-0.8) is the one known unit below this band — it's the same negative-keep-value class, flagged
// for a look, not necessarily a regression. This self-flags regressions on every corpus run.
const SUSPICIOUS_THRESHOLD = -0.3;
function buildTripwire(records) {
  let negMinLoss = 0;
  const suspicious = [];
  for (const r of records) {
    const loss = r.ai_ours && typeof r.ai_ours.loss === 'number' ? r.ai_ours.loss : 0;
    if (loss < -0.001) negMinLoss++;
    if (loss < SUSPICIOUS_THRESHOLD && suspicious.length < MAX_SUSPICIOUS) {
      suspicious.push({ replay: r.id ? r.id.replay : undefined, turn: r.id ? r.id.turnIndex : undefined, loss });
    }
  }
  return { negMinLoss, suspicious };
}

module.exports = { computeMetrics, aggregate, sameAssignment, unitValueKey };
