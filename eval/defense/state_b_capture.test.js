'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const cap = require('./state_b_capture');
const { loadJSON } = require('../replay_to_request');

test('captures one committed defense per attacked turn, undo-collapsed', () => {
  const code = 'FIm28-4p1PP';
  const fp = require('./_find_replay').find('c:/libraries/prismata-replay-parser/replays_archive', code);
  const replay = loadJSON(fp);
  const defenses = cap.captureCommittedDefenses(replay);
  assert.ok(Array.isArray(defenses));
  assert.ok(defenses.length > 0, 'should capture at least one committed defense');
  for (const d of defenses) {
    assert.equal(typeof d.turnIndex, 'number');
    assert.ok(d.player === 0 || d.player === 1);
    assert.ok(d.gameState && Array.isArray(d.gameState.table));
  }
});
