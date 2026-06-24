'use strict';
const Analyzer = require('../../js_engine/Analyzer');
const { buildInitInfo } = require('../replay_to_request');

// captureCommittedDefenses(replay) -> [{ turnIndex, player, gameState }]
//
// State B = the COMMITTED pre-swoosh defense board for each turn that ended a defense.
// We use the Analyzer's NATIVE replay-navigation API instead of monkeypatching recordClick
// and deep-cloning the whole board on every click (which OOM'd on long replays):
//
//   * loaderInit() replays the whole game and populates `endDefenses` — a Vector.<int> of click
//     indices, one per COMMITTED defense (undo-robust: a re-defend pops the stale entry and
//     re-pushes, Analyzer.js:348-355). It is seeded with a leading 0 and a trailing 2147483647
//     sentinel; the real entries are 0 < idx < numClicksInReplay.
//   * Each real entry is `numClicksInReplay - 1` at the moment the defense ended = the index of
//     the SWOOSH click. gotoCommand(idx) restores the containing turn-start and plays forward
//     applying clicks [0, idx) — i.e. it stops BEFORE the swoosh click — so the live gameState
//     lands on the committed PRE-swoosh board (per-unit `damage` still present, before swoosh
//     clears it), with analyzer.turnIndex set to the defending turn.
//
// Off-by-one: verified empirically against a 27-entry golden (FIm28-4p1PP) — gotoCommand(endDefenses[i])
// reproduces the old per-click-snapshot output EXACTLY (turnIndex, player, per-unit damage, iso keys).
// (offset -1 also matched on that replay, but endDefenses[i] is the documented/native boundary.)
//
// player convention: matches the old code (preSnap.turn % 2). The defending player is the active
// player at the pre-swoosh board; gameState.turn % 2 at the navigated state == old preSnap.turn % 2.
function captureCommittedDefenses(replay) {
  const analyzer = new Analyzer(buildInitInfo(replay), -1, -1, null);
  try { analyzer.loaderInit(); } catch (e) { return []; }  // faithful-failure replays: skip (corpus_scan)

  const N = analyzer.numClicksInReplay;
  // Real committed-defense indices: exclude the leading 0 + the 2147483647 sentinel.
  const indices = analyzer.endDefenses.filter(idx => idx > 0 && idx < N);

  const out = [];
  for (const idx of indices) {
    analyzer.gotoCommand(idx);                                  // -> committed PRE-swoosh board
    let gameState = null;
    try { gameState = JSON.parse(analyzer.gameState.toString()); } catch (e) { continue; }
    // gameState is the toString'd cpp board (the same shape oracle_diff.js relies on): per-unit
    // `damage` + the iso fields (disruptDamage/deadness/delay/constructionTime/role + health/
    // charge/lifespan/instId/owner/cardName) are all preserved.
    out.push({ turnIndex: analyzer.turnIndex, player: (gameState.turn % 2), gameState });
  }
  return out;
}

module.exports = { captureCommittedDefenses };
