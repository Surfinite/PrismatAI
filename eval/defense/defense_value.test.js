'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const dv = require('./defense_value');
const near = (a, b, eps = 0.02) => Math.abs(a - b) < eps;

function mk(name, over = {}) { // build a minimal game-state unit
  return Object.assign({ cardName: name, owner: 0, health: undefined, charge: undefined, lifespan: undefined }, over);
}

test('unitView resolves internal name + current state', () => {
  const v = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(v.internal, 'Wall');
  assert.equal(v.hp, 3);
  assert.equal(v.fragile, false);
});

test('body uses CURRENT hp and heal-aware effective soak', () => {
  // Xaetron: heal 4, max 12, fragile. At HP 8: effective soak min(8+4,12)=12 -> 12*2.2 - 0.1 fragile = 26.3
  const x8 = dv.body(dv.unitView(mk('Xaetron', { health: 8 })));
  assert.ok(near(x8, 26.3), `Xaetron@8 body expected ~26.3, got ${x8}`);
  // At HP 5: min(5+4,12)=9 -> 9*2.2 - 0.1 = 19.7
  const x5 = dv.body(dv.unitView(mk('Xaetron', { health: 5 })));
  assert.ok(near(x5, 19.7), `Xaetron@5 body expected ~19.7, got ${x5}`);
});

test('V(Energy Matrix@5) == 11', () => {
  const em = dv.V(dv.unitView(mk('Golem', { health: 5 })));
  assert.ok(near(em, 11), `EM expected 11, got ${em}`);
});

test('loss ours: chump = full V', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.ok(near(dv.loss(wall, 3, 'ours'), 6.6)); // damage>=hp -> dies -> full value
});

test('loss ours: non-fragile survivor = 0', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.loss(wall, 2, 'ours'), 0);     // survives (2<3), non-fragile -> 0
});

test('loss ours: fragile healer survivor = body delta (Xaetron@3 absorbs 2)', () => {
  const x = dv.unitView(mk('Xaetron', { health: 3 }));
  // body(@3)=min(3+4,12)*2.2-0.1=15.3 ; body(@1)=min(1+4,12)*2.2-0.1=10.9 ; delta=4.4
  assert.ok(near(dv.loss(x, 2, 'ours'), 4.4), `got ${dv.loss(x, 2, 'ours')}`);
});

test('loss ours: heal headroom makes absorption free (Xaetron@10 absorbs 2)', () => {
  const x = dv.unitView(mk('Xaetron', { health: 10 }));
  // body(@10)=min(14,12)=12 ; body(@8)=min(12,12)=12 ; delta 0
  assert.ok(near(dv.loss(x, 2, 'ours'), 0), `got ${dv.loss(x, 2, 'ours')}`);
});

test('loss cpp: non-fragile survivor = 0 (Wall absorbs 2)', () => {
  const wall = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.loss(wall, 2, 'cpp'), 0);
});

test('loss cpp: 1HP block-only special-case = 1.875', () => {
  const husk = dv.unitView(mk('House', { health: 1 }));
  assert.ok(near(dv.loss(husk, 1, 'cpp'), 1.875), `got ${dv.loss(husk, 1, 'cpp')}`);
});

test('loss cpp: lifespan==1 -> 0', () => {
  // Barrier internal "Sound Barrier": lifespan 1
  const b = dv.unitView(mk('Sound Barrier', { health: 1, lifespan: 1 }));
  assert.equal(dv.loss(b, 1, 'cpp'), 0);
});

test('isIsomorphic: two same-HP Husks match; different HP do not', () => {
  const a = dv.unitView(mk('House', { health: 1 }));
  const b = dv.unitView(mk('House', { health: 1 }));
  const c = dv.unitView(mk('Wall', { health: 3 }));
  assert.equal(dv.isIsomorphic(a, b), true);
  assert.equal(dv.isIsomorphic(a, c), false);
  assert.equal(dv.isoKey(a), dv.isoKey(b));
  assert.notEqual(dv.isoKey(a), dv.isoKey(c));
});
