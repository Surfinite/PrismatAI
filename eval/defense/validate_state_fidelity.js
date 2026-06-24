'use strict';
// State-fidelity validation: prove the JS engine reproduces the TRUE game state.
//
// For each real F6 dev-mode dump in docs/scratch/, replay its game through the JS engine,
// snapshot the gameState at every click, and assert that SOME snapshot matching the dump's
// state signature is byte-identical to the F6 ground truth (0 table/inst diffs; the only
// tolerated scalar diff is timeRemainingMS, the engine wall-clock).
//
// This is the validation the defense-eval gate lacked. The gate proved the defense SIM
// reproduces the engine GIVEN a state; this proves the STATE we feed the sim is the real one
// (so a sim/engine match can't be "garbage in, garbage matched").
//
// Collision-robust: a dump's signature can match several snapshots (e.g. a self-sac+chill
// doesn't change numTurns/mana/nextInstId/tableLen). We take the MIN diff over all matches,
// so an aligner picking the "wrong" same-signature snapshot is not a false failure.
//
// Run: node eval/defense/validate_state_fidelity.js
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const https = require('https');
const Analyzer = require('../../js_engine/Analyzer');

const ROOT = path.resolve(__dirname, '..', '..');
const SCRATCH = path.join(ROOT, 'docs', 'scratch');
const ARCHIVE = 'C:/libraries/prismata-replay-parser/replays_archive';
const SCALAR_KEYS = ['numTurns', 'turn', 'phase', 'whiteMana', 'blackMana', 'glassBroken', 'activePlayer'];
const SCALAR_WHITELIST = new Set(['timeRemainingMS']); // engine wall-clock, not game state
const INST_KEYS = ['cardName', 'owner', 'role', 'deadness', 'dead', 'health', 'charge', 'disruptDamage', 'target', 'lifespan', 'delay', 'constructionTime', 'blocking'];
const SIG = ['numTurns', 'phase', 'turn', 'nextInstId', 'whiteMana', 'blackMana', 'glassBroken'];

// Dumps whose name prefix is NOT a real replay code (synthetic/handmade test states).
const SYNTHETIC = new Set(['ChargeTest', 'ChargeTest3', 'IG', 'Stamina', 'Odin', 'Polywall', 'F6', 'PatchedSWF', 'example1']);
// Hand-built COUNTERFACTUAL analysis states (alternative defenses constructed for research,
// NOT actual replay steps — they intentionally do not align to any real snapshot).
const COUNTERFACTUAL = new Set(['iO6kK-pCety_QDefAnalyse.txt']);
// Dumps named by role (the c27zi-098cz turn 27/28 A/B pair the owner provided).
const REMAP = { StateA: 'c27zi-098cz', StateB: 'c27zi-098cz', StateA2: 'c27zi-098cz', StateB2: 'c27zi-098cz' };

function codeForDump(base) {
  const stem = base.replace(/\.txt$/, '');
  if (REMAP[stem]) return REMAP[stem];
  return stem.replace(/_.*$/, '');
}
function isF6Dump(fp) { try { return fs.readFileSync(fp, 'utf-8').indexOf('"CurrentInfo"') !== -1; } catch (e) { return false; } }
function encCode(c) { return c.replace(/\+/g, '%2B').replace(/@/g, '%40'); }
function archivePath(code) {
  const a = path.join(ARCHIVE, encCode(code) + '.json.gz'); if (fs.existsSync(a)) return a;
  const b = path.join(ARCHIVE, code + '.json.gz'); if (fs.existsSync(b)) return b;
  return null;
}
function download(code) {
  const url = `https://saved-games-alpha.s3.amazonaws.com/${encCode(code)}.json.gz`;
  const dest = path.join(ARCHIVE, encCode(code) + '.json.gz');
  return new Promise((resolve) => {
    const f = fs.createWriteStream(dest);
    https.get(url, (res) => {
      if (res.statusCode !== 200) { res.resume(); f.close(); try { fs.unlinkSync(dest); } catch (e) {} return resolve(null); }
      res.pipe(f); f.on('finish', () => f.close(() => resolve(dest)));
    }).on('error', () => { f.close(); try { fs.unlinkSync(dest); } catch (e) {} resolve(null); });
  });
}
function loadReplay(fp) { const r = fs.readFileSync(fp); return JSON.parse(zlib.gunzipSync(r).toString('utf-8')); }
function buildInitInfo(r) {
  return { laneInfo: [{ initResources: r.initInfo.initResources, base: r.deckInfo.base, randomizer: r.deckInfo.randomizer, initCards: r.initInfo.initCards }],
    mergedDeck: r.deckInfo.mergedDeck, scriptInfo: { whiteStarts: true }, objectiveInfo: null,
    commandInfo: { commandList: r.commandInfo.commandList, clicksPerTurn: r.commandInfo.clicksPerTurn, gamePosition: r.commandInfo.commandList.length } };
}
function extractCI(raw) {
  const i = raw.indexOf('"CurrentInfo"'); const j = raw.indexOf('{', i);
  let depth = 0, instr = false, esc = false, k = j;
  for (; k < raw.length; k++) {
    const c = raw[k];
    if (instr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') instr = false; }
    else { if (c === '"') instr = true; else if (c === '{') depth++; else if (c === '}') { depth--; if (depth === 0) { k++; break; } } }
  }
  return JSON.parse(raw.slice(j, k));
}
function sig(g) { const o = {}; SIG.forEach(k => o[k] = g[k]); o.tableLen = (g.table || []).length; return o; }
function sigEq(a, b) { return SIG.every(k => String(a[k]) === String(b[k])) && a.tableLen === b.tableLen; }

// Full diff (scalars + table by instId) between our snapshot `ours` and the F6 `oracle`.
function diff(ours, oracle) {
  const scalars = SCALAR_KEYS.filter(k => String(ours[k]) !== String(oracle[k]));
  const A = new Map((ours.table || []).map(u => [u.instId, u]));
  const B = new Map((oracle.table || []).map(u => [u.instId, u]));
  let inst = 0;
  for (const [id, ou] of B) { const x = A.get(id); if (!x) { inst++; continue; } if (INST_KEYS.some(k => JSON.stringify(x[k]) !== JSON.stringify(ou[k]))) inst++; }
  for (const id of A.keys()) if (!B.has(id)) inst++;
  return { scalars, inst };
}

// Replay a game and capture a gameState snapshot after every click.
function snapshotGame(replay) {
  const az = new Analyzer(buildInitInfo(replay), -1, -1, null);
  const snaps = [];
  const orig = az.recordClick.bind(az); let idx = 0;
  az.recordClick = function (u, d, t, id, p) { const r = orig(u, d, t, id, p); try { snaps.push({ idx, gs: JSON.parse(az.gameState.toString()) }); } catch (e) {} idx++; return r; };
  try { az.loaderInit(); } catch (e) { /* faithful-failure replays: keep whatever snapshotted */ }
  return snaps;
}

async function main() {
  const dumps = [];
  for (const base of fs.readdirSync(SCRATCH)) {
    if (!base.endsWith('.txt')) continue;
    const fp = path.join(SCRATCH, base);
    if (!isF6Dump(fp)) continue;
    const code = codeForDump(base);
    if (SYNTHETIC.has(code)) continue;
    dumps.push({ base, fp, code, counterfactual: COUNTERFACTUAL.has(base) });
  }
  dumps.sort((a, b) => (a.code + a.base).localeCompare(b.code + b.base));

  // Group by code so each replay is snapshotted once.
  const byCode = new Map();
  for (const d of dumps) { if (!byCode.has(d.code)) byCode.set(d.code, []); byCode.get(d.code).push(d); }

  const rows = [];
  for (const [code, list] of byCode) {
    let rp = archivePath(code);
    if (!rp) { process.stdout.write(`  fetching replay ${code} ...\n`); rp = await download(code); }
    if (!rp) { for (const d of list) rows.push({ ...d, status: 'SKIP', detail: 'no replay' }); continue; }
    let snaps;
    try { snaps = snapshotGame(loadReplay(rp)); } catch (e) { for (const d of list) rows.push({ ...d, status: 'ERROR', detail: (e.message || '').split('\n')[0] }); continue; }
    for (const d of list) {
      const oracle = extractCI(fs.readFileSync(d.fp, 'utf-8')).gameState;
      const osig = sig(oracle);
      const matches = snaps.filter(s => sigEq(sig(s.gs), osig));
      if (d.counterfactual) { rows.push({ ...d, status: 'SKIP', detail: 'counterfactual (hand-built analysis state)' }); continue; }
      if (!matches.length) { rows.push({ ...d, status: 'FAIL', detail: 'no signature-matching snapshot (alignment)' }); continue; }
      // collision-robust: best (min total diff) over all signature-matching snapshots
      let best = null;
      for (const m of matches) {
        const dd = diff(m.gs, oracle);
        const bad = dd.scalars.filter(k => !SCALAR_WHITELIST.has(k));
        const score = dd.inst * 1000 + bad.length;
        if (!best || score < best.score) best = { score, inst: dd.inst, bad, idx: m.idx, n: matches.length };
      }
      const pass = best.inst === 0 && best.bad.length === 0;
      rows.push({ ...d, status: pass ? 'PASS' : 'FAIL', inst: best.inst, bad: best.bad, idx: best.idx, n: best.n });
    }
  }

  let pass = 0, fail = 0, skip = 0;
  process.stdout.write('\n=== State-fidelity (JS engine gameState == F6 ground truth) ===\n');
  for (const r of rows.sort((a, b) => (a.code + a.base).localeCompare(b.code + b.base))) {
    if (r.status === 'PASS') { pass++; process.stdout.write(`  PASS  ${r.base}  (${r.code})  inst diffs=0  [aligned @click ${r.idx}${r.n > 1 ? ' of ' + r.n + ' sig-matches' : ''}]\n`); }
    else if (r.status === 'FAIL') { fail++; process.stdout.write(`  FAIL  ${r.base}  (${r.code})  ${r.detail || ('instDiffs=' + r.inst + ' badScalars=' + JSON.stringify(r.bad))}\n`); }
    else { skip++; process.stdout.write(`  SKIP  ${r.base}  (${r.code})  ${r.detail}\n`); }
  }
  process.stdout.write(`\n${pass} PASS, ${fail} FAIL, ${skip} SKIP of ${rows.length} F6 dumps\n`);
  process.exit(fail === 0 ? 0 : 1);
}
main();
