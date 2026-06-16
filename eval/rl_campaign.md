# RL Self-Play Loop — Frozen Config + Decision Rules (regime v4, proof-of-life)

> **Design spec:** `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`
> (the WHY of the reframe + the v4 policy/anchors/two-phase run). **Source audit:**
> `docs/superpowers/plans/2026-06-13-rl-loop-deep-audit-FINDINGS.md`.
> **Machine source:** `eval/campaign_frozen.json` (tuple_version 4, two-tier — §1 below).
> **Operator reference:** `eval/rl_runbook.md`. **Eval harness internals:** `eval/README.md`.
> **Iteration ledger + limitations register:** `eval/campaign_log.md`.
> **Status:** **REGIME v4 — frozen 2026-06-14; Phase 0 validated 2026-06-16 (iteration K=1).**

## What this is — the SYSTEMS milestone (proof-of-life)

This is the campaign contract. The loop has been **reframed from a scientific IG-axis
measurement campaign ("does RL learn the Infusion-Grid decision?") to a SYSTEMS MILESTONE:**
*the data → train → export → eval loop runs end-to-end, unattended, and produces a genuine
non-degenerate net.* **There is no axis under test.** The deliverable is a working, trustworthy
machine plus measured throughput — **not** a win-rate claim on any axis.

This reframe is defensible because the audit (finding **C1**) showed the IG over-click was
**already fixed by the action-space widening** (the IG-subset root iterator makes even the
untrained v221 pick the correct count), **not** by RL. So we **log the IG over-click as a
completed action-space fix**, keep the IG-subset in the candidate, and remove all IG-*measurement*
machinery. The IG axis survives only as a reusable worked example — see the **Appendix** at the
bottom. The campaign is now a general DSNN-improvement / fix-MasterBot-mistakes framework; IG is
proof-of-life, not the thing under test.

**Discipline that keeps it honest:** report results as "the loop works / the net is
non-degenerate," **never** as "RL improved the net." The moment the latter is claimed, the dropped
measurement findings (H1/H5/M7/M8…) come back and the measurement-grade rigor of the old regime is
required again.

**Any change to the frozen HP tuple below = a NEW campaign** (re-anchor and re-baseline). The
machine-readable tuple is **`eval/campaign_frozen.json`** — stage 0 of `eval/run_iteration.ps1`
(`eval/preflight_config.py`) **hard-fails if the dave `config.txt` drifts from it** and never
silently rewrites either side. The driver that wires the one-iteration loop is
`eval/run_iteration.ps1`; promotion is `eval/promote_candidate.ps1`; the powered measurement is
`eval/run_checkpoint.ps1`; the per-iteration dashboard is `eval/render_dashboard.py`.

---

## 1. Frozen HP tuple

Treat the whole tuple as the campaign identity. **FROZEN 2026-06-14** (owner decision, the
proof-of-life reframe). Machine source: `eval/campaign_frozen.json` (mirror these values exactly);
enforced against `config.txt` by `eval/preflight_config.py` (stage 0).

| HP | Symbol / key | Value | Notes |
|---|---|---|---|
| Self-play traversals | `N` (MaxTraversals) | **1000** | the per-move search budget the generator plays at. Lives on `RL_SelfPlay`. DECOUPLED from the eval budget (A1). |
| Temperature | `τ` (TemperatureTau) | **0.7** | self-play sampler only; eval is pure argmax. Sharpens the near-uniform root visit distributions at N=1000/c=0.3. |
| Temperature horizon | `K` (TemperatureK) | **12** | τ-sampling fires for turns **0–11 only** — past the opening book and through the early-mid region where the MB-flavour data bias lives. |
| ε-uniform root noise | `EpsilonUniform` | **0** | τ carries the opening-window exploration. |
| ε-late root noise | **`EpsilonLate`** | **0.05** | **v4: general, controllable late exploration** at turns ≥ K. A small, bounded label-cost knob — restored from the v3 retirement (v3 had replaced it with the IG-targeted `EpsilonIG`; v4 inverts that — see the table in "What v4 changed vs v3" below). |
| ε-IG targeted noise | **`EpsilonIG`** | **0 (OFF)** | **v4: IG-specific exploration removed** — there is no axis under test. (v3 ran it at 0.25.) |
| UCT constant | `c` (UCTConstant) | **0.3** | the tuned cValue, on every RL player AND injected by `js_engine/query_move.js` by default (omitting it silently regressed to the engine default 2.0, the worst measured c). |
| Self-play threads | `selfplay_threads` | **8** | the single self-play block runs Threads:8; the dave engine is x64 and Threads:8 export was audit-verified clean. |
| Self-play block | `selfplay_block` | **`RL_SelfPlay_General`** | **v4: ONE general block** (no forced-Hotel mix — IG is no longer the axis). NO `ForcedCards`. The forced block `RL_Step2_Smoke` is RETAINED in config but UNUSED (never referenced by the v4 driver/frozen tuple). |
| Self-play rounds | `selfplay_rounds` | **516** | = **1032 games/iter** (one round = a colour-swapped pair). Preserves the v3 training dose (344+172 → 516) now that the forced block is dropped. |
| Self-play seed base | `selfplay_seed_base` | **5600, + K at run time** | fresh card sets every iteration (coverage growth), reproducible per iteration; the driver sets `base+K` transiently and restores the base (preflight asserts the at-rest base). |
| Replay window | `W` (replay_window) | **2** | sliding self-play buffer. **v4 shrank it 5 → 2**: with a moving generator (Phase 1), the buffer should track the CURRENT net (off-policy hazard H4). |
| Rehearsal | — | **flat 0.10, ELITE corpus** | `human_elite_2000_45s_v2.h5` (both ratings ≥2000, 45s+ controls). Working knob, harmless tax (audit). `rehearsal_start = rehearsal_floor = 0.10`, `rehearsal_decay = 0.0`. |
| Training schedule | `train_schedule` | **6 epochs @ lr 1e-5, NO SWA, seeded** | the candidate is `final_model.pt` (last-epoch weights — SWA averaged near-collinear snapshots for no gain). Seed 2026000+K (reproducible candidates); `num_workers 0`. |
| Promotion policy | `promotion_policy` | **promote-unless-collapse** (Phase 0 = no promote; Phase 1 = promote unless aborted) | see §3. There is **no REJECT/REVIEW/INCOMPLETE verdict** — a boolean `collapse` is the only abort signal. |
| Eval budget | `eval_budget` | **TimeLimit 7000 (7 s) / MaxTraversals 100000 / UCTConstant 0.3** | **deployment-representative; DECOUPLED from self-play N** (A1). Candidate AND the origin anchor run at this budget. |
| Anchors | `anchor_blocks` | **`RL_PoL_origin` + `RL_PoL_masterbot`, rounds 48 each (= 96 games)** | the two same-path C++ tournaments — §6. Checkpoints bump to rounds 192 (= 384 games). |
| Abort threshold | `abort_winrate_vs_origin` | **0.35** | collapse iff the candidate's general win-rate vs the origin reference is below this. |
| Prediction-movement floor | `prediction_movement_floor` | **0.001** | calibrated from the Phase-0 smoke (§7). A fixed-probe mean \|dP\| below this = a null training update. |
| Game-length band | `game_length_band` | **[25, 60]** | calibrated from the Phase-0 smoke (§7). Self-play median game length must sit in band. |
| Parent net | `parent_bin` / `parent_pt` | `neural_weights_mixed_v221.bin` / `training/models/deepsets_v221/swa_model.pt` | warm-start source (`train.py --rl-mode` hard-fails without `--init-weights`); content-pinned by `parent_bin_sha256`; the `.pt`'s export is byte-identical to the deployed `.bin`. |
| Origin reference | `origin_bin` | **`neural_weights_mixed_v221.bin` (PERMANENT, never repointed)** | the fixed reference the `origin` anchor / collapse signal measures against; `parent_*` move on promotion, `origin_bin` never does. |

### What v4 changed vs regime v3 (the IG-axis campaign)

| Knob | v3 (IG axis) | v4 (proof-of-life) | Why |
|---|---|---|---|
| Self-play mix | ⅔ general (344) + ⅓ forced-Hotel (172) | **general only, rounds 516** | not measuring IG; 516 rounds = 1032 games/iter, preserving the training dose |
| `EpsilonIG` | 0.25 (targeted IG exploration) | **0 (OFF)** | IG-specific exploration removed |
| `EpsilonLate` | 0 (retired) | **0.05** | general, controllable late exploration (small, bounded label cost) — v4 **inverts** the v3 ε choice |
| Candidate interior iterator | `HardIterator_5var` (auto-fires IG) | **`HardIterator_5var_NoIG`** | interior never force-fires IG below root (M1 fixed the cheap way — §5) |
| Replay window `W` | 5 | **2** | with a moving generator, track the current net (H4) |
| Anchors | iter0 + narrow + steam (+ origin/masterbot at checkpoint cadence) | **origin + masterbot only** (§6) | no verdict; steam (cross-path 2016 binary) retired for the same-path AB `MasterBot_SWF` |
| Verdict / promotion | REJECT/REVIEW/INCOMPLETE + promote-unless-harm | **collapse boolean + promote-unless-collapse** | proof-of-life needs a coarse abort, not a powered gate (§3) |

Everything not listed is unchanged from v3 (N=1000, τ=0.7, K=12, c=0.3, Threads:8, rehearsal 0.10
elite, 6 ep / 1e-5 / no-SWA, eval budget 7 s / 100k, Base+8 card sets). The v3 tuple is preserved
in git (and snapshot at `eval/campaign_frozen_ig_v3.json`).

### 1a. `MaxChildren` — observe-only

`MaxChildren` caps the number of **root children** the search expands. Raising it spreads the
**fixed** search budget (`N` traversals) thinner — breadth competes with depth — so it is *coupled
to N* and stays observe-only. The engine emits `root_children` / `root_truncated` telemetry
(responder field `aitruncated`; the V2 exporter stamps both per record); we *confirm* `root_truncated`
is ~never true, we do **not** tune `MaxChildren`. The durable fix for genuinely-wide R-allocation
is a **candidate policy head + PUCT** (§6), **not** a larger `MaxChildren`.

### 1b. Label-quality & exploration regime (v4)

Self-play exploration is **early-noise + small late-noise**: τ=0.7 for turns 0–11, then argmax
whose only deviations come from the general late sampler (`EpsilonLate=0.05`). There is no
IG-targeted ε in v4 (no axis under test). A record's label noise depends on ALL deviations
occurring after it in the game, by either player — only records after the LAST deviation have
greedy-truthful labels; `EpsilonLate` is the bounded knob that trades a little of that for late
diversity. Late argmax ties break **uniformly at random** from the seeded stream
(`MoveSampler::argmaxIndex`; eval/deploy argmax unchanged) — the old first-wins tie-break composed
with the iterator's longest-move-first child ordering into a systematic over-click bias at
indifferent roots.

**Residual risk (accepted):** a value-only net gets **no counterfactual signal on unplayed
branches**. **WATCH every iteration:** the **4.6 prediction-movement probe** (a fixed-probe mean
\|dP\| below `prediction_movement_floor` = a null training update = the night's failure signal),
the **self-play game-length** (must sit in `game_length_band`) and per-seat win-rate (non-degeneracy),
and the **late sampled fraction** from the `sampled_idx`/`argmax_idx` stamps.

### 1c. Historical-baseline discontinuity (2026-06-10)

dave commit `09c5436` (Jun 10 — SWF-faithful buy-tree port + the 4-entry `DefaultOpeningBook` + the
`DefaultLimits` Mobile-Animus cap) changed partial players consumed by **every deployed player AND
the Playout evaluator** (so it also changed the `MasterBot_SWF` AB anchor's strength). Consequence:
**every number measured before Jun 10** is **not comparable** to post-port numbers. The campaign
re-baselines forward: the tuple was frozen **post-port** and the stage-0 preflight asserts the
post-port shape (`iterator_shape`, `book_sizes`). `c=0.3` is **retained** on the cValue sweep's
*monotonicity* (strength was monotonic in 1/c — a buy-tree change is unlikely to invert a monotonic
trend); a re-sweep is a cheap future experiment if the loop behaves oddly.

### 1d. Seed semantics at Threads>1

At `Threads>1` a block's `Seed` fixes the **card-set SEQUENCE** but **NOT game outcomes**: only the
main thread is seeded, and at multi-thread it does only the card-set draws while worker threads play
the games and seed independently (collision-free per-seat/slot since dave `6e93480`; the engine
warns at launch). Consequence: **same-Seed blocks in the same thread mode share card sets** (this is
why the two anchor blocks, both `Seed:2026`/`Threads:8`, get matched sets). Outcome-level
reproducibility exists only at `Threads:1`.

### 1e. Per-iteration state archive

Every iteration retains, under `training/data/rl_iter_<K>/`, alongside the JSONL/H5:
- **`parity_states/general_sp_*.json.gz`** — engine-native turn-start `GameState` JSON (gzipped),
  one per ply, slice-prefixed (the engine writes a per-block `<exportTrainingV2>_parity` dir).
  **This is the future-schema insurance**: if the DSNN feature schema evolves, past self-play is
  re-extractable by running any future `--dump-v2-record` exporter over these states — no
  re-generation with old weights needed. ⚠️ Do NOT reuse
  `training/extract_fleet_training_data.py` unmodified on archived C++ REPLAYS — it applies the JS
  convention `states[turnBoundaries[p]]`; the C++ rule is `states[p==0 ? 0 : turnBoundaries[p]-1]`.
- **`replays/general/game_*.json.gz`** — per-action snapshot replays (matchup format, viewable on
  `/replay/local`), each carrying a `meta` provenance header. The replay index **is** the V2 shard
  index (one shared per-game id, Threads-safe), so `game_0007.json.gz` is exactly
  `selfplay_0007.jsonl`'s game.
- Cost: a few MB per iteration; replay leftovers from crashed runs are moved to
  `training/data/_orphans/`, never deleted.

---

## 2. External-review addenda (A1, A6, A9) — folded in

> A2 (IG recurs all game → targeted late exploration) was an IG-axis addendum; it is **archived in
> the Appendix**, since v4 runs no IG-targeted ε.

### A1 — Decouple EVAL budget from self-play N

`RL_Eval` / `RL_Eval_origin` run at the **deployment budget** (`MaxTraversals:100000`,
`TimeLimit:7000`), **NOT** the self-play `N`. This is what makes the per-iteration eval cells (and
the powered checkpoint) deployment-representative rather than budget-confounded. Preflight enforces
the budget on both eval players (`eval_budget` check).

### A6 — Perspective round-trip (the value-orientation guard)

The bug class: a silent P0/P1 inversion anywhere along JSONL record perspective → H5 label →
net-output meaning → how the search interprets the value. Pinned on **two surfaces**:

1. **Data-side label/perspective consistency** (`training/tests/test_perspective_roundtrip.py`):
   V2 records are absolute-perspective (`outcome_p0` = P(P0/first/white wins), stamped game-level;
   `active_player` toggles per ply); `outcome_p0` constant within a game; the opposite-perspective
   twin flips the label AND swaps every feature block coherently; double-mirror is the exact
   identity.
2. **Inference-side decided-position orientation** + the **maxPlayer-negation seam** downstream of
   the scalar (`NeuralNet.cpp` `evaluateValue` tail + `UCTSearch.cpp`'s `(nnValue+1)/2`
   consumption) — covered by **`eval/a6_orientation_check.py`**: four near-final turn-start states
   from two decided elite games (both seats, both outcomes), driven through
   `js_engine/query_move.js`, asserting the engine's `airootwinrate` sides with the recorded outcome.
   Live-validated 0.998/0.001/1.000/0.001 against 0.7/0.3 thresholds.

**v4 automates this:** `a6_orientation_check.py` and the three-way feature-parity gate now run
**automatically at preflight** (`correctness_gates` check) plus an engine-exe **sha pin**
(`engine_sha`) so a stale/rebuilt binary that could silently flip the value sign or skew a feature
is caught before an unattended night.

### A9 — Pre-registered STOP condition (forward-looking)

The kill-criteria (§3) route to **escalate**, never **abandon**. Pre-register the evidence that
justifies **STOPPING** a *future measurement axis*: if the **O6 candidate-policy-head + PUCT
escalation ALSO comes back flat** (after a clean false-negative triage), that is the **action-space
/ approach** being the limit — not measurement — and the value-only-RL-on-that-axis line is
**stopped**, not re-spun. (This is dormant under proof-of-life — there is no axis being measured —
but it is the operating rule once a real axis is opened; see §6.)

---

## 3. Per-iteration signal: COLLAPSE (no verdict)

**There is no REJECT/REVIEW/INCOMPLETE verdict in v4.** It is replaced by a single boolean
**`collapse`** (a manifest field; computed by `run_eval.py::compute_collapse`):

```
collapse == True   iff the origin anchor's GENERAL win-rate < abort_winrate_vs_origin (= 0.35),
                       using the point estimate (a COARSE abort, NOT a powered gate)
collapse == False  iff the origin anchor completed at/above the threshold
collapse == None   iff the origin anchor is missing/errored (unknown — neither collapse nor safe)
```

`collapse` is a coarse, per-iteration abort signal that catches a degenerated candidate within one
iteration — which is all proof-of-life needs. It is deliberately **not** a powered comparison; the
campaign's actual strength evidence comes from the **checkpoint** (§ "Between iterations" in the
runbook), where origin + masterbot run at 384 games each (~±2.5pp).

### Promotion policy — pre-registered: promote-unless-collapse

- **Phase 0 (fixed generator):** do NOT promote anything. The generator is frozen v221; iterations
  validate the pipeline and measure throughput, they do not compound.
- **Phase 1 (promoting loop):** **promote every candidate UNLESS the run aborted** — i.e. a stage
  crash, the **4.5 val-acc tripwire** fired, **collapse == True**, or self-play is degenerate
  (game length out of band / per-seat win-rate out of [0.35, 0.65] / all draws).

Promotion runs through **`eval/promote_candidate.ps1` ONLY** (sha-verified lineage: a fresh
re-export of the candidate `.pt` must be byte-identical to the on-disk `.bin`). It repoints the
**TWO** parent pins (`RL_Eval` + `RL_SelfPlay`) and updates `campaign_frozen.json` (parent name +
sha + cached val-acc); it **NEVER** repoints `RL_Eval_origin` (the permanent v221 origin). Each
iteration + each checkpoint gets a human entry in `eval/campaign_log.md`.

### Abort criteria (pre-registered)

Abort a run if: any stage crashes; val-acc collapses (>3pp below parent at stage 4.5); win-rate vs
origin < 0.35 at stage 7 (collapse); or self-play is degenerate (length/seat/draws).

### Success criteria (pre-registered)

A run **succeeds** when it completes its iterations unattended **AND** prediction-movement is
non-null (fixed-probe mean \|dP\| ≥ `prediction_movement_floor`) **AND** self-play is
non-degenerate (game length in `game_length_band`; per-seat win-rate ∈ [0.35, 0.65]; not all draws)
**AND** strength stays within band of origin (no sustained drop below `abort_winrate_vs_origin`).
Success of the CAMPAIGN is "the loop works / the net is non-degenerate / here is the measured
throughput," never "RL improved the net."

---

## 4. False-negative triage checklist (run before declaring a flat/no-go run)

If a run "did nothing" (near-null prediction movement, flat trajectory), walk these before
concluding RL can't help — most "flat" results are a broken link, not a real result:

1. **Did temperature sample non-argmax?** → the self-play `sampled_idx` vs `argmax_idx` sidecar
   stamps. If `sampled_idx == argmax_idx` always, the sampler never explored.
2. **Labels pass inversion / scale tests?** → `test_labels.py` (scale) +
   `training/tests/test_perspective_roundtrip.py` (A6, data + inference surfaces).
3. **Did training change predictions on self-play positions?** → the **4.6** probe
   (`prediction_movement.json`): fixed-probe mean \|dP\| below `prediction_movement_floor` = a null
   update — then "flat" is a training-dose problem, not an RL-doesn't-work result.
4. **Does the exported `.bin` match PyTorch?** → the export-parity gate
   (`tools/parity/dump_value_batch.py`, worst |Δ| < 1e-4) + the **4.5** val-acc tripwire.
5. **Did eval load the intended net?** → active provenance in `run_eval.py`: pre-flight assert that
   `Players.RL_Eval.WeightsFile` == the `--weights` basename; each NeuralNet anchor's engine stderr
   must contain the per-player load line for the candidate `.bin` (`engine_confirmed_load`).
   (The `masterbot` anchor is an AB/Playout player — no NeuralNet load line to confirm.)
6. **Value ORIENTATION intact (the maxPlayer seam)?** → `python eval/a6_orientation_check.py`
   (now also auto-run at preflight as `correctness_gates`; run after any engine change).
7. **Engine binary the pinned one?** → the `engine_sha` preflight check — an unrecorded rebuild can
   silently flip a sign or skew a feature.
8. **Was self-play non-degenerate at N?** → game length vs `game_length_band`; per-seat win-rate;
   not-all-draws.
9. **Did rehearsal overwhelm the RL signal?** → rehearsal fraction (flat 0.10).
10. **Was the powered measurement read at the right cadence?** → per-iteration `collapse` cells are
    harm screens only; the powered question lives at the **checkpoint** (origin general = 384 games,
    ~±2.5pp). *Proving* a +5 pp gain needs ~786 games at 80% power (one-sided α=0.025); the
    checkpoint volume is a trend read, not a proof.

---

## 5. Candidate config + heuristic-change discipline

The candidate players (`RL_SelfPlay` generator, `RL_Eval` candidate-at-eval, `RL_Eval_origin` =
v221 reference) all share one iterator shape:

- **Root iterator:** `HardIterator_5var_IGsubset_Root` — **KEEP** (the action-space fix; the net
  chooses the IG count per turn).
- **Interior `MoveIterator`:** **`HardIterator_5var_NoIG`** — never auto-fires IG in lookahead.
  Rationale: "always-fire" collapses the hold-vs-fire distinction; "never-fire interior + per-turn
  root re-decision" gives a sensible reactive policy (hold until the root sees a reason to fire) at
  **zero combinatorial cost** (same branching, no interior enumeration). This is the **correct
  general default for every optional ability** we open up: *root chooses it; interior never
  force-fires it.* (Upgrades audit finding M1 from "accepted" to "fixed, cheaply".)
- `c=0.3`; `SelfPlaySampling:true` (generator only); eval players at the deployment budget.
  The candidate KEEPS its waste-avoid partials (measured beneficial/neutral; owner decision).

**Heuristic-change discipline.** Triage with the KEEP/OPEN lens: **KEEP-style heuristic *bugs***
(dominated misplays) → fix programmatically (they only remove provably-worse moves, helping the
loop). **Valuation / strategy** weaknesses → leave for RL. **One change per measured point.** Pin a
versioned baseline = (**resolved-config-hash** [post-parser], **net-hash**). During this campaign,
freeze everything except correctness bugs and the sanctioned levers (the RNG fix, the temperature /
root-exploration sampler, the IG-optional iterator). **Never change heuristics mid-campaign.**
Maintain a changelog (`eval/campaign_log.md`) mapping every win-rate point to one `(config-hash,
net-hash)` delta.

---

## 6. Baseline & anchors (closes audit M9)

The loop needs an external absolute-strength anchor that the steam (2016) binary couldn't provide
(it is cross-path and uses a different draw convention). v4 fixes this by running **the live
MasterBot config through the SAME C++ tournament runner** as the candidate.

**Two anchors per iteration (both same-path C++ tournaments; non-gating, small-N):**

| Anchor | Opponent | Role | N |
|---|---|---|---|
| `origin` | `RL_Eval_origin` = v221 (PERMANENT, never repointed), **same iterator as the candidate** (NoIG interior + IG-subset root) | relative — "did the lineage move from its start"; the **collapse/abort signal** (collapse iff general WR < 0.35) | 96 |
| `masterbot` | `MasterBot_SWF` — the faithful 2016-MasterBot reconstruction in the strong engine | absolute external strength **TREND** (non-gating) | 96 |

`MasterBot_SWF` is the existing AB SWF-faithful `LiveHardestAI`: `Player_StackAlphaBeta`, 7000 ms,
the narrow auto-fire iterator (`HardIterator_5var_Root` — NO IG-subset; the real bot auto-fires),
**Playout** eval, the SWF buy tree (`dave@09c5436`) + `LiveOpeningBook2` (50) + `DefaultOpeningBook`
(4) + `Ability_Filter_Live` **including Odin**. It is AB, so `UCTConstant` is inert on it
(`UCTConstant` is a UCT-only UCB1 parameter; AB does not use it).

**Checkpoint cadence (every 3–5 iterations):** both anchors bump to **rounds 192 = 384 games each**
for a powered read (~±2.5pp), run by `eval/run_checkpoint.ps1` (+ the B8 forgetting guard). THIS is
the campaign's go/no-go evidence — not per-iteration `collapse` cells.

**STEAM IS RETIRED.** The 2016 cross-path binary yardstick is replaced by the same-path AB
`MasterBot_SWF` (no cross-path-delta caveat anymore). The dropped v3 anchors — `iter0`
(candidate-vs-parent verdict; no verdict under proof-of-life), `narrow` (IG iterator-gap isolation;
not measuring IG), `steam` (cross-path 2016 binary) — are gone. The clean-attribution control
`HardestAIUCT` is parked for a future "did the *net* help" measurement.

### Escalation paths (DOCUMENTED, NOT BUILT — the durable future-axis levers)

These remain the durable levers once a *real* measurement axis is opened (they are not invoked
under proof-of-life). Reframed away from "IG kill criteria":

- **O6 — Candidate-level policy head, then PUCT.** Add a head emitting a prior over *just the ≤~30
  whole-turn portfolio candidates the iterator emits* (NOT the full click-sequence action space).
  Train it on the MCTS **visit distribution** over those candidates (AlphaZero-style). Turn **PUCT
  on at the root** so the search concentrates sims on net-preferred candidates — the standard fix
  for value-only MCTS under-exploration, and the general mechanism for "the search genuinely reasons
  about optional abilities at *every* node" (needed when "never-force interior" stops being good
  enough, and for richer action spaces). *Effort: large.* This is the **durable fix** for both
  value-only-MCTS under-exploration and the interior-optionality problem; it is the destination,
  the NoIG interior is the cheap interim. Also the durable fix for genuinely-wide R-allocation (cf.
  §1a — NOT raising `MaxChildren`).
- **O3 — Distillation bootstrap.** Periodically run the current net at high sims (10k–50k) on a
  position batch and train the value net to predict the **deep-search backed-up value** (MSE
  target) — distilling deep-search judgement into the static eval. *Effort: medium-large + extra
  deep-search compute; risks baking in the deep search's residual biases.*

**STOP (A9):** if the **O6 escalation ALSO flatlines** with a clean §4 triage on a real axis,
conclude the **action space / approach** is the limit; stop the value-only line; do not re-spin.

---

## 7. The two-phase run

**Phase 0 — fixed-generator pipeline smoke (DONE + validated 2026-06-16, iteration K=1).** Run with
**v221 frozen as the generator, no promotion**. Validates the entire pipeline (self-play →
vectorize → train → export → parity → eval) and measures throughput. Because the generator never
moves, the drift (H2) and off-policy (H4) hazards are nullified. Result (see the K=1 entry in
`eval/campaign_log.md`): **collapse False**, origin **49.5%**, masterbot **58.3%**,
prediction-movement **0.0172** (non-null), val-acc **71.6%** vs parent 71.8% (tripwire quiet), all
gates PASS, **NOT promoted**. The Phase-0 smoke is what calibrated `prediction_movement_floor` =
0.001 and `game_length_band` = [25, 60] into the frozen tuple.

**Phase 1 — promoting loop (owner launches when ready).** Separate session, **promotion on
(promote-unless-collapse)**, run N iterations unattended, bounded by the strength tripwire
(abort-on-collapse). This is the actual self-improvement loop; the goal remains "it runs and doesn't
degenerate," now with a moving generator.

---

## Run prerequisites

These MUST be satisfied before `eval/run_iteration.ps1 -K <k>` runs for real. Stage 0
(`eval/preflight_config.py`, **18 checks**) machine-checks most of them; all were green at the
Phase-0 run.

1. **Frozen tuple** matches `config.txt` — preflight `frozen_tuple` / `iterator_shape` /
   `selfplay_player` / `parent_repin` / `origin_pin` / `anchor_blocks` / `eval_budget`.
2. **Parent net** = v221, content-pinned (`parent_sha`); `RL_Eval_origin` permanently v221
   (`origin_pin`).
3. **`MasterBot_SWF`** defined (the AB SWF-faithful `LiveHardestAI` alias) + the `RL_PoL_origin` /
   `RL_PoL_masterbot` anchor blocks present and rest `run:false`.
4. **Correctness gates green** — a6 orientation + three-way feature parity auto-run at preflight
   (`correctness_gates`); both engine exes sha-match the frozen pins (`engine_sha`).
5. **Training data** — the ELITE rehearsal corpus (`human_elite_2000_45s_v2.h5`) and the capped
   held-out val set (`human_val_1700_50k_v2.h5`) exist (`existences`); the parent `.pt` exists.
6. **`unit_index.json`** present with the canonical 116 units (`unit_index`) — without it a
   NeuralNet player silently evaluates on globals alone.
7. **No `use_dsnn.txt`** drop-in sentinel next to the engine exes (`use_dsnn_sentinel`).

---

## Throughput

Phase 0 (iteration K=1, 2026-06-16) ran the full pipeline on **1,032 general games / 37,899
self-play records**, eval at 96 games/anchor. Self-play is **CPU-bound**; the dave engine is **x64**
(no x86 4-thread OOM cap), Threads:8. Stage 3 (the W=2 RL fine-tune, no-SWA, elite corpus) completed
in single-digit minutes on the iter-0 dry run. Fill the table below from a timed Phase-1 iteration
before sizing any AWS spend against measured throughput rather than assumption.

| Metric | Value | How measured | Status |
|---|---|---|---|
| games / hour @ N=1000 | _TBD_ | wall-clock over a fixed-rounds self-play block | measure on a Phase-1 iter |
| NN-evals / sec | _TBD_ | responder eval counter over the self-play run | measure on a Phase-1 iter |
| CPU utilisation | _TBD_ | OS monitor during self-play (Threads × instances) | measure on a Phase-1 iter |
| shard write throughput | _TBD_ | bytes/sec of `selfplay_*.jsonl` | measure on a Phase-1 iter |
| eval games / hour | _TBD_ | wall-clock over an anchor block at the 7 s budget | measure on a Phase-1 iter |

---

# Appendix: IG axis — worked example (regime v3, ARCHIVED)

> **SUPERSEDED — kept as the reusable next-axis template, NOT live.** Everything below describes the
> regime-v3 IG-optional (Infusion-Grid click-count) measurement campaign, which v4 retired (audit
> C1: the IG over-click was fixed by action-space widening, not RL). The reusable thing is the
> axis-measurement *framework* (a targeted exploration knob, an on-axis counterfactual watch-stat, a
> verdict, kill criteria) — instantiate it for the next real axis. **None of this runs in v4.**

## v3 IG exploration mechanism — `EpsilonIG` (ARCHIVED)

Regime v3 retired the untargeted `EpsilonLate` (its 0.69 deviations/game bought ~1 IG-relevant
deviation per 32 games while risking late-game label flips) in favour of **`EpsilonIG=0.25` —
TARGETED IG-count exploration**: at roots whose children span ≥2 distinct IG click counts, with
prob 0.25 play the most-visited child at a NON-argmax count — the search's best whole-turn line
conditional on a different IG count, an on-axis counterfactual at near-zero label-corruption cost.
Watch-stat: **`ig_contrast_pairs`** (stage 8) — realized matched-pair IG contrasts; if ~0, the
targeted ε was not reaching the axis. v4 sets `EpsilonIG=0` and restores `EpsilonLate=0.05`.

## v3 self-play data mix — forced-Hotel (ARCHIVED)

Regime v3 ran **⅔ general + ⅓ forced-Hotel, rounds 344 + 172**: `RL_SelfPlay_General` (no forcing)
+ `RL_Step2_Smoke` (`ForcedCards:["Hotel"]`) ≈ 1032 games/iter — the forced block guaranteed
IG-feasible states (Hotel/Infusion-Grid needs 5B + House tech, so IG decisions live past turn 12).
v4 drops the forced block (retained in config, unused) and runs one general block at rounds 516
(same game count).

## A2 — IG recurs all game → TARGETED late exploration (ARCHIVED)

IG is a per-turn decision that recurs all game, but the τ window ends at turn 12 — exactly where IG
decisions BEGIN. v1 (whole-game τ) over-corrected into label corruption; v2 (`EpsilonLate=0.05`)
was quantitatively thin (~1 IG-relevant deviation per 32 games). v3 resolved A2 with
`EpsilonIG=0.25` (≈0.4 on-axis counterfactuals per forced game, verified by `ig_contrast_pairs`).
Under v4 there is no IG axis, so A2 is moot — the late sampler is the general `EpsilonLate=0.05`.

## v3 verdict + kill/escalation framing (ARCHIVED)

v3 used a **REJECT/REVIEW/INCOMPLETE verdict** (detect-proven-harm; nothing auto-promotes), driven
off the `iter0/general` anchor's 95% Wilson `ci_upper` vs 0.5, with `d_rl` (forced pool, the
IG-widened axis) and `d_reg` (general pool) recorded as information. Kill criteria triggered on ≥3
consecutive flat iterations + a clean false-negative triage, then routed to escalate (Lever 0
re-tune `EpsilonIG`; O6 policy head + PUCT; O3 distillation). v4 replaces the verdict with the
boolean `collapse` (§3) and promote-unless-collapse; the escalation paths O6/O3 survive in the main
body (§6) reframed as durable future-axis levers. The §3 kill framing here is the **template** to
re-instantiate for the next real axis: pre-register an effect size, a targeted exploration knob, an
on-axis counterfactual watch-stat, and a powered checkpoint measurement.

## v3 IG watch-stats & coverage (ARCHIVED)

The v3 false-negative triage leaned on IG-specific instrumentation: `manifest.action_coverage`
IG-click-count distribution (`ig_click_dist_selfplay` / `ig_click_dist_argmax`,
`mean_ig_clicks_*`), the `ig_contrast_pairs` realized-counterfactual count, and the forced/general
pool split (`d_rl` vs `d_reg`) as the overfit detector. Under v4 the IG coverage stats still get
**recorded** (stage 8 telemetry — `action_coverage.py` is non-fatal) but they are watch-stats with
no axis riding on them; the gating signals are prediction-movement, game-length/seat non-degeneracy,
and collapse.
