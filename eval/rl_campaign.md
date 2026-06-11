# RL Self-Play Campaign — Frozen Config + Decision Rules

> **Spec:** `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` (§7, §9, §12, §14 are folded in below).
> **Scope:** the IG-optional (Infusion-Grid click-count) axis-1 proof-of-life campaign.
> **Status:** machinery BUILT + audited (Jun-9/10 audits + fixes landed Jun-10/11); tuple **FROZEN 2026-06-11**
> in `eval/campaign_frozen.json`; the multi-hour self-play / train / eval run is **DEFERRED to the user**
> (see "Run prerequisites" — now mostly RESOLVED).

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
| Temperature horizon | `K` (TemperatureK) | **12 (regime v2, 2026-06-11)** | τ-sampling fires for turns **0–11 only** — past the opening book and through the early-mid region where the MB-flavour data bias lives (supersedes the same-day v1 K=999 whole-game sampling — see the regime-v2 note below). |
| ε-uniform root noise | `ε` (EpsilonUniform) / **`EpsilonLate`** | **0** / **0.05** | EpsilonUniform stays 0 in the opening window (τ carries the early exploration). **`EpsilonLate=0.05`**: turns ≥12 are argmax with a 5% uniform-child chance (~1.1 mild deviations/game a priori; measured **0.69/game** at the 32-game re-screen — 23% of late roots are single-child and uniform picks can land on argmax) — present in config as a JSON double, preflight-enforced EQUAL to frozen (absent key = 0.0 = FAIL). |
| UCT constant | `c` (UCTConstant) | **0.3** | the tuned cValue, on every RL player AND injected by `js_engine/query_move.js` by default (M-06 fix — omitting it silently regressed to the engine default 2.0, the worst measured c). |
| Self-play threads | — | **Threads:8** | BOTH self-play blocks (`RL_Step2_Smoke` + `RL_SelfPlay_General`); the dave engine is x64 and Threads:8 export was audit-verified clean. |
| Self-play data mix | `selfplay_mix` | **⅔ general + ⅓ forced-Hotel** | regime v2: `RL_SelfPlay_General` (rounds:43 → ~86 games, NO ForcedCards — the broadened general-improvement goal) + `RL_Step2_Smoke` (rounds:21 → ~42 games, ForcedCards `["Hotel"]` — keeps IG-decision density). Separate export dirs REQUIRED (per-Tournament-instance export counter). Preflight-enforced from the frozen `selfplay_mix`. |
| Replay window | `W` | 5 | sliding self-play buffer (`--replay-window 5`). |
| Rehearsal fraction | — | start **0.30** → floor **0.10**, decay **0.07/iter** | human-only rehearsal mix (`rl_data.rehearsal_fraction_for_iter`). Epoch length = `ceil(sp_total/(1-frac))` draws ≈ one pass over the self-play window, NOT the rehearsal corpus (M-04 fix; LR schedule sized to match). |
| Verdict (was: promotion gate) | — | **REJECT / REVIEW / INCOMPLETE** | see §3 — detect-proven-harm on the general pool; **nothing auto-promotes**. The old group-sequential CI-lower>0.50 gate was deleted 2026-06-10. |
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

### 1b. Label-quality & exploration regime (v2, 2026-06-11)

The same-day **v1** regime (K=999 whole-game τ-sampling) was replaced after the verification sweep
measured **40–46% non-argmax moves** and **significantly longer games** under it: late noise corrupts
the outcome labels of **every earlier record** in the game, while early noise buys position coverage
cheaply (divergent trajectories whose labels stay truthful under near-greedy continuation). **v2 =
early-noise/late-precision**: τ=0.7 sampling for turns 0–11 (`TemperatureK=12`), then argmax with a 5%
uniform-child chance (`EpsilonLate=0.05`, ≈1.1 mild deviations/game a priori; measured **0.69/game** at
the 32-game re-screen, `eval/n1000_rescreen_k12.json` — 23% of late roots are single-child and uniform
picks can land on argmax) so
recurring decisions (e.g. the per-turn IG click) still get occasional exploration without whole-game
label corruption.

**Residual risk (accepted):** a value-only net gets **no counterfactual signal on unplayed branches** —
with the late game near-greedy, alternatives the argmax never picks are never labelled; the ~1.1 a-priori
(0.69 measured) late deviations/game is the deliberate compromise between that blindness and label corruption.
**WATCH at iter-1:** `d_rl` (forced-pool delta) **and the sampled-move fraction** for turns ≥12 from the
`sampled_idx`/`argmax_idx` stamps (expected ≈5% of late moves; re-screen observed value in
`eval/n1000_rescreen_k12.json`).

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

### A2 — IG recurs all game → late-ε keeps it explored (RESOLVED, regime v2)

The sampler (`τ`, `ε`) only fires for `turnNumber < K`. The original concern: with K=6 and the opening
book on, the effective IG-exploration window was ≈ turns 3–6, yet **IG is a per-turn decision that recurs
all game**. The v1 answer (K=999 whole-game τ-sampling) over-corrected — 40–46% non-argmax moves
corrupted outcome labels (§1b). **Regime v2 resolves A2 with `EpsilonLate=0.05`**: for `turnNumber ≥ K`
(=12) the root stays argmax but a persistent 5% uniform-child chance gives the recurring per-turn IG
decision exploration all game at ~1.1 mild deviations/game a priori (measured 0.69/game at the 32-game
re-screen — 23% of late roots are single-child and uniform picks can land on argmax), while τ=0.7 covers
turns 0–11.

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
(`tools/parity/dump_value_batch.py`): it compares `value = 2·sigmoid(logit) − 1` (P0-perspective)
between C++ inference and PyTorch on ~1000 real states at tol 1e-3, so a C++-side perspective flip
reads `value_cpp ≈ −value_torch` and blows the gate on any non-neutral state. Residual seam parity
does NOT cover: the single maxPlayer negation downstream of the scalar (dave-master
`NeuralNet.cpp` `evaluateValue` tail: `if (maxPlayer != Player_One) value = -value;` plus
`UCTSearch.cpp`'s `(nnValue+1)/2` consumption) — one code-visible negation, unchanged since the
port audit. The original A6 item-2 (end-to-end `query_move.js` winning-continuation assertion)
would be the durable cover for that seam and remains **not built**.

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

**The promotion decision is a HUMAN call** on the manifest + dashboard. The driver computes and prints
the inputs; **nothing auto-promotes** (a REVIEW verdict is an invitation to judge, not a promotion).

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
7. **Was eval statistically powered for the question asked?** → the verdict is detect-proven-harm — at
   128 games REJECT reliably fires only for ~−10pp-and-worse regressions (§3); *proving* a +5 pp gain
   would need ≈600 games/anchor at p<0.05 — that remains the bar for the human AWS-spend judgment, not
   an automated gate.
8. **Was self-play non-degenerate at N?** → the calibrate_n non-degeneracy check; game-length / ply stats.
9. **Did rehearsal overwhelm the RL signal?** → rehearsal fraction schedule (start 0.30 → floor 0.10).
10. **Target-up but general-down (overfit, not no-learning)?** → compare forced-pool `d_rl` vs general-pool
    `d_reg`.

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

- **Lever 0 (A2) — raise `EpsilonLate` / widen the τ window.** Regime v2 already runs
  `EpsilonLate=0.05` + K=12, so this lever is now *re-tuning* (e.g. ε→0.10, or K→16) rather than
  enabling — still **try it FIRST** if axis-1 is flat (cheapest; just config values; new campaign since
  it changes the sampler tuple, and `campaign_frozen.json` + the preflight must be updated together,
  deliberately — mind §1b's label-corruption tradeoff when raising late noise).
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
