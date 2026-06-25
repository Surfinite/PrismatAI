# Prime-Defender Keep-Value — Implementation Handoff (resume at writing-plans)

> A fresh session: your job is to turn the **approved design spec** into an implementation plan and then
> implement it. The design brainstorm is COMPLETE and approved; do NOT re-open it. Start at the
> `superpowers:writing-plans` skill, then implement subagent-driven. This doc carries all the background,
> rationale, and gotchas so you don't have to reconstruct them.

## 0. Task & how to resume

1. Read the **spec** (the authoritative design): `docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md`.
2. Invoke `superpowers:writing-plans` to produce `docs/superpowers/plans/2026-06-25-prime-defender-keep-value.md`
   — bite-sized TDD tasks (CommonJS + `node:test`), exact file paths, complete code, frequent commits.
3. Then implement **subagent-driven** (`superpowers:subagent-driven-development`), one fresh subagent per task,
   review between. Local commits only on `feature/production-vectors`; **do not push** (push only when the owner asks).
4. The whole change is in the **JS eval model** (`gen_our_numbers_v2.js` + `eval/defense/`). The C++ port is
   explicitly deferred. Validation = re-run `node eval/defense/compare.js <codes> <out>` (~2 min) and check the
   metrics move the right way (§5 of the spec).

## 1. What this is, in one paragraph

The defense-eval pipeline grades our functional defense value heuristic (`ours`) against elite human defense.
It found `ours` over-chumps reusable blockers (Walls) and under-chumps spent-economy/charge units (Engineers,
ch2-Rhinos), because the model counts an **attacker's** perpetual attack stream but only a **blocker's** one-soak
body — so it never prefers *keeping* a reusable Wall. This spec adds a **prime-defender keep-value** (credit the
one surviving anchor its perpetual absorb), on a **half-turn clock** (which also makes `ATK` derive cleanly from
`BV`), plus a **multi-turn heal** extension. Three coupled value-model changes, one spec.

## 2. The design in a nutshell (formulas + the rationale behind each — this is the part the spec compresses)

**Constants (half-turn clock).** `R_HALF=√(4/3)≈1.1547`; `d=1/R_HALF≈0.866`; `d²=0.75`; `P=1/(1−d²)=4`.
`ATK=BV/R_HALF≈1.905` (was a standalone 2.0). *Why:* a block is realized on my defense phase; an attack lands on
the opponent's defense phase a **half-turn later**, so `ATK = BV·d`. `R_full=4/3` was already grounded
(Wall 3HP prompt ≡ Infusion-Grid 4HP build-time-1: `3·BV=4·BV/R`). The only ripple is every attacker's attack
component scaling ≈×0.95; blockers/economy unchanged.

**Prime keep-value (the core new term).** `primeAbsorbCredit(unit) = sustainableAbsorb · BV · factor`, applied
**only to the single surviving prime**, **only in `ours` mode**, as a *credit* (negative loss):
- `sustainableAbsorb` = `HP−1` (non-fragile: absorbs HP−1, survives on 1, repairs) / `heal` (fragile healer:
  absorbs `heal`, heals it back, **uncapped**) / `0` (fragile non-healer: can't sustain).
- `factor` = `P−1 = 3` (permanent) / `Σ_{k=1}^{life−1} d^(2k)` (doomed: 0.75 at life2, 2.05 at life5, →3).
- *Why prime-only:* a non-prime surviving blocker is, by the model's own "same prime reused next turn"
  assumption, just a one-soak again (value `HP·BV`, already correct); only the prime lives and is reused as the
  anchor, so only it earns perpetuity. This also bounds the magnitude (a board of 1-HP Engineers doesn't become
  un-chumpable).
- *Why absorb-only:* an attacker's future attacks are ALREADY in chump-loss `V` (a surviving attacker attacks
  later AND can defend). So Steelsplitter-vs-Wall already resolves correctly via chump-loss (keep the 12.7, chump
  the 6.6) — DO NOT add anything for it. The ONLY thing chump-loss misses is the prime's perpetual *absorb*.
- *Why `(P−1)=3`:* the 2-half-turn discount — this turn's absorb is free (the prime survives, `loss 0` already),
  so the credit is only the *future* perpetual absorb, whose first term is the next defense phase, 2 half-turns
  out (`P·d² = 4·0.75 = 3`).
- *Why `HP−1` == `heal`:* Energy-Matrix(5HP) sustains HP−1=4; Xaetron sustains heal=4 → equal credit, so which of
  *those two* to keep falls to chump-loss (V(Xaetron@5)=19.7 > V(EM)=11 → keep Xaetron). Owner-confirmed.
- *Why doomed-finite factor:* a doomed unit can't be a perpetual anchor; it expires. This IS the case-3-vs-4
  distinction (5-life vs 2-life Doomed Mech).
- **Objective change:** `defense_sim` `ours` mode goes from `min Σ loss` to
  `min [Σ chump-loss − primeAbsorbCredit(surviving prime)]`. The credit is a *bounded negative* on the prime, so
  the branch-and-bound `negFloor` bound MUST include the best-possible credit among remaining candidates or it can
  prune a true optimum. Only a **truly surviving** prime earns it — a dying last-blocker (relabeled a chump) does
  NOT.

**Multi-turn heal (two distinct mechanisms).**
- (a) **Chump-loss, capped climb to max:** replace `min(HP+heal,max)` with
  `effectiveSoakHP = currentHP + Σ_{t≥1} (heal gained at turn t, cumulative-capped at max)·d^(2t)`. Xaetron@5 →
  21.3 (was 19.7); Xaetron@2 → 17.8 (was 13.2). Lives in `gen_our_numbers_v2.js coreValue`.
- (b) **Prime credit, uncapped perpetual rate:** the `sustainableAbsorb=heal` branch above — a rate, not a fill,
  so NOT capped by max (a maxed Xaetron is still a great anchor at `heal·BV·(P−1)`). A healer carries BOTH.

**Report decision-relevance filter (`metrics.js`):** exclude positions where
`incoming ≤ max_unit(survivable absorb) + Σ(lifespan-1 HP)` (no real unit must die → prime choice is cosmetic)
from the **divergence** and **tie-break-skew** diagnostic tables ONLY — **except keep any position whose prime
(human's or ours') is a healer** (we need to verify healer-prime selection). Headline regret/exact-match counts
stay over the full corpus.

**Acceptance tests** (unit tests on `solveDefense`, `ours` mode; exact numbers pinned after the ATK change):
1. Wall + ch2-Rhino, 4 dmg → keep Wall as prime, chump Rhino (the headline flip). 2. Engineer+2×Wall+ch2-Rhino,
5 dmg → chump the Engineer. 3/4. EM + 5-life vs 2-life Doomed Mech, 9 dmg → outcomes MUST differ.
**Regression guards (must NOT change):** Steelsplitter-vs-Wall, EM-vs-Xaetron@5, the `cpp` validation gate
(1234/1235), the tripwire (clean).

## 3. Codebase state & file map (current — all audit fixes already applied)

The eval pipeline is built, validated, run on 5000 elite games, and **all four audit bugs are fixed** (commits
`aafe403f`+`3649b149`). Corrected baseline: **`ours` 82.7% vs `cpp` 84.7% zero-regret** (and exact-match;
prime-match 88.7/91.7); tripwire clean. You are building ON TOP of this.

| File | What it is / current state |
|---|---|
| `docs/scratch/gen_our_numbers_v2.js` | **The value model** `ours(c, stateOverride)`. `stateOverride={hp,charge,life}`. `coreValue` has: heal `soakHP=min(_hp+heal,hpMax)` (~line 72 — §3a replaces this); `life===1→0` terminal check moved to the TOP of coreValue (~line 81); §4.4 fixes applied (DOOMED_NUDGE=0.1, OPT_SELFSAC_ATK=0.2, OPT_SELFSAC_TOKEN=0.1). `ours()` wrapper applies fragile/undef haircuts to `block` (guarded off terminal-0). `module.exports={ours,parseCost,costWill,attackOf,geom,geomPerp,lib,CONSTANTS}` + cpp helpers (willScoreCpp,inflCpp,resolveBT). Run standalone → regenerates `our_numbers_v2.md`. |
| `eval/defense/defense_value.js` | per-unit `unitView(stateUnit)`→{internal,hp,charge,life,fragile,heal,max,ct,raw,...}; `V(view)`; `body(view)`; `loss(view,damage,mode)` ('ours'/'cpp' — cpp is a faithful `DamageLoss_WillCost` replica WITH ITS BUGS); `isoKey`/`decodeIso` (status-free, 9 isIsomorphic fields); `canBlock`. **ADD `primeAbsorbCredit(unit)` here.** |
| `eval/defense/defense_sim.js` | `solveDefense(blockers, incoming, mode, eps)` — one-prime min-loss + branch-and-bound (`negFloor`). Returns `{assignment:{chumps,prime,untouched,perUnit}, loss, tiedAlts}`. **MODIFY `ours` objective + extend `negFloor`.** `cpp` mode must stay identical (gate). |
| `eval/defense/blockers.js` | shared `canBlockState`/`availableBlockers` (engine-faithful: excludes frozen `disruptDamage>=hp`, under-construction, delayed, dead). Used by compare + gate. |
| `eval/defense/metrics.js` | `computeMetrics`, `aggregate` (regret w/ `|x|<1e-9` FP tolerance; symmetric exact-match; multiset divergence; tie-break-skew; tripwire `loss<-0.3`). **ADD the decision-relevance filter to the two diagnostic tables.** |
| `eval/defense/compare.js` | harness CLI `node eval/defense/compare.js <codesFile> <outDir>`. |
| `eval/defense/report.js` | `renderReport` (display names, attribute columns, replay@step citations). |
| `eval/defense/validate_gate.js` | one-time cpp-vs-real-engine gate (steam bundle `C:/libraries/DSNN_steam_bundles/v221_rl_iter8`, think_time=0/max_traversals=1). |
| `eval/defense/state_b_capture.js` | committed-defense reader (`Analyzer.endDefenses`/`gotoCommand`). |
| `eval/defense/results/report.md` | the current 5000-game results (the baseline to beat). |
| `training/data/human_elite_2000_45s_v2.provenance.json` | `selected_codes` = the 5000-game corpus. |

**Tests:** CommonJS + `node:test`. Run with the **glob**: `node --test eval/defense/*.test.js` (the bare-dir form
errors on Node 24). ~31 tests currently pass.

## 4. Critical gotchas / must-not-break

- **WHICH ENGINE:** the strong engine is `c:/libraries/PrismataAI-dave-master` (engine_v1). THIS repo's `source/`
  is the indicted engine_v2 — ignore it. The card library + C++ heuristics live in dave-master; the JS engine in
  this repo's `js_engine/`.
- **`cpp` mode is sacred** — it's the faithful `DamageLoss_WillCost` replica validated against the real engine
  (gate 1234/1235). The prime keep-value, the ATK change's *value* effects, and the heal climb are all **`ours`**;
  do NOT let any of them leak into `cpp` mode or you break the gate. (The half-turn `ATK` is a `gen_our_numbers`
  constant used by `ours`; `cpp` mode uses its own WillScore weights, so it's naturally unaffected — verify.)
- **One-prime defense mechanic:** chumps are full-killed (take ≥ their HP); exactly ONE prime takes partial damage
  and survives; all other available units take 0 and survive untouched. The keep-value credits only the *surviving*
  prime.
- **Prime-absorb credit only on a TRULY surviving prime** (absorbs < its HP, lives). A dying last-blocker
  (`hp==remaining`, relabeled `prime:null`/chump in the sim) earns 0.
- **B&B soundness:** the credit is a negative term → extend `defense_sim`'s `negFloor` to include the
  best-possible `primeAbsorbCredit` among not-yet-fixed candidates, else pruning can drop the optimum. There is a
  brute-force oracle pattern in the repo (see the eval-pipeline audit) — re-validate the modified search against an
  unbounded reference.
- **Iso, not instId** everywhere; same-class units interchangeable.
- The value model's `ours(c, stateOverride)` reads `_hp/_chg/_rem` from the override; the heal climb (§3a) must use
  the unit's **current** HP (`_hp`), and the doomed factor uses **current remaining** lifespan (`_rem`), with
  `c.lifespan` as the nominal max.

## 5. Prismata mechanics that justify the design (so you don't re-derive or "fix" them)

- Defense is **set up in the action phase** and used next turn; the swoosh/reset is between defense and action.
- A **click-attacker** chooses each action phase: tap-to-attack (out of next defense) OR hold-untapped (defend).
  An **auto-attacker** attacks passively AND defends. So a click-attacker's attack is forgone when held for
  defense — but that's already in chump-loss `V`, so it's NOT part of the keep-value. A Steelsplitter as a
  *continuous prime* is exactly a Wall + the option to click-attack → it dominates a Wall, which is why chump-loss
  already keeps it.
- **Non-fragile** survivors repair to full each turn (free reuse); **fragile** persist then heal `healthGained`
  capped at `healthMax` (`Card.cpp:609-636`, `takeDamage` `:389-423`).
- `R_full=4/3`, `BV=2.2` etc. are **local approximations of an intentionally-uneven efficiency curve** (base units
  less efficient than advanced ones, e.g. Wall vs Polywall) — chase aggregate regret, not per-unit perfection.

## 6. Background docs (read if a point is unclear)

- `docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md` — **the spec** (authoritative).
- `docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md` — the eval harness this is measured in.
- `docs/superpowers/plans/2026-06-24-defense-eval-audit-findings.md` — the 4 bugs (now fixed) + the §5 divergence
  signal that motivated this work + the prime-defender direction.
- `docs/superpowers/plans/2026-06-24-defense-eval-results-handoff.md` — the 5000-game run write-up (UPDATE
  2026-06-25 = corrected post-audit numbers).
- `docs/scratch/2026-06-22-unit-value-heuristic-v3-handoff.md` §16 — the `DamageLoss_Functional`/survivor-delta
  rationale + the worked heal examples.
- `eval/defense/results/report.md` — the divergence/skew tables (the data the design responds to).

## 7. Git state (nothing pushed)

Branch `feature/production-vectors`. Recent local commits: `aafe403f` (audit fixes ①②③④), `3649b149` (re-run +
corrected baseline), and today's `…prime-defender keep-value design spec`. The implementation is NOT started.

## 8. Owner working style

Incremental, code-provable, low-regression; surface findings, don't over-produce. Token/subagent usage is NOT a
constraint (only AWS spend is cost-sensitive). Don't push or open PRs without asking. Git noob — do routine local
commits sensibly and say what you did; pause only before remote/destructive git actions.

## 9. KICKOFF PROMPT (paste into a fresh session)

```
Resume the prime-defender keep-value work at the writing-plans stage. First read
docs/superpowers/plans/2026-06-25-prime-defender-implementation-handoff.md (all background + gotchas),
then read the approved spec docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md, then
invoke superpowers:writing-plans to produce the implementation plan, and implement it subagent-driven
(superpowers:subagent-driven-development), TDD with a commit per task. It's a JS-eval-model change only
(gen_our_numbers_v2.js + eval/defense/), cpp mode untouched. Local commits only on
feature/production-vectors; do not push. Validate by re-running node eval/defense/compare.js and checking
the Wall over-chump / Rhino under-chump divergences shrink and zero-regret rises above the 82.7% baseline.
```
