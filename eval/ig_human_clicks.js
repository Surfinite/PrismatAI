'use strict';
/**
 * ig_human_clicks.js — for each F6 IG dump, align it to its replay (oracle_diff state-signature
 * matching over per-click snapshots) and count how many Infusion-Grid self-sac clicks the HUMAN
 * actually made from that decision point through the end of that turn.
 *
 * An IG self-sac click = engine click type "inst clicked" / "inst shift clicked" whose target
 * instId is an Infusion Grid owned by the active player (mirrors tactical_suite.count_ig_clicks,
 * which counts the same in the responder's aiclicks). BUYS ("card clicked", string arg) are not IG
 * self-sacs and never match here.
 *
 * The F6 dumps align at the space-click that ENTERS the action phase, so counting IG inst-clicks in
 * (alignedIdx, end-of-turn] is exactly "what the human did with the IGs from this position" — the
 * apples-to-apples human counterpart of the net's argmax IG-click count from the same state.
 *
 * Usage: node ig_human_clicks.js <IG_States dir> <replays dir> [--json out.json]
 */
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const Analyzer = require('../js_engine/Analyzer');

const IG_NAMES = new Set(['Infusion Grid', 'Hotel']);

function loadReplay(fp) {
    const raw = fs.readFileSync(fp);
    return fp.endsWith('.gz') ? JSON.parse(zlib.gunzipSync(raw).toString('utf-8'))
                              : JSON.parse(raw.toString('utf-8'));
}
function buildInitInfo(r) {
    return { laneInfo: [{ initResources: r.initInfo.initResources, base: r.deckInfo.base,
            randomizer: r.deckInfo.randomizer, initCards: r.initInfo.initCards }],
        mergedDeck: r.deckInfo.mergedDeck, scriptInfo: { whiteStarts: true }, objectiveInfo: null,
        commandInfo: { commandList: r.commandInfo.commandList, clicksPerTurn: r.commandInfo.clicksPerTurn,
            gamePosition: r.commandInfo.commandList.length } };
}
function findReplay(dir, code) {
    const enc = code.replace(/\+/g, '%2B').replace(/@/g, '%40');
    for (const name of [code + '.json.gz', enc + '.json.gz', code + '.json', enc + '.json']) {
        const fp = path.join(dir, name);
        if (fs.existsSync(fp)) return fp;
    }
    return null;
}
function extractCurrentInfo(raw) {
    const j = raw.indexOf('{', raw.indexOf('"CurrentInfo"'));
    let depth = 0, instr = false, esc = false, k = j;
    for (; k < raw.length; k++) {
        const c = raw[k];
        if (instr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') instr = false; }
        else { if (c === '"') instr = true; else if (c === '{') depth++; else if (c === '}') { depth--; if (depth === 0) { k++; break; } } }
    }
    return JSON.parse(raw.slice(j, k));
}
const SIG = ['numTurns', 'phase', 'turn', 'nextInstId', 'whiteMana', 'blackMana', 'glassBroken'];
function sig(gs) { const o = {}; SIG.forEach(k => o[k] = gs[k]); o.tableLen = (gs.table || []).length; return o; }
function sigEq(a, b) { return SIG.every(k => String(a[k]) === String(b[k])) && a.tableLen === b.tableLen; }
function sigScore(a, b) { let s = SIG.filter(k => String(a[k]) === String(b[k])).length; if (a.tableLen === b.tableLen) s++; return s; }

// Replay one game; return per-click records {idx, igClick, sig} (sig AFTER the click).
function replayClicks(replay) {
    const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
    const recs = [];
    const orig = analyzer.recordClick.bind(analyzer);
    let idx = 0;
    analyzer.recordClick = function (u, d, type, id, params) {
        // pre-click: is this an IG self-sac (inst-click on an active-owned IG)?
        let igClick = false;
        if (type === 'inst clicked' || type === 'inst shift clicked') {
            try {
                const gs = JSON.parse(analyzer.gameState.toString());
                const active = gs.turn;
                const inst = (gs.table || []).find(t => t.instId === id);
                if (inst && IG_NAMES.has(inst.cardName) && inst.owner === active) igClick = true;
            } catch (e) { /* ignore */ }
        }
        const r = orig(u, d, type, id, params);
        let s = null;
        try { s = sig(JSON.parse(analyzer.gameState.toString())); } catch (e) {}
        recs.push({ idx, igClick, sig: s });
        idx++;
        return r;
    };
    try { analyzer.loaderInit(); } catch (e) { /* replay may throw at end; snapshots already captured */ }
    return recs;
}

function alignAndCount(recs, oracleSig) {
    const exact = recs.filter(r => r.sig && sigEq(r.sig, oracleSig));
    let chosen, quality;
    if (exact.length) { chosen = exact[exact.length - 1]; quality = 'exact'; }
    else {
        let best = null, bs = -1;
        recs.forEach(r => { if (!r.sig) return; const sc = sigScore(r.sig, oracleSig); if (sc > bs) { bs = sc; best = r; } });
        chosen = best; quality = `partial ${bs}/${SIG.length + 1}`;
    }
    if (!chosen) return { alignedIdx: -1, humanIG: null, quality: 'NO MATCH' };
    const K = chosen.idx;
    // count IG inst-clicks from K+1 until numTurns changes (end of this player's turn)
    let humanIG = 0;
    for (let j = K + 1; j < recs.length; j++) {
        const s = recs[j].sig;
        if (s && String(s.numTurns) !== String(oracleSig.numTurns)) break;  // next turn
        if (recs[j].igClick) humanIG++;
    }
    return { alignedIdx: K, humanIG, quality };
}

function main() {
    const dumpDir = process.argv[2];
    const replayDir = process.argv[3];
    const jsonOut = process.argv.includes('--json') ? process.argv[process.argv.indexOf('--json') + 1] : null;

    const dumps = fs.readdirSync(dumpDir).filter(f => f.endsWith('.txt')).sort();
    const byCode = {};
    for (const f of dumps) { const code = f.replace(/_\d+\.txt$/, ''); (byCode[code] = byCode[code] || []).push(f); }

    const rows = [];
    for (const code of Object.keys(byCode).sort()) {
        const rfp = findReplay(replayDir, code);
        if (!rfp) { console.error(`  no replay for ${code}`); continue; }
        const recs = replayClicks(loadReplay(rfp));
        for (const f of byCode[code]) {
            const ci = extractCurrentInfo(fs.readFileSync(path.join(dumpDir, f), 'utf-8'));
            const gs = ci.gameState;
            const r = alignAndCount(recs, sig(gs));
            rows.push({ dump: f, code, realTurn: gs.numTurns, side: gs.turn === 0 ? 'P0' : 'P1',
                alignedIdx: r.alignedIdx, humanIG: r.humanIG, quality: r.quality });
        }
    }

    rows.sort((a, b) => a.dump.localeCompare(b.dump));
    console.log(`${'dump'.padEnd(22)} ${'realT'.padStart(5)} ${'side'.padStart(4)} ${'alignIdx'.padStart(8)} ${'humanIG'.padStart(7)}  quality`);
    console.log('-'.repeat(70));
    for (const r of rows) {
        console.log(`${r.dump.padEnd(22)} ${String(r.realTurn).padStart(5)} ${r.side.padStart(4)} ` +
            `${String(r.alignedIdx).padStart(8)} ${String(r.humanIG).padStart(7)}  ${r.quality}`);
    }
    const nExact = rows.filter(r => r.quality === 'exact').length;
    console.log(`\n${nExact}/${rows.length} aligned exactly.`);
    if (jsonOut) { fs.writeFileSync(jsonOut, JSON.stringify(rows, null, 2)); console.log(`-> ${jsonOut}`); }
}
main();
