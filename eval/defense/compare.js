'use strict';
const fs = require('fs'); const path = require('path');
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { loadJSON, buildInitInfo } = require('../replay_to_request');
const cap = require('./state_b_capture');
const sim = require('./defense_sim');
const dv = require('./defense_value');
const metrics = require('./metrics');
const { renderReport } = require('./report');
const { availableBlockers } = require('./blockers'); // shared canBlock-faithful filter (must match validate_gate.js)
const { find } = require('./_find_replay'); // tiny archive lookup helper (Task 8)

const ARCHIVE = 'c:/libraries/prismata-replay-parser/replays_archive';

// State-A: begin-of-defense states keyed by turnIndex (the AI input).
// beginTurnHistory[i] is the begin-state of turn i (Analyzer pushes it in lockstep
// with ++turnIndex), so the index i IS the turnIndex namespace that state_b_capture
// keys its committed defenses by (prevTurnIndex == analyzer.turnIndex at swoosh).
function stateAByTurn(replay) {
  const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
  analyzer.loaderInit();
  const out = new Map(); // turnIndex -> gameState
  analyzer.beginTurnHistory.forEach((st, i) => {
    const gs = replay_exporter.stateToCppJSON(st);
    if (gs.phase === 'defense' && ((gs.incomingAttack | 0) > 0)) out.set(i, gs);
  });
  return out;
}

// availableBlockers — the active player's available (blockable) units. Now the SHARED
// canBlock-faithful filter (imported from ./blockers), so this harness solves defense on
// exactly the unit set validate_gate.js validates (was a permissive owner/alive/
// constructionTime/delay-only filter that admitted non-blocking Drones/economy/tech units).

function humanAssignment(committedGS, player, board) {
  const perUnit = {}; const chumps = []; let prime = null; const untouched = [];
  const byId = new Map(board.map(b => [b.instId, b]));
  for (const u of (committedGS.table || [])) {
    if (u.owner !== player) continue;
    // State-B per-unit damage is carried under `damage` (Task 9 contract); there is no
    // `damageTaken` field. Reading the wrong field would classify EVERYTHING as untouched.
    const taken = (u.damage | 0);
    const view = byId.get(u.instId); if (!view) continue;
    perUnit[u.instId] = taken;
    const k = dv.isoKey(view);
    if (taken >= view.hp || (u.deadness && u.deadness !== 'alive')) chumps.push(k);
    else if (taken > 0) prime = k;          // the single partial-damage survivor
    else untouched.push(k);
  }
  // collapse chumps/untouched into {isoKey,count}
  const tally = arr => Object.entries(arr.reduce((m, k) => ((m[k] = (m[k] || 0) + 1), m), {})).map(([isoKey, count]) => ({ isoKey, count }));
  return { perUnit, chumps: tally(chumps), prime, untouched: tally(untouched) };
}

// Build the per-position records for ONE replay code. Returns an array of records.
// Pure compute over the loaded replay; no I/O. Throws on a faithful-failure / parse error.
function recordsForCode(code) {
  const replay = loadJSON(find(ARCHIVE, code));
  const stateA = stateAByTurn(replay);
  const committed = cap.captureCommittedDefenses(replay);
  const out = [];
  for (const c of committed) {
    const gsA = stateA.get(c.turnIndex); if (!gsA) continue;   // only attacked turns
    const player = c.player;
    const incoming = gsA.incomingAttack | 0;
    const rawBlockers = availableBlockers(gsA, player);
    const blockers = rawBlockers.map(u => dv.unitView(u));
    if (!blockers.length) continue;

    const aiOurs = sim.solveDefense(rawBlockers, incoming, 'ours');
    const aiCpp = sim.solveDefense(rawBlockers, incoming, 'cpp');
    if (!aiOurs.assignment || !aiCpp.assignment) continue;      // breach -> skip (spec §9)

    const human = humanAssignment(c.gameState, player, blockers);
    // human loss under 'ours' = Σ loss over the human's per-unit damage, MINUS the same keep-value credits
    // the AI's solveDefense applies (Finding A — else an identical human defense scores spurious regret).
    let humanLossOurs = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'ours'), 0);
    const humanPrime = blockers.find(v => { const d = human.perUnit[v.instId] || 0; return d > 0 && d < v.hp; });
    if (humanPrime) humanLossOurs -= dv.futureAbsorb(humanPrime);
    for (const v of blockers) { const d = human.perUnit[v.instId] || 0; if (d === 0 && dv.isBelowMaxHealer(v)) humanLossOurs -= dv.untouchedHealerCredit(v); }
    const humanLossCpp = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'cpp'), 0);

    const rec = metrics.computeMetrics({
      board: blockers.map(b => ({ isoKey: dv.isoKey(b) })), incoming,
      human: { assignment: human, humanLoss: humanLossOurs, humanLoss_cpp: humanLossCpp },
      aiOurs, aiCpp,
    });
    rec.id = { replay: code, turnIndex: c.turnIndex, player, step: c.step };
    rec.tags = [];
    if ((gsA.table || []).some(u => (u.disruptDamage | 0) > 0)) rec.tags.push('chillPresent');
    if (aiOurs.tiedAlts.length <= 1 && blockers.length <= 2) rec.tags.push('forced');
    out.push(rec);
  }
  return out;
}

function main() {
  const [codesFile, outDir] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const codes = fs.readFileSync(codesFile, 'utf-8').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const records = [];
  const recStream = fs.createWriteStream(path.join(outDir, 'records.jsonl'));
  let skipped = 0;

  // In-process per-replay extraction. State-B capture no longer deep-clones the whole board on
  // every click (it navigates via endDefenses/gotoCommand), removing the per-click-snapshot OOM
  // that motivated the old per-replay subprocess isolation. A try/catch per code skips (and counts)
  // a bad replay so one faithful-failure / parse error doesn't abort the whole corpus run.
  // NOTE: a JS throw is caught here, but a true V8 heap OOM aborts the process and CANNOT be caught
  // in-process. The remaining heavy consumer is defense_sim.solveDefense (its combinatorial solution
  // enumeration), not State-B capture; a handful of dev replays can still OOM it. If that recurs on a
  // corpus run, bound solveDefense rather than re-adding the subprocess workaround (see rework report).
  for (const code of codes) {
    let recs;
    try {
      recs = recordsForCode(code);
    } catch (e) {
      process.stderr.write(`skip ${code}: ${e && e.message ? e.message : e}\n`);
      skipped++;
      continue;
    }
    for (const rec of recs) {
      records.push(rec);
      recStream.write(JSON.stringify(rec) + '\n');
    }
  }
  recStream.end();
  const agg = metrics.aggregate(records);
  fs.writeFileSync(path.join(outDir, 'report.md'), renderReport(agg));
  // Value-sanity tripwire: a suspicious negative min-loss is a strong signal of a value-layer
  // bug (e.g. the lifespan -1 bug that gave Tia Thurnax value -34.86). Flag it prominently so
  // future regressions self-announce on every corpus run.
  if (agg.tripwire && agg.tripwire.suspicious.length > 0) {
    process.stderr.write(`WARNING: ${agg.tripwire.suspicious.length} suspicious negative-min-loss positions (possible value-layer bug) — see report tripwire section\n`);
  }
  process.stdout.write(`wrote ${records.length} records + report.md to ${outDir} (skipped ${skipped} codes)\n`);
}

if (require.main === module) main();

module.exports = { recordsForCode, stateAByTurn, availableBlockers, humanAssignment };
