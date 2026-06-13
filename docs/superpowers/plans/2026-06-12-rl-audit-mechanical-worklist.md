# RL Audit Mechanical Worklist (2026-06-12)

> **Handoff doc for an implementation session.** These are the MECHANICAL items from the third RL-loop
> audit (`docs/superpowers/plans/2026-06-12-rl-loop-design-audit-FINDINGS.md` — read its §§ for full
> evidence): each has one correct resolution determinable from the code; none requires an owner
> decision. The seven JUDGMENT items (J1–J7: training dose/schedule, promotion policy, anchor
> allocation, seed policy, IG exploration mechanism, tactical gate posture, volume-knob semantics) are
> owner decisions recorded separately — **do NOT implement those here**; where a task below touches a
> J-item's territory it is marked. Finding IDs in [brackets] map to the FINDINGS doc.
>
> Repos: main `c:/libraries/PrismataAI` (branch `feature/production-vectors`); engine
> `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`, builds x64/v145 — see
> CLAUDE.md "dave-master build"). After ANY engine change: rebuild Prismata_Testing + Standalone,
> verify with a diagnostic-string grep (never mtime), run `python -m pytest training/tests eval/tests`
> (expect 216+) and `python eval/preflight_config.py` (10/10) before finishing.

## A. Engine (dave-master)

- [ ] **A1. Seeded-random argmax tie-break** [selfplay-02]. Root argmax in `UCTSearch.cpp` (~:117-126,
  `v > maxVisits` first-wins) and `MoveSampler.cpp::argmaxEligible` (~:10-18) both resolve visit ties
  to the FIRST index; children are sorted longest-move-first (`MoveIterator_AbilitySubset.cpp:52-53`),
  so ties systematically resolve toward MORE IG clicks. Break ties uniformly at random from the
  engine's seedable RNG stream (preserves reproducibility). Cover with a unit-style check if feasible.
- [ ] **A2. Player name in NeuralNet load line** [prov-06]. `AIParameters.cpp` ~:30/:36 prints
  "created per-player NeuralNet from <path>" without the player name (name IS in scope — the FATAL at
  :41 uses it). Add the name; then update `run_eval.py` `engine_confirmed_load` /
  `engine_confirmed_parent_load` to match (player, basename) pairs instead of file-level substrings.
- [ ] **A3. mappedTypes==0 → FATAL for NeuralNet-eval players** [impl-unitindex-05].
  `AIParameters.cpp` ~:29/:35 discards `buildCardTypeMapping()`'s return; a missing/corrupt
  `unit_index.json` leaves `isLoaded()==true` and the net silently evaluates on globals only
  (`AITools.cpp:295-300` comment). Mirror the X5b hard-fail rationale.
- [ ] **A4. Per-round (per-card-set) result emission** [stats-05, rl-design-05]. Tournament currently
  emits only aggregate W/L/D; the eval design is intrinsically paired (one set per round, both seat
  orders). Emit per-round records (block, round, set id/seed-index, seat, winner) — statsTable
  extension or sidecar CSV, same scale of change as the `6e93480` per-seat columns. Then in
  `run_eval.py` compute a paired per-set differential CI alongside the existing Wilson numbers
  (REPORT both; do NOT change the verdict rule — that is J2 territory). Annotate manifests that the
  iid Wilson CI is conditional-on-pairing until then.
- [ ] **A5. Fix the wrong perspective comment** [a6-seam-01]. `UCTSearch.cpp` ~:374 says the net
  returns "value from active player's perspective" — it returns the MAXPLAYER's perspective
  (negation at `NeuralNet.cpp:692-694`). Comment-only fix; sits at the exact untested seam.

## B. Gates & tests (main repo)

- [ ] **B1. A6 end-to-end orientation test** [a6-seam-01]. The maxPlayer negation +
  `(nnValue+1)/2` consumption is pinned by NO test, and the stage-5 oracle always evaluates from
  Player_One so the negation branch never runs under any gate. Build the missing test (~2h on
  existing machinery): two near-decided curated states (one with each seat to move and winning),
  driven through `js_engine/query_move.js`, asserting the responder keeps the winning continuation
  (or sides correctly via aivalue/aivisits) from BOTH seats. Add it to the §4 triage list in
  `eval/rl_campaign.md` and the promotion checklist.
- [ ] **B2. Parity gate honesty** [parity-gate-01]. `tools/parity/compare_parity_deepsets.py`:
  VALUE_TOL 1e-3 → **1e-4** (measured floor ~1e-6); replace the sorted-prefix state sample
  (`dump_value_batch.py` ~:67-71 — will be ~100% forced-slice) with a deterministic stratified pick
  interleaving `general_`/`forced_`. Correct `rl_runbook.md:83` + `rl_campaign.md` A6 text: the gate
  pins weights-export + forward arithmetic ONLY (the PyTorch reference consumes C++-extracted
  features); feature extraction is pinned by the three-way gate.
- [ ] **B3. Three-way gate fixture coverage** [threeway-cov-01]. The fixture (4 plies of one human
  replay) never exercises `is_frozen`, `lifespan_remaining`, damaged-HP, and has zero IG states
  (measured). Add 3–5 states: frozen/chilled unit, damaged unit, lifespan unit, and ≥1 forced-Hotel
  self-play sidecar (use NATIVE archived `sp_*.json.gz` via `--dump-v2-record`/`--dump-features` —
  no `stateToCppJSON` round-trip, which drops damage/abilityUsed). Document non-covered features in
  the test docstring.
- [ ] **B4. Steam anchor conventions + one-off cross-path run** [steam-07, edge-08]. In
  `run_eval.py`: parse validGames (and draws) from matchup output and use for rate+CI; annotate the
  manifest cell's draw convention (steam: draws-count-against-both; C++: draw=half-win); a completed
  anchor with 0 games → INCOMPLETE, not REVIEW. Run the deferred **128-game cross-path sanity check**
  once (HardestAIUCT self-play, both paths) and replace the vacuous 16-game "bound" text in
  `eval/README.md` with the measured number.
- [ ] **B5. Prediction-movement probe (stage 4.5 addition)** [training-01 rider]. New cheap
  instrument: mean |V_candidate − V_parent| + winner-flip % over a fixed probe batch (e.g. 1–2k
  archived sidecar states, pinned set). Record in run_metadata + manifest + `eval/campaign_log.md`
  entry template. This is the loop's only direct null-update detector; seconds of CPU.
- [ ] **B6. IG-contrast watch-stat** [selfplay-01 rider]. Per iteration, count matched colour-swap
  pairs (same set, both seats) whose IG-click-count sequences DIFFER — the realized counterfactual
  count on the campaign axis. Compute from the V2 shards/stamps in stage 8; emit in manifest +
  dashboard.
- [ ] **B8. Cumulative-forgetting guard at checkpoints** [training-07 rider, added 06-13]. The 4.5
  tripwire compares candidate vs PARENT (3pp band); after promotions the parent moves, so human-val
  acc can ratchet down ~3pp per promotion without ever tripping. At each J2 checkpoint (powered
  origin eval), also assert candidate human-val acc ≥ the ORIGIN constant (v221 = 71.8% on
  human_val_1700) minus a wider band (e.g. 5pp). One comparison against a constant; record in the
  checkpoint log entry. If it trips, the pre-registered response is raising the rehearsal fraction
  (see rl_data.py schedule), not aborting.
- [ ] **B7. N/c discrimination probe (info-only run)** [selfplay-02 rider]. Re-run the 41-state probe
  at c=0.15 and/or N=4000; report top-share/entropy medians vs the frozen tuple's (0.141/0.984).
  Commit the artifact + producer script (also closes N-9's producer gap). OUTCOME IS OWNER INPUT
  (possible N/c re-freeze) — do not change config.

## C. Ops & driver (main repo)

- [ ] **C1. Promotion script + content pinning** [ops-promote-01]. `eval/promote_candidate.ps1`:
  takes K; asserts sha256(fresh re-export of new `parent_pt`) == sha256(new `parent_bin`); writes
  `parent_bin_sha256` into `campaign_frozen.json`; repoints the four parent-pinned players via the
  existing Edit-Config machinery; runs preflight; prints the two per-repo commit commands. Add the
  matching preflight CONTENT check (sha of on-disk parent bin == frozen sha — also catches the
  same-K re-export clobber). Driver startup guard: throw if `$candBin` == frozen `parent_bin`.
- [ ] **C2. Frozen-identity enforcement extension** [preflight-gaps-06, docs-02]. Extend
  `campaign_frozen.json` + `preflight_config.py`: eval budget (TimeLimit 7000 / MaxTraversals 100000)
  + UCTConstant on RL_Eval/RL_Eval_iter0/RL_Narrow; the four anchor blocks' rounds/Seed/Threads;
  `window_W` (assert `-Window` matches); sha256 pins for the two H5s + masterbot exe;
  `unit_index.json` exists + parses + 116 units [impl-unitindex-05]. Make `run_eval.py` read the
  eval budget FROM config and record actuals in the manifest (currently hardcoded ~:428). NOTE: seed
  *values* and rounds will change under J4/J1 — implement the enforcement plumbing now, freeze
  values after those decisions.
- [ ] **C3. TOCTOU + concurrency** [ops-toctou-07]. Two-line use_dsnn-sentinel + PRISMATA_FORCE_DSNN
  asserts at the top of `eval/tactical_suite.py` and `eval/action_coverage.py` (mirror
  `run_eval.py:538-539`). Driver lockfile (`eval/.iteration.lock`, created at start, removed in
  finally, stale-age warning). Document: no calibrate/matchup runs during an iteration.
- [ ] **C4. Resumability + ledger + transcript** [ops-resume-03]. `-ResumeFrom <stage>` switch
  (stages 2+ need only the already-archived `rl_iter_<K>` artifacts; refuse if absent). Validate K at
  startup (≥1; warn if `rl_iter_<K-1>` absent and K>1). Tee driver output to
  `$workDir/iteration_<K>.log`; capture stage-1 engine stderr/stdout to a log and grep for
  `WARNING:` post-run [impl-unitindex-05 rider]. Append a machine line per run (K, timestamps,
  parent sha, candidate sha, stage reached, verdict) — `eval/campaign_log.jsonl` companion to the
  human `eval/campaign_log.md`.
- [ ] **C5. Window lineage stamps** [training-05, ops-quarantine-04]. At vectorize time stamp each
  `selfplay_iter_<K>.h5` (H5 attrs: parent_bin sha256, frozen-tuple hash, slice counts, generation
  date). Stage-3 pre-check (or `select_replay_window`): refuse files whose stamps mismatch the
  current campaign identity unless `--override`; honor an `INVALID` marker file in `rl_iter_<K>/`.
  Correct `rl_runbook.md:118-121`: a non-promoted candidate's H5 is PARENT-generated and stays in
  the window; quarantine applies only to invalid GENERATION runs.
- [ ] **C6. Stage-3 efficiency + reproducibility + ELITE rehearsal set** [training-04, training-06;
  owner decisions 06-13]. Build the new rehearsal H5 by SLICING `human_1800_v2.h5` directly —
  NO re-extraction, NO DB-based eligibility (provenance is inherited: every record already passed
  the full exclusion pipeline; the elite cut only subtracts; some codes exist in NO local DB — the
  set was built from replays.db + the ladder-site DB):
  (1) rating filter from the H5's own per-record `rating_p0`/`rating_p1`: per-game min ≥ 2000;
  (2) time filter from the archived replay JSONs (`replays_archive/<urlencoded-code>.json.gz`,
  guaranteed present for every H5 code — the JS-engine extraction consumed them):
  `timeInfo.playerTime[*].increment >= 45` for both players (note `timeInfo.correspondence` games
  are effectively untimed — include them, they have maximal think time);
  (3) slice rows by code keeping whole games, randomly sample ~5k games / ~150k records, copy all
  datasets + root attrs (preserve `schema_hash`, update `num_records`); record the selected code
  list + sampling seed as the provenance artifact next to the H5.
  The VAL set and 4.5 tripwire stay on `human_val_1700_v2.h5` UNCHANGED (instrument comparability).
  Wire as `--human-file`; HP-tier change → part of the single pre-K1 re-freeze. Also:
  cap/subsample the tripwire val set (~50k → ±0.4pp vs the 3pp threshold); `num_workers=0` for the
  RL loader; cache the parent's val-acc at promotion time instead of recomputing both sides every
  iteration; pin the training seed (argv + run_metadata stamp).
- [ ] **C7. Stage-3 full-size dry run** [training-04]. Before `-K 1`: run stage 3 alone at full size
  (point `--selfplay-files` at any existing small V2 H5) and record RAM/wall-clock. The post-fix
  full-size path has never executed.
- [ ] **C8. Stage-8 coverage scope** [coverage-prov-01]. `action_coverage.py` invocation reads the
  FORCED dir only and describes the PARENT's self-play behaviour; pass both dirs, relabel manifest
  keys (or split `forced_`/`general_`), and note the parent-behaviour semantics in runbook stage 8.
- [ ] **C9. Papercuts** [impl-papercuts-08, env-01]. Atomic config writes (temp + rename) in the
  driver's Edit-Config; check `render_dashboard.py` exit code; build-freshness guard (embed git
  short-sha diagnostic string in the exes at build, or a build-stamp file preflight can compare —
  replaces the manual mtime convention).

## D. Documentation pass (one sitting)

- [ ] **D1.** [docs-01] Add `--swa-lr 5e-6` + the warmup auto-rescale policy to the `rl_campaign.md`
  §1 SWA row and the runbook knobs list (values per J1's outcome). Add the 3-line tactical
  case-provenance note (4 armed; 2 dropped flaky at 18%/33% false-fail @3s; ktink knife-edge 11/3)
  to runbook stage 6 or `tactical_suite.py`'s header.
- [ ] **D2.** [docs-03] Replace "≈600 games" with "~786 games @ 80% power (one-sided α=0.025)" in
  `rl_campaign.md` §4.7 (it sizes the AWS decision); fix the Jun-11 verification doc's resolution row
  (§3.1) from FIXED to PARTIAL→now-fixed; add the missing `selfplay_replays` row to the runbook's
  preflight table (10 checks, not 9) + README enumeration.
- [ ] **D3.** [docs-04] Spec status banner + per-section table on
  `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` (§5/§12 SUPERSEDED by campaign
  §3; §3 sampler values superseded by regime v2; §8.5 + §6 axes 2–4 still authoritative). Fix
  `rl_campaign.md` ~:308's dangling "(§8.5)" cross-ref to name the spec explicitly.
- [ ] **D4.** [selfplay-04] Correct `rl_campaign.md` §1b + the campaign_frozen rationale text: a
  record's label noise depends on ALL deviations after it (either player); only records after the
  LAST deviation are greedy-truthful; v2 = ~10× total-deviation reduction vs v1, not an early/late
  asymmetry. (Matters when Lever 0 is considered.)
- [ ] **D5.** [selfplay-02] Document the ~7–12pp UCB root indifference band at the frozen (N=1000,
  c=0.3) in `rl_campaign.md` §1 (N row or new §1f), incl. what it implies for "late-precision" and
  the now-fixed tie-break bias.
- [ ] **D6.** Small items: `mirror_record` docstring (role = A6 perspective spec, NOT used as
  augmentation; naive enablement unsound) [mirror-unused-01]; Base+8 scope-limit note (conclusions
  are RandomCards:8-scoped) [rl-design-07]; 200-instance vectorize cap vs uncapped C++ inference
  asymmetry note/assert [vectorize-ok-01]; "214/0" → measured 216/0 [env-02]; failure-mode/recovery
  table folded into `rl_runbook.md` (which stages resumable, what each crash leaves, where C4's
  artifacts are) [docs-06]; de-duplicate the quadruplicated tuple/verdict statements to pointers at
  one canonical home each [docs-07].

## NOT in this list (owner decisions J1–J7, implement only after they're made)

Rounds scaling + SWA/rehearsal/lr argv changes (J1) · promotion-policy text + powered checkpoint-eval
block (J2) · anchor-block reallocation + `RL_Eval_origin` player (J3) · seed-from-K driver logic +
eval-seed split (J4) · targeted IG-ε sampler (J5) · tactical majority-rerun/budget/abort posture (J6)
· two-tier tuple semantics in campaign_frozen + §1/prereq-7 reconciliation (J7). Those decisions plus
this worklist then converge in ONE deliberate re-freeze of `campaign_frozen.json` + preflight +
re-anchor before `-K 1`.
