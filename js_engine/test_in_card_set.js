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
    const whiteSupply = [];   // INITIAL total (the engine keeps this constant)
    const blackSupply = [];
    const whiteBought = [];    // copies purchased so far; remaining = whiteSupply - whiteBought
    const blackBought = [];

    // Base units: baseSet=true. Give the last base unit supply 0 to prove a SOLD-OUT
    // base unit still stays in_card_set=1 and present in the supply dict.
    BASE_UNITS.forEach((name, i) => {
        cards.push({ UIName: name, baseSet: true });
        const soldOut = (i === BASE_UNITS.length - 1);
        whiteSupply.push(soldOut ? 0 : 10);
        blackSupply.push(soldOut ? 0 : 10);
        whiteBought.push(0);
        blackBought.push(0);
    });

    // Advanced units in this game's randomizer set: baseSet=false, have supply.
    advancedInGame.forEach((name) => {
        cards.push({ UIName: name, baseSet: false });
        whiteSupply.push(10);
        blackSupply.push(10);
        whiteBought.push(0);
        blackBought.push(0);
    });

    // Created tokens: baseSet=false, NOT in the randomizer set, supply 0 (cannot be bought).
    tokens.forEach((name) => {
        cards.push({ UIName: name, baseSet: false });
        whiteSupply.push(0);
        blackSupply.push(0);
        whiteBought.push(0);
        blackBought.push(0);
    });

    return {
        table: [],                                   // no live instances needed for supply test
        cards,
        whiteSupply,
        blackSupply,
        whiteBought,
        blackBought,
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
// Test 6: in_card_set is PER-GAME buy-box membership, NOT a global token property.
//   - Every "token" unit could be a buyable randomizer pick in some set; conversely a
//     unit can be buyable AND also spawned as tokens (in-play count > purchasable supply).
//   - Membership therefore comes from THIS game's cardSet (randomizer) — never a global
//     token blacklist. The SAME unit name flips with the game's set.
// ---------------------------------------------------------------------------
console.log('\nTest 6: in_card_set is per-game (same unit flips with the set)');
{
    // Game A: a unit (use a normally-token name to make the point) IS in the randomizer set.
    const stateA = makeMockState(['Gauss Charge', 'Pixie'], []);
    const exA = extractTrainingExampleV2(stateA, ['Gauss Charge', 'Pixie'], 0);
    assert(exA.supply['Gauss Charge'] && exA.supply['Gauss Charge'][2] === 1,
        "unit in THIS game's set -> in_card_set=1 (even a normally-token name)",
        `got ${JSON.stringify(exA.supply['Gauss Charge'])}`);

    // Game B: the same unit is NOT in this game's set (created-only) -> in_card_set=0.
    const stateB = makeMockState(['Pixie'], ['Gauss Charge']);  // Gauss Charge as a created token, supply 0
    const exB = extractTrainingExampleV2(stateB, ['Pixie'], 0);
    assert(!('Gauss Charge' in exB.supply),
        'same unit NOT in this set (created-only, supply 0) -> excluded',
        `got ${JSON.stringify(exB.supply['Gauss Charge'])}`);
}

// ---------------------------------------------------------------------------
// Test 7: a "needs"/created token that is ALSO buyable in the SAME set. The total in-play
//   count (bought + created) can exceed the purchasable supply; in_card_set must remain 1
//   and the supply-remaining values are whatever the engine reports (created instances live
//   on the board / `table`, they do NOT decrement the buy-box supply array).
// ---------------------------------------------------------------------------
console.log('\nTest 7: needs-and-buyable unit in the same set stays in_card_set=1');
{
    const advanced = ['Pixie'];                 // Pixie is BOTH in the buy box AND need-created
    const state = makeMockState(advanced, []);
    const idx = state.cards.findIndex((c) => c.UIName === 'Pixie');
    state.whiteSupply[idx] = 3;                 // buy-box remaining (some purchased)
    state.blackSupply[idx] = 7;
    // Created/needs copies on the board push in-play count above remaining supply; they are
    // board instances, not buy-box supply — recorded in `table`, never in the supply array.
    state.table = [
        { deadness: C.DEADNESS_ALIVE, card: { UIName: 'Pixie' }, owner: 0, health: 1, damage: 0,
          constructionTime: 0, delay: 0, blocking: false, role: C.ROLE_DEFAULT,
          disruptDamage: 0, lifespan: -1, charge: 0 },
    ];
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
    assertEqual(ex.supply['Pixie'][0], 3, 'Pixie whiteRemaining reported as-is (not reduced by created tokens)');
    assertEqual(ex.supply['Pixie'][1], 7, 'Pixie blackRemaining reported as-is');
    assertEqual(ex.supply['Pixie'][2], 1, 'Pixie in_card_set=1 (buyable in this set, regardless of needs)');
}

// ---------------------------------------------------------------------------
// Test 8: supply VALUES are REMAINING (whiteSupply - whiteBought), matching C++
//   inference (NeuralNet.cpp cb.getSupplyRemaining) and the MB corpus. The engine keeps
//   whiteSupply at the INITIAL total and tracks purchases in whiteBought, so the extractor
//   MUST subtract — writing the raw total is a train↔inference skew (model trained on a
//   ~constant cap, evaluated on a decreasing remaining).
// ---------------------------------------------------------------------------
console.log('\nTest 8: supply values are REMAINING (total - bought)');
{
    const advanced = ['Pixie', 'Barrier'];
    const state = makeMockState(advanced, []);
    // Drone (base, idx 1) total 10; 3 white / 4 black bought -> remaining 7 / 6.
    const drone = state.cards.findIndex((c) => c.UIName === 'Drone');
    state.whiteBought[drone] = 3;
    state.blackBought[drone] = 4;
    // Pixie (advanced) total 10; 10 white bought -> remaining 0 (sold out but still in set).
    const pixie = state.cards.findIndex((c) => c.UIName === 'Pixie');
    state.whiteBought[pixie] = 10;
    const ex = extractTrainingExampleV2(state, advanced.slice(), 0);
    assertEqual(ex.supply['Drone'][0], 7, 'Drone p0 remaining = 10 - 3');
    assertEqual(ex.supply['Drone'][1], 6, 'Drone p1 remaining = 10 - 4');
    assertEqual(ex.supply['Drone'][2], 1, 'Drone still in_card_set=1');
    assertEqual(ex.supply['Pixie'][0], 0, 'Pixie p0 remaining = 10 - 10 (sold out)');
    assertEqual(ex.supply['Pixie'][2], 1, 'Pixie still in_card_set=1 despite sold out');
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
