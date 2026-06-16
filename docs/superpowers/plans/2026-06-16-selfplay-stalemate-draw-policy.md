# Self-Play & Eval Stalemate Draw Policy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End frozen self-play and eval games early as draws (a "no-progress" stalemate rule) and trim the frozen tail out of the self-play training shard, for cleaner training data and faster self-play/eval.

**Architecture:** A pure C++ `StalemateTracker` (header-only) drives a per-ply "board `(owner, cardType)` multiset unchanged for N plies" counter inside the shared `TournamentGame` loop (so both self-play and eval honour it). On firing it breaks the loop with both players alive → the existing `winner()==Player_None` path makes it a draw (`outcome_p0 = 0.5`). For self-play only, `SelfPlayV2Exporter::finalize` trims records past the last population change and stamps `total_plies` = the kept length. The threshold `N` is a per-tournament config knob (`StalemateThreshold`, plies). A Python oracle (`eval/stalemate.py`) is the executable spec + the 3-game calibration regression that the C++ must match.

**Tech Stack:** C++ (dave-master engine, MSBuild VS18/x64, no CMake edits — header-only + an existing `main.cpp` test-probe pattern), Python 3 (pytest; the oracle + the preflight assertion), JSON config (`config.txt`, strict no-BOM).

**Spec:** `docs/superpowers/specs/2026-06-16-selfplay-stalemate-draw-policy-design.md`.

**Repos:**
- dave-master engine: `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`). Push to `PrismatAlpha`.
- main repo (training/eval/docs): `c:/libraries/PrismataAI` (branch `feature/production-vectors`).

**Working rules:** dave-master config edits keep `config.txt` strict-JSON, **no BOM** (surgical edits only). The C++ rebuild is heavy — batch it into Task 7 (don't rebuild per C++ task); **stop any running engine first** (LNK1104 if the exe is in use) and **use `//t:Rebuild`** (incremental may not relink). Commit after every task.

---

## File structure (what each unit owns)

| File | Repo | Responsibility |
|---|---|---|
| `eval/stalemate.py` (new) | main | Pure oracle: `StalemateTracker` + multiset/replay helpers — the executable spec + calibration tool |
| `eval/tests/test_stalemate.py` (new) | main | Synthetic net-zero tests + the 3-game calibration regression |
| `source/testing/StalemateTracker.h` (new) | dave | Pure, header-only counter struct (no engine deps) — mirrors the oracle |
| `source/standalone/main.cpp` (modify) | dave | `--test-stalemate` PASS/FAIL probe (unit-tests the struct in C++) |
| `source/testing/TournamentGame.h/.cpp` (modify) | dave | Per-ply multiset build + tracker + early-break + `last_progress_ply` + the setter |
| `source/testing/SelfPlayV2Exporter.h/.cpp` (modify) | dave | `finalize` gains `lastProgressPly`: trim records + stamp kept-length `total_plies` |
| `source/testing/Tournament.h/.cpp` (modify) | dave | Read `StalemateThreshold` from config; plumb to each `TournamentGame` |
| `bin/asset/config/config.txt` (modify) | dave | `"StalemateThreshold": 40` on `RL_SelfPlay_General`, `RL_PoL_origin`, `RL_PoL_masterbot` |
| `eval/campaign_frozen.json` (modify) | main | Record `N` (scale-tier) + re-pin `engine_*_exe_sha256` after rebuild |
| `eval/preflight_config.py` + `eval/tests/test_preflight.py` (modify) | main | Assert the RL blocks carry the frozen `StalemateThreshold` |

---

## Task 1: Python stalemate oracle + calibration regression (the executable spec)

This is the TDD centerpiece: it defines the exact algorithm the C++ must mirror and pins it against the 3 known cap-draw games. No C++ build involved.

**Files:**
- Create: `c:/libraries/PrismataAI/eval/stalemate.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_stalemate.py`

- [ ] **Step 1: Write the failing test.** Create `eval/tests/test_stalemate.py`:

```python
"""Tests for eval/stalemate.py — the stalemate-detection oracle + the 3-game calibration."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stalemate import StalemateTracker, scan_replay, load_replay  # noqa: E402

REPLAY_DIR = r"C:/libraries/PrismataAI/training/data/rl_iter_1/replays/general"
# (last_progress_ply, fire_ply) at threshold=40, measured during the brainstorm calibration.
GAMES = {"game_0171": (59, 99), "game_0383": (50, 90), "game_0818": (54, 94)}


def test_frozen_run_fires_at_threshold():
    tr = StalemateTracker(threshold=3)
    a = {(0, "Drone"): 1}
    fired = [tr.observe(a, p) for p in range(5)]
    assert fired == [False, False, False, True, True]   # ply0 baseline, 3 unchanged -> fire ply3
    assert tr.last_progress_ply == 0


def test_change_resets_counter():
    tr = StalemateTracker(threshold=2)
    seq = [{(0, "Drone"): 1}, {(0, "Drone"): 1}, {(0, "Drone"): 2},
           {(0, "Drone"): 2}, {(0, "Drone"): 2}]
    fired = [tr.observe(s, p) for p, s in enumerate(seq)]
    assert fired == [False, False, False, False, True]   # change at ply2 -> fire ply4
    assert tr.last_progress_ply == 2


def test_cross_type_buy_sac_resets():
    # buy Engineer + sac Drone on one ply -> multiset changes -> counter resets (not frozen)
    tr = StalemateTracker(threshold=2)
    a = {(0, "Drone"): 5}
    b = {(0, "Drone"): 4, (0, "Engineer"): 1}
    assert [tr.observe(s, p) for p, s in enumerate([a, a, b])] == [False, False, False]
    assert tr.last_progress_ply == 2


def test_same_type_netzero_is_documented_blind_spot():
    # same-owner same-type buy+sac net-zero leaves the multiset unchanged -> treated as frozen.
    # This is the accepted residual (spec 3.1); the test pins the behaviour.
    tr = StalemateTracker(threshold=2)
    a = {(0, "Drone"): 5}
    assert [tr.observe(a, p) for p in range(3)] == [False, False, True]


@pytest.mark.parametrize("name,expected", GAMES.items())
def test_calibration_regression(name, expected):
    path = os.path.join(REPLAY_DIR, name + ".json.gz")
    if not os.path.exists(path):
        pytest.skip("calibration replay not present: " + path)
    assert scan_replay(load_replay(path), threshold=40) == expected
```

- [ ] **Step 2: Run it — expect FAIL** (`stalemate` module does not exist).

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_stalemate.py -q`
Expected: FAIL (ImportError / ModuleNotFoundError: stalemate).

- [ ] **Step 3: Implement `eval/stalemate.py`:**

```python
"""Stalemate (no-progress) detection oracle for the self-play/eval draw policy.

Mirrors the C++ StalemateTracker (PrismataAI-dave-master source/testing/StalemateTracker.h).
PRIMARY signal: the board (owner, cardType) multiset is unchanged across consecutive turn-start
states. The C++ engine MUST match this algorithm. This module is the executable spec + the
3-game calibration regression + a reusable analysis tool. Design:
docs/superpowers/specs/2026-06-16-selfplay-stalemate-draw-policy-design.md
"""
import gzip
import json


def population_multiset(table):
    """The (owner, cardName) multiset over ALIVE units in a replay state's `table`."""
    sig = {}
    for u in table:
        if u.get("deadness") == "alive":
            k = (u["owner"], u["cardName"])
            sig[k] = sig.get(k, 0) + 1
    return sig


class StalemateTracker:
    """Counts consecutive turn-start states with no population change; fires at `threshold` plies.

    threshold <= 0 disables firing (observe always returns False). last_progress_ply is the ply
    index of the most recent population change (the trim boundary for self-play).
    """

    def __init__(self, threshold):
        self.threshold = threshold
        self.no_change = 0
        self.last_progress_ply = 0
        self._prev = None

    def observe(self, sig, ply):
        """Feed one turn-start multiset at ply index `ply`. Returns True iff stalled."""
        if self._prev is None or sig != self._prev:
            self.no_change = 0
            self.last_progress_ply = ply
        else:
            self.no_change += 1
        self._prev = sig
        return self.threshold > 0 and self.no_change >= self.threshold


def turn_start_states(replay):
    """Turn-start state for ply p (C++ replay convention): states[p==0 ? 0 : turnBoundaries[p]-1]."""
    tb, states = replay["turnBoundaries"], replay["states"]
    return [states[0 if p == 0 else max(0, min(tb[p] - 1, len(states) - 1))]
            for p in range(len(tb))]


def scan_replay(replay, threshold):
    """Run the tracker over a replay's turn-start states. Returns (last_progress_ply, fire_ply|None)."""
    tr = StalemateTracker(threshold)
    for ply, state in enumerate(turn_start_states(replay)):
        if tr.observe(population_multiset(state["table"]), ply):
            return tr.last_progress_ply, ply
    return tr.last_progress_ply, None


def load_replay(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run it — expect PASS.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_stalemate.py -q`
Expected: PASS (the 3 calibration cases assert `(59,99) / (50,90) / (54,94)`; if the replays are absent they SKIP, but on this machine they exist).

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/stalemate.py eval/tests/test_stalemate.py && git commit -m "eval(rl): stalemate-detection oracle + 3-game calibration regression (draw-policy spec)"
```

---

## Task 2: C++ `StalemateTracker.h` (pure struct) + `--test-stalemate` probe

A header-only struct (no engine dependencies, keys are plain ints) so it is trivially testable and needs no build-file changes. The probe follows the existing `--test-rng` / `--test-sampler` pattern in `main.cpp`.

**Files:**
- Create: `c:/libraries/PrismataAI-dave-master/source/testing/StalemateTracker.h`
- Modify: `c:/libraries/PrismataAI-dave-master/source/standalone/main.cpp` (add the `--test-stalemate` branch next to the other `--test-*` branches, ~lines 241–361)

- [ ] **Step 1: Create `source/testing/StalemateTracker.h`:**

```cpp
#pragma once

#include <map>
#include <utility>

namespace Prismata
{
// (owner, cardTypeID) -> count over live units. Plain ints so this header has no engine deps
// and is unit-testable in isolation.
typedef std::map<std::pair<int, int>, int> PopulationMultiset;

// Mirrors eval/stalemate.py StalemateTracker. PRIMARY signal: the population multiset unchanged
// across consecutive turn-start states. See the design spec
// (docs/superpowers/specs/2026-06-16-selfplay-stalemate-draw-policy-design.md).
struct StalemateTracker
{
    int threshold = 0;          // plies; <= 0 disables firing
    int noChangeCount = 0;
    int lastProgressPly = 0;
    bool havePrev = false;
    PopulationMultiset prevSig;

    // Feed one turn-start multiset at index plyIndex. Returns true iff stalled (>= threshold).
    bool observe(const PopulationMultiset & sig, int plyIndex)
    {
        if (!havePrev || sig != prevSig)
        {
            noChangeCount = 0;
            lastProgressPly = plyIndex;
        }
        else
        {
            ++noChangeCount;
        }
        prevSig = sig;
        havePrev = true;
        return threshold > 0 && noChangeCount >= threshold;
    }
};
}
```

- [ ] **Step 2: Add the `--test-stalemate` probe to `source/standalone/main.cpp`.** Immediately after the existing `--test-sampler` block (which ends ~line 361 with `return ...;`), add:

```cpp
    // Usage: PrismataAI.exe --test-stalemate    (prints PASS/FAIL, returns 0/1)
    if (argc >= 2 && std::string(argv[1]) == "--test-stalemate")
    {
        Prismata::StalemateTracker tr1; tr1.threshold = 3;
        Prismata::PopulationMultiset a; a[std::make_pair(0, 0)] = 1;
        bool f[5];
        for (int p = 0; p < 5; ++p) { f[p] = tr1.observe(a, p); }
        bool ok = !f[0] && !f[1] && !f[2] && f[3] && f[4] && tr1.lastProgressPly == 0;

        Prismata::StalemateTracker tr2; tr2.threshold = 2;
        Prismata::PopulationMultiset b; b[std::make_pair(0, 0)] = 2;
        Prismata::PopulationMultiset seq[5] = { a, a, b, b, b };   // change at ply 2
        bool g[5];
        for (int p = 0; p < 5; ++p) { g[p] = tr2.observe(seq[p], p); }
        ok = ok && !g[3] && g[4] && tr2.lastProgressPly == 2;

        printf("--test-stalemate: %s\n", ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }
```

Add `#include "../testing/StalemateTracker.h"` to `main.cpp`'s includes (alongside its other `../testing/...` includes).

- [ ] **Step 3: (No build here — batched into Task 7.)** Re-read both edits to confirm: the struct compiles in isolation (only `<map>`/`<utility>`), the probe uses `std::make_pair` for the keys, and the expected booleans match Task 1's `test_frozen_run_fires_at_threshold` / `test_change_resets_counter` (this is the C++ mirror of those two Python tests).

- [ ] **Step 4: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add source/testing/StalemateTracker.h source/standalone/main.cpp && git commit -m "engine(rl): StalemateTracker.h (pure no-progress counter) + --test-stalemate probe"
```

---

## Task 3: Wire the tracker into the `TournamentGame` loop (self-play AND eval)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/TournamentGame.h`
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/TournamentGame.cpp` (loop ~lines 122–135 and the V2 finalize call ~line 321)

- [ ] **Step 1: `TournamentGame.h` — include the tracker, add members + a setter.** Add near the other includes:

```cpp
#include "StalemateTracker.h"
```

In the class body (next to the other per-game members), add:

```cpp
    Prismata::StalemateTracker _stalemate;   // threshold 0 = disabled
    int  _lastProgressPly = -1;              // last population change (trim boundary); -1 = no stalemate
    bool _stalemateDraw   = false;

public:
    void setStalemateThreshold(int n) { _stalemate.threshold = n; }
```

(Place the `public:` setter with the other public setters such as `setReplaySaveDir` / `setExportTrainingV2`; keep the data members with the private members.)

- [ ] **Step 2: `TournamentGame.cpp` — add the multiset builder** as a file-local helper near the top of the file (after the includes, before the playGame method):

```cpp
static Prismata::PopulationMultiset buildPopulationMultiset(const GameState & s)
{
    Prismata::PopulationMultiset sig;
    for (PlayerID p = 0; p < 2; ++p)
    {
        for (const auto & id : s.getCardIDs(p))   // getCardIDs returns LIVE cards only
        {
            const int typeID = static_cast<int>(s.getCardByID(id).getType().getID());
            sig[std::make_pair(static_cast<int>(p), typeID)] += 1;
        }
    }
    return sig;
}
```

- [ ] **Step 3: `TournamentGame.cpp` — drive the tracker at the loop top + move `++plyIndex`.** The current loop body (~lines 124–135) is:

```cpp
    while(!_game.gameOver())
    {
        PlayerID playerToMove = _game.getState().getActivePlayer();

        if (_v2Exporter)
        {
            _v2Exporter->capture(_game.getState(), plyIndex);
            ++plyIndex;
        }
```

Replace it with (the stalemate block runs for BOTH self-play and eval; `++plyIndex` moves out of the exporter guard so the index advances every ply):

```cpp
    while(!_game.gameOver())
    {
        PlayerID playerToMove = _game.getState().getActivePlayer();

        // Stalemate (no-progress) draw: end a frozen game early. Runs for self-play AND eval.
        // On firing we break with both players alive -> winner()==Player_None -> draw (0.5).
        if (_stalemate.threshold > 0)
        {
            const bool stalled = _stalemate.observe(buildPopulationMultiset(_game.getState()), plyIndex);
            _lastProgressPly = _stalemate.lastProgressPly;
            if (stalled)
            {
                _stalemateDraw = true;
                break;
            }
        }

        if (_v2Exporter)
        {
            _v2Exporter->capture(_game.getState(), plyIndex);
        }
        ++plyIndex;
```

(Everything else in the loop body is unchanged. The `break` exits before `playNextTurn`, so the captured records are `[0 .. plyIndex-1]` and `_lastProgressPly < plyIndex`.)

- [ ] **Step 4: `TournamentGame.cpp` — pass the trim boundary to the V2 exporter.** The current V2 finalize call (~lines 316–325) is:

```cpp
    if (_v2Exporter)
    {
        const GameState & finalState = _game.getState();
        _v2Exporter->finalize(finalState.winner(),
                              static_cast<int>(finalState.getTurnNumber()),
                              _exportV2GameId);
        _v2Exporter.reset();
    }
```

Change the `finalize` call to pass `_lastProgressPly` ONLY when this game ended by stalemate (a normal win/draw must not be trimmed):

```cpp
        _v2Exporter->finalize(finalState.winner(),
                              static_cast<int>(finalState.getTurnNumber()),
                              _exportV2GameId,
                              _stalemateDraw ? _lastProgressPly : -1);
```

(The `_serializer->finalize(...)` block above it is UNCHANGED: the replay keeps the full played game — through the break point — as the forensic record. Its top-level `"turns"` is the played length; that is intentional and separate from the V2 kept length.)

- [ ] **Step 5: (No build here — batched into Task 7.)** Re-read: `buildPopulationMultiset` uses `getCardIDs` (live only) + `getCardByID(id).getType().getID()`; the `break` precedes `playNextTurn`; `++plyIndex` now runs every iteration; the finalize call passes `-1` unless `_stalemateDraw`.

- [ ] **Step 6: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add source/testing/TournamentGame.h source/testing/TournamentGame.cpp && git commit -m "engine(rl): drive StalemateTracker in the tournament loop (self-play + eval); early draw on no-progress"
```

---

## Task 4: Trim + kept-length stamp in `SelfPlayV2Exporter::finalize`

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/SelfPlayV2Exporter.h` (the `finalize` declaration, ~line 76)
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/SelfPlayV2Exporter.cpp` (the `finalize` body + write loop, ~lines 41, 84–116)

- [ ] **Step 1: `SelfPlayV2Exporter.h` — add the `lastProgressPly` parameter** (default `-1` keeps every existing call site behaving identically). Change:

```cpp
    bool finalize(PlayerID winner, int totalPlies, int gameId);
```
to:
```cpp
    bool finalize(PlayerID winner, int totalPlies, int gameId, int lastProgressPly = -1);
```

- [ ] **Step 2: `SelfPlayV2Exporter.cpp` — update the signature + the write loop.** Change the definition line (~41) to match the header (`..., int gameId, int lastProgressPly)`). Then in the record-write loop (~lines 84–116) that iterates `_records`:
  - compute the kept length once, before the loop (non-stalemate ⇒ the unchanged passed length, so existing training data is byte-for-byte unaffected; `total_plies` feeds `compute_labels`, so this MUST stay exact):

```cpp
    const int keptPlies = (lastProgressPly >= 0) ? (lastProgressPly + 1) : totalPlies;
```
  - inside the loop (the loop index is the per-record ply index, since `capture` pushed one record per ply in order), **skip trimmed records**:

```cpp
        if (lastProgressPly >= 0 && static_cast<int>(i) > lastProgressPly)
        {
            continue;   // drop the frozen tail (and the N-ply confirmation window)
        }
```
  - when stamping `total_plies` into each kept record, use `keptPlies` instead of the passed `totalPlies`:

```cpp
        // was: rec.AddMember("total_plies", totalPlies, alloc);
        rec.AddMember("total_plies", keptPlies, alloc);
```

(Find the existing `total_plies` `AddMember` in the loop and replace its value with `keptPlies`. For non-stalemate games `lastProgressPly == -1` ⇒ `keptPlies == totalPlies` and the `lastProgressPly >= 0` skip-guard never fires, so the shard is byte-for-byte identical to today — only stalemate games are trimmed and re-stamped.)

- [ ] **Step 3: (No build here — batched into Task 7.)** Re-read: trimming uses the record index `i` vs `lastProgressPly`; `total_plies` is now the kept length; the default `-1` preserves all existing callers.

- [ ] **Step 4: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add source/testing/SelfPlayV2Exporter.h source/testing/SelfPlayV2Exporter.cpp && git commit -m "engine(rl): SelfPlayV2Exporter trims the frozen tail + stamps kept-length total_plies"
```

---

## Task 5: Read `StalemateThreshold` from config + plumb to `TournamentGame`

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/Tournament.h` (add the member)
- Modify: `c:/libraries/PrismataAI-dave-master/source/testing/Tournament.cpp` (read it ~lines 29–47; apply it where the other per-game setters are applied ~lines 187–196)

- [ ] **Step 1: `Tournament.h` — add the member** next to `_rounds` / `_threads`:

```cpp
    int _stalemateThreshold = 0;   // plies; 0 = disabled (config key "StalemateThreshold")
```

- [ ] **Step 2: `Tournament.cpp` — read the config key.** Alongside the existing `JSONTools::ReadInt(...)` calls (~lines 29–47), add:

```cpp
    JSONTools::ReadInt("StalemateThreshold", tournamentValue, _stalemateThreshold);
```

- [ ] **Step 3: `Tournament.cpp` — apply it to each `TournamentGame`.** Find where the other per-game settings are pushed onto the `TournamentGame` object before it plays (the same place `setReplaySaveDir(...)` / `setExportTrainingV2(...)` are called, ~lines 187–196), and add the matching setter on the SAME object:

```cpp
    <tournamentGameObject>.setStalemateThreshold(_stalemateThreshold);
```

(Use the exact variable name of the `TournamentGame` instance used by the neighbouring `setReplaySaveDir` / `setExportTrainingV2` calls so it is configured identically for both self-play and eval runs.)

- [ ] **Step 4: (No build here — batched into Task 7.)** Re-read: the key name is exactly `"StalemateThreshold"`; the setter is applied on the same `TournamentGame` instance as the existing setters.

- [ ] **Step 5: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add source/testing/Tournament.h source/testing/Tournament.cpp && git commit -m "engine(rl): read StalemateThreshold from config and plumb to TournamentGame"
```

---

## Task 6: Enable the rule on the RL blocks (config)

**Files:**
- Modify: `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt` (the `Benchmarks` blocks `RL_SelfPlay_General`, `RL_PoL_origin`, `RL_PoL_masterbot`)

- [ ] **Step 1: Add `"StalemateThreshold": 40` to the three RL tournament blocks.** Surgically insert the key into each block (keep strict JSON, no BOM). After the edit each block reads e.g.:

```json
{ "run":false, "type":"Tournament", "name":"RL_PoL_origin", "rounds":48, "Seed":2026, "UpdateIntervalSec":5, "Threads":8, "RandomCards":8, "StalemateThreshold":40, "players":[ ... ] }
```

Apply the same `"StalemateThreshold":40` to `RL_SelfPlay_General` (the self-play block) and `RL_PoL_masterbot`. Do NOT add it to any other block.

- [ ] **Step 2: Verify strict JSON + the three blocks carry it.**

Run:
```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); b={x['name']:x for x in c['Benchmarks'] if isinstance(x,dict)}; assert all(b[n].get('StalemateThreshold')==40 for n in ['RL_SelfPlay_General','RL_PoL_origin','RL_PoL_masterbot']); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit.**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): enable StalemateThreshold=40 on the RL self-play + eval blocks"
```

---

## Task 7: Build, unit-probe, smoke (self-play trim + eval early-end), re-pin sha, re-run gates

This is the consolidated verification of all C++ tasks (2–6). **Stop any running engine first.**

**Files:** none new — builds + a temporary config smoke (reverted) + `eval/campaign_frozen.json` (sha re-pin).

- [ ] **Step 1: Rebuild both engine targets** (Release x64, full rebuild).

Run (Git Bash):
```bash
MSB="/c/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe"
"$MSB" "c:/libraries/PrismataAI-dave-master/build/Prismata_Testing.vcxproj"   //t:Rebuild //p:Configuration=Release //p:Platform=x64 //m //v:minimal
"$MSB" "c:/libraries/PrismataAI-dave-master/build/Prismata_Standalone.vcxproj" //t:Rebuild //p:Configuration=Release //p:Platform=x64 //m //v:minimal
cp c:/libraries/PrismataAI-dave-master/bin/Prismata_Standalone.exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe
```
Expected: both `Build succeeded`. (If LNK1104: an exe is still running — stop it and retry.)

- [ ] **Step 2: Run the C++ unit probe.**

Run: `c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe --test-stalemate`
Expected: `--test-stalemate: PASS`

- [ ] **Step 3: Force the early-end + trim path with a tiny low-threshold self-play smoke.** A real stalemate is rare (3/1032), so set a deliberately low threshold to make the path fire deterministically. Temporarily, in `config.txt`: set `RL_SelfPlay_General` `"rounds":4`, `"StalemateThreshold":3`, `"run":true` (leave its `exportTrainingV2` / `saveReplays` as-is). Run the engine, then inspect the shard:

```bash
cd c:/libraries/PrismataAI-dave-master/bin && ./Prismata_Testing.exe
python - <<'PY'
import json, glob, os
d = r'c:/libraries/PrismataAI-dave-master/bin/asset/training/rl_general_v2'
fs = sorted(glob.glob(os.path.join(d, 'selfplay_*.jsonl')))
assert fs, 'no shards produced'
draws = 0
for g in fs:
    rows = [json.loads(l) for l in open(g) if l.strip()]
    assert rows, 'empty shard ' + g
    # records must be a contiguous 0..N-1 block (the frozen tail was trimmed)
    assert max(r['ply_index'] for r in rows) + 1 == len(rows), 'non-contiguous: ' + os.path.basename(g)
    # total_plies must be the KEPT length (== record count) for every record
    assert all(r['total_plies'] == len(rows) for r in rows), 'total_plies != kept length: ' + os.path.basename(g)
    if rows[0]['outcome_p0'] == 0.5:
        draws += 1
print('shards', len(fs), 'stalemate_draws', draws)
assert draws >= 1, 'no draw at threshold 3 - lower to 2 and re-run'
PY
```
Expected: `shards 4 stalemate_draws >=1` with no assertion error — every game is a contiguous trimmed block with `total_plies == kept record count`, and at least one game stalemate-drew (the rule fired + the tail was trimmed). (If `stalemate_draws` is 0 at threshold 3, set it to 2 and re-run.)

- [ ] **Step 4: Smoke the eval early-end.** Temporarily set `RL_PoL_origin` `"rounds":2`, `"StalemateThreshold":3`, `"run":true` (and ensure its opponent weights exist). Run `./Prismata_Testing.exe`; confirm it completes without crashing and the tournament HTML/`tests/` results are produced (a stalemate game ends as a draw and contributes 0.5 to the win-rate — no special output needed, just no crash and a completed block).

- [ ] **Step 5: RESTORE the config.** Revert all Step-3/Step-4 edits: `RL_SelfPlay_General` back to `rounds:516` (or its at-rest value), `StalemateThreshold:40`, `run:false`; `RL_PoL_origin` back to `rounds:48`, `StalemateThreshold:40`, `run:false`. Re-verify:

```bash
python -c "import json; c=json.load(open(r'c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt',encoding='utf-8-sig')); b={x['name']:x for x in c['Benchmarks'] if isinstance(x,dict)}; \
assert b['RL_SelfPlay_General']['rounds']==516 and b['RL_SelfPlay_General']['StalemateThreshold']==40 and b['RL_SelfPlay_General'].get('run')!=True; \
assert b['RL_PoL_origin']['rounds']==48 and b['RL_PoL_origin']['StalemateThreshold']==40 and b['RL_PoL_origin'].get('run')!=True; print('restored OK')"
```
Expected: `restored OK`

- [ ] **Step 6: Re-pin the engine exe shas + re-run the correctness gates.** The rebuild changed both exes, so preflight's `engine_sha` check will fail until re-pinned (and a6 + three-way must be re-run as discipline — expected unchanged since no value/feature code was touched).

```bash
cd c:/libraries/PrismataAI && python -c "import hashlib; \
print('testing', hashlib.sha256(open(r'c:/libraries/PrismataAI-dave-master/bin/Prismata_Testing.exe','rb').read()).hexdigest()); \
print('prismataai', hashlib.sha256(open(r'c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe','rb').read()).hexdigest())"
```
Edit `eval/campaign_frozen.json`: set `engine_testing_exe_sha256` and `engine_prismataai_exe_sha256` to those two values (surgical edits; keep it strict JSON). Then run the full preflight (it runs a6 + three-way):

Run: `cd c:/libraries/PrismataAI && python eval/preflight_config.py --config c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt --frozen eval/campaign_frozen.json`
Expected: `preflight PASSED` (a6 prints its 4 decisive values; three-way prints its pass count; both unchanged from before the rebuild).

- [ ] **Step 7: Commit (both repos).**

```bash
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "config(rl): restore RL blocks after stalemate smoke (rounds + StalemateThreshold 40, run:false)"
cd c:/libraries/PrismataAI && git add eval/campaign_frozen.json && git commit -m "eval(rl): re-pin engine exe shas after the stalemate-rule rebuild"
```

---

## Task 8: Record the threshold in the frozen tuple + assert it in preflight (Phase-1 reproducibility)

Makes the rule part of the campaign identity so a drifted/removed `StalemateThreshold` is caught at stage 0 (spec §10). Scale-tier (changing it = re-anchor + a campaign_log entry, not a new campaign).

**Files:**
- Modify: `c:/libraries/PrismataAI/eval/campaign_frozen.json`
- Modify: `c:/libraries/PrismataAI/eval/preflight_config.py`
- Test: `c:/libraries/PrismataAI/eval/tests/test_preflight.py`

- [ ] **Step 1: Add the frozen key.** In `eval/campaign_frozen.json`, add a scale-tier key:

```json
  "selfplay_stalemate_threshold": 40,
```
and add `"selfplay_stalemate_threshold"` to the `tiers.scale` list. Verify it parses:

```bash
python -c "import json; f=json.load(open(r'c:/libraries/PrismataAI/eval/campaign_frozen.json',encoding='utf-8-sig')); assert f['selfplay_stalemate_threshold']==40 and 'selfplay_stalemate_threshold' in f['tiers']['scale']; print('OK')"
```
Expected: `OK`

- [ ] **Step 2: Write the failing test.** Add to `eval/tests/test_preflight.py` (follow the existing `env` fixture pattern):

```python
def test_stalemate_threshold_drift_fails(env, capsys):
    """v4.1: the RL blocks must carry the frozen selfplay_stalemate_threshold."""
    env["frozen"]["selfplay_stalemate_threshold"] = 40
    for b in env["cfg"]["Benchmarks"]:
        if b["name"] in ("RL_SelfPlay_General", "RL_PoL_origin", "RL_PoL_masterbot"):
            b["StalemateThreshold"] = 40
    env["cfg"]["Benchmarks"][0]["StalemateThreshold"] = 8   # drift the self-play block
    rc, out = run_main(env, capsys)
    assert rc == 1
    assert_only_fails(out, "stalemate_threshold")
    assert "StalemateThreshold" in out
```
Also seed the baseline fixture so it passes when consistent: in `make_config()` add `"StalemateThreshold": 40` to the `RL_SelfPlay_General`, `RL_PoL_origin`, `RL_PoL_masterbot` blocks, and in `make_frozen()` add `"selfplay_stalemate_threshold": 40`.

- [ ] **Step 3: Run it — expect FAIL** (`check_stalemate_threshold` undefined / not wired).

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py::test_stalemate_threshold_drift_fails -v`
Expected: FAIL

- [ ] **Step 4: Implement `check_stalemate_threshold` in `preflight_config.py`** and wire it into `run_checks` (inside the `if frozen is not None:` block):

```python
STALEMATE_BLOCKS = ("RL_SelfPlay_General", "RL_PoL_origin", "RL_PoL_masterbot")


def check_stalemate_threshold(cfg, frozen):
    want = frozen.get("selfplay_stalemate_threshold")
    if want is None:
        return []   # older frozen files without the key: no-op
    blocks = {b.get("name"): b for b in cfg.get("Benchmarks", []) if isinstance(b, dict)}
    failures = []
    for name in STALEMATE_BLOCKS:
        blk = blocks.get(name)
        if blk is None:
            failures.append("block '%s' not found (must carry StalemateThreshold==%s)" % (name, want))
            continue
        got = blk.get("StalemateThreshold")
        if int(got if got is not None else -1) != int(want):
            failures.append("%s.StalemateThreshold is %r but frozen selfplay_stalemate_threshold is %s "
                            "(the draw rule is campaign identity; reconcile config + frozen together)"
                            % (name, got, want))
    return failures
```
Wire it: `results.append(("stalemate_threshold", check_stalemate_threshold(cfg, frozen)))`.

- [ ] **Step 5: Run it — expect PASS; then the full suite + live preflight.**

Run: `cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_preflight.py -q && cd c:/libraries/PrismataAI && python eval/preflight_config.py --config c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt --frozen eval/campaign_frozen.json`
Expected: tests PASS; `preflight PASSED` (the check count increments by one).

- [ ] **Step 6: Commit.**

```bash
cd c:/libraries/PrismataAI && git add eval/campaign_frozen.json eval/preflight_config.py eval/tests/test_preflight.py && git commit -m "eval(rl): freeze + preflight-assert the self-play StalemateThreshold (Phase-1 reproducibility)"
```

---

## Post-landing follow-on (NOT a task — needs a real run to measure)

- **Recalibrate `game_length_band`** (currently `[25, 60]` in `campaign_frozen.json`). Once the rule lands, the 200-ply outliers vanish and stalemate games become ~50–59 plies; re-measure the game-length distribution on the next real iteration and adjust the band (the median ~37 is unaffected). Record the change as a `campaign_log.md` scale-tier entry. (Reference: spec §10.)

---

## Self-review (coverage vs spec)

- Spec §3 board-multiset signal → Tasks 1 (oracle), 2 (`StalemateTracker.h`), 3 (`buildPopulationMultiset` + loop). Resource pools excluded by construction (the multiset has no resource term).
- Spec §3.1 residual blind spot → pinned by `test_same_type_netzero_is_documented_blind_spot` (Task 1) + the C++ probe (Task 2); the optional `numKilledCards`/buy secondary reset is documented in the spec as future hardening, intentionally NOT built in v1.
- Spec §3.3 N = 40 plies, decoupled from trim → config key (Task 6), the trim is to `last_progress_ply` regardless of N (Task 4).
- Spec §4 architecture (counter / kept-length stamp / export trim / config) → Tasks 2–6; eval = items 1–2 only (no trim) → Task 3 runs the tracker for both; Task 4's trim only fires when `_stalemateDraw` (self-play games that stalemated).
- Spec §4 "no `GameState`/feature/value/parity change" → all edits are in `TournamentGame` / `SelfPlayV2Exporter` / `Tournament` / `main.cpp` / config; the sha re-pin + a6 + three-way re-run (Task 7) is the rebuild discipline.
- Spec §6 200-cap backstop → untouched (`Game::gameOver()` still enforces `m_turnLimit = 200`).
- Spec §7 testing → Task 1 (oracle + 3-game regression + net-zero), Task 2 (`--test-stalemate`), Task 7 (low-threshold self-play trim smoke + eval early-end smoke).
- Spec §8 calibration numbers → encoded as the Task-1 regression expectations `(59,99)/(50,90)/(54,94)`.
- Spec §9 risks (rebuild discipline, false draw) → Task 7 sha re-pin + a6/three-way; N=40.
- Spec §10 follow-ons → Task 8 (frozen + preflight) + the post-landing band-recalibration note.
- No placeholders: every code step shows the actual code; every command has expected output. Type/name consistency: `StalemateTracker` / `PopulationMultiset` / `observe` / `lastProgressPly` / `setStalemateThreshold` / `StalemateThreshold` / `selfplay_stalemate_threshold` are used identically across tasks.
