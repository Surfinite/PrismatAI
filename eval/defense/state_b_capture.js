'use strict';
const Analyzer = require('../../js_engine/Analyzer');
const { buildInitInfo } = require('../replay_to_request');

function captureCommittedDefenses(replay) {
  const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
  const orig = analyzer.recordClick.bind(analyzer);
  const candidate = new Map();   // turnIndex -> { turnIndex, player, raw }  (last-write-wins)
  const committed = [];          // finalized at turn boundary

  analyzer.recordClick = function (u, d, type, id, params) {
    const prevPhase = analyzer.gameState.phase;
    const prevTurnIndex = analyzer.turnIndex;
    // capture by VALUE before the click mutates the live state (swoosh clears damage)
    let preSnap = null;
    try { preSnap = JSON.parse(analyzer.gameState.toString()); } catch (e) {}
    const r = orig(u, d, type, id, params);
    if (r && r.canClick) {
      // DEFENSE -> ACTION within the same turn = the swoosh; record/overwrite this turn's candidate
      if (preSnap && prevPhase === 'defense' && analyzer.gameState.phase === 'action'
          && analyzer.turnIndex === prevTurnIndex) {
        candidate.set(prevTurnIndex, { turnIndex: prevTurnIndex, player: (preSnap.turn % 2), raw: preSnap });
      }
      // turn boundary advanced -> the surviving candidate for prevTurnIndex is the committed defense
      if (analyzer.turnIndex !== prevTurnIndex && candidate.has(prevTurnIndex)) {
        committed.push(candidate.get(prevTurnIndex));
        candidate.delete(prevTurnIndex);
      }
    }
    return r;
  };

  try { analyzer.loaderInit(); } catch (e) { /* faithful-failure replays: skip, see corpus_scan */ }

  // flush any candidate that survived to game end (last turn never advances the index)
  for (const v of candidate.values()) committed.push(v);

  // raw is already toString of the cpp gameState (the same shape oracle_diff.js relies on),
  // captured PRE-swoosh so per-unit `damage` and the iso fields (disruptDamage/deadness/delay/
  // constructionTime/role + health/charge/lifespan/instId/owner/cardName) are all preserved.
  return committed.map(c => ({
    turnIndex: c.turnIndex,
    player: c.player,
    gameState: c.raw,
  }));
}

module.exports = { captureCommittedDefenses };
