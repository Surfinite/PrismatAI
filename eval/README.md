# RL self-play eval harness (Task 7)

Per-iteration evaluation for the RL self-play loop: win-rate math with Wilson CIs, a
group-sequential **promotion gate**, a card-set-level (clustered) CI for the paired
colour-swap design, a manifest orchestrator, and action-coverage metrics for the
IG-optional axis.

```
eval/
  wilson.py            # win_rate, wilson_ci, decisive, decisive_gate (A3), clustered_ci (A4)
  run_eval.py          # orchestrator: anchors, sequential gate, manifest
  action_coverage.py   # IG fire-rate + root-entropy metrics (RUNTIME DEFERRED, see below)
  tests/test_wilson.py # unit tests for the stats (incl. A3 stricter-gate, A4 clustered CI)
  tests/test_parse.py  # unit tests for both parsers (real HTML statsTable + A7 seat-independent)
  manifests/           # per-iteration eval_iter_<N>.json output
```

Run the tests:

```
cd c:/libraries/PrismataAI/eval && python -m pytest tests/ -v
```

## The three anchors (one path each)

| Anchor   | What                                    | Path                                  | Role |
|----------|-----------------------------------------|---------------------------------------|------|
| `iter0`  | wide-untrained iter-0 weights, IG-optional config | C++ tournament (`Prismata_Testing.exe`) | **regression-gate ref (A1)** |
| `narrow` | `DSNN_Mixed35_5var` (the deployment net)| C++ tournament                        | trajectory yardstick |
| `steam`  | STEAMAI / `PrismataAI.exe.ORIG`         | `matchup_clean.js`, `--player-switch` | trajectory yardstick (**DEFERRED live**) |

## Deployment budget, not self-play N (A1)

All eval players run at the **deployment budget** `TimeLimit:7000 / MaxTraversals:100000`,
NOT the self-play throughput N (`MaxTraversals:512`). Accordingly the `RL_Eval` player in
the dave `config.txt` was changed from `TimeLimit:0 / MaxTraversals:512` to
`TimeLimit:7000 / MaxTraversals:100000`. `RL_SelfPlay` is left at the self-play N (512)
unchanged — the eval budget is decoupled from the self-play budget.

## d_reg rule (A1)

The regression gate `d_reg` (candidate net_k vs the pre-RL net) **must** be computed from
`RL_Eval_iter0_general` — SAME config + SAME budget. Do **not** compute it from the narrow
`DSNN_Mixed35_5var` baseline: that baseline runs a different config (HardIterator_5var) at
the same budget, so a pure config/budget gap would trip `d_reg < -Y` and spuriously block a
GO. `narrow` and `steam` are **trajectory yardsticks only** — never gate on them.

## A7 — seat-independent identity parsing (NOT the seat tally)

`matchup_clean.js --player-switch` prints, at the end of a run, a seat-independent block:

```
[Parallel] --- Win Rates (seat-independent) ---
[Parallel] DaveAI(RL_Eval): 53.9%
[Parallel] SteamAI(HardestAI): 46.1%
```

`parse_matchup_seatindep()` reads the **candidate identity's** rate from this block. It
deliberately ignores the `[Parallel] White: N (X%)` / `Black:` / `Draws:` seat tally — for
a switched candidate the seat tally is NOT the candidate's win rate. (`[Pair]` is the serial
path; `[Parallel]` is the parallel path.)

## A8 — STEAMAI is a fixed-N yardstick (NOT sequential)

Only the candidate-vs-parent **promotion gate** uses sequential escalation
(`sequential_gate()`, 128→256→512). The STEAMAI yardstick uses a fixed `--steam-games` N
(default 200) plus a CI — no escalation. The `narrow` C++ yardstick is likewise a fixed-N
comparison + CI.

## A3 — group-sequential promotion gate

`decisive()` (naive "95% CI excludes 0.5", peeked at 128/256/512) has a family-wise Type-I of
~10–12%. That is tolerable for the **final asymmetric GO** signal, but a false-positive
*promotion* would poison the replay buffer. `decisive_gate()` therefore uses a Pocock-style
constant-z boundary (`Z_POCOCK_3LOOK = 2.289`, nominal alpha' ~ 0.022 per look) at the
interim looks, relaxing to full 95% alpha at the final look. Worked borderline case at the
interim look (verified): n=128, wins=76 (59.4%) → 95% iid CI lower bound 0.507 (`decisive`=True),
Pocock-z CI lower bound 0.493 (`decisive_gate(final_look=False)`=False).

## A4 — clustered (card-set-level) CI preferred for the paired pools

The paired colour-swap design has negative within-pair correlation that iid Wilson ignores,
yielding too-wide CIs (wasted games / spurious "inconclusive"). `clustered_ci(set_scores)`
takes per-card-set seat-independent scores and returns `(mean, lo, hi)` from a normal interval
on the across-set mean (SE = std/sqrt(k)). **This is the statistically-correct interval for
the paired pools** once per-set scores are parsed; the iid `wilson_ci` is the conservative
fallback.

## Parse-format note (validated Step 5, 2026-06-03)

The C++ tournament's **stdout** carries only a seat-symmetric *score matrix* (player×player
score + a `TotalScore` column) and a `Games completed:` line — it does **not** carry
per-player Wins/Loss/Draw/Games. The canonical per-player W/L/D/Games table is written to the
**HTML** results file `tests/Tournament_<name>_<date>.html` (table `id="statsTable"`, columns
Player, Score, Games, Wins, Loss, Draw, …). `run_cpp_tournament()` reads that HTML file and
`parse_tournament_stdout()` parses its statsTable rows; a stdout score-matrix fallback is kept
for diagnostics. The original plan regex (which assumed W/L/D in stdout) was corrected to this
HTML-statsTable form, validated against a real `AB_5var_Smoke` run
(`{DSNN_Mixed35_5var_F1s: w2 d0 g4, DSNN_M35_1s_c03: w2 d0 g4}`).

## Config blocks (dave `config.txt`)

Four `run:false` tournament blocks added (paired group1/group2, `Seed:2026`, `RandomCards:8`,
`Threads:8`, `rounds:64`):

- `RL_Eval_iter0_forced` / `RL_Eval_iter0_general`  — `RL_Eval` vs `RL_Eval_iter0`
- `RL_Eval_narrow_forced` / `RL_Eval_narrow_general` — `RL_Eval` vs `DSNN_Mixed35_5var`

`ForcedCards:["Hotel"]` and the `RL_Eval_iter0` player are **not yet wired** (Task 12/13);
unknown fields and run:false blocks referencing an undefined player are silently ignored by
the C++ parser — **verified**: with all four blocks present, `Prismata_Testing.exe` parsed
`config.txt` and ran the fast smoke block to completion (exit 0), no parse error / abort. The
iter0 blocks were therefore KEPT, not removed.

## Cross-path sanity (Step 7)

`HardestAIUCT` self-play on both paths (small-sample bound, NOT a gate). Caveat: the two paths
use **different engines** — the C++ tournament path is the dave `Prismata_Testing.exe`, while
`matchup_clean.js` drives the main-repo `build/Release/prismata_selfplay.exe` (fresh process per
turn). So this bounds the *combined* engine+path effect, not a pure path effect.

- C++ tournament (`HardestAIUCT_1s_TMP` self-play, 16 games / 32 seat-games, 1 s, Seed 2026):
  **50.0%** seat-independent (16W / 16L / 0D — exactly symmetric, as expected for identical
  config self-play).
- `matchup_clean.js` (`HardestAIUCT` self-play, 16 games, 1 s, `--player-switch`):
  seat-independent Player A **50.0%**, Player B **43.8%** (White 56.3% / Black 37.5%, 1 draw).
- Delta: **~0–6 pp** (Player A matches the C++ path exactly at 50.0%; the ~6 pp spread is
  within sampling noise at this very small N — single-digit absolute game counts).

The full 128-game cross-path measurement is **deferred** (documented bound only; small N here).
Note these two paths use different engines (dave `Prismata_Testing.exe` vs main-repo
`prismata_selfplay.exe`), so this bounds the combined engine+path effect, not a pure path
effect. This run also confirmed the live `matchup_clean.js` seat-independent line shape —
`[Parallel] Player A [HardestAIUCT[HardestAI]]: 50%` — which `parse_matchup_seatindep` handles.

## DEFERRED items

| Item | Blocked on | Task |
|------|-----------|------|
| STEAMAI live anchor run | `PrismataAI.exe.ORIG` not on disk | Task 14 |
| `human_val.py` live run (6s/12s yardstick) | needs `.ORIG` + A12 standalone-loads-config | Task 14 |
| `action_coverage.py` runtime | `js_engine/query_move.js` + exporter `ig_present`/`ig_click_count` stamps | Task 10 / Task 5 |
| `RL_Eval_iter0_*` block execution | wide-untrained iter-0 weights not yet generated (`RL_Eval_iter0` is defined but still points at the `neural_weights_mixed_35prop.bin` placeholder) | Task 14 |

The orchestration wiring of the live anchor runs (mapping `run_cpp_tournament` / `run_steam`
results into `manifest['anchors']`) is left as documented hooks; live runs happen in Task 14.
