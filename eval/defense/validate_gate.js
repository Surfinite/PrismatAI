'use strict';

// =============================================================================
// validate_gate.js — Task 12: prove the JS defense sim's `cpp` mode reproduces
// the REAL engine's defense picks (spec §8). This is the pipeline's correctness
// anchor: it licenses trusting `defense_sim.solveDefense(..., 'cpp')` for the
// `ours` comparison runs.
//
// For each begin-of-defense State A (incoming attack > 0) in a set of replays:
//   * run sim.solveDefense(blockers, incoming, 'cpp')                  (the JS replica)
//   * drive the real engine on the same State-A request via query_move.js against a
//     DSNN steam bundle, and read its DEFENSE clicks (ASSIGN_BLOCKER actions)
//   * compare the MULTISET of isomorphism-classes each one blocks.
//
// Why iso-class multisets, not instIds: the engine's click protocol (AITools.cpp
// GetClickString / FindIsomorphicCardID) identifies a blocked unit by its
// isomorphism fields, NOT by instId — its `aiclicks` carry no instId at all. The
// engine's own BlockIterator works entirely in iso-classes (BlockIterator.cpp), so
// two units of the same iso-class are interchangeable. The faithful comparison is
// therefore: does the sim block the same number of each iso-class as the engine?
//
// Output: `validation gate: N/N positions match (M mismatches)`; exit 0 iff M==0.
//
// Run:  node eval/defense/validate_gate.js <codesFile> [--bundle <dir>] [--limit N] [--keep-bundle]
// =============================================================================

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('node:child_process');
const Analyzer = require('../../js_engine/Analyzer');
const replay_exporter = require('../../js_engine/replay_exporter');
const { loadJSON, buildInitInfo } = require('../replay_to_request');
const sim = require('./defense_sim');
const dv = require('./defense_value');
const { canBlockState, availableBlockers } = require('./blockers');
const { find } = require('./_find_replay');

const REPO = path.resolve(__dirname, '..', '..');
const ARCHIVE = 'c:/libraries/prismata-replay-parser/replays_archive';
const SRC_BUNDLE = 'C:/libraries/DSNN_steam_bundles/v221_rl_iter8';
const AIPARAMS = path.join(REPO, 'docs', 'scratch', 'ktink_t9_action_request.json');
const WEIGHTS = 'neural_weights_rl_iter8.bin';
const PLAYER = 'RL_TestA12';

// canBlockState / availableBlockers — the canBlock-faithful blocker filter now lives
// in the shared ./blockers module (imported above), so compare.js and this gate feed
// solveDefense the IDENTICAL blocker set (the gate validates the harness's actual filter).

// -----------------------------------------------------------------------------
// Stable iso-class signature for cross-comparison. The engine's `aiclicks` carry
// the unit's state AT CLICK TIME, so `role`/`blocking` MUTATE as units are assigned
// (a clicked unit's role flips to 'assigned'/'inert' and blocking toggles); they are
// therefore NOT usable for matching the engine's clicks back to State-A iso-classes.
// We key on the fields that are invariant across the defense assignment itself:
// cardName, owner, currentHealth, currentChill, currentCharges, delay, lifespan,
// constructionTime. (These are exactly the isIsomorphic fields minus status/blocking.)
// -----------------------------------------------------------------------------
function classSig(name, owner, hp, chill, charge, delay, life, ctime) {
  return [name, owner, hp | 0, chill | 0, charge | 0, delay | 0,
    (life === undefined ? -1 : life), ctime | 0].join('|');
}

function sigFromStateUnit(u) {
  const name = u.cardName || u.cardType || u.name;
  return classSig(name, u.owner, u.health, u.disruptDamage, u.charge, u.delay, u.lifespan, u.constructionTime);
}

function sigFromClickArgs(a) {
  return classSig(a.cardName, a.owner, a.health, a.disruptDamage, a.charge, a.delay, a.lifespan, a.constructionTime);
}

function multisetOf(sigs) {
  const m = new Map();
  for (const s of sigs) m.set(s, (m.get(s) || 0) + 1);
  return m;
}

function multisetEqual(a, b) {
  if (a.size !== b.size) return false;
  for (const [k, v] of a) if (b.get(k) !== v) return false;
  return true;
}

function multisetStr(m) {
  return [...m.entries()].map(([k, v]) => `${v}x{${k}}`).sort().join(', ') || '(empty)';
}

// -----------------------------------------------------------------------------
// Build a temp DSNN bundle (copy of SRC_BUNDLE) whose use_dsnn.txt forces a tiny
// think budget. The defense is a deterministic PartialPlayer (DefenseSolver ->
// BlockIterator) that runs INDEPENDENT of the UCT search, so a 1ms / 1-traversal
// budget yields the IDENTICAL defense as the 10s default — verified — while cutting
// each engine call from ~10s to ~0.4s (makes the 100-game gate feasible).
// -----------------------------------------------------------------------------
function makeFastBundle() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vg_bundle_'));
  cpDir(SRC_BUNDLE, dir);
  fs.writeFileSync(path.join(dir, 'use_dsnn.txt'),
    `weights = ${WEIGHTS}\nthink_time = 1\nmax_traversals = 1\n`);
  return dir;
}

function cpDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const ent of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, ent.name);
    const d = path.join(dst, ent.name);
    if (ent.isDirectory()) cpDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

// Drive the real engine on a State-A request; return the multiset of iso-class
// signatures it assigned as DEFENSE blockers (the inst-clicked actions before the
// first 'space clicked', which commits the defense phase — AITools.cpp END_PHASE).
function engineDefenseSigs(gs, mergedDeck, aiParameters, bundleDir, tmpReqDir) {
  const reqPath = path.join(tmpReqDir, 'req.json');
  fs.writeFileSync(reqPath, JSON.stringify({ mergedDeck, gameState: gs, aiParameters }));
  const out = execFileSync('node', [
    'js_engine/query_move.js',
    '--request', reqPath,
    '--player', PLAYER,
    '--weights', WEIGHTS,
    '--dave-exe', path.join(bundleDir, 'PrismataAI.exe'),
    '--timeout', '60000',
  ], { cwd: REPO, encoding: 'utf-8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  const res = JSON.parse(out);
  const clicks = res.aiclicks || [];
  const sigs = [];
  for (const c of clicks) {
    if (c.type === 'space clicked') break;                 // defense phase commit -> stop
    if (c.type === 'inst clicked' || c.type === 'inst shift clicked') {
      if (c.args && typeof c.args === 'object') sigs.push(sigFromClickArgs(c.args));
    }
  }
  return multisetOf(sigs);
}

// Sim's blocked iso-class multiset = the classes it assigns damage>0 to.
//   ctx = resonate context built from the FULL active-player board (resonators like Resophore are
//   defaultBlocking=0 and so are NOT in rawBlockers, but still add resonateAttackAddedValue on death).
function simDefenseSigs(rawBlockers, incoming, ctx) {
  const ours = sim.solveDefense(rawBlockers, incoming, 'cpp', 0.001, ctx);
  if (!ours.assignment) return null;                       // breach -> skip
  const byId = new Map(rawBlockers.map(u => [u.instId, u]));
  const sigs = [];
  for (const [id, d] of Object.entries(ours.assignment.perUnit)) {
    if (d > 0) {
      const u = byId.get(Number(id));
      if (u) sigs.push(sigFromStateUnit(u));
    }
  }
  return multisetOf(sigs);
}

function parseArgs(argv) {
  const a = { codesFile: null, bundle: null, limit: Infinity, keepBundle: false };
  const rest = argv.slice(2);
  for (let i = 0; i < rest.length; i++) {
    const t = rest[i];
    if (t === '--bundle') a.bundle = rest[++i];
    else if (t === '--limit') a.limit = parseInt(rest[++i], 10);
    else if (t === '--keep-bundle') a.keepBundle = true;
    else if (!a.codesFile) a.codesFile = t;
  }
  return a;
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.codesFile) {
    process.stderr.write('usage: node eval/defense/validate_gate.js <codesFile> [--bundle <dir>] [--limit N] [--keep-bundle]\n');
    process.exit(2);
  }
  const codes = fs.readFileSync(args.codesFile, 'utf-8').split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const aiParameters = loadJSON(AIPARAMS).aiParameters;

  const bundleDir = args.bundle || makeFastBundle();
  const ownBundle = !args.bundle;
  const tmpReqDir = fs.mkdtempSync(path.join(os.tmpdir(), 'vg_req_'));
  process.stderr.write(`validate_gate: bundle=${bundleDir} (think_time=1 fast)\n`);

  let total = 0, mismatch = 0, skippedCodes = 0, positions = 0;
  try {
    for (const code of codes) {
      if (positions >= args.limit) break;
      let replay;
      try { replay = loadJSON(find(ARCHIVE, code)); }
      catch (e) { skippedCodes++; process.stderr.write(`skip ${code}: ${e.message}\n`); continue; }

      let analyzer;
      try {
        analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
        analyzer.loaderInit();
      } catch (e) { skippedCodes++; process.stderr.write(`skip ${code}: analyzer ${e.message}\n`); continue; }

      const mergedDeck = replay.deckInfo.mergedDeck;
      for (let i = 0; i < analyzer.beginTurnHistory.length; i++) {
        if (positions >= args.limit) break;
        let gs;
        try { gs = replay_exporter.stateToCppJSON(analyzer.beginTurnHistory[i]); }
        catch (e) { continue; }
        if (gs.phase !== 'defense' || (gs.incomingAttack | 0) <= 0) continue;

        const player = gs.turn % 2;
        const rawBlockers = availableBlockers(gs, player);
        if (!rawBlockers.length) continue;

        // Resonate context from the FULL active-player board (resonators may be non-blockers).
        const ownBoard = (gs.table || []).filter(u => u.owner === player);
        const ctx = dv.buildResonateContext(ownBoard);

        const incoming = gs.incomingAttack | 0;
        const simSigs = simDefenseSigs(rawBlockers, incoming, ctx);
        if (simSigs === null) continue;                    // sim says breach -> skip (spec §9)

        let engineSigs;
        try { engineSigs = engineDefenseSigs(gs, mergedDeck, aiParameters, bundleDir, tmpReqDir); }
        catch (e) {
          process.stderr.write(`ENGINE-ERR ${code} turn=${i}: ${(e.message || e).toString().split('\n')[0]}\n`);
          continue;
        }

        positions++;
        total++;
        if (!multisetEqual(simSigs, engineSigs)) {
          mismatch++;
          process.stderr.write(
            `MISMATCH ${code} turn=${i} incoming=${incoming} player=${player}\n` +
            `   sim    : ${multisetStr(simSigs)}\n` +
            `   engine : ${multisetStr(engineSigs)}\n`);
        }
      }
    }
  } finally {
    if (ownBundle && !args.keepBundle) { try { fs.rmSync(bundleDir, { recursive: true, force: true }); } catch (_) {} }
    try { fs.rmSync(tmpReqDir, { recursive: true, force: true }); } catch (_) {}
  }

  process.stdout.write(`validation gate: ${total - mismatch}/${total} positions match (${mismatch} mismatches)` +
    ` [${skippedCodes} codes skipped]\n`);
  process.exit(mismatch === 0 ? 0 : 1);
}

if (require.main === module) main();

module.exports = { canBlockState, availableBlockers, classSig, sigFromStateUnit, sigFromClickArgs, multisetEqual };
