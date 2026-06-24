'use strict';

/**
 * replay_to_request.js — turn recorded replay states into query_move.js REQUEST files
 * (the {mergedDeck, gameState, aiParameters} shape calibrate_n.py / action_coverage.py /
 * tactical_suite.py consume as battery members).
 *
 * It replays a game through PrismatAlpha's own JS engine (Analyzer), grabs the turn-START
 * snapshot at each requested ply (beginTurnHistory[ply], via replay_exporter.stateToCppJSON),
 * and wraps it with the replay's own mergedDeck + a reusable aiParameters template (defaults
 * to the ktink fixture — aiParameters is AI config, NOT card-set-specific, so one template
 * serves every state; query_move.js injects the player block + EmitDiagnostics itself).
 *
 *   PHASE CAVEAT: beginTurnHistory[ply] is the TURN-START state. For a no-attack turn that is
 *   the post-swoosh ACTION phase (good); for an ATTACKED turn it is the pre-swoosh DEFENSE
 *   phase (IGs tapped, often 0 red) — INVALID for IG-click testing. Use --ig-only to keep only
 *   action-phase plies where the active player owns a ready IG and has red; for hand-picked IG
 *   decision points an F6 action-phase dump is the more reliable ig_battery source.
 *
 * Usage:
 *   node replay_to_request.js <replay.json[.gz]> <ply|a,b,c|--all> <outDir> [--prefix P]
 *                             [--ig-only] [--defense-only] [--aiparams <request-or-template.json>]
 *
 *   --defense-only keeps only begin-of-defense plies with incoming attack (State A — the AI's
 *   defense input); see defenseDecidable().
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const Analyzer = require('../js_engine/Analyzer');
const replay_exporter = require('../js_engine/replay_exporter');

const REPO = path.dirname(__dirname);
const DEFAULT_AIPARAMS = path.join(REPO, 'docs', 'scratch', 'ktink_t9_action_request.json');

function loadJSON(filePath) {
    const raw = fs.readFileSync(filePath);
    const txt = filePath.endsWith('.gz') ? zlib.gunzipSync(raw).toString('utf-8')
                                         : raw.toString('utf-8');
    return JSON.parse(txt.charCodeAt(0) === 0xFEFF ? txt.slice(1) : txt);  // tolerate BOM
}

function buildInitInfo(replay) {
    return {
        laneInfo: [{
            initResources: replay.initInfo.initResources,
            base: replay.deckInfo.base,
            randomizer: replay.deckInfo.randomizer,
            initCards: replay.initInfo.initCards,
        }],
        mergedDeck: replay.deckInfo.mergedDeck,
        scriptInfo: { whiteStarts: true },
        objectiveInfo: null,
        commandInfo: {
            commandList: replay.commandInfo.commandList,
            clicksPerTurn: replay.commandInfo.clicksPerTurn,
            gamePosition: replay.commandInfo.commandList.length,
        },
    };
}

const IG_NAMES = new Set(['Hotel', 'Infusion Grid']);

// Does the ACTIVE player own a ready (untapped, built) IG, with red available to self-sac?
// Operates on the stateToCppJSON gameState so it matches exactly what query_move.js sees.
function igDecidable(gs) {
    if (gs.phase !== 'action') return false;
    // active player: turn parity (turn 0/even = white/P0 active in the cpp gameState convention).
    const active = (gs.turn % 2 === 0) ? 0 : 1;
    const mana = (active === 0 ? gs.whiteMana : gs.blackMana) || '';
    if (!mana.includes('C')) return false;                 // C = red; IG self-sac costs red
    const table = gs.table || [];
    return table.some(c => {
        const name = c.cardName || c.cardType || c.name;
        return IG_NAMES.has(name) && c.owner === active
            && (c.constructionTime | 0) === 0 && !c.blocking
            && (c.health === undefined || c.health > 0);
    });
}

// Is this a begin-of-defense state with incoming attack? (State A — the AI's defense input.)
// Operates on the stateToCppJSON gameState so it matches exactly what query_move.js sees.
function defenseDecidable(gs) {
    return gs.phase === 'defense' && ((gs.incomingAttack | 0) > 0);
}

function main() {
    const argv = process.argv.slice(2);
    if (argv.length < 3) {
        process.stderr.write('usage: node replay_to_request.js <replay.json[.gz]> <ply|a,b,c|--all> <outDir> [--prefix P] [--ig-only] [--defense-only] [--aiparams F]\n');
        process.exit(2);
    }
    const [replayPath, plySpec, outDir] = argv;
    const prefix = (argv.includes('--prefix')) ? argv[argv.indexOf('--prefix') + 1] : null;
    const igOnly = argv.includes('--ig-only');
    const defenseOnly = argv.includes('--defense-only');
    const aiparamsPath = (argv.includes('--aiparams')) ? argv[argv.indexOf('--aiparams') + 1] : DEFAULT_AIPARAMS;

    const replay = loadJSON(replayPath);
    const code = path.basename(replayPath).replace(/\.json\.gz$|\.gz$|\.json$/, '');
    const aiParameters = loadJSON(aiparamsPath).aiParameters;
    if (!aiParameters) { process.stderr.write(`no aiParameters in ${aiparamsPath}\n`); process.exit(1); }
    const mergedDeck = replay.deckInfo.mergedDeck;

    const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
    analyzer.loaderInit();
    const history = analyzer.beginTurnHistory;
    if (!history || !history.length) { process.stderr.write('no beginTurnHistory\n'); process.exit(1); }

    const plies = (plySpec === '--all') ? history.map((_, i) => i)
                : plySpec.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));

    fs.mkdirSync(outDir, { recursive: true });
    const written = [];
    for (const ply of plies) {
        const state = history[ply];
        if (!state) continue;
        const gameState = replay_exporter.stateToCppJSON(state);
        if (igOnly && !igDecidable(gameState)) continue;
        if (defenseOnly && !defenseDecidable(gameState)) continue;
        const base = `${prefix || code}_p${ply}`;
        const outPath = path.join(outDir, `${base}.json`);
        fs.writeFileSync(outPath, JSON.stringify({ mergedDeck, gameState, aiParameters }, null, 2));
        written.push({ ply, phase: gameState.phase, out: outPath });
    }
    process.stdout.write(JSON.stringify({ replay: code, requested: plies.length,
        written: written.length, igOnly, defenseOnly, files: written }, null, 2) + '\n');
}

module.exports = { loadJSON, buildInitInfo };
if (require.main === module) main();
