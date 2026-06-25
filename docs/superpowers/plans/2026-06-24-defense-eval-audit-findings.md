# Defense-Eval Pipeline — Audit Findings & Fix List (for the implementing session)

> Independent adversarial audit (4 parallel auditors) of the built+run defense-eval pipeline
> (`docs/superpowers/plans/2026-06-24-defense-eval-results-handoff.md`). Date: 2026-06-24.
> Branch `feature/production-vectors`. **Scope of this doc: four localized, fixable defects.** A
> separate heuristic *design* change (prime-defender perpetuity) is flagged at the end as
> **DO-NOT-IMPLEMENT-YET** — it will be specced separately.

## Verdict

The pipeline's **foundations are sound** and trustworthy: state generation is byte-identical to F6
(56 pass / 0 fail / 3 skip on re-run), the `cpp`-mode search is engine-faithful (independently
corroborated by a from-scratch C++ reimplementation across 39k scenarios + the gate's 1234/1235), and
the harness plumbing is correct (State-A/B join aligns 1:1, `gotoCommand` stops pre-swoosh, one-prime
human reading has 0 violations on real data, blocker filter shared between `compare` and the gate). The
three previously-self-reported fixes (canBlock, `lifespan:-1`, status-drop) are each individually
correct; the heal model, doomed nudge, survivor-delta, and loss boundaries are all faithful.

**But four defects need fixing before the numbers/tuning-signal can be trusted** — two of them
materially change the published headline. All are small. Three are recomputable from the committed
`records.jsonl` (no re-run); one is in the value model (needs the 2-minute re-run).

## The four bugs (prioritized)

### ② CRITICAL — floating-point dust inflates ours' deficit ~2× *(recomputable)*
`metrics.js:23` `regret_ours = Math.max(0, human.humanLoss - aiOurs.loss)` and `metrics.js:97`
`zeroRate_ours: ... regret_ours === 0` use **exact equality**. The human loss is summed in instId order
(`compare.js`), the sim sums the *identical physical assignment* in DFS order — FP non-associativity
makes them differ in the last ULP. **1,573 ours records are counted as misses on dust < 1.1e-13** (every
one also an exact-match); cpp suffers this only 319× (its tie-break epsilons make its sums coincide
bit-exactly more often) → an asymmetric penalty against ours.
- **Effect:** FP-corrected, **ours 79.8 → 82.6%, cpp 84.1 → 84.7% zero-regret — the gap collapses from
  4.3pp to ~2.1pp.**
- **Fix:** treat `|regret| < 1e-9` as 0 (consistent with the sim's own eps band) wherever regret is
  computed *and* counted (`metrics.js:23` clamp + `:97`/`:99` zero-test). Recompute from `records.jsonl`.

### ③ HIGH — exact-match comparison is apples-to-oranges *(recomputable)*
`metrics.js:30-32`: `exactMatch_ours` checks membership in ours' **entire tied-min-loss set**
(`tiedAltsOurs`), but `exactMatch_cpp` checks identity with cpp's **single chosen** assignment — cpp's
tied set is never computed. **1,923 records (3.44pp) credit ours an exact-match the cpp metric
structurally cannot earn.**
- **Effect:** like-for-like (single-chosen for both, or tied-set for both): **ours 79.2% < cpp 81.6% —
  the report's "ours 82.6 > cpp 81.6 on exact-match" REVERSES.**
- **Fix:** make it symmetric — either compute `tiedAlts` for the `cpp` solve too and use tied-set
  membership for both, or use the single chosen assignment for both. Recompute.

### ④ HIGH — divergence table censors same-class count differences *(recomputable)*
`metrics.js:37-40`: builds a chump multiset via `flatMap(Array(count).fill(isoKey))` then wraps it in
`new Set(...)`, discarding multiplicity; `aiOnly`/`humanOnly` are a pure set-difference. Any iso-class
**both** sides chump at different counts (AI 5 Engineers vs human 2) is in both sets and filtered out of
both. **4,809 records have exactly this same-class count divergence — invisible to the §5 table.**
- **Effect:** the §5 divergence *direction* (Wall over-, Engineer under-chumped) survives, but the
  *magnitudes* driving tuning are understated, and any class both sides touch is censored.
- **Fix:** multiset-aware divergence — count per-iso-class `max(0, aiCount − humanCount)` into `aiOnly`
  and `max(0, humanCount − aiCount)` into `humanOnly`, instead of set membership. Recompute.

### ① MEDIUM — `ours` mis-values genuinely-doomed fragile/undefendable units at `life==1` *(needs re-run)*
**Corrected scope (narrower than the auditor's first pass):** only units that are *both* doomed
(`lifespan`) *and* fragile/undefendable, on their final (`life==1`) turn. In `ours()`, the
`life===1 → {v:0, block:0}` terminal result has the fragile/undefendable haircuts applied to it
**unconditionally**, driving `block` negative:
- **Innervi Field** / **Chieftain** (fragile, lifespan 3) @ life=1 → **V = −0.1**
- **Thunderhead** (undefendable, lifespan 3) @ life=1 → **V = −5.5** (latent — only chumped on large
  incoming; would trip the tripwire as a *phantom* regression).

A negative chump-loss *rewards* the solver for sacrificing these. Measured reach is small (~9 records
firing at −0.1 in the 11k-subset; the −5.5 case latent). **Note:** the auditor's other examples
(Infusion Grid 8.9, Shiver Yeti 10.8, Photonic 4.6, Polywall −3.0) were artificial probes — those units
are **permanent (no lifespan)**, so they never reach `life==1` in real data; the "early-return branch
bypasses the terminal check" sub-defect is a **dead code path that never fires on the corpus** (no
chill/self-sac/netherfy unit is a lifespan unit). Fix it anyway for robustness, but it has zero current
corpus impact.
- **Fix:** in `gen_our_numbers_v2.js`, move the `life===1 → return {v:0,...}` check to the **top of
  `coreValue`** (before the chill/netherfy/self-sac branches — closes the dead path correctly), AND in
  `ours()` guard the fragile/undefendable haircuts so they do not apply to a terminal/zero unit (e.g.
  skip when the core `block === 0`/`v === 0`; a `max(0, …)` floor on `block` alone is insufficient — it
  masks the early-return path). Add a test exercising **`ours` mode at `life==1`** for a fragile and an
  undefendable doomed unit → expect `V = 0` (the existing 24 tests never hit `ours` at life=1). Re-run
  the 2-minute eval.

### LOW
- **Tripwire threshold too loose.** `metrics.js:146` flags only `loss < -1`, so it missed bug ① 's
  −0.1 cases (those are the "62 legitimate negatives" — they are *not* a doomed nudge) and would only
  catch the latent −5.5 as a false regression. After fixing ①, tighten the suspicious threshold toward
  **−0.3** (clear of the legitimate ~−0.1 doomed-nudge band) so future value-layer regressions surface.
- **`ours`-search omits the C++ depth-0 zero-loss early-return** (`defense_sim.js:133-140` vs
  `BlockIterator.cpp:92-96`). This is **beneficial** in `ours` mode (it finds the true min the engine
  would skip on a negative-loss term) — not a bug, but undocumented. Add a one-line note to the
  deviation comment (`defense_sim.js:24-34`) so a future reader doesn't assume `ours` == C++ search
  exactly. (Once ① is fixed, the only remaining `ours` negative term is a single Polywall@1 = −0.8,
  which is itself arguably the same class of issue — worth a look but not blocking.)

## Corrected headline (after the recomputable fixes ②③; before the value re-run ①)

| metric vs elite human | ours | current C++ |
|---|--:|--:|
| zero-regret (FP-corrected) | **82.6%** | 84.7% |
| exact-match (like-for-like) | **79.2%** | 81.6% |

So ours genuinely trails the strong engine's own metric by **~2pp, not ~4pp**, and does **not** lead on
exact-match. Fixing ① should *help* ours (it currently inflates ours' regret on those positions), so
the true gap is likely a touch smaller still.

## Recommended fix order
1. **① value-layer `life==1` fix** in `gen_our_numbers_v2.js` (+ the `ours`-mode life=1 test) → re-run
   `node eval/defense/compare.js <codesFile> <outDir>` (~2 min).
2. **②③④ metric-aggregation fixes** in `metrics.js` (FP-tolerant regret equality; symmetric exact-match;
   multiset-aware divergence) → recompute the report from `records.jsonl` (or fold into the re-run).
3. **Tighten the tripwire** to −0.3 and **document the search deviation** (`defense_sim.js:24-34`).
4. Regenerate `eval/defense/results/report.md`; the corrected headline + un-censored divergence
   magnitudes are what the planning session reads to decide hand-tune vs auto-tune.

Every fix is a few lines; the instrument itself is trustworthy once they land. **Do not change the
heuristic's prime-defender logic as part of this** — see below.

## DO-NOT-IMPLEMENT-YET — the prime-defender design direction (separate discussion)

The §5 tuning signal (ours over-chumps HP-efficient permanent blockers like Wall, under-chumps
Engineers) is **real and mechanism-confirmed**: `lossOurs` charges a dying non-fragile blocker its full
one-soak `V` and a surviving one `0`, so among chumps the solver picks the lowest **value-per-HP** unit
(Wall 2.2/HP < Engineer 3.4/HP). The model's `V` = *"what do I lose if this dies"* — which is **correct
for the chump decision**.

The gap is in the **prime-defender (keep-alive) choice**: the unit you keep should be valued on **what
it gains in perpetuity if it remains** — a reusable Wall re-blocks free forever, a spent-economy
Engineer does not. The current loss-of-0-when-survives doesn't credit that perpetual gain, so the model
has no reason to *prefer keeping the Wall*. The fix is a prime-defender valuation that weighs perpetuity
gain, NOT a raw Wall/Engineer constant bump.

**This is a heuristic design change, to be specced separately with the value-model owner. The
implementing session should NOT touch the prime-defender / value-model logic for it** — only the four
bugs above. The corrected eval (post-①②③④) is the baseline that design change will be measured against.
