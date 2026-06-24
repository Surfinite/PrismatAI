'use strict';
const vm = require('../../docs/scratch/gen_our_numbers_v2.js');
const { ours, lib, CONSTANTS } = vm;
const { BV, UNDEF_PER_HP, FRAGILE_PEN } = CONSTANTS;
const DOOMED_NUDGE = CONSTANTS.DOOMED_NUDGE !== undefined ? CONSTANTS.DOOMED_NUDGE : 0.1;

// Resolve a game-state unit (table[] entry) to its card-library key + current state.
function resolveInternal(stateUnit) {
  const nm = stateUnit.cardName || stateUnit.cardType || stateUnit.name;
  if (lib[nm]) return nm;                       // already an internal key
  // else search by UIName
  for (const k of Object.keys(lib)) if ((lib[k].UIName || k) === nm) return k;
  return null;
}

function unitView(stateUnit) {
  const internal = resolveInternal(stateUnit);
  const ct = internal ? lib[internal] : null;
  return {
    internal, ui: ct ? (ct.UIName || internal) : (stateUnit.cardName),
    owner: stateUnit.owner,
    instId: stateUnit.instId,
    hp: stateUnit.health !== undefined ? stateUnit.health : (ct ? ct.toughness : 0),
    charge: stateUnit.charge,
    life: stateUnit.lifespan,
    fragile: !!(ct && ct.fragile),
    heal: ct ? (ct.HPGained || 0) : 0,
    max: ct ? (ct.HPMax !== undefined ? ct.HPMax : ct.toughness) : 0,
    ct,
  };
}

// Full functional value at current state (ours mode), via the value model with overrides.
function V(view) {
  if (!view.ct) return 0;
  return ours(view.ct, { hp: view.hp, charge: view.charge, life: view.life }).v;
}

// Block floor only (effective-soak HP * BV, doomed nudge, fragile/undef haircuts) — exposed for tests/diagnostics.
function body(view) {
  if (!view.ct) return 0;
  const r = ours(view.ct, { hp: view.hp, charge: view.charge, life: view.life });
  return r.block;   // ours() returns block/atk split; block carries the heal-aware floor + nudge + haircuts
}

// Per-unit functional defense loss. mode 'ours' implemented here; 'cpp' lands in Task 5.
function loss(view, damage, mode) {
  if (mode === 'ours') return lossOurs(view, damage);
  if (mode === 'cpp')  return lossCpp(view, damage);   // implemented in Task 5
  throw new Error('unknown mode: ' + mode);
}

function lossOurs(view, damage) {
  if (!view.ct) return 0;
  const dies = damage >= view.hp;
  if (dies) return V(view);                       // chump: full value lost
  if (!view.fragile) return 0;                    // non-fragile survivor: repairs, free
  // fragile survivor: body(before) - body(after); body() already projects one heal
  const after = Object.assign({}, view, { hp: view.hp - damage });
  return body(view) - body(after);
}

module.exports = { unitView, V, body, resolveInternal, loss };
