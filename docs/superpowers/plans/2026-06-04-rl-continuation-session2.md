# RL Self-Play Loop — Continuation Prompt (Session 2, 2026-06-04)

Continue executing the RL self-play implementation, subagent-driven. **Invoke `superpowers:subagent-driven-development`** and resume at the REMAINING tasks below. Per-task discipline: dispatch implementer (full task text + curated context, no plan-reading) → spec-compliance review → code-quality review → fix loop → ONE commit per task → next. Dispatch fresh fix agents (SendMessage to a prior subagent is unavailable).

**PLAN:** `docs/superpowers/plans/2026-06-03-rl-selfplay-loop-implementation.md` — read it fully INCLUDING the "External-review addenda (A1–A12)" near the end (A1/A6/A7/A12 are load-bearing). **But see the IG REDESIGN below — the plan's axis-1 (Task 12 "binary IG-optional ActivateUtility filter") is SUPERSEDED.**

## ⚠ CRITICAL: axis-1 was redesigned (the plan is stale on this)
The plan models axis-1 as a binary "fire-IG / skip-IG" ActivateUtility filter. **That was wrong** (user-confirmed). The real decision is the **COUNT** of Infusion Grid (codename "Hotel") selfsac-clicks: each click pays R and sacrifices a 4HP unit → four 1HP Husks; the value is **defensive granularity** (vs freeze, e.g. Nivo Charges). **Usually click-1 is correct; the deployed AI over-clicks (fires all).** A binary filter can't express "1 of 2".
- **Built + committed:** `MoveIterator_AbilitySubset` (engine `dave-master-jsonclean@4bfdb61`) — a new `"AbilitySubset"` iterator type that wraps an inner PPPortfolio (ability variant excludes IG) and cross-products each whole-turn with IG-click subsets {0..N} (reuses `MoveIterator_AllAbility` recurse + isomorphic collapse, SCOPED to a card filter; regenerates Buy/Breach fresh per subset; ROOT-iterator only). Config: `IG_Only` filter, `HardIterator_5var_NoIG_Root` base, `HardIterator_5var_IGsubset_Root`; `RL_SelfPlay`/`RL_Eval`/`RL_Eval_iter0` repointed to it.
- **VERIFIED** on the real over-click state `docs/scratch/ktink_t9_action_request.json`: greedy `HardIterator_5var_Root` → 4 root children, argmax fires **2** IGs (the bug); `HardIterator_5var_IGsubset_Root` → **8** children, argmax fires **1** (correct). The net already preferred click-1; it just lacked the candidate.
- Full context: memory `project_ig_action_space_subset_decision.md` + `docs/rl-action-space-partials-map.md` §1/§4.
- **Implication for downstream tasks:** the IG "go-signal" is the **IG-click-count distribution** (not binary fire-rate). Task 5 Step 2 exporter stamps, Task 7's `action_coverage.py`, and Task 10's `tactical_suite.py` must all track COUNT, not binary.

## TWO REPOS (never cross-file; NEVER engine_v2)
- **Engine C++** = `c:/libraries/PrismataAI-dave-master` branch `dave-master-jsonclean`
- **Main** (train/JS/eval/docs) = `c:/libraries/PrismataAI` branch `feature/production-vectors`
- BRANCH HAZARD: `git branch --show-current` in BOTH before any commit. Main can switch to `feature/multicore-dsnn-play`. Push to PrismatAlpha fork ONLY, only when the user explicitly asks.
- A concurrent **multicore session** works in a worktree off `dave-master-jsonclean` and commits coordination docs to `feature/production-vectors` (e.g. `multicore-rl-coordination.md`) — harmless, don't be surprised by extra HEAD commits.

## BUILD (engine): x64, v145, always :Rebuild, stop running exes first (LNK1104)
```
"/c/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe" \
 c:/libraries/PrismataAI-dave-master/visualstudio/Prismata.sln \
 //t:Prismata_standalone:Rebuild //t:Prismata_Testing:Rebuild \
 //p:Configuration=Release //p:Platform=x64 //p:PlatformToolset=v145 //m
```
Outputs: `bin/PrismataAI.exe` (Steam-protocol responder; the `query_move.js`/matchup target), `bin/Prismata_Testing.exe` (runs every `"run":true` config.txt Benchmarks block). config.txt is STRICT JSON (no comments). Python tests: `cd c:/libraries/PrismataAI/training && python -m pytest tests/<f>.py -v`.

## DONE THIS SESSION (do NOT redo)
**Engine `dave-master-jsonclean`** (in order): `67d9b74` A12 (standalone loads config.txt defs — players skipped to avoid weight loads — then merges the per-request SWF blob without reset, so config-only iterators resolve on the Steam path); `4ec543d` Task 10 (`aivisits`/`aiargmax`/`aichosen` diagnostics gated by `EmitDiagnostics`; `Player_UCT::lastRootVisits/lastChosenIdx/lastArgmaxIdx`); `c132f26` null-safe `getPlayer`+`PlayerShouldResign`; `988c302` **resignation DISABLED** (gated `ENABLE_RESIGNATION=false`, user decision: no early resignation on eval/self-play); `1cc001e`+`2536883` Task 12 (binary IG-optional config — SUPERSEDED — + forced-card-set `GameState::setStartingState(p,n,forcedCards)` + `Tournament` `ForcedCards`); `4bfdb61` **MoveIterator_AbilitySubset** (IG-subset, see above); `1994698` **A2** (optional late-ε `EpsilonLate`, default 0/off; completes RL-hot UCTSearch changes). Earlier: `9c64813` Task 7 eval config blocks, `0869604` Task 8 exporter parity sidecar.
**Main `feature/production-vectors`**: `9588a5d` Task 6 (`training/rl_data.py` + `--rl-mode` in train.py + label tests); `79eb999` Task 7 (`eval/wilson.py` w/ A3 group-sequential + A4 clustered CI, `eval/run_eval.py`, `eval/action_coverage.py`, `eval/README.md`); `a56e9c3` Task 8 (`tools/parity/dump_value_batch.py`); `37b59c8` Task 9 (`eval/human_val.py`); `8874c63` Task 10 (`js_engine/query_move.js`, `eval/tactical_suite.py`).

## ENGINE HANDOFF (for the multicore session — tell the user)
Search surface they extend (`UCTSearch`, `UCTSearchParameters`, `UCTNode`, `Player_UCT`, `AITools`) is **stable at `dave-master-jsonclean@1994698`** (A2 was the last touch). Remaining RL engine work (exporter stamps) is testing-dir only and doesn't touch their surface. Their own finding: FORCE_DSNN live path runs default `c=2.0` (mis-tuned vs config's `0.3`) — their fix, not RL's.

## REMAINING TASKS (resume here)
1. **Task 5 Step 2 — exporter stamps (engine, testing dir).** Add to each `SelfPlayV2Exporter` V2 record: `ig_present` (active player has ≥1 alive IG at turn-start), `ig_click_count` (# IG selfsacs in the PLAYED/sampled move — count `USE_ABILITY` on IG instances; **plumb the move/count into `capture()` from `TournamentGame`** — the record is captured at turn-START which is pre-swoosh/defense, so IG legality+the count must come from the computed action-phase MOVE, not the turn-start state), `sampled_idx`/`argmax_idx` (from the existing `Player_UCT::lastChosenIdx()/lastArgmaxIdx()`). Feeds `action_coverage.py` + the campaign go-signal. Rebuild + verify on a forced-IG self-play smoke.
2. **Tactical case + suite reframe (main).** Curate `docs/scratch/ktink_t9_action_request.json` as a real case (correct = click-1, greedy does 2). Reframe `eval/tactical_suite.py` from binary `fires_hotel` → **IG-click count** (`expect.ig_click_count`). Click shape: ability-use = `{type:"inst clicked"|"inst shift clicked", args:{cardName:"Infusion Grid"}}`; buy = `{type:"card clicked", args:"Infusion Grid"}`. Also fix `action_coverage.py`'s IG detector (the plan's `{_type,_id}` assumption is WRONG — use the real shape above).
3. **Task 13 — N-calibration** (`eval/calibrate_n.py` + per-N config blocks). Apply **A5**: root-entropy = effective post-ε distribution (not raw aivisits); sweep ε alongside N. Uses `query_move.js` aivisits.
4. **Task 11 — off-book reachability audit** (axis-2, optional/parallel; `--probe-buys` engine hook + `RL_Explore` player + `eval/offbook_audit.py`).
5. **Task 14 — freeze HP tuple + iter-0/1 campaign** (`eval/rl_campaign.md`, `eval/run_iteration.ps1`, `eval/render_dashboard.py`). Apply A1 (eval at deployment budget; d_reg from `RL_Eval_iter0_general`), A2 (enable `EpsilonLate≈0.05` FIRST if axis-1 flat), A6 (perspective round-trip), A9 (pre-register a STOP condition). Repoint `RL_Eval_iter0` WeightsFile from the placeholder (`neural_weights_mixed_35prop.bin`) to the real wide-untrained iter-0 weights. The culmination — runs self-play → V2 export → train (`--rl-mode`) → export_weights_v2 → 3-anchor eval. Measure throughput before any AWS spend.
6. **Final**: whole-implementation review → `superpowers:finishing-a-development-branch`. Clean up `docs/scratch/` throwaways from this session (a12_*.py, harden_*.py, ig_count_t9.py, etc.; KEEP `ktink_replay.json.gz` + `ktink_t9_action_request.json`).

## GOTCHAS LEARNED THIS SESSION
- **F6 dumps from the game client = DEFENSE phase (pre-swoosh: IGs tapped, 0 red)** — useless for testing IG-fire. For action-phase IG states, REPLAY the server replay via the JS engine: `Analyzer` + `recordClick` over `commandInfo.commandList` to the post-swoosh action phase, then `replay_exporter.stateToCppJSON`. (That's how `ktink_t9_action_request.json` was made — replay code `KtInk-pMiQf`, P1=Master Bot=the DSNN AI, P1 turn-9 = slice 16, cmds 0..149.)
- The 4 old F6 dumps (`F6_test/FIm28-4p1PP/S1gfK-xUO5j/VXGaI-n97ZU`.txt) are pre-JS-fix UNPARSEABLE replays → degenerate states → NOT valid test fixtures.
- `query_move.js` does NOT forward the exe's stderr (so engine debug prints don't surface through it).
- Git Bash `/tmp` ≠ `C:\tmp` (node reads `C:\tmp`). Use explicit real paths for cross-tool files.
- `run_eval.parse_tournament_stdout` reads the HTML `statsTable` file (NOT stdout) for C++ tournament W/L/D.
- A7: `parse_matchup_seatindep` must read the `--- Win Rates (seat-independent) ---` identity block, not the White seat.
- Self-play tournament blocks need the player in group:1 AND group:2 (same-group = 0 games). Reproducible self-play = Threads:1 + non-zero Seed.
- Replay fetch: `https://saved-games-alpha.s3.amazonaws.com/{CODE}.json.gz`.

## VERIFICATION ASSETS
- `docs/scratch/ktink_t9_action_request.json` — real IG over-click state (greedy argmax=2 IGs, IGsubset argmax=1). Verify any IG lever against it via: `node js_engine/query_move.js --request docs/scratch/ktink_t9_action_request.json --player RL_Eval --weights neural_weights_mixed_35prop.bin --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe --root-iterator HardIterator_5var_IGsubset_Root --move-iterator HardIterator_5var`.
- `tools/parity/dump_value_batch.py` (matched-triple rule: `--weights` .bin must match `--pt`/`--bin` reference).
