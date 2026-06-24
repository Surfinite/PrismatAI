---
title: "Defense-Eval Pipeline — grading the functional defense heuristic against elite human play (DESIGN)"
date: 2026-06-24
status: DESIGN APPROVED (brainstorm complete) — ready for implementation plan
owner: Surfinite
scope: "Phase A — the eval harness + tuner-ready metrics. The automated constant-tuner is OUT of scope (its own spec, fed by this pipeline's data)."
builds_on:
  - docs/scratch/2026-06-20-defense-eval-pipeline-handoff.md   # the original scoped harness (State A/B extraction, undo-collapse, F6-equivalence proof)
  - docs/scratch/2026-06-22-unit-value-heuristic-v3-handoff.md # the functional value model + §16 DamageLoss_Functional / prime-absorber design
  - docs/scratch/gen_our_numbers_v2.js                          # the live functional value model (per-unit table generator)
engine_state_gen: "PrismataAI faithful JS engine, this repo, js_engine/ (feature/production-vectors)"
engine_defense_ref: "PrismataAI-dave-master @ dave-master-jsonclean (engine_v1, the strong engine) via js_engine/query_move.js"
---

# Defense-Eval Pipeline — DESIGN

## 1. Mission & scope

Grade our redesigned **functional** defense heuristic (the `DamageLoss_Functional` value model in
`gen_our_numbers_v2.js` + the §16 survivor-delta objective) against **how elite (2000+ ELO) humans actually
defend**, across every defense phase of a large replay corpus. The output is a set of **tuner-ready statistics**
that tell us (a) whether our heuristic ranks elite play as optimal, and (b) which unit valuations need correction.

**In scope (Phase A):**
- Extract, per defense phase, the AI input state (begin-of-defense) and the human's committed defense.
- A fast in-process JS re-implementation of the defense block-assignment search with a **pluggable value
  function** (current-C++ replica AND our functional model).
- A metric stack centred on **value-gap / regret** (primary), plus exact-match, prime-match, a **tie-break-skew
  misvaluation detector**, and per-unit divergence.
- A rich, **tuner-ready** per-position record + an aggregate report.
- A one-time **validation gate** proving the JS sim reproduces the real C++ engine's defense picks.

**Out of scope (Phase A) — deferred, see §11:** the automated constant-tuner; board-aware layers (multi-turn heal
projection, opponent unused-chill potential, drone-kill denial); the C++ port of `DamageLoss_Functional`;
action / buy / breach / chill-target comparison.

## 2. Background: how Prismata defense actually resolves (the corrected mechanic)

This is the precise mechanic the whole design rests on (verified against `Card::takeDamage`,
`PrismataAI-dave-master/source/engine/Card.cpp:389-423`, and confirmed by the owner):

- The defender assigns the opponent's incoming damage `D` across their own units, one click at a time.
- **Clicking a unit full-kills it (chump)** whenever the remaining damage to distribute is **≥** that unit's HP.
- You keep full-killing chumps until the remaining damage is **<** the HP of one of your still-alive blockers.
- That last unit — the single **prime defender** — absorbs the remainder and **survives**.
- **There is exactly ONE prime** (the only unit that takes *partial*, non-lethal damage). Damage is **not** split
  across multiple partial-absorbers.
- Every *other* available unit that is never targeted takes **0** damage and survives **untouched**.
- So **multiple units survive** (the one prime + all untargeted units), but only one took partial damage.

Survivor HP mechanics at the owner's next turn-start (`Card::beginOwnTurnPhase`, Card.cpp:609-636):
- **Non-fragile** unit (prime or untouched): never tracked as damaged — back to full next turn. Absorbing on it is
  **free**.
- **Fragile** unit: damage persists; then it heals `getHealthGained()` capped at `getHealthMax()`.
- A unit's "available to block" status excludes frozen/chilled, under-construction, and delayed units (handled by
  the engine; chilled units are simply unavailable that turn).

**"Committed blockers" = the entire pool of available defensive units** (every unit damage *could* be assigned to),
not only the ones that end up taking damage. Untargeted survivors are part of the pool and part of the objective
(they contribute 0 loss; see §4).

## 3. Architecture (six components)

```
elite replay.json.gz
  ├─(replay_to_request --defense-only)─→ State A  ┐  (per defense phase, both players, incomingAttack>0)
  └─(recordClick monkeypatch, doc §5)──→ State B  ┤  (committed defense, undo-collapsed)
                                                   ▼
                       comparison harness, per defense position:
                         State A → defense_sim(value="ours")   → AI pick + near-tied alternatives
                         State A → defense_sim(value="cpp")    → current-C++ baseline pick
                         State B → read human per-unit damage assignment
                         → metrics: regret (primary) / exact-match-iso / prime-match / tie-break-skew / per-unit
                         → per-position record (JSONL)  +  aggregate report (markdown)
```

| # | Component | New/extend | Purpose |
|---|---|---|---|
| 1 | `defense_value.js` | new (extracted+extended from `gen_our_numbers_v2.js`) | per-unit loss fn, HP-parameterized, two modes; `isIsomorphic` |
| 2 | `defense_sim.js` | new | one-prime min-loss block-assignment search; pluggable loss |
| 3 | State-A extractor | extend `eval/replay_to_request.js` | `--defense-only` predicate (~4 lines) |
| 4 | State-B capturer | new | `recordClick` monkeypatch, undo-robust committed defense |
| 5 | Comparison harness | new | pair A/B per position, compute metrics, emit records + report |
| 6 | Validation gate | new (one-time) | prove `cpp`-mode sim == real engine on 50–100 games |

All evaluation is in-process JS over the faithful engine. The real C++ engine (`query_move`) is used **only** for
the one-time validation gate (§8) and an optional final spot-check once the model is locked.

## 4. The objective and the per-unit loss (`defense_value.js`)

### 4.1 Single objective, pluggable loss

The defense decision is a damage assignment over the available pool. The objective is:

> **minimize** `Σ over ALL available units [ V(unit @ HP_before) − V(unit @ HP_after) ]`
> ≡ **maximize** the value of the resulting board.

Equivalently, the sim minimizes `Σ loss(unit, damage_applied)` over the pool, where `loss` is the per-unit term
below. Untouched units (`damage=0`) have `HP_before == HP_after` → contribute **0**, but they are *in* the
framework (their standing value is accounted), so the optimization sees the whole pool and chooses, per unit,
chump / prime / untouched. **The lineup-awareness lives entirely in the per-unit loss** — the search structure is
identical across value modes (this is the §16 result).

### 4.2 The value function `V(unit @ HP)`

Drawn from the locked `gen_our_numbers_v2.js` model, extracted into this shared module and **parameterized by
current HP**:

- `body(HP) = min(HP + heal, max) · BV` for healers (heal-aware effective soak), else `HP · BV`.
  - **The heal is encoded once, here**, so it applies uniformly to every role: prime (via the before/after delta),
    untouched (via unchanged standing value — already heal-projected), and chump (loses it).
- plus the unit's production terms (attack / charge / economy / token streams) as in the v2 model; these are
  independent of how much damage the unit takes when it survives, so they cancel in the survivor delta and only
  appear in full when a unit dies.

### 4.3 The per-unit loss — two modes

`loss(unit, damage, mode)`. Survive-vs-die is inferred exactly as the engine does: `damage < currentHP` ⇒ survives.

**`mode = "cpp"` (validation replica):** a faithful reproduction of `Heuristics::DamageLoss_WillCost`
(`PrismataAI-dave-master/source/ai/Heuristics.cpp:158-242`) — inflated-WillScore basis, non-fragile-survivor → 0,
the fragile damage-ratio branch, the 1-HP `1.875` pin, Forcefield `3.75`, the `0.001` charge/lifespan/exhaust
epsilons, first-min-loss-wins. **Reproduce its quirks verbatim — including the `damageTaken/getStartingHealth`
ratio bug — so the gate matches the engine bit-for-bit.** Nothing is "fixed" in this mode.

**`mode = "ours"` (functional heuristic):**
- **Dies (chump):** `loss = V(unit)` — full value (body + production), with `lifespan==1 → 0` and the doomed nudge.
- **Survives, non-fragile (prime or untouched):** `loss = 0` (repairs; HP never reduced).
- **Survives, fragile (prime):** `loss = body(currentHP) − body(currentHP − damage)` (recall from §4.2 that
  `body()` already projects one heal, so the "after" value is heal-aware — do not add heal twice). Production
  cancels (retained); this is the permanent HP value lost net of one heal — **0** when within the heal headroom
  (`max(0, HP + heal − max)`), HP-proportional beyond it.
- Uses **current/max HP, never startingHealth** (the C++ ratio bug fixed here, in this mode only).

### 4.4 Value-fn finalization (apply at the START of implementation)

These corrections to the v2 model are agreed and must be applied before the sim runs (captured during the
brainstorm):
1. **Doomed-body nudge** (replaces the wrong geometric idea): keep `lifespan==1 → 0`; for `lifespan ≥ 2` subtract a
   small penalty `0.1 · (1 + maxLife − remainingLife)` (HP-scaled variant `0.1 · HP · (1 + maxLife − remainingLife)`
   optional). **`const = 0.1` to start; adjust once the pipeline is running.** Rationale: a doomed unit keeps
   near-full *keep* value until its last turn (where it is
   a free chump), with only a small "finite tail / use-it-or-lose-it" discount — enough to land a Doomed Wall just
   below an equivalent ch0-Bombarder (charges do **not** recharge, so the Bombarder is correctly body-valued).
2. **Infusion Grid:** optionality bonus → **0.1** (a prompt 4HP→4×1HP *convert/fragment* for 1 red, gaining nothing
   important — not a "burst"); relabel the token-selfsac rule from "burst" to "convert/fragment".
3. **Attack-selfsac optionality → small tie-breaks** (Photonic Fibroid explicitly; Nitrocybe/Protoplasm ride the
   same constant). Exact magnitudes confirmable when applied (~0.2 proposed).

### 4.5 Module boundary

`defense_value.js` exports: `loss(unit, damage, mode)`, `V(unit, HP)`, and `isIsomorphic(a, b)` mirroring the C++
`Card::isIsomorphic` fields (type, owner, currentHealth, currentChill, charges, delay, constructionTime, lifespan,
dead, status). It depends only on the card library + the constants block. Unit-testable in isolation (feed a unit +
damage + mode, assert the loss). No replay/sim concerns leak in.

## 5. The defense sim (`defense_sim.js`)

A faithful JS port of the C++ `BlockIterator` (`PrismataAI-dave-master/source/ai/BlockIterator.cpp:50-118`):
- Group available blockers into **isomorphism classes** (`isIsomorphic`) — counts, not distinct instIds.
- **One-prime min-loss branch-and-bound:** chump (full-kill, takes full HP) units of a class; a single "last
  blocker" absorbs the remainder and survives. Minimize `Σ loss(unit, damage)` over the assignment.
- Tie handling reproduces the engine: **first minimal-loss assignment wins** (the BlockIterator's `tieBreakScore`
  channel is dead code, :60-65; ordering is by the value-fn's own `0.001` epsilons in `cpp` mode, by our value
  terms in `ours` mode).
- **Same search structure for both modes** (the Xaetron-heal play is reachable in the one-prime search — "chump
  down to the healer's heal-headroom, then prime the healer"; the current C++ misses it only because its value fn
  is heal-blind, not because of the search). The validation gate therefore exercises the identical search the
  engine uses.

**Inputs/outputs:** in = a State-A board (available units + incoming `D`). out = the chosen assignment as iso-
multisets `{chumps, prime, untouched}`, total loss, and (for the tie-break diagnostic) the set of near-tied
alternative assignments within ε.

## 6. State extraction (Sections 4 of the original handoff, with the corrected reading)

**State A — AI input (begin-of-defense).** `eval/replay_to_request.js` + a `--defense-only` predicate
(`gameState.phase==='defense' && incomingAttack>0`). The existing `--all` loop walks every ply; we filter to
defense-with-attack and emit one State-A JSON per such phase, **both players**, per replay. These are clean turn-
start states; F6-equivalence is **proven** (handoff §3) and the C++ round-trip lossiness does not apply
(no damage/targets at turn start).

**State B — human ground truth (committed defense).** New capturer via the `recordClick` monkeypatch (handoff §5):
last-write-wins keyed per turn, emit the committed just-before-swoosh board at each turn boundary. Undo-robust by
construction (a re-defend overwrites the stale candidate; the candidate surviving to the next turn boundary is the
real decision). Investigate the `Analyzer.endDefenses` shortcut first — it may yield B directly. **Read-only;
never fed to the C++ engine** (its `initFromJSON` is lossy on mid-defense frames).

**Reading the human's pick from State B (corrected — full damage assignment, not "the prime"):** for **each
available unit**, read `damageTaken` + alive/dead from the serialized table and classify:
- `damageTaken ≥ HP` (dead) → **chump**.
- `0 < damageTaken < HP` (alive) → **prime** (exactly one for a clean non-breach defense; non-fragile primes show
  `damageTaken>0` but full `currentHealth`, so they are still identifiable).
- `damageTaken == 0` → **untouched**.
Map each committed unit by instId back to its State-A iso-class, so the human pick is an iso-multiset assignment
directly comparable to the sim output.

## 7. Metrics & the per-position record

### 7.1 Why exact-match alone is wrong, and the metric stack

Elite humans are not oracles and many positions have multiple justifiable defends, so the **primary** metric is
value-gap, not identical clicks:

1. **Regret (primary, the eventual tuning objective):** `regret = max(0, loss_ours(humanSet) − aiMinLoss_ours)`.
   Zero ⇒ our heuristic ranks the human's actual defense as (tied-)optimal. Positive ⇒ we think they erred (review
   candidate). Computed for `ours` and for `cpp` (baseline). A *negative* raw difference is impossible if
   enumeration is correct → logged as an **enumeration-bug tripwire**.
2. **Exact-match-iso (secondary, descriptive):** `human.assignment ∈ {our tied-min-loss assignments}` — membership,
   so any tied-optimal play counts and any-Engineer-of-N matches (iso, not instId).
3. **Prime-match:** human's prime iso-class == sim's prime iso-class.
4. **Tie-break-skew (the misvaluation detector).** Metric (1) is blind to misvaluations *inside* our own value
   system: if our numbers wrongly tie two genuinely-unequal options, a human who systematically breaks the tie one
   way reveals the error. On positions with ≥2 sim assignments within ε, log the human's choice and the iso-class
   **feature contrast** vs the tied alternatives. Aggregated, this is a ranked list of "numbers needing a corrective
   term" (e.g. the Doomed-Wall-vs-ch0-Bombarder lean would surface here).
5. **Per-unit divergence:** per position, the symmetric difference of chump-sets (`aiChumped-not-human`,
   `humanChumped-not-ai`) by iso-class.

### 7.2 Per-position record (rich, tuner-ready — JSONL)

```js
{
  id: {replay, turn, player}, incomingAttack,
  available: [{isoClass, count, hp, fragile, heal, max, charge, lifespan}],
  human:   {assignment:[{isoClass, role:'chump'|'prime'|'untouched', count}], loss_ours, loss_cpp},
  ai_ours: {assignment, loss, tiedAltsWithinEps:[{assignment, loss}]},
  ai_cpp:  {assignment, loss},
  metrics: {regret_ours, regret_cpp, exactMatch_ours, exactMatch_cpp, primeMatch_ours, primeMatch_cpp},
  diag:    {chumpDiff_ours:{aiOnly, humanOnly}, tieBreakContrast:[...]},
  tags:    [chillPresent?, forcedSingleFeasibleSet?, multiPartialSurvivorAnomaly?]  // >1 unit with partial damage contradicts the one-prime model → investigate
}
```

### 7.3 Aggregate report

- Regret distribution + `% zero-regret`, `ours` vs `cpp`, **stratified** by `forced` vs real-choice and by
  `chillPresent` (so trivial/forced positions don't bury the signal).
- Exact-match-iso % and prime-match %, ours vs cpp.
- **Per-iso-class divergence table** — ranked by how often the AI chumps/saves it differently from humans.
- **Tie-break-skew table** — ranked by iso-class *pair*, the human's lean % when our heuristic ties them
  (the prioritized "corrective-term candidates" list).

Everything keys on iso-classes so it feeds a future tuner directly: regret = the loss to minimize; the
skew/divergence tables = where to apply corrective terms.

## 8. Validation gate (one-time)

Prove the JS sim (the BlockIterator port + `cpp` value replica) reproduces the real engine's defense picks.
- Drive the real engine via `query_move.js` → the steam bundle `C:/libraries/DSNN_steam_bundles/v221_rl_iter8/`
  (`use_dsnn.txt`) with **`think_time=0`, `max_traversals=1`** — owner-verified (2026-06-24) to emit a move at
  **< 0.5 s/process**. Defense is a deterministic `PartialPlayer` that runs *before* and *independent of* the UCT
  search, so the search budget does not affect the defense assignment — only the defense clicks are read; the
  degenerate action half is ignored. (Any DSNN bundle works: defense is shared code untouched by the net.)
- Run **100 full games** (thousands of defense positions; fast at < 0.5 s/process). **Pass** = the sim's defense
  assignment (iso-multiset) matches the engine on every position (whitelist `timeRemainingMS`).
- This licenses the sim for all `ours` runs. The **state generator** is validated separately and already proven
  (handoff §3 `oracle_diff.js`), so the two concerns don't entangle.

## 9. Position scope (capture rules)

- **Capture every defense phase, both players, `incomingAttack > 0`.** No decision-relevance pre-filtering at
  capture (forced positions score regret 0; stratify in the report).
- **Breach positions: skip** — a breached player had no defense phase to grade.
- **Chill present: include** — frozen units are simply unavailable blockers; the heuristic handles that. (Opponent's
  *unused* chill potential is a later board-aware layer.)
- **No created-blockers in defense** — the only defense choice is how to apply incoming damage to existing units
  (creation is action-phase).
- **Exclude (no decision):** no-attack turns (already filtered) and forced single-feasible-assignment positions
  (tagged, kept for completeness, separated in the report).

## 10. Corpus, runtime, outputs

- **Corpus:** elite (2000+ ELO) games from `c:/libraries/prismata-replay-parser/replays_archive`; ~1000 games →
  ~25k defense positions (both players). Build/validate on a small dev corpus (~20–50 games) first, then the full
  run; re-fetch missing codes from S3 (handoff §8–9).
- **Runtime:** the JS sim is in-process and fast; measure the full ~1000-game wall-clock once built — that number
  sizes the future tuner's test set. The only slow piece is the one-time ~20-min validation gate.
- **Outputs:** per-position records → JSONL; aggregate report → markdown + raw stats.

## 11. Out of scope (Phase A) & known limitations

**Deferred to their own work:**
- The **automated constant-tuner** (own spec, fed by this pipeline's data — the regret objective + the
  skew/divergence tables are designed to be its inputs).
- The **C++ port** of `DamageLoss_Functional` (after the model is locked and validated offline; it must fix the
  Heuristics.cpp:194 startingHealth ratio bug and the :219/:221 double `-= tieBreakLoss`).
- **Board-aware layers:** opponent unused-chill potential, drone-kill denial value.

**Known limitation — multi-turn heal projection (will cause a wrong play; DEFER + recorded):** `V(HP)` projects only
ONE heal, so a deeply-damaged healer is under-credited. Concrete counterexample — **Energy Matrix + Xaetron@5, 9
incoming:** (A) chump Xaetron, EM prime → loss = V(Xaetron@5) = **19.7**; (B) chump EM, Xaetron prime
(5→1→heals 5) → loss = V(EM 11) + δ_Xaetron(19.7−10.9 = 8.8) = **19.8**. We pick (A) by 0.1 — **chump the healer** —
which is wrong (Xaetron climbs back to a 12-HP fortress and dwarfs a static 5-HP wall). It's a knife-edge (0.1), so
the static model is "almost right." **This pipeline is the instrument to fix it:** healer-preservation positions
will surface as regret/divergence vs elite humans, sizing a forward-looking healer term (multi-turn projection or a
"keep the healer" bonus) and confirming it doesn't disturb other pairs. Detail: heuristic handoff §16.

## 12. Suggested build order

1. **De-risk State B (small):** confirm `beginTurnHistory` collapses cross-swoosh undos on a known undo-heavy local
   pro replay; check whether `Analyzer.endDefenses` yields B directly (handoff §10 step 1).
2. `defense_value.js` — port `V`/`body`/`loss` (both modes) + `isIsomorphic`; apply the §4.4 fixes; unit tests.
3. `defense_sim.js` — the one-prime BlockIterator port consuming `defense_value.js`.
4. **Validation gate (§8)** — `cpp` mode vs `query_move` on 50–100 games; gate must pass before trusting `ours`.
5. State-A `--defense-only` predicate; validate one code via `oracle_diff`.
6. State-B capturer (§6).
7. Comparison harness + metrics/report (§7) over the dev corpus, then the full ~1000 games.

## 13. Key file references

| Path | What |
|---|---|
| `docs/scratch/2026-06-20-defense-eval-pipeline-handoff.md` | original harness scope: State A/B, undo-collapse recipe (§5), F6-equivalence proof (§3), file/line table |
| `docs/scratch/2026-06-22-unit-value-heuristic-v3-handoff.md` | functional value model; §16 = `DamageLoss_Functional` survivor-delta + prime-absorber design |
| `docs/scratch/gen_our_numbers_v2.js` / `our_numbers_v2.md` | the live functional value model + current per-unit table |
| `eval/replay_to_request.js` | State-A emitter; add `--defense-only` |
| `js_engine/replay_exporter.js` | `stateToCppJSON` serializer (A and B) |
| `js_engine/query_move.js` | drives the dave-master Defense_Solver (validation gate) |
| `js_engine/oracle_diff.js` | state-generator validator + the `recordClick` monkeypatch pattern for State B |
| `js_engine/Analyzer.js` | `beginTurnHistory`, `recordClick` hook, `endDefenses` |
| `PrismataAI-dave-master/source/ai/BlockIterator.cpp` | the one-prime search to mirror (recursion :50-118; dead tie-break :60-65) |
| `PrismataAI-dave-master/source/ai/Heuristics.cpp` | `DamageLoss_WillCost` to replicate in `cpp` mode (:158-242; the :194 ratio bug, :219/:221 double-subtract) |
| `PrismataAI-dave-master/source/engine/Card.cpp` | `takeDamage` (:389-423), `beginOwnTurnPhase` heal (:609-636) — the survivor/heal mechanics |
