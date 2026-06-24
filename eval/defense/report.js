'use strict';
const { lib } = require('../../docs/scratch/gen_our_numbers_v2.js');

function pct(x) { return (100 * x).toFixed(1) + '%'; }

// Display name for an internal codename, e.g. Hotel -> "Infusion Grid".
function displayName(internal) {
  const ct = lib[internal];
  return (ct && ct.UIName) ? ct.UIName : internal;
}

// Render a per-unit-value-key's differentiating attributes as separate cells.
// hp is always meaningful; charge/lifespan show '-' when not applicable.
function attrCells(d) {
  const hp = (d.hp === undefined || Number.isNaN(d.hp)) ? '-' : d.hp;
  const charge = (d.charge && d.charge > 0) ? d.charge : '-';
  const life = (d.lifespan && d.lifespan >= 1) ? d.lifespan : '-';
  return { hp, charge, life };
}

// Format citations "CODE@tN, CODE@tN" from a list of {replay, turn}.
function citeList(examples) {
  if (!examples || !examples.length) return '';
  return examples.map(e => `${e.replay}@t${e.turn}`).join(', ');
}

function renderReport(a) {
  let md = `# Defense-Eval Report\n\n**Positions:** ${a.n}\n\n`;
  md += `## Regret (primary)\n`;
  md += `| | mean | zero-regret |\n|---|--:|--:|\n`;
  md += `| ours | ${a.regret.mean_ours.toFixed(3)} | ${pct(a.regret.zeroRate_ours)} |\n`;
  md += `| current C++ | ${a.regret.mean_cpp.toFixed(3)} | ${pct(a.regret.zeroRate_cpp)} |\n\n`;
  md += `## Exact-match-iso / Prime-match\n`;
  md += `| | exact-match | prime-match |\n|---|--:|--:|\n`;
  md += `| ours | ${pct(a.exactMatch.ours)} | ${pct(a.primeMatch.ours)} |\n`;
  md += `| current C++ | ${pct(a.exactMatch.cpp)} | ${pct(a.primeMatch.cpp)} |\n\n`;

  md += `## Per-unit divergence (AI chumps/saves differently than humans)\n`;
  md += `| Unit | HP | Charge | Lifespan | ai-only chumped | human-only chumped | examples (ai-only / human-only) |\n`;
  md += `|---|--:|--:|--:|--:|--:|---|\n`;
  for (const d of a.perUnitDivergence.slice(0, 30)) {
    const c = attrCells(d);
    const ex = [citeList(d.examplesAi), citeList(d.examplesHuman)].filter(Boolean).join(' / ') || '-';
    md += `| ${displayName(d.internal)} | ${c.hp} | ${c.charge} | ${c.life} | ${d.aiOnly} | ${d.humanOnly} | ${ex} |\n`;
  }

  md += `\n## Tie-break skew (corrective-term candidates)\n`;
  md += `| Unit | HP | Charge | Lifespan | vs Unit | HP | Charge | Lifespan | human lean | examples |\n`;
  md += `|---|--:|--:|--:|---|--:|--:|--:|---|---|\n`;
  for (const s of a.tieBreakSkew.slice(0, 30)) {
    const [k1, k2] = s.pair.split('||');
    const d1 = s.decode[k1] || {};
    const d2 = s.decode[k2] || {};
    const c1 = attrCells(d1);
    const c2 = attrCells(d2);
    // human lean rendered by display name so codenames never appear
    const leans = Object.entries(s.leans).map(([k, v]) => `${displayName((s.decode[k] || {}).internal)}: ${v}`).join(', ');
    const ex = citeList(s.examples) || '-';
    md += `| ${displayName(d1.internal)} | ${c1.hp} | ${c1.charge} | ${c1.life} | ${displayName(d2.internal)} | ${c2.hp} | ${c2.charge} | ${c2.life} | ${leans} | ${ex} |\n`;
  }

  md += `\n## Tripwire (value-sanity)\n`;
  const tw = a.tripwire || { negMinLoss: 0, suspicious: [] };
  md += `Negative min-loss positions (loss < -0.001): **${tw.negMinLoss}**\n\n`;
  if (!tw.suspicious || !tw.suspicious.length) {
    md += `Suspicious (loss < -1): **0 suspicious (clean)**\n`;
  } else {
    md += `Suspicious (loss < -1): **${tw.suspicious.length}**\n\n`;
    md += `| replay | turn | loss |\n|---|--:|--:|\n`;
    for (const s of tw.suspicious) md += `| ${s.replay} | ${s.turn} | ${s.loss.toFixed(3)} |\n`;
  }
  return md;
}
module.exports = { renderReport };
