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
| Self-play traversals | `N` (MaxTraversals) | **1000 — FROZEN by judgment** | Owner decision on the screen-only calibration data (the `calibrate_n.py` sweeps were screening, not proof; the Jun-4→9 crippled-iterator window invalidated the earlier N=256/512 picks). A **32-game re-screen at the shipped tuple passes ALL gates** (`eval/n1000_rescreen.json`: mean_len 35.19 in [16.00, 44.97], p0_wr 0.375 in [0.35, 0.65], 51/1126 records with IG clicks). Lives on `RL_SelfPlay` (+ the per-N `RL_SelfPlay_N*` blocks). |
| Temperature | `τ` (TemperatureTau) | **0.7** | self-play sampler only; eval is pure argmax. Set by the pre-agreed probe rule (`eval/tau_probe_n1000.json`): at N=1000/c=0.3 the root visit distributions are **near-uniform** (median top-share 0.141 < 0.20 AND median normalized entropy 0.984 > 0.90) → τ=0.7 sharpens them. |
| Temperature horizon | `K` (TemperatureK) | **999** | **whole-game τ-sampling** — the sampler fires for every turn, not an opening window (supersedes the old K=6; see A2). |
| ε-uniform root noise | `ε` (EpsilonUniform) | **0** | removed as uncalibrated (owner decision); whole-game τ-sampling carries the exploration. `EpsilonLate` is **absent** from the config (key-absent convention, preflight-enforced). |
| UCT constant | `c` (UCTConstant) | **0.3** | the tuned cValue, on every RL player AND injected by `js_engine/query_move.js` by default (M-06 fix — omitting it silently regressed to the engine default 2.0, the worst measured c). |
| Self-play threads | — | **Threads:8** | `RL_Step2_Smoke` block; the dave engine is x64 and Threads:8 export was audit-verified clean. |
| Replay window | `W` | 5 | sliding self-play buffer (`--replay-window 5`). |
| Rehearsal fraction | — | start **0.30** → floor **0.10**, decay **0.07/iter** | human-only rehearsal mix (`rl_data.rehearsal_fraction_for_iter`). Epoch length = `ceil(sp_total/(1-frac))` draws ≈ one pass over the self-play window, NOT the rehearsal corpus (M-04 fix; LR schedule sized to match). |
| Verdict (was: promotion gate) | — | **REJECT / REVIEW / INCOMPLETE** | see §3 — rule-out-harm on the general pool; **nothing auto-promotes**. The old group-sequential CI-lower>0.50 gate was deleted 2026-06-10. |
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
children); we do **not** tune `MaxChildren`. The durable fix for genuinely-wide R-allocation
(many competing portfolio candidates) is a **candidate policy head + PUCT** (§14, O6), **not** a larger
`MaxChildren`.

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

### A2 — IG recurs all game → whole-game sampling (RESOLVED in the frozen tuple)

The sampler (`τ`, `ε`) only fires for `turnNumber < K`. The original concern: with K=6 and the opening
book on, the effective IG-exploration window was ≈ turns 3–6, yet **IG is a per-turn decision that recurs
all game**. The frozen tuple resolves this directly: **`TemperatureK = 999` = whole-game τ-sampling** —
the τ=0.7 sampler fires every turn, so the per-turn IG decision keeps getting explored without an extra
noise source. The engine's optional **`EpsilonLate`** (persistent small late-ε for `turnNumber ≥ K`)
remains implemented but **off / key-absent** (preflight-enforced); it is retained as an escalation lever
(§6) should whole-game τ-sampling prove insufficient.

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

Cost note: the **local false-positive cost is more than £400** — a wrong "spend AWS" call buys the whole
AWS campaign's engineering + monitoring + opportunity cost. That asymmetry is why the verdict (§3) is
conservative (rule-out-harm + human judgment, never auto-promote) and the regression measurement (A1) is
wired carefully.

---

## 3. Per-iteration VERDICT (2026-06-10 — replaces the spec-§12 GO rule)

The spec's original GO rule (`CI_lower(d_rl) > 0 AND d_rl >= E AND d_reg >= -Y`) was **deleted as
statistically incoherent at the configured sample size**: at 128 games/anchor, an observed +5 pp needed
~58.7% to clear the CI condition, so P(GO | true +5 pp) ≈ 13% — the gate could essentially never fire on
the effect it was pre-registered for. "Prove improvement" is replaced by **"rule out harm" + human
judgment** (`run_eval.py::compute_verdict`, `VERDICT_RULE`):

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
3. **Labels pass inversion / scale tests?** → `test_labels.py` + A6 asymmetric-outcome parity.
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
7. **Was eval statistically powered for the question asked?** → the verdict is rule-out-harm, which 128
   games CAN answer; *proving* a +5 pp gain would need ≈600 games/anchor at p<0.05 — that remains the bar
   for the human AWS-spend judgment, not an automated gate.
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

- **Lever 0 (A2) — enable `EpsilonLate ≈ 0.05`.** Persistent small uniform late-ε on top of the sampler.
  With the frozen tuple already doing whole-game τ-sampling (K=999), this lever now adds *uniform* noise
  rather than extending the window — still **try it FIRST** if axis-1 is flat (cheapest; just a config
  flag; new campaign since it changes the sampler tuple, and the preflight's key-absent check must be
  updated deliberately).
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

1. **N / τ / ε — RESOLVED (FROZEN 2026-06-11).** The `calibrate_n.py` sweep ended as *screening only*
   (and the Jun-4→9 crippled-iterator window invalidated the earlier picks); the owner froze the tuple by
   judgment: **N=1000, τ=0.7 (probe-driven, `eval/tau_probe_n1000.json`), K=999, ε=0** in
   `eval/campaign_frozen.json`. A **32-game re-screen at the shipped tuple passes all gates**
   (`eval/n1000_rescreen.json`). Preflight asserts `config.txt` matches; a `-N` differing from `frozen_N`
   throws.

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

7. **Stage-1 self-play block.** `RL_Step2_Smoke` is now `rounds:64, Threads:8, ForcedCards:["Hotel"]`;
   for a longer production iteration bump `rounds` (the ps1 flags this near the Stage-1 comment) — N
   itself stays frozen.

---

## Throughput (measure on the deferred iter-0 run — spec §8)

We can only record what the smokes already produced (do **not** run a new campaign to fill this). Before
sizing the ~£400 AWS spend, the **iter-0 run** must measure each row.

What we know from smokes already run:
- The **N=100 self-play smoke** (`RL_SelfPlay_N100`, `RL_Cal_N100`) produced **~4 games quickly** (Threads:1).
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
