'use strict';
const { test } = require('node:test');
const assert = require('node:assert');
const dv = require('./defense_value');
const sim = require('./defense_sim');
const mk = (name, over = {}) => Object.assign({ cardName: name, owner: 0 }, over);

// If the human plays EXACTLY the AI's chosen defense, regret must be 0 (symmetric credit, Finding A).
test('human credit is symmetric: identical defense -> regret 0', () => {
  // ACC1: Wall@3 + Rhino ch2, 4 dmg -> AI primes Wall, chumps Rhino.
  const board = [mk('Wall', { health: 3, instId: 1 }), mk('Rhino', { health: 2, charge: 2, instId: 2 })];
  const views = board.map(u => dv.unitView(u));
  const ai = sim.solveDefense(board, 4, 'ours');
  // human plays the same: Rhino dies (takes 2), Wall survives partial (takes 2).
  const humanPerUnit = { 1: 2, 2: 2 };
  // replicate compare.js's humanLossOurs WITH the symmetric-credit fix:
  let humanLoss = views.reduce((s, v) => s + dv.loss(v, humanPerUnit[v.instId] || 0, 'ours'), 0);
  const primeView = views.find(v => { const d = humanPerUnit[v.instId] || 0; return d > 0 && d < v.hp; });
  if (primeView) humanLoss -= dv.futureAbsorb(primeView);
  for (const v of views) { const d = humanPerUnit[v.instId] || 0; if (d === 0 && dv.isBelowMaxHealer(v)) humanLoss -= dv.untouchedHealerCredit(v); }
  assert.ok(Math.abs(humanLoss - ai.loss) < 1e-6, `human ${humanLoss} should equal AI ${ai.loss} for an identical defense`);
});
