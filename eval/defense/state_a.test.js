'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const { execFileSync } = require('node:child_process');
const fs = require('fs'); const os = require('os'); const path = require('path');

const ARCHIVE = 'c:/libraries/prismata-replay-parser/replays_archive';

test('--defense-only emits only defense-phase states with incoming>0', () => {
  // FIm28-4p1PP is validated in the eval-pipeline handoff to have defense phases.
  const code = 'FIm28-4p1PP';
  const fp = require('./_find_replay').find(ARCHIVE, code);
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'defstateA_'));
  // replay_to_request.js arg order: <replay> <ply|--all> <outDir> [flags]
  execFileSync('node', ['eval/replay_to_request.js', fp, '--all', out, '--defense-only'], { cwd: process.cwd() });
  const files = fs.readdirSync(out).filter(f => f.endsWith('.json'));
  assert.ok(files.length > 0, 'should emit some defense states');
  for (const f of files) {
    const gs = JSON.parse(fs.readFileSync(path.join(out, f))).gameState;
    assert.equal(gs.phase, 'defense');
    assert.ok((gs.incomingAttack | 0) > 0, `expected incoming>0, got ${gs.incomingAttack}`);
  }
});
