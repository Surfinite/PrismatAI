# RL self-play eval harness

Per-iteration evaluation for the RL self-play loop: win-rate math with **iid Wilson CIs**, a
**REJECT / REVIEW / INCOMPLETE verdict** (detect-proven-harm; nothing auto-promotes), an **incremental
atomic manifest**, **active provenance** (config pre-flight + engine-stderr load confirmation),
and action-coverage metrics for the IG-optional axis. The campaign contract is
`eval/rl_campaign.md`; the operational reference is `eval/rl_runbook.md`; the frozen tuple is
`eval/campaign_frozen.json`.

```
eval/
  wilson.py             # win_rate + wilson_ci (iid 95%) — the COMPLETE stats surface (see below)
  run_eval.py           # orchestrator: anchors, verdict, provenance, incremental manifest
  preflight_config.py   # stage 0: config integrity + frozen tuple + parent re-pin (hard-fails)
  campaign_frozen.json  # the frozen HP tuple (N=1000, tau=0.7, K=12, eps=0 + EpsilonLate=0.05, c=0.3, Threads:8)
  run_iteration.ps1     # one-iteration driver (stages 0-8)
  tactical_suite.py     # O7 IG-click-COUNT regression suite (vs tactical_baseline.json)
  action_coverage.py    # IG click-count distribution + feasible-max binning
  render_dashboard.py   # per-iteration human-facing results table
  calib_states/         # 41 curated states (incl. ktink_t9) — calibration + coverage probes
  ig_battery/           # IG battery states (tactical/coverage defaults)
  tests/                # test_wilson, test_parse, test_run_eval_main, test_preflight,
                        # test_dashboard, test_ig_feasible
  manifests/            # per-iteration eval_iter_<N>.json output
```

Run the tests:

```
cd c:/libraries/PrismataAI/eval && python -m pytest tests/ -v
```

## The three anchors (one path each)

| Anchor   | What                                                         | Path                                  | Role |
|----------|--------------------------------------------------------------|---------------------------------------|------|
| `iter0`  | candidate vs **PARENT promoted net** (`RL_Eval_iter0` = v221, SAME IG-optional config + budget) | C++ tournament (`Prismata_Testing.exe`) | **verdict input** (general pool); forced pool = `d_rl` info |
| `narrow` | `RL_Narrow` = v221 on `HardIterator_5var_Root` (**iterator-only variable** vs the candidate) | C++ tournament                        | trajectory yardstick (non-gating) |
| `steam`  | candidate (DaveAI + injected `RL_Eval` block + `--candidate-weights`) vs the **genuine 2016 MasterBot** at `c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe` | `matchup_clean.js`, `--player-switch`, `--steam-exe-b` | trajectory yardstick (non-gating; **live 2-game verified** post F-08 rewire) |

The earlier narrow anchor (`DSNN_Mixed35_5var`) was replaced by `RL_Narrow` so the narrow
comparison isolates the iterator (same v221 net, same budget, same c=0.3). The earlier steam
anchor was mis-wired (the candidate never played); the F-08 rewire injects an `RL_Eval` player
block into the DaveAI side and threads the candidate `.bin` via `--candidate-weights`.

## Verdict (replaces the old GO / sequential gate — 2026-06-10)

The old rule (`d_rl >= +5pp AND CI-lower > 0.5`, group-sequential 128→256→512) was deleted as
statistically incoherent at 128 games (P(GO | true +5pp) ≈ 13%). Now (`run_eval.py`):

- **REJECT** iff the iter0/**general** anchor completed AND its 95% Wilson `ci_upper < 0.5`
  (candidate statistically proven worse than the parent);
- **REVIEW** iff it completed and `ci_upper >= 0.5` (everything else is a human call);
- **INCOMPLETE** iff that anchor is missing/errored.

`d_rl` (forced) and `d_reg` (general) are recorded as **information only**, each with a Wilson CI
on the win rate (`forced_wr_ci` / `general_wr_ci`). Nothing auto-promotes.

## Statistics: iid Wilson ONLY

`wilson.py` (`win_rate`, `wilson_ci`) is the **complete** statistics surface. The former
`decisive` / `decisive_gate` (A3 Pocock sequential) / `clustered_ci` (A4 per-card-set) helpers
were **dead code with zero live callers** and were removed 2026-06-10 per the RL-loop audit:
the C++ tournament HTML emits only aggregate W/L/D/Games per player — **no per-card-set scores
exist to cluster on, and no sequential-testing machinery is wired anywhere**.

## Incremental manifest + active provenance

- The manifest is (re)written **atomically after every completed pool/anchor** (temp file +
  `os.replace`), carrying `"complete": false` and `anchors_completed` until the final write — a
  killed run no longer erases hours of tournament results (the Jun-8 failure mode).
- **Provenance is active, not just a stamp**: before any block flips on, `run_eval.py` asserts
  `Players.RL_Eval.WeightsFile` == the `--weights` basename (hard abort otherwise). Each C++
  anchor's engine **stderr must contain the per-player NeuralNet load line for the candidate
  `.bin`** ("AIParameters: created per-player NeuralNet from ..."); the result is stamped
  `engine_confirmed_load` and a completed-but-unconfirmed anchor **hard-fails** after being
  recorded for the post-mortem.
- Engine-side guardrails (dave `26075fa`/`d0ec633`): the engine now **hard-fails at construction**
  on an unknown or raw-empty opening book, an unknown filter (including the
  `findCardFilter`/`subsetFilter` path), and a NeuralNet weights-load failure; the UCT value path
  guards against an unloaded net (X5b). Filtered-to-empty books warn once instead of dying.

## Deployment budget, not self-play N (A1)

All eval players run at the **deployment budget** `TimeLimit:7000 / MaxTraversals:100000`,
NOT the self-play throughput N. `RL_SelfPlay` runs the frozen self-play tuple
(`MaxTraversals:1000`, τ=0.7, K=12, εUniform=0, εLate=0.05 — regime v2, `campaign_frozen.json`,
preflight-asserted) — the eval budget is decoupled from the self-play budget.

## d_reg rule (A1)

`d_reg` (candidate vs the parent net — informational since 2026-06-10) **must** come from
`RL_Eval_iter0_general` — SAME config + SAME budget. Do **not** compute it from the `narrow`
anchor: `RL_Narrow` runs a different iterator (`HardIterator_5var_Root`) at the same budget, so
an iterator gap would masquerade as a net regression. `narrow` and `steam` are **trajectory
yardsticks only** — never gate on them.

## A7 — seat-independent identity parsing (NOT the seat tally)

`matchup_clean.js --player-switch` prints, at the end of a run, a seat-independent block:

```
[Parallel] --- Win Rates (seat-independent) ---
[Parallel] Player A [DAVEAI[RL_Eval]]: 53.9%
[Parallel] Player B [STEAMAI[HardestAI]]: 46.1%
```

`parse_matchup_seatindep()` reads the **candidate identity's** rate from this block
(exact-case substring on the label — `RL_Eval` keeps its argv case). It deliberately ignores the
`[Parallel] White: N (X%)` / `Black:` / `Draws:` seat tally — for a switched candidate the seat
tally is NOT the candidate's win rate. (`[Pair]` is the serial path; `[Parallel]` is parallel.)

## A8 — STEAMAI is a fixed-N yardstick

The STEAMAI yardstick uses a fixed `--steam-games` N (default 200) plus a Wilson CI — no
escalation (no sequential machinery exists anywhere; see the statistics note above). The
`narrow` C++ yardstick is likewise a fixed-N comparison + CI.

## Parse-format note (validated Step 5, 2026-06-03)

The C++ tournament's **stdout** carries only a seat-symmetric *score matrix* (player×player
score + a `TotalScore` column) and a `Games completed:` line — it does **not** carry
per-player Wins/Loss/Draw/Games. The canonical per-player W/L/D/Games table is written to the
**HTML** results file `tests/Tournament_<name>_<date>.html` (table `id="statsTable"`, columns
Player, Score, Games, Wins, Loss, Draw, …). `run_cpp_tournament()` reads that HTML file (with a
staleness guard: the HTML's mtime must postdate the run) and `parse_tournament_stdout()` parses
its statsTable rows; a stdout score-matrix fallback is kept for diagnostics. The original plan
regex (which assumed W/L/D in stdout) was corrected to this HTML-statsTable form, validated
against a real `AB_5var_Smoke` run
(`{DSNN_Mixed35_5var_F1s: w2 d0 g4, DSNN_M35_1s_c03: w2 d0 g4}`).

## Config blocks (dave `config.txt`)

Four anchor tournament blocks (paired group1/group2, `Seed:2026`, `RandomCards:8`,
`Threads:8`, `rounds:64`, `run:false` at rest — `run_eval.py` flips one at a time and flips it
back in a `finally`):

- `RL_Eval_iter0_forced` (`ForcedCards:["Hotel"]`) / `RL_Eval_iter0_general` — `RL_Eval` vs `RL_Eval_iter0`
- `RL_Eval_narrow_forced` (`ForcedCards:["Hotel"]`) / `RL_Eval_narrow_general` — `RL_Eval` vs `RL_Narrow`

`ForcedCards` IS wired (engine support landed; the self-play block `RL_Step2_Smoke` also forces
Hotel), and `RL_Eval_iter0` is a fully defined player pointing at `neural_weights_mixed_v221.bin`
(the parent — per the 2026-06-07 decision, NOT a wide-untrained placeholder).
`eval/preflight_config.py` (stage 0, 10 checks) asserts zero `run:true` blocks at rest, the RL
iterator shape, opening-book sizes, the full declared reference graph (including `WeightsFile`
existence), the frozen tuple (incl. regime-v2 `EpsilonLate` + the dual-block self-play mix),
ALL FOUR parent re-pins (`RL_Eval`/`RL_Eval_iter0`/`RL_SelfPlay`/`RL_Narrow`), required-file
existences, and the absence of the dave-bin `use_dsnn.txt` sentinel.

## Cross-path sanity (Step 7, historical)

`HardestAIUCT` self-play on both paths (small-sample bound, NOT a gate). Caveat: the two paths
use **different engines** — the C++ tournament path is the dave `Prismata_Testing.exe`, while
`matchup_clean.js` drives fresh per-turn processes. So this bounds the *combined* engine+path
effect, not a pure path effect.

- C++ tournament (`HardestAIUCT_1s_TMP` self-play, 16 games / 32 seat-games, 1 s, Seed 2026):
  **50.0%** seat-independent (16W / 16L / 0D — exactly symmetric, as expected for identical
  config self-play).
- `matchup_clean.js` (`HardestAIUCT` self-play, 16 games, 1 s, `--player-switch`):
  seat-independent Player A **50.0%**, Player B **43.8%** (White 56.3% / Black 37.5%, 1 draw).
- Delta: **~0–6 pp** (within sampling noise at this very small N).

The full 128-game cross-path measurement remains deferred (documented bound only).

## Remaining deferred items

| Item | Status |
|------|--------|
| Full production iteration (multi-hour self-play → train → eval) | DEFERRED to the user — all machinery + prerequisites in place (`rl_campaign.md` "Run prerequisites") |
| `human_val.py` live run (6s/12s yardstick) | not yet run live; the MasterBot baseline now exists at its permanent home |
| Throughput table (games/hour at N=1000 etc.) | measure on the first real iteration (`rl_campaign.md` Throughput) |

Previously-deferred items now RESOLVED: the STEAMAI anchor (F-08 rewire, live 2-game verified);
`action_coverage.py` runtime (exporter `ig_present`/`ig_click_count`/`ig_feasible_max` stamps,
dave `6037382`, + `js_engine/query_move.js`); `RL_Eval_iter0` weights (= v221, not a
placeholder); `run_eval.py` anchor orchestration (complete + unit-tested).
