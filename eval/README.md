# RL self-play eval harness

Per-iteration evaluation for the RL self-play loop (regime v4, proof-of-life): win-rate math with
**iid Wilson CIs** + **paired per-card-set CIs**, a boolean **`collapse`** abort signal
(detect-collapse — there is NO REJECT/REVIEW verdict, and nothing auto-promotes), an **incremental
atomic manifest**, **active provenance** (config pre-flight + engine-stderr load confirmation), and
IG-click coverage telemetry. The campaign contract is `eval/rl_campaign.md`; the operational
reference is `eval/rl_runbook.md`; the frozen tuple is `eval/campaign_frozen.json`.

```
eval/
  wilson.py             # win_rate + wilson_ci (iid 95%) + paired_round_ci — the COMPLETE stats surface
  run_eval.py           # orchestrator: origin + masterbot anchors, collapse, provenance, incremental manifest
  preflight_config.py   # stage 0: config integrity + frozen tuple + parent re-pin + correctness gates (hard-fails)
  campaign_frozen.json  # the frozen HP tuple (N=1000, tau=0.7, K=12, epsUniform=0, EpsilonLate=0.05, EpsilonIG=0, c=0.3, Threads:8)
  run_iteration.ps1     # one-iteration driver (stages 0-8; no stage 6)
  promote_candidate.ps1 # THE promotion mechanism (promote-unless-collapse; repoints RL_Eval + RL_SelfPlay)
  run_checkpoint.ps1    # powered origin + masterbot eval @ rounds 192 + the B8 forgetting guard
  render_dashboard.py   # per-iteration human-facing table (collapse / origin / masterbot / ig)
  action_coverage.py    # IG click-count distribution + feasible-max binning (telemetry only in v4)
  a6_orientation_check.py  # value-orientation (maxPlayer-seam sign-flip) guard; auto-run at preflight
  calib_states/         # curated states — calibration + coverage probes
  ig_battery/           # IG battery states (coverage defaults)
  tests/                # test_wilson, test_parse, test_run_eval_main, test_preflight, test_dashboard, test_ig_feasible
  manifests/            # per-iteration eval_iter_<N>.json output
```

Run the tests:

```
cd c:/libraries/PrismataAI/eval && python -m pytest tests/ -v
```

## The two anchors (v4)

Both are **same-path C++ tournaments** (the dave `Prismata_Testing.exe`), run per iteration at 96
games each, bumped to 384 games each at the checkpoint cadence:

| Anchor | What | Role |
|---|---|---|
| `origin` | candidate (`RL_Eval`) vs **`RL_Eval_origin` — PERMANENTLY v221, never repointed**, same iterator as the candidate (NoIG interior + IG-subset root) | **relative-drift** anchor ("did the lineage move from its start") **AND the COLLAPSE/abort signal** — collapse iff its general win-rate < `abort_winrate_vs_origin` (= 0.35) |
| `masterbot` | candidate vs **`MasterBot_SWF`** — the AB SWF-faithful `LiveHardestAI` (Player_StackAlphaBeta, 7000ms, narrow auto-fire iterator, Playout, SWF buy tree + LiveOpeningBook2(50)+DefaultOpeningBook(4) + Ability_Filter_Live incl. Odin) | **absolute external-strength TREND** (non-gating; trajectory, not per-iter decisions) |

`run_eval.py --anchors origin masterbot --pools general` selects them; `--abort-winrate` (default
0.35) sets the collapse threshold; `--origin-weights` names the origin opponent for provenance.
Pools map to block lists (`ANCHOR_BLOCKS`) whose results aggregate into one cell. Engine-load
provenance is PLAYER-level: the candidate's own NeuralNet load line is confirmed every anchor; the
`masterbot` opponent is AB/Playout (no NeuralNet) so only the candidate's load is checked there.

**Steam (the 2016 cross-path binary) is RETIRED** — replaced by the same-path AB `MasterBot_SWF`, so
there is no cross-path-delta caveat anymore. The dropped v3 anchors (`iter0`, `narrow`, `steam`) are
gone; the clean-attribution control `HardestAIUCT` is parked for a future "did the *net* help"
measurement.

## Collapse (replaces the old REJECT/REVIEW verdict)

There is **no verdict** in v4. `run_eval.py::compute_collapse(origin_cell, threshold)` returns a
boolean (a manifest field):

- **`collapse == True`** iff the origin anchor completed AND its general `win_rate < abort_winrate`
  (using the **point estimate** — a COARSE abort, NOT a powered gate);
- **`collapse == False`** iff it completed at/above threshold;
- **`collapse == None`** iff the origin anchor is missing/0-games (unknown — neither collapse nor
  safe; `promote_candidate.ps1` refuses to promote on a null collapse without `-Force`).

Nothing auto-promotes. `collapse` catches a degenerated candidate within one iteration; the powered
strength evidence lives at the **checkpoint** (origin + masterbot at 384 games). Promotion is
**promote-unless-collapse** (Phase 0 no-promote / Phase 1 promote unless aborted — collapse or the
4.5 val-acc tripwire), via `eval/promote_candidate.ps1` only.

## Statistics: pooled iid Wilson + paired per-card-set CI

`wilson.py`: `win_rate` + `wilson_ci` (iid 95%) + **`paired_round_ci`**: the engine emits a per-game
rounds CSV (`Tournament_<name>_<date>_rounds.csv`, round == shared-card-set id played in both seat
orders), so the eval design's intrinsic pairing is analyzable — the paired CI on per-round scores
removes the between-set variance the pooled per-game Wilson ignores (and is immune to the
within-pair correlation that makes the pooled CI slightly anti-conservative). Both are REPORTED in
every manifest cell (`ci` = pooled Wilson, `paired_ci` = paired). The collapse threshold reads the
point estimate, not a CI bound.

## Incremental manifest + active provenance

- The manifest is (re)written **atomically after every completed pool/anchor** (temp file +
  `os.replace`), carrying `"complete": false` and `anchors_completed` until the final write — a
  killed run no longer erases hours of tournament results.
- **Provenance is active, not just a stamp**: before any block flips on, `run_eval.py` asserts
  `Players.RL_Eval.WeightsFile` == the `--weights` basename (hard abort otherwise). Each NeuralNet
  anchor's engine **stderr must contain the per-player NeuralNet load line for the candidate `.bin`**
  ("AIParameters: created per-player NeuralNet from ..."); the result is stamped
  `engine_confirmed_load` and a completed-but-unconfirmed anchor **hard-fails** after being recorded
  for the post-mortem. The origin opponent's load is confirmed via `--origin-weights`
  (`engine_confirmed_parent_load`); the masterbot opponent is AB/Playout so that marker is skipped.
- Engine-side guardrails (dave `26075fa`/`d0ec633`): the engine **hard-fails at construction** on an
  unknown or raw-empty opening book, an unknown filter, and a NeuralNet weights-load failure; the
  UCT value path guards against an unloaded net. Filtered-to-empty books warn once instead of dying.

## Deployment budget, not self-play N (A1)

The eval players (`RL_Eval`, `RL_Eval_origin`) run at the **deployment budget** `TimeLimit:7000 /
MaxTraversals:100000`, NOT the self-play throughput N. `RL_SelfPlay` runs the frozen self-play tuple
(`MaxTraversals:1000`, τ=0.7, K=12, εUniform=0, **EpsilonLate=0.05**, **EpsilonIG=0** — v4,
`campaign_frozen.json`, preflight-asserted) — the eval budget is decoupled from the self-play
budget. Preflight's `eval_budget` check enforces the deployment budget on both eval players.

## Parse-format note (validated 2026-06-03)

The C++ tournament's **stdout** carries only a seat-symmetric *score matrix* (player×player score +
a `TotalScore` column) and a `Games completed:` line — it does **not** carry per-player
Wins/Loss/Draw/Games. The canonical per-player W/L/D/Games table is written to the **HTML** results
file `tests/Tournament_<name>_<date>.html` (table `id="statsTable"`). `run_cpp_tournament()` reads
that HTML file (with a staleness guard: the HTML's mtime must postdate the run) and
`parse_tournament_stdout()` parses its statsTable rows; a stdout score-matrix fallback is kept for
diagnostics. Per-seat P1/P2 W/G columns + SLOT-indexed attribution (dave `6e93480`) make same-name
self-match blocks render correctly.

## Config blocks (dave `config.txt`)

Two anchor tournament blocks (paired group1/group2, `Seed:2026`, `RandomCards:8`, `Threads:8`,
`rounds:48`, `run:false` at rest — `run_eval.py` flips one at a time and flips it back in a
`finally`; `run_checkpoint.ps1` bumps both to `rounds:192` for the powered read and restores them):

- `RL_PoL_origin` — `RL_Eval` (group 1) vs `RL_Eval_origin` (group 2, PERMANENTLY v221)
- `RL_PoL_masterbot` — `RL_Eval` (group 1) vs `MasterBot_SWF` (group 2, AB SWF-faithful)

The self-play block `RL_SelfPlay_General` (one general block, no `ForcedCards`) is the only block the
driver flips for generation; the v3 forced-Hotel block `RL_Step2_Smoke` is retained in config but
unused. `eval/preflight_config.py` (stage 0, **18 checks**) asserts zero `run:true` blocks at rest,
the RL iterator shape (incl. the NoIG interior), opening-book sizes, the full declared reference
graph (incl. `WeightsFile` existence), the frozen tuple (EpsilonLate=0.05 / EpsilonIG=0 + the
single self-play block), the **two** parent re-pins (`RL_Eval` + `RL_SelfPlay`, NOT "all four"), the
origin pin, the anchor blocks, the eval budget, required-file existences, the parent sha, the engine
sha, the a6 + three-way correctness gates, and the absence of the `use_dsnn.txt` sentinel.

## Remaining deferred items

| Item | Status |
|------|--------|
| Phase 1 promoting overnight loop | DEFERRED to the owner — Phase 0 (fixed generator) validated 2026-06-16; all machinery in place |
| Throughput table (games/hour at N=1000 etc.) | measure on a Phase-1 iteration (`rl_campaign.md` Throughput) |

Resolved during the v4 reframe: the eval orchestration (origin + masterbot, collapse, complete +
unit-tested); `MasterBot_SWF` same-path AB anchor (replaces the steam cross-path yardstick);
preflight auto-runs the a6 + three-way correctness gates and the engine-sha pin; the dashboard
renders the v4 collapse/origin/masterbot columns.
