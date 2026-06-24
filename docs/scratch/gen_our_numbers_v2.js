'use strict';
/*
 * gen_our_numbers_v2.js — v2 functional value: ADDITIVE body-floor + production.
 *   value = block_floor + production
 *   block_floor = HP*BV  (PERMANENT one-soak floor; lifespan==1 -> 0 free terminal chump)
 *   production by type:
 *     pure-block : 0
 *     auto-attack: net * perpetuity              (attacks AND blocks every turn, no tap -> NO penalty)
 *     click      : net * (perpetuity-1) + THREAT (taps -> forgoes the ONE death-eve attack it soaks on;
 *                                                 that forgone attack still THREATENS -> +THREAT residual)
 *     charge     : net * geom(charges)           (charges are a preserved STOCK -> NO death-eve penalty)
 *     doomed clk : net * geom(life-1) + THREAT   (finite; geom(life-1) already excludes the soak turn)
 *   net = (attack per activation)*ATK - ability cost (WILL). penalty & threat SCALE with the click's attack via net.
 *   block & atk columns are CONTRIBUTIONS to value (block=floor, atk=production); they sum to value. Run: node ...
 */
const fs = require('fs');
const LIB = 'c:/libraries/PrismataAI-dave-master/bin/asset/config/cardLibrary.jso';
const SHEET = 'c:/libraries/PrismataAI/docs/community_stats/math_analysis/sheet_Units.csv';
const OUT = 'c:/libraries/PrismataAI/docs/scratch/our_numbers_v2.md';
const lib = JSON.parse(fs.readFileSync(LIB, 'utf8'));

// ===================== TUNABLE CONSTANTS =====================
const BV = 2.2;     // block value per HP (one soak); blocker cost/HP w/ grounded resources (Wall 2.22, EM 2.27, Aegis 2.0)
const ATK = 2.0;    // value of 1 attack PRODUCED (community; pending an attacker-producer derivation)
const R = 4 / 3;    // interest rate: Wall-vs-IG promptness AND producer amortization BOTH give 4/3
const RES = { gold: 1, green: 4 / 3, blue: 5 / 3, red: 1, energy: 0.3 }; // green/blue/red PRODUCER-derived = gold-cost/(output x 1/(R-1)=3) [Conduit/Blastforge/Animus]. energy: NOT a clean producer value — the Engineer's 1HP body shares its 2g cost (body-adjusted estimate ~0.1; producer-naive 0.667). 0.3 = hedged starting point; real value is board-dependent (ability-usable gate, later).
const THREAT = 0.1; // residual value of a click-attacker's held-back (forgone-to-soak) attack, PER attack point (x abA). TUNABLE.
const OPT_SELFSAC_ATK = 0.2;   // optionality bonus for a self-sac unit whose burst is ATTACK (Nitrocybe/Protoplasm/Photonic). TUNABLE. (§4.4: 1.0→0.2)
const OPT_SELFSAC_TOKEN = 0.1; // optionality bonus for a self-sac unit whose burst is TOKENS (Infusion Grid) — smaller. TUNABLE. (§4.4: 0.5→0.1)
const DOOMED_NUDGE = 0.1; // small per-step doomed keep-value haircut (§4.4: lifespan>=2 only)
const CHILL_COEFF = 0.5;       // chill point valued as CHILL_COEFF x an attack point; forces one defense (flat, board-aware later). TUNABLE.
const UNDEF_PER_HP = 0.5;      // undefendable haircut: lose this much BLOCK value per HP (opponent can kill it directly). TUNABLE.
const FRAGILE_PEN = 0.1;       // fragile flat BLOCK haircut (differentiates e.g. Forcefield from a ch0-Rhino). TUNABLE.
// ============================================================

const f2 = x => +x.toFixed(2);
const geom = n => (1 - Math.pow(1 / R, n)) / (1 - 1 / R);        // sum_{t=0}^{n-1} (1/R)^t  (finite)
const geomPerp = period => 1 / (1 - Math.pow(1 / R, period));    // perpetual, attack every `period` turns

function parseCost(cost) { const r = { gold: 0, green: 0, blue: 0, red: 0, energy: 0, attack: 0 }; let n = ''; for (const c of String(cost || '')) { if (c >= '0' && c <= '9') n += c; else if (c === 'G') r.green++; else if (c === 'B') r.blue++; else if (c === 'C') r.red++; else if (c === 'H') r.energy++; else if (c === 'A') r.attack++; } r.gold = n ? parseInt(n, 10) : 0; return r; }
function costWill(s) { const r = parseCost(s); return r.gold * RES.gold + r.green * RES.green + r.blue * RES.blue + r.red * RES.red + r.energy * RES.energy; }
function attackOf(s) { return s && s.receive ? (String(s.receive).match(/A/g) || []).length : 0; }

// value of CREATED tokens. own = +ours().v (full value, a fresh defender of ours); opponent = −block-floor (a fresh
// blocker for THEM, ignoring our lifespan-1→0 rule — that only zeroes a token from the DEFENDER's PoV). Each token is
// discounted (1/R)^buildTime: a created producer isn't online until next turn (the Sentinel→Engineer one-turn delay).
// Own tokens are valued WITHOUT their own create (noCreate=true) so a self-creator (Ossified Drone) can't infinite-loop.
function createValue(arr) {
    if (!Array.isArray(arr)) return 0;
    let s = 0;
    for (const e of arr) {
        const u = lib[e[0]]; if (!u) continue;
        const owner = e[1] || 'own', count = e[2] || 1, bt = (e[3] !== undefined) ? e[3] : resolveBT(u);
        const disc = Math.pow(1 / R, bt);
        if (owner === 'opponent') s -= count * (u.toughness || 1) * BV * disc;
        else { const ov = ours(u, undefined, true); s += count * (ov && ov.v != null ? ov.v : (u.toughness || 0) * BV) * disc; }
    }
    return s;
}

// ---- RAW value (additive body-floor + production), BEFORE the undef/fragile haircuts (those are applied in ours()). ----
function coreValue(c, stateOverride, noCreate) {
    // stateOverride: { hp, charge, life } overrides the card's nominal toughness/charge/lifespan for the value PICKER.
    // Backward-compat shim: a numeric override is the legacy charge-override (`ours(c, 2)`).
    const _ov = (typeof stateOverride === 'number') ? { charge: stateOverride } : (stateOverride || {});
    const _hp  = _ov.hp     !== undefined ? _ov.hp     : c.toughness;
    const _chg = _ov.charge !== undefined ? _ov.charge : c.charge;
    const _rem = _ov.life   !== undefined ? _ov.life   : c.lifespan;
    // Heal: the table is BUY-state, but the value reflects the implementation rule — effective soak HP = current HP + one
    // heal, capped at max (a healer self-repairs across the soak window, so it absorbs more than its starting bar).
    const heal = c.HPGained || 0, hpMax = (c.HPMax !== undefined) ? c.HPMax : c.toughness;
    const soakHP = heal > 0 ? Math.min(_hp + heal, hpMax) : _hp;
    const HP = _hp, ab = c.abilityScript, bt = c.beginOwnTurnScript;
    let body = soakHP * BV;
    const abA = attackOf(ab), btA = attackOf(bt);
    const life = _rem, doomed = life !== undefined;
    // doomed keep-value nudge: lifespan==1 stays 0 (handled by the terminal branch); lifespan>=2 gets a small haircut
    const _maxLife = c.lifespan;          // nominal/max lifespan from the card
    const _remLife = _rem;                // current remaining lifespan (== nominal in table mode; overridden in state mode)
    if (_maxLife !== undefined && _remLife >= 2) {
        body -= DOOMED_NUDGE * (1 + _maxLife - _remLife);
    }
    const hpFunded = c.HPUsed !== undefined; // HP-funded ability (Xaetron: pay 7HP → 5 Flame Kin) — user ruling: ignore the click, treat as block
    const mods = []; if (doomed) mods.push('life=' + life); if (heal > 0 || c.HPMax) mods.push('heal→' + soakHP);
    const abCreateArr = (!hpFunded && ab && Array.isArray(ab.create)) ? ab.create : null;
    const btCreateArr = (bt && Array.isArray(bt.create)) ? bt.create : null;
    const abCreate = (!noCreate && abCreateArr) ? createValue(abCreateArr) : 0;
    const btCreate = (!noCreate && btCreateArr) ? createValue(btCreateArr) : 0;
    const hasCreate = !hpFunded && (abCreateArr || btCreateArr);
    // ---- chill (disrupt): body + flat "force one extra defense" premium. Board-aware later; chill point ≈ CHILL_COEFF attack. ----
    if (c.targetAction === 'disrupt') {
        const premium = (c.targetAmount || 0) * ATK * CHILL_COEFF;
        return { v: f2(body + premium), type: 'chill', flags: mods.concat('chill' + (c.targetAmount || 0)).join(','), block: f2(body), atk: f2(premium), rule: 'block+chill' };
    }
    // ---- drone-kill (netherfy): body + denied enemy-drone PRODUCTION (Plasmafier-style, but a BONUS not a cost). Deadeye = charge. ----
    if (c.abilityNetherfy) {
        const drone = lib['Drone'], denied = drone ? (ours(drone).atk || 0) : 0;
        const net = denied - costWill(c.abilityCost) - abilitySacWill(c);
        const ch = _chg === undefined ? 0 : _chg;
        const stream = net > 0 ? (c.charge ? net * geom(ch) : net * (geomPerp(1) - 1)) : 0;
        if (c.charge) mods.unshift('charge=' + ch);
        return { v: f2(body + stream), type: `drone-kill${c.charge ? `(x${ch})` : ''}`, flags: mods.join(','), block: f2(body), atk: f2(stream), rule: 'block+kill' };
    }
    // ---- self-sac-burst: block OR burst (mutually exclusive → max), plus an optionality bonus. ----
    if ((ab && ab.selfsac) || (bt && bt.selfsac)) {
        const sclick = !!(ab && ab.selfsac), s = sclick ? ab : bt;
        const tokens = Array.isArray(s.create) ? createValue(s.create) : 0;
        let burst = attackOf(s) * ATK + costWill(s.receive) + tokens - abilitySacWill(c);
        if (sclick) burst -= costWill(c.abilityCost);
        const isToken = Array.isArray(s.create);
        const opt = isToken ? OPT_SELFSAC_TOKEN : OPT_SELFSAC_ATK;
        const v = Math.max(body, burst) + opt;
        const word = isToken ? 'convert' : 'burst'; // IG (token) "converts" its body into Houses; atk-sac "bursts"
        return { v: f2(v), type: 'self-sac', flags: mods.concat(`${word}=${f2(burst)},opt=${opt}`).join(','), block: f2(body), atk: f2(v - body), rule: `max(block,${word})+opt` };
    }
    // ---- terminal lifespan (dies THIS turn regardless → free chump) ----
    if (life === 1) return { v: 0, type: 'pure-block', flags: 'life=1', block: 0, atk: 0, rule: 'terminal→0' };
    // ---- economy (resource producer). body + production stream; NO threat. Ossified Drone = econ + a ONE-SHOT self-create click. ----
    const resProd = s => (s && s.receive && /[0-9GBCH]/.test(String(s.receive))) ? costWill(s.receive) : 0;
    const autoEcon = resProd(bt), clickEcon = resProd(ab);
    if (abA === 0 && btA === 0 && (autoEcon > 0 || clickEcon > 0)) {
        const oneClick = abCreate ? Math.max(0, abCreate - costWill(c.abilityCost) - abilitySacWill(c)) : 0; // model the create click ONCE (red runs out)
        if (autoEcon > 0) { // passive producer (Engineer): no tap -> no penalty
            const stream = autoEcon * (doomed ? geom(life) : geomPerp(1));
            return { v: f2(body + stream + oneClick), type: oneClick ? 'economy-auto+create' : 'economy-auto', flags: mods.join(','), block: f2(body), atk: f2(stream + oneClick), rule: oneClick ? 'block+econ+create×1' : 'block+econ' };
        }
        const attacks = doomed ? geom(life - 1) : (geomPerp(1) - 1);
        const stream = clickEcon * attacks;
        return { v: f2(body + stream + oneClick), type: oneClick ? 'economy-click+create' : 'economy-click', flags: mods.join(','), block: f2(body), atk: f2(stream + oneClick), rule: doomed ? 'block+econ(doom)' : 'block+econ' };
    }
    // ---- pure block (no attack, no token creation, no usable ability) ----
    if (abA === 0 && btA === 0 && !hasCreate) return { v: f2(body), type: 'pure-block', flags: mods.join(','), block: f2(body), atk: 0, rule: 'block' };
    // ---- auto stream (begin-turn fire: attack + auto-created tokens), no tap -> no penalty. May coexist with a click ability. ----
    let autoStream = 0;
    const btProd = btA * ATK + btCreate;
    const hasClick = abA > 0 || !!abCreateArr && !hpFunded;
    if (btProd > 0) {
        autoStream = btProd * (doomed ? geom(life) : geomPerp(1));
        if (!hasClick)
            return { v: f2(body + autoStream), type: btCreate ? `auto-create` : `auto-atk(${btA})`, flags: mods.join(','), block: f2(body), atk: f2(autoStream), rule: 'block+auto' };
    }
    // ---- charge / click: production per activation = attack + created tokens, less mana + sacrificed-unit PRODUCTION. ----
    if (Array.isArray(c.abilitySac)) mods.unshift('sac:' + c.abilitySac.map(e => e[0]).join('+'));
    const abProd = abA * ATK + abCreate;
    const net = abProd - costWill(c.abilityCost) - abilitySacWill(c);
    const label = abCreate ? `create(${abA}A)` : `click-atk(${abA})`;
    if (c.charge) {
        const ch = _chg === undefined ? c.charge : _chg;
        const T = doomed ? Math.min(ch, life - 1) : ch;
        const stream = (ch > 0 && net > 0) ? net * geom(T) : 0;
        mods.unshift('charge=' + ch);
        return { v: f2(body + autoStream + stream), type: `${autoStream ? `auto(${btA})+` : ''}charge-${label}`, flags: mods.join(','), block: f2(body), atk: f2(autoStream + stream), rule: autoStream ? 'block+auto+charge' : 'block+charge' };
    }
    let attacks, ruleTag;
    if (doomed) {
        attacks = geom(life - 1); ruleTag = 'block+doomed';
    } else {
        const period = (ab && ab.delay) ? ab.delay : 1; if (period > 1) mods.push('exhaust' + period);
        attacks = geomPerp(period) - 1; ruleTag = period > 1 ? 'block+click/' + period : 'block+click';
    }
    if (net <= 0) return { v: f2(body + autoStream), type: `${autoStream ? `auto(${btA})+` : ''}${label}`, flags: mods.join(','), block: f2(body), atk: f2(autoStream), rule: autoStream ? 'block+auto' : 'block(atk≤0)' };
    const prod = net * attacks + THREAT * abA; // production premium; one death-eve attack removed, threat residual (scales w/ ATTACK only) added
    return { v: f2(body + autoStream + prod), type: `${autoStream ? `auto(${btA})+` : ''}${label}`, flags: mods.join(','), block: f2(body), atk: f2(autoStream + prod), rule: autoStream ? 'block+auto+click' : ruleTag };
}

// ---- ours() = coreValue, then apply the undefendable / fragile haircuts (both reduce BLOCK reliability, keeping block+atk = v). ----
// stateOverride: { hp, charge, life } values the unit at its CURRENT game-state (else nominal); a numeric arg is the legacy charge override.
function ours(c, stateOverride, noCreate) {
    const r = coreValue(c, stateOverride, noCreate);
    if (r.v == null) return r;
    let block = +r.block; const hit = [];
    if (c.undefendable) { const h = UNDEF_PER_HP * (c.toughness || 0); block -= h; hit.push(`undef−${f2(h)}`); }
    if (c.fragile) { block -= FRAGILE_PEN; hit.push('fragile−' + FRAGILE_PEN); }
    if (hit.length) { r.block = f2(block); r.v = f2(block + (+r.atk)); r.flags = (r.flags ? r.flags + ',' : '') + hit.join(','); }
    return r;
}

// value of units sacrificed per ability activation (Odin sacs a Treant, Plasmafier a Drone) -> netted vs the attack stream, perpetually.
// Use the sacced unit's PRODUCTION term only (atk), NOT its body: a unit fed to a sac engine is an attacker/economy unit, not a prompt
// defender, so its soak is ~10 turns away -> (1/R)^10 ~ 0 under our own promptness discount. You forgo its production, not its body.
function abilitySacWill(c) {
    if (!Array.isArray(c.abilitySac)) return 0;
    let s = 0;
    for (const e of c.abilitySac) { const u = lib[e[0]]; if (!u) continue; const ov = ours(u); s += (e[1] || 1) * (ov && ov.atk != null ? ov.atk : 0); }
    return s;
}

// ---- references: C++, Q, sheet ----
function willScoreCpp(c) { const r = parseCost(c); return r.gold + r.green * 1.2 + r.blue * 1.5 + r.red * 0.9 + r.energy * 0.5 + r.attack * 2.25; }
function inflCpp(bt) { return bt === 0 ? 1 / 1.13 : Math.pow(1.28, bt - 1); }
function resolveBT(c) { return c.spell !== undefined ? 0 : (c.buildTime === undefined ? 1 : c.buildTime); }
function blockOnlyC(c) { return !c.abilityScript && !c.targetAction; }
function buySac(c) { if (!Array.isArray(c.buySac)) return 0; let s = 0; for (const e of c.buySac) { const u = lib[e[0]]; if (u) s += (e[1] || 1) * willScoreCpp(u.buyCost); } return s; }
function cpp(c) { if (c.lifespan === 1) return 0; if ((c.UIName || '') === 'Forcefield') return 3.75; if (c.toughness === 1 && blockOnlyC(c)) return 1.875; const b = blockOnlyC(c) ? willScoreCpp(c.buyCost) : willScoreCpp(c.buyCost) + buySac(c); return f2(b * inflCpp(resolveBT(c))); }
const QVAL = [3, 4, 5, 3, 2, 6];
function qValue(c, name, h, ch, ls, cardLs) {
    const g1 = new Set(['Husk', 'Wall', 'Infusion Grid', 'Tough Barrier', 'Mini Barrier']);
    if (g1.has(name) || (name === 'Corpus' && ch === 0) || (name === 'Rhino' && ch === 0) || (name === 'Deadeye Operative' && ch === 0) || (name === 'Bombarder' && ch === 0)) return h * (7 - (h - 1) / 4000000) + (name === 'Infusion Grid' ? 1e-9 : 0);
    if (name === 'Doomed Wall') return 23 + ls;
    if (name === 'Forcefield' || name === 'Aegis' || (name === 'Tia Thurnax' && ch === 0) || (name === 'Sentinel' && ch === 0)) return h * (7 - (h - 1) / 8);
    if (name === 'Innervi Field') return (h + (ls === 1 ? 0 : 1)) * (7 - (h - (ls === 1 ? 1 : 0)) / 8);
    if (name === 'Engineer') return 7.3; if (name === 'Drone') return 11;
    if (name === 'Rhino' && ch > 0) return 18 + ch / 3; if (name === 'Bombarder') return 35 + ch * 7;
    if (name === 'Corpus' && ch > 0) return 16 + ch / 3; if (name === 'Ossified Drone') return 17;
    if (name === 'Steelsplitter') return 26; if (name === 'Cauterizer') return 27; if (name === 'Urban Sentry') return 28.01;
    if (name === 'Borehole Patroller') return 23; if (name === 'Tia Thurnax' && ch > 0) return 78; if (name === 'Redeemer') return 68;
    if (name === 'Centurion') return 77; if (name === 'Xaetron') return h * 8 + 21; if (name === 'Chieftain') return Math.max(h * 6.9, (ls - 1) * 2 * 6.2);
    const r = parseCost(c.buyCost); const amt = [r.gold, r.green, r.blue, r.red, r.energy, r.attack]; let conv = 0; for (let i = 0; i < 6; i++) conv += QVAL[i] * amt[i];
    let lsAdj = 1; if (ls === 2) lsAdj = 0.7; else if (cardLs > 0 && ls < cardLs) lsAdj = 0.8 + 0.2 * (ls - 2) / (cardLs - 2);
    return conv * Math.pow(1.28, resolveBT(c)) * lsAdj;
}
function Q(c, name) { return f2(qValue(c, name, c.toughness, c.charge || 0, c.lifespan === undefined ? -1 : c.lifespan, c.lifespan)); }
function csvLine(line) { const o = []; let cur = '', q = false; for (let i = 0; i < line.length; i++) { const ch = line[i]; if (q) { if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; } else { if (ch === ',') { o.push(cur); cur = ''; } else if (ch === '"') q = true; else cur += ch; } } o.push(cur); return o; }

if (require.main === module) {
const sheet = {};
for (const line of fs.readFileSync(SHEET, 'utf8').split(/\r?\n/).slice(1)) { if (!line.trim()) continue; const f = csvLine(line); const nm = (f[0] || '').trim(); if (!nm) continue; const num = x => { const v = parseFloat(x); return isNaN(v) ? '' : f2(v); }; sheet[nm] = { def: num(f[3]), tot: num(f[5]) }; }
// ---- build ----
const inscope = [], deferred = [];
for (const [k, c] of Object.entries(lib)) {
    if (c.defaultBlocking !== 1) continue;
    const name = c.UIName || k, o = ours(c), s = sheet[name] || {}, qv = Q(c, name);
    const row = { name, hp: c.toughness, ...o, q: qv, qr: (o.v > 0 ? f2(qv / o.v) : null), cpp: cpp(c), sdef: s.def === undefined ? '?' : s.def, stot: s.tot === undefined ? '?' : s.tot };
    (o.defer ? deferred : inscope).push(row);
}
inscope.sort((a, b) => a.v - b.v || a.hp - b.hp);
deferred.sort((a, b) => a.cpp - b.cpp);

let md = `# Our numbers — v2 (additive body-floor + production; expect iteration)

> \`docs/scratch/gen_our_numbers_v2.js\`. **Grounded constants:** BV=${BV}/HP · ATK=${ATK}/pt · R=4/3≈${f2(R)} · THREAT=${THREAT}/atk · P=perpetuity=1/(1−1/R)=${f2(geomPerp(1))}.
> Resources (WILL): gold 1 · green ${f2(RES.green)} (Conduit) · blue ${f2(RES.blue)} (Blastforge) · red ${RES.red} (Animus) — **producer-derived** = gold-cost/(output × 1/(R−1)=3). energy ${f2(RES.energy)} = **hedged** (Engineer's body shares its 2g cost; body-adjusted ~0.1, naive 0.667; real value board-dependent).
> **value = block_floor + production.** block_floor = HP·BV (PERMANENT; lifespan==1→0). net = attack·ATK − abilityCost − **abilitySac PRODUCTION** (Odin→Treant, Plasmafier→Drone; body excluded — the sacced unit isn't a prompt defender, ~10-turn soak ≈ 0).
> production: **auto** = net·P (no tap/penalty) · **click** = net·(P−1)+THREAT·atk (taps → forgoes the one death-eve soak attack; threat residual) ·
> **charge** = net·geom(ch) (preserved STOCK → no penalty) · **doomed** = net·geom(life−1)+THREAT·atk · **economy** = resource·{auto P / click P−1}.
> **block**/**atk** columns sum to **OURS**. Charge units at FULL charge (per-charge breakdown + convergence below).
> **New mechanics (tunable):** self-sac = max(block,burst)+opt (atk-burst ${OPT_SELFSAC_ATK} / token-burst ${OPT_SELFSAC_TOKEN}) · token-spawn = production stream of created tokens (own = +ours(token), discounted by build-time; opponent = −block) · chill = +targetAmount·ATK·${CHILL_COEFF} (flat, board-aware later) · drone-kill = +denied-drone PRODUCTION (Deadeye charge) · **undef −${UNDEF_PER_HP}/HP block** · **fragile −${FRAGILE_PEN} block**. Heal: effective soak HP = **current HP + one heal, capped at max** (buy-state in the table; matches the impl rule). Xaetron's HP-funded click ignored (→pure block).

## In-scope — sorted by OURS
| Unit | HP | type | flags | block | atk | rule | **OURS** | Q | Q/O | C++ | sDef | sTot |
|---|--:|---|---|--:|--:|---|--:|--:|--:|--:|--:|--:|
`;
for (const r of inscope) md += `| ${r.name} | ${r.hp} | ${r.type} | ${r.flags || ''} | ${r.block} | ${r.atk} | ${r.rule} | **${r.v}** | ${r.q} | ${r.qr == null ? '—' : r.qr} | ${r.cpp} | ${r.sdef} | ${r.stot} |\n`;

// Q/OURS spread: mean + the units furthest from it (these need a justification)
const rr = inscope.filter(r => r.qr != null).map(r => ({ name: r.name, qr: r.qr }));
const mean = f2(rr.reduce((a, r) => a + r.qr, 0) / rr.length);
const sorted = [...rr].sort((a, b) => a.qr - b.qr);
const lo = sorted.slice(0, 4).map(r => `${r.name} ${r.qr}`).join(', ');
const hi = sorted.slice(-4).reverse().map(r => `${r.name} ${r.qr}`).join(', ');
md += `\n> **Q/O ratio: mean ${mean}** (Q ≈ ${mean}× OURS on average). **Lowest** (OURS rich vs Q): ${lo}. **Highest** (OURS lean vs Q): ${hi}. Outliers from the mean are the rows to justify.\n`;

md += `\n## Charge breakdown (ch0=spent .. full)\n| Unit | ch0 | ch1 | ch2 | ch3 |\n|---|---|---|---|---|\n`;
for (const [k, c] of Object.entries(lib)) {
    if (c.defaultBlocking !== 1 || !(c.charge > 0 && c.abilityScript && attackOf(c.abilityScript) > 0)) continue;
    if (Array.isArray(c.abilityScript.create)) continue; // Sentinel etc. are charge-CREATORS, not pure attack-charge
    const name = c.UIName || k; const cells = [];
    for (let ch = 0; ch <= c.charge; ch++) cells.push(ours(c, ch).v);
    while (cells.length < 4) cells.push('');
    md += `| ${name} | ${cells.join(' | ')} |\n`;
}

md += `\n## Convergence check (charge ch→∞ vs the equivalent perpetual click)\n`;
md += `Charges are a preserved STOCK (no death-eve penalty), so a charge unit at ch→∞ converges to **body + net·P** — which sits ~1 net-attack ABOVE the equivalent **perpetual click** (which pays the death-eve −1). That gap is the stock-vs-flow distinction (a held-back charge is never lost; a perpetual click forgoes its soak-turn attack).\n\n`;
md += `| Unit | ch2 | ch5 | ch10 | ch50 | ch∞ (=body+net·P) | perp-click (=body+net·(P−1)+THREAT) |\n|---|--:|--:|--:|--:|--:|--:|\n`;
for (const [k, c] of Object.entries(lib)) {
    if (c.defaultBlocking !== 1 || !(c.charge > 0 && c.abilityScript && attackOf(c.abilityScript) > 0)) continue;
    if (Array.isArray(c.abilityScript.create)) continue; // pure attack-charge units only
    const name = c.UIName || k, bodyV = c.toughness * BV, abA = attackOf(c.abilityScript);
    const net = abA * ATK - costWill(c.abilityCost);
    const asymCharge = bodyV + (net > 0 ? net * geomPerp(1) : 0);
    const perpClick = bodyV + (net > 0 ? net * (geomPerp(1) - 1) + THREAT : 0);
    md += `| ${name} | ${ours(c, 2).v} | ${ours(c, 5).v} | ${ours(c, 10).v} | ${ours(c, 50).v} | ${f2(asymCharge)} | ${f2(perpClick)} |\n`;
}
const ev = lib['Fickle Marine']; // Electrovore = perpetual paid click(1)
if (ev) md += `\n_Electrovore (perpetual **paid** click-1, nets the energy) = **${ours(ev).v}**. A FREE 1A charge unit at ch∞ lands above it (free + stock: no cost, no death-eve penalty)._\n`;

if (deferred.length) {
    md += `\n## Still deferred (keep current C++) — sorted by C++\n| Unit | HP | type | Q | C++ | sDef | sTot |\n|---|--:|---|--:|--:|--:|--:|\n`;
    for (const r of deferred) md += `| ${r.name} | ${r.hp} | ${r.type} | ${r.q} | ${r.cpp} | ${r.sdef} | ${r.stot} |\n`;
} else {
    md += `\n## Still deferred\n_None — every defaultBlocking type is now modeled (chill / drone-kill / self-sac / token-spawn / heal folded in). The board-aware layer (chill tax, drone-denial value, ability-usable gate) and the undef magnitude remain TUNABLE._\n`;
}

fs.writeFileSync(OUT, md);
console.log(`wrote ${OUT}: ${inscope.length} in-scope, ${deferred.length} deferred`);
}

module.exports = {
  ours, parseCost, costWill, attackOf, geom, geomPerp, lib,
  willScoreCpp, inflCpp, resolveBT, buySac,   // C++ DamageLoss_WillCost helpers (reused by eval/defense/defense_value.js lossCpp)
  CONSTANTS: { BV, ATK, R, RES, THREAT, OPT_SELFSAC_ATK, OPT_SELFSAC_TOKEN, DOOMED_NUDGE, CHILL_COEFF, UNDEF_PER_HP, FRAGILE_PEN },
};
