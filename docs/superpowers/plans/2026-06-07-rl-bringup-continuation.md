# RL Bring-up Continuation — start here (2026-06-07)

> **You are picking up the RL self-play loop.** The build is ~90% done; a short, well-defined prep
> list + one hard blocker stand between here and the first local iteration. This doc is the
> authoritative current state (audited 2026-06-07) — trust it over the older docs where they conflict.

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
