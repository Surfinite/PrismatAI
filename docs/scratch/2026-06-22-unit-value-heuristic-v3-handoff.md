---
title: "Unit-Value Heuristic — v3 Functional-Value Handoff (RESUME HERE)"
date: 2026-06-22
status: active
summary: "Framework converged + grounded constants locked; generator implements the full model (additive body+production, charge-as-stock, click death-eve penalty + threat, promptness/R, producer-derived resources, economy, production-only abilitySac). NEXT = pending in-table mechanics (heal, fragile, Hannibull dual-stream), then deferred types, then holistic re-calibration, then C++ port."
owner: Surfinite
engine: "PrismataAI-dave-master @ dave-master-jsonclean (engine_v1, the strong engine; NOT this repo's source/ = engine_v2, indicted)"
target_function: "Heuristics::DamageLoss_WillCost at PrismataAI-dave-master/source/ai/Heuristics.cpp line 158, plus the HeuristicValues cost tables"
supersedes: "docs/scratch/2026-06-20-unit-value-heuristic-v2-handoff.md"
supersedes_note: "that doc's max()/optimal-stopping model and its section-4 divide-by-HP next-step are BOTH wrong; see this doc section 10"
model_file: "docs/scratch/gen_our_numbers_v2.js"
model_output: "docs/scratch/our_numbers_v2.md"
run_command: "node docs/scratch/gen_our_numbers_v2.js"
working_scale: "WILL-ish; only ordering and relative sizes matter, absolute scale is free; constants are grounded (derived), not arbitrary"
engine_cpp_touched: false
---

# Unit-Value Heuristic — v3 Handoff (RESUME HERE)

## 0. TL;DR / how to resume

We are redesigning the C++ AI's defensive chump/soak value (`Heuristics::DamageLoss_WillCost`) so a unit's value reflects
**functional worth** (what production you forgo when it dies soaking) instead of inflated buy cost. The **model shape and
all constants have converged and are grounded**. The generator `docs/scratch/gen_our_numbers_v2.js` is the live model;
run it to regenerate `docs/scratch/our_numbers_v2.md`.

**To resume:** read §1 (scope), §2 (constants), §3 (the model — exact formulas), §4 (generator), §6 (the pending
in-table mechanics: heal, fragile, Hannibull dual-stream — the immediate next work), §7 (deferred types), §9 (locked —
don't relitigate). Then implement the §6 mechanics in `gen_our_numbers_v2.js`, regenerate, eyeball ordering. Work is
collaborative + iterative: present numbers, take corrections one at a time, don't jump to a spec or C++.

## 1. Mission & scope

- Improve `DamageLoss_WillCost` (defense-side chump/soak loss) so it uses functional value. This is the **C++ heuristic, NOT the DSNN**.
- **Defense semantics only.** The value = "what you lose when this unit DIES taking damage (a soak/chump)". Survivors contribute 0
  in the engine; the prime absorber is a SEPARATE decision (BlockIterator keeps a surviving prime, chumps the rest).
- **Consumer scope (from the VERIFIED surface map, `docs/scratch/2026-06-19-unit-value-surface-map-VERIFIED.md`):** route a NEW
  `Heuristics::DefensiveValue` to consumers **#1 Defense BlockIterator, #7 AttackDamageScenario, #8 CalculateWipeoutLoss,
  #9 CalculateEnemyNextTurnDefenseLoss** (all "value lost when a unit dies defending", ours + enemy-prediction). KEEP the old
  `DamageLoss_WillCost`/`CurrentCardValue` for **#3 breach, #4 frontline, #5 offensive snipe, #6 AvoidAttackWaste** (offense
  target-selection) and **#10-12 buy** (price basis). **#2 Defense_GreedyKnapsack is DEAD** (token `DefenseWillKnapsack` is
  defined at config.txt:131 but referenced by ZERO deployed chains; the only runtime instance is value-blind AITools prediction).
- Prefer **small, code-provable, low-regression** changes; willing to call a unit "a wash".

## 2. CONSTANTS (grounded — see provenance)

```json
{
  "BV": 2.2,            // block value per HP (one prompt soak). blocker cost/HP w/ grounded resources: Wall 2.22, EM 2.27, Aegis 2.0 (community gold-equiv 2.37)
  "ATK": 2.0,           // value of 1 attack produced. community; PENDING a clean attacker-producer derivation
  "R": 1.3333,          // = 4/3. interest/discount rate. derived TWO ways (both agree): Wall-vs-IG promptness; producer amortization
  "RES": { "gold": 1, "green": 1.3333, "blue": 1.6667, "red": 1.0, "energy": 0.3 },  // gold/green/blue/red PRODUCER-derived (={1,4/3,5/3,1}); energy=0.3 hedged (NOT producer-clean: Engineer's body shares its 2g cost; body-adjusted ~0.1, naive 0.667)
  "THREAT": 0.1,        // residual value of a click-attacker's forgone-to-soak attack, PER attack point (x abA)
  "P_onboard": 4.0,     // = geomPerp(1) = 1/(1-1/R). perpetuity for an ON-BOARD unit (produces THIS turn onward)
  "P_bought": 3.0       // = 1/(R-1). perpetuity for a freshly-BOUGHT producer (produces NEXT turn, bt1). used to PRICE resources
}
```

**Provenance (do NOT re-derive; verify with `docs/scratch/backcalc_resources.js`):**
- **R = 4/3**: Wall (3HP, `5B`, prompt bt0) vs Infusion Grid (4HP, `5B`, bt1) — identical cost ⇒ `3·BV = 4·BV/R` ⇒ R = 4/3.
  Independently, producer amortization (below) only matches community at perpetuity 3 = 1/(R−1), i.e. R = 4/3. Both agree.
- **Resources from PRODUCERS** (gold-cost / (per-turn output × P_bought=3)):
  Blastforge 5g→1 blue ⇒ blue = 5/3 = 1.667 · Conduit 4g→1 green ⇒ green = 4/3 = 1.333 ·
  Animus 6g→2 red ⇒ red = 6/(2·3) = 1.0. **These three land EXACTLY on the community model** (their bodies are tech-buildings you never chump, so full cost → resource).
  (Do NOT back-solve resources from blockers — Wall/EM are compositionally collinear and give a degenerate blue=1.0.)
- **energy is the EXCEPTION** = 0.3 (hedged), NOT the producer-naive 0.667. The Engineer (2g→1 energy) ALSO has a 1HP body you DO use
  defensively, so its 2g is shared between body and energy — unlike the pure-producer tech buildings. Subtracting the body (Barrier/BV
  benchmark, discounted for its bt1+deferred use) gives energy ≈ 0.08–0.15; 0.3 is a hedged middle (body deferred ~2.6 turns). energy's
  real value is board-dependent (≈0 with no consumer; valuable feeding Electrovores) — the board-aware ability-usable gate sets it later.
  Reconstruction: docs/scratch/backcalc_resources.js + the node calc `energy = (2 − body)/3`.
- **BV ≈ 2.2**: pure blockers' cost/HP with grounded resources (Wall 6.67/3=2.22, EM 11.33/5=2.27, Aegis 10/5=2.0). Caveats:
  Husk is a created TOKEN (its `2C` is nominal — useless for pricing); Forcefield is fragile+onBuySac; Polywall is undefendable.
- **Two perpetuity conventions, same R:** on-board unit produces this turn → `P_onboard = 1/(1-1/R) = 4`. A bought producer
  produces next turn (bt1) → `P_bought = 1/(R-1) = 3`. This dissolves the apparent "R=1.5 from producers" (only appears if you
  wrongly use P_onboard for a bought producer).

## 3. THE MODEL (exact — this is what gen_our_numbers_v2.js implements)

```
# discount helpers
geom(n)        = (1 - (1/R)^n) / (1 - 1/R)     # n attacks, THIS turn onward (finite). geom(0)=0, geom(1)=1
geomPerp(k)    = 1 / (1 - (1/R)^k)             # perpetual, fire every k turns. geomPerp(1)=P_onboard=4
costWill(s)    = sum over parsed resources of RES[res]*count     # mana code: leading int=gold, G/B/C/H=green/blue/red/energy, A=attack
abA            = # 'A' in abilityScript.receive      (click attack per activation)
btA            = # 'A' in beginOwnTurnScript.receive (auto/passive attack per turn)
body           = HP * BV
period         = abilityScript.delay || 1            # exhaust/delay; regular click = 1
doomed         = (lifespan is defined)

# sacrifice cost: PRODUCTION term ONLY of each sacrificed unit (body EXCLUDED — see §6/§9). recursive but safe.
abilitySacWill(c) = sum over c.abilitySac entries [name,count?] of  count * ours(lib[name]).production
                    # .production = the unit's atk column (= value - body). count defaults to 1.

net = abA*ATK - costWill(abilityCost) - abilitySacWill(c)

# dispatch (first match wins) — value, plus block(=body floor) and atk(=production) columns that SUM to value:
if targetAction=='disrupt'                  -> DEFER (chill)
if abilityNetherfy                          -> DEFER (drone-kill)
if (ability|begin).selfsac                  -> DEFER (self-sac-burst)
if (ability|begin).create is array          -> DEFER (token-spawn)
if lifespan==1                              -> 0                                  # terminal free chump
if abA==0 and btA==0 and produces resource: # ECONOMY
    auto (begin receive):  value = body + costWill(beginReceive) * (doomed? geom(life) : P_onboard)         # no penalty, no threat
    click (abil receive):  value = body + costWill(abilReceive)  * (doomed? geom(life-1) : (P_onboard - 1)) # click penalty, NO threat (economy doesn't threaten)
if abA==0 and btA==0                        -> value = body                       # PURE-BLOCK
if btA>0                                     -> value = body + (btA*ATK) * (doomed? geom(life) : P_onboard)  # AUTO-ATTACK: no tap -> no penalty, no threat
if c.charge:                                # CHARGE-ATTACK (charges are a preserved STOCK -> NO penalty)
    T = doomed? min(charge, life-1) : charge
    value = body + (charge>0 and net>0 ? net*geom(T) : 0)
else:                                        # CLICK-ATTACK
    if net<=0 -> value = body                                                     # ability not worth firing -> floor
    else:
        attacks = doomed? geom(life-1) : (geomPerp(period) - 1)                   # perpetual/exhaust: -1 = the death-eve fire you forgo to soak
        value = body + net*attacks + THREAT*abA                                   # +threat residual (scales with attack)
```

**Why each piece (the converged rationale):**
- **Additive `body + production`, NOT `max(block, attack)` and NOT `÷HP`.** The BlockIterator min-loss knapsack already ranks
  chumps by value/HP; since `body/HP = BV` is a constant, additive value's chump priority IS attack/HP (what we want). Putting
  `/HP` in the value would double-divide (attack/HP²). (§10.)
- **Charge = preserved STOCK → no penalty.** Holding a charge unit on defense doesn't consume charges; a 2ch-Rhino held X turns is
  the same unit. The finite charge count is the only reduction. (Distinct from a perpetual FLOW attacker, which forgoes its
  death-eve fire — the `-1`.)
- **Click death-eve penalty (`-1`) + threat.** An auto-attacker attacks AND blocks every turn; a click-attacker, on the one turn
  it soak-dies, must tap-to-block instead of tap-to-attack, forgoing exactly ONE fire. Hence perpetual click uses `P-1` not `P`.
  The forgone attack still THREATENS (forces over-defense) → `+THREAT*abA` residual. Verified invariant:
  `auto_value - click_value = ATK - THREAT` for same HP/attack (e.g. Urban 14.6 - Steelsplitter 12.7 = 1.9 = 2.0 - 0.1).
- **Exhaust uses every-other term**, not naive click/k: `geomPerp(2) = 1 + (1/R)^2 + (1/R)^4 + ... = 2.04` (full-strength fires
  spaced k turns), and the `-1` (full fire) is correct because an exhausted unit CAN'T block while exhausted → you can only soak
  it on a fire-ready turn → you forgo a full fire.
- **Promptness via R.** A soak available t turns from now is worth `(1/R)^t` of a prompt soak. Delayed units (bt>0) are
  discounted; this is what makes IG (4HP bt1) cost the same as Wall (3HP bt0).
- **abilitySac = PRODUCTION only (body excluded).** A unit fed to a sac engine is an attacker/economy unit, not a prompt defender;
  its soak is ~10 turns out and `(1/R)^10 ≈ 0.056 ≈ 0`, so its body is correctly ~0. You forgo its production, not its body.
  (Odin sacs Treant; Plasmafier sacs Drone — field `abilitySac: [["Treant"]]` / `[["Drone"]]`, count defaults to 1.)

## 4. What's IMPLEMENTED (generator)

`docs/scratch/gen_our_numbers_v2.js` — run `node docs/scratch/gen_our_numbers_v2.js` → writes `our_numbers_v2.md`.
- All of §2 constants + §3 model. Outputs: in-scope table (sorted by OURS, with block/atk/rule + Q/C++/sheet ref columns),
  per-charge breakdown, charge→∞ convergence vs perpetual-click, deferred-types table.
- Reference columns: `cpp()` = approx C++ `DamageLoss_WillCost`; `Q()` = AS3 `valueOfUnit`; sheet sDef/sTot (community 2023 snapshot).
- `backcalc_resources.js` — the resource/R derivation (producers + blockers). Run to re-verify §2 provenance.

## 5. Current output (anchors; full table in our_numbers_v2.md — REGENERATE for live values)

`Husk 2.2 < Engineer 4.87 < Drone 5.2 < Wall 6.6 ≈ Odin 12.7 ... Perforator 7.5 < Rhino 7.9 < Electrovore 8.5 <
Steelsplitter 12.7 < Urban Sentry 14.6 ... Plasmafier 24.2 < Redeemer 27.1 < Centurion 29.2 ... Tia Thurnax 41.17 < Thunderhead 42.7`.
Odin = 12.7 (= Steelsplitter; its click ≈ converts a Treant's future stream into a slightly bigger now-burst). Plasmafier = 24.2
(sacs cheap Drones → stays high). Both correctly differentiated by what they sacrifice.

## 6. Mechanics PENDING for units ALREADY IN the table (the immediate next work)

These flags are currently SET but have ZERO value effect — they're no-ops to be modeled:

| mechanic | flag | in-table units | current behavior | what it should do |
|---|---|---|---|---|
| **Healing (heal-above-max)** | `heal` (`c.HPMax`/`c.HPGained`) | Innervi Field (→5), Mahar Rectifier, Xaetron(deferred), Forcefield/Aegis(no), Chieftain(no) | body = base `HP*BV` only | Body should reflect **compounding durability**: a healer regenerates, so it's a repeated/over-max absorber, not a one-soak. Use `getHealthMax` (not starting HP). This is a "hold-back line" value — likely a body MULTIPLIER (>1) reflecting multi-turn soak, or model it as a small perpetual "defense stream". Innervi Field heals to 5 (from 3), Xaetron to 12. |
| **Fragile** | `fragile` | Forcefield, Aegis, Scorchilla, Feral Warden, Chieftain, Mahar, Plasmafier, Colossus, Tia | no-op | For a **chump (dies)** fragile ≈ same body → CURRENT NO-OP IS CORRECT for chump-loss. It matters for the **prime-absorber/survive** decision (a fragile unit can't be a repeated surviving absorber — damage is permanent). That's out of chump scope, so likely leave as no-op BUT document. ⚠️ When porting to C++: the fragile branch has a double-subtract bug at Heuristics.cpp:221 (subtracts tieBreakLoss twice) + uses `getStartingHealth` not `getHealthMax` (wrong for healed units) — fix both. |
| **Hannibull dual attack stream** | (none) | **Hannibull** (begin `+1A` AND ability `+1A`) | code returns early on `btA>0` (AUTO branch) and **DROPS the click stream** → UNDERCOUNTED | Sum BOTH: `value = body + auto_stream(btA, no penalty) + click_stream(abA, penalty + threat)`. Corrected Hannibull ≈ `15.4 + 8.0 + (net·(P-1)+threat) ≈ 24.8` (before the undef modifier). Generalize: a unit can have both `btA>0` and `abA>0`. |
| **Undefendable (−)** | `undef` (`c.undefendable`=engine `frontline`) | Polywall, Shredder, Hannibull, Thunderhead | no-op | NEGATIVE modifier: the opponent can kill it directly (ASSIGN_FRONTLINE), so its defensive value can be DENIED → discount the body/value. Magnitude TBD (it's a probability-of-denial haircut). |
| **lifespan>1 producers** | `life=N` | Grimbotch(4), Doomed Mech(5), Doomed Wall(3,pure) | doomed click uses `geom(life-1)`; doomed auto `geom(life)`; pure doomed = body | Mostly handled. Edge unhandled: charge+lifespan combo (none in current set). |

## 7. Deferred types (currently `DEFER` → keep old C++ value as fallback; model these next)

| type | detector | units | sketch of the rule to build |
|---|---|---|---|
| **economy** | resource `receive`, no attack | Engineer, Drone, Doomed Drone, Mega Drone | **DONE** (now in-scope; auto=P, click=P−1, no threat). |
| **chill** | `targetAction=='disrupt'` | Shiver Yeti (+ Vai-style attack→chill) | Perpetual conditional defense-TAX: forces opponent to over-defend once; killing it recovers that. Board-aware (not a static constant). Sheet punted (`#DIV/0!`). User anchor: Shiver Yeti ≈ between ch0-Rhino and ch2-Rhino. |
| **token-spawn** | `(ability|begin).create` is array | Corpus, Sentinel, Ossified Drone, Xaetron, Valkyrion, Defense Grid | Value = body + the CREATED tokens' values (the tokens are separate units already on board / created on click). Corpus body + Husk-factory (charge of House×3). Net the created units' value into the production stream. Valkyrion creates OPPONENT barriers (a drawback → negative). |
| **self-sac-burst** | `(ability|begin).selfsac` | Nitrocybe, Photonic Fibroid, Protoplasm, Infusion Grid | Unit sacrifices ITSELF for a burst (IG: selfsac → 4 Husks; Protoplasm: selfsac → +4A). Value = max(hold-as-blocker, burst-now). IG's burst = 4 Husk bodies; the "click count" optionality is the deployed RL axis (separate). |
| **drone-kill** | `abilityNetherfy` | Deadeye Operative | Kills an ENEMY drone (denies opponent economy). Board-aware (value = opponent's drone marginal value). |

## 8. Board-aware layer (the big future extension — the WHOLE point of a formulaic model)

Static value is least adequate exactly where these bite. Each is a multiplier/term on the base value, conditioned on the board:
- **ability-usable gate**: `production *= P(ability firable | board)`. "A Cauterizer with no energy is just a wall"; energy-payers
  collapse toward body when starved.
- **resource-complement uplift**: a producer gains value with consumers present (2 Engineers feeding 2 Electrovores > 1 Perforator;
  "last Engineer + Tesla Coil").
- **economy diminishing returns / stage**: Drone gold value `*= min(1, spendable_gold/drone_count)` and shrinks late-game.
- **stage-dependent R**: R falls as the game saturates (fewer turns to compound). High early (~1.4+), lower late (~1.2). Re-introduces
  the sac-unit BODY late-game (when the ~10-turn soak draws near) and lowers perpetual streams.
- chill board-awareness, drone-kill denial value, undef denial probability — all board-aware.

## 9. LOCKED decisions (do NOT relitigate without a concrete counter-example)

1. Additive `body + production`; body is a PERMANENT floor; NOT `max()`; NOT `÷HP` (knapsack supplies the /HP).
2. Charge = preserved stock → no death-eve penalty. Perpetual/doomed CLICK (flow) → `-1` death-eve penalty + `THREAT*abA`.
3. Auto-attack (passive) → additive, no penalty (attacks AND blocks). `auto - click = ATK - THREAT` for same HP/attack.
4. Promptness via R: delayed defense `*(1/R)^t`. R = 4/3 (two independent derivations agree).
5. Resources are PRODUCER-derived (not blocker-back-solved). gold 1, green 4/3, blue 5/3, red 1, energy 2/3.
6. abilitySac cost = sacrificed unit's PRODUCTION only (body excluded — it's not a prompt defender; (1/R)^~10 ≈ 0).
7. Body = ONE prompt soak `HP*BV` (sheet convention). lifespan==1 → 0 (terminal free chump).
8. Scope = defense cluster (consumers #1/#7/#8/#9) via a NEW `Heuristics::DefensiveValue`; keep old for offense (#3/#4/#5/#6) + buy
   (#10-12). #2 Defense_GreedyKnapsack is dead.

## 10. SUPERSEDED decisions (were once "current"; now wrong — don't revert)

- `OURS = max(block, attackStream(T) + body·(1/R)^T)` optimal-stopping → REPLACED by additive (the `max` zeroed the ability premium
  for weak click-attackers; e.g. Perforator floored at 2·BV).
- §4 of the v2 handoff "value = Body + attack/HP" → REJECTED (the knapsack already divides by HP; ÷HP in the value gives attack/HP²).
- "perpetual click = attack stream only; afterBody→0" → REVERSED (body is a permanent floor, never washes out).
- `energy = 0.3` (a user what-if) → producer-derived `0.667`.
- abilitySac netting the sacrificed unit's FULL value → PRODUCTION-only (body excluded).
- BV/ATK = 1.9, R = 1.4 (early guesses) → grounded BV 2.2, ATK 2.0, R 4/3.
- The "ch100 smooth convergence" requirement → nuanced: a charge unit at ch→∞ sits ~1 net-attack ABOVE the equivalent perpetual
  click (stock vs flow); they intentionally do NOT converge to the same value.

## 11. Eval plan (how we'll validate before/after — DON'T run tournaments for a 2-unit change)

- **Primary: F6 before/after** = deterministic BlockIterator diff on fixed defense states. The auto-dumper + human-deviation harness
  is fully scoped in **docs/scratch/2026-06-20-defense-eval-pipeline-handoff.md** (replay_to_request.js --all + a `--defense-only`
  filter; oracle_diff.js proves states == real F6; two states/turn = begin-of-defense [AI input] + just-before-swoosh [human truth],
  undo-robust via beginTurnHistory). Deferred (build when there's a candidate to A/B).
- **Iterate offline** with a JS re-implementation of BlockIterator min-loss + a pluggable value fn (current C++ values vs our model);
  C++ before/after via `query_move.js` is the FINAL confirmation once the model is ported.
- Per-player A/B toggle (config field) for any tournament, first on UCT/NN players (no rollout). F6 mechanics: docs/og-masterbot-mistakes-research.md.

## 12. Verified facts (do NOT re-derive)

- Producer costs → resource values (Blastforge 5g/1blue→5/3; Conduit 4g/1green→4/3; Animus 6g/2red→1; Engineer 2g/1energy→2/3) at
  perpetuity 1/(R−1)=3. Wall(5B,3HP,bt0) vs IG(5B,4HP,bt1) → R=4/3. (backcalc_resources.js)
- `abilitySac` field format: top-level `[["Treant"]]` / `[["Drone"]]` ([internalName, count?]); count defaults to 1.
- Internal↔UI names: Husk=House, Steelsplitter=Treant, Rhino=Elephant, Infusion Grid=Hotel, Electrovore=Fickle Marine,
  Perforator=Trickster, Tia=Ephemeron, Odin=Furion, Plasmafier=BFD, Blastforge=Brooder, Animus=Academy, Aegis=Fragilewall,
  Energy Matrix=Golem, Forcefield=Blood Barrier, Barrier=Sound Barrier, Ossified Drone=Neo Overlord.
- Husk is a Corpus token (its `2C` is nominal; you get it by buying a Corpus = 6g+2red → Corpus 2HP + Husk). Resources can't be
  priced from blockers/tokens — only from producers.
- cardLibrary (live, deployed): c:/libraries/PrismataAI-dave-master/bin/asset/config/cardLibrary.jso.
- WILL cost weights (C++ reference, in cpp()/willScoreCpp): gold1, B1.5, G1.2, R0.9, H0.5, A2.25, × inflation[ct] (ct0=1/1.13,
  ct1=1, ct≥2 ×1.28). This is the OLD basis we're replacing on the defense side; kept only for the C++ comparison column.

## 13. Assets (all under c:/libraries/PrismataAI/)

| file | what / how |
|---|---|
| docs/scratch/gen_our_numbers_v2.js | **THE model generator.** `node` it → our_numbers_v2.md. EDIT HERE. |
| docs/scratch/our_numbers_v2.md | current model output (in-scope/charge/convergence/deferred). |
| docs/scratch/backcalc_resources.js | resource + R + BV derivation (producers + blockers). Re-run to verify §2. |
| docs/scratch/blocker_inventory.{md,csv} + gen_blocker_inventory.js | the problem set: every defaultBlocking unit classified + C++/Q/sheet answer-keys. |
| docs/scratch/2026-06-20-defense-eval-pipeline-handoff.md | F6 auto-dumper + human-deviation eval harness (scoped, not built). |
| docs/scratch/2026-06-19-unit-value-surface-map-VERIFIED.md | blast-radius / consumer map (the #1-#12 list; defines the scope in §1). |
| docs/scratch/2026-06-20-unit-value-heuristic-v2-handoff.md | SUPERSEDED predecessor (older model; read only for deep background). |
| docs/community_stats/math_analysis/sheet_{Units,Info}.csv, sheet_full.xlsx | community math reference (23-May-2023 snapshot; resource methodology). |
| docs/og-masterbot-mistakes-research.md | F6 tooling + the defense mistakes (M1/M3) this heuristic fixes. |
| PrismataAI-dave-master/source/ai/Heuristics.cpp:158 | TARGET fn `DamageLoss_WillCost` (+ :102 Forcefield 3.75 pin, :161 lifespan→0, :219-221 double-subtract bug, :194 fragile getStartingHealth). |
| PrismataAI-dave-master/source/ai/BlockIterator.cpp | the min-loss search to mirror in JS (:60-65 dead tie-break; first-min-loss wins; epsilons inside the value fn order ties). |

## 14. Open questions / next steps (in order)

1. **Model the §6 in-table mechanics**: heal (compounding/over-max body), Hannibull dual-stream (sum auto+click), undef (denial
   haircut). Fragile likely stays a no-op for chump-loss (document why). Implement in gen_our_numbers_v2.js, regenerate, eyeball.
2. **Model the §7 deferred types**: token-spawn (credit created tokens), self-sac-burst (max hold vs burst), chill + drone-kill
   (board-aware stubs). Un-defer as each rule lands.
3. **Holistic re-calibration**: with the full model, re-check ALL orderings vs Q / sheet / user intuition; tune BV/ATK/THREAT/R only
   if orderings demand it (constants are grounded — change with evidence).
4. **Spec → C++ port**: write **`Heuristics::DamageLoss_Functional`** (a NEW fn ALONGSIDE `DamageLoss_WillCost`, NOT a
   rename — the old one stays for the offense/buy consumers; see §16 for the name + the prime-absorber objective finding),
   route consumers #1/#7/#8/#9, fix the :221 double-subtract + fragile getStartingHealth/getHealthMax, add the per-player A/B
   toggle. Honor the surface-map preconditions (Forcefield 3.75 pin, 1-HP 1.875 pin, mana-vs-total table branch, the inert
   BlockIterator tie-break epsilons).
5. **Eval**: build the dumper harness (2026-06-20-defense-eval-pipeline-handoff.md) and run F6 before/after on ~20 elite replays.

## 15. User preferences (relevant here)

- Only ORDERING + relative sizes matter; absolute scale free. Iterative review — present numbers, corrections one at a time, don't
  over-produce or jump to a spec/C++. Small/provable/low-regression; willing to call a unit a wash. Cost-conscious re AWS only —
  NEVER ration Claude/Workflow/subagent usage.

## 16. Prime-absorber / BlockIterator integration (2026-06-23 finding — READ before the C++ port)

**Naming:** the new defense value fn = **`Heuristics::DamageLoss_Functional`** — a NEW function ALONGSIDE
`DamageLoss_WillCost` (which stays for offense/buy). "Functional" keeps the name accurate. (Supersedes the working
name "DefensiveValue" in §1/§14.)

**How the two implementations pick the prime absorber today (investigated 2026-06-23):**
- **C++ (the bot): `DefenseSolver → BlockIterator`** (`source/ai/BlockIterator.cpp`). Exhaustive min-loss DFS that
  minimises **Σ `DamageLoss_WillCost`(units that DIE)**. The prime absorber is **EMERGENT, not explicit**: a
  non-fragile survivor returns **loss 0** (`Heuristics.cpp:237-240`), so overflow routes into a big survivor for
  free. It is **lineup-blind** (only dead units are summed), **heal-blind** (absorption uses `currentHealth()`;
  `getHealthMax`/`getHealthGained` never referenced in the defense path), and among equal survivors picks by
  card-ID order ("first min-loss wins", strict `<` at BlockIterator.cpp:55; the tie-break channel at :60-65 is
  commented-out dead code).
- **AS3 "Q": `AutoClicks.primeDefender`** (client auto-defender). EXPLICIT two-phase: pick the prime by max
  survivable capacity (`health-1`) + a heal-aware `biggestFreeAbsorber` (`AutoClicks.as:407`:
  `freeDamage = health + healthGained − healthMax`), then a greedy knapsack picks the cheapest-`valueOfUnit`
  chumps around it. More functional than the C++, but hand-tuned/hardcoded and not on our values.

**The key finding — functional VALUE alone is necessary but NOT sufficient.** With a naive "survivor→0" value,
the existing min-loss absorbs everything onto the biggest unit (lose nothing) even when that cripples a healer —
WRONG (it can't see that a 5-HP Xaetron is worse than a 12-HP one). The fix is to make the per-unit fn return the
**HP value the survivor permanently loses**, so the min-loss SUM becomes lineup-aware (no search restructure):

> `DamageLoss_Functional(card, state, damage)` for a SURVIVING unit returns
> **value(card @ currentHP) − value(card @ currentHP − damage, after one heal/repair)**, using the heal-aware
> functional value (effective soak = `min(HP + heal, max)·BV`). Dead unit → full value (unchanged).

Then non-fragile survivor → 0 (repairs; never decremented, Card.cpp:415-422); fragile non-healer → permanent HP
lost; healer → HP lost NET of heal (0 when it has heal headroom). Because Σloss over assigned blockers =
(pre-board value) − (resulting-board value), **minimising loss == maximising the resulting lineup** — so min-loss
DOES then account for the whole defensive lineup.

**Worked checks (BV 2.2, value(h)=min(h+heal,max)·BV):**
- Xaetron@3(heal4,max12) + Wall@3, 2 dmg → Xaetron loss (7−5)·2.2 = **4.4**, Wall **0** → picks **Wall** (correct:
  Wall is non-fragile so it repairs free; Xaetron untouched heals 3→7).
- Xaetron@10 + Wall@3, 2 dmg → Xaetron loss (12−12)·2.2 = **0** = Wall → **indifferent** (correct: at 10hp the
  heal over-caps, so absorbing 2 on Xaetron is also free).
- 5 Husk + Wall + Xaetron@8, 7 dmg → (A) Xaetron solo-absorbs: loss (12−5)·2.2 = **15.4**; (B) keep Xaetron out,
  lose 5 Husks: loss 5·2.2 = **11** → min picks **(B)** (sacrifice husks, Xaetron stays a 12hp fortress) — matches
  owner intuition. NOTE the current `DamageLoss_WillCost` would (accidentally) also favour (B) here only via the
  buggy `damageTaken/getStartingHealth` ratio (7/4=1.75>1); `DamageLoss_Functional` gets it right by design.

**Caveat (refinement, not a blocker) — MULTI-TURN HEAL PROJECTION, known to cause a WRONG PLAY:** value projects
only ONE heal, so a deeply-damaged healer is under-credited (Xaetron@4 truly reaches 12 over 2 turns; value only
projects to 8). This is not merely cosmetic — it flips a real chump decision. **Counterexample (Energy Matrix +
Xaetron@5, 9 incoming):** (A) chump Xaetron, EM prime → loss = V(Xaetron@5) = **19.7**; (B) chump EM, Xaetron prime
(5→1→heals 5) → loss = V(EM 11) + δ_Xaetron(19.7−10.9=8.8) = **19.8**. We pick (A) by 0.1 — **chump the healer** —
which is WRONG: Xaetron climbs back to a 12-HP fortress and dwarfs a static 5-HP wall. Root cause = V(Xaetron@5)=19.7
sees only one heal (to 9), undercounting the multi-turn climb to max. **Decision (2026-06-24): DEFER + record** —
don't hand-tune a forward-looking healer value blind (risks throwing other units off; it's a knife-edge 0.1). The
defense-eval pipeline is built to quantify exactly this: healer-preservation positions will surface as regret /
divergence vs elite humans, and the data sizes the correction (a multi-turn heal projection or a forward "keep the
healer" term) and confirms it doesn't break other pairs. This is a flagged **candidate refinement** for the eval
loop, NOT a v1 blocker.

**Port-time bug to fix alongside:** the fragile branch `damageTaken / getStartingHealth` (Heuristics.cpp:194)
exceeds 1 for healed units (currentHealth > startingHealth) — `DamageLoss_Functional` must use current/max HP, not
startingHealth; also the :219/:221 double `-= tieBreakLoss`.
