'use strict';
const fs = require('fs'); const path = require('path');
const cp = require('child_process');
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { loadJSON, buildInitInfo } = require('../replay_to_request');
const cap = require('./state_b_capture');
const sim = require('./defense_sim');
const dv = require('./defense_value');
const metrics = require('./metrics');
const { renderReport } = require('./report');
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

// active player's available (blockable) units from a gameState.
function availableBlockers(gs, player) {
  return (gs.table || []).filter(u =>
    u.owner === player && (u.deadness === undefined || u.deadness === 'alive')
    && (u.constructionTime | 0) === 0 && !((u.delay | 0) > 0));
}

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
    // human loss under each mode = Σ loss over the human's per-unit damage
    const humanLossOurs = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'ours'), 0);
    const humanLossCpp = blockers.reduce((s, v) => s + dv.loss(v, human.perUnit[v.instId] || 0, 'cpp'), 0);

    const rec = metrics.computeMetrics({
      board: blockers.map(b => ({ isoKey: dv.isoKey(b) })), incoming,
      human: { assignment: human, humanLoss: humanLossOurs, humanLoss_cpp: humanLossCpp },
      aiOurs, aiCpp,
    });
    rec.id = { replay: code, turnIndex: c.turnIndex, player };
    rec.tags = [];
    if ((gsA.table || []).some(u => (u.disruptDamage | 0) > 0)) rec.tags.push('chillPresent');
    if (aiOurs.tiedAlts.length <= 1 && blockers.length <= 2) rec.tags.push('forced');
    out.push(rec);
  }
  return out;
}

// Worker mode: `compare.js --one <code>` prints this code's records as JSONL on stdout.
// Run per-replay in a child process so a single pathological replay (some long/undo-heavy
// games blow the V8 heap inside Analyzer's per-click snapshotting) is ISOLATED — its crash
// is skipped by the parent instead of killing the whole corpus run.
function runOne() {
  const code = process.argv[3];
  for (const rec of recordsForCode(code)) process.stdout.write(JSON.stringify(rec) + '\n');
}

function main() {
  const [codesFile, outDir] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const codes = fs.readFileSync(codesFile, 'utf-8').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const records = [];
  const recStream = fs.createWriteStream(path.join(outDir, 'records.jsonl'));
  let skipped = 0;

  for (const code of codes) {
    // Run the per-replay extraction in an isolated child (bounded heap; one crash != run abort).
    // Cap the child heap so a pathological replay fails FAST (skipped) instead of thrashing GC.
    const r = cp.spawnSync(process.execPath, ['--max-old-space-size=2048', __filename, '--one', code],
      { encoding: 'utf-8', maxBuffer: 256 * 1024 * 1024 });
    if (r.status !== 0 || r.error) {
      const why = r.error ? r.error.message
        : (r.stderr || '').split(/\r?\n/).filter(Boolean).pop() || `exit ${r.status}`;
      process.stderr.write(`skip ${code}: ${why}\n`);
      skipped++;
      continue;
    }
    for (const line of (r.stdout || '').split(/\r?\n/)) {
      if (!line.trim()) continue;
      records.push(JSON.parse(line));
      recStream.write(line + '\n');
    }
  }
  recStream.end();
  const agg = metrics.aggregate(records);
  fs.writeFileSync(path.join(outDir, 'report.md'), renderReport(agg));
  process.stdout.write(`wrote ${records.length} records + report.md to ${outDir} (skipped ${skipped} codes)\n`);
}

if (process.argv[2] === '--one') runOne();
else main();

module.exports = { recordsForCode, stateAByTurn, availableBlockers, humanAssignment };
