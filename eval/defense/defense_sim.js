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
//   NOTE: this port intentionally OMITS the C++ depth-0 zero-loss early-return
//   (BlockIterator.cpp:92-96). In 'cpp' mode loss is non-negative so this only prunes
//   a no-op; in 'ours' mode (which can have a negative-loss term) keeping it lets the
//   search find a true min the engine would skip. So 'ours' search != C++ search exactly
//   here — beneficial, not a bug; the gate validates 'cpp' only.
// ---------------------------------------------------------------------------
// ctx (optional): a resonate context (dv.buildResonateContext) for the DEFENDING board, used only by
// 'cpp' mode (the C++ adds resonateAttackAddedValue on death). The caller must build it from the FULL
// active-player board, NOT just the blockers — resonators (e.g. Resophore, defaultBlocking=0) are not
// blockers yet still contribute. Omitted -> resonate=0 (correct for resonate-free boards).
function solveDefense(stateUnits, incoming, mode, eps = 0.001, ctx = undefined) {
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
    return { assignment, perUnit, loss: 0, tiedAlts: [{ assignment, loss: 0 }], chumpLossComponent: 0 };
  }

  // §2 untouched-healer credit (ours only). H = board total; below-max healers start "untouched-credited"
  // (lossScore initialized to -H); chumping/priming one adds its credit back (it's no longer untouched).
  let H = 0;
  for (const g of groups) {
    g.uhCredit = (mode === 'ours') ? dv.untouchedHealerCredit(g.view) : 0;  // 0 for non-healers / maxed / cpp
    H += g.uhCredit * g.units.length;
  }

  // A solution = chump-count per iso-key + optional last blocker (key + damage it takes).
  //
  // BRANCH-AND-BOUND (output-identical to the former exhaustive enumeration).
  //   `lossScore` accumulates the per-unit chump (full-kill, death-path) terms of the current
  //   branch; the optional last blocker adds ONE more terminal term in record(). Each added term
  //   is `dv.loss(view, ..., mode)`. These are USUALLY >= 0, but NOT always: a unit's functional
  //   value can be negative ('ours' mode prices a Polywall@1 death at -0.8 via its undefendable
  //   haircut), so `lossScore` is NOT strictly monotonic and the naive bound (prune when
  //   lossScore > bestLoss+eps) would wrongly drop a tied alt that later chumps a negative-loss
  //   unit. We therefore prune against a SOUND lower bound: any completion of this branch can
  //   subtract at most `negFloor` (the most negative total a chump-set + one prime could add, a
  //   board constant <= 0). A completion's loss is thus >= lossScore + negFloor, so we prune only
  //   when lossScore + negFloor > bestLoss + eps. negFloor is ~0 on the husk-heavy boards that
  //   used to blow up (their death losses are all positive), so pruning stays aggressive there.
  //   * `bestLoss` tracks the minimum solution loss seen so far (Infinity until the first).
  //   * `kept` holds exactly the solutions within eps of the best — the tied set, bounded in size.
  //   record() drops any solution whose loss exceeds bestLoss+eps; a strictly-better solution
  //   lowers bestLoss and PURGES kept of now-stale entries. The exhaustive version stored EVERY
  //   feasible tuple, then filtered to <= best+eps and deduped; this stores only the survivors,
  //   but the surviving SET (and DFS order within it) is identical, so best/loss/tiedAlts/perUnit/
  //   prime are unchanged — only memory is bounded.

  // negFloor: a board-level lower bound on the TOTAL added loss any branch completion can have.
  // A completion adds some subset of full-kill chumps (each charged its death loss, independent of
  // `remaining`) plus at most one last blocker. The most a completion can REDUCE lossScore by is
  // the sum of every available unit's negative death-loss, plus one extra worst-case last-blocker
  // term (a prime can take partial/exact damage, a distinct term from the death loss). We sum
  // min(0, deathLoss) over all units, then add the single most-negative term seen on the board.
  let negFloor = 0;
  let minTerm = 0;                                           // most negative single term (chump or prime)
  for (const g of groups) {
    // death loss of one g-unit (full-kill): dv.loss is damage-independent once it dies, so any
    // damage >= g.hp gives the same value; use g.hp. Plus the forgone untouched-healer credit for a
    // below-max healer (the -H trick adds g.uhCredit back whenever it's chumped/dies, ours only).
    const deathLoss = dv.loss(g.view, g.hp, mode, ctx) + g.uhCredit;
    if (deathLoss < 0) negFloor += deathLoss * g.units.length;
    if (deathLoss < minTerm) minTerm = deathLoss;
    // a surviving prime (partial-damage last blocker) is a different term; sample its sign too.
    // The surviving prime earns -futureAbsorb (ours) and, if it's a below-max healer, +uhCredit.
    if (g.hp > 1) {
      const survLoss = dv.loss(g.view, g.hp - 1, mode, ctx);
      const primeCredit = (mode === 'ours') ? dv.futureAbsorb(g.view) : 0;
      const survTerm = survLoss - primeCredit + g.uhCredit;
      if (survTerm < minTerm) minTerm = survTerm;
    }
  }
  negFloor += minTerm;                                       // one extra terminal prime term

  const kept = [];               // solutions with loss <= bestLoss + eps (the live tied set)
  let bestLoss = Infinity;       // min solution loss seen so far
  const chumpCounts = new Map(); // key -> number currently chumping (mutated during recursion)

  function record(lossScore, lastKey, lastDmg) {
    if (lossScore > bestLoss + eps) return;                  // strictly outside the tied band -> drop
    if (lossScore < bestLoss) {                              // new strict best -> tighten + purge
      bestLoss = lossScore;
      for (let i = kept.length - 1; i >= 0; i--) {
        if (kept[i].loss > bestLoss + eps) kept.splice(i, 1);
      }
    }
    kept.push({ loss: lossScore, chumpCounts: new Map(chumpCounts), lastKey, lastDmg });
  }

  // cpp:50-118 recurse. `remaining` is the un-blocked incoming damage.
  function recurse(depth, remaining, lossScore) {
    // Prune: lossScore + negFloor is a SOUND lower bound on every completion of this branch
    // (negFloor <= 0 caps the largest reduction any future chump/prime set can contribute); if it
    // already exceeds the tied band, no descendant solution can be within eps of best (B&B cutoff).
    if (lossScore + negFloor > bestLoss + eps) return;

    // cpp:53-68 solve condition — chumps (and earlier last-blockers) already zeroed it.
    if (remaining === 0) { record(lossScore, null, 0); return; }

    // cpp:79-98 last-blocker pass: any iso-group with a spare unit whose hp >= remaining
    // can solo-absorb the remainder. NOTE '>=' (cpp:193) — hp==remaining is a valid (dying) prime.
    for (const g of groups) {
      const used = chumpCounts.get(g.key) || 0;
      if (used >= g.units.length) continue;          // no spare unit (canBlock, cpp:192)
      if (g.hp >= remaining) {                        // isLastBlocker (cpp:193)
        const primeLoss = dv.loss(g.view, remaining, mode, ctx); // heuristic charged FULL remaining (cpp:84/105)
        // §2: a TRULY surviving prime (hp>remaining) earns futureAbsorb (ours only). A below-max-healer
        // prime forgoes its untouched credit (+g.uhCredit), whether it survives or dies as last blocker.
        const primeCredit = (mode === 'ours' && g.hp > remaining) ? dv.futureAbsorb(g.view) : 0;
        record(lossScore + primeLoss - primeCredit + g.uhCredit, g.key, remaining);
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
      const chumpLoss = dv.loss(g.view, remaining, mode, ctx) + g.uhCredit; // + forgone untouched credit (0 unless below-max healer)
      chumpCounts.set(g.key, used + 1);
      recurse(depth, remaining - takeDamage, lossScore + chumpLoss); // cpp:109
      chumpCounts.set(g.key, used);                    // unwind (cpp:110)
    }

    // cpp:114-117 advance to the next iso-group, same remaining.
    if (depth + 1 < groups.length) recurse(depth + 1, remaining, lossScore);
  }

  recurse(0, incoming, -H);

  // No feasible defense (incoming overwhelms the pool; no group can ever zero it) -> breach/skip.
  if (!kept.length) return { assignment: null, loss: Infinity, tiedAlts: [] };

  // `kept` already holds exactly the within-eps tied set (B&B maintained it). A stable sort by
  // loss reproduces the exhaustive path's `solutions.sort((a,b)=>a.loss-b.loss)` ordering: the
  // DFS-first minimum-loss solution lands at index 0 (its branch was never pruned — its prefix
  // lower bound <= its own loss == bestLoss <= bestLoss+eps), matching the former `solutions[0]`.
  kept.sort((a, b) => a.loss - b.loss);
  const best = kept[0];
  const tied = kept;

  // Materialise an assignment from a solution: per-instId damage by iso-class.
  // Within a group: the first `nc` units are chumps (take full hp, die); if this
  // group is the last blocker, the next un-chumped unit takes lastDmg; the rest 0.
  const toAssignment = (s) => {
    const chumps = [], untouched = [], perUnit = {};
    // Honest prime labeling: the last blocker SURVIVES only if it takes < its hp
    // (partial damage). At the exact-absorb / hp==remaining boundary the "last
    // blocker" dies absorbing exactly its hp (lastDmg >= hp) — physically a chump,
    // not a surviving prime. Reclassify it as a chump and report prime = null.
    let primeKey = s.lastKey;
    if (primeKey !== null) {
      const pg = byKey.get(primeKey);
      if (s.lastDmg >= pg.hp) primeKey = null;   // last blocker died -> not a prime
    }
    for (const g of groups) {
      let nc = s.chumpCounts.get(g.key) || 0;
      const survivingPrime = (primeKey !== null && g.key === primeKey) ? 1 : 0;
      // The original last-blocker slot for this group: a surviving prime keeps its
      // own slot (not a chump); a dead "prime" folds into the chump count instead.
      const deadPrimeHere = (s.lastKey !== null && g.key === s.lastKey && survivingPrime === 0) ? 1 : 0;
      nc += deadPrimeHere;
      if (nc) chumps.push({ isoKey: g.key, count: nc });
      const untouchedN = g.units.length - nc - survivingPrime;
      if (untouchedN > 0) untouched.push({ isoKey: g.key, count: untouchedN });
      g.units.forEach((u, i) => {
        // perUnit is UNCHANGED by the relabel: the dead last blocker still shows its
        // damage (s.lastDmg == its hp). Original chumps occupy [0, originalNc); the
        // last-blocker slot is at originalNc (its damage is s.lastDmg either way).
        const originalNc = s.chumpCounts.get(g.key) || 0;
        const isLastSlot = (s.lastKey !== null && g.key === s.lastKey && i === originalNc);
        if (i < originalNc) perUnit[u.instId] = g.hp;                 // chump: full hp, dies
        else if (isLastSlot) perUnit[u.instId] = s.lastDmg;          // the single last blocker
        else perUnit[u.instId] = 0;                                   // untouched survivor
      });
    }
    return { chumps, prime: primeKey, untouched, perUnit };
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

  // chump-loss component (pre-credit) for the value-sanity tripwire (Finding B): Σ over damaged units of loss().
  // This is Σ_dead V + primeLoss with NO futureAbsorb / untouched-healer credit applied (the credits live
  // only in `best.loss`). Task-6 consumes it.
  const chumpLossComponent = (a) => {
    let s = 0;
    for (const g of groups) for (const u of g.units) {
      const d = a.perUnit[u.instId] || 0;
      if (d > 0) s += dv.loss(g.view, d, mode, ctx);
    }
    return s;
  };

  const assignment = toAssignment(best);
  return {
    assignment,
    perUnit: assignment.perUnit,   // convenience top-level mirror (== assignment.perUnit)
    loss: best.loss,
    tiedAlts,
    chumpLossComponent: chumpLossComponent(assignment),
  };
}

module.exports = { solveDefense };
