# Tactical cases (O7 regression suite) — Infusion-Grid CLICK COUNT

Curated tactical positions consumed by `eval/tactical_suite.py`. Each `*.json` file is one
case. The suite replays the case through dave's `PrismataAI.exe` responder (UCT + NeuralNet,
the real deploy path) via `js_engine/query_move.js` and asserts a tactical property of the
returned move — the **COUNT of Infusion Grid self-sac `USE_ABILITY` clicks**.

## Why a count (not a binary fire/skip)

Infusion Grid self-sacs a 4HP unit → four 1HP Husks, paying 1 red, for defensive granularity.
The real decision is not fire-vs-skip but **how many** IGs to self-sac (usually 1 is correct,
not all). The deployed greedy root iterator `HardIterator_5var_Root` over-clicks (fires every
legal IG). The widened `HardIterator_5var_IGsubset_Root` (a `MoveIterator_AbilitySubset`) emits
one root child per IG-click count `{0..N}`, so the net can choose the count. **The count metric
is therefore only meaningful under the widened iterator** — which is why the suite CLI defaults
to `--root-iterator HardIterator_5var_IGsubset_Root` / `--move-iterator HardIterator_5var`.

## Case format

```jsonc
{
  "name": "human_readable_id",
  "bucket": "known_move" | "looks_forced",
  "request": { "mergedDeck": [...], "gameState": {...}, "aiParameters": {...} }, // F6 CurrentInfo
  "root_iterator": "HardIterator_5var_IGsubset_Root",  // optional per-case override (else CLI default)
  "move_iterator": "HardIterator_5var",                // optional per-case override (else CLI default)
  "expect": { "ig_click_count": 1,                     // asserted COUNT (null expect = informational, no gate)
              "ig_feasible_max": 2 } | null,           // OPTIONAL curated denominator override (reporting only)
  "note": "where it came from / why it matters"
}
```

- **`known_move`** — run through the suite as a PASS/FAIL gate. PASS iff
  `count_ig_clicks(resp) == expect.ig_click_count`.
- **`expect.ig_feasible_max`** — optional, never gates. The suite reports each case as
  `count k of feasible m` where `m = min(ready IGs, attainable red)` (mirrors the engine's
  `ig_feasible_max` stamp, dave@6037382). If absent, `m` is computed from the case's
  `request.gameState` + `mergedDeck` — but ONLY for action-phase states; a pre-swoosh
  defense-phase dump would undercount (red zeroed, assigned producers unreset), so such cases
  report `?` unless this override is curated.
- **`looks_forced`** — NOT a gate (`expect: null`). Appended to `eval/backlog_action_space.md` as
  an informational watch-list of positions with no known-correct IG-click count yet.
- **`root_iterator` / `move_iterator`** — optional per-case overrides; fall back to the CLI
  `--root-iterator` / `--move-iterator` (which themselves default to the widened IGsubset pair).
  The IG-click count is only net-selectable under the widened root, so keep these on the IGsubset
  iterator for any case whose `expect` is a count < fire-all.

## What the metric counts

`count_ig_clicks(resp)` (in `eval/tactical_suite.py`, shared with `eval/action_coverage.py`)
counts Infusion-Grid **ability-use** clicks in `resp["aiclicks"]`:

```jsonc
{ "type": "inst clicked" | "inst shift clicked",
  "args": { "cardName": "Infusion Grid", "health": 4, ... } }   // ability-use; args is a DICT — COUNTED
```

It deliberately does **not** count IG **buys**, which are a different click whose `args` is a
**string**:

```jsonc
{ "type": "card clicked" | "card shift clicked", "args": "Infusion Grid" }   // buy — NOT counted
```

**Name note (verified Jun 4 2026):** the engine source (`Card.cpp:933`) emits the engine
**codename** `"Hotel"` for internal-name decks, but a live **F6 dump carries display names**
which the responder echoes back, so the ability click on the real ktink case reports
`args.cardName == "Infusion Grid"`. The counter matches **either** name (`IG_NAMES =
("Infusion Grid", "Hotel")`).

**Shift-batching caveat:** a single `"inst shift clicked"` could in principle batch several
identical IG self-sacs into one click object (the response carries no per-click multiplicity),
which the counter would under-count as 1. Curated cases are chosen so this is unambiguous —
`ktink_t9_ig` fires exactly one `"inst clicked"` IG ability-use (count 1, verified).

## Curated cases

### Armed gates (N-5 fix, Jun 11 2026)

Four cases curated from the **human-vs-net IG agreement set at c=0.3** (`eval/_ig_human_vs_net.json`,
rebuilt 2026-06-11 via `eval/ig_net_clicks.py` at the suite's own 3 s budget; human side
`eval/_ig_human.json`, replay-aligned F6-format states in `eval/ig_battery/`). All PASS at the
frozen budget — stable across every same-day sample — and are recorded `passed:true` in
`eval/tactical_baseline.json`, so the suite's regression gate has teeth in **both** directions:
the 1-click case catches **under-click** regressions, the 0-click cases catch **over-click**
regressions (the original bug class). All four are action-phase states with `ig_feasible_max >= 1`
(IG was genuinely fireable — ready IG + attainable red), so the 0-click expectations are non-vacuous.

- **`skkf1_t19_ig_1click`** — SkkF1-AC7gP, P0 turn-19; human fired 1 IG (feasible 2). Under-click
  sentinel. 10/10 same-budget samples correct (Jun 11).
- **`eobd_t15_ig_0click`** — @Eobd-nYKU2, P0 turn-15; human fired 0 IGs (feasible 1). Over-click sentinel.
- **`fxa1f_t16_ig_0click`** — FXa1F-jAdjL, P1 turn-16; human fired 0 IGs (feasible 2). Over-click sentinel.
- **`lreyq_t20_ig_0click`** — LReyq-o2cc5, P1 turn-20; human fired 0 IGs (feasible 1). Over-click sentinel.

Two further click-positive agreement candidates were curated and then **dropped as flaky** at the
3 s wall budget (Jun 11; "do not curate a flaky case" — an armed flaky case false-fires the
regression gate):

- **UIgf7-B9oYN P0 turn-27** (human=net=1): 2 count-0 flips in 11 samples (~18%), one of which
  fired a spurious REGRESSION on a clean tree during verification.
- **UIgf7-B9oYN P1 turn-28** (human=net=1): 3 count-0 flips in 9 samples (root children 9 vs 10
  essentially tied) — would false-fail ~1 run in 3.

The c=0.3 agreement set contained exactly 3 click-positive agreements (the two above + skkf1), so
no replacement under-click case exists until the net improves on these states. The 0-click cases
are intrinsically noise-robust: most root children contain zero IG clicks, so argmax jitter rarely
changes the count (observed argmax 12 vs 2 on `lreyq_t20`, count 0 both times; all three zeros went
10/10 on Jun 11).

### Standing reference (un-armed)

- **`ktink_t9_ig`** — the canonical gating case. Sourced from replay **KtInk-pMiQf**, P1 (Master
  Bot = the DSNN AI) **turn-9**, captured as an F6 `CurrentInfo` dump
  (`docs/scratch/ktink_t9_action_request.json`, embedded inline as the case `request`). A real
  over-click position: greedy `HardIterator_5var_Root` argmax fires **2** IGs (the bug); the
  widened `HardIterator_5var_IGsubset_Root` argmax fires **1** (correct — one IG self-sac is
  enough defensive granularity vs the freeze). `expect.ig_click_count = 1`.

  **c-dependence note (Jun 10 2026, M-06 re-baseline):** the original "fires 1" observation
  (and the Jun-4..9 baseline) was measured at the engine-default **c=2.0** because
  `query_move.js` did not inject `UCTConstant` (audit finding M-06). At the project-tuned
  **c=0.3** (now the `query_move.js` default), on the same SWF-faithful config, the search
  commits to the value net's actual preference and fires **0** IGs (argmax/chosen child 6,
  vs child 2 at c=2.0) — i.e. the c=2.0 "pass" was exploration smoothing masking a net
  evaluation weakness on this state; the net underrates the 1-IG defensive line. The case
  stays `expect.ig_click_count = 1` (human ground truth); the committed
  `eval/tactical_baseline.json` records the FAIL at c=0.3 as the standing reference (a
  known-issue for RL to fix, not a regression — the suite only gates on previously-passing
  cases). Verified same-budget A/B at 3 s: c=2.0 → count 1, visits `[191,191,455,211,211,303,305,253]`;
  c=0.3 → count 0, visits `[208,208,311,190,190,406,438,299]`.
  **Budget-dependence caveat:** the FAIL above is at the suite's 3 s budget (~2,250 traversals).
  At **N=256 fixed traversals** (the self-play-scale budget), c=0.3 picks child 2 → count **1**
  (visits `[16,16,76,36,36,22,37,17]`) — i.e. this case would PASS at N=256. The "net underrates
  the 1-IG line" reading is therefore budget-specific: deeper search at c=0.3 talks itself OUT of
  the correct click. Expect contradictory-looking results across budgets on this state.
  **Same-budget instability (Jun 11 2026, N-5 re-baseline):** the state is a knife edge even at a
  fixed 3 s / c=0.3 — same-day samples flipped between child 5 (count **1**, a PASS; 11 of 14 runs)
  and child 6 (count 0, the recorded FAIL; 3 of 14). The committed baseline deliberately keeps the
  **`passed:false` standing reference** (un-armed): with `passed:true` this case would spuriously
  fire the regression gate ~1 run in 5, and with the recorded FAIL it gates nothing in either
  direction — it remains a known-issue reference for RL to fix, tracked by expect = 1 (human
  ground truth).

> The earlier `standin_*` placeholder (built from VXGaI, one of 4 old F6 dumps that are
> unparseable/degenerate) has been removed; `ktink_t9_ig` is the canonical case.

## Capture workflow

1. Play (or replay) a real DSNN game to the Infusion-Grid decision you care about.
2. In the client (dev-mode SWF patch), press **F6** to copy the game-state JSON to the clipboard.
3. The payload is the `"CurrentInfo"` section (`{mergedDeck, gameState, aiParameters}`); the F6
   dump also carries other sections — `query_move.js` / `tactical_suite.py` brace-match
   `CurrentInfo` out automatically, so keep just that object as the case `request` (embedded inline).
4. Set `bucket`, `root_iterator`/`move_iterator` (IGsubset for a count gate), the correct
   `expect.ig_click_count`, and a descriptive `note`.

## Running

```bash
python eval/tactical_suite.py \
  --player RL_Eval \
  --weights neural_weights_mixed_v221.bin \
  --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe
# first run with no eval/tactical_baseline.json -> writes the baseline (exit 0)
python eval/tactical_suite.py --write-baseline   # re-persist current results as the regression baseline
```

The suite exits nonzero **only** when a case that matched its expected count in
`eval/tactical_baseline.json` now differs (a true regression). New cases never gate.
