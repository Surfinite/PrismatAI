# Defense-Eval Pipeline — Build + Results Handoff (for the planning session)

> **To the session that wrote the plan/spec** (you hold the discussion behind the functional value
> numbers in `docs/scratch/gen_our_numbers_v2.js`): the pipeline you specified is **built, validated,
> and run on 5,000 elite games**. This doc summarizes what was done, where deviations happened, where
> everything lives, what the results show, and frames the decision you're being asked to advise on:
> **hand-tune the value numbers first, or build an auto-tuner.**

Date: 2026-06-24. Branch: `feature/production-vectors` (pushed to `PrismatAlpha`, HEAD `e141b3f9`).
Built from: `docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md` +
`docs/superpowers/plans/2026-06-24-defense-eval-pipeline.md` (12-task TDD plan) +
`.../2026-06-24-defense-eval-implementation-handoff.md`.

---

> **UPDATE 2026-06-25 — audit fixes applied; numbers below are CORRECTED.** An independent
> adversarial audit (`docs/superpowers/plans/2026-06-24-defense-eval-audit-findings.md`) found four
> localized defects; all are now fixed (commit on `feature/production-vectors`) and the corpus re-run.
> The two that moved the headline: **② FP-dust** in the regret equality (exact `===` counted true
> 0-regret as a miss on ~1e-13 dust, asymmetrically against ours) and **③ asymmetric exact-match** (ours
> used its full tied-min-loss set; cpp only its single chosen pick). Also: **④** the divergence table
> censored same-class count differences (set-diff dropped multiplicity); **①** doomed fragile/
> undefendable units valued negative at `life==1` (terminal {v:0} took the undef/fragile haircuts).
> The tables/headline in §1/§5/§6 below have been updated to the corrected values.

## 1. TL;DR — what the run says

Over **5,000 elite (2000+ ELO) games → 55,839 defense positions** (~75 s, 0 skipped), **post-audit-fix**:

| metric (vs elite human defense) | **ours (functional)** | current C++ (`DamageLoss_WillCost`) |
|---|--:|--:|
| mean regret | 0.383 | 0.356 |
| **zero-regret** (ranks human optimal) | **82.7%** | 84.7% |
| exact-match-iso | 82.7% | **84.7%** |
| prime-match | 88.7% | 91.7% |

Read: the functional model is **competitive but trails the strong engine's own metric by ~2pp** (was
mis-reported as ~4pp before the FP fix). It does **not** lead on exact-match — the prior "ours 82.6 >
cpp 81.6" was the apples-to-oranges ③ bug; like-for-like (tied-set membership for both modes), **cpp
leads on both zero-regret and exact-match**. **~80% of positions are forced** (one min-loss defense),
so the signal lives in the ~20% genuine-choice positions and in the per-unit divergence/skew tables.
**Caveat:** regret measures agreement with *elite humans*, not ground-truth optimality — humans aren't
perfect oracles, so "close the gap to humans" is the working objective, not a proof of correctness.

The concrete tuning to-do list (from the divergence + tie-break-skew tables) is in §5.

---

## 2. What was built (the harness)

A CommonJS toolset under `eval/defense/`, driven by the repo's faithful JS engine (`js_engine/`). For
each elite replay it extracts **State A** (begin-of-defense = the AI's input) and **State B** (the
human's committed defense = ground truth), runs a one-prime min-loss block-assignment search with a
pluggable per-unit value function (`ours` = the functional model; `cpp` = a faithful
`DamageLoss_WillCost` replica), and emits regret/divergence statistics.

All 12 plan tasks completed TDD-style with per-task review; **31 tests pass** (`node --test
eval/defense/*.test.js` — use the glob, the bare-dir form errors on Node 24).

---

## 3. Deviations from the plan (important — these change assumptions in the plan/spec)

1. **`defense_sim` ported the *real* `BlockIterator`, not the plan's recursion** (Task 7). The plan's
   example recursion was wrong at two boundaries: `hp == remaining` (the engine's `isLastBlocker` uses
   `>=`, so such a unit is a valid *dying* last blocker) and exact-absorb (chumps zero the damage → a
   solution with no surviving prime). The port matches the engine; verified by an independent
   brute-force oracle (8,000 scenarios, both modes, 0 mismatches).

2. **State-B capture is native engine navigation, not a per-click snapshot** (Task 9 + rework). The
   plan's `recordClick` monkeypatch deep-cloned the whole board on *every* click → OOM on long
   replays. Replaced with `Analyzer.gotoCommand(endDefenses[i])` (the same forward/back navigation the
   prismata.live viewer uses); **proven byte-identical** to the old capture on the fixture. This also
   surfaced a *second* OOM in `defense_sim.solveDefense` (exhaustive solution enumeration) — fixed
   with **branch-and-bound** pruning (output-identical; ~84k-scenario oracle). Net: `compare.js` is a
   simple in-process loop, no subprocess workarounds.

3. **`compare.js` was solving defense on non-blockers** (caught during this session). Its
   `availableBlockers` lacked the `canBlock` check that `validate_gate.js` had — so it fed the search
   Drones/Conduits/Blastforge/etc. (e.g. 38 "blockers" where the real count was 9). Fixed by a
   **shared `blockers.js`** used by both `compare.js` and `validate_gate.js` (they can't drift again).
   This both corrected the metrics and cut per-game time 15.6s → ~25ms.

4. **`lifespan: -1` sentinel value bug** (caught this session). The engine emits `lifespan = -1` for
   *non-doomed* units; `unitView` passed it into `ours()`, which read it as a doomed unit with -1
   turns left and **inverted the charge/attack value** (e.g. Tia Thurnax @4/ch3: +41.08 → **-34.86**),
   making the heuristic want to *sacrifice* valuable units on defense. Fixed in `unitView`: normalize
   `-1` (and any `<1`) → `undefined`; keep real doomed remaining-lifespans (`>=1`). **This is the kind
   of value-layer bug the gate could not catch** — the gate validates `cpp` mode (which guards `-1`),
   not `ours`. The eval itself surfaced it (implausible regrets).

5. **Iso-class drops the `status` field** (this session, at the owner's direction). The plan's `isoKey`
   mirrored C++ `Card::isIsomorphic` including `getStatus()` (inert/sellable/default). For DEFENSE,
   status is irrelevant to value/canBlock, and a unit bought last turn keeps a stale `sellable` tag
   into its next defense phase (it can't actually be sold/bought during defense). Including status
   minted spurious duplicate iso-classes. Dropped it — now consistent with the gate's own `classSig`
   (which already excluded status).

6. **§4.4 value-fn fixes applied** (Task 2, as the plan specified): doomed-body nudge `0.1`,
   Infusion-Grid optionality `0.5→0.1`, attack-selfsac optionality `1.0→0.2`. The value model is
   otherwise **unchanged** ("leave the numbers").

7. **Report overhaul** (this session): the aggregate report keys by a unit-value-key
   (`internal|hp|charge|lifespan`, merging owner/status/chill), uses **display names**, shows the
   differentiating attributes as **columns** (`Unit | HP | Charge | Lifespan`), and cites example
   `replay@turn` per row. A **value-sanity tripwire** flags suspicious negative-min-loss positions
   (`< -1`) on every run (would have caught the lifespan bug).

### Structural note the planning session should know
The **validation gate only covers `cpp` mode** (it matches the real engine's `DamageLoss_WillCost`).
There is **no engine oracle for `ours`** (it's a proposed heuristic). So `ours` is validated only by:
(a) the gate licensing the shared *search* (1234/1235), (b) state-fidelity (states are real), and
(c) the regret/tripwire sanity. Bugs in the `ours` value layer surface as implausible regrets, not as
gate failures — that's how the canBlock and lifespan bugs were found. The tripwire now automates that.

---

## 4. Where everything lives

| Path | What |
|---|---|
| `docs/scratch/gen_our_numbers_v2.js` | **The functional value model** (`ours()`), require-able; §4.4 fixes applied; the numbers to tune live here. `our_numbers_v2.md` = generated table. |
| `eval/defense/defense_value.js` | per-unit `V`/`body`/`loss` (ours+cpp), `unitView`, `isoKey`/`decodeIso` (status-free), `canBlock` value-layer. |
| `eval/defense/blockers.js` | shared `canBlockState`/`availableBlockers` (engine-faithful blocker filter) — used by compare + gate. |
| `eval/defense/defense_sim.js` | one-prime min-loss search (BlockIterator port + branch-and-bound). |
| `eval/defense/state_b_capture.js` | committed-defense reader (native `endDefenses`/`gotoCommand`). |
| `eval/defense/metrics.js` | regret / exact-match / prime-match / per-unit divergence / tie-break-skew / tripwire aggregation. |
| `eval/defense/compare.js` | the harness CLI: `node eval/defense/compare.js <codesFile> <outDir>`. |
| `eval/defense/report.js` | renders the aggregate markdown (display names, columns, citations, tripwire). |
| `eval/defense/validate_gate.js` | one-time `cpp`-vs-real-engine gate (1234/1235; the 1 is a deployed-binary tie-break, regret-neutral). |
| `eval/defense/validate_state_fidelity.js` | **JS-state == F6 ground-truth** check (56/57 dumps byte-identical; collision-robust). |
| `eval/replay_to_request.js` | `--defense-only` State-A emitter. |
| `eval/defense/results/report.md` | **the 5000-game results report** (committed). |
| `eval/defense/results/records.jsonl.gz` | 55,839 tuner-ready per-position records (committed, gzipped; raw is gitignored). |
| `training/data/human_elite_2000_45s_v2.provenance.json` | `selected_codes` (5000) = the corpus. |

Reproduce: `node eval/defense/compare.js <codesFile> <outDir>` (replays must be cached in
`c:/libraries/prismata-replay-parser/replays_archive`). Validation: `node
eval/defense/validate_state_fidelity.js` and `node eval/defense/validate_gate.js <codesFile>`.

---

## 5. What the results show — the tuning signal

The per-unit **divergence** table (where ours chumps/saves a unit differently than elite humans) and
the **tie-break skew** table (when ours ties two options, which one humans systematically pick) point
at a small, concrete set of value corrections. Top signals (`eval/defense/results/report.md` has the
full tables with `replay@turn` citations for every row):

(Counts below are **post-④** — multiset-aware, so same-class count differences are no longer censored;
magnitudes are ~2–3× the pre-fix numbers, direction unchanged.)

**Ours OVER-chumps (treats as cheaper than humans do → likely under-valued):**
- **Wall (3hp): 4367 ai-only vs 1024 human-only** — the single biggest divergence. Ours sacrifices
  Walls; humans keep them.
- **Forcefield (2hp): 2559 vs 129**, **Nitrocybe (1hp): 1054 vs 66**, **Protoplasm (4hp): 585 vs 0**,
  **Husk (1hp): 682 vs 266**.

**Ours UNDER-chumps (treats as more valuable than humans do → likely over-valued for defense):**
- **Engineer (1hp): 1571 vs 7805** — the biggest the other way. Humans throw Engineers as chump
  fodder; ours keeps them.
- **Rhino (2hp, ch2): 283 vs 1468**, **Drone (1hp): 34 vs 589**, **Perforator (2hp): 24 vs 555**,
  **Barrier (1hp, life1): 8 vs 516**, **Ossified Drone (2hp): 4 vs 457**, **Steelsplitter (3hp):
  28 vs 350**.

**Tie-break skew (corrective-term candidates — humans break ties our model leaves even):**
- When ours ties a bigger body against a **Wall**, humans **keep the Wall** and chump the bigger unit:
  Rhino/Urban Sentry/Borehole/Arka Sodara/Centurion/Perforator/Ossified Drone/Bombarder/Energy
  Matrix/Xeno Guardian/Valkyrion all-vs-Wall lean strongly to chumping the non-Wall.
- But humans **chump Steelsplitter over Wall** (221:31) and **Odin over Steelsplitter** (33:1).
- Doomed-unit lifespan matters: humans chump the **lower-lifespan Doomed Wall** first (life2 over
  life3, 34:3) — a sensible "use-it-before-it-expires" ordering.

Rough reading: **Walls (and other cheap pure-blockers) are under-valued and Engineers over-valued in
the `ours` defense loss**, and there's a systematic "**keep the cheap Wall, chump the bigger body**"
tie-break the model doesn't yet encode. These are the first knobs to move.

---

## 6. Validation status (so you can trust the numbers)
- **State generation is faithful**: JS-engine `gameState` is **byte-identical to F6 dev-mode dumps**
  on 56/57 real dumps across 14 replays (the 1 is a hand-built counterfactual). So the states fed to
  the sim/engine are the real ones.
- **The `cpp` sim reproduces the real engine**: gate = **1234/1235** defense positions over 100 games
  (the 1 residual is a deployed-binary tie-break among equal-min-loss defenses — regret-neutral,
  unreproducible from the open `BlockIterator` source).
- **Tripwire fully clean** (post-①): **0 negative-min-loss, 0 suspicious**. The prior 62 negatives were
  exactly the `life==1` fragile/undefendable doomed units (fix ① now values them 0), and the threshold
  is tightened to −0.3 so future value-layer regressions surface.

---

## 7. The decision you're being asked to advise on: hand-tune vs auto-tune

Context that bears on it:
- **The eval is cheap**: 5,000 games / 55,839 positions in **~2 minutes**, single-threaded, pure JS
  (no engine `.exe`). So an auto-tuner's inner loop (edit constants → re-run → read regret) is ~2 min
  per evaluation — fast enough for coordinate-descent / grid / black-box optimization over the value
  constants.
- **The signal is concentrated and interpretable**: the divergence/skew tables name a *small* set of
  corrections (Wall up, Engineer down, a keep-cheap-blocker tie-break term). A handful of hand edits to
  `gen_our_numbers_v2.js` + a re-run would immediately show whether the metric moves and whether the
  model responds as expected — and would *validate the harness as a tuning instrument* before trusting
  an optimizer with it.
- **Risks for auto-tuning**: (a) the objective is *agreement with elite humans*, who are not optimal —
  over-fitting to them could degrade genuinely-good plays; (b) many of the model's constants encode
  deliberate design decisions (your context) — an optimizer doesn't know which are sacred; (c) ~80% of
  positions are forced (regret 0 regardless), so the optimizer effectively trains on the ~20%
  genuine-choice subset — worth stratifying the objective.
- **A pragmatic middle path** (my suggestion, not a decision): **hand-tune the few clear divergences
  first** (Wall/Engineer/Forcefield + a keep-cheap-blocker tie-break term), confirm the harness moves
  the right way and the model is responsive, *then* — if you want to push further — parameterize the
  constant set and let an optimizer minimize mean-regret / maximize zero-regret on the genuine-choice
  stratum, with the hand-tuned point as the seed and a held-out game split to watch for over-fit. The
  records.jsonl already carries everything an optimizer needs.

This is exactly the call to make with your context on *why* each number is what it is — which is why
this is handed back to you.

---

## 8. Outstanding / known items
- **`ours` has no engine oracle** (structural — §3 note); rely on the tripwire + regret sanity.
- The `cpp`/`ours` regret are each measured in their *own* value system (self-consistency with human
  play), so the head-to-head is "which agrees with elite humans more often," not a direct A/B of
  defensive strength.
- A few `lossCpp` approximations remain (documented in `defense_value.js`: `isAbilityHealthUserOnly`,
  Forcefield/resonate) — they passed the gate, so they're correct for the validated corpus, but flagged
  for completeness.
