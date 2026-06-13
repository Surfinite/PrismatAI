# RL Loop Design Audit — Third Audit (2026-06-12)

> **What this is.** The third full audit of the RL self-play loop, with a different mandate than the
> first two: *question WHY at every step, not just whether code matches docs* — flag any part whose
> underlying reason-for-existence is unsound even if implemented consistently, judged against good
> practice for a value-only MCTS self-play loop. Method: 8 parallel dimension auditors (self-play
> generation / training / eval-statistics / driver-ops / data-pipeline / first-principles design /
> docs coverage / empirical test run), each Medium+ finding then adversarially verified by independent
> agents (evidence-accuracy lens; + fairness-given-constraints lens for High/Critical). 62 agents total.
> A session limit killed 5 verifications + the completeness critic near the end; the 3 affected findings
> were re-verified by hand in the main session (noted inline). Severities below are POST-verification.
> Read-only: nothing was changed except this report and the new `eval/campaign_log.md`.

## 0. Bottom line

**Mechanically, the loop is run-ready and in the best shape it has ever been.** Empirical sweep: 216/216
tests pass, all 10 preflight checks PASS against the live config, the parent `.pt`/bin are bit-identical
across repos, the MasterBot baseline sha matches, both engine exes are current, zero tracked-file drift
in either repo. The prior audits' fixes are real; the engine-side self-play mechanics (labels, draws,
seat balance, dedup, stamps, `ig_feasible_max`) all independently check out.

**Structurally, the campaign as frozen cannot answer its own question.** Chaining the frozen numbers —
which no document ever does — the loop **generates** an effect of plausibly ≪1pp per iteration,
**carries** the IG-axis signal in single-digit explored counterfactuals per iteration, and **measures**
at ±8.7pp resolution with a verdict that only fires at ~−10pp. Three independent resolution mismatches
compound into one outcome: every iteration reads "REVIEW, flat", the 3-flat-iteration kill criteria
fire **by arithmetic, regardless of whether RL works**, and the campaign escalates having learned
nothing the numbers didn't already say. The per-stage machinery was audited three times; the
*composition* was never audited until now. This is fixable before `-K 1` with cadence and budget
re-allocation changes, not code rewrites (§2).

A second theme: **several load-bearing design parameters exist by inheritance, not decision** — fixed
self-play seeds that freeze the entire card-set universe of the campaign, SWA inherited from the
supervised pipeline, a 30% rehearsal tax defending against an empirically-absent risk, an eval budget
spending 70%+ of its games on anchors that gate nothing. Each was individually reasonable once;
none has a recorded rationale for the role it now plays.

---

## 1. The structural problem: three resolution mismatches that compound

These five findings are one story. Each is independently verified; together they say the frozen loop is
a null-iteration generator *by construction*, not by bug.

### 1.1 [HIGH] rl-design-01 / training-01 / selfplay-05 — the loop generates ~2 orders of magnitude less effect than its eval can resolve

The frozen chain: 128 games/iter → ~4,500 records (rescreen: 35 records/game) → `num_samples =
ceil(sp/(1−frac))` ≈ 6,400 draws/epoch → **~78 optimizer steps at peak lr 1e-5** (SWA phase 5e-6),
fine-tuning a parent trained 100 epochs @ 3e-4 on ~8.3M examples — ~4 orders of magnitude less
optimization pressure than built the parent.

**Measured, twice independently** (auditor simulation + verifier re-execution from the real v221
parent, matching to 2 significant figures): the exact post-N-1 stage-3 schedule on a 4.7k-record
self-play stand-in with *zero* rehearsal damping moves predicted win-probabilities by **mean |ΔP| ≈
0.003–0.004** and flips the predicted winner on **~0.5–0.7% of states**; held-out human-val accuracy
unchanged to 2 decimals (73.78% → 73.78%). The eval then asks a 128-game anchor — CI half-width
**±8.66pp**, REJECT threshold ≤52/128 wins, P(REJECT|parity)=2.1%, P(REJECT|−5pp)=18.3%,
P(REJECT|−10pp)=59.5% (all recomputed and confirmed) — whether anything changed.

The N-1 fix removed the *accidental* null-iteration generator (LR floor); this is the *designed* one
surviving it. Every knob is individually documented and defensible; **no document connects training
step size to eval detectability**, and the missing effect-size budget is the gap. The kill criteria
("≥3 consecutive flat iterations") are therefore guaranteed to fire on schedule, and triage item 4
("did training change predictions?") will technically pass (ΔP≈0.003 ≠ 0) while being decision-useless.

*Verification note:* fairness lens downgraded the original Critical → High on two grounds: the spec's
own interpretation guard ("flat local = uninformative") shows partial awareness, and the fix is cheap.

### 1.2 [HIGH] selfplay-01 / rl-design-02 — the campaign's named axis receives almost zero exploration signal

From the campaign's own committed rescreen artifact (`eval/n1000_rescreen_k12.json`): forced-Hotel
games contain **~1.7 IG-feasible decision points per game** (55/1121 records with `ig_feasible_max>0`)
and ~0.8 actual clicks/game; the τ=0.7 exploration window (turns 0–11) reaches **zero** IG-feasible
decisions (min IG-feasible turn in the rescreen: 12 — Hotel costs 5B and needs House tech, so IG
decisions live entirely past the window); late exploration is 0.69 uniform deviations/game *across all
decisions*. The verifier measured exactly **one** ε-deviation landing on an IG-feasible root in the
entire 32-game rescreen. Scaled to an iteration: **single-digit explored IG counterfactuals per
iteration** — the labels barely contain the signal the campaign exists to detect.

§1b/A2's accepted-risk paragraph honestly names counterfactual blindness but never quantifies it on
the campaign's own axis; quantified, "A2 RESOLVED (regime v2)" is too generous. A flat d_rl would be
evidence of *nothing* — the prior expectation under both "RL works" and "RL doesn't" is flat.

### 1.3 [HIGH] selfplay-02 — at N=1000/c=0.3 the self-play policy cannot express the preferences the campaign trains for

*(Verification agents lost to the session limit; re-verified by hand in the main session — the
indifference-band number independently matches the Jun-11 verification sweep's own "~9pp" recomputation,
and the tie-break code citations were confirmed directly.)*

UCB1 visits root children near-equally whenever their backed-up values are within
`c·sqrt(ln N / n_child)` of the best: at N=1000, c=0.3, 8–24 children that band is **0.071–0.123
win-prob** (vs 0.0125 at the 100k eval budget). The owner's own tau probe confirms it: 9/41 states show
*exact round-robin* visits (e.g. [84×12 ±1]); ±1-visit equilibrium implies the net+tree distinguished
those children by <0.001 win-prob, so "most-visited" there is noise. Consequences:

- The "late-precision" half of regime v2 is weaker than documented: late-game argmax among portfolio
  candidates within ~9pp of each other is not "precision", it's arbitrary selection in the band.
- **Tie-break bias toward over-clicking, verified in code**: root children are sorted longest-move-first
  (`MoveIterator_AbilitySubset.cpp:53`, comment explicit) and both argmax paths break ties
  first-index-wins (`UCTSearch.cpp:121` `v > maxVisits`; `MoveSampler.cpp:15`). In the indifference
  band, ties resolve toward **more IG clicks** — the exact over-click behaviour the campaign exists to
  fix is being *systematically regenerated into the training data* at indifferent roots.
- The frozen-tuple rationale "argmax now governs most moves, so N's argmax quality matters MORE" is
  contradicted by the probe: at this (N, c), argmax quality at near-tied roots is undefined.
- The IG over-click cost is plausibly a few pp — *inside* the self-play indifference band but
  resolvable at the eval budget: the generator literally cannot see the distinction it is generating
  training data about.

Cheap probe before iter-1: rerun the 41-state probe at c=0.15 or N=4000 and compare top-share medians.
Also: randomize (seed) the argmax tie-break.

### 1.4 [HIGH] verdict-01 / anchors-02 / rl-design-03/04/05 — the decision layer has no coherent operating point

- **verdict-01 (High, both lenses confirmed):** the REJECT/REVIEW redesign correctly killed the
  incoherent GO gate but replaced it with nothing decision-capable: the automated verdict is a −10pp
  tripwire, and every real decision is a human reading 5 uncorrected noise cells (iter0
  forced/general, narrow forced/general, steam) per iteration — P(≥1 of 4 parity cells reading ≥+5pp)
  ≈ 41% per iteration. Iterated without pre-registration or evidence accumulation, this is a
  garden-of-forking-paths machine: over several iterations the human will, with high probability,
  either promote noise or stall indefinitely.
- **anchors-02 (High):** the eval budget is inverted — of ~712 games/iteration (512 C++ + 200 steam),
  only 128 feed the verdict and marginal-progress judgment. The narrow anchor (256 games/iter) answers
  a question ("what does the IG-widened iterator itself buy?") that needs measuring ~once per
  campaign, not per iteration. Reallocating narrow+steam games into iter0/general would take the
  decision CI from ±8.5pp toward ±4–5pp **for free**.
- **rl-design-03 (High, both lenses confirmed):** nothing states when the human should promote — and
  the N-3 fix (correctly) pins the generator to the frozen parent until promotion, so **without
  promotions the generator never changes and consecutive iterations are near-replicates of the same
  one-step offline-RL experiment, not compounding RL**. Promotion requires positive evidence the n=128
  eval cannot supply; the kill criteria fire on power grounds alone; the A9 stop rule ("O6 also flat →
  stop") contradicts the spec's own interpretation guard ("flat local = uninformative") since O6 at
  this eval power will also read flat regardless of merit. The two coherent regimes at this scale:
  (a) AlphaZero-style **promote-unless-harm** (promote every candidate unless REJECT / tripwire /
  reproduced tactical regression — this is what a detect-harm verdict is *for*; iterations compound;
  judge the lineage every 3–5 iterations with ONE powered eval at n≥600–786 vs the fixed origin), or
  (b) declare the local phase an offline pipeline-shakeout that never promotes — and say so.
- **rl-design-04 (Medium):** per-iteration compute is ~30–50× weighted toward the under-powered eval
  over generation (eval: 712 games at 7s/100k ≈ 5–8k traversals/move; generation: 128 games at
  N=1000). On a cost-conscious box, the wall-clock re-allocation *is* the campaign's real budget lever.
- **rl-design-05 (Medium):** the one free power upgrade — paired per-card-set analysis — was deleted as
  dead code on the rationale "no per-set scores exist in the C++ output". The rationale no longer
  holds: dave `6e93480` demonstrably added per-seat statsTable columns, so per-round/per-set emission
  is the same scale of change, and the fixed-panel + colour-swap design already pays the price that
  pairing would redeem.

### 1.5 What §1 adds up to

Do not run `-K 1` to "see what happens" — the frozen numbers already say what will happen. Before
iter-1, in order of leverage:

1. **Pre-register the promotion policy** (recommend: promote-unless-harm + periodic powered
   lineage-vs-origin eval) and write the effect-size budget into `rl_campaign.md` §1. (docs + decision)
2. **Re-allocate the eval budget**: narrow → once-per-promotion; steam → ~100 games or
   checkpoint-only; freed games → iter0/general (n≥384). (config + `ANCHOR_BLOCKS` + frozen file)
3. **Raise the dose**: scale self-play rounds (prereq-7's sanctioned path) and/or drop SWA + cut
   rehearsal to 0–0.10 (§3 below) so stage-3 movement is measurable by the cheap probes; add the
   missing **prediction-movement instrument** (mean |V_cand − V_parent| on a fixed probe batch) so a
   null update is detected for pennies at stage 4.5 time, not after a 10-hour eval.
4. **Targeted IG exploration**: ε applied specifically at roots whose children differ in IG count
   (adds axis-relevant counterfactuals with near-zero label-corruption cost), or seed a forced-slice
   from curated IG-on-board states (`eval/ig_battery` exists). Add the per-iteration watch-stat:
   count of realized IG-click-count *contrasts* on matched (colour-swap) pairs.
5. **Probe (N, c)** once (41 states at c=0.15 / N=4000) and seed the argmax tie-break.

---

## 2. The frozen-seed universe (three auditors converged independently)

### [HIGH] selfplay-03 / design-seed-02 — self-play card sets are frozen for the life of the campaign

`RL_SelfPlay_General` has `Seed:56`, `RL_Step2_Smoke` `Seed:55`, permanently in config; at Threads>1
the per-block seed fixes the card-set sequence (the project's own §1d mechanics); the driver never
varies a seed per iteration (zero `seed` references in `run_iteration.ps1`) and preflight checks no
Seed key. Therefore **every iteration regenerates self-play on the identical 43 general + 21 forced
card sets; the campaign's entire training-data universe is ≤64 distinct sets, forever.** Successive
un-promoted iterations (same parent, same sets, argmax past turn 12) produce near-duplicate data —
the W=5 replay window accumulates *outcome-resamples, not coverage*. This is undocumented anywhere,
contrary to self-play good practice (fresh position coverage per generation is the cheapest thing
self-play buys), and appears to be an accident of smoke-block inheritance rather than a decision.
Both verifier lenses confirmed at High: there is NO recorded acceptance or rationale.

**Fix (pick deliberately):** derive self-play seeds from K (e.g. `5500+K`/`5600+K`, stamped into
replay meta + manifest) — keeps per-iteration reproducibility while restoring coverage growth; or
document fixed-sets as a chosen variance-reduction design with its cost accepted. Add `Seed` and
`RandomCards` to `campaign_frozen.json`/preflight either way.

### [MEDIUM] seed-04 — eval is likewise a fixed 64-set panel

All four anchor blocks share `Seed:2026`: the verdict is measured on the same 64-set panel every
iteration of the campaign. Benefits (cross-iteration comparability; accidental-but-real disjointness
from the self-play sets) and costs (CIs don't cover set-panel generalization; 5–10 iterations of
human judgment can overfit the panel; IG-interaction sets are frozen in) are nowhere weighed. Document
the tradeoff; cheaply de-risk (e.g. 2×rounds:32 at Seed:2026/2027).

---

## 3. Training-stage design (beyond §1.1)

- **[MEDIUM] training-02 — SWA buys nothing here and dilutes the update ~20%** (measured: SWA/final
  movement ratio 0.81, identical probe accuracy). SWA's premise — averaging diverse minima over a long
  flat-LR phase — does not transfer to a 78-step fine-tune averaging 4 near-collinear snapshots; the
  deployed artifact (`swa_model.pt`) is a blend in which half the averaged mass predates most of the
  (already minimal) learning. Inherited from the supervised pipeline without an RL-context rationale.
  Drop SWA for RL iterations (deploy final-epoch weights), folded into the same pre-iter-1 re-freeze.
- **[MEDIUM] training-03 — rehearsal at 0.30 defends an empirically-absent risk while taxing the RL
  gradient 30%.** *(Verifier lost to session limit; the supporting simulation is the same one
  independently reproduced for training-01.)* At 78 steps/lr 1e-5, catastrophic forgetting is nil
  (zero-rehearsal fine-tune left human-val acc unchanged); the schedule's own docstring admits it is a
  "Confidence schedule, NOT an accumulation argument". The mechanism (mixing math, colour balance,
  epoch sizing) is implemented exactly right. Start rehearsal at 0–0.10 and raise only if the stage-4.5
  tripwire (which already measures the relevant drift every iteration) crosses a pre-registered
  threshold.
- **[MEDIUM] training-04 — stage 3 loads ~23GB of tensors on the 32GB box to consume ~12k rehearsal
  draws** (full `human_1800_v2.h5` = 18.2GB in-RAM + val 4.6GB; 99.3% never touched), and the post-fix
  full-size path has **never been dry-run**. Do a stage-3-only dry run before iter-1; subsample the
  rehearsal source (~100–200k pre-built H5); cap the tripwire val set (~50k gives ±0.4pp vs a 3pp
  threshold); cache the parent's val-acc at promotion time instead of recomputing per iteration.
- **[LOW] training-06 — training seed unpinned**: each candidate is irreproducible, inconsistent with
  the campaign's sha256-everything lineage rigor elsewhere.
- **[INFO] training-07 — the stage-4.5 tripwire is sound** for its stated purpose (E1-class canary).
  Note it is a *don't-regress-on-human-val* guard, not a forgetting instrument; see training-03 for
  making it earn double duty.

---

## 4. Lineage, promotion, and ops seams

- **[HIGH] ops-promote-01 — promotion is non-atomic across 2 repos and the parent is pinned by NAME
  only.** A consistent-but-wrong promotion (all four players repointed to the wrong bin + frozen file
  updated to match) passes preflight; `parent_pt`/`parent_bin` can silently diverge by a generation
  (nothing asserts the export relationship); a same-K re-run **unconditionally overwrites
  `neural_weights_rl_iter<K>.bin`** (stage 4) — clobbering a just-promoted parent's bin while every
  name-based check stays green. Fix: `eval/promote_candidate.ps1` that asserts
  sha256(re-export of new `parent_pt`) == sha256(new `parent_bin`), writes `parent_bin_sha256` into
  `campaign_frozen.json`, adds the matching preflight content check (also catches the clobber), edits
  the four pins, runs preflight, prints the two per-repo commit commands. Plus: driver throws at
  startup if `$candBin` == frozen `parent_bin`.
- **[HIGH, split verdict] drl-03 — after the first promotion, the documented cumulative IG-axis
  measurement silently disappears.** `rl_campaign.md` prereq-2 says d_rl from iter-2 measures
  *cumulative gain vs fixed v221* — but d_rl's opponent (`RL_Eval_iter0`) is parent-repinned at every
  promotion by preflight check 7 + the runbook procedure, so d_rl is actually *marginal vs current
  parent*. The kill criteria, the §1b watch items, and the AWS judgment all consume d_rl assuming the
  documented semantics. (Evidence lens: Medium — doc contradiction, no harm until first promotion;
  fairness lens: High — it is THE campaign question.) Fix: add a permanently-v221-pinned
  `RL_Eval_origin` player + one forced-pool block (each iteration or each promotion), rename
  `RL_Eval_iter0` → conceptually "parent", fix the caveat text.
- **[MEDIUM] training-05 / ops-quarantine-04 — window membership is filename + human memory, and the
  quarantine guidance is conceptually wrong.** A REJECTED candidate's H5 was generated by the PARENT
  (RL_SelfPlay is parent-pinned), so candidate rejection does NOT taint the data — followed literally,
  the runbook's "quarantine the failed candidate's artifacts" makes the W=5 window permanently
  vestigial (it would only grow across consecutive promotions); read loosely, nothing detects a
  forgotten quarantine of genuinely-invalid generation runs (the Jun-8 crippled-window incident is the
  precedent). Fix both halves: correct the runbook (keep non-promoted iterations' data; quarantine
  only invalid GENERATION runs), and stamp H5s at vectorize time (parent sha, tuple hash) with a
  stage-3 pre-check refusing mismatched stamps.
- **[MEDIUM] ops-resume-03 — no stage resumability, no campaign ledger.** Any failure at stages 2–8
  forces a full multi-hour self-play re-run that also orphans the prior attempt's good data; K is
  unvalidated free input; no driver transcript is kept. Add `-ResumeFrom <stage>` (stages 2+ need only
  the already-archived artifacts), an append-only `eval/campaign_log` entry per run, K validation, and
  tee the driver output.
- **[MEDIUM] preflight-gaps-06 / docs-02 — the "frozen campaign identity" is only half
  machine-enforced.** Unchecked: eval budget (7000/100k) + UCTConstant on the three eval players, the
  anchor blocks' rounds/Seed/Threads, W (a freely-passable `-Window` param), the training schedule,
  and data-file *content* (existence only). The manifest **hardcodes** the eval-budget string rather
  than reading config. Extend `campaign_frozen.json` + preflight, or amend the "single source of
  truth" sentence to state which knobs are convention-only.
- **[MEDIUM] ops-toctou-07 — contamination checks are point-in-time.** Preflight check 9's docstring
  claims it protects stages 6/8, but it runs at stage 0, hours earlier; `tactical_suite.py` and
  `action_coverage.py` contain no sentinel/env assert (only run_eval re-asserts at stage 7); nothing
  prevents a concurrent calibrate/matchup run mutating the same live config mid-iteration. Two-line
  asserts in both tools + a driver lockfile.
- **[MEDIUM] prov-06 — engine load confirmation is FILE-level, not PLAYER-level.** The engine's
  "created per-player NeuralNet from <path>" line omits the player name (it's in scope at the FATAL
  one line down), and many players share the parent bin — so `engine_confirmed_parent_load`
  structurally cannot catch the exact stale-`RL_Eval_iter0` scenario N-2 documents. One-line engine
  change (add player name to the line) + match (player, basename) pairs; or have run_eval re-read the
  config and assert the parent pins before flipping blocks.

---

## 5. Gate semantics — thin regression armor

The gates all *run*; what several of them *prove* is narrower than documented.

- **[MEDIUM, downgraded from High] a6-seam-01 — the maxPlayer negation seam remains the one sign flip
  every automated gate is blind to.** `NeuralNet.cpp:692-694` (`if (maxPlayer != Player_One) value =
  -value;`) + `UCTSearch.cpp:379-389` (`(nnValue+1)/2`) are pinned by NO test; the stage-5 oracle
  always evaluates from `Player_One` so the negation branch never executes during the gate; and the §4
  false-negative triage (the sanctioned route to ABANDONING the campaign per A9) contains no
  orientation-capable item. Live aggravator found: the comment at `UCTSearch.cpp:374` is WRONG at the
  exact seam ("returns value from active player's perspective" — it's maxPlayer's). Currently
  empirically correct (v221 scores 46–55% vs strong anchors — a flip would score ~0), hence Medium not
  High; but engine commits land continuously and the missing end-to-end orientation test is ~2 hours
  on existing machinery (two near-decided states, both seats, assert the winning continuation via
  `query_move.js`). Build it before iter-1; fix the comment; add it as a triage item.
- **[MEDIUM] parity-gate-01 — stage 5 verifies less than documented.** The PyTorch reference consumes
  the C++-extracted features (`compare_parity_deepsets.py:79-98`), so C++ feature-extraction bugs feed
  both sides identically and PASS — the gate pins weights-export + forward arithmetic only, while
  `rl_runbook.md:83` claims it "catches export/feature bugs". Tolerance 1e-3 is 1000× the measured
  floor (5.84e-07 / 1.09e-06); the sorted-prefix sample will be ~100% forced-slice. Tighten to 1e-4,
  stratify the sample, correct the docs (feature extraction is pinned by the three-way gate, not
  stage 5).
- **[MEDIUM] tactical-gate-01 — stage 6 aborts a whole iteration on single nondeterministic 3-second
  samples.** The gate's own history shows 18%/33% false-fail rates on the dropped sibling cases and an
  11/3 knife-edge on ktink; the 4 armed cases were stability-screened only under the PARENT at one
  load condition; a fine candidate can move any armed case onto its own knife-edge. As built, the
  abort treats one noisy 3s sample as stronger evidence than the 128-game eval it preempts. Re-run
  mismatches 3–5× and gate on majority (≤60s), and/or run at the deployment budget and re-baseline
  once; or demote to telemetry feeding the human REVIEW.
- **[MEDIUM] threeway-cov-01 — the three-way feature gate's fixture never exercises `is_frozen`,
  `lifespan_remaining`, or damaged-HP units, and contains zero IG/self-play states** (measured
  directly from the gate's own dump: 162 instances, those features nonzero zero times; no Infusion
  Grid in the card set). The features most relevant to the IG campaign (Husk boards, chill/freeze,
  damaged blockers) are exactly the blind spots. Add 3–5 fixture states incl. one forced-Hotel
  archived sidecar (native `sp_*.json.gz` → `--dump-v2-record`/`--dump-features`, no lossy
  round-trip); document the non-covered features in the gate's docstring.
- **[LOW, downgraded from Medium] impl-unitindex-05 — the unit_index.json silent-lobotomy is unguarded
  on the campaign path** (config players ignore `buildCardTypeMapping()`'s return; the X5b guard
  checks only `isLoaded`; preflight never checks the file; stage-1 stderr is not captured). Low
  trigger probability today (git-tracked, untouched by the loop) but the blast radius is the known
  5-day-handicapped-engine class. Preflight check 11 (exists + parses + 116 units) + make
  `mappedTypes==0` FATAL for NeuralNet-eval players.
- **[MEDIUM] steam-07 — the 16-game cross-path "bound" is statistically vacuous** (±24pp CI at n=16
  bounds nothing) and the steam rate's draw/n conventions silently differ from the C++ anchors
  (draws-count-against-both vs draw=half-win). Fine as a trend yardstick; reword the README, parse
  validGames/draws, align or annotate the convention.

---

## 6. Self-play data quality (beyond §1.2–1.3)

- **[LOW, downgraded from Medium] selfplay-04 — regime-v2's label-truthfulness rationale overclaims.**
  A record's label depends on ALL deviations after it, by either player — early-window records (the
  ones §1b says get "coverage with truthful labels") average ~1–2 future τ-deviations in their own
  continuations. v2 is correctly understood as a ~10× total-deviation reduction vs v1, not an
  early/late asymmetry. Matters mainly when Lever 0 (raising late-ε) is considered: the recorded
  causal story would mis-guide that re-tune. Fix is a paragraph edit + prefer targeted IG-sibling
  exploration over raising global ε.
- **[MEDIUM] selfplay-06 — campaign identity is self-contradictory on data volume**: §1 declares ANY
  frozen-tuple change a NEW campaign while prereq-7 sanctions scaling the frozen `selfplay_mix` rounds
  as routine. Pick one (recommend: declare volume knobs a separate "scale" tier requiring only an
  iter-0 re-anchor + manifest note) and encode it in `campaign_frozen.json`.
- **[INFO] selfplay-07 — positive confirmation:** labels (1.0/0.5/0.0, draws + 200-turn cap), exact
  seat balance by construction, Move-level dedup, 1:1 move stamps, decision-time `ig_feasible_max`
  (0 violations measured), discarded games dropped without partial labels, Threads:8 acceptance — all
  independently verified sound.

---

## 7. Statistics fine print

- **[MEDIUM] stats-05 — iid Wilson on colour-swap-paired games is mis-calibrated fine print.** The 128
  "trials" are 64 clusters of 2 (shared card set per round); positive within-pair correlation (a set
  favouring one NET — plausible exactly on IG-relevant sets) shrinks effective n (ρ=0.2 → n_eff≈107,
  true half-width ~9.3pp vs reported 8.5pp) and drifts REJECT's stated 2.1% type-I upward; draw=half-win
  additionally makes the statistic non-binomial. The "no per-set scores exist" acceptance treats
  owner-controlled C++ output as immovable (see rl-design-05 — same ~20-line fix unlocks the paired CI
  that *helps* power). Until then, annotate manifests that the CI is iid-conditional-on-pairing.
- **[LOW] edge-08** — a 0-game completed anchor yields REVIEW (not INCOMPLETE); "REJECT reliably fires
  for ~−10pp" is generous (59.5% at exactly −10pp).

---

## 8. Documentation

- **[MEDIUM, downgraded from High] docs-01 — re-deriving stage 3 from the maintained docs reproduces
  the N-1 bug.** `--swa-lr 5e-6` appears in NONE of the three maintained docs (the tuple table and
  knobs list state "6 @ 1e-5, SWA from 3"); train.py's default is lr×0.1 = 1e-6 = the floor — anyone
  reconstructing the stage-3 command from the docs silently re-creates the null-SWA-phase bug. Same
  pattern: tactical case provenance (armed/dropped-flaky/knife-edge) lives only in the historical
  verification doc. Add the swa-lr row + a 3-line case-provenance note.
- **[MEDIUM] docs-02** — see preflight-gaps-06 (§4): "single source of truth" overstates; half the
  declared identity knobs are enforced by nothing.
- **[MEDIUM] docs-03 — stale claims that survived the fix sweep**, incl. one the resolution table
  falsely certifies FIXED: `rl_campaign.md` §4.7 still says "≈600 games/anchor" (the audits corrected
  this to ~786 @ 80% power; the cited fix commits demonstrably did not land this edit; '786' appears
  nowhere in eval/) — this is the stated sizing bar for the £400+ AWS decision. Also: the runbook's
  preflight table lists 9 of the 10 checks (missing `selfplay_replays`), and stage-8 coverage silently
  reads the FORCED dir only while presenting under global-sounding manifest keys (also
  coverage-prov-01: it describes the PARENT's behaviour, not the candidate's).
- **[MEDIUM] docs-04 — the spec is half-superseded with no per-section status marking**, yet
  `rl_campaign.md`'s O3 escalation gates on "O2's deep-label diagnostic (§8.5)" — a dangling
  cross-reference that silently resolves into the spec, where deleted designs (GO rule, sequential
  testing, ε≈0.25, K≈6–8) sit unmarked next to still-authoritative content (§8.5 diagnostics, the
  axes-2–4 curriculum). A future session executing the escalation path months from now cannot tell
  which is which. Add a status banner + per-section table, or fold §8.5 + the curriculum into
  `rl_campaign.md` and demote the spec to pure history.
- **[MEDIUM] docs-05 — the genuinely missing doc class: a campaign logbook / decision ledger.**
  `rl_campaign.md` §5 itself mandates "maintain a changelog mapping every win-rate point to exactly
  one (config-hash, net-hash) delta" — no such file, template, or location exists. The machine record
  exists (manifests, dashboard, run_metadata); there is no home for the per-iteration HUMAN record
  (decision + reasoning + watch-stats) on which this campaign's entire epistemics rest, and the
  de-facto accepted-limitations ledger lives in a doc labelled "historical record".
  **→ Created as part of this audit: `eval/campaign_log.md`** (per-iteration entry template + living
  accepted-limitations ledger seeded from the resolution table). Secondary gap (docs-06, Low): a
  failure-mode/mid-run recovery table — the recovery machinery is built and good, but the procedures
  live only in ps1 comments; recommend folding a short table into `rl_runbook.md` rather than a new doc.
- **[INFO] docs-07 — doc architecture verdict:** the contract/ops/harness division is principled and
  currently coherent; the tuple + verdict are quadruplicated (drift risk); no stated reading order for
  a new maintainer (campaign_log.md now states one).

---

## 9. Empirical sweep (test-runner, 2026-06-12)

ALL GREEN: 216/216 tests pass (116 training + 100 eval, 28.4s); standalone preflight 10/10 PASS
against the live config; parent .pt present, parent bin **bit-identical in both repos** (sha
22CC647E…C57E97); both H5s present; masterbot2016 exe sha **exactly matches** the documented value;
both engine exes present and build-fresh (the apparent staleness of Prismata_Standalone.exe vs HEAD
was verified a non-issue — the newer sources are not compiled into it); tactical_baseline.json matches
the documented 4-armed/ktink-unarmed state; calib_states=41 (matches doc), ig_battery=39; **zero
tracked-file modifications in either repo**, both branches in sync with PrismatAlpha remotes.
Minor: (env-01, Low) no build-freshness guard exists — exe↔source consistency rests on manual mtime
convention; (env-02, Info) the documented "214/0" test count is stale — measured 216/0.

## 10. Verification record

39 Medium+ findings were adversarially verified (evidence-accuracy lens for all; + fairness lens for
High/Critical): 0 refuted outright; severity changes: rl-design-01 Critical→High, a6-seam-01
High→Medium, docs-01 High→Medium, impl-unitindex-05 Medium→Low, selfplay-04 Medium→Low; drl-03 carries
a split verdict (evidence Medium / fairness High). Five verification calls + the completeness critic
were lost to a session limit; the affected findings (selfplay-02, selfplay-05, training-03) were
re-verified in the main session — selfplay-02's code citations and indifference-band math confirmed
directly (and corroborated by the Jun-11 sweep's independent "~9pp" recomputation); selfplay-05 and
training-03 rest on the same simulation independently reproduced for training-01. The completeness
critic did not run; cross-cutting coverage (seams between stages, AWS-scale behaviour, dashboard/
render pipeline internals, replay-archive integrity) is therefore the least-swept territory of this
audit.

## 11. Suggested ordering (recommendations only — nothing here was changed)

**Before `-K 1` (decisions + small code):**
1. §1.5 items 1–3: pre-register the promotion policy; re-allocate eval games to the decision anchor;
   raise the training dose (more rounds, drop SWA, rehearsal 0–0.10) + add the prediction-movement
   probe. These three convert the loop from a null-iteration generator into an experiment.
2. selfplay-03/design-seed-02: per-iteration self-play seeds (or document fixed-sets deliberately).
3. ops-promote-01: `promote_candidate.ps1` + sha-pinned parent + same-K clobber guard.
4. a6-seam-01: the 2-hour end-to-end orientation test; fix the wrong comment.
5. training-04: stage-3-only dry run at full size.
6. docs-03's ≈600→786 correction (it sizes the AWS decision).

**Before iter-2:** drl-03 (origin anchor), quarantine-guidance rewrite + H5 stamps, tactical-gate
majority re-runs, preflight extension (frozen eval budget/W/seeds/shas), TOCTOU asserts + lockfile,
per-set paired CI emission.

**Whenever:** remaining docs items, fixture states for the three-way gate, steam conventions,
training seed, `-ResumeFrom`.
