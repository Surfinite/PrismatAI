# RL Iteration Runbook — one loop, at a glance

> Reference card for what `eval/run_iteration.ps1 -K <k>` does, what must be true before it starts, and
> what changes between iterations. One sentence per step; tags mark what's load-bearing:
> **[core]** = the loop doesn't work without it · **[gate]** = cheap check that aborts a bad run ·
> **[optional]** = yardstick/reporting, removable without breaking the loop.
> The Jun-9/Jun-10 audit findings (E1 random-init, M-03 val leak, F-07 dangling repoint, F-08 steam
> mis-wire, M-04 epoch sizing, M-06 missing UCTConstant, dead stats) are all FIXED in the current code;
> the two FINDINGS docs in `docs/superpowers/plans/` remain the historical record.

## Pre-flight (before ANY iteration) — ENFORCED by `eval/preflight_config.py` (stage 0)

The driver runs this automatically and aborts on any FAIL; it is also runnable standalone before any
engine launch. It never rewrites `config.txt` — drift must be reconciled deliberately (edit
`campaign_frozen.json` AND `config.txt` together).

| Check (preflight name) | What it asserts | Why |
|---|---|---|
| `json_bom` | `config.txt` is strict JSON, no BOM | BOM makes the C++ parser skip the file silently |
| `run_true` | every Benchmarks block `run:false` at rest | a stray `run:true` runs an unintended tournament on launch |
| `iterator_shape` | `HardIterator_5var_IGsubset_Root` = AbilitySubset/IG_Only wrapping the 5-variant NoIG portfolio, dims [1,5,5,1], exact variant set; `V5_CS2_NoIG` transitively reaches `LiveOpeningBook2` | the Jun-4→9 crippled-iterator incident — now machine-checked |
| `book_sizes` | `LiveOpeningBook2` == 50, `DefaultOpeningBook` == 4 (post SWF port) | book truncation/drift |
| `reference_graph` | every declared reference resolves (openingBook, filter, subsetFilter, buyLimits, combination, PartialPlayers, include, iterator keys, PlayoutPlayer, WeightsFile file on disk) | dangling names; complements the engine's own construction-time hard-fails |
| `frozen_tuple` | `RL_SelfPlay` MaxTraversals/TemperatureK/Tau/EpsilonUniform/**EpsilonLate** == `campaign_frozen.json` (regime v2 freezes EpsilonLate=0.05 — an ABSENT config key means 0.0 to the engine and FAILS; older frozen files without the key keep the absent-or-0 rule); BOTH self-play blocks match the frozen `selfplay_threads` + `selfplay_mix` (rounds, ForcedCards on the forced block ONLY, run:false at rest) | the three-way N skew happened once; the tuple IS the campaign identity |
| `parent_repin` | ALL FOUR parent-side players' `WeightsFile` == the frozen `parent_bin`: `RL_Eval` (eval pin), `RL_Eval_iter0` (the VERDICT opponent), `RL_SelfPlay` (the data generator), `RL_Narrow` (the iterator-only anchor) | F-07 recovery + N-2 — a killed run must not leave an unpromoted candidate pinned, and a forgotten post-promotion repoint must not turn "candidate vs parent" into "candidate vs grandparent" |
| `existences` | frozen `parent_pt`, the train/val H5s, and the 2016 MasterBot exe all exist | warm-start, M-03 val, and the steam yardstick depend on them |

The dave-bin `use_dsnn.txt` sentinel is preflight check 9 (`use_dsnn_sentinel`) — present, it would
silently swap the net on every query_move/tactical/coverage call; `run_eval.py` re-asserts it (plus
`PRISMATA_FORCE_DSNN`) at eval time as defense-in-depth. The engine itself **hard-fails at construction**
on unknown/empty books, unknown filters/iterators/partials/players, and NN weights-load failures
(dave `26075fa`/`d0ec633`/`6e93480`), with an unloaded-net guard on the UCT value path (X5b).

## The stages (0–8, plus the 1.5 archive and 4.5 tripwire)

**0 — Structural preflight [gate]** — `preflight_config.py` (the table above); also rejects a `-N` that
differs from `frozen_N`.

**1 — Self-play export [core]** — flips **TWO** blocks to `run:true` (regime-v2 data mix, one
`Prismata_Testing.exe` launch): `RL_SelfPlay_General` (`rounds:43` → ~86 games, **no forcing** — the
broadened general-improvement goal) and `RL_Step2_Smoke` (`rounds:21` → ~42 games, ForcedCards Hotel —
keeps IG-decision density), i.e. **⅔ general + ⅓ forced-Hotel**, each into its own export dir
(separate dirs REQUIRED — the export counter is per-Tournament-instance). The parent-net-guided UCT
(frozen N=1000) plays itself under the **early-noise/late-precision regime** (τ=0.7 sampling turns
0–11; turns ≥12 argmax with `EpsilonLate=0.05` uniform-child chance) and writes one JSONL record per
position, labelled with the eventual game outcome. Both blocks also `saveReplays` (per-action snapshot
replays, ~50 KB gz/game, viewable on `/replay/local`). Clears stale shards (both dirs) + parity
sidecars first (replay leftovers are moved to `training/data/_orphans/`, never deleted); flips both
blocks back in a `finally`.

**1.5 — Archive state artifacts [core, 2026-06-12 replay-audit fixes]** — moves this run's parity
sidecars (`sp_*.json.gz`, engine-native turn-start states from the per-block
`<exportTrainingV2>_parity` dirs, archived flat with a `general_`/`forced_` slice prefix — the
**future-schema re-extraction source**: any future exporter can rebuild training data from them via
`--dump-v2-record`) and replays
(`game_*.json.gz` — forensic record; same per-game id as the `selfplay_NNNN.jsonl` shards, so
`game_0007` IS shard 0007's game; turn-start state = `states[p==0 ? 0 : turnBoundaries[p]-1]`) into
`training/data/rl_iter_<K>/{parity_states, replays/{general,forced}}/`. Disk: ~50 KB gz/game replays
+ ~3 KB gz/state sidecars ≈ 15–20 MB per 128-game iteration.

**2 — Vectorize [core]** — concatenates the shards from BOTH export dirs (general then forced; game
boundaries re-detected via `ply_index==0`) and converts JSONL → H5 tensors (schema v2.2.1), the
format `train.py` consumes.

**3 — Train [core]** — **warm-starts from the parent checkpoint via `--init-weights`** (E1 fix:
`train.py --rl-mode` now HARD-FAILS without it; the parent = the FROZEN `parent_pt` from
`campaign_frozen.json` — `deepsets_v221/swa_model.pt` until a promotion updates the frozen file, whose
export is byte-identical to the deployed v221 `.bin`. N-3: running K>1 WITHOUT a promotion deliberately
warm-starts from the SAME frozen parent again — an unpromoted candidate never enters the lineage;
`-ParentPt` is an explicit, loudly-printed override), then
fits 6 low-LR epochs (SWA from epoch 3) on the last-W iterations' H5s mixed with human rehearsal.
Validates on the **HELD-OUT** `human_val_1700_v2.h5` (M-03 fix — never the rehearsal file). Epoch
length = ~one pass over the self-play window, not the rehearsal corpus (M-04 fix; LR schedule sized to
match). Produces `swa_model.pt`.

**4 — Export [core]** — converts `swa_model.pt` → `neural_weights_rl_iter<K>.bin` (the C++ DSN2 format).

**4.5 — Val-acc tripwire [gate]** — candidate vs parent val-acc on the held-out human set
(`eval_deepsets_h5.py`); **aborts if the candidate is >3.0 pp below its parent** (parent ≈71.8% on
this set) — catches an E1-class bad-init/bad-train cheaply, before the expensive eval stages.

**5 — Export-parity gate [gate]** — asserts C++ inference == PyTorch on a state batch (worst |Δ| < 1e-3),
explicitly pinning `--pt`/`--bin` to THIS candidate; catches export/feature bugs, NOT net quality.
Reads the stage-1.5 **archived** sidecars (`rl_iter_<K>/parity_states/`) — guaranteed to be this
run's own states, never a shared live dir's leftovers.

**6 — Tactical suite [gate]** — replays the curated IG positions through the candidate via
`query_move.js` (which injects the tuned `UCTConstant 0.3` by default — M-06) and fails only on a
regression vs `eval/tactical_baseline.json`. The baseline's standing ktink FAIL is recorded
(count 0 of feasible 2, want 1, at the suite's 3 s budget) — it is **budget-dependent** (the correct
1-click line wins at N=256) and never gates, being a never-passed case.

**7 — Eval [core]** — repoints `RL_Eval.WeightsFile` → the candidate, runs `run_eval.py` (anchors:
iter0 = vs parent, forced+general; narrow = vs `RL_Narrow`; steam = DaveAI+candidate vs the 2016
MasterBot at its permanent home), then **always restores `RL_Eval` → the parent in a `finally`**
(F-07 fix). `run_eval.py` adds: active provenance (config must already point at the candidate;
engine stderr must confirm the candidate-net load per anchor AND — N-2 — the PARENT-net load for the
parent-pinned opponent, `engine_confirmed_parent_load`), an **incremental atomic manifest**
(a kill keeps finished anchors), and the **verdict** — REJECT iff general-pool Wilson ci_upper < 0.5,
REVIEW otherwise, INCOMPLETE if the general anchor is missing. Nothing auto-promotes.

**8 — Coverage + dashboard [optional]** — tabulates the IG-click-count distribution (with feasible-max
binning) from the self-play data and renders the human-facing results table.

## Between iterations (manual today)

1. **Decide** from the manifest/dashboard: promote, iterate, or stop. REJECT = proven worse on the
   general pool; REVIEW = your judgment on the recorded numbers (`d_rl`/`d_reg` + CIs are information,
   not gates).
2. **If promoting:** the candidate becomes the new parent — update the frozen `parent_bin`/`parent_pt`
   in `campaign_frozen.json` (the next iteration's warm-start resolves from `parent_pt` automatically)
   AND repoint **all four** parent-side players' `WeightsFile`: `RL_SelfPlay` (data generator),
   `RL_Eval` (eval pin), `RL_Eval_iter0` (the VERDICT opponent — forgetting this one silently turns
   "candidate vs parent" into "candidate vs grandparent"), `RL_Narrow` (iterator-only anchor); commit
   the new `.bin` + config + `campaign_frozen.json` together so the campaign identity stays one
   consistent tuple (the preflight's `parent_repin`/`frozen_tuple` checks will otherwise fail the next
   run — by design).
3. **If iterating:** keep the parent everywhere (stage 7 already restored `RL_Eval`); adjust data;
   quarantine the failed candidate's artifacts (`training/data/rl_iter_<K>/`, the `.bin`) — the replay
   window selects H5s **by filename**, so stale/invalid iterations would silently rejoin the training
   mix at the same K.
4. **Increment K** — stage 3's sliding window then picks up `rl_iter_{K-W+1..K}` automatically.

## The knobs that ARE the campaign identity

Single source of truth: **`eval/campaign_frozen.json`** (stage 0 asserts `config.txt` matches; nothing
rewrites either side silently). Frozen 2026-06-11 (**regime v2** — early-noise/late-precision,
superseding the same-day v1 whole-game sampling, which measured 40–46% non-argmax moves +
significantly longer games): `N=1000` (self-play MaxTraversals) · `TemperatureTau=0.7` /
`TemperatureK=12` (τ-sampling turns 0–11 only) · `EpsilonUniform=0` / **`EpsilonLate=0.05`** (turns
≥12: argmax with a 5% uniform-child chance, ~1.1 mild deviations/game a priori — measured 0.69/game at
the 32-game re-screen: 23% of late roots are single-child and uniform picks can land on argmax) ·
`UCTConstant=0.3` ·
`Threads:8` self-play · self-play mix **⅔ general + ⅓ forced-Hotel** (`selfplay_mix`:
`RL_SelfPlay_General` rounds:43 + `RL_Step2_Smoke` rounds:21) · `W=5` (replay window) · epochs/lr
(6 @ 1e-5, SWA from 3) · rehearsal fraction (0.30 → 0.10, −0.07/iter) · anchor budget (7000 ms /
100k) · parent weights (v221). Change any of these mid-campaign and iteration results stop being
comparable — that's a NEW campaign (`rl_campaign.md` §1).
