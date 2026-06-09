# RL Bring-up Continuation — start here (2026-06-07)

> **You are picking up the RL self-play loop.** The build is ~90% done; a short, well-defined prep
> list + one hard blocker stand between here and the first local iteration. This doc is the
> authoritative current state (audited 2026-06-07) — trust it over the older docs where they conflict.
>
> **⚠️ READ THE LATE-2026-06-07 ADDENDUM AT THE BOTTOM FIRST** — an 8-agent re-audit + fix pass ran after
> this doc was written. It found 2 run-fatal driver bugs + a stale-weights cluster the §3/§4 lists missed,
> applied the fixes, and resolved the iter-0 design question. The addendum supersedes §2–§4 where they conflict.

## 0. Read first (but mind the dates)

Read these three, in order, for the design + task detail — **but note that 4–5 days of work plus a
full feature-consistency session (today, 2026-06-07) happened after they were written**, so treat
their "remaining work", weights names, and "training now" claims as *stale*; §2–§4 below is the
reconciled truth:

1. `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` — the design (loop arch, 3-anchor eval, IG-optional first campaign, go/no-go rule). **Still valid.**
2. `docs/superpowers/plans/2026-06-03-rl-selfplay-loop-implementation.md` — the 14-task build plan. **Mostly DONE** (see §3).
3. `docs/plans/2026-05-31-linux-rl-bringup-and-go-no-go.md` — the £400 go/no-go framing + 6 phases. Phase 3.5 (cValue) is DONE (= 0.3). Phase 0 (Linux build) is **not** a blocker (the proof-of-life runs native Windows).
4. Session-2 continuation (for the IG-count redesign detail): `docs/superpowers/plans/2026-06-04-rl-continuation-session2.md`.

## 1. What changed since those docs were written (today's session — load-bearing)

A train↔inference **feature-consistency** session shipped today and it changes the RL data substrate:

- **The RL init is now `neural_weights_mixed_v221.bin`** (the v2.2.1 consistency-fixed SWA) — **supersedes `mixed_v22` and `mixed_35prop`** everywhere. RL_SelfPlay/RL_Eval/RL_Eval_iter0 were repointed (dave commit `eca0469`). **Two stale refs still point at `mixed_35prop` — fix them (see §4.5):** `eval/run_iteration.ps1:51` (`$parentBin`) and `RL_Explore`'s `WeightsFile`.
- **Four train↔inference skews were fixed** (all in the FEATURE layer, not the engine): `in_card_set` (base+advanced), `supply` (REMAINING not cap), `is_blocking` (SWF `inst.blocking`), `ability_used`/`is_blocking` at inference (role/`canBlock`, not the non-serialized `abilityUsedThisTurn`). Details: `docs/dsnn-feature-schema.md` v2.2.1 changelog.
- **A committed three-way parity gate exists: `training/tests/test_three_way_feature_parity.py` (52/52)** — JS extractor == C++ exporter (`V2Record.cpp`) == C++ inference. **This SUPERSEDES the plan's Task 5 Step 6 `test_selfplay_export_parity`.** Run it before/after any feature/extractor/exporter change.
- **The self-play export path is verified.** I ran `RL_SelfPlay_Smoke` this session → it produced `selfplay_*.jsonl` + native `parity_states/`, and the C++ self-play exporter (`V2Record.cpp`) is byte-consistent with inference (0 divergence, both phases). This retires the spec §9 risk *"SelfPlayDataExport was exercised with playout self-play, not DSNN(UCT+NN)"* and the §10.4 round-trip item — **done.**
- **The human rehearsal corpus `human_1800_v2.{jsonl,h5}` was re-extracted with the four fixes** (so it's now the v2.2.1 version; `is_blocking` is alive ~30%, `supply` is remaining, base in `card_set`). MB corpora (`fleet_v3_v2`/`fleet_v4_v2`/`local_mbvmb_v2`) are **verified feature-identical** to the fixed pipeline (1000-game + C++ cross-check) — no re-extraction needed.
- **New eval util: `eval/eval_deepsets_h5.py`** — offline DeepSets value-net metrics on a V2 H5 (reuses `train.py eval_epoch`; CPU default). Use it for the secondary MB-val / forgetting diagnostic. (Legacy `training/evaluate_model.py` is flat-PrismataNet only — won't load DeepSets.) v2.2.1 SWA on `local_mbvmb_v2` = **0.3458 / 81.8% / 0.1164** (== v2.2; the fixes don't regress MB-val — the payoff is consistency + RL).

## 2. Current verified state (audited 2026-06-07)

**DONE / live (do not rebuild):**
- RNG fix + `--test-rng` (seedable, thread-hash-free); pure temperature+ε sampler + `--test-sampler`; sampler wired self-play-only into `UCTSearch::getBestRootNode` (argmax preserved for eval). [plan Tasks 1–3]
- `RL_SelfPlay` / `RL_Eval` / `RL_Eval_iter0` players in dave `config.txt:252-254` — `RootMoveIterator=HardIterator_5var_IGsubset_Root` (the **IG-click-COUNT** AbilitySubset space, `MoveIterator_AbilitySubset`, `dave@4bfdb61`), `MaxTraversals:512` (placeholder), `SelfPlaySampling`/`TemperatureTau:1.0`/`TemperatureK:6`/`EpsilonUniform:0.25`, **`UCTConstant:0.3`** (cValue swept), `WeightsFile=neural_weights_mixed_v221.bin`. [Tasks 4, 12]
- C++ self-play V2 exporter (`SelfPlayV2Exporter` + `V2Record.cpp`) with live telemetry: `ig_click_count, sampled_idx, argmax_idx, root_children, root_truncated`; writes native `parity_states/` sidecar. [Task 5 — and fixed/verified this session]
- All eval scripts are **real implementations, not stubs** (the older note saying `run_eval.main()` is a stub is OUTDATED): `eval/run_eval.py` (3-anchor manifest + GO logic), `eval/calibrate_n.py` (N-sweep + non-degeneracy gates), `eval/action_coverage.py` (parses `ig_click_count`), `eval/offbook_audit.py` (`--probe-buys` reachability), `eval/tactical_suite.py` (IG-click-count regression), `eval/wilson.py` (CIs + sequential), `eval/human_val.py` (STEAMAI bridge), `eval/run_iteration.ps1` (full 8-stage driver). [Tasks 7–14]
- `ForcedCards:["Hotel"]` curriculum wired in 13 tournament blocks (RL_Cal_*, RL_Eval_iter0_*, RL_Step2_*). cValue 0.3 on all RL_* players.
- `train.py --rl-mode` flags wired (`train.py:923`, imports `rl_data` at `:1108`).

## 3. Outstanding prep — the actual remaining work (ordered)

> **Verified Jun 7 (the audit that produced an earlier draft of this doc had several false "missing"
> claims — re-checked by hand).** ALREADY PRESENT and wired (do NOT rebuild): `training/rl_data.py`
> (real: `colour_balance_weights`, `build_rl_sampler`, `rehearsal_fraction_for_iter`,
> `select_replay_window`; imports clean), `eval/rl_campaign.md`, `eval/tactical_cases/` (2 cases),
> `eval/tactical_baseline.json`, `training/data/human_1800_v2.h5`, and all eval scripts. **There is NO
> hard code blocker.** Always `ls`/grep before assuming something is missing.

**🟠 Genuinely missing — content + two stale refs (no heavy compute):**
1. **Populate the two curated state batteries** (extract via the JS engine `Analyzer` + `replay_exporter.stateToCppJSON` — **NOT** F6 dumps, which are pre-swoosh DEFENSE phase with IGs tapped/0 red → invalid for IG testing):
   - `eval/calib_states/` — ~20 representative states (varied turn/resources/IG-availability) for `calibrate_n.py`.
   - `eval/ig_battery/` — ~20 states where the active player owns ≥1 Infusion Grid (for `action_coverage.py` argmax click-count distribution).
   - (`eval/tactical_cases/` already has 2 cases — just confirm they're real `known_move` cases so the regression gate is non-vacuous; `docs/scratch/ktink_t9_action_request.json` is a real IG over-click fixture if you want more.)
2. **Fix the two stale `mixed_35prop` weight refs → `neural_weights_mixed_v221.bin`** (this session's repoint missed them): `eval/run_iteration.ps1:51` (`$parentBin`; or pass `--parent-weights`) and `RL_Explore`'s `WeightsFile` in dave `config.txt` (axis-2 only).
3. **Confirm the config blocks `run_iteration.ps1` drives exist** in dave `config.txt` (`run:false`): `RL_Eval_iter0_forced/general`, `RL_Step2_Smoke`, `RL_Cal_N*`/`RL_Cal_vs_deploy_N*` — each with an `exportTrainingV2` target. (The audit found `ForcedCards:["Hotel"]` in 13 such blocks, so they likely all exist — verify.)

**🟡 Then run (compute):**
4. **N-calibration** (plan Task 13 / spec §3-M5): with `calib_states/` populated, run `eval/calibrate_n.py` (→ `eval/n_calibration.json`) to sweep `N∈{100,256,512,1k,2k,5k}` (the `RL_Cal_N*` blocks), pick the **smallest N passing the non-degeneracy check** (game-length within 2σ of human-1800; P0/P1 WR∈[0.35,0.65]; root visit-entropy above floor; N comfortably > branching factor ≤30). Freeze N into `RL_SelfPlay.MaxTraversals`. (Multi-hour.)
5. **De-risk iter-0 the cheap way first (spec §8.5 / O4):** generate ONE fixed self-play dataset on the IG-optional config, `--rl-mode` fine-tune once (no loop), eval. A clean offline improvement validates data→train→export→eval with zero self-play-poisoning risk. Optionally O1 (deep-sim ~10k–50k early batch overnight) for cleaner labels.
6. **Run the gated loop** via `eval/run_iteration.ps1`: iter-0 (wide-untrained anchor = current `v221` on the IG-optional config) → iter-1 → 3-anchor eval {wide-untrained iter-0, `DSNN_Mixed35_5var`, `STEAMAI`} with Wilson CIs + sequential 128→256→512 → human-reviewed promote/reject/inconclusive. **Measure games/hr at the chosen N before any AWS spend.**

**⚪ Optional / parallel (not blockers):**
- Linux/WSL2 build is **configured but never compiled** (`build-linux/` has CMakeCache but no binaries). Only needed if you want WSL2 self-play; the proof-of-life is native-Windows, so this is deferrable. To finish: `ninja -C build-linux` (GUI already OFF).
- Blend/rotation curriculum (currently pure forced-Hotel) — fine for axis-1; revisit for later axes.
- `eval/offbook_audit.py` → `RL_Explore` filter gates **axis-2 only**; parallelizable, doesn't block axis-1.

## 4. Run/build conventions + gotchas (from this session + the plan)

- **Two repos, don't cross-file:** engine C++ → `c:/libraries/PrismataAI-dave-master` (`dave-master-jsonclean`); training/JS/eval/docs → `c:/libraries/PrismataAI` (`feature/production-vectors`). **Never engine_v2** (this repo's `source/` is the indicted clean-room). Push to the `PrismatAlpha` fork only.
- **dave-master build** (`cmake` NOT on PATH; = "v145" = VS 18 / 2026): `"C:/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe" build/Prismata_Standalone.vcxproj //p:Configuration=Release //p:Platform=x64 //m //v:minimal` (and `build/Prismata_Testing.vcxproj`). Output → `bin/`. `bin/PrismataAI.exe` is a manual copy of `Prismata_Standalone.exe`.
- **C++ parity tooling:** `Prismata_Standalone --dump-v2-record <state> <out>` (exporter), `--dump-features <state> <out> <weights.bin>` (inference), `--test-rng`, `--test-sampler`, `--probe-buys`. `js_engine/dump_shared_state.js <replay> <ply> <prefix>` emits paired cppstate+jsrecord. Use a **15-global** weights `.bin` (`mixed_v221`) for `--dump-features` parity.
- **config.txt is strict JSON** (no comments). **Self-play tournament blocks need the same player in `group:1` AND `group:2`** (same-group = 0 games). Reproducible self-play = `Threads:1` + non-zero `Seed`.
- **Export + parity per iteration:** `python training/export_weights_v2.py <swa_model.pt> bin/asset/config/<name>.bin --property-table training/property_table.json` (loads `model_config` defaults: 37 prop / 15 global; SWA ckpts are unwrapped). Then `tools/parity/compare_parity_deepsets.py <dumps> --pt <swa.pt> --bin <name.bin>` (worst |Δ| was 1.09e-6 this session, tol 1e-3).
- **SWA is val-independent** (averages epochs swa_start..end regardless of `--val-file`; `--patience ≥ --epochs` ⇒ no early stop). Deploy SWA.
- Git Bash `/tmp` ≠ Windows `C:\tmp`; pass native exes absolute Windows paths. Python on Windows: `PYTHONIOENCODING=utf-8`; use absolute paths (relative paths break after a `cd`).

## 5. The decision being served (don't lose the thread)

A **defensible local go/no-go**, not a finished agent: does RL self-play improve the value net on the IG-optional widened axis (IG fire/skip **count** learned) beyond the wide-untrained iter-0 anchor, **without** regressing the general pool — at a pre-registered effect size and N? A *flat local* result is **"the local setup can't measure it,"** not "RL fails" (spec §1 interpretation guard). Clear go → spend the £400 AWS scale; flat after the §9 false-negative triage → raise N / widen further / document the O6 policy-head escalation before spending.

---
*Companion context: `docs/dsnn-feature-schema.md` (v2.2.1), `docs/rl-action-space-partials-map.md`, the three-way parity gate `training/tests/test_three_way_feature_parity.py`, and `eval/eval_deepsets_h5.py`.*

---

## Session addendum — 2026-06-07 (late): independent re-audit + fix pass (AUTHORITATIVE)

An 8-agent evidence-based re-audit re-verified every load-bearing claim above against the actual files in
both repos (running the tests/commands, not trusting prose). The infra is genuinely solid — but the audit
found **2 run-fatal driver bugs and a stale-weights cluster the §3/§4 lists missed**, and surfaced a design
ambiguity on the iter-0 anchor. All fixes below are **applied + verified** this session.

### Decisions (user, 2026-06-07)
- **iter-0 anchor = v221, NOT a random net.** A random-init anchor would make `d_rl` fire vacuously (beating
  random is trivial). `RL_Eval_iter0` = `neural_weights_mixed_v221.bin` is correct as-is; `init_random_deepsets.py`
  is **not needed**. `rl_campaign.md` Run-prereq item 2 was rewritten accordingly (and item 6, the stale
  "run_eval.main() is a skeleton" note, retired).
- **Strategic flag (open):** the user reports v221 *already* plays IG correctly once the action space is opened
  (humans rarely over-click IG; human games are in its training mix). So the IG axis may have **little headroom**
  → a flat `d_rl` would mean "pipeline validated, axis saturated," NOT "RL fails." Do the **O4 cheap offline
  de-risk first** (one fixed dataset, fine-tune once, eval) to validate data→train→export→eval; a headroom-bearing
  axis may be needed to actually demonstrate an RL *win* before AWS.

### Fixes applied this session
1. **Stale weights repointed → `neural_weights_mixed_v221.bin`** (the §3/§4 lists only named 2 of these):
   dave `config.txt` `RL_Explore` + all six `RL_SelfPlay_N100..N5000` (the N-cal self-play movers — would have
   run the multi-hour N-sweep on the wrong 14-global net); `eval/calibrate_n.py` + `eval/tactical_suite.py`
   `--weights` defaults; `run_iteration.ps1:51 $parentBin`. (The legitimate `DSNN_M35*`/`Mixed35` baselines
   stay on 35prop by design.) Verified: **0 RL_* players still on 35prop**; config.txt still strict-JSON.
2. **RUN-FATAL parity gate fixed:** `tools/parity/dump_value_batch.py` spawned `compare_parity_35prop.py`
   (does not exist) → now `compare_parity_deepsets.py` (identical CLI, generation-agnostic, handles 15-global).
3. **RUN-FATAL states-dir fixed:** `run_iteration.ps1 $parityStates` pointed at `tools/parity` (dump *outputs*,
   14-global) → now `$bin/asset/training/parity_states` (the native `sp_*.json` GameState sidecar).
4. **`PrismataAI.exe` re-synced** to the current build (was a stale 09:00 build predating the is_blocking
   rebuild) and the genuine **721,920-byte `PrismataAI.exe.ORIG`** installed in dave `bin/` (from the Steam
   install) → STEAMAI anchor no longer silently deferred.
5. **`run_iteration.ps1` hardened:** Stage-1 now clears stale `selfplay_*.jsonl` + `sp_*.json` before self-play
   (export counter resets to 0 each run → cross-iter contamination); N now auto-reads `eval/n_calibration.json`
   (`-N 0` placeholder refused — must calibrate or pass `-N` explicitly); Stage-8 passes `--battery` explicitly.
6. **Three-way parity gate hardened:** pinned to `neural_weights_mixed_v221.bin`; added a `def test_*` pytest
   wrapper so `python -m pytest` no longer collects **0 tests**, and a missing-dep SKIP is now a *visible*
   `pytest.skip` (not a silent green). Direct run still **52/52**.
7. **Batteries:** `eval/calib_states/` + `eval/ig_battery/` created and seeded (smoke). New extractor
   `eval/replay_to_request.js` (replay code + ply → full `{mergedDeck, gameState, aiParameters}` request;
   `--ig-only` filter). `calib_states` seeded with 3 action-phase states (ktink + gNUTm p4/p6); `ig_battery`
   has the ktink IG state. **Full IG curation pending user states** (see below).

### Doc corrections
- `tactical_cases/` has **1** real known-move case (ktink), not "2" as §2/§3 said (gate is non-vacuous but thin —
  consider adding a 2nd case). `ForcedCards:["Hotel"]` is in **16** config blocks, not 13 (cosmetic).
- The eval scripts are all real (not stubs); `eval/tests/` = **24 passed**. MB-val of v221 SWA on
  `local_mbvmb_v2` reproduced **exactly** (0.3458 / 81.8% / 0.1164). C++ telemetry/iterator/RNG/sampler all
  verified in source + at runtime.

### Remaining before the first real iteration
- **ig_battery full curation (USER):** best source = **F6 dumps taken in the ACTION phase (post-swoosh)** at a
  turn where the active player owns a **ready** IG with **red** available — these drop straight into
  `eval/ig_battery/` (that's exactly how the ktink case was made; replay-code extraction gives turn-START
  snapshots that are pre-swoosh DEFENSE on attacked turns → IGs tapped). Human games where IG is already bought
  are ideal. For non-IG `calib_states`, replay codes work — the extractor handles them (codes
  `6OtS1-OZsWI / Ou1Me-@rcWv / KtInk-pMiQf` are NOT in the local archive → would need fetching).
- **Then:** N-calibration (`calibrate_n.py`, now on v221) → freeze N → O4 offline de-risk → gated `run_iteration.ps1`.
- **Open verification:** the extractor's `--ig-only` active-player heuristic (turn-parity) needs validating
  against the stateToCppJSON active-player convention before trusting it to auto-mine IG states from codes.

### Session-2 results (2026-06-08): N-calibration done + IG human-vs-net

- **N-calibration COMPLETE → `recommended_N = 256`** (`eval/n_calibration.json`). Smallest N passing all
  non-degeneracy gates under BOTH the (resignation-biased) human band AND the correct MB full-wipeout band
  [16,45]; N=100 fails game-length (45.3, weak/long play), N≥256 all pass. Game length plateaus ~38-40 (in-band),
  `wr_vs_deploy` climbs 0.25→0.44 with N, `root_children≈9`/never-truncated (MaxChildren never binds). **256 is
  frozen into `RL_SelfPlay.MaxTraversals`.** Baseline-corpus caveat fixed this session (resignation vs wipeout —
  see the `calibrate_n.py --baseline-h5` change; default now `fleet_v4_v2`).
- **ig_battery populated with 38 real F6 IG states** (5 human games) + ktink; all action-phase, red available,
  deduped. Tooling: `eval/f6_to_request.py` (F6→request), `eval/ig_human_clicks.js` (oracle_diff align →
  human IG clicks/turn), `eval/ig_net_clicks.py` (net argmax IG vs human merge).
- **IG human-vs-net (the headroom read):** v221 matches the human IG-click count **23/38 = 61%** exactly;
  divergences almost all ±1, with a **mild residual OVER-fire** (10 net>human, 5 net<human). So the IG axis is
  **broadly human-like but NOT saturated** — small, non-zero headroom (residual over-fire echoing a much-milder
  version of the old MB over-click). Caveat: human ≠ optimal, so some net-disagreements may be fine/better.
  Implication: expect a **modest `d_rl`**; read flat-after-triage as low-headroom, not failure (spec §1).
- **NEXT: O4 cheap offline de-risk** — generate ONE fixed self-play dataset at N=256 on the IG-optional config,
  `--rl-mode` fine-tune once (no loop), eval. Validates data→train→export→eval with zero self-play-poisoning
  risk AND shows whether RL nudges the residual IG over-fire down (+ win-rate). Then the gated loop.

### Session-3 (2026-06-08→09): O4 de-risk → OB+5var confound (substrate was wrong) → N re-sweep + threading

> **⚠️ SUPERSEDES Session-2's `recommended_N=256` and the O4 run — both ran on a HANDICAPPED config (no
> `LiveOpeningBook2`, 1 of 5 variants; see OB+5var below). A fresh N re-sweep on the corrected config is in progress.**

- **Laptop DSNN bundle (dave `80e8fe7`):** the `use_dsnn.txt` FORCE_DSNN drop-in now defaults to **cValue=0.3**
  (env `PRISMATA_DSNN_CVALUE`) + 7→10s think, so the Steam swap-in plays a strong DSNN. Bundle at
  `C:\libraries\dsnn_steam_bundle\` (exe + sentinel + `asset/config/{config.txt, 35prop+v221 weights}` + README).
  Uses `HardIterator_Root` (non-OB = deployed `DSNN_Mixed35`), NOT the IG-subset/OB iterator.

- **O4 de-risk RAN — pipeline mechanics validated, then killed on the confound.** Found+fixed a run-fatal
  Stage-1 bug: `run_iteration.ps1` launched `Prismata_Testing.exe` without cwd=`$bin`, so it couldn't open
  `asset/config/cardLibrary.jso` → abort (the ps1 had never actually been run). Fix = `Push-Location $bin`
  (main `bd006fa`). Stages 1–6 then ran **clean**: self-play (128g) → vectorize → `--rl-mode` SWA fine-tune →
  export → **parity gate PASSED over 1000 self-play states** → tactical (no IG regression). So
  data→train→export→parity→tactical is mechanically sound. Killed at Stage-7 eval once the confound was found
  (the candidate was getting crushed by full-config anchors — expected on the handicapped substrate).

- **🔴 OB+5var confound — the RL substrate was WRONG (dave `40d3bdc`, FIXED + verified).**
  `HardIterator_5var_IGsubset_Root` (root iterator ALL RL players use) wraps `HardIterator_5var_NoIG_Root`,
  which had **collapsed to ONE variant** (`V5_CS_NoIG`) chaining only the **4-entry `DefaultOpeningBook`** —
  silently dropping the **50-entry `LiveOpeningBook2`** AND 4 of the 5 chill-solver variants. So RL self-play +
  eval ran a **handicapped opening regime** (couldn't buy the 3rd-Engineer book line; non-OB buy-gen caps
  Engineers at 2). User caught it. Fix: rebuilt all 5 NoIG variants as **byte-faithful mirrors** of
  `HardIterator_5var_Root` with ONLY the IG-firing ability stripped (`AbilityActivateUtilityLive/Click → NoIG`;
  new `AbilityActivateUtilityClickNoIG` = `IG_Only`-filtered ActivateUtility). **Decision: RL runs on the live
  OB + 5 variants** — config is now **one-change-from-deployed** (IG enumerated 0..N, not auto-fired). Verified:
  engine parses/runs; runtime differential on an IG-free opening state → new IGsubset iterator == deployed
  `HardIterator_5var_Root` (`root_children=2, argmax=0` both). NOTE the subset *requires* a NoIG inner
  (`MoveIterator_AbilitySubset.cpp:226` only enumerates not-yet-used IGs), so re-pointing at the auto-firing
  full 5var is impossible — the NoIG mirror is the only correct path.

- **Traversal mental model (measured):** a 7s deployment turn = **~5k–22k UCT traversals** (typically ~5–8k),
  and **never hits the 100k cap** — the *time* limit binds, not `MaxTraversals`. So **N=5000 ≈ deployment
  strength, N=256 ≈ ~5%** (confirms 256 was far too weak). Eval is decoupled from self-play N (always full 7s →
  ~5–8k traversals; A1).

- **🟢 Self-play PARALLELIZES (the `Threads:1` setting was wrong — big AWS-cost lever).** The V2 export is
  **thread-safe by construction**: `Tournament.cpp:163+` runs games as `std::future`s up to `_threads`
  concurrently, each a separate `TournamentGame` with its own `SelfPlayV2Exporter`, atomic-unique `gameId`, and
  own output file. `Threads:1` was overly conservative (carryover from the old multi-PROCESS self-play / x86 4 GB
  limit — neither applies to this x64 build); eval/vs-deploy already run `Threads:8` with NN players. **TODO:
  empirically verify a `Threads:8` self-play export (game count, no clobber/dup, valid records), then bump
  `RL_Step2_Smoke` / `RL_SelfPlay` / `RL_Cal_N*` to `Threads:8`.** Self-play then scales with vCPUs.

- **N re-sweep (in progress, corrected config):** grid `{256,512,1000,2000,5000}` (user dropped 100; no 10k since
  5k≈deployment), MB full-wipeout baseline `[16,45]`. **Key finding: at 32 games/N, `wr_vs_deploy` is too noisy
  to RANK N** (bounces 0.375/0.469/0.406/0.3125 — indistinguishable; more search can't make it weaker). So the
  sweep gives a non-degeneracy check, NOT a quality ranking; N choice rests on non-degeneracy (≥512 pass; 256
  flagged on a noisy `p0_wr 0.656` from 32g) + the traversal model + throughput (now cheap with Threads:8).
  `recommended_N` pending the N=5000 point. (Self-play `p0_wr`/`wr_vs_deploy` are recomputed from the exported H5
  records via `metrics_from_h5`, NOT from the tournament HTML — e.g. `p0_wr 0.656` = 21 P0 wins / 32 games.)

- **Other fixes committed:** `calibrate_n.py` clears stale shards before each N (main `039c88e`); `tools/`
  gitignore → default-deny + explicit-allow so real tooling tracks (main `4b3b031`); `calibrate_n` length
  baseline → MB `fleet_v4_v2` (main `cf0d8b1`).

- **Immediate next (PAUSED for user):** report the N re-sweep result → (on user go) verify Threads:8 self-play →
  set games-count + N + threads together → redo self-play → eval, all on the corrected **5var + LiveOpeningBook2**
  substrate. Open decisions: self-play **games count** for a real iteration (currently `RL_Step2_Smoke` rounds=64
  = 128g, the O4 size — bump substantially); whether to weight quality (higher N) vs the smallest-passing rule.
