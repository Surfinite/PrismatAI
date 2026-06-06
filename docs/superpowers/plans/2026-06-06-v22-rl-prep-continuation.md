# v2.2 + RL-prep continuation (handoff, 2026-06-06)

Continuation from the session that shipped DSNN **feature schema v2.2** (frontline + auto/click_attack
split + under_attack global) and retrained the mixed model. Read `docs/dsnn-feature-schema.md` first.

## State (done + committed, NOT pushed)
- v2.2 schema live: `property_table.json` (37 props), `schema_v2.json` (37/15/79/303, `feature_revision v2.2`),
  `vectorize_v2.py` (`under_attack`), `model_deepsets.py`, `export_weights_v2.py` (self-check derives num_global).
  Engine `NeuralNet.cpp` (under_attack 15th global; COMBINED 303). Doc: `docs/dsnn-feature-schema.md`.
- **Model trained + verified:** `neural_weights_mixed_v22.bin`. Recipe = mixed_35prop's exactly
  (train fleet_v3_v2+fleet_v4_v2+human_1800_v2, val local_mbvmb_v2, 100ep SWA@80, XPU). SWA val_loss
  **0.3458 / 81.8% / brier 0.1165** (35prop: 0.3464/81.7% — micro-edge on a val that can't see the new feats).
  C++↔PyTorch parity worst |Δ| **6.31e-07**. SWA .pt: `training/models/deepsets_mixed_v22/swa_model.pt`.
- Commits: main `f62e160`(schema) + `ace7672`(v22.bin, tracked); engine `2346963`(NeuralNet) + `55d9d02`(config repoint + parity 15-global compat). Branches: main `feature/production-vectors`, engine `dave-master-jsonclean`.
- RL players (`RL_SelfPlay`/`RL_Eval`/`RL_Eval_iter0`) repointed → `neural_weights_mixed_v22.bin` (the RL init = RL_Eval_iter0 pre-RL baseline).
- H5 globals patched in place to 15-d (under_attack appended; under_attack=1 frac ~52% MB / 44% human).

## TASK (A) — make the engine load 14- AND 15-global models (do FIRST)
> ✅ **DONE 2026-06-06 — `dave-master-jsonclean@481f916`.** `num_global` is now derived from the
> value-head input width at load (`val_linear1.in_dim − (2*ENC_H+SUP_H)`); `COMBINED` (both spots) +
> the dump loop use it; `under_attack` emitted only `if num_global>=15`. Rebuilt x64/v145
> (`Prismata_Standalone`→`PrismataAI.exe` refreshed). **Dual-parity PASS:** v22 (15-global) worst
> |Δ| 2.21e-07; mixed_35prop (14-global, previously crashed) loads + ties out 2.02e-08 (== the
> FINDINGS_35prop baseline). Write-up: `PrismataAI-dave-master/tools/parity/FINDINGS_dual_global.md`.
> **Tooling follow-up (deferred, NOT engine):** `compare_parity_deepsets.py` can no longer construct the
> 14-global torch ref — v2.2 moved `PrismataDeepSets()` defaults to 37-prop and `model_deepsets.py:91`
> hardcodes the 303-wide value head. Add `num_global`/`num_properties` overrides to model + tool to make
> the harness first-class for both generations (main-repo schema change).

The v2.2 engine build is currently **15-global-ONLY**: it can't load 14-global (35-prop) `.bin`s
(value head 303 vs 302) → `DSNN_Mixed35_*` players / the non-gating narrow yardstick crash on it.
Fix: make `num_global` **derived from the loaded value head** (mirrors how `num_properties` is header-driven),
not hardcoded 15. In `PrismataAI-dave-master/source/ai/NeuralNet.cpp`:
- Compute `num_global = <val_linear1 input width> - 2*ENC_H - SUP_H` at load (val head input == COMBINED).
- `COMBINED = ENC_H*2 + SUP_H + num_global` (was `+15`, lines 359 & 515).
- Global build (~line 617-636): always emit the 14 base globals; **`if (num_global >= 15) { compute+emit under_attack }`** else skip.
- dump-features loop (~line 808): iterate `num_global` (was 15).
- Verify `LinearLayer` exposes its input dim (grep the struct; may need to store num_global as a member at load).
Then rebuild (x64/v145, both targets) and **dual-parity**: (1) v22 (15-global) still passes (`tools/parity/compare_parity_deepsets.py <dumps> --pt swa_model.pt --bin neural_weights_mixed_v22.bin`, worst |Δ|<1e-3); (2) 35prop (14-global) LOADS + ties out to its 35prop ref (`--pt models/deepsets_mixed_35prop/best_model.pt --bin docs/scratch/deepsets_mixed_35prop.bin`). Commit. (Parity dump cmd: `./PrismataAI.exe --dump-features <state.json> <out.json> <weights.bin>`; states in `bin/asset/training/parity_states/sp_*.json`.)

## Human val-set curation (user's plan — NOT done yet; v2.2 run used the MB val)
Goal: a HUMAN-vs-human val set, disjoint from training, built by the SAME pipeline that made the training set. Steps:
1. Collate a NEW candidate list = `replays.db` games where BOTH players **1500+** (exclude MB bot games — `p1/p2_rating<=1`) **∪** a ladder-site dump (~250 more h-v-h codes — user pulls a fresh one from the prismata-ladder workspace). **OPEN: verify whether the recent ladder games were ingested into `replays.db` or just kept as a code list** — check before assuming.
2. **Subtract the codes actually USED in training** = the `human_1800_v2` corpus list = `C:\libraries\prismata-replay-parser\final_training_codes_1800.txt`. (NOT `eligible_1500_ranked_clean.txt` — that's a different/overlapping *candidate* list, not the train-exclusion set. The thing trained on is `final_training_codes_1800.txt`.)
3. **Run the leftover through the SAME exclusion scripts/rules that produced `human_1800_v2`** (the pipeline that turned the raw 1800+ set into `final_training_codes_1800.txt`): the thorough balance validator (`prismata-replay-parser/audit_ranked_balance.py` — drops pre-2019-balance-unit games, ~17% historically) + the 6s/12s exclusion (keep 6s-AND-12s-out **if enough survive**; 6s especially — even master 6s games are low quality under time pressure). Report the surviving count.
4. Vectorize the survivors → a human-val H5 (15-global automatically via the updated vectorize_v2; or patch globals like the others). Use as (part of) the val for future runs.
Rationale: 1500+ for VAL is fine (held-out distribution check; lower-but-clean human games still useful, distinct from the 1800+ train). The fresh ladder dump is the most valuable bit (guaranteed not in training). Key: build the val with the IDENTICAL cleaning the training set got, so train/val differ only by which codes — not by cleaning.

## Self-play set size — a spread IS well-motivated (corrected)
Real Prismata games are **Base+5 OR Base+8–11** (NOT always 8). The human training/val data spans these
(up to 11 advanced buyables; some B+5). So self-play at **B+8 only UNDER-covers the deployed distribution**:
the net is deployed on B+5 and B+8–11 but would get RL signal only at B+8 (B+5/B+9–11 lean on the supervised init).
Trade-off: B+8-only concentrates RL signal on the commonest size + keeps root branching small (MaxChildren=40 freeze safe);
a spread (match real: B+5 + B+8–11) covers deployment + the training distribution but dilutes signal across sizes and
raises root branching at B+10–11 (the `root_truncated` telemetry becomes relevant — may need MaxChildren co-calibration).
**Recommendation:** B+8 is defensible for the FIRST proof-of-life IG campaign (signal concentration, cap-safe), but the
spread is the right call for a production RL model and should be planned — ideally matching the human-data set-size
distribution. Decide explicitly before the real campaign; don't default to 8 by inertia.

> ✅ **DECIDED 2026-06-06 (user):** first campaign is **B+8 only** — it's what all the MasterBot games used, so it
> concentrates RL signal on the deployed-commonest size and keeps root branching cap-safe (MaxChildren=40). The
> **B+8–11 spread is deferred** to a later production run (revisit `root_truncated`/MaxChildren co-calibration then).

## RL-prep roadmap (after A)
- **B1 (main code lift):** complete `eval/run_eval.py::main()` — currently a skeleton that writes empty `anchors{}`.
  Wire: flip per-anchor config blocks → `run_cpp_tournament` → `parse_tournament_stdout` → Wilson/clustered CIs
  (A3/A4) → STEAMAI at fixed-N (A8) seat-independent (A7) → manifest. **The gate to real eval numbers.**
  > ✅ **DONE 2026-06-06 (`8f02684`).** `build_manifest()` (injectable runners) flips the 4 anchor blocks,
  > runs/parses iter0 + narrow, fixed-N steam (A7/A8, soft-skip+DEFERRED if `.ORIG` absent), emits §3 GO inputs
  > (d_rl=iter0/forced, d_reg=iter0/general, `GO_suggested`) with `decision:"(human call)"`. Flat anchor cells
  > match the dashboard; full forced+general under `.pools`. Tests `eval/tests/test_run_eval_main.py` (7) + the
  > 17 existing eval tests green; dashboard integration confirmed. **Still needs the deferred prereqs to produce
  > REAL numbers** (calibrated N+ε, wide-untrained iter-0 weights, `.ORIG`, populated calib/IG batteries — §Run
  > prerequisites). The candidate-vs-parent sequential promotion gate (A3) remains a separate, block-less concern.
- **B2:** populate `eval/calib_states/` + an IG battery (~20 states each; replay real games to action-phase via the ktink method).
- **B3 (setup):** confirm `PrismataAI.exe.ORIG` on disk (STEAMAI anchor); decide N (calibrate vs 512 for proof-of-life).
- **C:** RL **self-play smoke** on v2.2 (`RL_SelfPlay` self-play, ForcedCards Hotel, exportTrainingV2; confirm IG-subset
  emits varied `ig_click_count` + sampler explores `sampled_idx!=argmax_idx` + first throughput) → full **iteration-0**
  via `eval/run_iteration.ps1 -K 0` → review manifest/dashboard. Then measure throughput → AWS go/no-go.

Frozen HP tuple + decision rule: `eval/rl_campaign.md`. Session-2 RL machinery (sampler, IG-subset iterator, C++ V2 exporter,
ForcedCards, `train.py --rl-mode`, `rl_data.py`, tactical_suite, action_coverage, parity harness, calibrate_n) is built+reviewed.
