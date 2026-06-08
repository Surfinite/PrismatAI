/**
 * Fixture tests for visual_state.js — verifies the pure-function port matches
 * PixiJS visual-state.ts output for known scenarios.
 */

'use strict';

const { computeVisualState,
    BACK_DEAD, BACK_BLOCK, BACK_ABSORB, BACK_BLOCK_FROST, BACK_BOUGHT,
    BACK_WHITEPINK, BACK_BLOCKRED, BACK_BUSYBLUE, BACK_BUSYRED,
    COVER_EMPTY, COVER_INVSPAWN, COVER_ASSIGNED, COVER_BANG,
    SHADING_EMPTY, SHADING_BLOCK, SHADING_NOTBLOCK, SHADING_REDBLOCK,
    INST_HACK_ALPHA, ALPHA_FOR_INVULNERABLE,
} = require('../visual_state');

// Helper: create a snapshot unit with defaults
function makeUnit(overrides = {}) {
    const base = {
        id: 1,
        cardId: 'drone',
        displayName: 'Drone',
        owner: 0,
        stats: { hp: 1, maxHp: 1, attack: 0, chill: 0 },
        state: {
            mode: 'idle',
            blocking: false,
            attacking: false,
            chilled: 0,
            buildTurnsRemaining: 0,
            lifespan: -1,
            delay: 0,
            charge: 0,
            fragile: false,
            frontline: false,
        },
        render: { row: 'back', slot: 23 },
    };

    // Deep merge overrides
    const unit = JSON.parse(JSON.stringify(base));
    if (overrides.owner != null) unit.owner = overrides.owner;
    if (overrides.stats) Object.assign(unit.stats, overrides.stats);
    if (overrides.state) Object.assign(unit.state, overrides.state);
    if (overrides.cardId) unit.cardId = overrides.cardId;
    return unit;
}

// Helper: basic card metadata
function makeMeta(overrides = {}) {
    return {
        attack: 0,
        toughness: 1,
        isFragile: false,
        isFrontline: false,
        defaultBlocking: false,
        cardType: 'unit',
        charge: 0,
        lifespan: -1,
        ...overrides,
    };
}

// ================================================================
// Test runner (simple assert-based, no test framework needed)
// ================================================================

let passed = 0;
let failed = 0;

function assert(condition, msg) {
    if (!condition) {
        console.error(`  FAIL: ${msg}`);
        failed++;
    } else {
        passed++;
    }
}

function test(name, fn) {
    try {
        fn();
        console.log(`  OK: ${name}`);
    } catch (e) {
        console.error(`  FAIL: ${name} — ${e.message}`);
        failed++;
    }
}

// ================================================================
// Fixtures from spec
// ================================================================

console.log('visual_state.test.js');
console.log('');

test('Idle P0 drone → BACK_BUSYBLUE, COVER_EMPTY', () => {
    const unit = makeUnit({ owner: 0 });
    const meta = makeMeta();
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BUSYBLUE, `backFrame=${vs.backFrame} expected ${BACK_BUSYBLUE}`);
    assert(vs.coverFrame === COVER_EMPTY, `coverFrame=${vs.coverFrame} expected ${COVER_EMPTY}`);
    assert(vs.shadingFrame === SHADING_EMPTY, `shadingFrame=${vs.shadingFrame}`);
    assert(vs.cardAlpha === INST_HACK_ALPHA, `cardAlpha=${vs.cardAlpha}`);
    assert(!vs.showSkull, 'should not show skull');
    assert(!vs.showChillSnowflake, 'should not show snowflake');
});

test('Idle P1 drone → BACK_BUSYRED, COVER_EMPTY', () => {
    const unit = makeUnit({ owner: 1 });
    const meta = makeMeta();
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BUSYRED, `backFrame=${vs.backFrame} expected ${BACK_BUSYRED}`);
    assert(vs.coverFrame === COVER_EMPTY, `coverFrame=${vs.coverFrame}`);
});

test('Under construction → BACK_BOUGHT, COVER_INVSPAWN', () => {
    const unit = makeUnit({ state: { buildTurnsRemaining: 2 } });
    const meta = makeMeta();
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BOUGHT, `backFrame=${vs.backFrame} expected ${BACK_BOUGHT}`);
    assert(vs.coverFrame === COVER_INVSPAWN, `coverFrame=${vs.coverFrame} expected ${COVER_INVSPAWN}`);
    assert(vs.cardAlpha === ALPHA_FOR_INVULNERABLE, `cardAlpha=${vs.cardAlpha} expected ${ALPHA_FOR_INVULNERABLE}`);
});

test('Blocking P0 → BACK_BLOCK, SHADING_BLOCK', () => {
    const unit = makeUnit({ owner: 0, state: { blocking: true } });
    const meta = makeMeta({ defaultBlocking: true });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BLOCK, `backFrame=${vs.backFrame} expected ${BACK_BLOCK}`);
    assert(vs.shadingFrame === SHADING_BLOCK, `shadingFrame=${vs.shadingFrame} expected ${SHADING_BLOCK}`);
});

test('Blocking P1 → BACK_BLOCKRED, SHADING_REDBLOCK', () => {
    const unit = makeUnit({ owner: 1, state: { blocking: true } });
    const meta = makeMeta({ defaultBlocking: true });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BLOCKRED, `backFrame=${vs.backFrame} expected ${BACK_BLOCKRED}`);
    assert(vs.shadingFrame === SHADING_REDBLOCK, `shadingFrame=${vs.shadingFrame} expected ${SHADING_REDBLOCK}`);
});

test('Fully chilled → BACK_BLOCK_FROST, snowflake in action phase', () => {
    const unit = makeUnit({
        stats: { hp: 3, maxHp: 3, attack: 0, chill: 0 },
        state: { chilled: 3 },
    });
    const meta = makeMeta({ toughness: 3 });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_BLOCK_FROST, `backFrame=${vs.backFrame} expected ${BACK_BLOCK_FROST}`);
    assert(vs.showChillSnowflake === true, 'should show snowflake in action phase');
});

test('Fully chilled in defense phase → no snowflake', () => {
    const unit = makeUnit({
        stats: { hp: 3, maxHp: 3, attack: 0, chill: 0 },
        state: { chilled: 3 },
    });
    const meta = makeMeta({ toughness: 3 });
    const vs = computeVisualState(unit, meta, 'defense', 0);
    assert(vs.backFrame === BACK_BLOCK_FROST, `backFrame=${vs.backFrame}`);
    assert(vs.showChillSnowflake === false, 'should NOT show snowflake in defense phase');
});

test('Partial damage in defense → BACK_ABSORB, COVER_BANG', () => {
    // hp=4 maxHp=5 → damage=1, health=4 → isPartiallyDamaged (1 < 4)
    const unit = makeUnit({
        stats: { hp: 4, maxHp: 5, attack: 0, chill: 0 },
    });
    const meta = makeMeta({ toughness: 5 });
    const vs = computeVisualState(unit, meta, 'defense', 0);
    assert(vs.backFrame === BACK_ABSORB, `backFrame=${vs.backFrame} expected ${BACK_ABSORB}`);
    assert(vs.coverFrame === COVER_BANG, `coverFrame=${vs.coverFrame} expected ${COVER_BANG}`);
    assert(vs.damageCounter === 1, `damageCounter=${vs.damageCounter} expected 1`);
});

test('Dead with full damage → BACK_WHITEPINK, skull', () => {
    const unit = makeUnit({
        stats: { hp: 0, maxHp: 3, attack: 0, chill: 0 },
    });
    const meta = makeMeta({ toughness: 3 });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_WHITEPINK, `backFrame=${vs.backFrame} expected ${BACK_WHITEPINK}`);
    assert(vs.showSkull === true, 'should show skull');
    assert(vs.coverFrame === COVER_BANG, `coverFrame=${vs.coverFrame} expected ${COVER_BANG}`);
    assert(vs.damageCounter === 3, `damageCounter=${vs.damageCounter} expected 3`);
});

test('Assigned to attack → COVER_ASSIGNED', () => {
    const unit = makeUnit({ state: { attacking: true } });
    const meta = makeMeta({ attack: 1 });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.coverFrame === COVER_ASSIGNED, `coverFrame=${vs.coverFrame} expected ${COVER_ASSIGNED}`);
});

test('Default-blocking unit not blocking → SHADING_NOTBLOCK', () => {
    const unit = makeUnit({ state: { blocking: false } });
    const meta = makeMeta({ defaultBlocking: true });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.shadingFrame === SHADING_NOTBLOCK, `shadingFrame=${vs.shadingFrame} expected ${SHADING_NOTBLOCK}`);
});

test('Partial damage in action phase (non-blocking) → BACK_ABSORB', () => {
    const unit = makeUnit({
        stats: { hp: 3, maxHp: 5, attack: 0, chill: 0 },
    });
    const meta = makeMeta({ toughness: 5 });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_ABSORB, `backFrame=${vs.backFrame} expected ${BACK_ABSORB}`);
});

test('Blocking unit with damage → BACK_DEAD, skull', () => {
    const unit = makeUnit({
        stats: { hp: 2, maxHp: 3, attack: 0, chill: 0 },
        state: { blocking: true },
    });
    const meta = makeMeta({ defaultBlocking: true, toughness: 3 });
    const vs = computeVisualState(unit, meta, 'action', 0);
    assert(vs.backFrame === BACK_DEAD, `backFrame=${vs.backFrame} expected ${BACK_DEAD}`);
    assert(vs.showSkull === true, 'should show skull for damaged blocker');
});

// ================================================================
// Summary
// ================================================================

console.log('');
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
