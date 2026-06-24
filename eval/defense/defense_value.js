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
    // The engine emits lifespan = -1 (the "no lifespan" sentinel) for NON-doomed units, and a
    // positive remaining-lifespan (>=1) for doomed ones. The value model expects `undefined` for
    // non-doomed (it then uses the card's nominal lifespan); passing -1 makes ours() treat the unit
    // as a doomed unit with -1 turns left and corrupts the charge/attack valuation (e.g. Tia Thurnax
    // @4/ch3 -> -34.86 instead of +41.08). Normalize the sentinel to undefined; keep real (>=1) lifespans.
    life: (stateUnit.lifespan !== undefined && stateUnit.lifespan >= 1) ? stateUnit.lifespan : undefined,
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
// NOTE: the trailing C++ `getStatus` field (role||status) is DELIBERATELY EXCLUDED.
// For DEFENSE, status does not affect a unit's value or canBlock — non-`assigned` statuses
// (inert/sellable/default) are all equivalent, and State-A blockers are never `assigned`
// (a blocker stays role=DEFAULT until MOVE_DEFEND). Including it minted spurious duplicate
// iso-classes (e.g. "Wall|...|inert" vs "Wall|...|sellable"). This now MATCHES the validation
// gate's own matcher (validate_gate.js classSig, which likewise excludes status/blocking),
// removing a real inconsistency between the sim's grouping and the gate's matching.
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
  ].join('|');
}

// decodeIso — parse an isoKey back into its structural fields, for report aggregation
// (so callers key on internal/hp/charge/lifespan structurally, not by string position).
// Field order MUST track isoKey() above: internal|owner|hp|chill|charge|delay|ctime|life|dead.
function decodeIso(isoKey) {
  const p = String(isoKey).split('|');
  return {
    internal: p[0],
    owner: p[1] === undefined ? undefined : (p[1] === 'undefined' ? undefined : Number(p[1])),
    hp: Number(p[2]),
    chill: Number(p[3]),
    charge: Number(p[4]),
    lifespan: Number(p[7]),
  };
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

// Per-unit functional defense loss.
//   mode 'ours' = the fixed functional model (Task 1-6); 'cpp' = the faithful C++ replica (Task 5/12).
//   ctx (optional) = a resonate context built by buildResonateContext() for the defending board;
//        consumed only by 'cpp' (the C++ adds resonateAttackAddedValue when a card dies). Omitting
//        ctx (as compare.js / the value tests do for resonate-free boards) yields resonate=0.
function loss(view, damage, mode, ctx) {
  if (mode === 'ours') return lossOurs(view, damage);
  if (mode === 'cpp')  return lossCpp(view, damage, ctx);
  throw new Error('unknown mode: ' + mode);
}

// ---------------------------------------------------------------------------
// buildResonateContext — precompute resonateAttackAddedValue per blocker iso-class for a defending
// board, mirroring Heuristics.cpp:177-178 (the only lossCpp approximation left after the Forcefield/
// canBlockOnly/isAbilityHealthUserOnly fixes). For a DYING card of type T the C++ adds:
//   ( GetReceiveFromResonators(T).Attack + GetReceiveFromResonatees(T).Attack ) * WILL_VALUE_ATTACK
// where (AITools.cpp):
//   * Resonators = every card R on the player's board (constructionTime <= 1) whose `resonate` field
//     names T; each contributes R's resonate receive. cardLibrary encodes `resonate` as 1 Attack
//     and `goldResonate` as 1 gold (CardTypeInfo.cpp:98-104) -> only `resonate` adds Attack.
//   * Resonatees = if T itself has a `resonate` field, the count of ready cards of the named type on
//     the board, each adding T's own resonate receive (1 Attack).
// WILL_VALUE_ATTACK = 2.25 (gen_our_numbers_v2). Returns a map keyed by internal card name.
// TASK-12 FIX (gate-revealed): a Resophore (resonate=Forcefield) on the board adds 2.25 to every
// Forcefield's death loss, which is why the engine used Perforators/Walls over Forcefields in the one
// dev replay with a resonator (U+ttn). Threading this context closes that class.
// ---------------------------------------------------------------------------
const WILL_VALUE_ATTACK = 2.25;
function buildResonateContext(stateUnits) {
  // Count ready (constructionTime<=1) units of each internal type on the (single) defending side.
  const readyCountByType = new Map();
  const views = stateUnits.map(u => unitView(u));
  for (const v of views) {
    if (!v.internal) continue;
    if (((v.raw && v.raw.constructionTime) | 0) > 1) continue;   // maxConstructionTime = 1
    readyCountByType.set(v.internal, (readyCountByType.get(v.internal) || 0) + 1);
  }
  // For each card type present, sum resonator (incoming) + resonatee (outgoing) Attack.
  const resonateAtk = new Map();
  // distinct internal types present as potential dying blockers
  const presentTypes = new Set(views.map(v => v.internal).filter(Boolean));
  for (const T of presentTypes) {
    let atk = 0;
    // Resonators: any ready card R whose ct.resonate == T's UIName (resonate names the UI/display card).
    const Tct = lib[T];
    const Tname = Tct ? (Tct.UIName || T) : T;
    for (const [otherInternal, count] of readyCountByType) {
      const oct = lib[otherInternal];
      if (!oct) continue;
      // `resonate` field carries the resonate target's name; matches by UIName or internal key.
      if (oct.resonate && (oct.resonate === Tname || oct.resonate === T)) {
        atk += count * 1;   // resonate -> Resources("A") = 1 Attack per resonator
      }
    }
    // Resonatees: if T itself resonates, count ready cards of the named type.
    if (Tct && Tct.resonate) {
      // resolve the resonate target's internal key
      let targetInternal = lib[Tct.resonate] ? Tct.resonate : null;
      if (!targetInternal) for (const k of Object.keys(lib)) if ((lib[k].UIName || k) === Tct.resonate) { targetInternal = k; break; }
      if (targetInternal) atk += (readyCountByType.get(targetInternal) || 0) * 1;
    }
    if (atk > 0) resonateAtk.set(T, atk * WILL_VALUE_ATTACK);
  }
  return { resonateAtk };
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

// FAITHFUL port of Card::canBlockOnly() (PrismataAI-dave-master/source/engine/Card.cpp:827-860).
// A unit is "block-only" iff it can default-block AND has no economy/ability function:
//   1. !canBlock(false)            -> false   (defaultBlocking gate)
//   2. hasBeginOwnTurnScript()     -> false   (e.g. Engineer's receive:H, Tarsier's receive:A)
//   3. hasTargetAbility()          -> false   (CHILL/SNIPE units)
//   4. hasAbility() && (!usesCharges() || currentCharges>=chargeUsed) -> false
// Mapping to cardLibrary.jso fields:
//   canBlock(false) = !!ct.defaultBlocking ; hasBeginOwnTurnScript = !!ct.beginOwnTurnScript ;
//   hasTargetAbility = !!ct.targetAction ; hasAbility = !!ct.abilityScript ;
//   usesCharges = (ct.charge|0) > 0 ; getChargeUsed() == 1 (constant, CardType.cpp:336).
// TASK-12 FIX (gate-revealed): the old approximation (`!abilityScript && !targetAction`) wrongly
// returned TRUE for Engineer/Tarsier/etc. (they have a beginOwnTurnScript but no ability), so a
// dying Engineer was priced via the canBlockOnly-1hp special case (1.875) instead of its real
// non-block-only path (totalValue=2.0). On a [6 Eng + 3 Wall] vs 9-attack board this flipped the
// BlockIterator's min from the engine's "1 Eng + 3 Walls" to a spurious "4 Eng + 2 Walls".
function canBlockOnly(ct, currentCharge) {
  if (!ct.defaultBlocking) return false;
  if (ct.beginOwnTurnScript) return false;
  if (ct.targetAction) return false;
  if (ct.abilityScript) {
    const usesCharges = (ct.charge | 0) > 0;
    if (!usesCharges) return false;
    const cur = currentCharge !== undefined ? currentCharge : (ct.charge | 0);
    if (cur >= 1) return false;   // getCurrentCharges() >= getChargeUsed()(==1)
  }
  return true;
}

// CardType::isFragile (CardType.cpp:82) is a static flag; live blockers in defense are built
// (constructionTime==0), so it equals ct.fragile.
function isFragileCpp(ct) { return !!ct.fragile; }

// FAITHFUL port of CardTypeInfo::isAbilityHealthUserOnly (PrismataAI-dave-master/source/engine/
// CardTypeInfo.cpp:158-162). True for a fragile unit whose ONLY function spends its own HP via a
// free (no mana / no sac) ability — its block value is then proportional to HP, like a pure blocker.
//   (hasAbility || targetActionType!=NONE) && fragile && !defaultBlocking && startingCharge==0
//   && !abilityScript.hasManaCost() && !abilityScript.hasSacCost()
//   && abilityScript.getHealthUsed() > 0 && !beginOwnTurnScript.hasEffect()
// Field mapping: hasAbility=!!abilityScript ; targetActionType!=NONE=!!targetAction ;
//   startingCharge=ct.charge|0 ; abilityScript.hasManaCost()=ability has a non-empty mana cost
//   (ct.abilityCost) ; hasSacCost()=ability has a sac cost (ct.abilitySac/ct.sac) ;
//   getHealthUsed()=ct.HPUsed ; beginOwnTurnScript.hasEffect()=!!ct.beginOwnTurnScript.
// TASK-12 FIX (gate-revealed): the old approximation (`ct.HPUsed !== undefined`) wrongly returned
// TRUE for Xaetron (HPUsed=7 but defaultBlocking=1, so the engine's `!defaultBlocking` excludes it).
// That mispriced a fragile, NON-block-only Xaetron down the linear branch (high proportional loss)
// instead of the "has other functions" branch (near-zero loss when it survives) — so the sim avoided
// blocking with Xaetron where the engine reliably picks it. Including !defaultBlocking fixes Xaetron;
// the 4 genuine HPUsed-only healers (Ion/Tantalum/Giga Cannon, Distractorod) still qualify, except
// Ion Cannon which has an ability mana cost (GGGG) -> hasManaCost -> excluded, matching the engine.
function isAbilityHealthUserOnly(ct) {
  if (!ct) return false;
  const hasAbility = !!ct.abilityScript;
  const hasTarget  = !!ct.targetAction;
  if (!(hasAbility || hasTarget)) return false;
  if (!ct.fragile) return false;
  if (ct.defaultBlocking) return false;
  if ((ct.charge | 0) !== 0) return false;
  const hasManaCost = !!(ct.abilityCost && String(ct.abilityCost).length > 0);
  if (hasManaCost) return false;
  const hasSacCost = !!(ct.abilitySac || ct.sac);
  if (hasSacCost) return false;
  if (!((ct.HPUsed | 0) > 0)) return false;
  if (ct.beginOwnTurnScript) return false;
  return true;
}

function lossCpp(view, damage, ctx) {
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
  const blockOnly = canBlockOnly(ct, curCharge);
  const linearHealthValue = blockOnly || isAbilityHealthUserOnly(ct);

  // Heuristics.cpp:177-178 — resonateAttackAddedValue (added only when the card DIES). Looked up from
  // the per-board context built by buildResonateContext(); 0 when no ctx (resonate-free boards/tests).
  const resonate = (ctx && ctx.resonateAtk && view.internal && ctx.resonateAtk.get(view.internal)) || 0;

  // Heuristics.cpp:181 — special case: 1HP block-only blocker, valued below an engineer.
  if (blockOnly && view.hp === 1) return 1.875 + resonate;

  // Heuristics.cpp:187-188 — custom designer heuristic value overrides BOTH mana and total when set.
  let manaVal  = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedManaValue(ct);
  let totalVal = ct.heuristicValue !== undefined ? ct.heuristicValue : inflatedTotalValue(ct);

  // Heuristics.cpp:95-104 — Forcefield mana pin. HeuristicValues::Init() OVERWRITES Forcefield's
  // precomputed values after the generic loop: the INFLATED MANA cost becomes a hard-coded 3.75
  // ("approx 2/3 of a wall" — Forcefield's 1.95 inflated mana is otherwise below an Engineer, which
  // makes the blocker prefer chumping Forcefields over Engineers), and the INFLATED TOTAL cost is
  // set to the (un-inflated) buy TOTAL cost, NOT the inflated one. Both must be reproduced.
  //   _precomputedInflatedManaCostValue[FF]  = 3.75
  //   _precomputedInflatedTotalCostValue[FF] = _precomputedBuyTotalCosts[FF] (= manaWill + buySacWill)
  // TASK-12 FIX (gate-revealed): without this pin the sim valued Forcefield at ~1.95 and chumped/primed
  // Forcefields where the engine used Engineers/Walls/Xaetron (every Forcefield-board dev replay).
  // hasCustomHeuristicValue() is false for Forcefield, so this pin (not the heuristicValue branch) applies.
  if ((view.ui || '') === 'Forcefield' && ct.heuristicValue === undefined) {
    manaVal = 3.75;
    totalVal = willScoreCpp(ct.buyCost) + (buySac ? buySac(ct) : 0);   // un-inflated buy total cost
  }

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

module.exports = { unitView, V, body, resolveInternal, loss, isoKey, decodeIso, isIsomorphic, buildResonateContext };
