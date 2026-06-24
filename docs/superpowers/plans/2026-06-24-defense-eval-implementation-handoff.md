# Defense-Eval Pipeline — Implementation Handoff (subagent-driven)

> Paste the "KICKOFF PROMPT" at the bottom into a fresh session, or just say:
> *"Read docs/superpowers/plans/2026-06-24-defense-eval-implementation-handoff.md and execute it."*

## Your task

Implement the defense-eval pipeline by executing the plan at
**`docs/superpowers/plans/2026-06-24-defense-eval-pipeline.md`**, **subagent-driven**.
REQUIRED SKILL: `superpowers:subagent-driven-development` — a fresh subagent per task, with a
two-stage review between tasks. The implementation has NOT been started; begin at Task 1.

## Read first (in order)

1. **The plan** — `docs/superpowers/plans/2026-06-24-defense-eval-pipeline.md`. 12 TDD tasks with
   complete code, exact file paths, and the test cases. This is your executable spec.
2. **The design spec** — `docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md`. The
   *why* behind each task (the corrected one-prime mechanic, the single-objective/pluggable-loss
   design, the metric stack).
3. **Background (consult as needed)** — `docs/scratch/2026-06-20-defense-eval-pipeline-handoff.md`
   (State A/B extraction, the undo-collapse recipe §5, the F6-equivalence proof §3) and
   `docs/scratch/2026-06-22-unit-value-heuristic-v3-handoff.md` §16 (the `DamageLoss_Functional`
   survivor-delta rationale + the worked examples).

## Execution protocol

- Use `superpowers:subagent-driven-development`. Dispatch ONE subagent per task, **Tasks 1–12 in
  order** (they have dependencies — value model → defense_value → defense_sim → harness → gate).
  Review each subagent's deliverable before dispatching the next.
- Every task is TDD: failing test → minimal implementation → passing test → commit. The plan carries
  the exact code and assertions (your worked examples *are* the unit tests).
- **Commit after each task** (the plan has the commit commands). **Local commits only — DO NOT push.**
  Branch is `feature/production-vectors`; push only when the owner explicitly asks.
- **The hard correctness checkpoint is Task 12 (the validation gate):** the `cpp`-replica sim must
  match the real engine's defense picks on 100 games (0 mismatches). The plan deliberately routes the
  few unavoidably-empirical details there — `query_move`'s defense-click field name, and the
  `lossCpp` `isAbilityHealthUserOnly`/Forcefield approximations. **Iterate Task 12 until 0 mismatches
  before declaring the pipeline done.**

## Critical non-obvious context (the things that will bite)

1. **WHICH ENGINE.** The strong engine is `c:/libraries/PrismataAI-dave-master` (engine_v1, branch
   `dave-master-jsonclean`). THIS repo's `source/` is the **INDICTED engine_v2 — do NOT read or build
   it.** The card library and the C++ heuristics you mirror live in dave-master; the faithful JS engine
   (`Analyzer.js`, `replay_exporter.js`, `query_move.js`) is in THIS repo's `js_engine/`.
2. **The defense mechanic is ONE-PRIME (subtle — it was gotten wrong twice during design).** Chumps are
   FULL-killed (take ≥ their HP); exactly ONE prime takes partial, non-lethal damage and survives; every
   other available unit takes ZERO damage and survives untouched. Multiple units survive (the prime +
   the untouched), but only one takes partial damage — there is NO damage-splitting across survivors.
   Spec §2.
3. **The value model is LOCKED** ("leave the numbers"). The plan's **Task 2** applies exactly three
   agreed fixes — doomed-body nudge `0.1·(1+maxLife−remainingLife)`, Infusion Grid opt `0.1`,
   attack-selfsac opt `0.2`. Apply those, nothing more. Do not re-tune the model.
4. **CommonJS + `node:test`.** All new modules use `require`/`module.exports` (match
   `docs/scratch/gen_our_numbers_v2.js`). Tests use the built-in runner: `node --test <file>`.
5. **Card library:** `c:/libraries/PrismataAI-dave-master/bin/asset/config/cardLibrary.jso`, keyed by
   **INTERNAL** name (Husk=House, Energy Matrix=Golem, Infusion Grid=Hotel, Steelsplitter=Treant, …);
   `UIName` is the display name. `defense_value.unitView` resolves either form.
6. **The heal is encoded once** in `body(HP) = min(HP+heal, max)·BV`, so it flows uniformly to the prime
   (survivor-delta), the untouched (standing value), and the chump (full loss). Do NOT add heal twice.
7. **Two value modes share ONE search** (`defense_sim`). `cpp` mode = a faithful `DamageLoss_WillCost`
   replica **with its bugs intact** (so the gate matches the engine bit-for-bit, incl. the
   `damageTaken/getStartingHealth` ratio and the `:219/:221` double-subtract). `ours` mode = the same
   logic with the bugs fixed (current/max HP, never startingHealth). The lineup-awareness lives entirely
   in the per-unit loss, not the search structure.
8. **A tiny `eval/defense/_find_replay.js`** (archive lookup mirroring `oracle_diff.js findFile`:
   try `<code>.json.gz`, then URL-encoded `+`→`%2B`/`@`→`%40`) is referenced by Tasks 8/11/12 — create
   it during Task 8.
9. **Validation gate driver:** the steam bundle `C:/libraries/DSNN_steam_bundles/v221_rl_iter8/` at
   `think_time=0`, `max_traversals=1` (owner-verified < 0.5 s/process). Defense is a deterministic
   PartialPlayer that runs before/independent of the UCT search, so the search budget does not change
   the defense assignment — only the defense clicks are read.

## Known limitation already recorded — do NOT try to fix it

The **multi-turn heal projection** (one-heal undercounts a deeply-damaged healer; concrete wrong-play:
Energy Matrix + Xaetron@5, 9 incoming → our numbers chump the healer by 0.1) is a DEFERRED candidate
refinement, recorded in spec §11 and heuristic handoff §16. It is OUT of scope; this pipeline is the
instrument to size its fix later. Don't re-litigate or patch it now.

## Status (nothing pushed)

- Branch `feature/production-vectors`. Local commits this session:
  - `cba46309` — v3 heuristic handoff §16 + the locked functional value model (`gen_our_numbers_v2.js`).
  - `8452222` — the design spec (+ doomed-nudge 0.1 / 100-game gate adjustments).
  - `c55e322f` — the implementation plan.
- The implementation itself is **not started**. Start at Task 1.

## Owner working style

Incremental, code-provable, low-regression; surface findings, don't over-produce. **Token/subagent
usage is NOT a constraint** (only AWS spend is cost-sensitive — irrelevant here). Don't push or open
PRs without asking. The owner is a self-described git noob — do routine local commits sensibly and say
what you did; pause only before remote/destructive git actions.

---

## KICKOFF PROMPT (paste into a fresh session)

```
Implement the defense-eval pipeline, subagent-driven. Start by reading
docs/superpowers/plans/2026-06-24-defense-eval-implementation-handoff.md (the handoff with all
critical context), then execute docs/superpowers/plans/2026-06-24-defense-eval-pipeline.md using
the superpowers:subagent-driven-development skill — one fresh subagent per task, Tasks 1–12 in
order, TDD with a commit after each, review between tasks. Local commits only on
feature/production-vectors; do not push. The correctness anchor is Task 12 (the 100-game cpp-replica
validation gate) — iterate it to 0 mismatches before declaring done. Critical: use the dave-master
engine (this repo's source/ is the indicted engine_v2 — ignore it); the defense mechanic is ONE-PRIME
(chumps full-killed, one partial-damage prime, the rest untouched); CommonJS + node:test.
```
