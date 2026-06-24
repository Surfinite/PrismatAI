'use strict';

// =============================================================================
// blockers.js — the ONE shared, canBlock-faithful blocker filter for the
// defense-eval harness. Both compare.js (the `ours` comparison runs) and
// validate_gate.js (the correctness gate) MUST feed `solveDefense` the same
// blocker set, or the gate validates a different code path than the harness runs.
// (compare.js previously had a permissive owner/alive/constructionTime/delay-only
// filter that let Drones/economy/tech non-blockers into the search — wrong metrics
// + a ~15s/game blowup. They drifted; this module makes that impossible.)
//
// Moved VERBATIM from validate_gate.js — behavior is byte-identical to its prior
// versions.
// =============================================================================

const dv = require('./defense_value');

// -----------------------------------------------------------------------------
// canBlockState — faithful JS port of Card::canBlock() (PrismataAI-dave-master/
// source/engine/Card.cpp:478-505). The engine's BlockIterator only ever considers
// units for which canBlock() is true (BlockIterator.cpp:21), so the sim MUST be fed
// exactly that set or it will block iso-classes the engine cannot (e.g. an Animus
// with defaultBlocking=0, or a tapped role=assigned Drone with assignedBlocking=0).
//
//   getType().canBlock(status==Assigned)   -> assigned ? assignedBlocking : defaultBlocking
//                                              (CardType.cpp:336-346; flags default false)
//   getCurrentDelay() > 0                   -> excluded
//   isUnderConstruction()                   -> constructionTime > 0 excluded
//   isDead()                                -> deadness != 'alive' excluded
//   isFrozen()  (currentChill >= currentHealth, Card.cpp) -> excluded
// -----------------------------------------------------------------------------
function canBlockState(u, ct) {
  if (!ct) return false;
  const assigned = (u.role === 'assigned');
  const typeCanBlock = assigned ? !!ct.assignedBlocking : !!ct.defaultBlocking;
  if (!typeCanBlock) return false;
  if ((u.delay | 0) > 0) return false;
  if ((u.constructionTime | 0) > 0) return false;
  if (u.deadness !== undefined && u.deadness !== 'alive') return false;
  const hp = (u.health !== undefined) ? u.health : (ct.toughness | 0);
  if ((u.disruptDamage | 0) >= hp) return false;   // isFrozen()
  return true;
}

// Available blockers for `player` at a defense State A, filtered exactly like the engine.
function availableBlockers(gs, player) {
  return (gs.table || []).filter(u => {
    if (u.owner !== player) return false;
    const v = dv.unitView(u);
    return canBlockState(u, v.ct);
  });
}

module.exports = { canBlockState, availableBlockers };
