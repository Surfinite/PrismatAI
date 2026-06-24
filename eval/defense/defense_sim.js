'use strict';
const dv = require('./defense_value');

// ---------------------------------------------------------------------------
// solveDefense — JS port of the C++ BlockIterator one-prime min-loss search
//   (PrismataAI-dave-master/source/ai/BlockIterator.cpp:50-194).
//
// The engine groups available blockers into isomorphism classes, then recurses:
//   * a "last blocker" (the prime) is ANY iso-group with a spare unit whose
//     currentHealth >= damageRemaining (BlockIterator.cpp:190-194, NOTE: '>=').
//     Choosing it zeroes the remaining damage in one step and is charged
//     loss(card, damageRemaining). If hp > remaining the prime SURVIVES; if
//     hp == remaining the prime DIES (loss sees damage==hp) but still legally
//     zeroes the incoming — so hp==remaining is a valid last blocker (see below).
//   * a "chump" at the current depth-group takes min(hp, remaining) damage and
//     the recursion continues with the reduced remaining (cpp:101-111). A chump
//     whose hp <= remaining is a full-kill (dies). Chumps that reduce remaining
//     to exactly 0 record a solution with NO last blocker (cpp:53 solve cond).
//
// The objective Σ loss(unit, damage, mode) lives entirely in defense_value.loss,
// so 'ours' and 'cpp' share this identical search structure (lineup-awareness is
// inside the per-unit loss only). This file consumes dv.{unitView, loss, isoKey}.
//
// DEVIATION FROM THE TASK-7 PLAN (intentional, verified against the C++):
//   The plan modelled "chump some, then ONE prime that survives", priming only
//   when g.hp > remaining and breaking the chump loop at g.hp >= remaining.
//   The real BlockIterator does NOT do that. Two boundary cases the plan misses:
//     (1) hp == remaining: the C++ isLastBlocker uses '>=', so such a unit IS a
//         valid last blocker (it dies absorbing exactly `remaining`, remaining->0,
//         fully blocked). The plan would emit no assignment for that branch.
//     (2) exact-absorb by chumps: if chumps zero out the damage, the C++ records
//         a solution with no prime at all. The plan requires a surviving prime.
//   This port follows the C++ so the Task-12 gate (which runs 'cpp' mode against
//   the real engine) sees a structure-matching search.
// ---------------------------------------------------------------------------
function solveDefense(stateUnits, incoming, mode, eps = 0.001) {
  const views = stateUnits.map(u => dv.unitView(u));

  // Group into iso-classes (mirrors _isoBlockers; order = first-appearance, as C++).
  const groups = [];
  const byKey = new Map();
  views.forEach(v => {
    const k = dv.isoKey(v);
    let g = byKey.get(k);
    if (!g) { g = { key: k, view: v, hp: v.hp, units: [] }; byKey.set(k, g); groups.push(g); }
    g.units.push(v);
  });

  // No incoming damage -> nothing to block, zero loss, trivial assignment.
  if (!(incoming > 0)) {
    const untouched = groups.filter(g => g.units.length).map(g => ({ isoKey: g.key, count: g.units.length }));
    const perUnit = {};
    groups.forEach(g => g.units.forEach(u => { perUnit[u.instId] = 0; }));
    const assignment = { chumps: [], prime: null, untouched, perUnit };
    return { assignment, perUnit, loss: 0, tiedAlts: [{ assignment, loss: 0 }] };
  }

  // A solution = chump-count per iso-key + optional last blocker (key + damage it takes).
  const solutions = [];
  const chumpCounts = new Map(); // key -> number currently chumping (mutated during recursion)

  function record(lossScore, lastKey, lastDmg) {
    solutions.push({ loss: lossScore, chumpCounts: new Map(chumpCounts), lastKey, lastDmg });
  }

  // cpp:50-118 recurse. `remaining` is the un-blocked incoming damage.
  function recurse(depth, remaining, lossScore) {
    // cpp:53-68 solve condition — chumps (and earlier last-blockers) already zeroed it.
    if (remaining === 0) { record(lossScore, null, 0); return; }

    // cpp:79-98 last-blocker pass: any iso-group with a spare unit whose hp >= remaining
    // can solo-absorb the remainder. NOTE '>=' (cpp:193) — hp==remaining is a valid (dying) prime.
    for (const g of groups) {
      const used = chumpCounts.get(g.key) || 0;
      if (used >= g.units.length) continue;          // no spare unit (canBlock, cpp:192)
      if (g.hp >= remaining) {                        // isLastBlocker (cpp:193)
        const primeLoss = dv.loss(g.view, remaining, mode); // heuristic charged FULL remaining (cpp:84/105)
        record(lossScore + primeLoss, g.key, remaining);
      }
    }

    if (depth >= groups.length) return;

    // cpp:101-111 chump the depth-group, take min(hp, remaining), recurse SAME depth.
    // The C++ allows a PARTIAL chump (hp > remaining): it takes `remaining`, survives,
    // and the recursion immediately solves. That path is physically IDENTICAL to this
    // unit being the last blocker (same unit, same loss(card, remaining), same perUnit)
    // — a pure duplicate already produced by the last-blocker pass above. We therefore
    // restrict the chump branch to FULL-KILL chumps (hp <= remaining); every distinct
    // min-loss outcome is preserved and the spurious partial-chump duplicate is removed
    // (it would otherwise inflate tiedAlts). The min-loss RESULT is unchanged vs the C++.
    const g = groups[depth];
    const used = chumpCounts.get(g.key) || 0;
    if (used < g.units.length && g.hp <= remaining) {  // canBlock (cpp:102) + full-kill only
      const takeDamage = g.hp;                         // cpp:104 (= min(hp, remaining) here)
      const chumpLoss = dv.loss(g.view, remaining, mode);     // heuristic charged FULL remaining (cpp:105)
      chumpCounts.set(g.key, used + 1);
      recurse(depth, remaining - takeDamage, lossScore + chumpLoss); // cpp:109
      chumpCounts.set(g.key, used);                    // unwind (cpp:110)
    }

    // cpp:114-117 advance to the next iso-group, same remaining.
    if (depth + 1 < groups.length) recurse(depth + 1, remaining, lossScore);
  }

  recurse(0, incoming, 0);

  // No feasible defense (incoming overwhelms the pool; no group can ever zero it) -> breach/skip.
  if (!solutions.length) return { assignment: null, loss: Infinity, tiedAlts: [] };

  solutions.sort((a, b) => a.loss - b.loss);
  const best = solutions[0];
  const tied = solutions.filter(s => s.loss <= best.loss + eps);

  // Materialise an assignment from a solution: per-instId damage by iso-class.
  // Within a group: the first `nc` units are chumps (take full hp, die); if this
  // group is the last blocker, the next un-chumped unit takes lastDmg; the rest 0.
  const toAssignment = (s) => {
    const chumps = [], untouched = [], perUnit = {};
    for (const g of groups) {
      const nc = s.chumpCounts.get(g.key) || 0;
      const isPrime = (s.lastKey !== null && g.key === s.lastKey) ? 1 : 0;
      if (nc) chumps.push({ isoKey: g.key, count: nc });
      const untouchedN = g.units.length - nc - isPrime;
      if (untouchedN > 0) untouched.push({ isoKey: g.key, count: untouchedN });
      g.units.forEach((u, i) => {
        if (i < nc) perUnit[u.instId] = g.hp;                       // chump: full hp, dies
        else if (isPrime && i === nc) perUnit[u.instId] = s.lastDmg; // the single last blocker
        else perUnit[u.instId] = 0;                                  // untouched survivor
      });
    }
    return { chumps, prime: s.lastKey, untouched, perUnit };
  };

  // Materialise + dedup tied alternatives by PHYSICAL outcome (perUnit signature).
  // Distinct solution records can map to the SAME physical defense:
  //   * the last-blocker pass reaching an assignment also reachable via a different
  //     chump ordering across iso-groups, and
  //   * the hp==remaining / exact-absorb boundary, where a unit dying as the "last
  //     blocker" (damage==hp) is physically identical to that unit being a full-kill
  //     chump (different `prime` LABEL, identical perUnit).
  // tiedAlts lists each DISTINCT physical defense once. perUnit fully determines the
  // defense (survive-vs-die is damage>=hp, derivable from perUnit), so the signature
  // intentionally EXCLUDES the prime label — a label-only difference is not a distinct defense.
  const sig = (a) => Object.keys(a.perUnit).sort((x, y) => x - y)
    .map(id => id + ':' + a.perUnit[id]).join(',');
  const seen = new Set();
  const tiedAlts = [];
  for (const s of tied) {
    const a = toAssignment(s);
    const k = sig(a);
    if (seen.has(k)) continue;
    seen.add(k);
    tiedAlts.push({ assignment: a, loss: s.loss });
  }

  const assignment = toAssignment(best);
  return {
    assignment,
    perUnit: assignment.perUnit,   // convenience top-level mirror (== assignment.perUnit)
    loss: best.loss,
    tiedAlts,
  };
}

module.exports = { solveDefense };
