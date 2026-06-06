'use strict';

/**
 * dump_shared_state.js — emit a SHARED game state in both representations so the JS
 * training extractor and the C++ engine (self-play exporter + inference) can be diffed
 * element-by-element. Backs the three-way feature-parity test (test_three_way_feature_parity.py).
 *
 * Given a recorded replay and a ply index, it replays the game through PrismatAlpha's own
 * JS engine (Analyzer), grabs the turn-START snapshot at that ply (beginTurnHistory[ply] —
 * the exact state the training extractor captures), and writes:
 *   - <out>.cppstate.json : the C++ GameState JSON (replay_exporter.stateToCppJSON) — feed to
 *                           Prismata_Standalone --dump-v2-record / --dump-features
 *   - <out>.jsrecord.json : the JS V2 training record (extractTrainingExampleV2) for this state
 *
 * Usage:
 *   node dump_shared_state.js <replay.json.gz> <plyIndex> <outPrefix>
 *   node dump_shared_state.js <replay.json.gz> --all <outPrefix>   # every ply -> <outPrefix>.<ply>.{cppstate,jsrecord}.json
 */

const fs = require('fs');
const zlib = require('zlib');
const Analyzer = require('./Analyzer');
const replay_exporter = require('./replay_exporter');
const { extractTrainingExampleV2 } = require('./training_example');

function loadReplay(filePath) {
    const raw = fs.readFileSync(filePath);
    return filePath.endsWith('.gz')
        ? JSON.parse(zlib.gunzipSync(raw).toString('utf-8'))
        : JSON.parse(raw.toString('utf-8'));
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

// advanced-only card set (randomizer; tokens excluded) — the SAME helper the human extractor
// uses for the card_set field + the advanced half of in_card_set. Inlined to avoid coupling.
function buildAdvancedCardSet(replay) {
    const di = replay.deckInfo || {};
    const rnd = di.randomizer;
    if (Array.isArray(rnd) && rnd.length) {
        const set = new Set();
        for (const item of rnd) {
            if (Array.isArray(item)) { for (const n of item) set.add(n); }
            else if (typeof item === 'string') { set.add(item); }
        }
        if (set.size) return Array.from(set);
    }
    const md = di.mergedDeck || [];
    return md.filter(c => !c.baseSet).map(c => c.UIName || c.name);
}

function main() {
    const args = process.argv.slice(2);
    if (args.length < 3) {
        process.stderr.write('usage: node dump_shared_state.js <replay.json.gz> <plyIndex|--all> <outPrefix>\n');
        process.exit(2);
    }
    const replayPath = args[0];
    const plySpec = args[1];
    const outPrefix = args[2];

    const replay = loadReplay(replayPath);
    const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
    analyzer.loaderInit();
    const history = analyzer.beginTurnHistory;
    if (!history || history.length < 1) {
        process.stderr.write('ERROR: no beginTurnHistory\n');
        process.exit(1);
    }
    const cardSet = buildAdvancedCardSet(replay);

    const plies = (plySpec === '--all')
        ? history.map((_, i) => i)
        : [parseInt(plySpec, 10)];

    const written = [];
    for (const ply of plies) {
        const state = history[ply];
        if (!state) continue;
        const cppState = replay_exporter.stateToCppJSON(state);
        const jsRecord = extractTrainingExampleV2(state, cardSet, ply);
        const suffix = (plySpec === '--all') ? `.${ply}` : '';
        const cppPath = `${outPrefix}${suffix}.cppstate.json`;
        const jsPath = `${outPrefix}${suffix}.jsrecord.json`;
        fs.writeFileSync(cppPath, JSON.stringify({ gameState: cppState }, null, 2));
        fs.writeFileSync(jsPath, JSON.stringify(jsRecord, null, 2));
        written.push({ ply, cppPath, jsPath });
    }
    process.stdout.write(JSON.stringify({ replay: replayPath, plies: written.map(w => w.ply), count: written.length }, null, 2) + '\n');
}

main();
