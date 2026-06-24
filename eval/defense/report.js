'use strict';
function pct(x) { return (100 * x).toFixed(1) + '%'; }
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
  md += `| iso-class | ai-only chumped | human-only chumped |\n|---|--:|--:|\n`;
  for (const d of a.perUnitDivergence.slice(0, 30)) md += `| ${d.isoKey} | ${d.aiOnly} | ${d.humanOnly} |\n`;
  md += `\n## Tie-break skew (corrective-term candidates)\n`;
  md += `| iso-class pair | human lean |\n|---|---|\n`;
  for (const s of a.tieBreakSkew.slice(0, 30)) md += `| ${s.pair} | ${JSON.stringify(s.leans)} |\n`;
  return md;
}
module.exports = { renderReport };
