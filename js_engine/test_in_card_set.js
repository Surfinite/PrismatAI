'use strict';

/**
 * test_in_card_set.js — Unit tests for the `in_card_set` supply flag produced by
 * extractTrainingExampleV2() in training_example.js (the SHARED extractor used by
 * BOTH the MB matchup corpus and the human replay corpus).
 *
 * CONVENTION UNDER TEST (must match C++ inference NeuralNet.cpp ~581-591, which marks
 * in_card_set=1 for ALL `numCardsBuyable()` = base + advanced randomizer, tokens excluded):
 *
 *   supply[name] = [whiteRemaining, blackRemaining, in_card_set]
 *   in_card_set = 1  iff the unit is BUYABLE in this game:
 *                     - base units (card.baseSet === true)            -> always 1
 *                     - advanced units in this game's randomizer set  -> 1
 *                     - created tokens (Husk, Gauss Charge, ...)      -> 0
 *
 * This is the convention the MB corpora on disk already use (base+advanced ~= 19) and
 * the one C++ inference uses. The bug being fixed: the shared extractor derived
 * in_card_set purely from `cardSet.includes(name)` with an advanced-only cardSet, so
 * base units were wrongly marked 0 (human corpora measured base_in_set = 0.0).
 *
 * MUST be count-agnostic: human games span Base+5 .. Base+11 (and RL will explore
 * larger sets). No assertion may hardcode "8 advanced".
 *
 * Plain-node test (no framework), matching the js_engine/test_*.js convention.
 */

const C = require('./C');
const { extractTrainingExampleV2 } = require('./training_example');

let passed = 0;
let failed = 0;

function assert(condition, testName, detail) {
    if (condition) {
        console.log(`  PASS: ${testName}`);
        passed++;
    } else {
        console.error(`  FAIL: ${testName}${detail ? ' — ' + detail : ''}`);
        failed++;
    }
}

function assertEqual(actual, expected, testName) {
    if (actual === expected) {
        console.log(`  PASS: ${testName}`);
        passed++;
    } else {
        console.error(`  FAIL: ${testName} — expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
        failed++;
    }
}

// The 11 base units (always buyable, always in_card_set). card.baseSet === true for these.
const BASE_UNITS = [
    'Engineer', 'Drone', 'Conduit', 'Blastforge', 'Animus', 'Forcefield',
    'Gauss Cannon', 'Wall', 'Steelsplitter', 'Tarsier', 'Rhino',
];

/**
 * Build a minimal mock gameState faithful to the fields extractTrainingExampleV2 reads.
 *
 * @param {string[]} advancedInGame - advanced (non-base) units present & buyable this game
 * @param {string[]} tokens         - created-token unit names present on the board (not buyable)
 */
function makeMockState(advancedInGame, tokens) {
    const cards = [];
    const whiteSupply = [];
    const blackSupply = [];

    // Base units: baseSet=true. Give the last base unit supply 0 to prove a SOLD-OUT
    // base unit still stays in_card_set=1 and present in the supply dict.
    BASE_UNITS.forEach((name, i) => {
        cards.push({ UIName: name, baseSet: true });
        const soldOut = (i === BASE_UNITS.length - 1);
        whiteSupply.push(soldOut ? 0 : 10);
        blackSupply.push(soldOut ? 0 : 10);
    });

    // Advanced units in this game's randomizer set: baseSet=false, have supply.
    advancedInGame.forEach((name) => {
        cards.push({ UIName: name, baseSet: false });
        whiteSupply.push(10);
        blackSupply.push(10);
    });

    // Created tokens: baseSet=false, NOT in the randomizer set, supply 0 (cannot be bought).
    tokens.forEach((name) => {
        cards.push({ UIName: name, baseSet: false });
        whiteSupply.push(0);
        blackSupply.push(0);
    });

    return {
        table: [],                                   // no live instances needed for supply test
        cards,
        whiteSupply,
        blackSupply,
        numTurns: 5,
        turn: 0,
        playerMana: () => ({ pool: [0, 0, 0, 0, 0, 0] }),
    };
}

function countInSet(supply) {
    return Object.values(supply).filter((v) => v[2] === 1).length;
}

// ---------------------------------------------------------------------------
// Test 1: Base units are ALWAYS in_card_set=1 (the core regression)
// ---------------------------------------------------------------------------
console.log('\nTest 1: Base units are in_card_set=1 even when absent from the advanced cardSet');
{
    const advanced = ['Pixie', 'Barrier', 'Cryo Ray'];   // a Base+3 game
    const tokens = ['Husk', 'Gauss Charge'];
    const state = makeMockState(advanced, tokens);
    // cardSet passed in is ADVANCED-ONLY (as both MB config.cardSet and the human
    // randomizer provide) — base is intentionally NOT listed here.
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);

    for (const name of BASE_UNITS) {
        assert(ex.supply[name] && ex.supply[name][2] === 1,
            `base '${name}' in_card_set=1`,
            `got ${JSON.stringify(ex.supply[name])}`);
    }
}

// ---------------------------------------------------------------------------
// Test 2: Advanced units in the game's set are in_card_set=1
// ---------------------------------------------------------------------------
console.log('\nTest 2: Advanced (randomizer) units are in_card_set=1');
{
    const advanced = ['Pixie', 'Barrier', 'Cryo Ray'];
    const state = makeMockState(advanced, []);
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
    for (const name of advanced) {
        assert(ex.supply[name] && ex.supply[name][2] === 1,
            `advanced '${name}' in_card_set=1`,
            `got ${JSON.stringify(ex.supply[name])}`);
    }
}

// ---------------------------------------------------------------------------
// Test 3: Created tokens are NOT in the card set (in_card_set=0; absent if supply 0)
// ---------------------------------------------------------------------------
console.log('\nTest 3: Created tokens are excluded from the card set');
{
    const advanced = ['Pixie', 'Barrier'];
    const tokens = ['Husk', 'Gauss Charge'];
    const state = makeMockState(advanced, tokens);
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
    for (const name of tokens) {
        // token has supply 0 and is not buyable -> excluded entirely from supply dict
        assert(!(name in ex.supply),
            `token '${name}' excluded from supply (not in card set, supply 0)`,
            `got ${JSON.stringify(ex.supply[name])}`);
    }
}

// ---------------------------------------------------------------------------
// Test 4: Sold-out base unit stays in_card_set=1 AND present (Rhino, supply 0)
// ---------------------------------------------------------------------------
console.log('\nTest 4: Sold-out base unit (supply 0) stays in_card_set=1 and present');
{
    const advanced = ['Pixie'];
    const state = makeMockState(advanced, []);
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
    const rhino = ex.supply['Rhino'];   // last base unit -> supply 0 in the mock
    assert(rhino !== undefined, 'sold-out base Rhino present in supply', `got ${JSON.stringify(rhino)}`);
    if (rhino) {
        assertEqual(rhino[0], 0, 'Rhino whiteRemaining=0 (sold out)');
        assertEqual(rhino[2], 1, 'Rhino in_card_set=1 (still in the set though sold out)');
    }
}

// ---------------------------------------------------------------------------
// Test 5: COUNT-AGNOSTIC — base always full regardless of advanced-set size
//         (Base+3 .. Base+11; never hardcode 8)
// ---------------------------------------------------------------------------
console.log('\nTest 5: count-agnostic across Base+3 .. Base+11');
{
    const advancedSets = [
        ['Pixie', 'Barrier', 'Cryo Ray'],                                              // B+3
        ['Pixie', 'Barrier', 'Cryo Ray', 'Thorium Dynamo', 'Gauss Fabricator',
         'Xeno Guardian', 'Plasmafier', 'Gaussite Symbiote'],                          // B+8
        ['Pixie', 'Barrier', 'Cryo Ray', 'Thorium Dynamo', 'Gauss Fabricator',
         'Xeno Guardian', 'Plasmafier', 'Gaussite Symbiote', 'Apollo', 'Drake',
         'Hellhound'],                                                                 // B+11
    ];
    for (const advanced of advancedSets) {
        const state = makeMockState(advanced, ['Husk']);
        const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
        const total = countInSet(ex.supply);
        const expected = BASE_UNITS.length + advanced.length;  // 11 + N, token excluded
        assertEqual(total, expected,
            `Base+${advanced.length}: in_card_set count = ${BASE_UNITS.length}+${advanced.length}`);
    }
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(`\n${'='.repeat(50)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failed === 0) {
    console.log('All tests passed.');
} else {
    console.error(`${failed} test(s) FAILED.`);
    process.exit(1);
}
