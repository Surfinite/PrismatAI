#!/usr/bin/env node
'use strict';

/**
 * validate_snapshots_batch.js — Tier 1 invariant validation at scale.
 *
 * Runs the preprocessor on many replays and checks invariants that should
 * ALWAYS hold, regardless of game state. Violations indicate either
 * preprocessor extraction bugs or JS engine logic bugs.
 *
 * Usage:
 *   node tools/validate_snapshots_batch.js [--count N] [--verbose]
 *
 * Default: 100 random replays from local archive.
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const { processReplayData } = require('./replay_to_snapshots');
const { buildCardIdMap } = require('./card_id_map');

const ARCHIVE_DIR = path.join(__dirname, '..', '..', 'prismata-replay-parser', 'replays_archive');
const LIB_PATH = path.join(__dirname, '..', 'bin', 'asset', 'config', 'cardLibrary.jso');

// ---------------------------------------------------------------------------
// Invariant checks — each returns an array of violation strings
// ---------------------------------------------------------------------------

function checkResourcesNonNegative(snapshots) {
    const violations = [];
    for (const snap of snapshots) {
        for (const player of snap.players) {
            const res = player.resources;
            for (const [key, val] of Object.entries(res)) {
                if (typeof val === 'number' && val < 0) {
                    violations.push(`seq=${snap.seq} P${player.id} ${key}=${val} (negative)`);
                }
            }
        }
    }
    return violations;
}

function checkHpInRange(snapshots) {
    const violations = [];
    for (const snap of snapshots) {
        for (const player of snap.players) {
            for (const unit of player.units) {
                const hp = unit.stats.hp;
                const maxHp = unit.stats.maxHp;
                if (hp < 0) {
                    violations.push(`seq=${snap.seq} P${player.id} unit=${unit.id} ${unit.cardId} hp=${hp} (negative)`);
                }
                if (maxHp > 0 && hp > maxHp) {
                    violations.push(`seq=${snap.seq} P${player.id} unit=${unit.id} ${unit.cardId} hp=${hp} > maxHp=${maxHp}`);
                }
            }
        }
    }
    return violations;
}

function checkSeqMonotonic(snapshots) {
    const violations = [];
    for (let i = 1; i < snapshots.length; i++) {
        if (snapshots[i].seq <= snapshots[i - 1].seq) {
            violations.push(`seq=${snapshots[i].seq} not strictly increasing (prev=${snapshots[i - 1].seq})`);
        }
    }
    return violations;
}

function checkValidPhases(snapshots) {
    const validPhases = ['action', 'defense', 'confirm'];
    const violations = [];
    for (const snap of snapshots) {
        if (!validPhases.includes(snap.phase)) {
            violations.push(`seq=${snap.seq} invalid phase="${snap.phase}"`);
        }
    }
    return violations;
}

function checkActivePlayerValid(snapshots) {
    const violations = [];
    for (const snap of snapshots) {
        if (snap.activePlayer !== 0 && snap.activePlayer !== 1) {
            violations.push(`seq=${snap.seq} invalid activePlayer=${snap.activePlayer}`);
        }
    }
    return violations;
}

function checkUnitIdsUnique(snapshots) {
    const violations = [];
    for (const snap of snapshots) {
        const allIds = new Set();
        for (const player of snap.players) {
            for (const unit of player.units) {
                if (allIds.has(unit.id)) {
                    violations.push(`seq=${snap.seq} duplicate unit id=${unit.id}`);
                }
                allIds.add(unit.id);
            }
        }
    }
    return violations;
}

function checkUnitCountDelta(snapshots) {
    // Between consecutive snapshots, total unit count shouldn't jump by more
    // than a reasonable amount (most turns add/remove a few units, not dozens)
    const violations = [];
    const MAX_DELTA = 20; // generous threshold
    for (let i = 1; i < snapshots.length; i++) {
        const prevTotal = snapshots[i - 1].players[0].units.length + snapshots[i - 1].players[1].units.length;
        const currTotal = snapshots[i].players[0].units.length + snapshots[i].players[1].units.length;
        const delta = Math.abs(currTotal - prevTotal);
        if (delta > MAX_DELTA) {
            violations.push(`seq=${snapshots[i].seq} unit count jumped by ${delta} (${prevTotal}→${currTotal})`);
        }
    }
    return violations;
}

function checkBuyEventsHaveUnits(snapshots) {
    // Every buy event should reference a unit that exists in the CURRENT snapshot
    const violations = [];
    for (const snap of snapshots) {
        const allUnitIds = new Set();
        for (const player of snap.players) {
            for (const unit of player.units) {
                allUnitIds.add(unit.id);
            }
        }
        for (const evt of snap.events) {
            if (evt.type === 'buy' && evt.unitId !== undefined) {
                if (!allUnitIds.has(evt.unitId)) {
                    violations.push(`seq=${snap.seq} buy event unitId=${evt.unitId} not in snapshot`);
                }
            }
        }
    }
    return violations;
}

function checkKillEventsRemoveUnits(snapshots) {
    // Every kill/sacrifice event should reference a unit that existed in the
    // PREVIOUS snapshot but NOT in the current one
    const violations = [];
    for (let i = 1; i < snapshots.length; i++) {
        const prevIds = new Set();
        for (const player of snapshots[i - 1].players) {
            for (const unit of player.units) {
                prevIds.add(unit.id);
            }
        }
        const currIds = new Set();
        for (const player of snapshots[i].players) {
            for (const unit of player.units) {
                currIds.add(unit.id);
            }
        }
        for (const evt of snapshots[i].events) {
            if ((evt.type === 'kill' || evt.type === 'sacrifice' || evt.type === 'breach_kill')
                && evt.unitId !== undefined) {
                if (currIds.has(evt.unitId)) {
                    violations.push(`seq=${snapshots[i].seq} ${evt.type} unitId=${evt.unitId} still alive`);
                }
                // Note: unit might not have been in prev snapshot if multiple events
                // happen between snapshots. This is OK — don't flag it.
            }
        }
    }
    return violations;
}

function checkResultMatch(snapshots, replay) {
    // The engine's final state should match the replay's result field
    const violations = [];
    if (replay.result === undefined || replay.result === null) return violations;

    const last = snapshots[snapshots.length - 1];
    if (!last) return violations;

    // replay.result: 0 = P1 wins (first player), 1 = P2 wins, 2 = draw
    // We can infer from the last snapshot: if one side has 0 units and the other
    // doesn't, that side lost. But this is heuristic — the game could end by
    // resignation or other means.
    //
    // Better check: does the engine even FINISH? If we have pending events
    // and the game isn't over, that's a concern.
    // For now, just check that we produced snapshots at all.
    if (snapshots.length < 2) {
        violations.push('Only ' + snapshots.length + ' snapshot(s) produced');
    }

    return violations;
}

function checkTurnCountMatch(snapshots, replay) {
    const violations = [];
    if (!replay.commandInfo || !replay.commandInfo.clicksPerTurn) return violations;

    const expectedTurns = replay.commandInfo.clicksPerTurn.length;
    const lastSnap = snapshots[snapshots.length - 1];
    const actualTurns = lastSnap ? lastSnap.turn : 0;

    // Allow some tolerance — the preprocessor counts turns differently
    // (numTurns vs clicksPerTurn.length)
    if (Math.abs(expectedTurns - actualTurns) > 2) {
        violations.push(`Turn count mismatch: expected ~${expectedTurns}, got ${actualTurns}`);
    }

    return violations;
}

function checkClickAcceptance(replay) {
    // Replay the clicks and count failures (without generating snapshots)
    // This validates the JS engine can process the replay
    const violations = [];

    try {
        const { replayToGameInitInfo } = require('../js_engine/replay_validator');
        const Analyzer = require('../js_engine/Analyzer');

        const gameInitInfo = replayToGameInitInfo(replay);
        const initOnly = {
            laneInfo: gameInitInfo.laneInfo,
            mergedDeck: gameInitInfo.mergedDeck,
            scriptInfo: gameInitInfo.scriptInfo,
            objectiveInfo: null,
            commandInfo: null
        };
        const analyzer = new Analyzer(initOnly, -1, -1, null);
        analyzer.loaderInit();

        const cmdList = replay.commandInfo.commandList;
        let accepted = 0;
        let rejected = 0;
        let emotes = 0;

        for (let i = 0; i < cmdList.length; i++) {
            const cmd = cmdList[i];
            if (String(cmd._type).indexOf('emote') === 0) { emotes++; continue; }
            const result = analyzer.recordClick(false, false, cmd._type, cmd._id, cmd._params);
            if (result && result.canClick) {
                accepted++;
            } else {
                rejected++;
            }
        }

        const total = accepted + rejected;
        if (total > 0 && rejected > 0) {
            const pct = ((rejected / total) * 100).toFixed(1);
            violations.push(`${rejected}/${total} clicks rejected (${pct}%)`);
        }
    } catch (e) {
        violations.push('Click replay failed: ' + e.message);
    }

    return violations;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function loadReplayFromArchive(filePath) {
    const raw = zlib.gunzipSync(fs.readFileSync(filePath));
    return JSON.parse(raw.toString());
}

function main() {
    const args = process.argv.slice(2);
    const verbose = args.includes('--verbose') || args.includes('-v');
    let count = 100;
    const countIdx = args.indexOf('--count');
    if (countIdx !== -1 && args[countIdx + 1]) {
        count = parseInt(args[countIdx + 1], 10);
    }

    // Get replay files
    if (!fs.existsSync(ARCHIVE_DIR)) {
        console.error('Archive not found: ' + ARCHIVE_DIR);
        process.exit(1);
    }

    const allFiles = fs.readdirSync(ARCHIVE_DIR).filter(f => f.endsWith('.json.gz'));
    console.log('Archive: ' + allFiles.length + ' replays');
    console.log('Testing: ' + Math.min(count, allFiles.length) + ' replays');
    console.log('');

    // Shuffle and pick
    const shuffled = allFiles.sort(() => Math.random() - 0.5);
    const selected = shuffled.slice(0, count);

    // Run checks
    const results = {
        total: 0,
        passed: 0,
        failed: 0,
        errors: 0,
        violationCounts: {},
    };

    const failedReplays = [];

    for (let i = 0; i < selected.length; i++) {
        const file = selected[i];
        const code = file.replace('.json.gz', '');
        results.total++;

        if (!verbose && i % 10 === 0) {
            process.stderr.write('\rProgress: ' + i + '/' + selected.length);
        }

        try {
            const replay = loadReplayFromArchive(path.join(ARCHIVE_DIR, file));

            // Skip non-API-format replays
            if (!replay.commandInfo || !replay.deckInfo || !replay.initInfo) {
                results.errors++;
                continue;
            }

            const snapshots = processReplayData(replay);

            // Run all invariant checks
            const allViolations = {};
            const checks = {
                resources_non_negative: checkResourcesNonNegative(snapshots),
                hp_in_range: checkHpInRange(snapshots),
                seq_monotonic: checkSeqMonotonic(snapshots),
                valid_phases: checkValidPhases(snapshots),
                active_player_valid: checkActivePlayerValid(snapshots),
                unit_ids_unique: checkUnitIdsUnique(snapshots),
                unit_count_delta: checkUnitCountDelta(snapshots),
                buy_events_have_units: checkBuyEventsHaveUnits(snapshots),
                kill_events_remove_units: checkKillEventsRemoveUnits(snapshots),
                result_match: checkResultMatch(snapshots, replay),
                turn_count_match: checkTurnCountMatch(snapshots, replay),
                click_acceptance: checkClickAcceptance(replay),
            };

            let hasViolation = false;
            for (const [checkName, violations] of Object.entries(checks)) {
                if (violations.length > 0) {
                    hasViolation = true;
                    allViolations[checkName] = violations;
                    results.violationCounts[checkName] = (results.violationCounts[checkName] || 0) + 1;
                }
            }

            if (hasViolation) {
                results.failed++;
                failedReplays.push({ code, violations: allViolations });
                if (verbose) {
                    console.log('\nFAIL: ' + code);
                    for (const [check, vs] of Object.entries(allViolations)) {
                        console.log('  ' + check + ':');
                        for (const v of vs.slice(0, 3)) {
                            console.log('    ' + v);
                        }
                        if (vs.length > 3) console.log('    ... and ' + (vs.length - 3) + ' more');
                    }
                }
            } else {
                results.passed++;
            }
        } catch (e) {
            results.errors++;
            if (verbose) {
                console.log('\nERROR: ' + code + ' — ' + e.message);
            }
        }
    }

    process.stderr.write('\r');

    // Print summary
    console.log('\n=== Batch Validation Results ===');
    console.log('Total:   ' + results.total);
    console.log('Passed:  ' + results.passed);
    console.log('Failed:  ' + results.failed);
    console.log('Errors:  ' + results.errors);
    console.log('');

    if (Object.keys(results.violationCounts).length > 0) {
        console.log('Violation breakdown (replays affected):');
        const sorted = Object.entries(results.violationCounts)
            .sort((a, b) => b[1] - a[1]);
        for (const [check, count] of sorted) {
            console.log('  ' + check + ': ' + count);
        }
        console.log('');
    }

    if (failedReplays.length > 0 && !verbose) {
        console.log('First 5 failures:');
        for (const fr of failedReplays.slice(0, 5)) {
            console.log('  ' + fr.code + ': ' + Object.keys(fr.violations).join(', '));
        }
        console.log('');
        console.log('Run with --verbose to see details.');
    }

    // Exit code
    const passRate = results.total > 0
        ? ((results.passed / (results.total - results.errors)) * 100).toFixed(1)
        : 0;
    console.log('Pass rate: ' + passRate + '%');
    process.exit(results.failed > 0 ? 1 : 0);
}

main();
