# RL Self-Play Campaign — Frozen Config + Decision Rules

> **Spec:** `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` (§7, §9, §12, §14 are folded in below;
> the spec carries a per-section status banner — several of its sections are superseded).
> **Scope:** the IG-optional (Infusion-Grid click-count) axis-1 proof-of-life campaign.
> **Status:** **REGIME v3 — re-frozen 2026-06-13** after the third (design-level) audit
> (`docs/superpowers/plans/2026-06-12-rl-loop-design-audit-FINDINGS.md`) and the owner's J1–J7
> decisions (`eval/campaign_log.md`). Machine source: `eval/campaign_frozen.json` (now TWO-TIER,
> §1 below); operator reference: `eval/rl_runbook.md`. v3 headlines vs v2: J1 volume (rounds
> 344+172, ~1032 games/iter) + NO SWA + rehearsal flat 0.10 on the ELITE corpus; J2
> promote-unless-harm + checkpoint origin evals (the campaign's answer-producing measurement);
> J3 per-iteration eval = iter0 only at 192+384 games (2-seed panels); J4 self-play seeds derive
> from K; **J5 targeted IG-ε replaces EpsilonLate**; J6 tactical = telemetry; J7 two-tier tuple.

This document is the campaign contract. **Any change to the frozen HP tuple below = a NEW campaign**
(re-anchor and re-baseline). The machine-readable tuple is **`eval/campaign_frozen.json`** — stage 0 of
`eval/run_iteration.ps1` (`eval/preflight_config.py`) **hard-fails if the dave `config.txt` drifts from it**
and never silently rewrites either side. The driver that wires the one-iteration loop is
`eval/run_iteration.ps1`; the per-iteration dashboard is `eval/render_dashboard.py`.

---

## 1. Frozen HP tuple (spec §10 item 10, §11)

Treat the whole tuple as the campaign identity. **FROZEN 2026-06-11** (owner decision post-audit) —
no placeholders remain. Machine source: `eval/campaign_frozen.json`; enforced against `config.txt`
by `eval/preflight_config.py` (stage 0).

| HP | Symbol | Value | Notes |
|---|---|---|---|
| Self-play traversals | `N` (MaxTraversals) | **1000 — FROZEN by judgment** | Owner decision on the screen-only calibration data (the `calibrate_n.py` sweeps were screening, not proof; the Jun-4→9 crippled-iterator window invalidated the earlier N=256/512 picks). Under regime v2 argmax governs most moves, so **N's argmax quality matters MORE**, not less. A **32-game re-screen at the regime-v2 tuple passes ALL gates** (`eval/n1000_rescreen_k12.json`; the v1 whole-game-sampling record is `eval/n1000_rescreen.json`). Lives on `RL_SelfPlay` (+ the per-N `RL_SelfPlay_N*` blocks). |
| Temperature | `τ` (TemperatureTau) | **0.7** | self-play sampler only; eval is pure argmax. Set by the pre-agreed probe rule (`eval/tau_probe_n1000.json`): at N=1000/c=0.3 the root visit distributions are **near-uniform** (median top-share 0.141 < 0.20 AND median normalized entropy 0.984 > 0.90) → τ=0.7 sharpens them. |
| Temperature horizon | `K` (TemperatureK) | **12** | τ-sampling fires for turns **0–11 only** — past the opening book and through the early-mid region where the MB-flavour data bias lives. |
| ε-uniform root noise | `ε` (EpsilonUniform) / `EpsilonLate` / **`EpsilonIG`** | **0** / **0 (retired)** / **0.25 (regime v3)** | EpsilonUniform stays 0 in the opening window (τ carries the early exploration). **Regime v3 retires the untargeted `EpsilonLate`** (its 0.69 deviations/game bought ~1 IG-relevant deviation per 32 games while risking late-game label flips) **in favour of `EpsilonIG=0.25` — TARGETED IG-count exploration**: at roots whose children span ≥2 distinct IG click counts, with prob 0.25 play the most-visited child at a NON-argmax count — the search's best whole-turn line conditional on a different IG count, an on-axis counterfactual at near-zero label-corruption cost. Watch-stat: `ig_contrast_pairs` (stage 8). All three preflight-enforced EQUAL to frozen (absent key = 0.0). Late argmax ties now break uniformly at random (A1 — see §1f). |
| UCT constant | `c` (UCTConstant) | **0.3** | the tuned cValue, on every RL player AND injected by `js_engine/query_move.js` by default (M-06 fix — omitting it silently regressed to the engine default 2.0, the worst measured c). |
| Self-play threads | — | **Threads:8** | BOTH self-play blocks (`RL_Step2_Smoke` + `RL_SelfPlay_General`); the dave engine is x64 and Threads:8 export was audit-verified clean. |
| Self-play data mix | `selfplay_mix` | **⅔ general + ⅓ forced-Hotel, rounds 344+172 (J1 upper)** | `RL_SelfPlay_General` (rounds:344 → ~688 games, NO ForcedCards) + `RL_Step2_Smoke` (rounds:172 → ~344 games, ForcedCards `["Hotel"]`) ≈ **1032 games/iter, ~36k records, ~470 optimizer steps** — the J1 dose fix (the old 43+21 smoke scale produced ~78 steps, an update ~2 orders below eval resolution). Separate export dirs REQUIRED. Preflight-enforced. |
| Self-play seeds | `selfplay_seed_base` | **general 5600 / forced 5500, + K at run time (J4)** | fresh card sets every iteration (coverage growth — the old fixed Seeds froze the campaign's whole set universe), reproducible per iteration; the driver sets base+K transiently and restores the base (preflight asserts the at-rest base). |
| Replay window | `W` | 5 | sliding self-play buffer; membership now stamp-checked (C5: lineage attrs + `INVALID` markers — quarantine = `touch INVALID`, not file-moving; a non-promoted candidate's H5 STAYS, it was parent-generated). |
| Rehearsal | — | **flat 0.10, ELITE corpus** | `human_elite_2000_45s_v2.h5` (both ratings ≥2000, 45s+ controls; provenance-inherited slice of human_1800_v2 — same logic as the MB-fleet exclusion: weaker-play outcomes fight the RL signal). The 0.30 start was retired: forgetting measured ABSENT at this step size (training-03); the instrumented raise path is the 4.5 tripwire + the checkpoint B8 origin-constant guard. Epoch length = `ceil(sp_total/(1-frac))` (M-04). |
| Training schedule | — | **6 epochs @ 1e-5, NO SWA, seeded** | J1/training-02: SWA averaged 4 near-collinear snapshots, shrinking the update ~20% for no accuracy gain — the candidate is `final_model.pt` (last-epoch weights). Seed 2026000+K (reproducible candidates). |
| Verdict + promotion policy | — | **REJECT/REVIEW/INCOMPLETE + PROMOTE-UNLESS-HARM (J2)** | see §3 — the verdict stays detect-proven-harm; the PROMOTION POLICY is now pre-registered: promote every candidate unless REJECT / tripwire / REPRODUCED tactical regression (via `eval/promote_candidate.ps1`, the only legal promotion mechanism — sha-pinned). The campaign's evidence comes from CHECKPOINT origin evals (`eval/run_checkpoint.ps1`, every 3–5 iterations: 768 general + 192 forced games vs the PERMANENT v221 origin, ~±3.5pp), not per-iteration cells. |
| Rollback margin | `Y` | 0.03 (**recorded metadata only**) | nothing gates on it since 2026-06-10; `d_reg` is informational (with `general_wr_ci`). |
| Eval budget | — | **MaxTraversals 100000 / TimeLimit 7000 (7 s)** | **deployment-representative; DECOUPLED from self-play N** — A1. Candidate AND every anchor run at this budget. |
| Effect size | `E` | +5 pp (**recorded metadata only**) | the smallest IG-driven gain judged worth AWS spend; informs the human call, gates nothing (the old GO rule that used it was statistically incoherent — see §3). |
| Root child cap | `MaxChildren` | **40 — FROZEN, observe-only** | see §1a. |
| SWA | — | start-epoch **3**, epochs **6**, lr **1e-5** | RL fine-tune schedule (frozen per campaign). |
| Parent net | — | `neural_weights_mixed_v221.bin` / `training/models/deepsets_v221/swa_model.pt` | warm-start source (E1 fix: `train.py --rl-mode` hard-fails without `--init-weights`); the `.pt`'s export is byte-identical to the deployed `.bin`. |

### 1a. `MaxChildren = 40` — FROZEN (observe-only) rationale

`MaxChildren` caps the number of **root children** the search expands. Raising it spreads the **fixed**
search budget (`N` traversals) thinner — breadth competes with depth — so it is *coupled to N* and stays
**frozen** for this IG-only campaign. On the IG axis the iterator emits ~8 root children, far below 40,
so the cap **never binds** (`root_truncated` should be ~never true).

The engine now emits `root_children` / `root_truncated` telemetry (responder field `aitruncated`; the V2
exporter stamps both per record). This campaign treats them as **OBSERVE-only**: we *confirm* `root_truncated`
is ~never true (the calibration screens measured `any_root_truncated: false` across all N, max 33 root
children — committed artifact `eval/n_calibration.json`); we do **not** tune `MaxChildren`. The durable fix for genuinely-wide R-allocation
(many competing portfolio candidates) is a **candidate policy head + PUCT** (§14, O6), **not** a larger
`MaxChildren`.

### 1b. Label-quality & exploration regime (v3, 2026-06-13)

History: **v1** (K=999 whole-game τ-sampling) measured 40–46% non-argmax moves; **v2** (K=12 +
EpsilonLate=0.05) cut total deviations ~10× but its 0.69 untargeted deviations/game bought roughly
ONE IG-relevant deviation per 32 games (measured: the τ window reaches ZERO IG-feasible decisions —
Hotel needs 5B + House tech, so IG decisions live past turn 12). **v3 = early-noise +
late-TARGETED-precision**: τ=0.7 for turns 0–11, then argmax whose only deviations are
**EpsilonIG-targeted IG-count counterfactuals** (§1 table) — exploration mass goes exactly where
the campaign question lives, at near-zero trajectory-divergence cost (the deviation is a searched
whole-turn sibling, not a random move).

**Mechanism correction (third audit, selfplay-04):** a record's label noise depends on ALL
deviations occurring after it in the game, by either player — only records after the LAST
deviation have greedy-truthful labels. "Early noise = truthful labels" was an overclaim; the real
v2/v3 win is the ~10× reduction in TOTAL deviations plus (v3) confining late deviations to
value-adjacent IG siblings. Mind this when re-tuning exploration (Lever 0, §6).

**Residual risk (accepted):** a value-only net gets **no counterfactual signal on unplayed
branches**; EpsilonIG buys IG-axis counterfactuals only. **WATCH every iteration:** the stage-8
`ig_contrast_pairs` watch-stat (realized matched-pair IG contrasts — if ~0, the targeted ε is not
reaching the axis), the 4.6 prediction-movement probe (a near-zero fixed-probe mean|dP| = a null
training update), and the late sampled fraction from the `sampled_idx`/`argmax_idx` stamps.

### 1f. UCB indifference band at the frozen (N, c) — and the A1 tie-break fix (2026-06-13)

At N=1000/c=0.3 with 8–24 root children, UCB1 visits children near-equally whenever their backed-up
values are within `c·sqrt(ln N / n_child)` ≈ **0.07–0.12 win-prob** of the best (the probe shows
9/41 roots at EXACT round-robin visits). Two consequences, both now handled: (a) "late-game argmax"
among portfolio candidates inside that band is arbitrary selection, so per-iteration self-play
quality claims should not lean on argmax precision (the eval budget's band is ~0.0125 — A1's
decoupling is what makes eval numbers meaningful); (b) the old first-wins visit tie-break composed
with the iterator's longest-move-first child ordering into a SYSTEMATIC over-click bias at
indifferent roots — fixed 2026-06-13: self-play argmax ties now break uniformly at random from the
seeded stream (`MoveSampler::argmaxIndex`; eval/deploy argmax unchanged). A cheap (N,c)
discrimination re-probe (c=0.15 / N=4000 over the 41 states) is the sanctioned first experiment if
checkpoint trends look exploration-starved.

### 1c. Historical-baseline discontinuity (2026-06-10)

dave commit `09c5436` (Jun 10 — SWF-faithful buy-tree port + the 4-entry `DefaultOpeningBook` + the
`DefaultLimits` Mobile-Animus cap) changed partial players consumed by **every deployed player AND the
Playout evaluator**. Consequence: **every number measured before Jun 10** — including the pre-RL cValue
sweep that chose the frozen `c=0.3`, the May 17–18 parity/DSNN results, and the Jun-8 anchor runs — was
measured against a **DIFFERENT opponent configuration** and is **not comparable** to post-port numbers.
The campaign re-baselines forward: the tuple was frozen **post-port** (2026-06-11) and the stage-0
preflight asserts the post-port shape (`iterator_shape`, `book_sizes`). `c=0.3` is **retained** on the
cValue sweep's *monotonicity* (strength was monotonic in 1/c — a buy-tree change is unlikely to invert
a monotonic trend); a re-sweep is a cheap future experiment if iter-1 behaves oddly.

### 1d. Seed semantics at Threads>1 (E9)

At `Threads>1` a block's `Seed` fixes the **card-set SEQUENCE** but **NOT game outcomes**: only the
main thread is seeded, and at multi-thread it does only the card-set draws while worker threads play
the games and seed independently (collision-free per-seat/slot since dave `6e93480`; the engine warns
at launch). Consequences: **same-Seed blocks in the same thread mode share card sets** — that is why
the whole cal N-family (shared `Seed:4242`, all `Threads:8` since 2026-06-11) gets **matched sets**
across N. `Threads:1` blocks do **not** share sets across blocks even at the same Seed: the game RNG
interleaves with the set draws, so each block's per-set sequence diverges after game 1. Outcome-level
reproducibility exists only at `Threads:1`.

### 1e. Per-iteration state archive (2026-06-12 — replay-audit fixes)

Every iteration retains, under `training/data/rl_iter_<K>/`, alongside the JSONL/H5:
- **`parity_states/{general,forced}_sp_*.json.gz`** — engine-native turn-start `GameState` JSON
  (gzipped), one per ply, slice-prefixed (the engine writes per-block `<exportTrainingV2>_parity`
  dirs — gameIds restart at 0 per block, so a shared dir would collide; stage 1.5 archives both
  flat with the prefix). **This is the future-schema insurance**: if the DSNN feature schema
  evolves, past self-play is re-extractable by running any future `--dump-v2-record` exporter over
  these states — no re-generation with old weights needed. (Previously deleted every iteration; the
  V2 JSONL alone is schema-frozen and cannot serve this purpose.) ⚠️ Do NOT reuse
  `training/extract_fleet_training_data.py` unmodified on archived C++ REPLAYS — it applies the JS
  convention `states[turnBoundaries[p]]`; the C++ rule is `states[p==0 ? 0 : turnBoundaries[p]-1]`.
- **`replays/{general,forced}/game_*.json.gz`** — per-action snapshot replays (matchup format,
  viewable on `/replay/local`), each carrying a `meta` provenance header (tournament/seed/threads;
  `formatVersion:1`). The replay index **is** the V2 shard index (one shared per-game id,
  Threads-safe), so `game_0007.json.gz` is exactly `selfplay_0007.jsonl`'s game; a replay's
  turn-start state for ply p is `states[p==0 ? 0 : turnBoundaries[p]-1]` (verified equal to the V2
  capture).
- Cost: ~15–20 MB per 128-game iteration (replays ~50 KB gz/game; sidecars ~3 KB gz/state; capture
  overhead measured below run-to-run noise). Replay leftovers from crashed runs are moved to
  `training/data/_orphans/`, never deleted.

---

## 2. External-review addenda (A1, A2, A6, A9) — folded in

### A1 — Decouple EVAL budget from self-play N; regression measured on the right anchor

`RL_Eval` / `RL_Eval_iter0` run at the **deployment budget** (`MaxTraversals:100000`, `TimeLimit:7000`),
**NOT** the self-play `N`. The regression delta `d_reg` (informational since 2026-06-10, recorded with
`general_wr_ci`) is computed from **`RL_Eval_iter0_general`** (candidate vs the parent net, **SAME
IG-optional config + SAME budget**), **NOT** from the narrow anchor (`RL_Narrow` = v221 on
`HardIterator_5var_Root` — a *different iterator* at 100k; the only variable vs the candidate is the
iterator). Using the narrow anchor for `d_reg` would let a pure iterator gap masquerade as a net
regression. The narrow and STEAMAI anchors are **trajectory yardsticks only** — never gate on them.

### A2 — IG recurs all game → TARGETED late exploration (RESOLVED for real, regime v3)

The original concern: IG is a per-turn decision that recurs all game, but the τ window ends at
turn 12 — exactly where IG decisions BEGIN (Hotel needs 5B + House tech; the rescreen measured the
τ window reaching ZERO IG-feasible roots). v1 (whole-game τ) over-corrected into label corruption;
v2 (`EpsilonLate=0.05`) was quantitatively thin — ~1 IG-relevant deviation per 32 games. **v3
resolves A2 with `EpsilonIG=0.25`**: at every late root where the IG decision is actually LIVE
(children span ≥2 click counts), a 25% chance of playing the most-visited DIFFERENT-count child —
≈0.4 on-axis counterfactuals per forced game, verified per-iteration by `ig_contrast_pairs`.

### A6 — Perspective round-trip (IMPLEMENTED 2026-06-11 — `training/tests/test_perspective_roundtrip.py`)

The bug class: a silent P0/P1 inversion anywhere along JSONL record perspective → H5 label →
net-output meaning → how the search interprets the value. Implemented as **two test surfaces** in
`training/tests/test_perspective_roundtrip.py`, run via the standard pytest suite
(`python -m pytest training/tests/ -v`; ~3 s, CPU):

1. **Data-side label/perspective consistency.** V2 records are **absolute-perspective**
   (`outcome_p0` = P(P0 / first / white wins), stamped game-level; `active_player` toggles per ply).
   Pinned on the real human corpus + pure functions: `outcome_p0` constant within a game
   (a label varying with `active_player` IS the inversion class); `active_player == ply_index % 2`;
   the opposite-perspective twin (`vectorize_v2.mirror_record`) flips the label AND swaps every
   feature block coherently (globals p0↔p1, supply columns, instance owners; `under_attack`
   invariant); double-mirror is the exact identity. Note: a P0-win-rate bound has **no** inversion
   power on the seat-balanced 1800+ human corpus (measured P0 WR 0.508) — orientation is carried
   by surface 2.
2. **Inference-side decided-position orientation.** The v221 SWA net evaluated on the LAST
   turn-start record of each player from 60 decided human games (measured 2026-06-11): mean value
   **0.952** on P0-won records, **0.025** on P0-lost, **97.5%** sided correctly. Gate thresholds sit
   with headroom below measurement (>0.80 / <0.20 / ≥85%): an inversion scores ~0.05 / ~0.95 /
   ~2.5% — the gate catches INVERSION, not net quality.

The **C++ side** of the round-trip is pinned by the stage-5 export-parity gate
(`tools/parity/dump_value_batch.py`, tol 1e-4 since B2 — scope: weights-export + forward
arithmetic only). The maxPlayer-negation seam downstream of the scalar (`NeuralNet.cpp`
`evaluateValue` tail + `UCTSearch.cpp`'s `(nnValue+1)/2` consumption) — the one sign flip every
other gate is structurally blind to — is **now COVERED (B1, 2026-06-13)** by
**`eval/a6_orientation_check.py`**: four near-final turn-start states from two decided elite
games (both seats, both outcomes; `eval/a6_states/`), driven end-to-end through
`js_engine/query_move.js`, asserting the engine's `airootwinrate` (chosen root child's backed-up
win rate, mover perspective) sides with the recorded game outcome. Validated live:
0.998/0.001/1.000/0.001 against 0.7/0.3 thresholds — a sign flip inverts all four. **Run it after
ANY engine change** (it is §4 triage item 11 and on the promotion checklist).

### A9 — Pre-registered STOP condition

The kill-criteria (§3) always route to **escalate**, never **abandon**. Pre-register the evidence that
justifies **STOPPING**: if the **O6 candidate-policy-head + PUCT escalation ALSO comes back flat** (after a
clean false-negative triage), that is the **action-space / approach** being the limit — not measurement —
and the value-only-RL-on-this-axis line is **stopped**, not re-spun.

Cost note: the **local false-positive cost is more than £400** — a wrong "spend AWS" call buys the whole
AWS campaign's engineering + monitoring + opportunity cost. That asymmetry is why the verdict (§3) is
conservative (detect-proven-harm + human judgment, never auto-promote) and the regression measurement (A1) is
wired carefully.

---

## 3. Per-iteration VERDICT (2026-06-10 — replaces the spec-§12 GO rule)

The spec's original GO rule (`CI_lower(d_rl) > 0 AND d_rl >= E AND d_reg >= -Y`) was **deleted as
statistically incoherent at the configured sample size**: at 128 games/anchor, an observed +5 pp needed
~58.7% to clear the CI condition, so P(GO | true +5 pp) ≈ 13% — the gate could essentially never fire on
the effect it was pre-registered for. "Prove improvement" is replaced by **"detect proven harm" + human
judgment** (`run_eval.py::compute_verdict`, `VERDICT_RULE`). **REVIEW means the numbers could not prove
harm — NOT that safety is certified.** Honest power at n=128: P(REJECT | true −5pp) ≈ 18% and
P(REJECT | true parity) ≈ 2.1% — REJECT reliably fires only for ~−10pp-and-worse regressions:

```
verdict input = the iter0/GENERAL anchor (candidate vs PARENT promoted net, unforced sets,
                deployment budget, iid 95% Wilson CI on the candidate's win rate):
  REJECT     iff the anchor completed AND ci_upper < 0.5   (proven worse than the parent)
  REVIEW     iff it completed and ci_upper >= 0.5          (everything else is a human call)
  INCOMPLETE iff it is missing/errored                     (cannot certify not-worse)
```

`d_rl` (forced pool, the IG-widened axis) and `d_reg` (general pool) are still computed and recorded —
as **information only**, each with a Wilson CI on the underlying win rate (`forced_wr_ci` /
`general_wr_ci`). `E` and `Y` are recorded metadata; nothing gates on them. The manifest is written
**incrementally and atomically** (temp file + `os.replace` after every completed pool/anchor, with
`"complete": false` until the end) so a killed run keeps its finished anchors.

**PROMOTION POLICY — PRE-REGISTERED (J2, 2026-06-13): promote-unless-harm.** The third audit found
the decision layer had no coherent operating point: REVIEW is near-certain at these volumes, and
without promotions the generator never changes (N-3 pins it to the frozen parent), so iterations
were near-replicates rather than compounding RL. The frozen policy: **promote every candidate
UNLESS (a) verdict == REJECT, (b) the 4.5 tripwire fired, or (c) a REPRODUCED tactical regression**
(one-shot stage-6 reports don't count — re-run the case 3–5×). Promotion runs through
**`eval/promote_candidate.ps1` ONLY** (sha-verified lineage; the manual 6-edit procedure is
retired). The campaign's actual evidence is the **checkpoint origin eval**
(`eval/run_checkpoint.ps1`, every 3–5 iterations: lineage vs the PERMANENT v221 `RL_Eval_origin`,
768 general + 192 forced games ≈ ±3.5pp — ~80% power at +5pp) — per-iteration cells are harm
screens. d_rl-vs-origin keeps its CUMULATIVE meaning across promotions because `RL_Eval_origin` is
never repointed (drl-03; preflight `origin_pin`). Each iteration + each checkpoint gets a human
entry in `eval/campaign_log.md`.

### Kill criteria (spec §8)

Trigger when **≥3 consecutive iterations** show no improvement beyond the CI **AND** the false-negative
triage (§4) passes (action present, temperature sampling, labels valid, predictions changed, export parity
OK, eval powered, self-play non-degenerate). Then terminate the local phase and either **increase N**,
**widen further**, or **escalate** (→ §6). Per A9, the only route to *abandon* is a flat O6 escalation with a
clean triage.

---

## 4. False-negative triage checklist (spec §9 — run before declaring no-go)

Adapted for the IG-click-count axis (items 1–2 mapped to this campaign's instrumentation):

1. **Was the new action (IG-click-count change) in the root candidate set often enough?**
   → `manifest.action_coverage` IG-click-count distribution (`ig_click_dist_selfplay` /
   `ig_click_dist_argmax`, `mean_ig_clicks_*`). If counts collapse to {0} or {all}, the action was never
   actually optional in search.
2. **Did temperature sample non-argmax?** → the self-play `sampled_idx` vs `argmax_idx` sidecar stamps
   (per-record). If `sampled_idx == argmax_idx` always, the sampler never explored.
3. **Labels pass inversion / scale tests?** → `test_labels.py` (scale) +
   `training/tests/test_perspective_roundtrip.py` (A6 perspective round-trip, data + inference surfaces).
4. **Did training change predictions on self-play positions?** (a static net → no learning).
5. **Does the exported `.bin` match PyTorch?** → the export-parity gate (`tools/parity/dump_value_batch.py`,
   worst |Δ| < 1e-3) + the stage-4.5 val-acc tripwire (candidate within 3 pp of parent on the held-out
   human val set — catches an E1-class bad-init/bad-train cheaply).
6. **Did eval load the intended net?** → ACTIVE provenance in `run_eval.py`: (a) pre-flight assert that
   `Players.RL_Eval.WeightsFile` == the `--weights` basename BEFORE any block flips on; (b) each C++
   anchor's engine **stderr must contain the per-player NeuralNet load line for the candidate `.bin`**
   (`engine_confirmed_load` stamped per anchor; a completed-but-unconfirmed anchor hard-fails). Plus the
   passive stamps (`candidate_net_sha256`) and the contamination asserts (no `PRISMATA_FORCE_DSNN`, no
   `use_dsnn.txt`; a missing 2016-MasterBot baseline soft-skips ONLY the steam yardstick — stage-0
   preflight hard-fails on it for campaign runs).
7. **Was eval statistically powered for the question asked?** → per-iteration cells are harm
   screens only; the powered question lives at the CHECKPOINT (origin general = 768 games ≈
   ±3.5pp). *Proving* a +5 pp gain needs **~786 games at 80% power (one-sided α=0.025)** — the
   third audit corrected the old "≈600" figure (600 ≈ 67–78% power) — which is what the checkpoint
   volume was sized to. The paired per-card-set CI (manifest `paired_ci`, from the A4 rounds CSV)
   is reported alongside and is typically tighter; it is not yet the verdict statistic.
8. **Was self-play non-degenerate at N?** → the calibrate_n non-degeneracy check; game-length / ply stats.
9. **Did rehearsal overwhelm the RL signal?** → rehearsal fraction schedule (start 0.30 → floor 0.10).
10. **Target-up but general-down (overfit, not no-learning)?** → compare forced-pool `d_rl` vs general-pool
    `d_reg`.
11. **Value ORIENTATION intact (the maxPlayer seam)?** → `python eval/a6_orientation_check.py`
    (B1 — seconds; the only test that catches a sign flip at the NeuralNet→UCT consumption seam;
    run after any engine change and before declaring any no-go).
12. **Did training move predictions MEASURABLY?** → the stage-4.6 prediction-movement probe
    (`prediction_movement.json`): fixed-probe mean|dP| ≲ 1e-4 = a null update (rl-design-01) —
    the "flat" result is then a training-dose problem, not an RL-doesn't-work result.

---

## 5. Heuristic-change discipline (spec §7)

Triage with the KEEP/OPEN lens: **KEEP-style heuristic *bugs*** (dominated misplays — stamina-blind absorb,
Galvani-over-Drone breach, chill on irrelevant walls, resource floating) → fix programmatically (they only
remove provably-worse moves, helping RL). **Valuation / strategy** weaknesses (Gauss-rush, passivity,
Zemora/Antima planning) → **leave for RL**.

**One change per measured point.** Pin a versioned baseline = (**resolved-config-hash** [post-parser, not
source JSON], **net-hash**). A/B a heuristic fix with the *fixed* net, then merge + re-anchor (re-run the
iter-0 anchor baseline — v221 on the changed config). **RL iterations change ONLY the net** on a
**resolved-config-hash-pinned** frozen config.

**During this first proof-of-life campaign, freeze everything except the 4 sanctioned levers:**
1. the **RNG fix** (seedable, thread-hash-free stream),
2. the **temperature / root-exploration sampler**,
3. the **IG-optional iterator** (`HardIterator_5var_IGsubset_Root`),
4. **correctness bugs** that invalidate the run.

**Never change heuristics mid-RL-campaign.** Maintain a **changelog** mapping every win-rate point to exactly
one `(config-hash, net-hash)` delta.

---

## 6. Escalation paths (spec §14 — DOCUMENTED, NOT BUILT)

If the §3 kill-criteria trigger (≥3 flat iterations with a clean §4 triage), escalate **in this order**
before spending AWS or abandoning the value-only approach:

- **Lever 0 (A2) — re-tune `EpsilonIG` (e.g. 0.25→0.5) and/or re-probe (N, c).** Regime v3 already
  runs targeted IG-ε, so this lever is re-tuning, not enabling — **try it FIRST** if the checkpoint
  trend is flat AND `ig_contrast_pairs` reads low (config values + the §1f (N,c) discrimination
  probe; HP-tier change = new campaign, update `campaign_frozen.json` + preflight together). Mind
  §1b's corrected label-noise mechanism — deviations anywhere in the game tax all earlier labels,
  which is why the targeted form (value-adjacent siblings only) is preferred over raising any
  global ε.
- **O6 — Candidate-level policy head, then PUCT.** Add a head emitting a prior over *just the ≤~30 whole-turn
  portfolio candidates the iterator emits* (NOT the full click-sequence action space — that's the hard
  "mapping problem" and is why it's deferred). Train it on the MCTS **visit distribution over those
  candidates** (AlphaZero-style, on the small fixed candidate set). Turn **PUCT on at the root** so the
  search concentrates sims on net-preferred candidates — the standard fix for value-only MCTS
  under-exploration. *Effort: large.* Cheapest route to PUCT because the portfolio iterator already supplies
  the candidate set. This is also the **durable fix for genuinely-wide R-allocation** (cf. §1a — NOT raising
  `MaxChildren`).
- **O3 — Distillation bootstrap.** Periodically run the current net at high sims (10k–50k) on a position
  batch and train the value net to predict the **deep-search backed-up value** (MSE target) — distilling
  deep-search judgement into the static eval so shallow self-play yields cleaner labels. *Effort:
  medium-large + extra deep-search compute; risks baking in the deep search's residual biases.* **Invoke
  only if O2's deep-label diagnostic (§8.5) confirms shallow search is the binding bottleneck.**

**STOP (A9):** if the **O6 escalation ALSO flatlines** with a clean §4 triage, conclude the **action space /
approach** is the limit — stop the value-only line; do not re-spin.

---

## Run prerequisites (status as of 2026-06-11 — mostly RESOLVED)

These MUST be satisfied before `eval/run_iteration.ps1 -K 1` is run for real. Stage 0
(`eval/preflight_config.py`) machine-checks most of them.

1. **N / τ / ε — RESOLVED (FROZEN 2026-06-11, regime v2).** The `calibrate_n.py` sweep ended as
   *screening only* (and the Jun-4→9 crippled-iterator window invalidated the earlier picks); the owner
   froze the tuple by judgment: **N=1000, τ=0.7 (probe-driven, `eval/tau_probe_n1000.json`), K=12,
   ε=0, EpsilonLate=0.05** in `eval/campaign_frozen.json` (regime v2 — see §1b; supersedes the
   same-day v1 K=999). A **32-game re-screen at the regime-v2 tuple passes all gates**
   (`eval/n1000_rescreen_k12.json`; v1 record: `eval/n1000_rescreen.json`). Preflight asserts
   `config.txt` matches; a `-N` differing from `frozen_N` throws.

2. **iter-0 anchor = v221 (RESOLVED 2026-06-07 — NOT a random net).** `RL_Eval_iter0.WeightsFile` =
   `neural_weights_mixed_v221.bin`, the pre-RL supervised net (= the parent), run on the **SAME** IG-optional
   config + **SAME** eval budget as the candidate. A **random-init** anchor was explicitly **REJECTED** —
   beating a random net is trivial/vacuous; and RL warm-starts from v221 (§1), so v221 is the correct
   "where the widened-axis net started" reference. CAVEAT: at iter-1, `d_rl` (candidate vs v221) coincides
   with the verdict comparison (candidate vs parent = v221); from iter-2 on they diverge — `d_rl` measures
   *cumulative* gain vs the fixed v221 anchor, the verdict measures *marginal* standing vs the parent.

3. **2016 MasterBot baseline — RESOLVED (F-08, permanent home).** The genuine 721,920-byte 2016 binary
   lives at `c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe` (sha256
   `0A70B198342B998650D98CF2F1CF74E9C478D50F4E9918FB49E09286B64A41FC`) — outside both repos and the Steam
   dir, so the `use_dsnn.txt` contamination guard passes structurally. The steam anchor was **rewired**:
   candidate = DaveAI + the matchup runner's injected `RL_Eval` block (`--candidate-weights`) vs the
   MasterBot via `--steam-exe-b`; **live 2-game verified**. `run_eval.py` soft-skips the steam yardstick if
   the binary is absent; stage-0 preflight hard-fails on it (a campaign run must not silently lose its
   strength yardstick).

4. **`eval/calib_states/` + `eval/ig_battery/` — POPULATED** (41 curated states incl. `ktink_t9` and the
   multi-replay batteries; defaults of `action_coverage.py` / `tactical_suite.py`).

5. **Training data — EXISTS.** `training/data/human_1800_v2.h5` = the **rehearsal** mix (`--human-file`)
   and game-length baseline; `training/data/human_val_1700_v2.h5` = the **HELD-OUT val set** (M-03:
   `--val-file` must be this, never the rehearsal file). Preflight checks both exist.

6. **`eval/run_eval.py::main()` is COMPLETE (RESOLVED 2026-06-07; verdict semantics replaced the GO gate
   2026-06-10).** `build_manifest()` runs the real per-anchor wiring: active provenance pre-flight, block
   flips (via the `ANCHOR_BLOCKS` registry), C++ tournaments, HTML statsTable parse, Wilson CIs,
   engine-stderr load confirmation per anchor, the seat-independent steam anchor (A7/A8), incremental
   atomic manifest writes, and the §3 verdict. Unit-tested (`eval/tests/test_run_eval_main.py`).

7. **Stage-1 self-play blocks (regime-v2 mix).** TWO blocks, both `Threads:8`, run in one engine
   launch: `RL_SelfPlay_General` (`rounds:43`, NO forcing — ⅔) + `RL_Step2_Smoke` (`rounds:21`,
   `ForcedCards:["Hotel"]` — ⅓). For a longer production iteration scale BOTH `rounds` together
   (keep the ⅔:⅓ ratio AND update the frozen `selfplay_mix` — preflight enforces they match) — N
   itself stays frozen.

---

## Throughput (measure on the deferred iter-0 run — spec §8)

We can only record what the smokes already produced (do **not** run a new campaign to fill this). Before
sizing the ~£400 AWS spend, the **iter-0 run** must measure each row.

What we know from smokes already run:
- The **N=100 self-play smoke** (`RL_SelfPlay_N100`, `RL_Cal_N100`) produced **~4 games quickly** (then
  Threads:1; the whole cal family is **Threads:8** since 2026-06-11 — matched sets + ~5-8× wall-clock,
  see `eval/calibrate_n.py` THREADING and §1d).
- The **N=1000 32-game re-screen** at the frozen tuple completed at **Threads:8** (`eval/n1000_rescreen.json`).
- Self-play is **CPU-bound**. The dave engine is **x64**, so the old x86 4-thread OOM cap does not apply;
  Threads:8 export was audit-verified clean.

| Metric | Value | How measured | Status |
|---|---|---|---|
| games / hour @ chosen N | _TBD_ | wall-clock over a fixed-rounds self-play block | **measure on iter-0** |
| NN-evals / sec | _TBD_ | responder eval counter over the self-play run | **measure on iter-0** |
| CPU utilisation | _TBD_ | OS monitor during self-play (Threads × instances) | **measure on iter-0** |
| shard write throughput | _TBD_ | bytes/sec of `selfplay_*.jsonl` | **measure on iter-0** |
| eval games / hour | _TBD_ | wall-clock over an `RL_Eval_*` tournament block at the 7 s budget | **measure on iter-0** |

Only once these are filled should the £400 be sized **against measured throughput, not assumption** (§8).
