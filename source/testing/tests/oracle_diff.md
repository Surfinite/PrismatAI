# Replay serializer — verification log (Task 19)

This is the fidelity-verification record for the native C++ replay serializer
(`source/testing/ReplaySerializer.{h,cpp}`), which emits the matchup-format
`game_NNNN.json.gz` files the PixiJS `/replay/local` viewer consumes.

## Why there is no automated "oracle diff"

The original plan (Task 19) called for a field-by-field diff of the C++ output
against `matchup_clean.js --save-replays`. We deliberately did **not** do this:

1. **`matchup_clean.js` is an unverified producer.** Its `--suggest`
   click-emission path has documented click failures, so it is not a trusted
   oracle. A diff between two unvalidated producers proves nothing: a clean
   diff wouldn't establish correctness, and a dirty diff wouldn't localize the
   fault.
2. **The only trusted reference — S3 live replays — exercises a different
   path.** In the viewer, S3 replays load via `processS3Replay`
   (clicklist → real-engine reconstruction); they never touch the pre-baked
   `states[]` the C++ serializer emits. So an S3 comparison validates nothing
   about this code.

Instead we verified the output against **pipeline-independent ground truth**:
known card mechanics + structural invariants, plus an adversarial multi-agent
code review. All checks run on engine-pristine, deterministic output.

## Verification performed

### Structural fidelity (per-instance `table[]`)
- **`blocking` = `Card::canBlock()`** — the exact expression Dave's own
  `Card::toJSONString()` uses. Fixed an always-false bug (`status==Assigned &&
  canBlock()`); now ~20% of alive units block, distribution sane by phase.
- **`lifespan`** uses the `0 → -1` (infinite) convention.
- **`role`** maps sellable / assigned / inert / default from `isSellable()` +
  `getStatus()`.
- **`instId` — synthetic monotonic remap.** Dave's engine recycles `CardID`
  slots when units die (~39% of ids in a game refer to >1 unit). The viewer
  assumes unique, creation-monotonic ids (JS `nextInstId++`) for the pile
  newest-sorts-left tiebreak and for cross-frame sprite pairing. The serializer
  remaps each distinct unit to a stable, ever-increasing id. **Verified across
  80 games / 2.25M instances: 0 reuse, fully monotonic, freshly-placed unit is
  always the newest id in its pile.**
- **Freshness flags.** `boughtThisPhase = isSellable()` (faithful to the SWF
  `role===SELLABLE` gate). `bornThisTurn` = a non-sellable unit tagged at first
  appearance with its owner's turn index, expiring at the owner's next turn —
  covering both ability spawns (Sentinel→Engineer, Valkyrion→Sound Barrier) and
  begin-turn spawns (Gauss Fabricator→Minicannon, Defense Grid→Drone). Verified:
  0 born-while-sellable, 0 never-expire; a port of the viewer's `pile-sort.ts`
  bunches every freshly-placed unit leftmost.

### Derived HUD fields (Task 17) — mechanic checks
- **Gold-estimate bounds**: lower ≤ upper and ≥ current gold — 0 violations /
  13,414 player-states.
- **Drone floor**: estimate ≥ in-window Drone count — 0 violations.
- **Per-unit gold coverage**: all 116 units scanned; every gold producer
  (Thorium Dynamo, Centrifuge, Blood Phage, all drone variants, …) is counted
  with the correct amount, reading `Resources::amountOf(Gold)`.
- **Resonate**: Savior gold-resonate and the three attack-resonate units
  (Resophore, Amporilla, Antima Comet) are handled by one generic
  `resonateBonus` path (runtime-confirmed on real boards).

### Adversarial code review
A 3-lens multi-agent review (correctness · cross-reference integrity · SWF
faithfulness) with adversarial verification of each finding. It caught a real
bug — `bornThisTurn` never firing for begin-turn-create spawns, because the
engine omits begin-turn creates from `getCreatedCardIDs()`
(`GameState.cpp:1043`) — which was then fixed (owner-turn tagging). It also
confirmed no surviving raw-`CardID` cross-reference: `table[]` synthetic ids are
internally consistent, and `actions[]` labels keep raw ids but no consumer
correlates them back to instances.

## Known limitations (honest)
- **Begin-turn spawns not observed end-to-end.** The 4 begin-turn creators
  appear in the buy pool but the AI doesn't build them in random games (0/80
  on-table), so a begin-turn spawn was never produced for a live screenshot.
  Covered by construction: the `bornThisTurn` code path is identical for ability
  and begin-turn spawns, and ability spawns are verified.
- **`actions[]` labels are raw `Action::toHistoryString()`** ("player type id
  targetId", raw recycled CardIDs) — cosmetic; richer labels ("Buy Drone") and
  any id-correlation are deferred.

## Conclusion
Task 19's intent — establishing serializer fidelity — is met via mechanic-based
verification plus adversarial review. No automated `matchup_clean.js` diff was
run, by design: it would be misleading rather than informative.

## Addendum — 2026-06-12 replay-audit fixes (audit doc:
## `PrismataAI/docs/superpowers/plans/2026-06-10-replay-export-audit-FINDINGS.md`)

A full audit (4 investigators + empirical runs) verified the capture mechanism
**exact** (re-applied states == V2 exporter turn-start records, 34/34 + 96/96
plies; all phase transitions incl. `beginTurn` run inside `doAction`; action
resolution RNG-free) and landed these serializer/harness fixes:

- **Trailing `turnBoundaries` sentinel dropped at finalize** (V1/RC-1): the old
  `== states.Size()` entry crashed `nextTurn()` in all three viewers; now
  `turnBoundaries.length == turns`, matching the JS writer.
- **HUD charge gate fixed** (F3): `abilityUsable` now gates on CURRENT charges
  (the old `startingCharge < chargeUsed` form was unsatisfiable dead code, and
  its "beginTurn refreshes charges" justification was false — charges are spent
  permanently). Depleted Rhino/Tia/Sentinel/Bombarder no longer inflate
  maxAttack/oppAttackPotential.
- **Sniper `*` gated on potentiallyMoreAttack** (F6): only Apollo counts
  (Kinetic Driver lacks pMA in the SWF card data; Deadeye is `abilityNetherfy`,
  not a targetAction unit — outside this loop on both sides).
- **Provenance meta** (RC-3): top-level `formatVersion:1`, `gameIndex`,
  `savedAtUtc`, and a `meta` object (tournament/seed/threads) — additive;
  viewers ignore unknown keys.
- **Shared per-game artifact id** (O1): one counter feeds both
  `game_NNNN.json.gz` and `selfplay_NNNN.jsonl`, so the indices pair to the
  same game even at Threads>1.
- **Failure paths loud** (R7/R11): `finalize()` failure now logs; after each
  move re-application the clone is fingerprint-compared against the live state
  (turn/player/phase/card-counts/resources) and a diverged replay is dropped
  loudly instead of written corrupt.
- **Parity sidecars gzipped** (`sp_*.json.gz`, shared `GzipUtil.h`) into
  **per-export-dir** `<exportTrainingV2>_parity` dirs (a shared sibling dir let
  two same-launch tournaments overwrite each other's `sp_0000_*` — adversarial
  review catch), and **archived per iteration** (slice-prefixed) with the
  replays by `run_iteration.ps1` stage 1.5.

Known limitations carried forward (documented in the audit doc): `numTurns`
keeps the ENGINE convention (= JS `numTurns` − 1) **deliberately** — changing
it would break `GameState::initFromJSON` re-extraction; consumers must use the
explicit `turn` field, never `numTurns` parity. `deadness` stays coarse
alive/dead; `actions[]` keep raw recycled CardIDs.
