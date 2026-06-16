# Self-Play & Eval Stalemate Draw Policy — Design

> **Date:** 2026-06-16 · **Status:** APPROVED (brainstorm 2026-06-16; revised same day after review —
> eval promoted to first-class scope, signal hardened to the board multiset, N-framing and
> `total_plies` semantics corrected).
> **Scope:** the dave-master tournament game loop (self-play **and** eval) + the self-play training-data
> trim. **`GameState`, feature extraction, `NeuralNet` value, and the export-parity/a6/three-way gates
> are untouched.**
> **Owner goal:** data quality + self-play/eval speed, via a cheap robust proxy (NOT a faithful port of
> the SWF stalemate ladder).

---

## 1. Problem & motivation

Phase-0 (RL iteration K=1, 2026-06-16) produced 3 of 1,032 self-play games that hit the flat
~200-turn cap and ended as genuine draws (`game_0171`, `game_0383`, `game_0818`). Calibration on the
three archived replays showed the board goes **completely static around ply 50–59** and then runs dead
to ply 200 — **~70–75 % of every one of these games (~140 plies, ≈435 records) is identical frozen
junk.** The final boards are lopsided (7-vs-1, 1-vs-8, 2-vs-6): one side has a large unit lead and
*still* cannot kill the opponent's last 1–2 non-fragile units.

dave-master (the C++ engine) has **no stagnation detection** — only the flat ~200-turn cap. A game ends
when a player is wiped (`GameState::winner()` returns the survivor); otherwise the ~200-turn cap forces
termination with both players alive → `winner() == Player_None` → draw → `outcome_p0 = 0.5`. The
faithful `js_engine/State.js` ports the SWF stalemate ladder, but the C++ engine does not.

Two costs follow, one per tournament type:
- **Self-play:** frozen tails dilute the training data (hundreds of near-duplicate 0.5-labelled states)
  and waste generation compute.
- **Eval:** the per-iteration origin+masterbot eval is the **~1.5 hr bottleneck**; a stalemate game
  running to ply 200 at the 7 s/move budget dominates the tail. Ending it at the stalemate point as a
  draw is **pure speedup** — a stalemate draw contributes to the win-rate identically to a 200-cap draw,
  so eval *results are unchanged*.

## 2. Reference: how the live client decides a draw (informative)

The SWF button is **"Claim Draw"** ([`UIBottomBarRight.as:101`](../../../prismata_decompiled/scripts/starlingUI/game/bar/UIBottomBarRight.as#L101)) — a *unilateral stalemate claim*, enabled on your turn when
`Game.gameState.colorIsStagnated(Game.colorOnTop)` (your opponent has not progressed). The engine
([`State.as`](../../../prismata_decompiled/scripts/mcds/engine/State.as#L76)) uses a **4-level per-colour no-progress counter**: `NUM_LEVELS_OF_DRAW_VARIABLES = 4`,
`CUTOFFS_FOR_DRAW = [2, 8, 20, 40]`; a colour is stagnated if **any** level's counter ≥ its cutoff. All
four counters increment every turn; a "progress" event of level `L` resets counters `0..L-1`:

| Level | Cutoff | Progress event |
|---|---|---|
| 1 | 2 | delay/build countdown ticked · charge recharged · HP healed (pay-HP) · damage dealt > healing |
| 2 | 8 | money stored |
| 3 | 20 | **card bought / unit created** · buildtime ticked · opponent lifespan ticked · combo-gas stored |
| 4 | 40 | **opponent unit killed** (`LEVEL_OPP_UNIT_COLLECTED`) |

The binding stalemate signal is level 4. Two facts we borrow: (i) **the ladder never resets on a raw
resource pool** — only on a unit *bought/created* (L3) or *killed* (L4); (ii) the counter is **per
colour-turn** — the level-4 cutoff of 40 means 40 of *one colour's* turns ≈ **80 plies**. `js_engine/State.js`
ports this exactly; dave-master does not.

## 3. Decision — Approach A: board-multiset "no-progress" counter

Detect a stalemate with a single counter in the tournament game loop: **consecutive plies with no
change to the board's `(owner, cardType)` multiset.** Each ply, compute the multiset of unit
`(owner, cardType)` over the live units (the units `numCards` counts); **reset** the counter and record
`last_progress_ply` whenever the multiset differs from the previous checkpoint, otherwise **increment**.
On reaching the threshold **N (default 40 plies)**, end the game as a draw (the existing
`winner() == Player_None → outcome_p0 = 0.5` path). For **self-play**, also trim every record after
`last_progress_ply`; for **eval**, the early end is the whole benefit (no training records to trim).

### 3.1 Why the board `(owner, cardType)` multiset
- It is exactly the **"board change" signal the calibration validated** (`last kill == last board
  change` on all three games) — we implement the signal we proved, not a coarser proxy of it.
- **Misfire-resistant** (not misfire-*proof*). In Prismata you win only by destroying enemy units, and
  a kill is always *cross-owner* (the enemy's count drops), so the multiset catches **every kill** plus
  every buy/cross-type churn. Real progress toward a win changes the multiset.
- **Card-set-independent** and robust to the known instId slot-reuse (it is a count keyed by
  `(owner, cardType)`, not an id set).

**Residual blind spot (documented, accepted).** A signature taken at ply boundaries cannot see a
*same-owner, same-type* net-zero churn within a ply — e.g. a self-sacrifice (or lifespan-expiry) of a
Drone **and** a re-buy of a Drone on the same ply leaves the multiset unchanged. Sustained for N plies
this would not reset the counter. It is narrow (same owner *and* same type *and* a non-kill removal,
every ply) and such a player is arguably not progressing anyway. **Mitigations:** (a) verify the
`numCards`/`numKilledCards` semantics on a self-sac / buy-then-expire ply and **pin them with a unit
test**; (b) optionally add `Σ numKilledCards increased` as a secondary reset (closes any same-type
*kill*-then-rebuy variant). The dangerous direction is a *false draw of a live game* (it corrupts a
value target / biases an eval cell), which is why the signature is the safer multiset and N is set high
— see §3.3.

### 3.2 Why resource accumulation is excluded (empirical)
Measured on the 3 cap-draws, **stored Green grows throughout the frozen tail** (White 112→160 in
`game_0171`; Black 174→249 in `game_0383`; Black 54→79 in `game_0818`). A "reset on resource growth"
guard would have *prevented* drawing real stalemates — a player passively piles up a pool it cannot
convert into a board change. Resource pools are also card-set-dependent (e.g. green is inert without a
green-cost unit such as Cluster Bolt). This is exactly why the SWF ladder resets on buys/kills, never on
a pool.

### 3.3 The threshold N — units, framing, and the safety/trim decoupling
- **N is in plies.** The loop fires once per ply (player-turn), so **N = 40 plies = 20 full rounds.**
  This is *not* the SWF's "40" (which is 40 colour-turns ≈ 80 plies); N=40 plies is in fact **tighter
  than the SWF window**. Frame it as "20 rounds of frozen population," which clears the observed
  turn-50–59 freeze with wide margin (fires ~ply 90–99).
- **N does not change how much data is trimmed** — the self-play trim always cuts back to
  `last_progress_ply`. N only sets how long a *suspected* stalemate runs before being called: the
  false-positive safety margin vs a few plies of wasted compute. A wrong draw corrupts a value target
  (self-play) or biases a win-rate cell (eval); wasted compute on a frozen board is ~free. So **err
  high — N = 40 is the safe default**, fully tunable. (A larger N for eval than self-play is available
  if false draws ever appear in eval, but one N=40 is conservative enough for both.)

*Accepted under-detection:* a player buying a *new* unit every ply for N plies without any other change
would not be drawn. Supply caps (legendary 1 / rare 4 / normal 10) make this implausible; the
calibration games show buys stop (ply 27–42) before the freeze.

## 4. Architecture & components

1. **C++ stalemate counter** — `source/testing/TournamentGame.cpp` game loop (`while(!_game.gameOver())`),
   active for **both self-play and eval** tournaments. Each ply, build the `(owner, cardType)` multiset
   over live units (iterating the same units `numCards` counts); reset the counter + set
   `last_progress_ply = current_ply` when it differs from the previous checkpoint, else increment. When
   the counter reaches **N**, terminate the game with a **draw** (`winner == Player_None`). The
   ~200-turn hard cap remains as a backstop. (Optional belt-and-suspenders per §3.1: also reset on
   `Σ numKilledCards` increasing.)
2. **Kept-length stamp** — the finalised game records its **kept length** as `total_plies`
   = `last_progress_ply + 1` (the trimmed/H5 length, ~50–59), **not** the played length (~90–99). The
   game-length non-degeneracy stat reads `total_plies`, so it must reflect what is actually in the H5.
3. **Export metadata stamp (self-play only)** — pass `last_progress_ply` into the V2 exporter's
   `finalize(...)` so training records carry enough to trim (a per-record `after_last_progress` flag, or
   `last_progress_ply` written per record alongside its ply index). The full replay + parity sidecars
   are **not** trimmed — they remain the per-iteration forensic / future-re-extraction record.
4. **Training-data trim (self-play only)** — the concat/vectorize step (`run_iteration.ps1` stage 2 →
   `training/vectorize_v2.py`) drops records beyond `last_progress_ply`. Because the engine already
   ended the game at `last_progress_ply + N`, only the ~N-ply confirmation window is trimmed here;
   everything past it was never generated. Kept records carry the game's `outcome_p0 = 0.5`.
5. **Eval** — needs items 1–2 only. The early end produces a normal draw that the win-rate math already
   handles; **no trim, no training records.** Pure speedup.
6. **Config / knobs** — a config flag enabling the rule + the `N` parameter, applied to the tournament
   loop (so both self-play and eval honour it). Recorded for reproducibility (a `campaign_frozen.json`
   scale-tier knob + a preflight assertion is the recommended follow-on).

## 5. Data flow

```
tournament game (C++ TournamentGame loop)            [self-play OR eval]
  → per-ply board (owner,cardType) multiset; on N consecutive no-change plies:
        end game = DRAW (winner = Player_None → outcome 0.5), record last_progress_ply
  → finalize(): total_plies = last_progress_ply + 1 (kept length)

  self-play only:
    → finalize() also stamps last_progress_ply onto the V2 records   [full replay + sidecars kept]
    → run_iteration stage 2: concat + vectorize_v2 drop records with ply > last_progress_ply
    → H5 (frozen tail removed; lead-up labelled 0.5)

  eval:
    → the draw flows into the win-rate the same as a 200-cap draw — just sooner
```

## 6. Scope / non-goals

- **In scope:** the tournament game-loop counter (self-play **and** eval) + the self-play training trim.
- **No change** to `GameState`, feature extraction, `NeuralNet` value, or the export-parity / a6 /
  three-way gates. The change lives in the tournament loop + the Python trim. After the dave-master
  rebuild, `engine_*_exe_sha256` in `campaign_frozen.json` must be **re-pinned** and a6 + three-way
  **re-run** as standard rebuild discipline (expected unchanged — no value/feature code is touched).
- **Not** a faithful SWF 4-level ladder port (rejected as too costly for the data-quality goal; the
  single board-multiset counter is a cheap, validated approximation).
- The ~200-turn hard cap **stays** as a backstop.

## 7. Testing

- **Regression calibration (fixture):** replay `game_0171` / `game_0383` / `game_0818` (archived at
  `training/data/rl_iter_1/replays/general/`) through the multiset logic (or a Python mirror) and assert
  it fires at the freeze ply (50–59) and trims ~140 plies.
- **Net-zero unit tests (the §3.1 residual):** synthetic mini-sequences pinning (i) a cross-type buy+sac
  ply → resets (multiset changes); (ii) a same-type buy + enemy kill ply → resets (cross-owner);
  (iii) a same-owner same-type buy + self-sac/expire ply → assert the *documented* behaviour (does/does
  not reset, per the verified `numKilledCards` semantics); (iv) a genuinely frozen run → trips exactly
  at N.
- **Trim test (self-play):** records with `ply > last_progress_ply` dropped; lead-up kept and labelled
  0.5; `total_plies` == kept length.
- **Post-build smoke:** a tiny self-play run (rounds ≈ 8) — games end ≤ ~200, a stalemate stamps
  `last_progress_ply`, the H5 has no post-stalemate records, `total_plies` is the kept length.
- **Eval smoke:** a tiny eval block confirms a stalemate game ends early as a draw and the win-rate is
  unchanged vs the cap behaviour (same 0.5 contribution).

## 8. Empirical evidence (calibration, 2026-06-16)

Per-ply, on the three archived cap-draw replays (kill = an owner's alive-unit count dropped; buy =
supply spent rose; board-change = the `(owner, cardName)` multiset changed):

| Game | Winner | Last kill | Last buy | Last board change | Frozen tail | Final units (W/B) |
|---|---|---|---|---|---|---|
| `game_0171` | Draw | ply 59 | ply 39 | ply 59 | **140 plies** | 7 / 1 |
| `game_0383` | Draw | ply 50 | ply 27 | ply 50 | **149 plies** | 1 / 8 |
| `game_0818` | Draw | ply 54 | ply 42 | ply 54 | **145 plies** | 2 / 6 |

`last kill == last board change` in all three (the board is genuinely static); stored Green *grows*
through every frozen tail (excluding it as a signal). The board-multiset counter at **N = 40 plies**
fires ~ply 90–99; trimming back to `last_progress_ply` (ply 50–59) removes the full ~140-ply tail.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| False draw of a live game (corrupts a self-play target / biases an eval cell) | Board-multiset signal + N = 40 plies; real progress changes the multiset |
| Same-owner same-type net-zero churn (self-sac + rebuy) evades the multiset | Documented residual; verify `numKilledCards` semantics + pin with a unit test; optional `numKilledCards` secondary reset |
| Under-detection (buying a new unit every ply for N plies) | Accepted; supply-limited; buys stop before the freeze in calibration |
| Rebuild discipline | Re-pin `engine_*_exe_sha256`; re-run a6 + three-way after the dave-master rebuild (formality — no value/feature code touched) |
| `game_length_band` [25,60] drifts once 200-tails vanish | Recalibrate the band post-landing (median ~37 unaffected; the outliers disappear) |
| Phase-1 reproducibility | Record the enabled-flag + `N` (config, and ideally `campaign_frozen.json` scale-tier + preflight) |

## 10. Open follow-ons (not blocking the first implementation)

- Record `N` + the enabled-flag in `campaign_frozen.json` (scale-tier) and assert in
  `eval/preflight_config.py` — recommended for Phase-1 reproducibility; can land with or just after the
  core.
- Recalibrate `game_length_band` after the rule lands (the 200-ply outliers vanish).
