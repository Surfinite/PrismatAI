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
  "expect": { "ig_click_count": 1 } | null,            // asserted COUNT (null = informational, no gate)
  "note": "where it came from / why it matters"
}
```

- **`known_move`** — run through the suite as a PASS/FAIL gate. PASS iff
  `count_ig_clicks(resp) == expect.ig_click_count`.
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
