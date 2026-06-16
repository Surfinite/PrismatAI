# RL Iteration Runbook — one loop, at a glance (regime v4, proof-of-life, 2026-06-14)

> Reference card for what `eval/run_iteration.ps1 -K <k>` does, what must be true before it starts,
> and what happens between iterations. Tags: **[core]** = the loop doesn't work without it ·
> **[gate]** = cheap check that aborts a bad run · **[telemetry]** = recorded, never aborts.
> The campaign contract (frozen tuple, collapse/abort policy, anchors) is `eval/rl_campaign.md`;
> the eval harness internals are `eval/README.md`; the per-iteration human record + accepted-
> limitations register is `eval/campaign_log.md`. Design spec for the reframe:
> `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`.
>
> **v4 = SYSTEMS milestone (proof-of-life): validate the loop runs end-to-end and produces a
> non-degenerate net. NO axis under test.** (The IG axis is archived as a worked example in
> `rl_campaign.md`.)

## Pre-flight (before ANY iteration) — ENFORCED by `eval/preflight_config.py` (stage 0)

The driver runs this automatically and aborts on any FAIL; also runnable standalone. It never
rewrites `config.txt` — drift must be reconciled deliberately (edit `campaign_frozen.json` AND
`config.txt` together; parent changes go through `eval/promote_candidate.ps1` ONLY).
**18 checks** (a full run, with the slow correctness gates; `--skip-slow-gates` drops to 17). The
authoritative ordered list is `run_checks()` in `preflight_config.py`:

| Check | What it asserts | Why |
|---|---|---|
| `json_bom` | config is strict JSON, no BOM (first byte `{`) | BOM makes the C++ parser skip the file silently |
| `use_dsnn_sentinel` | no `use_dsnn.txt` next to the engine exes | the Steam drop-in sentinel silently swaps the net + think params on every protocol-path call (stage 8 runs through it) |
| `run_true` | every Benchmarks block `run:false` at rest | a stray `run:true` runs an unintended tournament on launch |
| `iterator_shape` | the IGsubset root iterator's exact structure **AND** the **`HardIterator_5var_NoIG` interior** (`[[], ['V5_CS_NoIG'], [], []]`) wired as each candidate-side player's `MoveIterator` | the crippled-iterator guard + v4: the interior must never auto-fire IG below root |
| `book_sizes` | `LiveOpeningBook2`==50, `DefaultOpeningBook`==4 | book truncation/drift |
| `reference_graph` | every declared reference resolves (incl. `WeightsFile` on disk) | dangling names |
| `selfplay_replays` | the self-play block carries the expected `saveReplays` dir (`asset/replays/rl_selfplay_general`) | the per-iteration replay archive contract (stage 1.5 throws only AFTER self-play otherwise) |
| `frozen_tuple` | `RL_SelfPlay` tuple == frozen (N/τ/K/εUniform/**EpsilonLate=0.05**/**EpsilonIG=0**/c) **AND** the ONE self-play block (`RL_SelfPlay_General`) matches frozen `selfplay_rounds`/`selfplay_seed_base`/`selfplay_threads`, **NO `ForcedCards`**, `run:false` at rest | the tuple IS the campaign identity; the driver sets Seed=base+K transiently and must restore the base; an absent EpsilonLate/EpsilonIG key = 0.0 (so frozen 0.05 + absent FAILS) |
| `selfplay_player` (M2) | the self-play block references `RL_SelfPlay` in **both** group slots, `RL_SelfPlay.SelfPlaySampling==true`, and its `RootMoveIterator` is the IG-subset root | the frozen-tuple knobs are meaningless if a different player generates the data, or sampling is off, or the wrong action space fires at root |
| `parent_repin` | the **TWO** parent pins (`RL_Eval`, `RL_SelfPlay`) == frozen `parent_bin` | a killed run or forgotten repoint must not silently change the comparison or the generator |
| `origin_pin` | `RL_Eval_origin.WeightsFile` == frozen `origin_bin` (v221, PERMANENT) | the origin anchor is NEVER repointed — it carries the relative-drift / collapse measurement |
| `anchor_blocks` | `RL_PoL_origin` / `RL_PoL_masterbot` rounds/Seed/Threads == frozen | eval volume is campaign identity |
| `eval_budget` | TimeLimit/MaxTraversals/UCTConstant on `RL_Eval` + `RL_Eval_origin` == frozen `eval_budget` | A1: the deployment budget was previously enforced by nothing |
| `unit_index` | `unit_index.json` exists + carries the canonical 116 units | a missing index silently lobotomizes every NeuralNet player (engine also FATALs on mappedTypes==0) |
| `existences` | frozen `parent_pt` + `rehearsal_file` (elite) + `tripwire_val_file` exist | warm-start, stage 3, 4.5 depend on them |
| `parent_sha` | sha256(on-disk parent bin) == frozen `parent_bin_sha256` | the parent is CONTENT-pinned — catches a same-K re-export clobber and name-consistent-but-wrong promotions |
| `engine_sha` | both engine exes sha256-match the frozen `engine_*_exe_sha256` pins | an unrecorded rebuild can silently flip the maxPlayer value SIGN or a shared-C++ feature (fast; always runs when frozen loaded) |
| `correctness_gates` | auto-runs `a6_orientation_check.py` (value sign-flip guard) + `test_three_way_feature_parity.py` (JS extractor == C++ exporter == C++ inference) as subprocesses | the two catastrophic-but-silent value failures, previously caught only by MANUAL tests; SLOW (~30–60s) — skip with `--skip-slow-gates` (the fast `engine_sha` pin still runs) |

## The stages (0–8, plus 1.5 / 4.5 / 4.6 — there is NO stage 6 in v4)

**0 — Structural preflight [gate]** — the 18-check table above; also rejects `-N` ≠ `frozen_N` and
`-Window` ≠ frozen `replay_window`. **Stage-0 self-heal (Task 12):** before preflight, if a host-kill
left the self-play block at `run:true` or a drifted `Seed` (the stage-1 `finally` restores them, but
a host-kill skips the `finally`), the driver resets them via `Edit-Config` and logs it — preflight
would otherwise hard-fail a recoverable, self-inflicted drift. The driver takes a **lockfile**
(`eval/.iteration.lock`) with **PID-liveness** (Task 12): a lock whose `pid=` is dead is reclaimed
with a log line; a live one refuses — never run two drivers (or calibrate/matchup tools) against the
live config at once. Everything is **transcribed** to `rl_iter_<K>/iteration_<K>_<ts>.log` and
ledgered to `eval/campaign_log.jsonl`.

**1 — Self-play export [core]** — **ONE general block** (`RL_SelfPlay_General`; the v3 forced-Hotel
block was dropped with the IG axis). Sets its **Seed = base + K** (J4: fresh card sets every
iteration, reproducible per iteration; base restored in a `finally`), flips it `run:true`, one
engine launch: **rounds 516 → 1032 games**, no forcing. The parent-net-guided UCT (N=1000) plays
itself under **regime v4**: τ=0.7 sampling turns 0–11; turns ≥12 **argmax with the general
`EpsilonLate=0.05`** late sampler (no IG-targeted ε in v4) and **seeded-random argmax tie-breaks**
(the old first-wins tie-break + longest-move-first ordering systematically over-clicked inside the
UCB indifference band). Engine output is captured to `selfplay_<ts>.log` and WARNING lines surfaced.

**1.5 — Archive [core]** — parity sidecars + replays → `training/data/rl_iter_<K>/{parity_states,
replays/general}/` (ONE general slice in v4; the future-schema re-extraction source). A prior
attempt's stale archive for this K is moved aside to `_orphans/` first (the stale-archive bug
caught + fixed in the Phase-0 run).

**2 — Vectorize [core]** — concat the general dir → H5, **lineage-stamped** (C5: `rl_parent_bin`/
`rl_parent_sha256`/`rl_frozen_sha256` attrs).

**3 — Train [core]** — warm-starts from the frozen `parent_pt`; **NO SWA** (the candidate is
**`final_model.pt`**, last-epoch weights); 6 epochs @ lr 1e-5; rehearsal **flat 0.10** from the
**ELITE corpus** (`human_elite_2000_45s_v2.h5`); trains over the **W=2** replay window (this iter +
the previous); validates on the **capped held-out** `human_val_1700_50k_v2.h5`; **seeded**
(2026000+K) and `num_workers 0`. Refuses window H5s with no lineage stamps or next to an `INVALID`
marker.

**4 — Export [core]** — `final_model.pt` → `neural_weights_rl_iter<K>.bin`.

**4.5 — Val-acc tripwire [gate]** — candidate vs parent on the capped val set; abort if >3pp below.
The parent's value is **cached** in `campaign_frozen.json` (`parent_val_acc_pct`, written at
promotion) — no recompute per iteration.

**4.6 — Prediction-movement probe [telemetry]** — mean |P_cand − P_parent| + winner-flip % on a
FIXED probe batch (elite corpus head) and on this iteration's own H5 → `prediction_movement.json`.
**This is the null-update detector and v4's first-class success readout**: a fixed-probe mean|dP|
below `prediction_movement_floor` (= 0.001) means stage 3 didn't actually train — record it in
`campaign_log.md` every iteration and watch the trend.

**5 — Export-parity GATE [gate]** — C++ == PyTorch on the archived sidecar states, tol **1e-4**
(measured floor ~1e-6). SCOPE: pins weights-export + forward arithmetic ONLY — feature extraction is
pinned by the three-way gate, value ORIENTATION by `a6_orientation_check.py` (both now also auto-run
at preflight as `correctness_gates`).

**6 — REMOVED in v4.** The O7 tactical suite was IG-specific and dropped with the IG axis. No stage
6 runs.

**7 — Eval [core]** — repoints `RL_Eval` → candidate (finally-restored), runs `run_eval.py
--anchors origin masterbot --pools general --abort-winrate 0.35`: **`origin`** (candidate vs the
PERMANENT v221 `RL_Eval_origin`, rounds 48 = 96 games) is the relative-drift anchor **and the
COLLAPSE/abort signal** (collapse iff its general win-rate < 0.35); **`masterbot`** (candidate vs the
AB SWF-faithful `MasterBot_SWF`, 96 games) is the absolute-strength trend. **No REJECT/REVIEW
verdict, no forced pool, no narrow/iter0/steam.** Player-level engine-load provenance on the
candidate (the masterbot opponent is AB/Playout — no NeuralNet load line to confirm). The manifest
carries pooled Wilson + paired per-card-set CIs and the boolean `collapse`. On collapse the driver
prints a loud `*** COLLAPSE ***` line.

**8 — Coverage + dashboard [telemetry]** — IG-click coverage stats (general slice; **non-fatal** — a
failure must NOT abort the iteration) + `render_dashboard.py` (the v4 table: `iter`, `collapse`,
`origin(vs v221)`, `masterbot(vs SWF-AB)`, `ig(sp/argmax)`). The coverage stats are watch-stats with
no axis riding on them in v4.

## Between iterations — promote-unless-collapse (FROZEN)

1. **Phase 0 (fixed generator): do NOT promote.** Validate the pipeline + record the iteration.
2. **Phase 1: PROMOTE by default** — unless the run aborted: a stage crash, the 4.5 tripwire fired,
   `collapse == True`, or self-play degenerate (game length out of `game_length_band` / per-seat
   win-rate out of [0.35, 0.65] / all draws) → run **`eval/promote_candidate.ps1 -K <k>`**. It
   sha-verifies the lineage (a fresh re-export of the `.pt` must equal the on-disk bin), updates
   `campaign_frozen.json` (parent name + sha + cached val-acc), repoints the **TWO** parent pins
   (`RL_Eval` + `RL_SelfPlay` — **NEVER `RL_Eval_origin`**), re-runs preflight, copies the tracked
   bin, and prints the two per-repo commit commands. Promotion through ANY other route is a bug.
3. **Collapse / abort** → keep the parent; record the decision + numbers in `eval/campaign_log.md`.
   The candidate's DATA stays in the window (it was generated by the PARENT); only an invalidated
   GENERATION run gets quarantined (`touch INVALID` in its `rl_iter_<k>` dir).
4. **Every 3–5 iterations (and before any AWS decision): `eval/run_checkpoint.ps1`** — the powered
   **origin + masterbot** eval (both anchor blocks bumped to **rounds 192 = 384 games each**,
   ~±2.5pp) + the **B8** forgetting guard (lineage val-acc vs the fixed v221 origin constant, 5pp
   band). **No steam.** **This is where the campaign's actual answer comes from** — per-iteration
   `collapse` cells are harm screens, not evidence. Kill criteria (rl_campaign §3/§6) read CHECKPOINT
   trend, not per-iteration noise.
5. **Record every iteration** in `eval/campaign_log.md` (template at the top): collapse, the
   origin/masterbot headline numbers, watch-stats (4.6 probe values, self-play P0 win-rate /
   non-degeneracy, game length, late sampled fraction, tripwire Δval-acc), decision + reasoning.
6. A failed stage ≥2 can resume without regenerating self-play: `run_iteration.ps1 -K <k>
   -ResumeFrom <stage>` (validates per-stage prerequisites).

## The two-phase run

**Phase 0** = fixed-generator smoke (DONE, K=1, 2026-06-16: collapse False, origin 49.5%, masterbot
58.3%, prediction-movement 0.0172, all gates PASS, NOT promoted — it calibrated the
`prediction_movement_floor`/`game_length_band` into the frozen tuple). **Phase 1** = the promoting
overnight loop (owner launches when ready), promotion on, bounded by abort-on-collapse.

## The knobs that ARE the campaign identity (two-tier)

Single source of truth: **`eval/campaign_frozen.json`** (stage 0 asserts config matches; the
`tiers` key documents which is which). **HP tier** (change = NEW campaign, re-anchor AND
re-baseline): N=1000 · τ=0.7/K=12 · εUniform=0 · **EpsilonLate=0.05** · **EpsilonIG=0** · c=0.3 ·
eval budget 7000ms/100k/c0.3 · train schedule (6 @ 1e-5, **no SWA**, rehearsal flat 0.10) ·
rehearsal/tripwire files (elite corpus + capped val) · the promotion policy · the candidate
interior + root iterators (NoIG interior + IG-subset root). **Scale tier** (change = re-anchor + a
campaign_log entry, same campaign): selfplay rounds 516 · seed base 5600 · Threads:8 · anchor blocks
(rounds/Seed/Threads) · **W=2** · `abort_winrate_vs_origin=0.35`. Parent keys change ONLY via
`promote_candidate.ps1`; `origin_bin` NEVER changes.
