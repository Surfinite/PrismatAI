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
    raw: stateUnit,   // original game-state unit, for iso fields not on the view (chill/delay/construction/status)
  };
}

// ---------------------------------------------------------------------------
// isoKey / isIsomorphic — stable isomorphism-class identity for a blocker,
// mirroring Card::isIsomorphic (PrismataAI-dave-master/source/engine/Card.cpp:862-874).
// C++ compares 10 fields: getType, getPlayer, currentHealth, currentChill,
// getCurrentCharges, isDead, getCurrentDelay, getConstructionTime,
// getCurrentLifespan, getStatus. Defense grouping/matching keys on iso-class
// (never instId), so this is load-bearing for the sim + human-pick matching.
// Reads iso fields not on the view (chill/delay/construction/status) from view.raw.
// ---------------------------------------------------------------------------
function isoKey(view) {
  const r = view.raw || {};
  return [
    view.internal,                                    // getType
    view.owner,                                       // getPlayer
    view.hp,                                          // currentHealth
    r.disruptDamage | 0,                              // currentChill
    view.charge | 0,                                  // getCurrentCharges
    r.delay | 0,                                      // getCurrentDelay
    r.constructionTime | 0,                           // getConstructionTime
    view.life === undefined ? -1 : view.life,         // getCurrentLifespan
    r.deadness && r.deadness !== 'alive' ? 1 : 0,     // isDead
    r.role || r.status || 'default',                  // getStatus
  ].join('|');
}

function isIsomorphic(a, b) { return isoKey(a) === isoKey(b); }

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

// ---------------------------------------------------------------------------
// lossCpp — FAITHFUL JS port of Heuristics::DamageLoss_WillCost
//   (PrismataAI-dave-master/source/ai/Heuristics.cpp:158-242, the strong engine_v1).
// Purpose: let the Task-12 validation gate match the real C++ engine bit-for-bit, so
// this MUST reproduce the C++ behaviour INCLUDING ITS BUGS. Do NOT "fix" anything here
// (the 'ours' mode is the fixed model). C++ line numbers are cited inline.
//
// Reuses the WillScore helpers already defined in gen_our_numbers_v2.js for the
// reference column (willScoreCpp/inflCpp/resolveBT/buySac) — DO NOT re-derive the math.
//   willScoreCpp(buyCost): gold 1.00, blue 1.50, green 1.20, red 0.90, energy 0.50,
//                          attack 2.25  (Heuristics.cpp:7-14 WILL_VALUE_* / CalculateBuyManaCost)
//   inflCpp(bt): WILL_VALUE_CONSTR=1.28^(bt-1), bt0 -> 1/1.13 (Heuristics.cpp:67-76 _precomputedInflation)
// ---------------------------------------------------------------------------
const { willScoreCpp, inflCpp, resolveBT, buySac } = vm;

// GetInflatedManaCostValue (Heuristics.cpp:41-44/85): buy-mana WillScore * inflation.
function inflatedManaValue(ct)  { return willScoreCpp(ct.buyCost) * inflCpp(resolveBT(ct)); }
// GetInflatedTotalCostValue (Heuristics.cpp:46-49/86): (buy-mana + buySac) WillScore * inflation.
function inflatedTotalValue(ct) { return (willScoreCpp(ct.buyCost) + (buySac ? buySac(ct) : 0)) * inflCpp(resolveBT(ct)); }

// APPROXIMATION (C++ Card::canBlockOnly, Card.cpp:827): the real flag also returns false on
// hasBeginOwnTurnScript() and treats a charge unit with spent charges as block-only. Here we
// approximate with "no click ability AND no target ability" (matches gen_our_numbers_v2's
// blockOnlyC). The Task-12 gate will reveal any unit where this diverges; fix those by name then.
function canBlockOnly(ct) { return !ct.abilityScript && !ct.targetAction; }

// CardType::isFragile (CardType.cpp:82) is a static flag; live blockers in defense are built
// (constructionTime==0), so it equals ct.fragile.
function isFragileCpp(ct) { return !!ct.fragile; }

function lossCpp(view, damage) {
  const ct = view.ct; if (!ct) return 0;
  // Heuristics.cpp:161 — doom card with 1 lifespan is useless to us anyway; damage 0 -> 0.
  // getCurrentLifespan() is 0 for a non-lifespan unit (-> not ==1); ct.lifespan is undefined there.
  const remLife = view.life !== undefined ? view.life : ct.lifespan;
  if (remLife === 1 || damage === 0) return 0;

  // Heuristics.cpp:166-171 — tie-break epsilons for charge / lifespan / exhaust.
  const eps = 0.001;
  const usesCharges = !!ct.charge;                                  // CardType::usesCharges()
  const curCharge = view.charge !== undefined ? view.charge : (ct.charge || 0);  // getCurrentCharges()
  const chargeLoss   = usesCharges ? (1 / (1 + curCharge)) * eps : 0;            // :168
  const lifespanLoss = (remLife > 0) ? (1 / remLife) * eps : 0;                  // :169 (lifespan 0/undef -> 0)
  const exhaustLoss  = 0;                                           // :170 getCurrentDelay()==0 for ready blockers (APPROXIMATION: exhaustLoss ignored for v1)
  const tieBreakLoss = chargeLoss + lifespanLoss + exhaustLoss;     // :171

  // Heuristics.cpp:174 — linearHealthValue = canBlockOnly() || isAbilityHealthUserOnly().
  // APPROXIMATION: isAbilityHealthUserOnly is a C++ flag not in cardLibrary.jso. Its C++ predicate
  // (CardTypeInfo.cpp:158) requires abilityScript.getHealthUsed()>0, so approximate that arm with
  // ct.HPUsed !== undefined. Gate (Task 12) fixes any divergent unit by name.
  const linearHealthValue = canBlockOnly(ct) || (ct.HPUsed !== undefined);

  // APPROXIMATION: resonators (resonateAttackAddedValue, Heuristics.cpp:177-178) ignored for v1 -> 0.
  const resonate = 0;

  // Heuristics.cpp:181 — special case: 1HP block-only blocker, valued below an engineer.
  if (canBlockOnly(ct) && view.hp === 1) return 1.875 + resonate;

  // Heuristics.cpp:187-188 — custom designer heuristic value overrides BOTH mana and total when set.
  const manaVal  = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedManaValue(ct);
  const totalVal = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedTotalValue(ct);

  // APPROXIMATION (Heuristics.cpp:102 Forcefield 3.75 mana pin): left as a marked no-op stub. The
  // Task-12 gate adds `return 3.75 ...` by name if it flags Forcefield. (gen_our_numbers_v2's cpp()
  // uses 3.75 for Forcefield, so the gate will likely need it.)
  if ((view.ui || '') === 'Forcefield') { /* Heuristics.cpp:102 mana pin — add if gate flags */ }

  if (isFragileCpp(ct)) {                                           // Heuristics.cpp:191
    const damageTaken = Math.min(damage, view.hp);                  // :193
    // BUG REPLICATED (Heuristics.cpp:194): ratio uses getStartingHealth() (nominal toughness),
    // NOT current or max HP. ct.toughness == getStartingHealth() (CardTypeInfo.cpp:25).
    const startHP = ct.toughness;
    const ratio = damageTaken / startHP;
    if (linearHealthValue) {                                        // :197 block-only -> cost-proportional
      let dmgValue = ratio * (manaVal - tieBreakLoss);             // :199-200
      if (damageTaken < view.hp) dmgValue -= eps;                  // :203-206 survives -> favour alive
      if (view.hp === 1)        dmgValue += 2 * eps;               // :209-212 1hp card worse than 1hp of a big card
      return damageTaken >= view.hp ? (dmgValue + resonate) : dmgValue;  // :214
    } else {                                                        // :217 has other functions
      // BUG REPLICATED (Heuristics.cpp:219/221): tieBreakLoss subtracted TWICE.
      const cardValue = totalVal - tieBreakLoss - tieBreakLoss;     // :219 (-tieBreakLoss) then :221 (-= tieBreakLoss)
      const dmgValue = ratio * cardValue;                          // :222
      return damageTaken >= view.hp ? (cardValue + resonate) : (dmgValue * eps);  // :226
    }
  } else {                                                          // Heuristics.cpp:229 non-fragile
    if (damage >= view.hp) {                                        // :232 dies -> full heuristic value
      return (linearHealthValue ? manaVal : totalVal) - tieBreakLoss + resonate;  // :234
    }
    return 0;                                                       // :239 survives, repairs -> no loss
  }
}

module.exports = { unitView, V, body, resolveInternal, loss, isoKey, isIsomorphic };
