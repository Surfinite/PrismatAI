# PrismatAlpha — Project Instructions

> **Full project history**: `docs/PROJECT_HISTORY.md`
> **Extended reference** (cloud ops, dashboard, sniffer, commentary, full file tables): `docs/CLAUDE_REFERENCE.md`
> **Training plan V1**: `docs/plans/2026-03-06-training-plan-v1.md`
> **Self-play master plan**: `docs/plans/2026-02-15-selfplay-training-master-plan.md`

## ⚠️ WHICH ENGINE — read before touching any C++

**This repo's `source/engine` + `source/ai` are the clean-room `engine_v2`, which is INDICTED** (~33 pts weaker than Dave's original — see *Parity-Gap Experiments* below / `docs/deepsets-training-results.md`). **Do NOT read, build, or modify it for AI or engine work — it is legacy.** The current, strong engine + AI is **engine_v1 in the SEPARATE repo `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`, builds x64/v145).** Query/run it via `node js_engine/query_move.js … --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe`. **THIS** repo (`feature/production-vectors`) is for **training (`training/`), the JS engine (`js_engine/`), eval (`eval/`), and docs** — not the C++ engine. ⚠️ The "How to Build and Run" section below builds **engine_v2** and is **legacy**; don't follow it for current work.

## Current Status (June 19, 2026)

**RL campaign REGIME v4 "proof-of-life" — COMPLETE. K=1–8 ran; K=2–8 all PROMOTED (parent now `neural_weights_rl_iter8.bin`, 235b689d…). The Mobile-Animus (MA) action-space axis was opened (K=5–8) + powered-checkpointed: cleanly integrated, NO powered gain. Loop validated end-to-end; next lever is a policy head (hypothesized) — see `docs/superpowers/plans/2026-06-19-policy-head-brainstorm-context.md`.**
Reframed (Jun 14) from the IG-axis measurement campaign to a general DSNN-improvement /
fix-MasterBot-mistakes framework: ONE general self-play block (516 rounds ≈ 1032 games), **EpsilonLate
0.05 / EpsilonIG 0** (IG over-click already fixed by action-space widening), NoIG interior iterator
`HardIterator_5var_NoIG`, replay window **W=2**, NO SWA (candidate = `final_model.pt`), rehearsal 0.10
elite. Eval = TWO same-path anchors: **origin** (cand vs the PERMANENT v221 `RL_Eval_origin`) =
relative-drift + the **collapse** signal (collapse iff origin general WR < 0.35); **masterbot** (cand vs
the AB SWF-faithful `MasterBot_SWF`) = absolute-strength trend. NO REJECT/REVIEW verdict —
**promote-unless-collapse** via `eval/promote_candidate.ps1` (repoints the TWO pins RL_Eval + RL_SelfPlay;
RL_Eval_origin never moves). Preflight **19 checks**. Contract: `campaign_frozen.json` (tuple_version 4) +
spec `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`; operate via
`eval/rl_runbook.md`.

**Phase-1 ran K=1–8; parent now `neural_weights_rl_iter8.bin` (235b689d…).** K=2–8 all PROMOTED
(promote-unless-collapse). **MA axis opened at K=5 (config-only re-anchor: `IG_Only` +
`Ability_Filter_Live_NoIG` extended with "Mobile Animus"; `MaxChildren` 40→80)** — the net now chooses the
IG×MA fire-count at root (replaces the forced-MA-sac over-click). **K=8 powered checkpoint** (rl_iter8 vs
v221, 384 games/anchor): **origin 53.6% (paired [0.502,0.571]), masterbot 63.8%, B8 no-forgetting, collapse
False** — statistically indistinguishable from the pre-MA K=4 checkpoint (52.3% / 67.3%): **MA integrated
cleanly but bought NO powered ≥5pp gain** (the value-only "generator-insensitive fixed point" Campbell &
Churchill predicted + measured). **Proof-of-life COMPLETE.** Recommended next (a NEW campaign — lr is
hp-tier): ONE coverage-controlled crux iteration (forced-MA curriculum block + lr 1e-5→3e-5, powered
≥780/anchor) to disambiguate "MA neutral" vs "MA under-covered/under-trained"; if still flat → pivot to the
**policy head** (`docs/superpowers/plans/2026-06-19-policy-head-brainstorm-context.md` — the dave-master PUCT
consumer is already built). **⚠️ The RL parent is `neural_weights_rl_iter8.bin`** — always read
`campaign_frozen.json` `parent_bin` + the latest `eval/campaign_log.md` entry, never assume. Logbook:
`eval/campaign_log.md`.

**Steam drop-in: per-checkpoint bundle builder + FORCE_DSNN fidelity fix (Jun 17).** `eval/build_steam_bundle.ps1
-Label <name>` packages any net (default = frozen lineage head) into `C:/libraries/DSNN_steam_bundles/<name>/`
— a **self-describing** (`use_dsnn.txt` `weights=` key; no env var, no renamed `.bin`), **self-verifying**
DSNN drop-in. Engine `dave@50977510` (re-pin main `d94908b9`): the FORCE_DSNN deploy path gained the `weights=`
key **AND** its interior iterator `HardIterator_5var` → **`HardIterator_5var_NoIG`** — the deployed bot now plays
the campaign's trained/measured NoIG-interior action space (closes the RL-vs-deployed asymmetry; bundles ≤ v221
shipped the IG-included, unmeasured interior). a6 + three-way UNCHANGED (FORCE_DSNN unused in self-play/eval).
First bundle built + verified: `DSNN_steam_bundles/v221_rl_iter4`.

**Self-play/eval stalemate draw rule SHIPPED + validated live (Jun 17)** — a frozen game ends early as a
0.5 draw + self-play trims the frozen tail; the first Phase-1 run had **0 games hit the 200-turn cap (vs 3
in Phase-0)**. Mechanism + files: see the Engine & Build gotchas.

## Status history (superseded)

**RL Phase-1 PAUSED at parent `rl_iter4` (Jun 17) [SUPERSEDED — campaign continued to rl_iter8].** Phase-0
(K=1) passed; K=2/3/4 PROMOTED (per-iter origin vs v221 54.7/52.1/50.0, masterbot 62.5/58.3/62.5); first
powered checkpoint on rl_iter4 = origin 52.3% [0.47–0.57] / masterbot 67.3% [0.62–0.72], no-forgetting =
proof-of-life healthy with a modest ~+2pp gain. Owner paused, then opened the MA axis (K=5–8) — see Current
Status. Full record: `eval/campaign_log.md`.

**RL campaign REGIME v3 — third audit implemented, RUN-READY (Jun 12–13) [SUPERSEDED by v4].** The third (design-level)
audit (`docs/superpowers/plans/2026-06-12-rl-loop-design-audit-FINDINGS.md`) found the loop
mechanically green but structurally unable to resolve its own output (~78 optimizer steps/iter vs
±8.7pp eval resolution; ~zero IG counterfactuals; no promotion policy). ALL J1–J7 owner decisions +
the 29-item mechanical worklist are IMPLEMENTED (main `461f58dc`, dave `1eba023c`): rounds 344+172
(~1032 games/iter), **NO SWA** (candidate = `final_model.pt`), rehearsal flat 0.10 on the **ELITE
corpus** (`human_elite_2000_45s_v2.h5`), self-play **seeds derive base+K**, **targeted
`EpsilonIG=0.25`** replaces EpsilonLate (+ seeded argmax tie-breaks — the old first-wins tie-break
systematically over-clicked inside the ~9pp UCB indifference band), per-iteration eval = **iter0
only** (192 forced + 384 general across 2 seed panels), **promote-unless-harm** via
`eval/promote_candidate.ps1` (sha-pinned parent), **checkpoint origin evals** via
`eval/run_checkpoint.ps1` (768+192 games vs the PERMANENT `RL_Eval_origin`=v221 — the campaign's
answer-producing measurement), tactical = telemetry-only, preflight **15 checks**, A6 orientation
check BUILT+validated (`eval/a6_orientation_check.py`), paired per-card-set CI from the new engine
rounds-CSV. **Bonus catch:** extending the three-way gate's fixtures (frozen/damaged/lifespan/IG
states) caught + fixed a REAL fifth v2.2.1-class skew (`is_blocking` was 1 on frozen units in both
C++ legs; the faithful JS engine says 0). Tests 218/218; the campaign logbook + decision ledger is
**`eval/campaign_log.md`**. First real run: `eval/run_iteration.ps1 -K 1`.

**RL loop audited, remediated, RUN-READY (Jun 9–12).** Two independent cold-start audits + a verification sweep + three fix batches landed (main `2654e21..1a9788d`, dave `26075fa..eb52fa8`, all pushed to PrismatAlpha). Headlines: `train.py --rl-mode` now **WARM-STARTS** (`--init-weights` required — it previously trained every iteration from RANDOM init, the E1 bug; iter-1 parent = `training/models/deepsets_v221/swa_model.pt`, sha-verified == the deployed v221 bin); the GO gate is replaced by a **REJECT/REVIEW/INCOMPLETE verdict** (detect-proven-harm + human decision; nothing auto-promotes); the engine **hard-fails** on config mistakes (unknown books/filters/iterators/players, NN load failures); the dave config is **SWF-faithful** (buy tree incl. `BuyEconFast`, 4-entry `DefaultOpeningBook`; EconLimits matched=untouched); the campaign tuple is **FROZEN** in `eval/campaign_frozen.json` (**N=1000, τ=0.7, K=12, εlate=0.05 "regime v2"**, ⅔ general + ⅓ forced-Hotel self-play mix, Threads:8) and asserted by `eval/preflight_config.py` (stage 0, 10 checks — never rewrites config); the steam anchor pits the candidate vs the genuine **2016 MasterBot at `c:/libraries/prismata_baselines/masterbot2016/`**; tournament HTML now carries **per-seat P1/P2 W/G columns** with slot-indexed attribution. The infamous "25.8% iter0" was the random-init candidate vs v221 — the harness is sound (identical players = exactly 50%, proven four ways). Operate via **`eval/rl_runbook.md`**; first real run: `eval/run_iteration.ps1 -K 1`. Record: the two FINDINGS docs + `docs/superpowers/plans/2026-06-11-rl-fixes-verification.md` (resolution table added Jun 12).

**RL self-play loop + Infusion-Grid action space (Jun 3–4).** The full gated RL value-net self-play pipeline was built (`train.py --rl-mode` + replay buffer/human rehearsal; 3-anchor Wilson-CI eval harness; export-parity scaled to ~1000 states; O7 tactical suite + `js_engine/query_move.js`). **The current engine + AI now lives in the SEPARATE repo `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`, builds x64/v145)**; this repo's `feature/production-vectors` holds the training/JS/eval/docs side — don't cross-file. Engine prereqs landed: **A12** (standalone now loads `config.txt`, so config-only iterators resolve on the Steam/`query_move` path), **resignation DISABLED** (eval/self-play integrity), **A2** optional late-ε sampler (default off). **Headline:** the deployed AI over-clicks Infusion Grid (internal codename `Hotel`; click = R→selfsac→4 Husks) — rebuilt as **`MoveIterator_AbilitySubset`** (`dave@4bfdb61`) so the value net selects the IG-click COUNT (0..N); on a real over-click state it now picks click-1, not 2. Remaining: exporter IG-count stamps → N-calibration → the iter-0/1 campaign. Continuation prompt: `docs/superpowers/plans/2026-06-04-rl-continuation-session2.md`.

**Repo renamed `PrismatAI → PrismatAlpha`** (May 5–9). GitHub at github.com/Surfinite/PrismatAlpha. Local filesystem path unchanged (`c:\libraries\PrismataAI\`).

**prismata.live LIVE.** Split architecture (data box + site box, S3-synced every 60s). Active maintenance and live-spectating work is tracked in the prismata-ladder workspace — related but separate repo.

**DeepSets models exported.** MB-only: 82.4% val acc, Human-only: 78.2%, Mixed: 82.2%. Five DSNN players configured. Results doc: `docs/deepsets-training-results.md`.

**35-prop production-vector DSNN trained + deployable (Jun 1).** Clean 100-epoch mixed re-run (35-property tokens, token_dim 77) completed: SWA **81.7% val / val_loss 0.3464**, exported to `bin/asset/config/neural_weights_mixed_35prop.bin`. C++↔PyTorch parity re-verified on the final weights (worst |Δ| 5.84e-07). `train.py` gained `--resume` + `--stop-after-epoch` + an XPU OOM fix (per-epoch `empty_cache`; `reserved` stayed flat at 346 MB all 100 epochs — an allocator-pool issue, not a leak). Treat this as the **RL init**: ~82% is in-band/expected (MB-flavoured val can't see the production-vector features); the payoff is RL, not a supervised win. **Neural weights are now git-tracked** (never-commit rule retracted — swap-in path sanctioned + paper in prospect). Engine fix: `dominionNames[]` allow-list (file-library load path only) was missing 12 ranked units added post-open-source; regenerated to the full 105 (live `InitFromMergedDeckJSON` AI path was never affected). Details: `docs/deepsets-training-results.md`.

**Parity gap quantified.** Mar 17 single-unit sweep (105 units × 4 games): LiveHardestAIUCT wins ~20% vs STEAMAI, 60% of units lose 0/4. May 14 ablation (800 games at 5 s think): `DSNN_MBonly` vs `LiveHardestAIUCT` ended **30.0% to 66.9%** — DSNN lost decisively on the same engine + OB.

**OB parity confirmed (May 16, retracts May 14 claim).** Earlier note said `LiveOpeningBook2` was the wrong OB and that the real MB OB was 120 entries in the short-params blob. Wrong on both counts. The 120 was a cross-OB sum across 7 separate books in `93_*.bin`. Live MB = `HardestAI` difficulty (per [UINotHonorableIcon.as:50](prismata_decompiled/scripts/starlingUI/game/gameover/UINotHonorableIcon.as#L50)) → `NewIterator_Root` → 5 ChillSolver branches whose only consumed OBs are `DefaultOpeningBook2` (50) and `DefaultOpeningBook` (4). Our `LiveOpeningBook2` / `LiveOpeningBook` are byte-identical to those. Full structural diff: `docs/scratch/iterator_diff_report.md`. **PrismataAI.exe compiled-in-OB question still open** — the prior strings-dump check is weak for structured binary tables; DeadGameBot's MB-level strength wrapping the .exe is consistent with either hypothesis.

**DeadGameBot live** — Plays casual games on the Prismata server using the SteamAI bridge. First live replay Mar 31. State-tracker work ongoing.

**Active work items (RL campaign, regime v3):**
1. **Run iteration 1**: `eval/run_iteration.ps1 -K 1` (~1032 self-play games + 576 eval games);
   then promote-unless-harm (`eval/promote_candidate.ps1 -K 1` unless REJECT / tripwire /
   REPRODUCED tactical regression); record the entry in `eval/campaign_log.md`.
2. **Iter-1 watch-stats**: the 4.6 prediction-movement probe (fixed-probe mean|dP| ≲1e-4 = null
   update), stage-8 `ig_contrast_pairs` (~0 = targeted ε not reaching the axis), late sampled
   fraction, game length.
3. **Checkpoint at K=3–5**: `eval/run_checkpoint.ps1` — the powered origin eval carries the
   campaign's evidence; kill criteria read CHECKPOINT trend, not per-iteration cells.
4. **Deferred one-off measurements**: B4 128-game cross-path bound (steam yardstick is trend-only
   until then); B7 (N,c) discrimination re-probe at c=0.15/N=4000 (rl_campaign §1f — first lever
   if checkpoints look exploration-starved).
5. **Next RL axis after IG** (owner): OB / 3rd-Engineer openings — the Engineer:2 cap (`EconLimits` + `BuyGK_Filter` exclusion) is live-faithful, so unlocking it is an RL axis, NOT a fidelity fix.

**Older / parked:** verify `PrismataAI.exe` compiled-in OBs; DeadGameBot state-tracker divergence after MB turns; `Odin` in the live `Ability_Filter` (SWF has it, local doesn't).

## What This Project Is

A C++ game engine and AI for **Prismata**, a turn-based perfect-information strategy card game by Lunarch Studios. The engine simulates game states, the AI uses Alpha-Beta search, UCT/MCTS, and a PartialPlayer phase decomposition system (Defense, ActionAbility, ActionBuy, Breach).

## User Preferences

- **Cost-conscious about AWS / cloud spend ONLY** — prefer local compute, minimize cloud (AWS) spend. This does **NOT** extend to Claude/Anthropic usage: sessions rarely hit the 5-hour usage cap, so **never restrict Workflow, subagents, model choice, or how thoroughly a session works on token-cost grounds.** Token cost is not a constraint on Claude Code usage.
- Git comfort: "noob" — not well versed with git, so **proactively recommend the best-practice approach and explain the why briefly** instead of waiting to be asked. Don't ask permission for routine local work (branching, staging, committing) — just do it sensibly and say what you did. Only pause to confirm before actions that leave the machine or are hard to undo: pushing to a remote, force-pushing, or history rewrites (rebase, `reset --hard`, filter-repo). Push to the `PrismatAlpha` fork, never the `davechurchill` upstream, and never open PRs against upstream.
- The user is "Surfinite" everywhere

## How to Build and Run

> ⚠️ **LEGACY — this builds `engine_v2` (this repo's indicted clean-room C++).** For current AI/engine work do NOT build this; use the dave-master engine (see "⚠️ WHICH ENGINE" at the top). This section is kept only for the legacy clean-room pipeline.

Build via the Visual Studio solution in `visualstudio/`. Three executables:

- **Prismata_GUI** — SFML-based GUI for watching AI vs AI games
- **Prismata_Testing** — Engine unit tests + tournament runner
- **Prismata_Standalone** — Console-based tournament runner (no GUI)

**Build notes:**
- Build the full solution `visualstudio/Prismata.sln`, not individual `.vcxproj` files
- MSBuild path: `C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe`
- **x86 only**: Debug|x86, Release|x86, Static Release|x86. No x64 configs.
- Debug builds have `_d` suffix: `bin/Prismata_Testing_d.exe`
- **MSBuild from Git Bash**: `"/c/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe" "c:/libraries/PrismataAI/visualstudio/Prismata.sln" //t:Rebuild //p:Configuration=Debug //p:Platform=x86 //m`
- **Always use `/t:Rebuild`** (not `/t:Build`) — incremental builds may not relink the exe
- **File lock**: Cannot rebuild while exe is running (LNK1104 error). Stop tournaments first.
- **Static Release config**: If adding new source dirs, check Static Release has matching include paths.
- **CI build uses `/p:PlatformToolset=v143`** (VS 2022) since runners don't have v145.

**Legacy PrismataNet pipeline:** Superseded by DeepSets. See `training/train.py --help` and `training/export_weights.py` if needed.

**Matchup runner (JS engine):**
```bash
node js_engine/matchup_clean.js --games 10 --parallel 4 --think-time 3000
node js_engine/matchup_clean.js --player SteamAI --steam-difficulty HardestAI --games 10
node js_engine/matchup_clean.js --player-white DSNN_MBonly --player-black SteamAI --steam-difficulty HardestAI --games 2048 --parallel 8 --player-switch --think-time 7000 --save-replays DSNN_MBonlyVsMB
```

**Replay viewers:**
```bash
# Per-game HTML from matchup replay JSON:
node js_engine/replay_to_html.js bin/asset/replays/.../game_0001.json

# Build self-contained viewer (15MB HTML, all card art embedded):
node js_engine/build_replay_viewer.js [output.html]
# Output: bin/prismata_replay_viewer.html — drag-drop .json.gz or enter replay code
```

**Expert replay pipeline** (at `c:\libraries\prismata-replay-parser\`):
```bash
node fetch_expert_replays.js    # fetch from API (incremental)
node filter_expert_replays.js   # filter (instant)
node extract_training_data.js   # ⚠️ DEPRECATED — stale ./lib (Feb 2026) TS parser; NOT for training data (see Training pipeline)
```

**Training pipeline (current — DeepSets, FAITHFUL js_engine extractor):**
> ⚠️ **Human extraction MUST use `js_engine/extract_training_jsengine.js`** — it replays each
> `commandList` click-by-click through PrismatAlpha's OWN faithful JS engine (`Analyzer`; turn-START
> snapshot via `beginTurnHistory`) and emits **V2 records DIRECTLY** via the SAME `extractTrainingExampleV2`
> the MB corpus uses (validate-and-drop unfaithful replays → `<output>.dropped.txt`). The OLD
> `prismata-replay-parser/extract_training_data.js` → `convert_human_to_v2.py` path uses a **stale
> third-party TS parser (`./lib`, Feb 2026)** that silently diverges from MB on card_set / turn_number /
> p0_attack — **DEPRECATED; do NOT use for training data.** (`human_1800_v2` was built with the faithful
> extractor — verified Jun 6 via `card_set`=8.4 advanced-only vs the old path's 19.2.)
>
> ✅ **train↔inference feature consistency — RESOLVED v2.2.1 (Jun 7).** Four silent skews fixed, ALL in the
> FEATURE layer (not the engine): (1) `in_card_set` = base + advanced randomizer (tokens excluded = C++
> `numCardsBuyable()`); count-agnostic — NEVER hardcode 8 advanced (sets span Base+5..11+). (2) `supply` =
> REMAINING (`whiteSupply - whiteBought`), not the constant initial cap. (3) `is_blocking` = the SWF
> `inst.blocking` blocking-mode flag (defense contribution), NOT `blocking && role==ASSIGNED` (a blocker
> stays role=DEFAULT; MOVE_DEFEND never sets ASSIGNED); C++ = `getType().canBlock(status==Assigned) &&
> !isUnderConstruction()`. (4) inference used non-serialized `abilityUsedThisTurn()` → now role/`canBlock`.
> MB was already correct (verified feature-identical: 1000-game + C++ cross-check). Deployed:
> `neural_weights_mixed_v221.bin` (SWA RL init; parity 1.09e-06; MB-val 0.3458/81.8% == v2.2). **GATE:
> `training/tests/test_three_way_feature_parity.py` (JS extractor == C++ exporter == C++ inference) — run
> before ANY feature/extractor/exporter change.** Details: `docs/dsnn-feature-schema.md` v2.2.1 changelog.
```bash
# 1. Extract human replays → V2 JSONL DIRECTLY (no convert step; codes pre-validated from JSON):
node js_engine/extract_training_jsengine.js \
    --codes c:/libraries/prismata-replay-parser/final_training_codes_1800.txt \
    --replays-dir c:/libraries/prismata-replay-parser/replays_archive \
    --output training/data/human_1800_v2.jsonl

# 2. Vectorize: V2 JSONL → HDF5 (15-global v2.2.1 via schema_v2.json)
python training/vectorize_v2.py \
    --input training/data/human_1800_v2.jsonl \
    --output training/data/human_1800_v2.h5 --schema training/schema_v2.json

# 3. Train DeepSets model (data_dir then model_dir)
python training/train.py training/data training/models/deepsets_human \
    --model deepsets --streaming --epochs 100 --batch-size 512 --lr 3e-4 --patience 15

# 4. Export weights (DSN2 binary for C++ inference)
python training/export_weights_v2.py \
    training/models/deepsets_human/best_model.pt \
    bin/asset/config/neural_weights.bin
```

## Gotchas & Non-Obvious Patterns

> Cloud provider operational details: `docs/cloud-ops-reference.md`
> Extended gotchas (dashboard, sniffer, commentary, cloud ops): `docs/CLAUDE_REFERENCE.md`

### Engine & Build

- **C++ feature/parity tooling** (dave-master `Prismata_Standalone`): `--dump-v2-record <stateJson> <out>` = run the V2 EXPORTER (`V2Record.cpp`); `--dump-features <stateJson> <out> <weights.bin>` = run INFERENCE (`NeuralNet.cpp`) → tokens/supply/globals/value. Both parse a gameState JSON (run from anywhere w/ absolute paths; soft asserts "Unknown Card instance property" are harmless). `js_engine/dump_shared_state.js <replay> <ply> <prefix>` emits the paired cppstate+jsrecord. SelfPlayV2Exporter also writes native turn-start states to `<exportTrainingV2 dir>_parity/sp_<g>_<ply>.json.gz` (gzipped + PER-export-dir since 2026-06-12 — a shared sibling dir let same-launch blocks overwrite each other; parity tooling reads .gz directly; compare exporter↔inference with NO `stateToCppJSON` round-trip — which drops `abilityUsedThisTurn` + instance `damage`). **run_iteration stage 1.5 ARCHIVES sidecars + self-play replays into `training/data/rl_iter_<K>/{parity_states,replays}/`** — the future-schema re-extraction source (replay turn-start state = `states[p==0 ? 0 : turnBoundaries[p]-1]`). Replay + V2 shard share ONE per-game id (`game_0007.json.gz` IS `selfplay_0007.jsonl`'s game, Threads-safe since the O1 fix).
- **C++ replay consumption traps**: `numTurns` = ENGINE convention (= JS replays' `numTurns` − 1) — use the explicit `turn` field, never numTurns parity; turn-start state = `states[p==0 ? 0 : turnBoundaries[p]-1]` (JS-written fleet replays use `states[turnBoundaries[p]]` — don't reuse `extract_fleet_training_data.py` on C++ replays unmodified); `GameState::initFromJSON` silently discards instance `damage` + targeting, so only TURN-START states re-extract cleanly (mid-defense frames with partially-damaged blockers re-parse wrong).
- **Binary staleness: never infer from mtime vs commit time** (build-before-commit is the norm here). Grep the exe for a new diagnostic string instead, e.g. `grep -c "FATAL: AIParameters" bin/Prismata_Testing.exe`.
- **Isolated engine experiments**: copy `Prismata_Testing.exe` + `asset/config/` into a scratch dir (+ empty `tests/`, `asset/training/`, `asset/replays/`) and run from there — e.g. `eval/_audit_scratch/bin_audit/`. Never edit the real `bin/asset/config/config.txt` for probes; the exe is self-contained (no DLLs).
- **dave-master build (= "v145" = VS 18 / 2026; `cmake` NOT on PATH)**: `"C:/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe" build/Prismata_Standalone.vcxproj //p:Configuration=Release //p:Platform=x64 //m //v:minimal` (also `build/Prismata_Testing.vcxproj`). Output → `bin/`. `bin/PrismataAI.exe` is a manual copy of `Prismata_Standalone.exe` (not a CMake target).
- **dave-master has NO C++ unit-test framework** (no gtest); unit-test pure C++ via a standalone `bin/PrismataAI.exe --test-X` PASS/FAIL probe in `source/standalone/main.cpp` (pattern `--test-rng`/`--test-sampler`/`--test-stalemate`). A header-only struct + a probe needs no `.vcxproj` edit. **After ANY dave-master rebuild: re-pin `engine_testing_exe_sha256`/`engine_prismataai_exe_sha256` in `campaign_frozen.json` + re-run a6/three-way**, or preflight's `engine_sha`/`correctness_gates` fail. Build heavy (~min) — batch C++ edits, build once; C++ tasks can be committed un-built (the build is a separate gate).
- **Self-play/eval stalemate draw rule (LIVE 2026-06-17)**: a frozen game (board `(owner,cardType)` multiset over LIVE units unchanged for `StalemateThreshold`=40 plies) ends early as a 0.5 draw; self-play ALSO trims the frozen tail (kept-length `total_plies`; eval is early-end only). C++: `source/testing/StalemateTracker.h` + the `TournamentGame.cpp` loop (`buildPopulationMultiset`) + `SelfPlayV2Exporter::finalize` trim + `Tournament` reads `StalemateThreshold`. Python oracle (the C++ MUST mirror it): `eval/stalemate.py`; probe `--test-stalemate`. Frozen `selfplay_stalemate_threshold` (scale-tier) + preflight `check_stalemate_threshold`. Spec/plan: `docs/superpowers/{specs,plans}/2026-06-16-selfplay-stalemate-draw-policy*`.
- **Internal name system**: Engine uses codenames (e.g., "Tesla Tower" = Tarsier, "Brooder" = Blastforge). Full mapping in `cardLibrary.jso`.
- **AS3↔C++ naming dictionary**: `role`=`CardStatus`, `disruptDamage`=`m_currentChill`, `MOVE_MELEE`=`ASSIGN_FRONTLINE`, `glassBroken`=breach flag (not a phase — no `Phases::Breach` equivalent in JS), `MOVE_ASSIGN`=`USE_ABILITY`, `MOVE_DEFEND`=`ASSIGN_BLOCKER`. Full dictionary in `docs/plans/engine-logic-audit-plan.md`.
- **Two git remotes**: `origin` = davechurchill upstream, `PrismatAlpha` = user's fork. Push to `PrismatAlpha`.
- **`PrismataAI-dave-master` is a git WORKTREE of the main repo, not a clone** (started as a fork; now `git worktree add`-ed). It SHARES main's `.git` (object store + branch namespace): its `.git` is a file → `gitdir: …/PrismataAI/.git/worktrees/PrismataAI-dave-master`, `git-common-dir` = main's `.git`. Several dave-* worktrees exist (`git worktree list` from main: `dave-master`, `dave-fixes`, `dave-mc`, `dave-preport`) at sibling `C:/libraries/PrismataAI-dave-*` paths (NOT under `.worktrees/`). So commits in either repo share one object DB; both branches (`feature/production-vectors`, `dave-master-jsonclean`) track `PrismatAlpha`; helper scripts that use `git rev-parse --git-path` resolve under main's `.git/worktrees/`.
- **Deployable `neural_weights_*.bin` are git-tracked in the MAIN repo `bin/asset/config/`**; a working copy lives in `dave-master/bin/asset/config/` (where the dave engine reads). Export to dave-master; commit the tracked copy in main.
- **Steam drop-in bundles (per checkpoint)**: `eval/build_steam_bundle.ps1 -Label <name>` packages a net (default = frozen lineage head) → `C:/libraries/DSNN_steam_bundles/<name>/`; **self-describing** (`use_dsnn.txt` `weights=<bin>` key — precedence `use_dsnn.txt weights=` > `PRISMATA_DSNN_WEIGHTS` env > built-in default; no env var / no renamed `.bin`) + **self-verifying** (drives FORCE_DSNN, asserts the net loads + `treeIterator=HardIterator_5var_NoIG` + `mappedTypes>0` + a move). FORCE_DSNN deploy path (engine `dave@50977510`+) = root `HardIterator_5var_IGsubset_Root` + interior **`HardIterator_5var_NoIG`** (now matches the campaign's measured action space; bundles ≤ v221 used the IG-included interior). The script REFUSES an exe whose sha ≠ frozen pin → re-pin after any rebuild first. Bundles live OUTSIDE the repo (not tracked). Detail: `eval/rl_runbook.md` "Building a Steam bundle".
- **Branch can switch unexpectedly**: Always `git branch --show-current` before branch-dependent operations.
- **Config tournament toggles**: Check `"run":true` in `config.txt` before launching.
- **Feature schema contract (DeepSets, current = v2.2.1)**: doc `docs/dsnn-feature-schema.md`; machine source `training/schema_v2.json` + `training/property_table.json`. Token = 32 embed + **37 static** + 10 instance = **79**; **15 globals** (incl. `under_attack`); value head 303. `schema_version` stays `v2` (= DeepSets generation); use `feature_revision` for additive changes. **Static props flow via the DSN2 `.bin` header → no C++ edit**; a GLOBAL change needs `vectorize_v2.py` + the per-global *construction* in dave-master `NeuralNet.cpp` (`evaluateValue` build + the `if (num_global>=N)` guard) + bumping `model_deepsets.py`'s default `num_global`. The global *count* now auto-derives from the value-head width at load (`NeuralNet.cpp` `COMBINED`/dump loop, `export_weights_v2.py`, `compare_parity_deepsets.py`) — no manual count edits. Engine loads either supported count (14 or 15) from the `.bin`; a width implying an unsupported count warns (`dave@481f916`).
- **Legacy flat schema (PrismataNet)**: `training/schema.json` + `training/FEATURES.md`, state_dim=1785. Kept for the value-only baseline; not the current path.
- **Per-player NN weights**: Players with `"WeightsFile":"neural_weights_X.bin"` in config.txt auto-load their weights in `--suggest` mode. `--weights <path>` CLI arg overrides. Weight files live in `bin/asset/config/`.
- **DSNN players**: `DSNN_MBonly` (ep98, 82.4%), `DSNN_MBonly_SWA` (SWA avg), `DSNN_Human` (ep26, 78.2%). All use UCT + NeuralNet eval + the `LiveHardestAI_Root` move iterator. Its OB consumption (via `Live_BuyOpeningBook2` in the CS2 portfolio branch → `LiveOpeningBook2`) is byte-identical to what live MB uses (May 16 verification).
- **SWF aiParameters routing**: SWF embeds two parameter blobs — full (`tmp_swf_extract/148_*.bin`) and short (`tmp_swf_extract/93_*.bin`). AS3 `aiNoOpenings` list at `prismata_decompiled/scripts/AI/AIThreadHandler.as:110` routes `HardestAI`/`MediumAI`/etc. to the SHORT blob; everything else gets the FULL blob. The variable name is misleading: the short blob still defines 7 OBs (120 entries total), but each player config consumes specific ones via its iterator chain. For `HardestAI`/`NewIterator_Root` the only consumed OBs are `DefaultOpeningBook2` (50) and `DefaultOpeningBook` (4), reached transitively through `ACAvoidBreach_ChillSolver*` → `ACEasy*` → `BuyOpeningBook*`. Whether `PrismataAI.exe` *also* has compiled-in OB tables is unverified (the May 14 strings-dump check is weak for structured binary data).
- **OB parity verified (May 16)**: Local `LiveOpeningBook2` ≡ SWF `DefaultOpeningBook2` byte-for-byte (50 entries); local `LiveOpeningBook` ≡ SWF `DefaultOpeningBook` (4 entries). The portfolio structure of `LiveHardestAI_Root` mirrors `NewIterator_Root` exactly. The only structural delta in the chain is `Ability_Filter` missing `Odin` locally (SWF: `[Drake, Grenade Mech, Odin]`, local: `[Drake, Grenade Mech]`) plus two intentional local additions (`AbilityAvoidDefenseWaste`, `AbilityAvoidResourceWaste`). Full diff: `docs/scratch/iterator_diff_report.md`; reproducer: `docs/scratch/diff_iterator_chains.py`. ⚠️ **Scope: this verdict covers the MAIN-repo (engine_v2) config only** — `diff_iterator_chains.py` hard-codes this repo's config and was never run against dave-master. The Jun-10 audit (F-09) found dave-master's **buy tree diverges from the SWF in 4 partials** (missing `BuyEconFast`; `BuyEcon`/`BuyOneDrone`/`BuyEconLimited` differ — inherited unchanged from Dave's 2020 open-sourcing, a pre-refactor aiParameters vintage) **and its `DefaultOpeningBook` is a 5-entry Vivid-Drone book vs the SWF's 4-entry Doomed-Drone book**. **SWF-faithful port LANDED `dave@09c5436` (Jun 10)**: buy tree (`BuyEconFast` added; `BuyEcon`/`BuyOneDrone`/`BuyEconLimited`/`BuyTechEcon` corrected, each json-asserted equal to the SWF blob) + the 4-entry `DefaultOpeningBook` (byte-identical to THIS repo's `LiveOpeningBook`) + the `DefaultLimits` Mobile-Animus cap; `EconLimits`/`EconLimits15` already matched the SWF — untouched. ⚠️ This created a **historical-baseline discontinuity**: pre-Jun-10 numbers (cValue sweep, May 17-18 parity/DSNN results, Jun-8 anchors) were measured against the pre-port config — see `eval/rl_campaign.md` §1c.
- **NeuralNet singleton (engine_v2 ONLY)**: engine_v2 routes all NN eval through `NeuralNet::Instance()` — can't pit two NN players in one process there. **dave-master gives each player with a `WeightsFile` its own net, deep-cloned per game/thread** (`UCTSearchParameters::deepClone`) — NN-vs-NN in one process at `Threads:8` is fine (audit-verified Jun 9-10). Hazard: on a weights-load FAILURE dave-master silently falls back to the unloaded shared singleton → segfault mid-run (Jun-10 audit X5b); a hard-fail guard is on the fix list.
- **PRISMATA_ASSERT**: Soft assert — prints to **stdout**, does NOT abort. Use `std::ifstream` instead of `FileUtils::ReadFile` when stdout must stay clean.
- **Engine hard-fail guards (dave `26075fa`/`d0ec633`/`6e93480`)**: unknown/raw-empty opening book, unknown filter/iterator/partial/player name, NN weights-load failure, and an unloaded net reaching the UCT value path all `FATAL:` + `abort()` (exit 0xC0000409). PRISMATA_ASSERT stays soft everywhere else. Books *filtered-to-empty by the card library* WARN once instead (legitimate on the Steam merged-deck path — the R_* books).
- **Tournament per-seat stats + slot attribution (dave `6e93480`)**: statsTable has `P1 W/G`/`P2 W/G` columns; results are credited by SLOT index, so same-name self-match blocks are legitimate (rows render `Name (gN)`; the old first-name-match `-nan` bug is gone).
- **2016 MasterBot baseline**: permanent home `c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe` (sha-pinned README in-dir; the Steam-dir `.ORIG` remains as backup). run_eval's steam anchor + matchup tooling point here — never at the Steam install (whose live exe is our DSNN swap-in).
- **query_move.js defaults**: WIDENED `HardIterator_5var_IGsubset_Root` + `UCTConstant 0.3`, echoed to stderr per run. Pass `--root-iterator HardIterator_5var_Root` to probe the narrow (auto-fire) space deliberately.
- **Fast C++ defense eval**: `query_move.js` at `think_time=0`/`max_traversals=1` returns defense-correct picks (<0.5s/process) — the defense `PartialPlayer` (`BlockIterator`) runs before/independent of the UCT search, so the budget never affects block assignment (only the action half degenerates). Drive a steam-bundle exe (e.g. `DSNN_steam_bundles/v221_rl_iter8`).
- **query_move.js eats raw F6 `.txt` dumps directly** (`parseRequestFile` brace-matches the `"CurrentInfo"` object out of the multi-section blob — no separate extractor needed). An F6 dump = `"CurrentInfo":{mergedDeck,gameState,aiParameters,aiPlayerName}` + `"TurnStartInfo":{…}` + trailing plain-text `VOU [Unit] chN hpM val=…` debug lines (a VOU-instrumented SWF build appends these; board state is still fully recoverable, and such dumps can be ACTION-phase, not only the historical pre-swoosh DEFENSE). To run `action_coverage.py --battery`, convert dumps → clean `*.json` (see `eval/build_ma_battery.py`).
- **x86 OOM — 4 threads max per process (engine_v2 x86 builds ONLY)**: `/LARGEADDRESSAWARE` = 4GB. Use `"Threads": 4` + multiple bat instances. Process dies silently at ~1400 games. dave-master builds x64 — not affected.
- **Console output routing**: `[SelfPlay]`/`[Progress]` use `fprintf(stderr, ...)`. New Tournament.cpp messages should use stderr.
- **Tournament `tests/` directory required**: `HTMLTable::appendHTMLTableToFile()` crashes if `tests/` doesn't exist.
- **Prismata client architecture**: Adobe AIR/Flash app. Memory reading infeasible — use clipboard or network proxy.
- **Clipboard game state export**: F6 copies JSON to clipboard. Requires SWF dev mode patch. JSON key is `"CurrentInfo"` with `mergedDeck`, `gameState`, `aiParameters`. Card names are **display names**.
- **SWF developer mode patch**: Single byte at decompressed offset `0x1580196`: `0x27`→`0x26`. Requires hosts entry for load balancing bypass.
- **JS engine is faithful to the AS3 client (faithfulness campaign COMPLETE, May 2026)**: replays the full 61,267-replay human corpus with only 33 residual failures — all recordings the *official client itself cannot replay* (rare client recording / live-vs-replay bug, persisted to 2020, ~0.05%). Our engine faithfully reproduces those failures; do NOT "fix" them (that would diverge from the client). The headline fix was porting AVM2 `Dictionary` for-in order into `AS3Dictionary.js` (begin-turn token instIds). Faithfulness meter: `js_engine/corpus_scan.js`; AS3 ground-truth diff: `js_engine/oracle_diff.js` (needs an F6 dev-mode dump). Full write-up: `docs/jsengine-faithfulness-results.md`.
- **matchup_clean.js auto end-swipe**: Applies to ALL AIs. Without it, stale BREACH swipes block OVERKILL clicks.
- **matchup_clean.js confirm→defense auto-commit**: Auto-inserts commit click when confirm phase has incoming defense clicks.
- **SteamAI is one-shot**: `PrismataAI.exe` exits after each response. Must spawn fresh process per turn. EPIPE if you reuse stdin.
- **SteamAI protocol differs from MCDSAI**: SteamAI gets ALL 4 fields every turn (mergedDeck, gameState, aiParameters, aiPlayerName). MCDSAI only gets gameState + aiPlayerName per turn.
- **Don't add LiveHardestAI resignation until click verification (V11) is complete**: Early resignation hides click failures.
- **matchup log false positives**: Use `grep -E "[1-9][0-9]* failed"`, not bare keyword grep.
- **Move representation**: `Player::getMove(state, move)` returns `Move` (sequence of `Action`s). BUY resolves via `CardType(action.getID()).getUIName()`.
- **`--suggest` CLI mode**: `Prismata_Testing.exe --suggest state.json [--player PrismatAlpha_AB] [--think-time 3000] [--weights path/to/weights.bin]`. Output includes `"clicks":[{_type,_id},...]` for wire protocol. If `--weights` is omitted, uses the player's `WeightsFile` from config.txt.
- **mergedDeck buyCost format**: Digits = gold, `G` = green, `B` = blue, `C` = red, `H` = energy.
- **Mana/script codes** (buyCost, `receive`, abilityCost): digits/bare-int = gold, `G`=green, `B`=blue, `C`=red, `H`=energy, `A`=attack. Quantity is letter REPETITION; a leading number is gold only — `5G` = 5 gold + 1 green (Thorium), `3BBCCGG` = 3 gold/2 blue/2 red/2 green.
- **Replay commandList format**: `_type` (NOT `_action`) and `_id`. `clicksPerTurn` slices commandList. `playerInfo` has NO `playerNumber` key — use array index.
- **Click counting ≠ buy counting (CRITICAL)**: `card clicked` does NOT guarantee purchase. Must enforce supply limits.
- **Replay JSON structure**: `deckInfo.mergedDeck` for card data. Derive supply from `rarity`: legendary=1, rare=4, normal=10, trinket=20.
- **C++ `eval_pct` is a string with `%` suffix**: Strip `%` before `float()`.
- **prismata-replay-parser git config**: Must set `git config user.name "Surfinite"` locally before first commit.
- **SQLite trigger DDL splitting**: Never split on `;` — split on `END;` boundary.
- **`build_replay_db.py --source X` wipes the DB**: Always use `--incremental --source` for partial updates.

### Live Spectating (<ladder> repo)

- **Prismata server sends `Moved` during login**: Load-balancing redirect. `login()` must handle it or auth times out silently. Fixed in `headless_client.py`.
- **React `useState` drops rapid WebSocket messages**: Batching means only the last message survives per render. Use queue-based hook (`useWebSocket.ts`) with `drainMessages()`.
- **Late-joiner cache race condition**: Server adds client to subscribers before sending cached history. Live clicks can interleave with cache replay. Fixed with seq-based dedup on client.
- **`npx next build` needs `--webpack`**: Next.js 16 defaults to Turbopack which fails with webpack config.
- **VPS spectator files must be in repo**: `ws_broadcast.py`, `spectator_bridge.py` were VPS-only and got lost on deploy. Now tracked in git.
- **`prismata_amf3.py` is the canonical module name**: Renamed from `prismata_sniffer.py`. Deploy script and all imports updated.
- **S3 replay URL must be HTTPS**: `https://saved-games-alpha.s3.amazonaws.com/` (not `s3-website`). HTTP causes mixed content block on HTTPS sites.
- **VPS deployment / prismata.live ops**: tracked in the separate **prismata-ladder workspace** (not this repo). Deploy scripts, credentials path, python symlink, disk constraints, and deploy keys live there; this repo keeps only the durable spectating gotchas above.
- **AWS default region is `eu-north-1`**: prismata.live infra is in `us-east-1`. Always pass `--region us-east-1`.
- **ARM Ubuntu 24.04 has no `python` command**: Only `python3`. Subprocess calls to `python` fail silently. Data box has `/usr/bin/python` symlink.
- **SSH to data box**: `ssh -i ~/.ssh/<SSH_KEY>.pem -o ProxyCommand="ssh -i ~/.ssh/<SSH_KEY>.pem -W %h:%p ubuntu@<SITE_EIP>" ubuntu@<DATA_BOX_PRIVATE_IP>`
- **Client7 is PrismataLiveBot**: Replaced SpectatorBot3. Login fails if the account is already logged in elsewhere (Prismata allows only one session). Running several spectator bots.
- **S3 export prefix is `exports/`**: Not `site-data/`. Data box uploads here, site box syncs from here.
- **`headless_multi.py` has no `--quiet` flag**: Only `--add-account`. Don't add unknown flags to systemd ExecStart.

### Self-Play & Data

- ⚠️ **Several items below describe the LEGACY engine_v2 self-play pipeline** (binary shards + CRC, `SelfPlay_CI` playout generation, timestamped `run_*` dirs, PID-based seeding, value-only 26-tensor export). Current RL self-play = **dave-master**: JSONL V2 export (`SelfPlayV2Exporter`), NN-guided sampled UCT, unconditional colour-swap, per-block seedable `thread_local` RNG, Threads:8-safe. See `eval/rl_runbook.md`.
- **RL campaign is now v4 "proof-of-life"** (reframed from regime v3 IG-axis): contract = `eval/campaign_frozen.json` (`tuple_version` 4) + spec `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`; Phase-0 validated (loop runs end-to-end, real candidate). The top-of-file "Current Status" regime-v3 narrative is **superseded**.
- **The Phase-1 loop is MANUAL**: `eval/run_iteration.ps1 -K <k>` → inspect manifest + watch-stats → `eval/promote_candidate.ps1 -K <k>` → `-K+1`; checkpoint every 3–5 via `eval/run_checkpoint.ps1 -Iteration 0`. `eval/run_phase1_loop.ps1` is a DRAFT chaining wrapper (HALT-on-abort / file-lock bounded-retry / config self-heal) for unattended runs.
- **Commit dave `config.txt` only at a QUIESCENT boundary** (after `promote_candidate`, before the next `run_iteration` launch): during self-play the block is flipped `run:true` (restored to `false` in a `finally`), so committing mid-run captures a preflight-invalid config.
- **`MaxChildren` is NOT preflight-pinned** (preflight pins only `MaxTraversals`==frozen_N + the `eval_budget` keys); it's observe-only / scale-tier, so widening it for a wider action-space axis (opening IG×MA needed 40→80) is a re-anchor + a `campaign_log` entry, NOT a new campaign. (HP knobs — N/τ/K/ε/c/lr/iterators — ARE a new campaign.)
- **Opening an AbilitySubset axis (IG, MA, …) is config-only** (no rebuild): add the unit to the subset filter (`IG_Only`) AND the interior exclusion (`Ability_Filter_Live_NoIG`); the existing `HardIterator_5var_IGsubset_Root` then branches on the per-unit fire-count cross-product automatically. Result so far: both IG and MA = clean integration, ~parity over v221 (no powered gain) — the value-only fixed point.
- **RL driver reuse without re-running self-play**: `run_iteration.ps1` WIPES the live export dirs (`rl_general_v2`, `_parity`, replays) at stage 1. To reuse an existing ~95-min self-play after a downstream crash, pre-stage `training/data/rl_iter_<K>/{parity_states, replays/general}` + concat shards → `selfplay_iter_<K>.jsonl`, then `-ResumeFrom 2` (skips stages 1/1.5; requires catJsonl + parity_states present).
- **RL parity gate + sidecar names**: stage 5 (`tools/parity/dump_value_batch.py`) samples max 1000 sidecars (`--max-states`), so it stays fast on 36k-record runs. Archived sidecars carry a `general_`/`forced_` slice prefix; the live exporter writes unprefixed `sp_*.json.gz` (a glob that assumes one form misses the other — caused a stage-1.5 re-run collision, fixed `d319ef62`).
- **SkipColorSwap auto-detection (engine_v2 ONLY)**: the legacy engine_v2 self-play auto-detects identical AI configs (`rounds = desired_games`). **dave-master has NO SkipColorSwap** — its `Tournament.cpp` colour-swaps unconditionally (every cross-group pair plays both seat orderings of a shared per-round card set; same-group pairs play zero games). Treating this gotcha as universal derailed the Jun-9 audit's recon.
- **Self-play crash safety**: Timestamped `run_*` subdirs. Restart anytime — only in-flight games lost.
- **Selfplay shard CRC**: Use `validate_crc=False` for live/crashed data.
- **Selfplay positions per game**: ~37 records/game (both players' turns).
- **Real Prismata sets are Base+5 OR Base+8–11** (not always 8); human training data spans these. Self-play at B+8-only under-covers the deployed distribution.
- **Selfplay shard binary format**: Header 64 bytes + 4-byte CRC32 footer. Record size = 7152 bytes.
- **Selfplay game counting**: `python -c "import os; base='bin/training/data/selfplay'; total=sum((os.path.getsize(os.path.join(r,f))-68)//7152 for r,_,fs in os.walk(base) for f in fs if f.endswith('.bin') and os.path.getsize(os.path.join(r,f))>68); print(f'{total} records, ~{total//37} games')"`.
- **Self-play uses playout eval**: `SelfPlay_CI` runs `OriginalHardestAI_1s` vs itself. Neural net NOT used for generation. ~4 games/min per 4-thread process.
- **P2 wins ~57% in current AI matchups**: Real observed asymmetry, not a data quality issue. The *cause* isn't fully settled — the extra Drone is compensation for going second, not an advantage in itself. Community view is it may equalise under strong-enough AI.
- **PID-based random seeding**: `srand(time ^ PID)` prevents identical sequences.
- **Value-only model export**: `export_weights.py` exports zero-initialized policy tensors. C++ requires all 26 tensors.

### Training

- **DeepSets offline eval on an H5**: `eval/eval_deepsets_h5.py --model <best/swa_model.pt> --val-file <h5>` (reuses train.py `eval_epoch`; CPU default to avoid XPU contention; handles SWA ckpts). Legacy `training/evaluate_model.py` is flat-PrismataNet ONLY — won't load DeepSets. `mixed_35prop.bin`=14-global, `mixed_v22/v221.bin`=15-global (match weights' global count to the schema for `--dump-features`).
- **V2 self-play H5 label columns are `label_A`/`label_B_weight`/`label_C`/`label_D`** (NOT `labels`/`outcome_p0` — those don't exist as H5 datasets); `label_A` is the **raw game outcome** (`outcome_p0`; P0 win=1.0 / loss=0.0 / draw=0.5) stamped **identically on every ply — it is NOT ply-discounted** (`vectorize_v2.py::compute_labels`: `label_a = float(outcome_p0)`; the ply-dependent columns are `label_B_weight`, a per-record *sample weight*, and the prior-blended `label_C`/`label_D`). The RL loop trains on **strategy A** (`train.py` default; `run_iteration.ps1` passes no override). A naive record-weighted `label_A` mean ≠ self-play P0 win-rate only because longer games contribute more records — dedupe to one record/game (`ply_index==0`) to read P0 win-rate (cf. `eval/calibrate_n.py::metrics_from_h5`). `total_plies` per record = the KEPT (stalemate-trimmed) game length.
- **`train.py --rl-mode` REQUIRES `--init-weights`** (warm-start from the parent `.pt`; hard-fails without — the E1 random-init bug guard). Warmup auto-rescales for short RL runs (`resolve_warmup`); pass `--swa-lr` explicitly (the default lr×0.1 equals the 1e-6 floor at the RL lr of 1e-5 — N-1 bug).
- **RL self-play null-update trap**: `train.py --batch-size` default = 512 (with `drop_last`), so an RL iteration whose self-play yields < ~512 records runs **0 optimizer steps** → candidate bit-identical to the parent (stage-4.6 prediction-movement reads `dP=0.0`). `rounds:4` (~280 recs) hits this; smoke at `rounds>=64` (~4.5k recs); the real run is 516 rounds (~37.9k recs, ~95 min self-play, ~1.5 hr full eval).
- **RL smoke override is TWO files**: to shrink a smoke, set BOTH dave `RL_SelfPlay_General.rounds` AND `campaign_frozen.json` `selfplay_rounds` (stage-0 preflight asserts they're EQUAL), run, then RESTORE both to 516. Eval-block volume (`RL_PoL_origin`/`RL_PoL_masterbot`, 48 rounds) is separate.
- **`vectorize_v2.py` is STRICT by default**: any drop (parse error, wrong schema_version, unknown unit, missing `outcome_p0`, board truncation) → counters + exit 1, no partial H5. Drops at vectorize are NEVER normal — extraction is where legitimate dropping happens. `--allow-drops` = forensic use only.
- **Property table = 37 static props** (token 79 = 32 embed + 37 static + 10 instance); "35prop" survives only in weight FILENAMES (`neural_weights_mixed_35prop.bin`) — don't hardcode 35 in tests/tools.
- **SWA is val-independent**: averages epochs `swa_start..end` regardless of `--val-file`; with `--patience >= --epochs` no early stop, so val only affects `best_model.pt` + the log, not the deployed SWA. `swa_model.pt` = unwrapped `model_state_dict`; `export_weights_v2.py` rebuilds via `PrismataDeepSets()` defaults (37 prop / 15 global).
- **Quick training tests**: Use `--selfplay-dir bin/training/data/selfplay/2026-02-15_11-31-33/` (4 shards, instant).
- **Training CRC**: `train.py` uses `validate_crc=False`.
- **Training RAM limit**: Full dataset = ~50GB+. Use `--streaming` (memory-mapped) or `--max-records 1000000` (32GB).
- **Training RAM: max 2 concurrent jobs** on 32GB.
- **best_model.pt gets overwritten**: Copy to unique filename immediately after run.
- **Training lock file**: `training.lock` in model dir. Auto-cleaned on exit.
- **C++ NeuralNet hidden_dim AND num_layers are dynamic**: Read from weight file header. No C++ rebuild needed.
- **Tournament output needs `2>&1`**: stderr routing.
- **Parallel tournament eval**: Separate `bin_eval_X/` directories.
- **train.py positional args**: `data_dir` then `model_dir`. Must pass both for custom output.
- **XPU training**: `--device xpu --num-workers 4`. 3.2x speedup. BF16 adds overhead — skip.
- **Streaming num_workers=2 on 32GB RAM**: `--num-workers 4` causes 94% RAM, system unusable.
- **Cloud GPU RAM (16GB)**: Must use `--streaming`. g2-standard-8 (32GB) for full dataset. g2-standard-4 OOM-kills.
- **D: drive backup**: `D:\PrismataAI_backup\` has selfplay data, models, weights.
- **Replay `result` field is 1-indexed**: `result=0` = P1 (first player) wins, `result=1` = P2 wins, `result=2` = draw. Training uses 0-indexed: `outcome_p0 = 1.0 - float(result)`, draws → 0.5. Verify P0 win rate <50%.
- **Labels must be in [0,1] for BCE**: Out-of-range labels (e.g. draw=2) cause loss explosion. Validate before training.
- **TF32 disabled for CUDA training**: `train.py` sets `torch.backends.cuda.matmul.allow_tf32 = False` — safety net for small models on Ampere+ GPUs.
- **GCP spot L4 unreliable**: Frequent preemption and stockouts. AWS eu-north-1 spot (g6.2xlarge) more stable for long runs.

### Windows & Python Environment

- **Reading PDFs**: the `Read` tool needs poppler (`pdftoppm`, NOT installed here) and `WebFetch` can't parse PDF text — but `WebFetch` DOES save the raw binary to `tool-results/`. Extract text with **PyMuPDF** (`import fitz`, available): per-page `get_text()` → a `.txt`, then Read/grep that. (Papers cached at `.parity_tmp/papers/`.)
- **Bash heredocs mangle backslashes**: an inline `python - <<'PY'` corrupts backslash string literals (`'\\'`, regex `\d`, `chr(92)` workaround needed) — write the Python to a file and run it instead.

- **`nohup &` broken in Git Bash**: Use `run_in_background` parameter or persistent PowerShell.
- **Python stdout buffering**: Use `PYTHONUNBUFFERED=1`.
- **Python cp1252**: Use `PYTHONIOENCODING=utf-8` or ASCII.
- **`python3` not available**: Use `python` on Windows.
- **Python on Windows needs `C:/...` paths, not Git-Bash `/c/...`** (h5py/open fail on `/c/`). Distinct from `/tmp` ≠ `C:	mp`.
- **Adding a derived global to H5s = re-vectorize-only, not re-extract**: derive it from existing columns and replace the `globals` dataset in place (e.g. `under_attack` from `active_player`+attacks); avoids re-parsing the multi-GB JSONLs.
- **`gcloud` only in Git Bash**: Use full path `C:/google-cloud-sdk/bin/gcloud.cmd` with `shell=True` for subprocess.
- **PowerShell JSON BOM**: Use `encoding='utf-8-sig'` in Python.
- **Git Bash mangles `$_`**: Write `.ps1` script files instead of inline PowerShell.
- **PowerShell `-Include` is a no-op without a wildcard path**: use `Get-ChildItem -Path "$dir/*" -Include 'a','b'` (or `-Filter` for one pattern) — `-Path $dir -Include ...` silently matches nothing without `-Recurse`.
- **Env vars unreliable in bash scripts**: Use `python -c "import subprocess, os; ..."` workaround.
- **Hosts file editing**: Use `[System.IO.File]::WriteAllText()`, never `Set-Content`. Needs UAC.

### Historical / Concluded

- **Blend tournaments**: Neural component hurts. Don't revisit until model >60% val accuracy.
- **Batch validation**: 50.4% pass (1,072/2,127). Remaining failures are genuine TS↔C++ differences.
- **Replay balance validation**: 102,697 training-eligible replays in `replays_archive/`. Full query and re-validation steps in `docs/CLAUDE_REFERENCE.md`.
- **Revalidation is destructive**: Always backup `replays.db` and `balance_results.json` first.

## Claude Code Tooling

**Slash commands**: `/revise-claude-md` (capture session learnings into CLAUDE.md), `/claude-md-improver` (periodic CLAUDE.md audit). Older `/status`, `/selfplay-count`, `/preflight` exist but are stale — don't trust their output without verifying.

**Hooks** (`.claude/settings.local.json`):
- PreToolUse: Blocks access to credential files
- Stop: Reminds to run `/revise`

**MCP**: context7 in `.mcp.json`. `npx`-based MCP servers need `cmd /c` wrapper on Windows.

**C++ style**: `.clang-format` (Allman braces, 4-space indent, 120 col limit).

## Claude Code Behavior

**Session close-out** — when the user says "wrapping up" or "closing context":
1. Check for undocumented results — write to appropriate docs
2. Update stale plan/results docs with actual outcomes
3. Run `/revise-claude-md` for CLAUDE.md updates
4. List anything only in conversation context
5. Save important findings to claude-mem

## Key Architecture

### Engine Internal Name System

Engine uses codenames internally (e.g., "Tesla Tower" = Tarsier). Full mapping in `cardLibrary.jso` (105 competitive + 11 base = 116 units; canonical names in `training/data/unit_index.json`). All script references must use **internal names**, not display names.

### Game Phases & Turn Numbering

From the **player's experience**: Defense (assign blockers for incoming attack) → Breach if wipeout (opponent clicks through undefended units) → Swoosh → Action → Confirm → back to Defense or Swoosh.

From the **engine's internal sequence**: a player's `MOVE_COMMIT` (end of action) triggers the *opponent's* Defense phase, then Swoosh, then the opponent's Action. JS engine has 3 explicit phases: `PHASE_DEFENSE`, `PHASE_ACTION`, `PHASE_CONFIRM`. There is **no `PHASE_BREACH`** — breach is the `glassBroken` flag resolved within the defense/swoosh transition. The old CLAUDE.md sequence "Action → Breach → Confirm → Defense → Swoosh" described engine ownership order but read as the wrong player-turn sequence.

`m_turnNumber` increments once per **player-turn**. **`beginTurn()` runs during Swoosh** (GameState.cpp:1317), NOT at start of Defense. Tapped units cannot block; untapped can. Do NOT reset statuses before Defense.

**Targeting abilities are two-step**: USE_ABILITY on source (sets `m_targetAbilityCardClicked`), then SNIPE/CHILL on target. `"disrupt"` maps to `ActionTypes::CHILL`. 12 units have `targetAction`.

### AI Architecture

**PartialPlayer** phase decomposition: Defense, ActionAbility, ActionBuy, Breach. **HardestAI** = Stack Alpha-Beta + playout eval. **HardestAIUCT** = UCT/MCTS. Both support Playout, WillScore, and NeuralNet evaluation.

**Will Score** heuristic (`source/ai/Heuristics.cpp`): ATTACK=2.25, BLUE=1.50, GREEN=1.20, GOLD=1.00, RED=0.90, ENERGY=0.50.

**Three HardestAI baselines**: `OriginalHardestAI` (Churchill's original), `HardestAI` (our modified), `LiveHardestAI` (exact SWF match — 5 ability variants, 50-entry opening book, Odin filter). 
`HardestAI` should be exactly equivalent to `OriginalHardestAI` at default configurations.
**Strength: LiveHardestAI < MCDSAI <= SteamAI ≈ MasterBot (Steam).** Quantified gap: ~20% WR overall in single-unit matchups (60% of units at 0/4). Full data: `docs/deepsets-training-results.md`.

**Defense block resolution is ONE-PRIME** (engine rule, dave-master `Card::takeDamage` Card.cpp:389-423): each committed blocker either FULL-dies (damage ≥ HP = chump) or is the SINGLE prime that absorbs the partial remainder and survives; every other available unit takes 0 damage (untouched). No damage-splitting across survivors. Non-fragile survivors are never decremented (repair free next turn); fragile persist then heal `getHealthGained()` capped at `getHealthMax()` in `beginOwnTurnPhase`. Live C++ defense = `DefenseSolver → BlockIterator` (min-loss over `DamageLoss_WillCost`); the prime absorber is EMERGENT (non-fragile survivor → loss 0, Heuristics.cpp:237-240) and heal-BLIND; GreedyKnapsack is dead. The AS3 "Q" defender (`AutoClicks.valueOfUnit`/`primeDefender`) is the heal-aware contrast (explicit prime + `health+healthGained−healthMax` free-absorber).

### Training Data Inventory

| Dataset | File | Replays | Examples | Min Rating |
|---|---|---|---|---|
| Human HDF5 | `training/data/human_1500_no6s_v2.h5` | 97,317 | 2.49M | 1500 |
| MB Fleet v3 | `training/data/fleet_v3.h5` | ~160K | 5.9M | — (self-play) |
| MB Fleet v4 | `training/data/fleet_v4.h5` | ~160K | 5.9M | — (self-play) |
| MB Local | `training/data/local_mbvmb.h5` | ~11K | 414K | — (self-play, val set) |

HDF5 files at `training/data/`. JSONL files at `c:\libraries\prismata-replay-parser\`. Only use balance-validated.

### Hardware

AMD Ryzen 7 5700X3D (8c/16t), 32GB DDR4-3200, Intel Arc B580 (12GB VRAM). Self-play: ~16 games/min (4 instances). Training: XPU `--device xpu --num-workers 4` = ~7 min/epoch (4.5x speedup).

## Known Issues (Current)

- **PUCT consumer BUILT in dave-master; policy PRODUCER missing** — `source/ai/UCTSearch.cpp` has the `usePUCT()` branch + the PUCT formula (`Q + c·P·√N/(1+n)`, :294–315) + a per-unit-type buy-logit policy representation (candidate prior = softmax of summed bought-unit logits, :379–405) + a uniform-prior fallback. BUT the DeepSets `.bin` has NO policy head (value head only) → priors are uniform; and self-play stamps argmax/chosen but NOT the per-child visit distribution. The old "13.3% policy / enable at >30%" was **legacy PrismataNet (engine_v2), NOT this DSNN**. Adding a policy head = model+export+reader+train+stamp, not search plumbing. See `docs/superpowers/plans/2026-06-19-policy-head-brainstorm-context.md`.
- **C++ missing stagnation detection**: AS3 has 4-level progress counter. C++ only has flat 200-turn limit (a frozen-multiset stalemate draw rule trims most of it, but MA-style sac/rebuy churn that keeps the multiset CHANGING can still reach the 200 cap — rare, ~0.1% of self-play games).
- **C++ `killCardByID` may have cleanup bugs** (unverified): Prismata has no on-death triggers — actual bug unknown.
- **Replay validation tests legality, not state correctness** (unverified): 50.4% pass rate.

## Key Files

| Path | Description |
|---|---|
| `bin/asset/config/config.txt` | AI player definitions, tournament configs |
| `eval/campaign_frozen.json` | THE frozen RL campaign tuple (N/τ/K/ε/c, parent, mix) — single source of truth |
| `eval/preflight_config.py` | Stage-0 structural preflight (10 checks; asserts config==frozen, never rewrites) |
| `eval/run_iteration.ps1` | One-RL-iteration driver (stages 0–8 + the 4.5 val-acc tripwire) |
| `eval/rl_runbook.md` | Operator reference: what each stage does, promotion checklist, frozen knobs |
| `eval/run_eval.py` | 3-anchor eval: REJECT/REVIEW/INCOMPLETE verdict, incremental manifest, active provenance |
| `bin/asset/config/cardLibrary.jso` | Master unit definitions (105+11 units) |
| `bin/asset/config/neural_weights_*.bin` | Per-player NN weights — **now git-tracked** (mbonly, mbonly_swa, human, mixed, mixed_swa, mixed_35prop) |
| `source/ai/NeuralNet.h/cpp` | Neural network inference engine |
| `source/ai/UCTSearch.cpp` | UCT/MCTS search |
| `source/ai/StackAlphaBetaSearch.cpp` | Stack Alpha-Beta search |
| `source/ai/Eval.cpp` | Evaluation functions (WillScore, Playout, NeuralNet) |
| `source/ai/Heuristics.cpp` | Will Score evaluation and resource values |
| `source/ai/AIParameters.cpp` | AI config JSON parser |
| `source/engine/GameState.cpp` | Core game logic |
| `source/engine/Constants.h` | Game constants, EvaluationMethods enum |
| `source/testing/Tournament.cpp` | Multi-threaded tournament runner |
| `source/testing/TournamentGame.cpp` | Single game runner with self-play export |
| `source/gui/GUIState_Play.cpp` | Game play GUI, debug panel |
| `training/train.py` | PyTorch training (`--model deepsets` or legacy PrismataNet) |
| `training/export_weights.py` | PyTorch → C++ binary weights (legacy format) |
| `training/export_weights_v2.py` | PyTorch → DSN2 binary weights (current DeepSets format) |
| `training/schema_v2.json` | DeepSets per-instance feature schema (current) |
| `training/property_table.json` | Static per-unit properties (DeepSets) |
| `training/schema.json` + `training/FEATURES.md` | Legacy flat PrismataNet schema (state_dim=1785) |
| `training/data/unit_index.json` | 116 canonical unit names |
| `js_engine/matchup_clean.js` | JS matchup runner (LiveHardestAI, MCDSAI, SteamAI) |
| `js_engine/matchup_worker.js` | Parallel worker script |
| `js_engine/steam_ai.js` | SteamAI wrapper for Steam's PrismataAI.exe (one-shot process) |
| `js_engine/replay_to_html.js` | Per-game HTML replay viewer generator (LEGACY — superseded by prismata.live `/replay/local`) |
| `js_engine/build_replay_viewer.js` | Self-contained replay viewer builder (15MB HTML) |
| `js_engine/replay_exporter.js` | JS State → C++ GameState JSON converter |
| `js_engine/replay_validator.js` | S3 replay validator (click-by-click) |
| `gcp/launch_human_training.sh` | GCP human-only DeepSets training launcher |
| `aws/launch_deepsets_training.sh` | AWS mixed MB+Human DeepSets training |
| `.clang-format` | C++ code style |
| `.mcp.json` | MCP server config |

> <ladder> repo files: see `<LADDER_REPO_PATH>\` directly. Full file tables: `docs/CLAUDE_REFERENCE.md`

## Documentation Index

| Document | Description |
|---|---|
| `docs/PROJECT_HISTORY.md` | Full chronological dev history (sections 1-29) |
| `docs/jsengine-faithfulness-results.md` | JS engine faithfulness campaign — COMPLETE (May 2026): faithful to AS3 client; residual 33/61267 = client recording bugs reproduced faithfully (~0.05% replays unviewable in real client too) |
| `docs/deepsets-training-results.md` | DeepSets training results + parity-gap finding (May 2026) |
| `docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md` | Defense-eval pipeline: grade the functional `DamageLoss_Functional` heuristic vs elite human defense — design + plan (`.../plans/2026-06-24-defense-eval-pipeline.md`) + handoff (built + gate-validated Jun 24; harness in eval/defense/, 26 tests, cpp-sim 1234/1235 vs engine) |
| `docs/scratch/2026-06-22-unit-value-heuristic-v3-handoff.md` | Functional unit-value model (`docs/scratch/gen_our_numbers_v2.js`); §16 = the prime-absorber survivor-delta redesign |
| `docs/CLAUDE_REFERENCE.md` | Extended reference (cloud, sniffer, commentary, full file tables) |
| `docs/plans/2026-03-09-training-plan-v3-READY-v3.md` | Training plan v3 (finalized) |
| `docs/plans/2026-02-15-selfplay-training-master-plan.md` | Self-play training master plan |
| `docs/cloud-ops-reference.md` | Cloud provider operational gotchas |
| `training/FEATURES.md` | Neural net feature layout |
| `docs/WEIGHT_FORMAT.md` | Binary weight format spec |
| `docs/wiki/PRISMATA_REFERENCE.md` | Curated game knowledge reference |
| `docs/prismata-strategy-guide.md` | Comprehensive strategy guide |

## Replay API

Replays: `http://saved-games-alpha.s3-website-us-east-1.amazonaws.com/{CODE}.json.gz` (URL-encode `+`→`%2B`, `@`→`%40`).

Search: `POST https://prismata-stats.web.app/api/search/replays` (needs `ssl.CERT_NONE`). Submit: `POST .../replays/submit` (field `codes`, newline-separated, batches of 50).

**Key format**: `expert_replays.json` uses capital `Code`. Null Decks possible — guard before iterating.

> Full replay API details, code sources, Discord export: `docs/CLAUDE_REFERENCE.md`

## Third-Party Credits

| Dependency | License | Description |
|---|---|---|
| **PrismataAI** (base) | CC BY-NC-SA 2.5 CA | Engine and AI by David Churchill / Lunarch Studios |
| **SFML 2.6.2** | zlib/libpng | GUI rendering (at `c:\libraries\sfml\`) |
| **RapidJSON** | MIT | JSON parsing (embedded at `source/rapidjson/`) |
| **prismata-replay-parser** | Open source | TS replay parser (at `c:\libraries\prismata-replay-parser\`) |

## External Resources

| Resource | URL |
|---|---|
| Prismata Wiki | https://prismata.fandom.com/wiki/ |
| Churchill Publications | https://davechurchill.ca/publications/ |
| ML State Eval Paper (2019) | https://skatgame.net/mburo/aiide19ws/paper-3.pdf |
| HPS Paper (AIIDE 2015) | https://davechurchill.ca/publications/pdf/aiide15_churchill_prismata.pdf |
| prismata-stats | https://gitlab.com/prismata-stats/v3/-/tree/dev |
