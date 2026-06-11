'use strict';

/**
 * query_move.js — one-shot move-query helper for the dave-line PrismataAI.exe responder.
 *
 * Given an F6-dump-shaped request file ({mergedDeck, gameState, aiParameters}), a player
 * name, a weights file, and a path to dave's PrismataAI.exe, this:
 *   1. Injects a Player_UCT + NeuralNet block for <player> into aiParameters.Players,
 *      mirroring matchup_clean.js's DSNN auto-inject convention (RootMoveIterator /
 *      MoveIterator / Eval:"NeuralNet" / WeightsFile), and sets aiPlayerName=<player>.
 *   2. Adds "EmitDiagnostics":true to aiParameters so the (rebuilt) responder emits the
 *      optional UCT root diagnostics aivisits / aiargmax / aichosen alongside aiclicks.
 *   3. Spawns the exe fresh (one-shot, stdin → stdout, like steam_ai.js), sends the
 *      one-line request, reads ALL stdout, and prints the parsed LAST-JSON-line response
 *      object {aiclicks, aivisits, aiargmax, aichosen, ...} to stdout.
 *
 * The responder redirects engine-internal printfs to stderr during init/search
 * (standalone/main.cpp), so stdout is normally a single clean JSON line; we still
 * parse the LAST valid-JSON stdout line to be robust against stray prints.
 *
 * The default iterator pair is HardIterator_5var_Root / HardIterator_5var: these are
 * config-only iterators that now resolve by name on the Steam-protocol path thanks to
 * the A12 fix already in the engine (config defs loaded first, then the request blob
 * merged on top without resetting).
 *
 * CLI:
 *   node query_move.js --request <file> --player <name> --weights <bin> --dave-exe <path>
 *                      [--root-iterator <name>] [--move-iterator <name>]
 *                      [--time-limit <ms>] [--max-traversals <int>] [--timeout <ms>]
 *                      [--uct-constant <float>]   (default 0.3 — the tuned cValue; see M-06)
 *
 * Prints the parsed response object as JSON to stdout. Exit 0 on success, nonzero on error.
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

function parseArgs(argv) {
    const args = {
        request: null,
        player: null,
        weights: null,
        daveExe: null,
        // Default = the WIDENED IG-subset root (the deployed/campaign action space). The old
        // default was the narrow HardIterator_5var_Root, which silently auto-fires every IG —
        // an ad-hoc probe of an IG state would measure the wrong action space and "discover"
        // over-clicking that is just the narrow iterator (audit T4-6/L-02). Pass
        // --root-iterator HardIterator_5var_Root explicitly to probe the narrow space.
        rootIterator: 'HardIterator_5var_IGsubset_Root',
        moveIterator: 'HardIterator_5var',
        timeLimit: 7000,
        maxTraversals: 100000,
        timeout: 60000,
        // Default 0.3 = the project's tuned UCTConstant (cValue sweep: strength monotonic in
        // 1/cValue; the engine default 2.0 is the known-WORST value). Every RL/eval player in
        // config.txt runs at 0.3 — omitting it here silently reverted query_move measurements
        // to c=2.0 because injectPlayer REPLACES the whole config player block (audit M-06).
        uctConstant: 0.3,
    };
    for (let i = 2; i < argv.length; i++) {
        const a = argv[i];
        const next = () => argv[++i];
        switch (a) {
            case '--request': args.request = next(); break;
            case '--player': args.player = next(); break;
            case '--weights': args.weights = next(); break;
            case '--dave-exe': args.daveExe = next(); break;
            case '--root-iterator': args.rootIterator = next(); break;
            case '--move-iterator': args.moveIterator = next(); break;
            case '--time-limit': args.timeLimit = parseInt(next(), 10); break;
            case '--max-traversals': args.maxTraversals = parseInt(next(), 10); break;
            case '--timeout': args.timeout = parseInt(next(), 10); break;
            case '--uct-constant': args.uctConstant = parseFloat(next()); break;
            case '-h':
            case '--help': args.help = true; break;
            default:
                console.error(`query_move.js: unknown argument '${a}'`);
                args.error = true;
        }
    }
    return args;
}

function usage() {
    console.error(
        'Usage: node query_move.js --request <file> --player <name> --weights <bin> --dave-exe <path>\n' +
        '                          [--root-iterator <name>] [--move-iterator <name>]\n' +
        '                          [--time-limit <ms>] [--max-traversals <int>] [--timeout <ms>]\n' +
        '                          [--uct-constant <float>]  UCT exploration constant injected into the\n' +
        '                              player block (default 0.3, the tuned cValue; engine default 2.0\n' +
        '                              is the known-worst). Integral values are nudged by +1e-9 so they\n' +
        '                              serialize as JSON doubles (the engine ignores integer literals).\n'
    );
}

/**
 * Extract the balanced {...} object that immediately follows a "<key>" : marker in text.
 * Returns the substring including braces, or null if not found. Brace-aware and string-aware
 * (so braces inside JSON string values don't throw off the depth count).
 */
function extractBalancedObject(text, key) {
    const marker = text.indexOf('"' + key + '"');
    if (marker === -1) return null;
    const start = text.indexOf('{', marker);
    if (start === -1) return null;
    let depth = 0;
    let inStr = false;
    let esc = false;
    for (let i = start; i < text.length; i++) {
        const ch = text[i];
        if (inStr) {
            if (esc) { esc = false; }
            else if (ch === '\\') { esc = true; }
            else if (ch === '"') { inStr = false; }
            continue;
        }
        if (ch === '"') { inStr = true; }
        else if (ch === '{') { depth++; }
        else if (ch === '}') {
            depth--;
            if (depth === 0) return text.slice(start, i + 1);
        }
    }
    return null;
}

/**
 * Parse a request file's text into an object.
 *
 * F6 clipboard dumps are NOT a self-contained JSON document: they are a multi-section
 * dump that begins with the bare fragment `"CurrentInfo" : { ... }` (no enclosing braces),
 * followed by other sections (`"TurnStartInfo" : ...`, an "AI Status Log:" tail, etc.).
 * We brace-match the CurrentInfo object out of such a dump. Plain JSON documents (raw
 * {mergedDeck,...} or {"CurrentInfo":{...}}) parse directly.
 */
function parseRequestFile(text) {
    const trimmed = text.trim();
    try {
        return JSON.parse(trimmed);
    } catch (_) {
        // F6 dump: pull just the balanced CurrentInfo {...} object out of the multi-section text.
        const obj = extractBalancedObject(trimmed, 'CurrentInfo');
        if (obj) {
            return { CurrentInfo: JSON.parse(obj) };
        }
        throw new Error('not valid JSON and no "CurrentInfo" object found');
    }
}

/**
 * Accepts a parsed F6-dump object. F6 dumps wrap the payload under "CurrentInfo";
 * raw {mergedDeck, gameState, aiParameters} objects are also accepted as-is.
 */
function extractCurrentInfo(raw) {
    if (raw && typeof raw === 'object' && raw.CurrentInfo && typeof raw.CurrentInfo === 'object') {
        return raw.CurrentInfo;
    }
    return raw;
}

/**
 * ENGINE QUIRK (dave-master AIParameters.cpp:894): the C++ parser only honors UCTConstant when
 * the JSON value is TYPED as a double — `args["UCTConstant"].IsDouble()`. RapidJSON types a
 * bare integer literal (`2`) as int, so it would be SILENTLY ignored (engine keeps its default
 * c=2.0). JS `JSON.stringify(2.0)` emits `2` (int!), so an integral cValue cannot be expressed
 * as a JSON double from here. Guard: nudge integral values by +1e-9 — behaviorally identical
 * for UCT (c scales the exploration term; a 1e-9 delta is far below any decision threshold)
 * but guarantees double typing on the wire. Warn so the substitution is never silent.
 */
function asWireDouble(v) {
    if (!Number.isFinite(v)) {
        // JSON.stringify(NaN/Infinity) emits null, which the engine's IsDouble() silently
        // ignores -> default c=2.0. Throw so module consumers can't hit that regression.
        throw new Error(`UCTConstant must be a finite number (got ${v})`);
    }
    if (Number.isInteger(v)) {
        const nudged = v + 1e-9;
        console.error(`query_move.js: note: UCTConstant ${v} is integral; sending ${nudged} ` +
            `instead (the engine's IsDouble() check silently ignores JSON integer literals).`);
        return nudged;
    }
    return v;
}

/**
 * Inject the Player_UCT + NeuralNet block + EmitDiagnostics into aiParameters.
 * Mirrors matchup_clean.js's DSNN auto-inject (the aiParams.Players[difficulty] = {...} block).
 */
function injectPlayer(aiParameters, opts) {
    aiParameters = aiParameters || {};
    aiParameters.Players = aiParameters.Players || {};
    // Always (re)write our player block so the eval path + weights + iterators are deterministic.
    // NOTE: this REPLACES any same-named config player block, so every tunable the config player
    // carries must be re-supplied here — omitting UCTConstant was audit finding M-06 (all
    // query_move measurements silently ran at the engine-default c=2.0, the known-worst value).
    aiParameters.Players[opts.player] = {
        type: 'Player_UCT',
        TimeLimit: opts.timeLimit,
        MaxChildren: 40,
        MaxTraversals: opts.maxTraversals,
        RootMoveIterator: opts.rootIterator,
        MoveIterator: opts.moveIterator,
        Eval: 'NeuralNet',
        WeightsFile: opts.weights,
        // Default 0.3 here too, so direct module consumers of injectPlayer() can't silently
        // fall back to the engine-default c=2.0 by omitting the field.
        UCTConstant: asWireDouble(opts.uctConstant === undefined ? 0.3 : opts.uctConstant),
    };
    // Request the optional UCT root diagnostics from the (rebuilt) responder.
    aiParameters.EmitDiagnostics = true;
    return aiParameters;
}

/**
 * One-shot spawn of the responder: write the request on stdin, read all stdout,
 * return the parsed LAST valid-JSON line. Mirrors steam_ai.js spawning but buffers
 * the entire stdout stream rather than stopping at the first newline.
 */
function queryExe(daveExe, requestJson, timeoutMs) {
    return new Promise((resolve, reject) => {
        const proc = spawn(daveExe, [], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: path.dirname(daveExe),
        });

        let stdout = '';
        let stderr = '';
        let settled = false;

        const finish = (fn, arg) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            try { proc.kill(); } catch (_) {}
            fn(arg);
        };

        const timer = setTimeout(() => {
            finish(reject, new Error(
                `query_move.js: responder timed out after ${timeoutMs}ms\n` +
                `--- last stderr ---\n${stderr.slice(-1500)}\n--- end stderr ---`));
        }, timeoutMs);

        proc.on('error', (err) => finish(reject, new Error(`query_move.js: spawn error: ${err.message}`)));
        proc.stdout.on('data', (d) => { stdout += d.toString(); });
        proc.stderr.on('data', (d) => { stderr += d.toString(); if (stderr.length > 8192) stderr = stderr.slice(-8192); });
        proc.stdin.on('error', (err) => finish(reject, new Error(`query_move.js: stdin error: ${err.message}`)));

        proc.on('close', () => {
            // Parse the LAST non-empty stdout line that is valid JSON.
            const lines = stdout.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
            for (let i = lines.length - 1; i >= 0; i--) {
                const clean = lines[i].replace(/[\x00-\x1f]/g, ' ').trim();
                try {
                    const obj = JSON.parse(clean);
                    return finish(resolve, obj);
                } catch (_) { /* try the previous line */ }
            }
            finish(reject, new Error(
                `query_move.js: no valid JSON line in responder stdout.\n` +
                `--- stdout (last 1000) ---\n${stdout.slice(-1000)}\n` +
                `--- stderr (last 1000) ---\n${stderr.slice(-1000)}\n--- end ---`));
        });

        const payload = requestJson.endsWith('\n') ? requestJson : requestJson + '\n';
        proc.stdin.write(payload);
        proc.stdin.end();
    });
}

async function main() {
    const args = parseArgs(process.argv);
    if (args.help) { usage(); process.exit(0); }
    if (args.error) { usage(); process.exit(2); }

    const missing = [];
    if (!args.request) missing.push('--request');
    if (!args.player) missing.push('--player');
    if (!args.weights) missing.push('--weights');
    if (!args.daveExe) missing.push('--dave-exe');
    if (missing.length) {
        console.error(`query_move.js: missing required argument(s): ${missing.join(', ')}`);
        usage();
        process.exit(2);
    }

    if (!fs.existsSync(args.request)) {
        console.error(`query_move.js: request file not found: ${args.request}`);
        process.exit(2);
    }
    if (!fs.existsSync(args.daveExe)) {
        console.error(`query_move.js: dave exe not found: ${args.daveExe}`);
        process.exit(2);
    }
    // Self-documenting ad-hoc runs: always say which action space + constant is being measured.
    console.error(`query_move.js: root=${args.rootIterator} move=${args.moveIterator} ` +
        `c=${args.uctConstant} (pass --root-iterator HardIterator_5var_Root for the narrow space)`);

    let raw;
    try {
        raw = parseRequestFile(fs.readFileSync(args.request, 'utf8'));
    } catch (err) {
        console.error(`query_move.js: failed to parse request JSON: ${err.message}`);
        process.exit(2);
    }

    const info = extractCurrentInfo(raw);
    if (!info || typeof info !== 'object' || !info.gameState || !info.mergedDeck) {
        console.error('query_move.js: request must contain {mergedDeck, gameState, aiParameters} ' +
            '(optionally wrapped under "CurrentInfo").');
        process.exit(2);
    }

    if (!Number.isFinite(args.uctConstant)) {
        console.error(`query_move.js: --uct-constant must be a finite number (got '${args.uctConstant}')`);
        process.exit(2);
    }

    const aiParameters = injectPlayer(info.aiParameters || {}, {
        player: args.player,
        weights: args.weights,
        rootIterator: args.rootIterator,
        moveIterator: args.moveIterator,
        timeLimit: args.timeLimit,
        maxTraversals: args.maxTraversals,
        uctConstant: args.uctConstant,
    });

    const requestJson = JSON.stringify({
        mergedDeck: info.mergedDeck,
        gameState: info.gameState,
        aiParameters: aiParameters,
        aiPlayerName: args.player,
    });

    let response;
    try {
        response = await queryExe(args.daveExe, requestJson, args.timeout);
    } catch (err) {
        console.error(err.message || String(err));
        process.exit(1);
    }

    // Emit the parsed response object: {aiclicks, aivisits, aiargmax, aichosen, ...}.
    process.stdout.write(JSON.stringify(response, null, 2) + '\n');
    process.exit(0);
}

if (require.main === module) {
    main();
}

module.exports = { parseRequestFile, extractBalancedObject, extractCurrentInfo, injectPlayer, queryExe };
