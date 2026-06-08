# RL Self-Play Campaign — Frozen Config + Decision Rules

> **Spec:** `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` (§7, §9, §12, §14 are folded in below).
> **Scope:** the IG-optional (Infusion-Grid click-count) axis-1 proof-of-life campaign.
> **Status:** machinery BUILT + validated; the multi-hour self-play / train / eval run is **DEFERRED to the user** (see "Run prerequisites").

This document is the campaign contract. **Any change to the frozen HP tuple below = a NEW campaign**
(re-anchor: regenerate the wide-untrained iter-0 net and re-baseline). The driver that wires the
one-iteration loop is `eval/run_iteration.ps1`; the per-iteration dashboard is `eval/render_dashboard.py`.

---

## 1. Frozen HP tuple (spec §10 item 10, §11)

Treat the whole tuple as the campaign identity. Two entries (`N`, `ε`) are **placeholders pending the
calibration sweep** (`eval/calibrate_n.py`, a deferred user run) and MUST be set before iter-1.

| HP | Symbol | Value | Notes |
|---|---|---|---|
| Self-play traversals | `N` (MaxTraversals) | **512 (PLACEHOLDER)** | Set from `eval/calibrate_n.py`'s `recommended_N` (smallest N passing the non-degeneracy check) before iter-1. Until the sweep runs, 512 stands. Lives on `RL_SelfPlay` (+ the per-N `RL_SelfPlay_N*` blocks). |
| Temperature | `τ` (TemperatureTau) | 1.0 | self-play sampler only; eval is pure argmax. |
| Temperature horizon | `K` (TemperatureK) | 6 | sampler fires only for `turnNumber < K`; argmax after K (see A2). |
| ε-uniform root noise | `ε` (EpsilonUniform) | **0.25 (PLACEHOLDER)** | A5: sweep ε analytically in calibration; set from the effective-entropy curve before freezing. |
| Replay window | `W` | 5 | sliding self-play buffer (`--replay-window 5`). |
| Rehearsal fraction | — | start **0.30** → floor **0.10**, decay **0.07/iter** | human-only rehearsal mix (`rl_data.rehearsal_fraction_for_iter`). |
| Promotion gate margin | — | candidate-vs-current **CI-lower > 0.50** | group-sequential per A3 (`sequential_gate`, looks 128→256→512). |
| Rollback margin | `Y` | **0.03** | on the **GENERAL** pool only (no material regression). |
| Eval budget | — | **MaxTraversals 100000 / TimeLimit 7000 (7 s)** | **deployment-representative; DECOUPLED from self-play N** — A1. Candidate AND every anchor run at this budget. |
| Pre-registered effect size | `E` | **+5 pp** (≈ **600 games / anchor**) | smallest IG-driven win-rate gain worth AWS spend; sizes eval N at p<0.05. |
| Root child cap | `MaxChildren` | **40 — FROZEN, observe-only** | see §1a. |
| SWA | — | start-epoch **3**, epochs **6**, lr **1e-5** | RL fine-tune schedule (frozen per campaign). |

### 1a. `MaxChildren = 40` — FROZEN (observe-only) rationale

`MaxChildren` caps the number of **root children** the search expands. Raising it spreads the **fixed**
search budget (`N` traversals) thinner — breadth competes with depth — so it is *coupled to N* and stays
**frozen** for this IG-only campaign. On the IG axis the iterator emits ~8 root children, far below 40,
so the cap **never binds** (`root_truncated` should be ~never true).

The engine now emits `root_children` / `root_truncated` telemetry (responder field `aitruncated`; the V2
exporter stamps both per record). This campaign treats them as **OBSERVE-only**: we *confirm* `root_truncated`
is ~never true; we do **not** tune `MaxChildren`. The durable fix for genuinely-wide R-allocation
(many competing portfolio candidates) is a **candidate policy head + PUCT** (§14, O6), **not** a larger
`MaxChildren`.

---

## 2. External-review addenda (A1, A2, A6, A9) — folded in

### A1 — Decouple EVAL budget from self-play N; fix the regression gate

`RL_Eval` / `RL_Eval_iter0` run at the **deployment budget** (`MaxTraversals:100000`, `TimeLimit:7000`),
**NOT** the self-play `N`. The regression delta `d_reg` is computed from **`RL_Eval_iter0_general`**
(net_k vs the pre-RL/wide-untrained net, **SAME config + SAME budget**), **NOT** from the narrow
`DSNN_Mixed35_5var` anchor (a *different config* at 100k). Using the narrow anchor for `d_reg` would let a
pure budget/config gap trip `d_reg < −Y` and wrongly **block a GO**. The narrow and STEAMAI anchors are
**trajectory yardsticks only** — never gate on them.

### A2 — Exploration is gated to the opening, but IG recurs all game

The sampler (`τ`, `ε`) only fires for `turnNumber < K`; after K it is pure argmax. With the opening book on,
the effective IG-exploration window ≈ **turns 3–6**, yet **IG is a per-turn decision that recurs all game**.
The engine has an optional **`EpsilonLate ≈ 0.05`** — a persistent small late-ε for `turnNumber ≥ K`
(default 0 / off). **If axis-1 comes back flat, enable `EpsilonLate` FIRST**, before the §14 escalation.
This is the **first escalation lever** (see §6).

### A6 — Perspective round-trip (REQUIRED pre-iter-1 check)

Beyond `test_labels.py` (Python label scale) + the export-parity gate (PyTorch↔C++ forward value), add:
1. **Asymmetric-outcome parity check** — a parity assertion on ≥1 shared state with a **KNOWN ASYMMETRIC
   outcome** (e.g. P0 won, but active player that turn = P1) so a perspective **inversion** surfaces as a
   value mismatch rather than silently cancelling on symmetric positions.
2. **End-to-end `query_move.js` assertion** — a clearly-winning continuation must score **higher** through
   the loop's own deploy path (`query_move.js` → responder → NeuralNet eval).

Verify `outcome_p0` (the C++ exporter's **P0-perspective** label) matches (a) the JS human-corpus convention
AND (b) how `Eval.cpp` / `NeuralNet` interpret the net output for `maxPlayer`. **This round-trip is a
REQUIRED pre-iter-1 gate.**

### A9 — Pre-registered STOP condition

The kill-criteria (§3) always route to **escalate**, never **abandon**. Pre-register the evidence that
justifies **STOPPING**: if the **O6 candidate-policy-head + PUCT escalation ALSO comes back flat** (after a
clean false-negative triage), that is the **action-space / approach** being the limit — not measurement —
and the value-only-RL-on-this-axis line is **stopped**, not re-spun.

Cost note: the **local false-positive cost is more than £400** — a wrong "GO" buys the whole AWS campaign's
engineering + monitoring + opportunity cost. That asymmetry is why the gate is conservative and the
regression guard (A1) is wired carefully.

---

## 3. Local go / no-go DECISION RULE (spec §12, verbatim)

```
pre-register: effect_size E (pp), eval N per anchor (sized to E at p<0.05), regression tol Y.
run IG-optional campaign for up to MAX_ITERS, gated promotion (§5).
for each iteration:
    d_rl   = winrate(net_k) - winrate(wide-untrained iter-0)   # RL's contribution
    d_reg  = winrate(net_k, general) - winrate(baseline, general)
    if  CI_lower(d_rl) > 0  AND  d_rl >= E  AND  d_reg >= -Y:
        GO (spend AWS) — RL demonstrably improved the net on the widened axis.
if MAX_ITERS reached with no GO:
    run false-negative triage (§9).
    if triage clean and still flat:  conclude "local setup cannot measure it" (NOT "RL fails").
        -> raise N, widen further, or invoke the policy-head fallback (§13-C6) before spending.
    else: fix the flagged issue and re-run (new campaign).
```

**The decision is a HUMAN call** on the manifest + dashboard. The driver computes and prints the inputs;
it does not auto-promote.

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
3. **Labels pass inversion / scale tests?** → `test_labels.py` + A6 asymmetric-outcome parity.
4. **Did training change predictions on self-play positions?** (a static net → no learning).
5. **Does the exported `.bin` match PyTorch?** → the export-parity gate (`tools/parity/dump_value_batch.py`,
   worst |Δ| < 1e-3).
6. **Did eval load the intended net?** → `candidate_net_sha256` in the manifest; the `run_eval.py`
   contamination asserts (no `PRISMATA_FORCE_DSNN`, no `use_dsnn.txt`, `.ORIG` present).
7. **Was eval statistically powered?** → eval N sized to `E` at p<0.05 (≈600 games/anchor at +5pp).
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
source JSON], **net-hash**). A/B a heuristic fix with the *fixed* net, then merge + re-anchor (re-run iter-0
wide-untrained). **RL iterations change ONLY the net** on a **resolved-config-hash-pinned** frozen config.

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

- **Lever 0 (A2) — enable `EpsilonLate ≈ 0.05`.** Persistent small late-ε for `turnNumber ≥ K` so the
  per-turn IG decision keeps getting explored past the opening window. **Try this FIRST** (cheapest; just a
  config flag; new campaign since it changes the sampler tuple).
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

## Run prerequisites (deferred)

These MUST be satisfied before `eval/run_iteration.ps1 -K 1` is run for real. None are executed here.

1. **`recommended_N` + ε from calibration.** Run `eval/calibrate_n.py` (the deferred N-sweep) → read
   `recommended_N` (smallest N passing the non-degeneracy check) and the ε from the effective-entropy curve
   (A5) → set `MaxTraversals` on `RL_SelfPlay` (and the `-N` arg to the driver) and `EpsilonUniform` on the
   self-play players. Until then the placeholders (N=512, ε=0.25) stand.

2. **iter-0 anchor = v221 (RESOLVED 2026-06-07 — NOT a random net).** `RL_Eval_iter0.WeightsFile` =
   `neural_weights_mixed_v221.bin`, the pre-RL supervised net, run on the **SAME** IG-optional config + **SAME**
   eval budget as the candidate. This IS the intended A1 regression-gate reference: `d_rl` then isolates RL's
   **marginal** contribution over the supervised starting point (a clean controlled A/B). A **random-init**
   anchor was explicitly **REJECTED** — beating a random net is trivial, so it would make the GO gate fire
   *vacuously*; and RL inits from v221 (§1), not from scratch, so v221 is the correct "where the widened-axis
   net started" reference. Therefore `init_random_deepsets.py` is **NOT needed** and the config is already
   correct (dave `eca0469`). CAVEAT: at iter-1, `d_rl` (candidate vs v221) coincides with the promotion gate
   (candidate vs parent = v221); from iter-2 on they diverge — `d_rl` measures *cumulative* gain vs the fixed
   v221 anchor, the promotion gate measures *marginal* gain vs the previous iteration.

3. **STEAMAI baseline `PrismataAI.exe.ORIG` on disk.** `run_eval.py` asserts it exists (the contamination
   guard — without it the eval would silently diff against our DSNN swap-in). It must be the preserved
   721,920-byte 2016 MasterBot binary, not the swap-in.

4. **Populate `eval/calib_states/` (~20 states) + an IG battery** (`eval/ig_battery/`, default of
   `action_coverage.py` / `tactical_suite.py`). `eval/calib_states/` is currently **empty**;
   `action_coverage.argmax_ig_rate` and `tactical_suite` need ~20 curated states (incl. an
   untapped-IG + red state where IG self-sac is genuinely legal — the T9 dump is IG-illegal:
   tapped + 0 red).

5. **`human_1800_v2.h5`** — EXISTS at `training/data/human_1800_v2.h5`; it is the **rehearsal** mix
   (`--human-file`) AND the game-length baseline file.

6. **`eval/run_eval.py::main()` is COMPLETE (RESOLVED 2026-06-07 — this prereq is retired).** An earlier
   draft called it a Task-7 skeleton writing `anchors:{}`/`pools:{}`; that is no longer true. `build_manifest()`
   runs the real per-anchor wiring: it flips the `RL_Eval_iter0_*` / `RL_Eval_narrow_*` blocks to `run:true`,
   runs the C++ tournament (`run_cpp_tournament`), parses the candidate's W/L/D (`parse_tournament_stdout`),
   computes Wilson CIs per anchor, runs the STEAMAI anchor seat-independently (A7/A8), flips the blocks back
   (in a `finally`), and computes the §3 GO inputs (`d_rl` forced / `d_reg` general). It is unit-tested
   (`eval/tests/test_run_eval_main.py`, 7 tests). No work remains here.

7. **Stage-1 self-play `rounds`.** `run_iteration.ps1` Stage 1 uses the small smoke block
   (`RL_Step2_Smoke`, `rounds:4`); for a real iteration bump the self-play rounds substantially
   (the ps1 already flags this near the Stage-1 comment) and use the calibrated N (item 1).

---

## Throughput (measure on the deferred iter-0 run — spec §8)

We can only record what the smokes already produced (do **not** run a new campaign to fill this). Before
sizing the ~£400 AWS spend, the **iter-0 run** must measure each row.

What we know from smokes already run:
- The **N=100 self-play smoke** (`RL_SelfPlay_N100`, `RL_Cal_N100`) produced **~4 games quickly** (Threads:1).
- Self-play is **CPU-bound**; x86 OOM caps each process at **4 threads** (`/LARGEADDRESSAWARE` 4GB).

| Metric | Value | How measured | Status |
|---|---|---|---|
| games / hour @ chosen N | _TBD_ | wall-clock over a fixed-rounds self-play block | **measure on iter-0** |
| NN-evals / sec | _TBD_ | responder eval counter over the self-play run | **measure on iter-0** |
| CPU utilisation | _TBD_ | OS monitor during self-play (Threads × instances) | **measure on iter-0** |
| shard write throughput | _TBD_ | bytes/sec of `selfplay_*.jsonl` | **measure on iter-0** |
| eval games / hour | _TBD_ | wall-clock over an `RL_Eval_*` tournament block at the 7 s budget | **measure on iter-0** |

Only once these are filled should the £400 be sized **against measured throughput, not assumption** (§8).
