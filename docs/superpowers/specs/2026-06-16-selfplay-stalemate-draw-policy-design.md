# Self-Play Stalemate Draw Policy — Design

> **Date:** 2026-06-16 · **Status:** APPROVED (brainstorm 2026-06-16)
> **Scope:** dave-master self-play generation + the training-data trim. **Self-play only** — eval,
> `GameState`, features, value, and the export-parity/a6/three-way gates are untouched.
> **Owner goal (chosen during brainstorm):** data quality + speed, via a cheap robust proxy (NOT a
> faithful port of the SWF stalemate ladder).

---

## 1. Problem & motivation

Phase-0 (RL iteration K=1, 2026-06-16) produced 3 of 1,032 self-play games that hit the flat
~200-turn cap and ended as genuine draws (`game_0171`, `game_0383`, `game_0818`). Calibration on the
three archived replays showed the board goes **completely static around turn 50–59** and then runs
dead to turn 200 — **~70–75 % of every one of these games (~140 turns, ≈435 records) is identical
frozen junk.** The final boards are lopsided (7-vs-1, 1-vs-8, 2-vs-6): one side has a large unit lead
and *still* cannot kill the opponent's last 1–2 non-fragile units.

dave-master (the C++ self-play engine) has **no stagnation detection** — only the flat ~200-turn cap.
A game ends when a player is wiped (`GameState::winner()` returns the survivor); otherwise the
~200-turn cap forces termination with both players alive → `winner() == Player_None` → draw →
`outcome_p0 = 0.5`. The faithful `js_engine/State.js` ports the SWF stalemate ladder, but self-play
runs in C++, which does not.

These frozen tails dilute the training data (hundreds of near-duplicate 0.5-labelled states) and waste
self-play compute (each stalemate plays ~140 dead turns). The goal is to **end frozen self-play games
at the stalemate point and trim the frozen tail from the training shard.**

## 2. Reference: how the live client decides a draw (informative)

The SWF button is **"Claim Draw"** ([`UIBottomBarRight.as:101`](../../../prismata_decompiled/scripts/starlingUI/game/bar/UIBottomBarRight.as#L101)) — a *unilateral stalemate claim*, enabled on your turn when
`Game.gameState.colorIsStagnated(Game.colorOnTop)` (your opponent has not progressed). The engine
([`State.as`](../../../prismata_decompiled/scripts/mcds/engine/State.as#L76)) uses a **4-level per-colour no-progress counter**: `NUM_LEVELS_OF_DRAW_VARIABLES = 4`,
`CUTOFFS_FOR_DRAW = [2, 8, 20, 40]`; a colour is stagnated if **any** level's counter ≥ its cutoff.
All four counters increment every turn; a "progress" event of level `L` resets counters `0..L-1`
(more significant progress resets deeper, buying a longer leash):

| Level | Cutoff | Progress event |
|---|---|---|
| 1 | 2 | delay/build countdown ticked · charge recharged · HP healed (pay-HP ability) · damage dealt > healing |
| 2 | 8 | money stored |
| 3 | 20 | **card bought / unit created** · buildtime ticked · opponent lifespan ticked · gas/charge stored on a combo unit |
| 4 | 40 | **opponent unit killed** (`LEVEL_OPP_UNIT_COLLECTED`) |

The binding stalemate signal is level 4 (no enemy kill in 40 turns). **Crucially, the ladder never
resets on a raw resource pool** — only on a *unit bought/created* (L3) or *killed* (L4).
`js_engine/State.js` ports this exactly; dave-master does not.

## 3. Decision — Approach A: unit-population-change counter

Detect a stalemate with a single counter in the self-play game loop: **consecutive player-turns with
no change to the unit population on either side.** The counter **resets** on a unit *bought/created*
**or** *killed/removed*, and **increments** otherwise. Resource pools are ignored. On reaching the
threshold **N (default 40)**, end the game as a draw (the existing `winner() == Player_None →
outcome_p0 = 0.5` path), record the **last-progress ply**, and have the training pipeline drop every
record after it.

### 3.1 Why "unit-population change"
- **Misfire-proof.** In Prismata you win only by destroying enemy units; every real path to victory
  (buying attackers, breach, lifespan expiry, combat kills) changes the unit population and resets the
  counter. If the population is unchanged for 40 turns, nobody is progressing.
- **Card-set-independent** and robust to the known instId slot-reuse (it is a count, not an id set).
- **Matches the SWF's binding events** (L3 buy / L4 kill).

### 3.2 Why resource accumulation is excluded (empirical)
Measured on the 3 cap-draws, **stored Green grows throughout the frozen tail** (White 112→160 in
`game_0171`; Black 174→249 in `game_0383`; Black 54→79 in `game_0818`). A "reset on resource growth"
guard would therefore have *prevented* drawing real stalemates — a player passively piles up a
resource it cannot convert into a board change. Resource pools are also card-set-dependent (e.g. green
is inert without a green-cost unit such as Cluster Bolt in the set). This is exactly why the SWF ladder
resets on buys/kills, never on a pool.

### 3.3 The role of N — safety decoupled from trimming
**N does not change how much data is trimmed** — the trim always cuts back to the last real population
change (`last_progress_ply`). N only sets how long a *suspected* stalemate runs before it is called:
the false-positive safety margin vs a few turns of wasted compute. Wasted compute on a frozen board is
nearly free (~16 extra turns); a wrong draw corrupts a value target. So **err high — N = 40 (the SWF's
own level-4 value) is the safe default**, fully tunable.

*Edge case (accepted):* a player buying a new unit every turn for 40 turns without ever killing would
not be drawn. Supply caps (legendary 1 / rare 4 / normal 10) make perpetual buying implausible, and
the 3 calibration games show buys stop (turn 27–42) well before the freeze. Mild under-detection,
acceptable.

## 4. Architecture & components

1. **C++ stalemate counter** — `source/testing/TournamentGame.cpp` game loop (`while(!_game.gameOver())`).
   After each applied move, derive a cheap **population signature** from the existing accessors
   `numCards(p)` / `numKilledCards(p)` (the same ones `winner()` uses): the per-side 4-tuple
   `(numCards(P0), numCards(P1), numKilledCards(P0), numKilledCards(P1))`. **Reset** the counter and set
   `last_progress_ply = current_ply` whenever the signature changes vs the previous checkpoint —
   this catches a unit *entering* play (a buy/creation raises `numCards`) **and** a unit *leaving* play
   by any route (a kill raises `numKilledCards`; a sacrifice or lifespan-expiry lowers `numCards`).
   Otherwise **increment**. When the counter reaches **N**, terminate the game with a **draw** result
   (`winner == Player_None`). The ~200-turn hard cap remains as a backstop.
2. **Export metadata stamp** — pass `last_progress_ply` into the V2 exporter's `finalize(...)` so the
   training records carry enough to trim (e.g. a per-record `after_last_progress` flag, or the game's
   `last_progress_ply` written alongside each record's ply index). The full replay and parity sidecars
   are **not** trimmed — they remain the per-iteration forensic / future-re-extraction record.
3. **Training-data trim** — the concat/vectorize step (`run_iteration.ps1` stage 2 →
   `training/vectorize_v2.py`) drops records beyond `last_progress_ply` before vectorizing. Because the
   engine already ended the game at `last_progress_ply + N`, only the N-turn confirmation window
   (≈40 records/stalemate-game) needs trimming here; everything past `last_progress_ply + N` was never
   generated. Kept lead-up records carry the game's `outcome_p0 = 0.5`.
4. **Config / knobs** — a config flag enabling the rule on the self-play block(s), plus the `N`
   parameter. Recorded for reproducibility (a `campaign_frozen.json` scale-tier knob + a preflight
   assertion is the suggested follow-on, so Phase-1 data stays reproducible). **Eval blocks do not
   enable it.**

## 5. Data flow

```
self-play game (C++ TournamentGame loop)
  → per-ply V2 capture
  → [population counter; on N consecutive no-change turns: end game = DRAW, record last_progress_ply]
  → finalize() stamps last_progress_ply (winner = Player_None → outcome_p0 = 0.5)
  → JSONL shard (records flagged/keyed by ply)            [full replay + sidecars kept untrimmed]
  → run_iteration stage 2: concat + vectorize_v2 drops records with ply > last_progress_ply
  → H5 (frozen tail removed; lead-up labelled 0.5)
```

## 6. Scope / non-goals

- **Self-play generation only.** Eval (origin / masterbot anchors) keeps the existing cap; its draws
  are already correctly 0.5, just slower — out of scope.
- **No change** to `GameState`, feature extraction, `NeuralNet` value, or the export-parity / a6 /
  three-way gates. The change lives in the tournament game loop + the Python trim. After the
  dave-master rebuild, `engine_*_exe_sha256` in `campaign_frozen.json` must be **re-pinned** and a6 +
  three-way **re-run** as the standard rebuild discipline (expected unchanged — no value/feature code
  is touched).
- **Not** a faithful SWF 4-level ladder port (considered and rejected as too costly for the
  data-quality goal; the single population-change counter is a cheap, robust approximation).
- The ~200-turn hard cap **stays** as a backstop.

## 7. Testing

- **Regression calibration (fixture):** replay `game_0171` / `game_0383` / `game_0818` (archived at
  `training/data/rl_iter_1/replays/general/`) through the population-change logic (or a Python mirror)
  and assert it fires at the population-freeze ply (turn 50–59) and trims ~140 turns.
- **Unit tests (C++ or a Python mirror):** the population-change signal + counter reset/increment + the
  N trigger, on synthetic mini-sequences (a buy resets; a kill resets; a frozen run trips exactly at N).
- **Unit test the trim:** records with `ply > last_progress_ply` are dropped; the lead-up is kept and
  labelled 0.5.
- **Post-build smoke:** a tiny self-play run (rounds ≈ 8) confirms games end ≤ ~200, a stalemate game
  stamps `last_progress_ply`, and the resulting H5 contains no post-stalemate records.

## 8. Empirical evidence (calibration, 2026-06-16)

Per-turn, on the three archived cap-draw replays (kill = an owner's alive-unit count dropped; buy =
supply spent rose; board-change = the `(owner, cardName)` multiset changed):

| Game | Winner | Last kill | Last buy | Last board change | Frozen tail | Final units (W/B) |
|---|---|---|---|---|---|---|
| `game_0171` | Draw | turn 59 | turn 39 | turn 59 | **140 turns** | 7 / 1 |
| `game_0383` | Draw | turn 50 | turn 27 | turn 50 | **149 turns** | 1 / 8 |
| `game_0818` | Draw | turn 54 | turn 42 | turn 54 | **145 turns** | 2 / 6 |

`last kill == last board change` in all three (the board is genuinely static, not "churning economy");
stored Green *grows* through every frozen tail (excluding it as a progress signal). A no-kill (≡
no-population-change here) counter at **N = 40** fires at turn 90–99 and trims ~100–110 dead turns;
trimming back to `last_progress_ply` removes the full ~140-turn frozen tail.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| False draw (declaring a non-frozen game) | N = 40 + population-change is misfire-proof (real progress changes the population) |
| Under-detection (buying-but-not-killing ≥ N turns) | Accepted; supply-limited and rare; calibration shows buys stop before the freeze |
| Rebuild discipline | Re-pin `engine_*_exe_sha256`; re-run a6 + three-way after the dave-master rebuild (formality — no value/feature code touched) |
| Phase-1 reproducibility | Record the enabled-flag + `N` (config, and ideally `campaign_frozen.json` scale-tier + preflight) |
| Trim vs forensics | Trim only the V2 training shard; keep the full replay + parity sidecars for re-extraction |

## 10. Open follow-ons (not in scope of the first implementation)

- Whether to record `N` + the enabled-flag in `campaign_frozen.json` (scale-tier) and assert it in
  `eval/preflight_config.py` — recommended for Phase-1 reproducibility, can land with or after the core.
- Whether to also apply the rule to eval tournaments (would speed eval; changes nothing about the 0.5
  labels). Deferred — eval is out of scope here.
