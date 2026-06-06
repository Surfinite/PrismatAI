# PrismatAlpha Tooling Cleanup & Reorg Plan (2026-06-06)

> Scope: `prismata-replay-parser/`, `PrismataAI/js_engine/`, `PrismataAI/training/`, `PrismataAI/eval/`, `PrismataAI/docs/`. **Nothing is deleted without your approval** — this is a plan to approve.
> Total disk reclaimable (regenerable intermediates only): **~460+ GB** across the three data-bearing areas.

---

## 1. Canonical pipeline (KEEP — the live extraction → train → export → eval path)

**Extraction (human + MB → V2 JSONL):**
- `js_engine/extract_training_jsengine.js` — canonical human extractor (faithful JS engine; emits V2 directly via `extractTrainingExampleV2`; validate-and-drop).
- `js_engine/matchup_clean.js` — MB corpus generator (same `extractTrainingExampleV2`); also the LiveHardestAI/MCDSAI/SteamAI/DSNN runner.
- `js_engine/training_example.js` — shared `extractTrainingExampleV2` (single source of truth for both extractors).
- `js_engine/{state_adapter,card_library,ai_params}.js` + the transpiled engine core (`Analyzer/Controller/State/Inst/...` + `AS3Dictionary.js`) — required infra.

**Fetch + corpus management (replay-parser):**
- `fetch_codes_from_s3.py`, `ladder_fetch.py`, `ladder_status.py`, `ladder_crossref.py` — S3 fetch + ladder set.
- `fetch_player_replays.py` + `batch_fetch.py` — per-player API fetch.
- `replay_db.py`, `build_replay_db.py`, `replay_queries.py`, `replay_cli.py`, `backfill_metadata.py`, `import_ladder.py` — replay DB.

**Balance validation (trustworthy 2026-05-30 set):**
- `audit_ranked_balance.py`, `ladder_validate.py`, `ladder_valset_profile.py`, `build_human_val.py` — code-list curation (built `human_1800`/`human_val_1700`).

**Vectorize → train → export (training/):**
- `vectorize_v2.py` → `train.py` (+ `model_deepsets.py`, `rl_data.py`) → `export_weights_v2.py`.
- Schema/config: `schema_v2.json` (v2.2), `property_table.json` (37-prop), `data/unit_index.json`.

**Eval harness (eval/ — freshly built, all canonical):**
- `run_eval.py`, `wilson.py`, `calibrate_n.py`, `tactical_suite.py`, `action_coverage.py`, `offbook_audit.py`, `render_dashboard.py`, `human_val.py`, `run_iteration.ps1` + `tests/`.

**Current data (KEEP):**
- H5: `human_1800_v2.h5`, `human_val_1700_v2.h5`, `fleet_v3_v2.h5`, `fleet_v4_v2.h5`, `local_mbvmb_v2.h5`.
- Current intermediate JSONL (keep or archive after re-verify): `human_1800_v2.jsonl`, `human_val_1700_v2.jsonl`, `local_mbvmb_v2_training.jsonl`.
- Irreplaceable corpus: `prismata-replay-parser/replays_archive/` (~137k `.json.gz`), `replays.db`, `balance_results.json`.

---

## 2. Deprecate / archive / remove candidates

### 2a. Deprecated extraction stack (retire as one unit)

| path | status | why | risk-if-removed | action |
|---|---|---|---|---|
| `prismata-replay-parser/extract_training_data.js` | DEAD/SUPERSEDED | V1 extractor on plampila `./lib`; `diff_parsers.py` proved divergent on card_set/turn_number/p0_attack | none (provenance of `human_1500_all.jsonl` only) | deprecate-in-place (banner) + archive copy |
| `prismata-replay-parser/lib/` (`replayParser.js`, `gameState.js`, `blueprint.js`, `unit.js`, `.d.ts`/`.map`) | DEAD/SUPERSEDED | plampila TS-port engine behind the deprecated extractor; not imported by canonical extractor | low — keep one historical baseline copy | archive |
| `prismata-replay-parser/src/`, `tools/generateSchemas.ts`, `lib/schemas/`, `src/schemas/` | DEAD/SUPERSEDED | TS source + schema-gen for `lib/` | low | archive |
| `prismata-replay-parser/{package.json,package-lock.json,tsconfig.json,tslint.json}` | DEAD/SUPERSEDED | build metadata for `lib/`; only needed if `lib/` ever rebuilt | low | verify-with-user (keep; harmless) |
| `prismata-replay-parser/{dump_replay_states.js,batch_validate.js,check_defense_phase.js}` | DEAD/SUPERSEDED | use deprecated `./lib`; superseded by JS faithfulness work | low | archive |
| `prismata-replay-parser/batch_validation/` (state-dump pairs) | DATA (dead) | output of dead `dump_replay_states.js` | none | remove-candidate |
| `training/convert_human_to_v2.py` | DEAD/SUPERSEDED | self-confessed `[DEPRECATED 2026-05-31]`; bypassed by V2-direct js extractor; only self-references | none | archive (`training/legacy/`) |

### 2b. Duplicate / stale fetchers + validators (replay-parser)

| path | status | why | risk-if-removed | action |
|---|---|---|---|---|
| `download_all_replays.js` | DUPLICATE | superseded by `fetch_codes_from_s3.py` (newer, threaded) | none | deprecate / archive |
| `fetch_expert_replays.js`, `fetch_1500_replays.js`, `batch_fetch_units.js`, `fetch_units.js`, `fetch_single.js` | STALE/SCRATCH | one-time corpus seeds; superseded by player-fetch+ladder | none | archive (keep `fetch_one_replay.js` as encoding ref) |
| `validate_db_codes.py` | STALE | older DB-balance path; superseded by `audit_ranked_balance.py` | none | deprecate / archive |
| `validate_db_codes.js` | DUPLICATE | exact JS twin of the `.py` | none | archive |
| `validate_balance_all.js`, `check_balance*.js`, `test_balance_logic.js`, `validate_discord_codes.js`, `validate_tournament_codes.js` | STALE/SCRATCH | superseded by `audit_ranked_balance.py` | none | archive |

### 2c. Scratch / research one-offs (replay-parser — ~50 files; findings already in docs/DB)

| group | status | why | action |
|---|---|---|---|
| `elo_audit{,2,3}.py`, `diff_parsers.py`, `qzaO6_turndiff.py`, `ladder_inspect_json.py` | SCRATCH | findings baked into `ladder_validate`/`build_human_val`; `diff_parsers.py` = the deprecation evidence | archive (`_archive/scratch/`) |
| `scan_format203_variants.py`, `scan_balance_full.py`, `scan_fetch_failed.py`, `build_change_table.py`, `analyze_ab.py`, `format_discord.py`, `audit_rarity_changes.py`, `reset_for_rarity_revalidation.py`, `deadeye_analysis.py` | SCRATCH | May-2026 community-patch research one-offs | archive (keep `scan_format203.py` — `diff_unit` source-of-truth) |
| `diff_units.js`, `smart_diff.js`, `compare_units.js`, `apply_updates.js`, `verify_coverage.js` | STALE | original cardLibrary-completion pass (done) | archive |
| `extract_discord_codes.js`, `extract_all_discord_codes.js`, `extract_tournament_codes.py`, `generate_community_codes.js`, `generate_expert_1500_codes.js`, `prepare_all_training_codes.js`, `filter_expert_replays.js`, `filter_1500_replays.js` | STALE | one-time corpus assembly | archive |
| `check_*` family (~11: `check_costs*.js`, `check_ratings.js`, `check_time*.js`, `check_replay_*.js`, `dump_rating_fields.js`, `scan_all_replays.js`) | SCRATCH | throwaway inspection probes | archive |

### 2d. js_engine dead/superseded scripts

| path | status | why | risk-if-removed | action |
|---|---|---|---|---|
| `build_property_table.js` | DEAD/SUPERSEDED | emits **13**-prop table; current is **37**-prop (Python path). **Re-running overwrites `property_table.json` with stale columns** | HIGH if re-run → add banner first | deprecate-in-place (banner) then archive |
| `extract_turn_data.js` | DEAD/SUPERSEDED | "Replaced by `bulk_extract.js`" per its successor's header | none | remove-candidate |
| `bulk_extract.js` | DEAD/SUPERSEDED | pre-V2; replay-DB extractor, not training path | none | deprecate / archive |
| `mcdsai_wrapper.js`, `mcdsai_worker.js`, `mcdsai_manager.js`, `selfplay_main.js` | DEAD/SUPERSEDED | depend on absent `MCDSAI3441.js` (cluster non-runnable); `selfplay_main.js` is sole consumer of legacy `state_adapter.stateToTrainingExample` (V1) | none — frees `state_adapter` to shed V1 path | archive |
| `relabel_replays.js` | DEAD (one-shot) | completed side-identity migration | none | remove-candidate |
| `debug_*.js` (13) | SCRATCH | self-labeled "THROWAWAY"; untracked; faithfulness campaign complete | none | remove-candidate (archive any retained to `docs/scratch/`) |
| `step_m7.js`, `flip_rate_diag.js`, `optA_stats.js`, `run_single_unit_sweep.js`, `oracle_diff.js`, `classify_failures.js`, `verify_dsnn_load.js`, `smoke_dsnn.js`, `validate_jsonl.py`, `batch_validate.py` | SCRATCH | concluded experiments (Option-A no-gain, M7 resolved, sweep concluded) | none | archive (`js_engine/scratch/`) |
| `state_tracker.js` | STALE | DeadGameBot tracker = ladder-repo territory now | low | verify-with-user |
| `viewer_prototype.html`, `matchup_config.json` | misc | stale | none | remove-candidate (keep `package.json`) |

### 2e. training/ legacy PNET cluster

| path | status | why | risk-if-removed | action |
|---|---|---|---|---|
| `vectorize.py`, `export_weights.py` | STALE (PNET) | state_dim 1290/1785; superseded by `*_v2` | none | archive (`training/legacy/`) |
| `schema_v1.json` | STALE (PNET) | **but `train.py` still hashes it (L776-788, 1042-1053) even in DeepSets mode** | breaks `train.py` run-metadata stamping | verify-with-user — fix `train.py` hash dependency FIRST, then archive |
| `extract_fleet_training_data.py`, `prepare_combined_dataset.py`, `split_dataset.py` | STALE (PNET) | superseded by `matchup_clean.js` + `vectorize_v2` | none | archive |
| `audit_dataset.py`, `sanity_check.py`, `evaluate_model.py`, `validate_extraction.py` | STALE (PNET QA) | ref legacy vectorize/schema_v1; some logic may be v2-reusable | low | verify-with-user |
| `test_resume.py` | SCRATCH | ad-hoc `--resume` smoke | none | keep or move to `tests/` |

### 2f. Stale H5 / vectorized intermediates (disk reclaim — verify the paired output exists first)

| path | size | status | why | action |
|---|---|---|---|---|
| **replay-parser JSONL** (`human_1500_all.jsonl` 67.6 GB, `human_1500_no6s.jsonl` 64.5 GB, `human_1800_clean_v1.jsonl` 28.2 GB, 6× `jsengine_v1_sample*` ~1.9 GB, `expert_1500_training_data.jsonl` 6.9 GB, `training_data*.jsonl` ~9.3 GB, others) | **~167 GB** | DATA (regenerable) | intermediates re-derivable from code lists via canonical extractor | remove-candidate (verify `.h5` exists) |
| `training/data/fleet_v3_v2_training.jsonl` + `fleet_v4_v2_training.jsonl` | **122.7 GB** | DATA (intermediate) | `fleet_v3_v2.h5`/`fleet_v4_v2.h5` already CURRENT | remove-candidate (highest-value, lowest-risk) |
| `training/data/{mb_fleet_filtered,masterbot_fleet_combined,raw_states,human_1500_v2,human_1500_no6s_v2,human_expert_v2,...}.jsonl` | **~110 GB** | STALE/PNET intermediate | superseded / PNET-era | remove-candidate |
| `training/data/masterbot_fleet/` + `masterbot_fleet_v3//v4/` + `splits/` | **~88 GB** | raw shards (vectorized) | rolled into `fleet_*_v2.h5`; regenerable | remove-candidate |
| `training/data/{fleet_v3,fleet_v4,fleet_v4_new,mb_fleet,local_mbvmb,dataset}.h5` | **~11.7 GB** | STALE H5 | non-v2 / PNET dims; `fleet_v4_new.h5` byte-dup of `fleet_v4.h5` | remove-candidate |
| `training/data/{human_1500_v2,human_1500_no6s_v2}.h5` | **~1.6 GB** | STALE (stat-contaminated) | pre-2019 unit stats; superseded by `human_1800_v2` | remove-candidate (after 1800 retrain locked) |
| `training/data/{test_dataset,test_deepsets}.h5`, `test_deepsets/`, `new_fleet_check/` | ~0.3 MB | SCRATCH | smoke-test artifacts | remove-candidate |
| `training/data/Local/Replays/` | **41 GB** | raw MBvMB replays | self-play source material | verify-with-user |

### 2g. Logs / stale outputs / stubs

| group | area | status | action |
|---|---|---|---|
| 432 `.log` (~1.1 GB; incl. 315 `LiveVsMB*_SingleUnit*`), 142 `_suggest_state_*.json`, `*.jsonl` (~68 GB), `overnight_run/` (~2 GB), `cloud_results/` (~133 MB), empty stubs | js_engine | LOG/DATA (gitignored) | remove-candidate (keep headline-result logs cited in docs) |
| `*.log`/`*_stderr.txt`/`*_report.txt`, dozens of 2-byte `*_all_replays_v2.json` stubs, stale `*_processed_codes.txt` | replay-parser | LOG/DATA | remove-candidate (keep canonical code lists + `balance_results.json`) |
| `eval/__pycache__/`, `eval/tests/__pycache__/`, `eval/.pytest_cache/` | eval | artifact | gitignore |

---

## 3. Doc fixes

| path | what's wrong | fix |
|---|---|---|
| `CLAUDE.md` — "Expert replay pipeline" + "Training pipeline (current)" blocks | Still list `extract_training_data.js` + `convert_human_to_v2.py` as live steps | Replace with `js_engine/extract_training_jsengine.js` (V2-direct); note convert step is bypassed |
| `docs/claude-app-instructions.md` | **Most misleading durable doc** — presents legacy PNET flat net (state_dim 1785, `export_weights.py`, `vectorize.py`) as current/deployed | Prepend SUPERSEDED banner → point to `dsnn-feature-schema.md` + `deepsets-training-results.md` (verify-with-user) |
| `docs/PROJECT_HISTORY.md` (L372/417/421/428/1066/1459/1681/1765/1769) | ~9 refs to `extract_training_data.js` as active tool (historically correct) | Do NOT rewrite history; add ONE forward-pointer note: "extraction superseded 2026-05-31 by `js_engine/extract_training_jsengine.js`; old TS path diverges on card_set/turn_number/p0_attack" |
| `docs/plans/engine-validation-plan.md` (L113/L465-467), `docs/session-logs/ctx4-engine-validation.md` (L71-75/242/310) | Cite `prismata-replay-parser/lib/replayParser.js`/`gameState.js` (the diverging TS port) as reference patterns | Archive both (completed work for an indicted path) |
| `docs/superpowers/plans/2026-03-19-js-extraction-pipeline.md` | `bulk_extract.js` replay-DB extractor; easily confused with training extractor | Add 1-line note: "this is the replay-DB extractor, NOT training-data `extract_training_jsengine.js`" |
| `docs/plans/2026-03-18-opening-book-analysis-planning-prompt.md`, `docs/superpowers/specs/2026-03-18-opening-book-analysis-design.md` | ref deprecated extractor for S3 fetch pattern; superseded by OB-explorer specs | archive |
| `eval/rl_campaign.md` §"Run prerequisites" item 6 | Stale — calls `run_eval.py::main()` an "incomplete Task-7 skeleton" / "EMPTY-anchors manifest"; made false by commit `8f02684` (Jun 6) | Update that one row to reflect `main()`→`build_manifest()` wired + tested |
| `training/export_weights_v2.py` docstring | Says "13" props; actual is dynamic 37 | Fix stale docstring |

---

## 4. Proposed reorganization

**replay-parser** — create `_archive/` with three subdirs:
- `_archive/deprecated_parser/` ← `extract_training_data.js`, `lib/`, `src/`, schema-gen, `dump_replay_states.js`, `batch_validate.js`, `check_defense_phase.js` + a `README.md` pointing to `js_engine/extract_training_jsengine.js` and naming the `diff_parsers.py` divergence as the reason.
- `_archive/scratch/` ← the ~50 Feb/May one-offs (2b/2c above).
- `_corpus_dumps/` ← ~130 per-player `*_all_replays*.json` (already imported into `replays.db`).

**js_engine** — create `js_engine/scratch/` for the legitimately-useful diagnostics (`corpus_scan`, `oracle_diff`, `classify_failures`, `flip_rate_diag`, `optA_stats`, `step_m7`, `verify_dsnn_load`, `smoke_dsnn`, `run_single_unit_sweep`, `validate_jsonl.py`, `batch_validate.py`); archive the dead MCDSAI cluster + `debug_*.js` separately. This leaves the ~10 canonical tools + engine core as the visible surface.

**training** — create `training/legacy/` for the PNET cluster (`vectorize.py`, `export_weights.py`, `convert_human_to_v2.py`, `prepare_combined_dataset.py`, `split_dataset.py`, `extract_fleet_training_data.py`, and `schema_v1.json` *after* the `train.py` hash dependency is resolved).

**docs** — create `docs/plans/_archive/` for completed `-CONTEXT.md`/`-v2.md`/`META-REVIEW-*.md`/`.pdf` sibling triplets and the two engine-validation docs; sweep `docs/scratch/` entries older than ~30 days into a dated subdir wholesale (don't chase individual deprecated refs — only 5 of 118 files mention them).

**eval** — no structural reorg; add `eval/.gitignore` (`__pycache__/`, `.pytest_cache/`, `backlog_action_space.md`). It is already a clean, single-sourced harness.

> Reorg caveat: archiving moves files — update CLAUDE.md "Expert replay pipeline" block and any plan docs that reference moved paths. Prefer `git mv` so history follows.

---

## 5. Open decisions for the user

1. **MB ↔ human `in_card_set` convention mismatch** — the two V2 extractors (`matchup_clean.js` vs `extract_training_jsengine.js`) disagree on `in_card_set`. This is the one *substantive* (not cleanup) question: do we (a) reconcile the convention and **re-extract + retrain**, or (b) flag-and-defer (KNOWN-FACTS says "flag, don't fix")? Recommend deferring to a dedicated work item; do not bundle into the cleanup.
2. **Large stale H5/JSONL deletion vs archive** — ~460 GB of regenerable intermediates. Confirm per-group deletion: the two `fleet_v*_v2_training.jsonl` (122.7 GB) and raw shard trees (88 GB) are the safest, highest-value deletes (their CURRENT `.h5` exist). The `human_1500*` corpora (~57 GB, stat-contaminated) only after the 1800 retrain is locked. **Verify each `.h5` exists before deleting its `.jsonl`.**
3. **`data/Local/Replays/` (41 GB) raw MBvMB** — keep as self-play source material, or dispose? (verify-with-user flagged in inventory.)
4. **Delete vs archive the deprecated extractor + `./lib`** — recommend **archive, not delete** (one historical baseline copy; it's the provenance of `human_1500_all.jsonl` and the thing `diff_parsers.py` measured against).
5. **`train.py` → `schema_v1.json` hash dependency** — `train.py` version-stamps run metadata from the legacy schema even in DeepSets mode (wrong generation stamped). Fix to hash `schema_v2.json` **before** `schema_v1.json` can be archived. Small code change; confirm you want it done.
6. **`state_tracker.js`** (js_engine) — DeadGameBot tracker; ladder-repo territory now. Relocate/archive, or leave?
7. **`docs/claude-app-instructions.md`** — top-level reference; confirm before bannering it SUPERSEDED.
8. **`prismata-replay-parser` `package.json`/`tsconfig`** — keep (harmless, needed only to rebuild `lib/`) or remove with the archived parser?

---

## 6. Suggested execution order (phased, lowest-risk first — nothing deleted without approval)

**Phase 0 — Zero-risk hygiene (no approval needed):**
- Add `eval/.gitignore` (`__pycache__/`, `.pytest_cache/`, `backlog_action_space.md`).
- Fix two stale docstrings/rows: `export_weights_v2.py` ("13"→37) and `eval/rl_campaign.md` §6 item 6 (`main()` now wired).

**Phase 1 — Deprecation banners (in-place, reversible, prevents foot-guns):**
- Banner `build_property_table.js` (DEAD, would overwrite the 37-prop table — **highest foot-gun**), `extract_training_data.js`, `bulk_extract.js`, `download_all_replays.js`.
- CLAUDE.md "Expert replay pipeline" + "Training pipeline" blocks → point to `extract_training_jsengine.js`.

**Phase 2 — Doc fixes (forward-pointers + SUPERSEDED banners):**
- `claude-app-instructions.md` banner (after decision #7), `PROJECT_HISTORY.md` forward-pointer, `2026-03-19-js-extraction-pipeline.md` note.

**Phase 3 — Resolve the `train.py` hash dependency (decision #5):**
- Repoint `train.py` schema hash to `schema_v2.json`; verify a smoke run. This unblocks archiving `schema_v1.json` + the PNET cluster.

**Phase 4 — Archive moves (`git mv`, reversible, after Phase 1-3 land):**
- replay-parser `_archive/deprecated_parser/` + `_archive/scratch/` + `_corpus_dumps/`.
- `js_engine/scratch/` + archive dead MCDSAI cluster + `debug_*.js`.
- `training/legacy/`.
- `docs/plans/_archive/` + dated `docs/scratch/` sweep + the two engine-validation docs.
- Update any moved-path references; commit.

**Phase 5 — Disk reclaim (destructive — requires explicit per-group approval, decisions #2/#3):**
1. `fleet_v3_v2_training.jsonl` + `fleet_v4_v2_training.jsonl` (122.7 GB) — verify `fleet_v*_v2.h5` exist, then delete.
2. Raw shard trees `masterbot_fleet*` + `splits/` (88 GB).
3. replay-parser regenerable JSONL (~167 GB) — verify paired `.h5`, then delete.
4. Stale non-v2/PNET H5 + remaining stale JSONL (~120 GB).
5. Logs / `_suggest_state_*` / `overnight_run/` / `cloud_results/` / empty stubs / `batch_validation/` / `__pycache__/`.
6. `human_1500*` corpora (~57 GB) — **only after** the 1800 retrain is locked.
7. `data/Local/Replays/` (41 GB) — only on explicit decision #3.

**Phase 6 — Deferred (separate work item, NOT cleanup):**
- The MB↔human `in_card_set` convention reconciliation + any re-extract/retrain (decision #1).

Key canonical anchors: `c:/libraries/PrismataAI/js_engine/extract_training_jsengine.js`, `c:/libraries/PrismataAI/js_engine/training_example.js`, `c:/libraries/PrismataAI/training/{vectorize_v2,train,export_weights_v2}.py`, `c:/libraries/PrismataAI/training/{schema_v2.json,property_table.json}`, `c:/libraries/prismata-replay-parser/{audit_ranked_balance,ladder_validate,build_human_val,build_replay_db}.py`. Foot-gun to banner first: `c:/libraries/PrismataAI/js_engine/build_property_table.js`. Code fix gating archive: `train.py` schema-hash → `schema_v1.json`.