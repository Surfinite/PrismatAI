/**
 * Fixture tests for status_overlay.js — verifies the pure-function port matches
 * PixiJS StatusOverlay.ts update() logic for known scenarios.
 */

'use strict';

const { computeStatusIcons } = require('../status_overlay');

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

    const unit = JSON.parse(JSON.stringify(base));
    if (overrides.owner != null) unit.owner = overrides.owner;
    if (overrides.stats) Object.assign(unit.stats, overrides.stats);
    if (overrides.state) Object.assign(unit.state, overrides.state);
    if (overrides.cardId) unit.cardId = overrides.cardId;
    return unit;
}

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

console.log('status_overlay.test.js');
console.log('');

test('Idle Drone — defense icon, no attack', () => {
    const unit = makeUnit();
    const meta = makeMeta({ toughness: 1 });
    const so = computeStatusIcons(unit, meta);

    assert(so.constructionTimer === null, `constructionTimer=${so.constructionTimer}`);
    assert(so.fixedIcons.attack === null, 'should have no attack icon');
    assert(so.fixedIcons.defense !== null, 'should have defense icon');
    assert(so.fixedIcons.defense.value === 1, `defense=${so.fixedIcons.defense.value}`);
    assert(so.variableIcons.length === 0, `variableIcons.length=${so.variableIcons.length}`);
});

test('Tarsier (2 attack, fragile) — attack icon, no defense, HP icon', () => {
    const unit = makeUnit({
        cardId: 'tarsier',
        stats: { hp: 1, maxHp: 1, attack: 2, chill: 0 },
    });
    const meta = makeMeta({ attack: 2, isFragile: true, toughness: 0 });
    const so = computeStatusIcons(unit, meta);

    assert(so.fixedIcons.attack !== null, 'should have attack icon');
    assert(so.fixedIcons.attack.value === 2, `attack=${so.fixedIcons.attack.value}`);
    assert(so.fixedIcons.defense === null, 'should have no defense (fragile)');
    assert(so.fixedIcons.spell === false, 'not a spell');
    // Fragile units show HP
    const hpIcon = so.variableIcons.find(i => i.type === 'hp');
    assert(hpIcon != null, 'should show HP icon for fragile unit');
    assert(hpIcon.count === 1, `hp count=${hpIcon.count}`);
});

test('Under construction (timer=2) — construction timer, no variable icons', () => {
    const unit = makeUnit({ state: { buildTurnsRemaining: 2 } });
    const meta = makeMeta();
    const so = computeStatusIcons(unit, meta);

    assert(so.constructionTimer === 2, `constructionTimer=${so.constructionTimer}`);
    assert(so.variableIcons.length === 0, `variableIcons.length=${so.variableIcons.length}`);
});

test('Fragile unit under construction — timer + HP icon', () => {
    const unit = makeUnit({
        stats: { hp: 1, maxHp: 1, attack: 0, chill: 0 },
        state: { buildTurnsRemaining: 3 },
    });
    const meta = makeMeta({ isFragile: true });
    const so = computeStatusIcons(unit, meta);

    assert(so.constructionTimer === 3, `constructionTimer=${so.constructionTimer}`);
    assert(so.variableIcons.length === 1, `variableIcons.length=${so.variableIcons.length}`);
    assert(so.variableIcons[0].type === 'hp', `type=${so.variableIcons[0].type}`);
});

test('Chilled unit (partial) — chill icon with count', () => {
    const unit = makeUnit({
        stats: { hp: 5, maxHp: 5, attack: 0, chill: 0 },
        state: { chilled: 3 },
    });
    const meta = makeMeta({ toughness: 5 });
    const so = computeStatusIcons(unit, meta);

    const chillIcon = so.variableIcons.find(i => i.type === 'chill');
    assert(chillIcon != null, 'should show chill icon');
    assert(chillIcon.count === 3, `chill count=${chillIcon.count}`);
    assert(chillIcon.full === false, 'should be partial chill');
});

test('Fully chilled unit — chill icon marked full', () => {
    const unit = makeUnit({
        stats: { hp: 3, maxHp: 3, attack: 0, chill: 0 },
        state: { chilled: 3 },
    });
    const meta = makeMeta({ toughness: 3 });
    const so = computeStatusIcons(unit, meta);

    const chillIcon = so.variableIcons.find(i => i.type === 'chill');
    assert(chillIcon != null, 'should show chill icon');
    assert(chillIcon.full === true, 'should be full chill');
});

test('Unit with delay=1 — delay icon', () => {
    const unit = makeUnit({ state: { delay: 1 } });
    const meta = makeMeta();
    const so = computeStatusIcons(unit, meta);

    const delayIcon = so.variableIcons.find(i => i.type === 'delay');
    assert(delayIcon != null, 'should show delay icon');
    assert(delayIcon.count === 1, `delay count=${delayIcon.count}`);
});

test('Unit with lifespan=3 — lifespan icon', () => {
    const unit = makeUnit({ state: { lifespan: 3 } });
    const meta = makeMeta();
    const so = computeStatusIcons(unit, meta);

    const lifespanIcon = so.variableIcons.find(i => i.type === 'lifespan');
    assert(lifespanIcon != null, 'should show lifespan icon');
    assert(lifespanIcon.count === 3, `lifespan count=${lifespanIcon.count}`);
});

test('Unit with charge=2 — charge icon with level', () => {
    const unit = makeUnit({ state: { charge: 2 } });
    const meta = makeMeta({ charge: 3 });
    const so = computeStatusIcons(unit, meta);

    const chargeIcon = so.variableIcons.find(i => i.type === 'charge');
    assert(chargeIcon != null, 'should show charge icon');
    assert(chargeIcon.count === 2, `charge count=${chargeIcon.count}`);
    assert(chargeIcon.level === 2, `charge level=${chargeIcon.level}`);
});

test('Frontline unit — frontline icon (no count)', () => {
    const unit = makeUnit();
    const meta = makeMeta({ isFrontline: true, isFragile: true });
    const so = computeStatusIcons(unit, meta);

    const frontlineIcon = so.variableIcons.find(i => i.type === 'frontline');
    assert(frontlineIcon != null, 'should show frontline icon');
    assert(frontlineIcon.count === undefined, 'frontline has no count');
});

test('Spell unit — spell icon instead of defense', () => {
    const unit = makeUnit();
    const meta = makeMeta({ cardType: 'spell', toughness: 0 });
    const so = computeStatusIcons(unit, meta);

    assert(so.fixedIcons.spell === true, 'should show spell icon');
    assert(so.fixedIcons.defense === null, 'should not show defense for spell');
});

test('Damaged unit under construction — no timer (damage > 0)', () => {
    const unit = makeUnit({
        stats: { hp: 1, maxHp: 3, attack: 0, chill: 0 },
        state: { buildTurnsRemaining: 2 },
    });
    const meta = makeMeta({ toughness: 3, isFragile: true });
    const so = computeStatusIcons(unit, meta);

    // When damage > 0 during construction, construction timer is suppressed
    assert(so.constructionTimer === null, `constructionTimer should be null when damaged, got ${so.constructionTimer}`);
    // Should show normal variable icons instead
    const hpIcon = so.variableIcons.find(i => i.type === 'hp');
    assert(hpIcon != null, 'should show HP in normal mode');
});

// ================================================================
// Summary
// ================================================================

console.log('');
console.log(`Results: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
