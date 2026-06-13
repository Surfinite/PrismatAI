# RL Iteration Runbook — one loop, at a glance (regime v3, 2026-06-13)

> Reference card for what `eval/run_iteration.ps1 -K <k>` does, what must be true before it starts,
> and what happens between iterations. Tags: **[core]** = the loop doesn't work without it ·
> **[gate]** = cheap check that aborts a bad run · **[telemetry]** = recorded, never aborts.
> The campaign contract (frozen tuple, verdict, kill/escalation rules) is `eval/rl_campaign.md`;
> the eval harness internals are `eval/README.md`; the per-iteration human record + accepted-
> limitations register is `eval/campaign_log.md`. Historical audit trail:
> `docs/superpowers/plans/2026-06-{09,10,11,12}-*` (the 06-12 third audit drove this regime).

## Pre-flight (before ANY iteration) — ENFORCED by `eval/preflight_config.py` (stage 0)

The driver runs this automatically and aborts on any FAIL; also runnable standalone. It never
rewrites `config.txt` — drift must be reconciled deliberately (edit `campaign_frozen.json` AND
`config.txt` together; parent changes go through `eval/promote_candidate.ps1` ONLY).
**15 checks** (machine list = the script's own docstring):

| Check | What it asserts | Why |
|---|---|---|
| `json_bom` | config is strict JSON, no BOM | BOM makes the C++ parser skip the file silently |
| `use_dsnn_sentinel` | no `use_dsnn.txt` next to the engine exes | the Steam drop-in sentinel silently swaps the net on every protocol call (stages 6/8 also re-assert at time of use — C3) |
| `run_true` | every Benchmarks block `run:false` at rest | a stray `run:true` runs an unintended tournament on launch |
| `iterator_shape` | the IGsubset root iterator's exact structure | the Jun-4→9 crippled-iterator incident — machine-checked |
| `book_sizes` | `LiveOpeningBook2`==50, `DefaultOpeningBook`==4 | book truncation/drift |
| `reference_graph` | every declared reference resolves (incl. WeightsFile on disk) | dangling names |
| `selfplay_replays` | both self-play blocks carry the expected saveReplays dirs | the per-iteration replay archive contract |
| `frozen_tuple` | `RL_SelfPlay` tuple == frozen (N/τ/K/ε/**EpsilonIG**/c) + both self-play blocks match `selfplay_mix` rounds/forcing/threads + **at-rest Seeds == `selfplay_seed_base`** | the tuple IS the campaign identity; the driver sets Seed=base+K transiently (J4) and must restore the base |
| `parent_repin` | ALL FOUR parent pins (`RL_Eval`/`RL_Eval_iter0`/`RL_SelfPlay`/`RL_Narrow`) == frozen `parent_bin` | F-07/N-2: a killed run or forgotten repoint must not silently change the comparison |
| `origin_pin` | `RL_Eval_origin.WeightsFile` == frozen `origin_bin` (v221, PERMANENT) | drl-03: the origin anchor is NEVER repointed — it carries the campaign's cumulative measurement |
| `anchor_blocks` | every frozen anchor block's rounds/Seed/Threads | eval volume/panels are campaign identity (J3/J4) |
| `eval_budget` | TimeLimit/MaxTraversals/UCTConstant on all four eval players == frozen `eval_budget` | A1: the deployment budget was previously enforced by nothing |
| `unit_index` | `unit_index.json` exists + carries the canonical 116 units | a missing index silently lobotomizes every NeuralNet player (engine also FATALs on mappedTypes==0 now) |
| `existences` | frozen `parent_pt` + `rehearsal_file` + `tripwire_val_file` + masterbot exe exist | warm-start, stage 3, 4.5, and the steam yardstick depend on them |
| `parent_sha` | sha256(on-disk parent bin) == frozen `parent_bin_sha256` | ops-promote-01: the parent is CONTENT-pinned — catches a same-K re-export clobber and name-consistent-but-wrong promotions |

## The stages (0–8, plus 1.5 / 4.5 / 4.6)

**0 — Structural preflight [gate]** — the table above; also rejects `-N` ≠ `frozen_N` and
`-Window` ≠ frozen `replay_window`. The driver takes a **lockfile** (`eval/.iteration.lock`) —
never run two drivers (or calibrate/matchup tools) against the live config at once; everything
is **transcribed** to `rl_iter_<K>/iteration_<K>_<ts>.log` and ledgered to `eval/campaign_log.jsonl`.

**1 — Self-play export [core]** — sets both blocks' **Seed = base + K** (J4: fresh card sets every
iteration, reproducible per iteration; bases restored in a `finally`), flips both blocks
`run:true`, one engine launch: `RL_SelfPlay_General` (rounds **344** → ~688 games, no forcing) +
`RL_Step2_Smoke` (rounds **172** → ~344 games, ForcedCards Hotel) = **~1032 games/iter, ⅔+⅓ mix**
(J1 upper). The parent-net-guided UCT (N=1000) plays itself under **regime v3**: τ=0.7 sampling
turns 0–11; turns ≥12 **argmax with TARGETED IG-ε** (`EpsilonIG=0.25`: at roots whose children
span ≥2 IG click counts, play the most-visited child at a NON-argmax count — an on-axis
counterfactual; `EpsilonLate` retired to 0) and **seeded-random argmax tie-breaks** (A1: the old
first-wins tie-break + longest-move-first ordering systematically over-clicked inside the ~9pp
UCB indifference band). Engine output is captured to `selfplay_<ts>.log` and WARNING lines surfaced.

**1.5 — Archive [core]** — parity sidecars + replays → `training/data/rl_iter_<K>/…` (unchanged;
the future-schema re-extraction source).

**2 — Vectorize [core]** — concat both dirs → H5, now **lineage-stamped** (C5: `rl_parent_bin`/
`rl_parent_sha256`/`rl_frozen_sha256` attrs).

**3 — Train [core]** — warm-starts from the frozen `parent_pt`; **NO SWA** (J1/training-02: the
4-snapshot average diluted the update ~20% for nothing — the candidate is **`final_model.pt`**,
last-epoch weights); 6 epochs @ lr 1e-5; rehearsal **flat 0.10** from the **ELITE corpus**
(`human_elite_2000_45s_v2.h5` — both ratings ≥2000, 45s+ controls, provenance inherited from
human_1800_v2); validates on the **capped held-out** `human_val_1700_50k_v2.h5`; **seeded**
(2026000+K) and `num_workers 0`. Stage 3 also **refuses window H5s** that carry no lineage stamps
or sit next to an `INVALID` marker (C5 — the quarantine mechanism is now `touch INVALID` in the
bad `rl_iter_<k>` dir, not file-moving).

**4 — Export [core]** — `final_model.pt` → `neural_weights_rl_iter<K>.bin`.

**4.5 — Val-acc tripwire [gate]** — candidate vs parent on the capped val set; abort if >3pp below.
The parent's value is **cached** in `campaign_frozen.json` (`parent_val_acc_pct`, written at
promotion) — no recompute per iteration.

**4.6 — Prediction-movement probe [telemetry, B5]** — mean |P_cand − P_parent| + winner-flip % on a
FIXED probe batch (elite corpus head) and on this iteration's own H5 → `prediction_movement.json`.
**This is the null-update detector**: a fixed-probe mean|dP| ≲ 1e-4 means stage 3 didn't actually
train (rl-design-01) — record it in `campaign_log.md` every iteration and watch the trend.

**5 — Export-parity GATE [gate]** — C++ == PyTorch on ~1000 archived sidecar states, tol **1e-4**
(B2; measured floor ~1e-6), stratified across both slices. SCOPE: pins weights-export + forward
arithmetic ONLY — feature extraction is pinned by the three-way gate
(`training/tests/test_three_way_feature_parity.py`, 7 fixture states incl. frozen/damaged/
lifespan/IG since B3) and value ORIENTATION by `eval/a6_orientation_check.py` (B1 — run it after
ANY engine change; it is the only test that catches a maxPlayer sign flip).

**6 — Tactical suite [telemetry, J6]** — runs and RECORDS; **never aborts** (single 3s UCT samples
measured 18–33% false-fail on sibling cases). A reported regression must be REPRODUCED (re-run the
case 3–5×) before it counts as harm under the promotion policy.

**7 — Eval [core]** — repoints `RL_Eval` → candidate (finally-restored), runs `run_eval.py
--anchors iter0`: forced (rounds 96 = 192 games) + general (**two seed panels** generalA/generalB,
2026/2027, rounds 96 each = 384 games, aggregated into one cell). Player-level engine-load
provenance (prov-06) on BOTH seats. The manifest now also carries a **paired per-card-set CI**
(from the engine's per-round CSV) alongside the verdict's pooled Wilson CI. Narrow/origin/steam do
NOT run here (J3): narrow runs at promotion, origin+steam at checkpoints.

**8 — Coverage + dashboard [telemetry]** — IG stats per slice + combined (C8; the self-play stats
describe the GENERATOR/parent, not the candidate) + the **B6 `ig_contrast_pairs` watch-stat**: how
many colour-swap pairs realized DIFFERENT IG-click sequences — the campaign's actual counterfactual
count. If it reads ~0, the targeted ε is not reaching the axis.

## Between iterations — the J2 promote-unless-harm policy (FROZEN)

1. **PROMOTE by default**: unless verdict==REJECT, the 4.5 tripwire fired, or a REPRODUCED
   tactical regression → run **`eval/promote_candidate.ps1 -K <k>`**. It sha-verifies the lineage
   (fresh re-export of the .pt must equal the on-disk bin), updates `campaign_frozen.json`
   (parent name + sha + cached val-acc), repoints the four parent pins (NEVER `RL_Eval_origin`),
   re-runs preflight, copies the tracked bin, runs the promotion-time **narrow** anchor, and
   prints the two per-repo commit commands. Promotion through ANY other route is a bug.
2. **REJECT** → keep the parent; record the decision + numbers in `eval/campaign_log.md`. The
   candidate's DATA stays in the window (it was generated by the PARENT); only an invalidated
   GENERATION run gets quarantined (`touch INVALID` in its `rl_iter_<k>` dir).
3. **Every 3–5 iterations (and before any AWS decision): `eval/run_checkpoint.ps1`** — the
   powered origin eval (768 general + 192 forced games vs the PERMANENT v221 origin, ~±3.5pp),
   the steam yardstick (100 games), and the B8 forgetting guard (lineage val-acc vs the origin
   constant, 5pp band). **This is where the campaign's actual answer comes from** — per-iteration
   REVIEW cells are harm screens, not evidence. Kill criteria (rl_campaign §3) read CHECKPOINT
   trend, not per-iteration noise.
4. **Record every iteration** in `eval/campaign_log.md` (template at the top): verdict, watch-stats
   (4.6 probe values, `ig_contrast_pairs`, late sampled fraction, game length), decision + reasoning.
5. A failed stage ≥2 can resume without regenerating self-play: `run_iteration.ps1 -K <k>
   -ResumeFrom <stage>` (validates per-stage prerequisites).

## The knobs that ARE the campaign identity (two-tier since J7)

Single source of truth: **`eval/campaign_frozen.json`** (stage 0 asserts config matches; the
`tiers` key documents which is which). **HP tier** (change = NEW campaign, re-anchor AND
re-baseline): N=1000 · τ=0.7/K=12 · ε=0 · **EpsilonIG=0.25** (EpsilonLate retired) · c=0.3 ·
eval budget 7000ms/100k/c0.3 · train schedule (6 @ 1e-5, **no SWA**, rehearsal flat 0.10) ·
rehearsal/tripwire files (elite corpus + 50k val) · the promotion policy. **Scale tier** (change =
re-anchor the iter-0 baseline + a campaign_log entry, same campaign): selfplay rounds 344+172 ·
seed bases 5600/5500 · Threads:8 · anchor blocks (rounds/Seeds/Threads) · W=5. Parent keys change
ONLY via `promote_candidate.ps1`; `origin_bin` NEVER changes.
