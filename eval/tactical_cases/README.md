# Tactical cases (O7 regression suite)

Curated tactical positions consumed by `eval/tactical_suite.py`. Each `*.json` file is one
case. The suite replays the case through dave's `PrismataAI.exe` responder (UCT + NeuralNet,
the real deploy path) via `js_engine/query_move.js` and asserts a tactical property of the
returned move — currently **whether the Infusion Grid (engine codename `Hotel`) `USE_ABILITY`
click fires**.

## Case format

```jsonc
{
  "name": "human_readable_id",
  "bucket": "known_move" | "looks_forced",
  "request": { "mergedDeck": [...], "gameState": {...}, "aiParameters": {...} }, // F6 CurrentInfo
  "expect": { "fires_hotel": true | false } | null,  // the asserted property (null = no gate)
  "hotel_inst_id": 1234 | null,   // forward-compat; see note below
  "note": "where it came from / why it matters"
}
```

- **`known_move`** — run through the suite as a PASS/FAIL gate against `expect.fires_hotel`.
- **`looks_forced`** — NOT a gate. Appended to `eval/backlog_action_space.md` as a watch-list of
  positions where the iterator may be pinning the move. These only become *meaningful for
  Infusion-Grid optionality once **Task 12** wires the IG-optional iterator* (before that, the
  deployed iterator always fires IG when legal, so an "IG-skip" expectation is unreachable).

## Capture workflow

1. Play (or replay) a real DSNN game to the decision you care about — e.g. an Infusion Grid
   turn where firing vs holding the ability is a genuine choice.
2. In the client (dev-mode SWF patch), press **F6** to copy the game-state JSON to the clipboard.
3. Paste the clipboard. The payload is the `"CurrentInfo"` section (`{mergedDeck, gameState,
   aiParameters}`); the F6 dump also carries other sections (`TurnStartInfo`, an AI Status Log
   tail) — `query_move.js` / `tactical_suite.py` brace-match `CurrentInfo` out automatically, so
   you can keep just that object as the case `request`, or paste the raw dump and extract it with
   `node js_engine/query_move.js` plumbing.
4. Set `bucket`, `expect.fires_hotel` (the move you believe is correct), and a descriptive `note`.

## Running

```bash
python eval/tactical_suite.py \
  --player RL_Eval \
  --weights neural_weights_mixed_35prop.bin \
  --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe
# first run with no eval/tactical_baseline.json -> establishes the baseline (exit 0)
python eval/tactical_suite.py --write-baseline   # persist current results as the regression baseline
```

The suite exits nonzero **only** when a case that passed in `eval/tactical_baseline.json` now
fails (a true regression). New cases never gate.

## Status / what's real vs deferred

- **REAL curated cases are DEFERRED to the user** — they come from your own DSNN games (capture
  workflow above). Do not fabricate them.
- **IG-SKIP cases need Task 12** — until the IG-optional iterator is wired, the deployed iterator
  always fires the Infusion Grid when legal, so a `fires_hotel:false` expectation on an
  IG-available state is not reachable by the current engine. Those cases only become meaningful
  after Task 12.
- **Hotel click shape NEEDS CONFIRMATION on a real IG state.** The responder emits `USE_ABILITY`
  clicks as `{"type":"inst clicked"|"inst shift clicked", "args":{"cardName":"Hotel", ...}}`
  (internal name, no per-click instance id). `fires_hotel()` matches on `args.cardName == "Hotel"`;
  `hotel_inst_id` is retained for forward-compat but unused. Confirm the exact shape against a real
  Infusion-Grid decision and adjust `tactical_suite.py` if it differs.
- The current cases directory ships a **clearly-marked STAND-IN** (`standin_*`) that only exercises
  the harness mechanism (query → classify → PASS) — it is **not** a curated tactical case.
