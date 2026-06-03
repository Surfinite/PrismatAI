# RL Self-Play Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a gated single-iteration RL value-net self-play loop on engine_v1 and run the Infusion-Grid-optional first campaign, producing a defensible local go/no-go signal (per spec §12).

**Architecture:** Self-play (CPU, fixed-sims UCT + temperature/ε-uniform root sampler) → `saveReplays` replay JSON → JS V2 extractor → HDF5 → low-LR SWA fine-tune with a sliding replay buffer + human-only rehearsal → `export_weights_v2` `.bin` (+ parity) → 3-anchor win-rate eval (Wilson CIs, sequential testing, manifest) → human-reviewed promote/reject/inconclusive gate. The supervised net is the RL init; argmax is preserved for eval, temperature is self-play-only.

**Tech Stack:** C++17 (engine_v1, `Prismata.sln`, x64/v145), PyTorch (XPU on Intel Arc), Node.js (JS engine + SteamAI bridge), Python 3 (training + eval orchestration).

**Source spec:** `docs/superpowers/specs/2026-06-02-rl-selfplay-loop-design-v2.md` (+ `META-REVIEW-*`, `-CONTEXT.md`). Companions: `docs/rl-action-space-partials-map.md`, `docs/plans/2026-05-31-linux-rl-bringup-and-go-no-go.md`.

---

## Two-repo map (read before starting)

| Repo | Path | Branch | Holds |
|---|---|---|---|
| **Engine (RL target)** | `c:/libraries/PrismataAI-dave-master/` | `dave-master-jsonclean` | engine_v1 C++ (RNG, UCT, config, ReplaySerializer, parity harness) |
| **Main** | `c:/libraries/PrismataAI/` | `feature/production-vectors` | `training/` (train.py, vectorize_v2, export_weights_v2), `js_engine/` (matchup_clean.js, training_example.js, steam_ai.js), docs/specs/plans |

- **Never use engine_v2** (the `PrismataAI/` clean-room engine — indicted ~33 pts weaker). All engine work is in `PrismataAI-dave-master/`.
- C++ commits go on `dave-master-jsonclean`. Training/JS/eval commits go on `feature/production-vectors`. Do not cross-file (see memory `feedback_cpp_replay_branch_scope`).
- Push to the `PrismatAlpha` fork only, never upstream. Branch before committing if on a default branch.

## Build & test conventions (every C++ task ends here)

**Build (engine_v1, from a shell):**
```bash
"/c/Program Files/Microsoft Visual Studio/18/Community/MSBuild/Current/Bin/MSBuild.exe" \
  "c:/libraries/PrismataAI-dave-master/visualstudio/Prismata.sln" \
  //t:Prismata_standalone:Rebuild //t:Prismata_Testing:Rebuild \
  //p:Configuration=Release //p:Platform=x64 //p:PlatformToolset=v145 //m
```
- **Build only `Prismata_standalone` + `Prismata_Testing`** — the `Prismata_GUI` project is broken (SFML 3.x) and building the whole solution fails.
- Always `:Rebuild` (incremental builds may not relink). Stop any running `.exe` first (LNK1104 file lock).
- Outputs (Release x64): `c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe` (= `Prismata_standalone` — the one-shot **Steam stdin/stdout responder** plus `--dump-features`/`--test-rng`/`--test-sampler`/`--probe-buys` CLI hooks) and `c:/libraries/PrismataAI-dave-master/bin/Prismata_Testing.exe` (runs `Benchmarks::DoBenchmarks("asset/config/config.txt")` — every `"run":true` block; no CLI args).

**C++ "unit tests":** there is **no C++ test framework** (`source/testing/tests/` holds only docs). Two test mechanisms, both used in this plan:
1. **CLI-hook tests** in `source/standalone/main.cpp` (pattern = the existing `--dump-features` hook at line 47): a `--test-X` arg runs asserts, prints `PASS`/`FAIL`, returns exit code 0/1. Run from `bin/`.
2. **Benchmark tournaments**: add a `{"run":false,...}` block to `config.txt`, flip to `"run":true`, run `Prismata_Testing.exe` from `bin/`.

**Python tests:** `cd c:/libraries/PrismataAI/training && python -m pytest tests/<file>.py -v` (pattern = `tests/test_model_deepsets.py`).

**Commit cadence:** one commit per task (after its verification passes). Use `feat(ai|train|eval): …`; end the message with the Co-Authored-By trailer.

## File structure (what gets created / modified)

**Engine (`PrismataAI-dave-master/`):**
- Modify `source/engine/Random.cpp`, `source/engine/Random.h` — thread-hash-free seedable RNG + `Real01()` (Task 1).
- Create `source/ai/MoveSampler.h`, `source/ai/MoveSampler.cpp` — pure temperature+ε sampler (Task 2); add to `Prismata_AI.vcxproj`.
- Modify `source/ai/UCTSearchParameters.hpp`, `source/ai/UCTSearch.cpp`, `source/ai/AIParameters.cpp`, `source/ai/Player_UCT.*` — wire sampler self-play-only + last-root-visits/chosen/argmax accessors (Tasks 3, 5, 10).
- Modify `source/standalone/main.cpp` — `--test-rng`, `--test-sampler` hooks (Tasks 1–2); `--probe-buys` (Task 11); Steam-responder `aivisits` diagnostics (Task 10).
- Create `source/testing/SelfPlayV2Exporter.h/.cpp` — C++ V2 training exporter (Task 5); add to `Prismata_Testing.vcxproj`.
- Modify `source/testing/TournamentGame.*`, `source/testing/Tournament.*`, `Tournament.h` — turn-start capture + `exportTrainingV2` + optional `Seed` + `ForcedCards` (Tasks 1, 5, 12).
- Modify `source/engine/GameState.cpp/.h` — forced-card-set overload (Task 12).
- Modify `bin/asset/config/config.txt` — `RL_SelfPlay`/`RL_Eval`/`RL_Explore` players, IG-optional variant + iterator, tournament blocks (Tasks 1, 4, 7, 9, 11, 12, 13, 14).

**Main (`PrismataAI/`):**
- Create `js_engine/query_move.js` — one-shot Steam-protocol move-query helper (Task 10).
- Create `training/rl_data.py` — replay buffer + rehearsal + colour-balance loaders (Task 6).
- Modify `training/train.py` — `--rl-mode` flags + SWA + fine-tune (Task 6).
- Create `training/tests/test_labels.py`, `training/tests/test_rl_data.py`, `training/tests/test_selfplay_export_parity.py` (Tasks 5, 6).
- Create `eval/wilson.py`, `eval/run_eval.py`, `eval/human_val.py`, `eval/tactical_suite.py`, `eval/action_coverage.py`, `eval/render_dashboard.py`, `eval/offbook_audit.py`, `eval/calibrate_n.py`, `eval/rl_campaign.md`, `eval/run_iteration.ps1` (Tasks 7–14).
- Create `eval/tests/test_wilson.py` (Task 7); `tools/parity/dump_value_batch.py` (Task 8).

---

## Task 1: Thread-hash-free seedable RNG + deterministic mode (Prereq §10.1)

**Repo:** `PrismataAI-dave-master` (`dave-master-jsonclean`). **Files:**
- Modify: `source/engine/Random.h`, `source/engine/Random.cpp`
- Modify: `source/standalone/main.cpp` (add `--test-rng` hook)
- Modify: `source/testing/Tournament.cpp` (optional `Seed` field), `source/testing/main.cpp` (seed source)

**Why:** `nextThreadSeed()` mixes `std::hash<std::thread::id>` into every engine seed (`Random.cpp:26`), so a fixed base seed does **not** reproduce a run. The temperature sampler and tournament card-sets need a clean seedable stream + a single-thread deterministic mode (spec §3, §9, §10.1). UCT tie-breaking is already deterministic (no Random); randomness enters via card-set generation (`GameState::setStartingState`), playouts, `PPPortfolio::getRandomMove`, and the new sampler — all funnel through `Random`.

- [ ] **Step 1: Add the `--test-rng` CLI hook (failing test).**

In `source/standalone/main.cpp`, immediately after the existing `--dump-features` block (after its closing `}` near line 92), add:

```cpp
    // --- RNG determinism self-test ---
    // Usage: PrismataAI.exe --test-rng    (prints PASS/FAIL, returns 0/1)
    if (argc >= 2 && std::string(argv[1]) == "--test-rng")
    {
        // mixSeed replicated locally (must match Random.cpp's anonymous-namespace mixSeed).
        auto mixSeed = [](uint64_t x) -> uint64_t {
            x += 0x9e3779b97f4a7c15ULL;
            x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
            x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
            return x ^ (x >> 31);
        };

        // (1) Seed(S) must reseed the engine to a PURE function of S (no thread::id term).
        //     Reference stream = mt19937_64(mixSeed(S)) consumed by the same distribution.
        const uint64_t S = 123456789ULL;
        std::mt19937_64 ref(mixSeed(S));
        std::uniform_int_distribution<size_t> dist(0, 1000000 - 1);

        Prismata::Random::Seed(S);
        bool pureFnOfSeed = true;
        for (int i = 0; i < 8; ++i)
        {
            size_t expected = dist(ref);
            size_t got = Prismata::Random::Int(1000000);
            if (got != expected) { pureFnOfSeed = false; break; }
        }

        // (2) Re-seeding with the same S reproduces the same stream.
        Prismata::Random::Seed(S);
        size_t a = Prismata::Random::Int(1000000);
        Prismata::Random::Seed(S);
        size_t b = Prismata::Random::Int(1000000);
        bool reproducible = (a == b);

        bool ok = pureFnOfSeed && reproducible;
        printf("--test-rng: pureFnOfSeed=%d reproducible=%d => %s\n",
               (int)pureFnOfSeed, (int)reproducible, ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }
```

Add `#include <random>` to the top of `source/standalone/main.cpp` if not already present.

- [ ] **Step 2: Build and run — verify it FAILS.**

Build (see conventions), then:
```bash
cd c:/libraries/PrismataAI-dave-master/bin && ./PrismataAI.exe --test-rng
```
Expected: `pureFnOfSeed=0 ... => FAIL` — because `nextThreadSeed()` still adds the thread hash, so `Random` ≠ `mt19937_64(mixSeed(S))`.

- [ ] **Step 3: Remove the thread-hash; add `Real01()`.**

In `source/engine/Random.cpp`, change `nextThreadSeed()` (remove the `threadHash` term):

```cpp
    uint64_t nextThreadSeed()
    {
        const uint64_t sequence = g_seedSequence.fetch_add(1, std::memory_order_relaxed);
        return mixSeed(g_baseSeed.load(std::memory_order_relaxed) + sequence);
    }
```
(Delete the `threadHash` line and the `#include <functional>`/`#include <thread>` if now unused — leave the includes if other code needs them; unused includes are harmless, so prefer leaving them to avoid breaking siblings.)

Then add a `[0,1)` double draw. In `source/engine/Random.cpp`, inside `namespace Prismata { namespace Random {`, after `Int`:

```cpp
    double Real01()
    {
        std::uniform_real_distribution<double> dist(0.0, 1.0);
        return dist(engine());
    }
```
And in `source/engine/Random.h`, after `size_t Int(size_t exclusiveMax);`:
```cpp
    double Real01();   // uniform double in [0, 1), from the seedable stream
```

- [ ] **Step 4: Build and run — verify it PASSES.**
```bash
cd c:/libraries/PrismataAI-dave-master/bin && ./PrismataAI.exe --test-rng
```
Expected: `pureFnOfSeed=1 reproducible=1 => PASS`, exit 0.

- [ ] **Step 5: Make tournaments seedable (single-thread deterministic mode).**

In `source/testing/Tournament.cpp` constructor (immediately after `_threads` is initialized — the `_threads = std::max<size_t>(1, _threads);` line, ~line 30), add an optional seed member read:
```cpp
    _seed = 0;
    JSONTools::ReadInt("Seed", tournamentValue, _seed);   // 0 = time-based (default)
```
Declare `int _seed;` in `source/testing/Tournament.h` next to `_threads`.

At the **start of** `Tournament::run()` (after `_date` is set, ~line 54), add:
```cpp
    if (_seed != 0)
    {
        Random::Seed((uint64_t)_seed);
        if (_threads > 1)
        {
            fprintf(stderr, "[Tournament] Seed set but Threads=%zu>1; "
                            "full reproducibility requires Threads:1.\n", _threads);
        }
    }
```
Add `#include "Random.h"` to `Tournament.cpp` if absent.

In `source/testing/main.cpp` leave `Random::Seed((uint64_t)time(NULL))` as the default; a per-block `"Seed"` now overrides it inside `run()`.

- [ ] **Step 6: Add a reproducibility integration block + verify.**

Append to the `"Benchmarks"` array in `bin/asset/config/config.txt` (use real existing players; pure-NeuralNet players have no playout RNG, so at `Threads:1` games are fully deterministic):
```json
    {"run":false, "type":"Tournament", "name":"RNG_Repro_Check", "rounds":4, "Seed":777, "UpdateIntervalSec":5, "Threads":1, "RandomCards":8, "players":[{"name":"DSNN_Mixed35_5var_F1s","group":1},{"name":"DSNN_Mixed35_5var_F1s","group":1}]},
```
(Self-play: both same group — every pair is identical-config self-play.) Flip `"run":true`, run `Prismata_Testing.exe` from `bin/` twice, and confirm identical output (same per-player Turns total and Wins). Flip back to `"run":false`.

```bash
cd c:/libraries/PrismataAI-dave-master/bin
./Prismata_Testing.exe 2>&1 | grep -E "DSNN_Mixed35_5var_F1s|Turns" | tee /tmp/run1.txt
./Prismata_Testing.exe 2>&1 | grep -E "DSNN_Mixed35_5var_F1s|Turns" | tee /tmp/run2.txt
diff /tmp/run1.txt /tmp/run2.txt && echo "REPRODUCIBLE"
```
Expected: `REPRODUCIBLE` (empty diff). If not, recheck `Threads:1` and that no playout player is involved.

- [ ] **Step 7: Commit.**
```bash
cd c:/libraries/PrismataAI-dave-master
git add source/engine/Random.cpp source/engine/Random.h source/standalone/main.cpp \
        source/testing/Tournament.cpp source/testing/Tournament.h bin/asset/config/config.txt
git commit -m "feat(ai): thread-hash-free seedable RNG + Real01 + tournament Seed (RL determinism)"
```

---

## Task 2: Pure temperature + ε-uniform move sampler (unit-tested before engine wiring) (Prereq §10.2)

**Repo:** `PrismataAI-dave-master`. **Files:**
- Create: `source/ai/MoveSampler.h`, `source/ai/MoveSampler.cpp`
- Modify: `source/standalone/main.cpp` (add `--test-sampler`)
- Modify: `visualstudio/Prismata_AI.vcxproj` (add the new `.cpp`)

**Why:** Spec §10.2 — "Unit-test the sampler against a known visit distribution **before** it touches the engine." Extracting the math into a pure function (no engine, no Random) makes it deterministic and testable; the engine passes in two uniform draws.

- [ ] **Step 1: Create the header.**

`source/ai/MoveSampler.h`:
```cpp
#pragma once

#include <vector>
#include <cstddef>

namespace Prismata
{
namespace MoveSampler
{
    // Selects an index into `visits` for self-play root-move sampling.
    //   - Only candidates with visits > 0 are eligible.
    //   - With probability `epsilon` (when u1 < epsilon): sample UNIFORMLY over eligible candidates.
    //   - Otherwise: sample proportional to visits^(1/tau) (floating point).
    //   - tau <= 1e-6 degenerates to argmax (most-visited) over eligible candidates.
    // u1, u2 are uniform draws in [0,1). Deterministic given inputs (unit-testable; no RNG, no engine).
    // Returns 0 if there are no eligible candidates (caller guarantees >=1 in practice).
    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2);
}
}
```

- [ ] **Step 2: Create the implementation.**

`source/ai/MoveSampler.cpp`:
```cpp
#include "MoveSampler.h"

#include <cmath>
#include <limits>

namespace Prismata
{
namespace MoveSampler
{
    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2)
    {
        // Collect eligible candidates (visited at least once).
        std::vector<size_t> elig;
        for (size_t i = 0; i < visits.size(); ++i)
        {
            if (visits[i] > 0) { elig.push_back(i); }
        }
        if (elig.empty()) { return 0; }

        // epsilon-uniform branch.
        if (u1 < epsilon)
        {
            size_t k = (size_t)(u2 * (double)elig.size());
            if (k >= elig.size()) { k = elig.size() - 1; }  // guard u2 == nextafter(1.0)
            return elig[k];
        }

        // Near-zero temperature => argmax (most visited; first-wins tie-break).
        if (tau <= 1e-6)
        {
            size_t best = elig[0];
            for (size_t i = 1; i < elig.size(); ++i)
            {
                if (visits[elig[i]] > visits[best]) { best = elig[i]; }
            }
            return best;
        }

        // Proportional to visits^(1/tau).
        const double invTau = 1.0 / tau;
        std::vector<double> w(elig.size());
        double total = 0.0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            double wi = std::pow((double)visits[elig[i]], invTau);
            w[i] = wi;
            total += wi;
        }
        if (total <= 0.0) { return elig[0]; }

        double target = u2 * total;
        double cum = 0.0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            cum += w[i];
            if (target < cum) { return elig[i]; }
        }
        return elig.back();  // floating-point fallthrough
    }
}
}
```

- [ ] **Step 3: Register the new file in the project.**

In `visualstudio/Prismata_AI.vcxproj`, add `MoveSampler.cpp` to the `<ClCompile>` item group and `MoveSampler.h` to the `<ClInclude>` group, next to the other `source/ai/` entries (mirror an existing line such as `<ClCompile Include="..\source\ai\UCTSearch.cpp" />`).

- [ ] **Step 4: Add the `--test-sampler` hook (failing test, then passing).**

In `source/standalone/main.cpp`, after the `--test-rng` block, add:
```cpp
    // --- Move sampler self-test ---
    if (argc >= 2 && std::string(argv[1]) == "--test-sampler")
    {
        using Prismata::MoveSampler::sampleRootIndex;
        bool ok = true;
        auto check = [&](bool cond, const char * msg){ if (!cond) { ok = false; printf("  FAIL: %s\n", msg); } };

        // (A) Uniform visits, tau=1, eps=0 -> proportional == uniform; u2 picks the bucket.
        std::vector<size_t> uni = {1,1,1,1};
        check(sampleRootIndex(uni, 1.0, 0.0, 0.5, 0.00) == 0, "uniform u2=0.00 -> idx0");
        check(sampleRootIndex(uni, 1.0, 0.0, 0.5, 0.99) == 3, "uniform u2=0.99 -> idx3");

        // (B) tau->0 => argmax regardless of u2 (eps=0).
        std::vector<size_t> skew = {10,1,1};
        check(sampleRootIndex(skew, 1e-9, 0.0, 0.5, 0.99) == 0, "tau~0 -> argmax idx0");

        // (C) eps=1, u1=0 forces uniform branch over eligible.
        check(sampleRootIndex(skew, 1.0, 1.0, 0.0, 0.99) == 2, "eps=1 uniform u2=0.99 -> idx2");

        // (D) visits {4,1}, tau=1, eps=0 => p0=0.8 cut at u2=0.8.
        std::vector<size_t> v41 = {4,1};
        check(sampleRootIndex(v41, 1.0, 0.0, 0.5, 0.79) == 0, "v41 u2=0.79 -> idx0");
        check(sampleRootIndex(v41, 1.0, 0.0, 0.5, 0.81) == 1, "v41 u2=0.81 -> idx1");

        // (E) zero-visit candidates are ineligible.
        std::vector<size_t> z = {0, 5, 0};
        check(sampleRootIndex(z, 1.0, 0.0, 0.5, 0.50) == 1, "only idx1 eligible");

        printf("--test-sampler: %s\n", ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }
```
Add `#include "MoveSampler.h"` to `source/standalone/main.cpp`.

- [ ] **Step 5: Build and run.**
```bash
cd c:/libraries/PrismataAI-dave-master/bin && ./PrismataAI.exe --test-sampler
```
Expected: `--test-sampler: PASS`, exit 0. (If `MoveSampler.cpp` was not added to the vcxproj, the link fails — add it and rebuild.)

- [ ] **Step 6: Commit.**
```bash
cd c:/libraries/PrismataAI-dave-master
git add source/ai/MoveSampler.h source/ai/MoveSampler.cpp source/standalone/main.cpp visualstudio/Prismata_AI.vcxproj
git commit -m "feat(ai): pure temperature+epsilon root move sampler with unit-test hook"
```

---

## Task 3: Wire the sampler into UCTSearch (self-play-only; argmax preserved for eval) (Prereq §10.2)

**Repo:** `PrismataAI-dave-master`. **Files:**
- Modify: `source/ai/UCTSearchParameters.hpp` (new params + accessors)
- Modify: `source/ai/UCTSearch.cpp` (root selection branch)
- Modify: `source/ai/AIParameters.cpp` (parse optional config fields)

**Why:** The sampler must run **only** during self-play and **only** during the `τ=1` opening (first `K` plies), drawing from the seedable RNG; eval/deploy keep argmax. Root selection happens in `UCTSearch::getBestRootNode()` (lines 77–90), called once after the search loop (`doSearch` line 71).

- [ ] **Step 1: Add params + accessors.**

In `source/ai/UCTSearchParameters.hpp`, after `bool _usePUCT = false;` (line ~32) add:
```cpp
    bool            _selfPlaySampling   = false;   // self-play-only temperature/epsilon root sampling
    double          _temperatureTau     = 1.0;     // visits^(1/tau)
    size_t          _temperatureK       = 6;       // tau=1 for plies < K, then argmax
    double          _epsilonUniform     = 0.25;    // epsilon-uniform mix over root candidates
```
After the `usePUCT()` accessor (line ~57) add getters + setters:
```cpp
    bool           selfPlaySampling()                              const   { return _selfPlaySampling; }
    const double & temperatureTau()                                const   { return _temperatureTau; }
    const size_t & temperatureK()                                  const   { return _temperatureK; }
    const double & epsilonUniform()                                const   { return _epsilonUniform; }
    void setSelfPlaySampling(bool b)                                       { _selfPlaySampling = b; }
    void setTemperatureTau(double t)                                       { _temperatureTau = t; }
    void setTemperatureK(size_t k)                                         { _temperatureK = k; }
    void setEpsilonUniform(double e)                                       { _epsilonUniform = e; }
```
(Match the file's existing accessor style; if setters are declared elsewhere, follow that pattern instead.)

- [ ] **Step 2: Branch root selection in UCTSearch.cpp.**

Add `#include "MoveSampler.h"` and `#include "Random.h"` at the top of `source/ai/UCTSearch.cpp`. Replace `getBestRootNode()` (lines 77–90) with:
```cpp
UCTNode * UCTSearch::getBestRootNode()
{
    // Self-play-only: sample the root move during the tau=1 opening (first K plies).
    if (_params.selfPlaySampling()
        && _rootNode.getState().getTurnNumber() < _params.temperatureK()
        && _rootNode.numChildren() > 0)
    {
        std::vector<size_t> visits(_rootNode.numChildren());
        for (size_t c = 0; c < _rootNode.numChildren(); ++c)
        {
            visits[c] = _rootNode.getChild(c).numVisits();
        }
        const double u1 = Random::Real01();
        const double u2 = Random::Real01();
        const size_t idx = MoveSampler::sampleRootIndex(
            visits, _params.temperatureTau(), _params.epsilonUniform(), u1, u2);
        return &_rootNode.getChild(idx);
    }

    // Default (eval/deploy and late-game self-play): argmax.
    UCTNode * bestNode = NULL;
    if (_params.rootMoveSelectionMethod() == UCTMoveSelect::HighestValue)
    {
        bestNode = &_rootNode.bestUCTValueChild(true, _params);
    }
    else if (_params.rootMoveSelectionMethod() == UCTMoveSelect::MostVisited)
    {
        bestNode = &_rootNode.mostVisitedChild();
    }
    return bestNode;
}
```
(`getChild(size_t)`, `numChildren()`, `numVisits()`, and `getState().getTurnNumber()` all exist — `getState()`/`getTurnNumber()` are used in `traverse()` and `NeuralNet::dumpFeaturesJSON`.)

> **Design note (spec §3, deliberate):** this sampler does **not** add explicit forced-`≥1`-visit traversals. The spec chose to rely on **`N` ≫ root branching factor** (so incremental expansion already gives every root candidate ≥1 visit) plus the **ε-uniform mix** as the diversity lever ("the ε-uniform mix (no extra traversals) is the real diversity lever, not 'forcing' visits" — §3 MaxChildren note). The sampler therefore samples only over visited (eligible) candidates, and ε-uniform spreads mass across all generated root children. The guarantee that this holds is enforced in **Task 13's non-degeneracy check**, which rejects any `N` not comfortably above the branching factor (≤30 for IG-optional) and any `N` whose root visit-entropy falls below the floor. Do not add explicit forced-visit logic — it would burn budget and collapse depth at small `N`, which is exactly what calibration prevents.

- [ ] **Step 3: Parse the optional config fields.**

In `source/ai/AIParameters.cpp`, in the `Player_UCT` block, after the `UCTConstant` parse (line ~780) add:
```cpp
        if (args.HasMember("SelfPlaySampling") && args["SelfPlaySampling"].IsBool())
            params.setSelfPlaySampling(args["SelfPlaySampling"].GetBool());
        if (args.HasMember("TemperatureTau") && args["TemperatureTau"].IsDouble())
            params.setTemperatureTau(args["TemperatureTau"].GetDouble());
        if (args.HasMember("TemperatureK") && args["TemperatureK"].IsInt())
            params.setTemperatureK((size_t)args["TemperatureK"].GetInt());
        if (args.HasMember("EpsilonUniform") && args["EpsilonUniform"].IsDouble())
            params.setEpsilonUniform(args["EpsilonUniform"].GetDouble());
```

- [ ] **Step 4: Build (verify it compiles, eval path unchanged).**

Build both targets. Then confirm the **argmax path is unchanged** for an eval player (sampler off): run an existing tiny self-play block, e.g. flip `AB_5var_Smoke` (line 266) to `"run":true`, run `Prismata_Testing.exe`, confirm it completes 2 rounds without crashing, flip back. (No behavior change expected: no player sets `SelfPlaySampling` yet.)

- [ ] **Step 5: Commit.**
```bash
cd c:/libraries/PrismataAI-dave-master
git add source/ai/UCTSearchParameters.hpp source/ai/UCTSearch.cpp source/ai/AIParameters.cpp
git commit -m "feat(ai): self-play-only temperature+epsilon root sampling in UCTSearch (argmax preserved for eval)"
```

---

## Task 4: `RL_SelfPlay` player config — fixed sims + sampler flags (Prereq §10.3)

**Repo:** `PrismataAI-dave-master`. **File:** `bin/asset/config/config.txt`.

**Why:** Spec §3 / §10.3 — a clone of `DSNN_Mixed35_5var` with `MaxTraversals = N` (`TimeLimit` off), temperature/ε flags, on the 5-variant + OB-on iterator. `searchShouldStop()` skips the time check when `timeLimit()==0`, so `"TimeLimit":0` gives pure fixed-sims. `N` is a **placeholder** until Task 14 calibrates it; start at 512.

- [ ] **Step 1: Add the `RL_SelfPlay` player.**

After `LiveHardestAIUCT` (line ~230) in the players block, add:
```json
    "RL_SelfPlay" :         { "type":"Player_UCT", "TimeLimit":0, "MaxChildren":40, "MaxTraversals":512, "RootMoveIterator":"HardIterator_5var_Root", "MoveIterator":"HardIterator_5var", "Eval":"NeuralNet", "WeightsFile":"neural_weights_mixed_35prop.bin", "UCTConstant":0.3, "SelfPlaySampling":true, "TemperatureTau":1.0, "TemperatureK":6, "EpsilonUniform":0.25 },
    "RL_Eval" :             { "type":"Player_UCT", "TimeLimit":0, "MaxChildren":40, "MaxTraversals":512, "RootMoveIterator":"HardIterator_5var_Root", "MoveIterator":"HardIterator_5var", "Eval":"NeuralNet", "WeightsFile":"neural_weights_mixed_35prop.bin", "UCTConstant":0.3 },
```
`RL_Eval` is the **argmax twin** (no sampler) used for evaluation at the same `N`. Both initially point at the production 35-prop weights (the RL init); Task 13 repoints them at the IG-optional iterator and Task 5's loop swaps `WeightsFile` per iteration.

- [ ] **Step 2: Verify both players parse and the sampler is active only for `RL_SelfPlay`.**

Add a smoke block:
```json
    {"run":false, "type":"Tournament", "name":"RL_SelfPlay_Smoke", "rounds":2, "Seed":101, "UpdateIntervalSec":5, "Threads":1, "RandomCards":8, "saveReplays":"asset/replays/rl_smoke", "players":[{"name":"RL_SelfPlay","group":1},{"name":"RL_SelfPlay","group":1}]},
```
Flip `"run":true`, run `Prismata_Testing.exe` from `bin/`, confirm 2 rounds complete and `bin/asset/replays/rl_smoke/` contains replay JSON files. Flip back.

Determinism sanity: because the sampler draws from the seeded stream at `Threads:1`, two runs with `Seed:101` must produce identical games — re-run and diff the printed Turns/Wins (same check as Task 1 Step 6).

- [ ] **Step 3: Commit.**
```bash
cd c:/libraries/PrismataAI-dave-master
git add bin/asset/config/config.txt
git commit -m "feat(ai): RL_SelfPlay (fixed-sims + sampler) and RL_Eval (argmax twin) players"
```

---

## Task 5: C++ self-play V2 training exporter (Prereq §10.4)

**Repos:** `PrismataAI-dave-master` (exporter) + `PrismataAI` (vectorize + parity test). **Files:**
- Create: `source/testing/SelfPlayV2Exporter.h`, `source/testing/SelfPlayV2Exporter.cpp`
- Modify: `source/testing/TournamentGame.cpp`, `TournamentGame.h` (turn-start capture + winner backfill)
- Modify: `source/testing/Tournament.cpp`, `Tournament.h` (parse `exportTrainingV2` field, pass to games)
- Modify: `visualstudio/Prismata_Testing.vcxproj` (add the new `.cpp`)
- Create: `training/tests/test_selfplay_export_parity.py`
- Reuse: `training/vectorize_v2.py`

**Why (architecture decision — full C++ export, user-selected):** The C++ engine already computes the exact `schema_v2` features for inference (`NeuralNet::dumpFeaturesJSON`, parity-verified to 1.33e-6 vs PyTorch). Emitting self-play training records from the **same GameState** the net evaluates gives train/inference feature parity **by construction**, and eliminates the JS `extractTrainingExampleV2` as a second, drift-prone feature implementation (it has already caused three silent skews: card_set semantics, turn_number base, attack stripping). It also removes the replay-format mismatch — dave's `ReplaySerializer` emits the **PixiJS viewer format** (`states/actions/turnBoundaries/winner`, no replayable commandList), unsuitable for re-simulation — and the two-engine drift. The exporter emits the **raw V2 JSONL** record (so `vectorize_v2.py`/`schema_v2.json` remain the single normalization source), and a one-time parity test (Step 6) asserts the C++ records match the JS extractor, keeping self-play consistent with the JS-built human rehearsal corpus.

**The exact record contract** (from `js_engine/training_example.js::extractTrainingExampleV2` — the single source of truth; one JSON object per player-turn, captured at the turn-start snapshot):
```json
{"schema_version":"v2","ply_index":<int>,"card_set":[<advanced-unit UINames>],
 "instances":[<one per ALIVE table instance; fields per state_adapter._instToRichUnit>],
 "supply":{"<UIName>":[whiteSupply,blackSupply,inSet], ...},
 "p0_resources":{...},"p1_resources":{...},"p0_attack":<int>,"p1_attack":<int>,
 "turn_number":<numTurns>,"active_player":<0|1>,
 "outcome_p0":<1.0|0.5|0.0>,"total_plies":<int>}
```
`outcome_p0`/`total_plies` are game-level (backfilled at game end). The per-state core mirrors `extractTrainingExampleV2`'s return value field-for-field.

- [ ] **Step 1: Write the V2 record builder (model it on `serializeState`).**

`source/testing/SelfPlayV2Exporter.h` — a class that accumulates per-game records, backfills the outcome, and writes JSONL:
```cpp
#pragma once
#include "Prismata.h"
#include <string>
#include <vector>

namespace Prismata
{
class SelfPlayV2Exporter
{
    std::string              _outDir;
    std::vector<std::string> _records;   // one JSON line per captured turn-start (without outcome)
public:
    explicit SelfPlayV2Exporter(const std::string & outDir) : _outDir(outDir) {}
    // Build + stash one raw V2 record (without outcome_p0/total_plies) from a turn-start state.
    void capture(const GameState & state, const std::vector<std::string> & cardSet);
    // Backfill outcome_p0 (P0 win=1.0 / draw=0.5 / P1 win=0.0) + total_plies, then write <outDir>/selfplay_<gameId>.jsonl
    void finalize(PlayerID winner, int totalPlies, int gameId);
};
}
```
`source/testing/SelfPlayV2Exporter.cpp` — `capture()` builds the record using the **same GameState accessors as `ReplaySerializer::serializeState`** (`ReplaySerializer.cpp:318`): resources via `state.getResources(p).getString()` (then split to the `p0_resources`/`p0_attack` shape `manaToResources` produces), `turn_number = state.getTurnNumber()`, `active_player = state.getActivePlayer()`, alive instances via `state.getCardIDs(p)` (skip non-alive, matching `extractTrainingExampleV2` line 34), per-instance fields from `currentHealth/getConstructionTime/canBlock/getCurrentLifespan/currentChill/getCurrentCharges/getType()`, supply via `getCardBuyableByIndex`. **Emit each instance with the field names `state_adapter._instToRichUnit` outputs** (owner, is_constructing, turns_until_ready, is_blocking, ability_used, current_hp, hp_fraction, is_frozen, lifespan_remaining, stamina_remaining) — read `js_engine/state_adapter.js::_instToRichUnit` to pin the exact names/derivations; the Step 6 parity test gates this. `card_set` = advanced (non-base) unit UINames. Serialize with rapidjson (as `ReplaySerializer` does).

- [ ] **Step 2: Hook capture + winner backfill in `TournamentGame`.**

In `TournamentGame.h/.cpp`, add an optional `SelfPlayV2Exporter` member set when an export dir is configured. Capture a record at each **turn-start** — the same snapshot point `beginTurnHistory` uses (the mixed Defense/Action leaf the value net is queried on; `beginTurn()` runs during Swoosh per GameState.cpp). Concretely, capture in the game loop right after a player's `MOVE_COMMIT` triggers the next player's turn-start, before that player acts. At game end call `exporter.finalize(state.winner(), state.getTurnNumber(), gameId)`. On each captured record also stamp four cheap booleans/indices the search has in-process (so action-coverage and the §9 triage need no replay parsing):
- `ig_legal` — was firing Infusion Grid (`Hotel`) legal at this turn-start (red legal + a `Hotel` instance present);
- `ig_fired` — did the move actually played (the τ-sampled move in self-play) fire `Hotel`;
- `sampled_idx` / `argmax_idx` — the chosen vs argmax root child indices (add `Player_UCT::lastChosenIndex()`/`lastArgmaxIndex()` accessors populated in `doSearch`), satisfying spec §10.4's "record both" and §9 triage item 2.

- [ ] **Step 3: Wire the `exportTrainingV2` Tournament field.**

In `Tournament.cpp` constructor, read optional `"exportTrainingV2"` into `std::string _exportTrainingV2Dir;` (declare in `Tournament.h`, mirror the `saveReplays` handling at lines 33–36). In `run()`, next to the `setReplaySaveDir` calls (lines 114–118), call `g1.setExportTrainingV2(_exportTrainingV2Dir, ...)` / `g2....` when non-empty. Register `SelfPlayV2Exporter.cpp` in `visualstudio/Prismata_Testing.vcxproj`.

- [ ] **Step 4: Build + run rl_smoke with export, inspect JSONL.**

Add `"exportTrainingV2":"asset/training/rl_smoke_v2"` to the `RL_SelfPlay_Smoke` block (Task 4). Build `Prismata_Testing`, run from `bin/`, then:
```bash
ls c:/libraries/PrismataAI-dave-master/bin/asset/training/rl_smoke_v2/
head -1 c:/libraries/PrismataAI-dave-master/bin/asset/training/rl_smoke_v2/selfplay_0.jsonl \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const r=JSON.parse(s);console.log('schema',r.schema_version,'instances',r.instances.length,'supply_keys',Object.keys(r.supply).length,'outcome_p0',r.outcome_p0,'turn',r.turn_number,'active',r.active_player);})"
```
Expected: `schema v2 instances <N> supply_keys <K> outcome_p0 <0|0.5|1> turn <int> active <0|1>`.

- [ ] **Step 5: Vectorize to H5; confirm shapes + P0 win-frac.**
```bash
cd c:/libraries/PrismataAI/training
cat c:/libraries/PrismataAI-dave-master/bin/asset/training/rl_smoke_v2/*.jsonl > /tmp/rl_smoke_v2.jsonl
python vectorize_v2.py --input /tmp/rl_smoke_v2.jsonl --output /tmp/rl_smoke_v2.h5 --schema training/schema_v2.json
python -c "import h5py; f=h5py.File('/tmp/rl_smoke_v2.h5','r'); print({k:f[k].shape for k in ['instance_features','instance_unit_ids','supply','globals','label_A']})"
python -c "import h5py,numpy as np; f=h5py.File('/tmp/rl_smoke_v2.h5','r'); l=f['label_A'][:]; print('P0 win frac', float((l==1.0).mean()), 'draws', float((l==0.5).mean()))"
```
Expected: `instance_features (N,200,10)`, `supply (N,116,3)`, `globals (N,14)`, `label_A (N,)`. (`vectorize_v2.py` ingests the C++ JSONL unchanged — same schema as the JS extractor.)

- [ ] **Step 6: C++↔JS extractor parity test (the consistency gate).**

`training/tests/test_selfplay_export_parity.py`: take a handful of states for which BOTH a C++ exporter record and a JS `extractTrainingExampleV2` record exist (drive the same self-play game once with export on, and once through `matchup_clean.js` on the identical seeded card set), and assert the two V2 records are equal field-for-field (instances sorted by `instId`, supply dict, resources, attack, turn_number, active_player) within integer equality. A mismatch is a real skew between self-play and the human rehearsal corpus — fix the C++ field mapping (not the test). Run: `cd training && python -m pytest tests/test_selfplay_export_parity.py -v`.
> If producing a perfectly-aligned shared state is awkward, the minimum viable parity check is structural: assert the C++ record has the exact same keys and instance-field names as `extractTrainingExampleV2`'s output on a hand-built state, and that `vectorize_v2.py` produces identical `instance_features`/`supply`/`globals` tensors from a C++ record and a JS record of the same position.

- [ ] **Step 7: Commit (engine + test).**
```bash
cd c:/libraries/PrismataAI-dave-master
git add source/testing/SelfPlayV2Exporter.h source/testing/SelfPlayV2Exporter.cpp \
        source/testing/TournamentGame.cpp source/testing/TournamentGame.h \
        source/testing/Tournament.cpp source/testing/Tournament.h visualstudio/Prismata_Testing.vcxproj
git commit -m "feat(testing): C++ self-play V2 training exporter (inference-parity features)"
cd c:/libraries/PrismataAI && git add training/tests/test_selfplay_export_parity.py
git commit -m "test(train): C++ exporter <-> JS extractor V2 parity"
```

---

## Task 6: Replay buffer + human-only rehearsal + colour-balance + label tests (Prereq §10.5)

**Repo:** `PrismataAI/`. **Files:**
- Create: `training/rl_data.py`, `training/tests/test_labels.py`, `training/tests/test_rl_data.py`
- Modify: `training/train.py` (argparse + loader wiring + fine-tune)

**Why:** Spec §4 / §10.5 — sliding replay buffer (last `W` iteration H5 files), human-only rehearsal at a named fraction with decay (no MB-fleet in value targets), colour-balanced batches, few-epoch low-LR SWA fine-tune. Label correctness is a known hazard (historical P0/P1 inversion) → label unit tests. `H5DatasetV2` has no per-sample weighting today; `train_epoch` already applies weighted BCE when `sample_weight` is passed (it currently forces `ones` for deepsets).

- [ ] **Step 1: Write the label unit tests (failing).**

`training/tests/test_labels.py`:
```python
"""Label-correctness tests for the V2 pipeline. Run: cd training && python -m pytest tests/test_labels.py -v"""
import os, sys, math
import numpy as np
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)
from vectorize_v2 import compute_labels   # existing function

class TestOutcomeScale:
    def test_win_draw_loss_map_to_1_half_0(self):
        # Strategy A is the raw outcome_p0 in [0,1].
        assert compute_labels(1.0, 10, 30, 1800, 1800)[0] == 1.0   # P0 win
        assert compute_labels(0.5, 10, 30, 1800, 1800)[0] == 0.5   # draw
        assert compute_labels(0.0, 10, 30, 1800, 1800)[0] == 0.0   # P0 loss

    def test_labels_in_unit_interval(self):
        for o in (0.0, 0.5, 1.0):
            a, bw, c, d = compute_labels(o, 5, 40, 1500, 2000)
            for v in (a, c, d):
                assert 0.0 <= v <= 1.0
            assert 0.0 <= bw <= 1.0

class TestInversion:
    def test_opposite_outcome_inverts(self):
        # The P0/P1 inversion bug would make a P0-win and a P0-loss collapse to the same label.
        assert compute_labels(1.0, 20, 40, 1800, 1800)[0] != compute_labels(0.0, 20, 40, 1800, 1800)[0]

class TestColourBalanceHelper:
    def test_balance_weights_equalise_active_player(self):
        from rl_data import colour_balance_weights
        ap = np.array([0,0,0,1])          # 3 P0-to-move, 1 P1-to-move
        w = colour_balance_weights(ap)
        # expected total weight per colour equal
        assert abs(w[ap==0].sum() - w[ap==1].sum()) < 1e-6
```

- [ ] **Step 2: Run — verify failure (no `rl_data` yet).**
```bash
cd c:/libraries/PrismataAI/training && python -m pytest tests/test_labels.py -v
```
Expected: import error / fail on `from rl_data import colour_balance_weights`.

- [ ] **Step 3: Write `rl_data.py`.**

`training/rl_data.py`:
```python
"""RL data assembly: sliding replay buffer (last W self-play H5) + human-only rehearsal at a
named fraction + colour balancing. Operates on schema_v2 H5DatasetV2 datasets from train.py."""
import numpy as np
import torch
from torch.utils.data import ConcatDataset, WeightedRandomSampler, DataLoader

ACTIVE_PLAYER_GLOBAL_IDX = 13   # globals[...,13] = active_player (schema_v2.json global_features)

def colour_balance_weights(active_player):
    """Per-sample weights so total weight of active_player==0 equals that of ==1.
    active_player: int array in {0,1}. Returns float array summing to len(active_player)."""
    ap = np.asarray(active_player).astype(np.int64)
    w = np.ones(len(ap), dtype=np.float64)
    for c in (0, 1):
        n = int((ap == c).sum())
        if n > 0:
            w[ap == c] = 0.5 * len(ap) / n
    return w

def _active_player_of(ds):
    """Extract per-sample active_player (the colour-to-move) from a V2 dataset's globals."""
    g = ds.globals if hasattr(ds, "globals") else None
    if g is None:
        return np.zeros(len(ds), dtype=np.int64)
    return (np.asarray(g[:, ACTIVE_PLAYER_GLOBAL_IDX]) > 0.5).astype(np.int64)

def build_rl_sampler(selfplay_datasets, human_dataset, human_fraction, batch_size,
                     num_workers=2):
    """Combine the last-W self-play datasets + human rehearsal into one weighted-sampling loader.
       - Expected human share per draw == human_fraction.
       - Within each source, colours (active_player) are balanced.
    Returns (loader, combined_dataset)."""
    parts = list(selfplay_datasets) + ([human_dataset] if human_dataset is not None else [])
    combined = ConcatDataset(parts)

    weights = np.empty(len(combined), dtype=np.float64)
    offset = 0
    sp_total = sum(len(d) for d in selfplay_datasets) or 1
    hu_total = len(human_dataset) if human_dataset is not None else 0
    for d in selfplay_datasets:
        n = len(d)
        cb = colour_balance_weights(_active_player_of(d))
        # self-play mass = (1 - human_fraction), split across all self-play samples
        weights[offset:offset + n] = cb * ((1.0 - human_fraction) / sp_total)
        offset += n
    if human_dataset is not None and hu_total > 0:
        n = len(human_dataset)
        cb = colour_balance_weights(_active_player_of(human_dataset))
        weights[offset:offset + n] = cb * (human_fraction / hu_total)
        offset += n

    sampler = WeightedRandomSampler(torch.as_tensor(weights, dtype=torch.double),
                                    num_samples=len(combined), replacement=True)
    loader = DataLoader(combined, batch_size=batch_size, sampler=sampler,
                        num_workers=num_workers, drop_last=True)
    return loader, combined

def rehearsal_fraction_for_iter(iteration, start=0.30, floor=0.10, decay_per_iter=0.07):
    """Named-fraction schedule: ~30% human at iter-1, decaying to ~10-15% by iter-3."""
    return max(floor, start - decay_per_iter * max(0, iteration - 1))

def select_replay_window(selfplay_h5_paths, window):
    """Keep only the last `window` per-iteration self-play H5 files (sliding buffer)."""
    return list(selfplay_h5_paths)[-window:] if window and window > 0 else list(selfplay_h5_paths)
```

- [ ] **Step 4: Run tests — verify PASS.**
```bash
cd c:/libraries/PrismataAI/training && python -m pytest tests/test_labels.py -v
```
Expected: all PASS.

- [ ] **Step 5: Write `tests/test_rl_data.py` (buffer + fraction).**

`training/tests/test_rl_data.py`:
```python
import os, sys, numpy as np
TRAINING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TRAINING_DIR)
from rl_data import select_replay_window, rehearsal_fraction_for_iter, colour_balance_weights

def test_window_keeps_last_w():
    paths = ['i1.h5','i2.h5','i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 3) == ['i3.h5','i4.h5','i5.h5']
    assert select_replay_window(paths, 0) == paths

def test_fraction_decays():
    assert abs(rehearsal_fraction_for_iter(1) - 0.30) < 1e-9
    assert rehearsal_fraction_for_iter(3) < rehearsal_fraction_for_iter(1)
    assert rehearsal_fraction_for_iter(99) == 0.10   # floored

def test_colour_weights_nonnegative_and_balanced():
    ap = np.array([0,1,1,1,0,0])
    w = colour_balance_weights(ap)
    assert (w >= 0).all()
    assert abs(w[ap==0].sum() - w[ap==1].sum()) < 1e-6
```
Run: `cd training && python -m pytest tests/test_rl_data.py -v` → PASS.

- [ ] **Step 6: Wire `--rl-mode` into `train.py`.**

In `train.py` argparse (after `--stop-after-epoch`, line ~922) add:
```python
    # RL fine-tuning
    parser.add_argument("--rl-mode", action="store_true",
                        help="RL fine-tune: replay buffer + human rehearsal + colour balance")
    parser.add_argument("--selfplay-files", nargs="*", default=[],
                        help="Per-iteration self-play V2 H5 files (newest last)")
    parser.add_argument("--human-file", type=str, default=None,
                        help="human_1800_v2 H5 for rehearsal")
    parser.add_argument("--replay-window", type=int, default=5, help="W: sliding buffer size")
    parser.add_argument("--rl-iteration", type=int, default=1, help="iteration index (sets rehearsal fraction)")
    parser.add_argument("--rehearsal-fraction", type=float, default=None,
                        help="override the scheduled human fraction")
    parser.add_argument("--swa-start-epoch", type=int, default=None,
                        help="SWA start epoch (default 80%% of --epochs)")
```
In the loader-construction region (where `H5DatasetV2`/`train_loader` are built for `--model deepsets`, ~line 1046–1084), branch when `args.rl_mode`. `H5DatasetV2` is already defined in `train.py`; reference it directly:
```python
    if args.rl_mode:
        from rl_data import select_replay_window, rehearsal_fraction_for_iter, build_rl_sampler
        sp_paths = select_replay_window(args.selfplay_files, args.replay_window)
        sp_datasets = [H5DatasetV2(p, label_strategy=args.label_strategy) for p in sp_paths]
        human_ds = (H5DatasetV2(args.human_file, label_strategy=args.label_strategy)
                    if args.human_file else None)
        frac = (args.rehearsal_fraction if args.rehearsal_fraction is not None
                else rehearsal_fraction_for_iter(args.rl_iteration))
        train_loader, train_ds = build_rl_sampler(sp_datasets, human_ds, frac,
                                                  args.batch_size, num_workers=args.num_workers)
        print(f"[RL] window={len(sp_datasets)} files, human_fraction={frac:.2f}, "
              f"combined={len(train_ds):,} samples")
```
Set SWA start from `args.swa_start_epoch` if provided (replace `swa_start_epoch = max(1, int(args.epochs * 0.8))` with `swa_start_epoch = args.swa_start_epoch or max(1, int(args.epochs * 0.8))`) so a 6-epoch fine-tune starts SWA at epoch 3.

> **Non-flat collection-LR (spec §4 / S5):** SWA's smoothing only helps if the collection LR is **not flat**. The existing `train.py` already does this — the pre-SWA phase steps a per-batch cosine `scheduler` (recon: "smooth cosine decay") and the SWA phase uses `SWALR(optimizer, swa_lr=args.lr*0.1)` which anneals down. For the short RL fine-tune, keep the warm-start LR on `CosineAnnealingLR` (peak `--lr 1e-5` → `~1e-6` over epochs 1–3) and let SWALR collect over epochs 3–6 — confirm both schedulers are active (not a constant LR) and record the chosen schedule in `eval/rl_campaign.md`.

- [ ] **Step 7: Smoke the fine-tune path.**

Using the `rl_smoke_v2.h5` from Task 5 as both self-play and (stand-in) human file:
```bash
cd c:/libraries/PrismataAI/training
python train.py --model deepsets --property-table training/property_table.json \
  --train-file /tmp/rl_smoke_v2.h5 --val-file /tmp/rl_smoke_v2.h5 \
  --rl-mode --selfplay-files /tmp/rl_smoke_v2.h5 --human-file /tmp/rl_smoke_v2.h5 \
  --replay-window 5 --rl-iteration 1 --epochs 2 --swa-start-epoch 1 \
  --batch-size 64 --lr 1e-5 --device cpu --output-dir /tmp/rl_smoke_model
```
Expected: runs 2 epochs without error, prints `[RL] window=1 files, human_fraction=0.30`, writes a checkpoint. (`--lr 1e-5`, 2 epochs = the low-LR few-epoch regime.)

- [ ] **Step 8: Commit.**
```bash
cd c:/libraries/PrismataAI
git add training/rl_data.py training/tests/test_labels.py training/tests/test_rl_data.py training/train.py
git commit -m "feat(train): RL replay buffer + human-only rehearsal + colour balance + label tests"
```

---

## Task 7: Eval harness — 3 anchors, Wilson CIs, sequential testing, manifest + dashboard (Prereq §10.6)

**Repo:** `PrismataAI/`. **Files:**
- Create: `eval/wilson.py`, `eval/tests/test_wilson.py`, `eval/run_eval.py`

**Why:** Spec §5 / §12 — primary signal is win-rate vs three anchors (wide-untrained iter-0, `DSNN_Mixed35_5var`, `STEAMAI/.ORIG`), with Wilson 95% CIs, draw=0.5 in win-rate math, paired card sets both colours, sequential testing (128→256→512→inconclusive), per-iteration manifest + dashboard, contamination checks. **One eval path per anchor:** anchors 1–2 via the C++ tournament (`Prismata_Testing` Benchmarks, paired colour-swap), anchor 3 (`STEAMAI`) via `matchup_clean.js` against `PrismataAI.exe.ORIG`.

- [ ] **Step 1: Wilson CI + win-rate math (failing test first).**

`eval/tests/test_wilson.py`:
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wilson import win_rate, wilson_ci, decisive

def test_win_rate_counts_draw_half():
    assert win_rate(wins=60, draws=20, n=100) == 0.70   # (60 + 0.5*20)/100

def test_wilson_brackets_point():
    lo, hi = wilson_ci(0.70, 100)
    assert lo < 0.70 < hi and 0.0 <= lo and hi <= 1.0

def test_decisive_when_ci_excludes_half():
    assert decisive(wins=400, draws=0, n=512) is True     # ~78% over 0.5
    assert decisive(wins=260, draws=0, n=512) is False    # ~51%, CI straddles 0.5
```

- [ ] **Step 2: Run — fails (no `wilson.py`).**
```bash
cd c:/libraries/PrismataAI/eval && python -m pytest tests/test_wilson.py -v
```

- [ ] **Step 3: Implement `eval/wilson.py`.**
```python
"""Win-rate (draw=0.5) and Wilson score interval (95%), plus a decisive-vs-0.5 test."""
import math
Z95 = 1.959963984540054

def win_rate(wins, draws, n):
    if n <= 0: return 0.0
    return (wins + 0.5 * draws) / n

def wilson_ci(p, n, z=Z95):
    if n <= 0: return (0.0, 1.0)
    denom = 1.0 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = (z / denom) * math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (max(0.0, center - half), min(1.0, center + half))

def decisive(wins, draws, n, boundary=0.5):
    p = win_rate(wins, draws, n)
    lo, hi = wilson_ci(p, n)
    return lo > boundary or hi < boundary
```
Run the test → PASS.

- [ ] **Step 4: Implement `eval/run_eval.py` (orchestrator: sequential testing + manifest + dashboard).**

`eval/run_eval.py` — drives the C++ tournament for anchors 1–2 and `matchup_clean.js` for anchor 3, escalates 128→256→512, computes Wilson CIs, writes a per-iteration manifest + a dashboard line:
```python
"""Per-iteration RL eval. Sequential testing (128->256->512), Wilson CIs, manifest + dashboard.

Anchors (one path each):
  1. iter0  : wide-untrained iter-0 weights on the IG-optional config (C++ tournament)
  2. narrow : DSNN_Mixed35_5var (C++ tournament)
  3. steam  : STEAMAI / PrismataAI.exe.ORIG (matchup_clean.js)

Usage:
  python run_eval.py --iteration 1 --weights neural_weights_rl_iter1.bin \
      --dave-bin c:/libraries/PrismataAI-dave-master/bin \
      --orig-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe.ORIG \
      --pools forced general --out eval/manifests
"""
import argparse, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wilson import win_rate, wilson_ci, decisive

SEQ = [128, 256, 512]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def run_cpp_tournament(dave_bin, block_name):
    """Flip the named block run:true in config.txt, run Prismata_Testing, parse (wins,draws,n).
    The caller pre-writes the block. Returns dict per group."""
    # Run the testing exe from bin/ (it executes every run:true Benchmarks block).
    p = subprocess.run([os.path.join(dave_bin, "Prismata_Testing.exe")],
                       cwd=dave_bin, capture_output=True, text=True, timeout=36000)
    return parse_tournament_stdout(p.stdout + p.stderr, block_name)

def parse_tournament_stdout(text, block_name):
    """Extract per-player Wins/Draws/Games from the Overall Statistics table the tournament prints.
    Returns {player_name: {'wins':int,'draws':int,'games':int}}. Adapt the regex to the exact
    stdout/HTML the runner emits (Tournament.cpp printResults)."""
    import re
    out = {}
    # Lines look like: <player> <score> <games> <wins> <loss> <draw> ...
    for m in re.finditer(r"^\s*(\S+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text, re.M):
        name, _score, games, wins, _loss, draws = m.groups()
        out[name] = {"wins": int(wins), "draws": int(draws), "games": int(games)}
    return out

def run_steam(dave_bin, orig_exe, candidate_weights, games, pool_args):
    """matchup_clean.js: RL candidate (DaveAI w/ candidate weights) vs STEAMAI/.ORIG.
    Returns (wins, draws, n) for the candidate. Parse the [Pair] TALLY from stderr."""
    cmd = ["node", "c:/libraries/PrismataAI/js_engine/matchup_clean.js",
           "--games", str(games), "--parallel", "4", "--player-switch", "--think-time", "7000",
           "--player", "SteamAI", "--steam-difficulty", "HardestAI",
           "--dave-exe", orig_exe] + pool_args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=36000)
    return parse_matchup_tally(p.stderr)

def parse_matchup_tally(text):
    import re
    w = d = n = 0
    mw = re.search(r"White:\s+(\d+)", text); mb = re.search(r"Black:\s+(\d+)", text)
    md = re.search(r"Draws:\s+(\d+)", text); mg = re.search(r"Games:\s+(\d+)", text)
    if mw and mb and md and mg:
        n = int(mg.group(1)); d = int(md.group(1)); w = int(mw.group(1))  # candidate = White seat
    return w, d, n

def sequential(run_fn):
    """Escalate 128->256->512, stop when decisive; return (wins,draws,n,outcome)."""
    wins = draws = n = 0
    for target in SEQ:
        add = target - n
        w, d, _ = run_fn(add)
        wins += w; draws += d; n = target
        if decisive(wins, draws, n):
            return wins, draws, n, "decisive"
    return wins, draws, n, "inconclusive"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--weights", required=True, help="candidate .bin filename (in dave bin/asset/config)")
    ap.add_argument("--parent-weights", default=None, help="current promoted .bin (primary comparison)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--orig-exe", required=True)
    ap.add_argument("--pools", nargs="+", default=["forced", "general"])
    ap.add_argument("--out", default="eval/manifests")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    wpath = os.path.join(args.dave_bin, "asset/config", args.weights)

    # Contamination checks (spec §5).
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set — eval contamination"
    assert not os.path.exists(os.path.join(args.dave_bin, "use_dsnn.txt")), "use_dsnn.txt present"
    assert os.path.exists(args.orig_exe), "STEAMAI .ORIG missing — would diff against the DSNN swap-in"

    manifest = {
        "iteration": args.iteration,
        "candidate_weights": args.weights,
        "candidate_net_sha256": sha256(wpath),
        "parent_weights": args.parent_weights,
        "fixed_sims": True,
        "anchors": {}, "pools": {},
        # caller fills resolved-config-hash, seed range, replay window, rehearsal datasets+weights
    }
    # NOTE: the caller writes the per-anchor C++ tournament blocks (paired group1/group2, Seed,
    # forced-set pool) into config.txt before invoking, then maps run_cpp_tournament results into
    # manifest['anchors'][name] = {wins,draws,n, win_rate, ci_lo, ci_hi, outcome}.
    # STEAMAI anchor uses sequential(run_steam ...).

    path = os.path.join(args.out, f"eval_iter_{args.iteration}.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest -> {path}")

if __name__ == "__main__":
    main()
```
> The `parse_*` regexes must be matched to the **actual** `Tournament::printResults` stdout and `matchup_clean.js` `[Pair] TALLY` lines (both quoted in the recon). Verify against a real run (Step 5) and adjust the regex; do not assume.

- [ ] **Step 5: Validate parsing against a real run.**

Run the existing `AB_5var_vs_Mixed35_7s` block (set `rounds:2`, `"run":true`), capture stdout, and confirm `parse_tournament_stdout` returns sensible `{player: {wins,draws,games}}`. Run a 4-game `matchup_clean.js` SteamAI smoke and confirm `parse_matchup_tally` returns `(w,d,n)`. Fix the regexes if needed.

- [ ] **Step 6: Add the three eval tournament blocks to `config.txt`.**

For axis-1, **every eval game must force Infusion Grid into the card set** (spec §6.1 — else the per-unit signal is unmeasurable at ~7.6% by chance), AND a separate **general (random) pool** runs as the regression check. So each anchor gets a `ForcedCards:["Hotel"]` block *and* a general block (all `"run":false`, the orchestrator flips them):
```json
    {"run":false, "type":"Tournament", "name":"RL_Eval_iter0_forced",  "rounds":64, "Seed":2026, "Threads":8, "RandomCards":8, "ForcedCards":["Hotel"], "players":[{"name":"RL_Eval","group":1},{"name":"RL_Eval_iter0","group":2}]},
    {"run":false, "type":"Tournament", "name":"RL_Eval_iter0_general", "rounds":64, "Seed":2026, "Threads":8, "RandomCards":8, "players":[{"name":"RL_Eval","group":1},{"name":"RL_Eval_iter0","group":2}]},
    {"run":false, "type":"Tournament", "name":"RL_Eval_narrow_forced",  "rounds":64, "Seed":2026, "Threads":8, "RandomCards":8, "ForcedCards":["Hotel"], "players":[{"name":"RL_Eval","group":1},{"name":"DSNN_Mixed35_5var","group":2}]},
    {"run":false, "type":"Tournament", "name":"RL_Eval_narrow_general", "rounds":64, "Seed":2026, "Threads":8, "RandomCards":8, "players":[{"name":"RL_Eval","group":1},{"name":"DSNN_Mixed35_5var","group":2}]},
```
(`RL_Eval_iter0` = a copy of `RL_Eval` pinned to the pre-RL iter-0 weights file — added in Task 12/13 once the IG-optional iterator exists. `RL_Eval`'s `WeightsFile` is rewritten to the candidate `.bin` each iteration. The forced/general split feeds the go-criterion (forced) and the regression tolerance Y (general) in §12. `ForcedCards` requires Task 12 Step 3.) The `STEAMAI/.ORIG` anchor (3) runs forced + general via `matchup_clean.js` — see Task 14's driver — `matchup_clean.js`'s card-set selection forces IG by constraining the random set.

- [ ] **Step 6b: Action-coverage metrics (the IG go-signal, spec §5/§6.1).**

The headline go-signal for axis-1 is **IG fire/skip behaviour change**, not aggregate win-rate. Add `eval/action_coverage.py` that, given a directory of this-iteration self-play replays (and the tactical-suite argmax results from Task 10), computes and writes into the manifest: **IG fire rate in self-play** (fraction of IG-legal player-turns where the played move fired `Hotel`), **IG fire rate at argmax** (from `RL_Eval` on IG-legal positions), **% of positions where IG is legal**, **avg root candidates**, **root visit-entropy** (from the `visits` array added for Task 13), and **win-rate conditioned on IG availability** (forced-set games vs general). A shift in IG fire rate across iterations (toward the curated correct skip/fire) is the per-axis learning signal even when aggregate win-rate is flat.
Two stable sources (no replay-format parsing): the **C++ exporter** stamps `ig_legal` + `ig_fired` per V2 record (the exporter knows the played/sampled move — add these two booleans in Task 5 Step 2, cheap), giving the **self-play sampled** fire-rate directly from the JSONL; and **`query_move.js`** over the IG-legal battery gives the **argmax** fire-rate + root entropy from `aivisits`.
```python
"""Action-coverage metrics for the IG-optional axis -> merged into the eval manifest."""
import argparse, glob, json, os, subprocess, math

def selfplay_ig_rate(jsonl_dir):
    legal = fired = 0
    for f in glob.glob(os.path.join(jsonl_dir, "*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if r.get("ig_legal"):                 # stamped by the C++ exporter (Task 5)
                legal += 1
                if r.get("ig_fired"): fired += 1
    return {"ig_legal_turns": legal, "ig_fired": fired,
            "ig_fire_rate_selfplay": (fired / legal) if legal else None}

def argmax_ig_rate(dave_exe, weights, battery="eval/ig_battery"):
    legal = fired = 0; ents = []
    for s in glob.glob(os.path.join(battery, "*.json")):
        out = subprocess.run(["node", "c:/libraries/PrismataAI/js_engine/query_move.js",
                              "--request", s, "--player", "RL_Eval",
                              "--weights", weights, "--dave-exe", dave_exe],
                             capture_output=True, text=True, timeout=120)
        resp = json.loads(out.stdout.strip().splitlines()[-1])
        legal += 1
        if any(c.get("_type") in ("inst", "inst shift") and c.get("_id") == json.load(open(s)).get("hotel_inst_id")
               for c in resp.get("aiclicks", [])): fired += 1
        v = resp.get("aivisits", [])
        if v:
            tot = float(sum(v)); ents.append(-sum((x/tot)*math.log(x/tot) for x in v if x > 0))
    return {"ig_fire_rate_argmax": (fired / legal) if legal else None,
            "root_entropy_mean": (sum(ents)/len(ents)) if ents else None,
            "ig_legal_positions": legal}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfplay-jsonl-dir", required=True)
    ap.add_argument("--dave-exe", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    m = json.load(open(a.manifest))
    m["action_coverage"] = {**selfplay_ig_rate(a.selfplay_jsonl_dir),
                            **argmax_ig_rate(a.dave_exe, a.weights)}
    json.dump(m, open(a.manifest, "w"), indent=2)
    print("action_coverage ->", m["action_coverage"])

if __name__ == "__main__":
    main()
```
> The IG-legal/IG-fired detection reuses the exact `Hotel` `USE_ABILITY` click shape confirmed in Task 10; wire it in once that shape is known (do not guess the click `_type`/`_id` here).

- [ ] **Step 7: Cross-path sanity check (one-off).**

Run `HardestAIUCT` vs itself on **both** paths (C++ tournament and `matchup_clean.js`) at 128 games; record the win-rate delta as the documented path effect bound (spec §5). Store the number in `eval/README.md`.

- [ ] **Step 8: Commit.**
```bash
cd c:/libraries/PrismataAI
git add eval/wilson.py eval/tests/test_wilson.py eval/run_eval.py eval/README.md
git commit -m "feat(eval): 3-anchor harness — Wilson CIs, sequential testing, manifest"
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt && git commit -m "feat(config): RL eval tournament blocks (iter0 + narrow anchors)"
```

---

## Task 8: Per-iteration export-parity check (Prereq §10.6) — scale the existing harness

**Repos:** both. **Files:**
- Create: `tools/parity/dump_value_batch.py` (main repo, thin driver)
- Reuse: `tools/parity/compare_parity_35prop.py`, C++ `--dump-features`

**Why:** Spec §5 — every iteration, compare PyTorch vs C++ `.bin` value on ~1000 sampled positions; assert max |Δ| below threshold. The harness **already exists** (`tools/parity/compare_parity_35prop.py` + C++ `--dump-features`, threshold 1e-3, observed 1.33e-6) but uses **5 fixed states**. This task scales it to ~1000 positions sampled from self-play replays.

- [ ] **Step 1: Sample ~1000 states from self-play replays into state JSONs.**

Add `tools/parity/dump_value_batch.py` (main repo) that: takes ~1000 `gameState` JSONs (in the `--dump-features` input shape), runs `PrismataAI.exe --dump-features` on each against the candidate `.bin`, then invokes `compare_parity_35prop.py` over all dumps and asserts the worst |Δ| < 1e-3 (exit nonzero on fail). **Source the ~1000 states cheaply from self-play:** have the Task-5 `SelfPlayV2Exporter` optionally also write the engine's raw `state.toJSONString()` per captured turn into a sibling `parity_states/` dir (one extra line; the exact shape `--dump-features`'s `GameState(gs)` constructor consumes). The export-parity check then runs over a fixed sample of those.
```python
"""Scale the parity harness to ~1000 self-play states. Exits nonzero if worst |dval| >= 1e-3."""
import argparse, glob, json, os, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states-dir", required=True, help="dir of gameState JSONs (sp_*.json)")
    ap.add_argument("--weights", required=True, help="candidate .bin (absolute)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--parity-dir", default="c:/libraries/PrismataAI-dave-master/tools/parity")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()

    states = sorted(glob.glob(os.path.join(args.states_dir, "*.json")))[:args.limit]
    dumps = []
    for i, s in enumerate(states):
        out = os.path.join(args.parity_dir, f"out_sp_{i}.json")
        subprocess.run([os.path.join(args.dave_bin, "PrismataAI.exe"),
                        "--dump-features", s, out, args.weights],
                       cwd=args.dave_bin, check=True)
        dumps.append(out)
    # compare_parity_35prop.py prints worst |dval| and exits 0 (PASS) / 1 (FAIL).
    r = subprocess.run([sys.executable, "compare_parity_35prop.py"] + dumps,
                       cwd=args.parity_dir)
    sys.exit(r.returncode)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run on the production weights as a baseline (must PASS).**
```bash
cd c:/libraries/PrismataAI && python tools/parity/dump_value_batch.py \
  --states-dir /tmp/sp_states --weights c:/libraries/PrismataAI-dave-master/bin/asset/config/neural_weights_mixed_35prop.bin \
  --dave-bin c:/libraries/PrismataAI-dave-master/bin --limit 1000
```
Expected: `worst |value_cpp - value_torch| = …e-0x (tol 1e-3) … ALL PASS`, exit 0. (Reference `.pt`/`.bin` pinning lives inside `compare_parity_35prop.py`; for a freshly-trained candidate, re-pin its `.pt` per that script's convention.)

- [ ] **Step 3: Commit.**
```bash
cd c:/libraries/PrismataAI && git add tools/parity/dump_value_batch.py
git commit -m "feat(eval): scale export-parity harness to ~1000 self-play states"
```

---

## Task 9: 6s/12s human validation harness (Prereq §10.6)

**Repo:** `PrismataAI/`. **File:** `eval/human_val.py` (thin wrapper over `matchup_clean.js`).

**Why:** Spec §10.6 — "build the 6s/12s human val (exact-match-audited)" — a forgetting/strength diagnostic at human-relevant think-times against the exact-match-clean human distribution, separate from the fast fixed-sims anchors.

- [ ] **Step 1: Implement `eval/human_val.py`.**

Run the candidate (`RL_Eval` argmax twin) vs `STEAMAI/.ORIG` at `--think-time 6000` and `12000` on a general (random) card pool, using `matchup_clean.js`; report Wilson CIs via `eval/wilson.py`. (This reuses the `run_steam`/`parse_matchup_tally` helpers from Task 7 with a `--think-time` override and a held-out card pool.)
```python
"""6s and 12s human-relevant-think-time validation vs STEAMAI/.ORIG (forgetting diagnostic)."""
import argparse, subprocess, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from wilson import win_rate, wilson_ci
from run_eval import parse_matchup_tally

def run(think_ms, games, orig_exe, candidate):
    cmd = ["node", "c:/libraries/PrismataAI/js_engine/matchup_clean.js",
           "--games", str(games), "--parallel", "4", "--player-switch",
           "--think-time", str(think_ms), "--player", "SteamAI",
           "--steam-difficulty", "HardestAI", "--dave-exe", orig_exe]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=72000)
    return parse_matchup_tally(p.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig-exe", required=True)
    ap.add_argument("--games", type=int, default=128)
    a = ap.parse_args()
    for t in (6000, 12000):
        w, d, n = run(t, a.games, a.orig_exe, "RL_Eval")
        p = win_rate(w, d, n); lo, hi = wilson_ci(p, n)
        print(f"think={t}ms  WR={p:.3f}  CI=[{lo:.3f},{hi:.3f}]  (n={n})")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke (8 games each think-time), confirm output.** Then commit:
```bash
cd c:/libraries/PrismataAI && git add eval/human_val.py
git commit -m "feat(eval): 6s/12s human-think-time validation harness"
```

---

## Task 10: O7 tactical regression suite (spec §5)

**Repo:** `PrismataAI/`. **Files:** `eval/tactical_suite.py`, `eval/tactical_cases/*.json`.

**Why:** Spec §5 (O7) — a fixed curated set (~20–50) of single-state move-query cases with known-correct moves, run after each iteration in seconds *before* the expensive tournaments. Sourced from the user's own games vs DSNN, with card sets curated to include Infusion Grid. Two buckets: (a) known-correct-move (e.g. "should fire IG"/"should skip IG") → regression checks; (b) "a decision looks forced here" → action-space backlog. **Not a promotion metric** — a cheap diagnostic + backlog feeder.

> **Mechanism note (verified + user-confirmed):** dave-master's `PrismataAI.exe` (standalone) has **no `--suggest` CLI** — it is the **one-shot Steam-protocol stdin responder** (read `{mergedDeck, gameState, aiParameters, aiPlayerName}` on stdin → emit clicks JSON on stdout → exit) plus the `--dump-features` hook. So a single-state move query **reuses that existing protocol** (exactly what `js_engine/steam_ai.js` already does, and the shape an F6 dev-dump gives: `CurrentInfo` = `{mergedDeck, gameState, aiParameters}`) — **no new CLI hook.** For the one thing the clicks response lacks — root visit counts for the calibration entropy floor (Task 13) — **extend the responder's stdout JSON** with an optional `aivisits` array, gated by an `aiParameters` flag so normal play is untouched.

- [ ] **Step 0a: Extend the Steam responder's stdout with optional `aivisits` (engine).**

In dave's Steam-protocol responder (`source/standalone/main.cpp`, the stdin-request path that builds the player and emits `aiclicks`), add: if the request's `aiParameters` carries `"EmitDiagnostics":true` and the selected player is a `Player_UCT`, also emit `"aivisits":[<root child visit counts>]` and `"aiargmax":<argmax child idx>` / `"aichosen":<chosen idx>` in the response object. Expose the counts via a `Player_UCT` accessor populated in `doSearch` from `_rootNode`'s children (`const std::vector<size_t> & lastRootVisits() const`, plus the argmax/chosen indices). Normal play (flag absent) is byte-identical. Build `Prismata_standalone`.

- [ ] **Step 0b: A Node move-query helper over the existing protocol.**

Reuse `js_engine/steam_ai.js` (the one-shot responder client). Add `js_engine/query_move.js`: given a state file `{mergedDeck, gameState, aiParameters}` (F6-dump shape) + a player name, it spawns dave's `PrismataAI.exe`, injects the `RL_Eval`/`RL_SelfPlay` player block + `EmitDiagnostics:true` into `aiParameters` (mirroring `matchup_clean.js`'s DSNN auto-inject at line ~846), sends the request, and returns the parsed response `{aiclicks, aivisits, aiargmax, aichosen}`. The Python suite shells out to this helper. (This is the same path that drives DSNN-in-dave today, so it is known-good.)

- [ ] **Step 1: Define the case format + 3 seed cases.**

Each case = `{ "name", "bucket": "known_move"|"looks_forced", "request": <F6-dump: {mergedDeck, gameState, aiParameters}>, "expect": {"fires_hotel": true|false}|null, "note" }`. The `request` is captured directly from the live client via the **F6 dev-mode clipboard dump** (`CurrentInfo` JSON) on the curated IG position, or reconstructed from a saved replay state. Create `eval/tactical_cases/ig_skip_01.json` etc. **from the user's own DSNN games** — placeholder states are NOT acceptable; these must be real curated positions. Document the capture workflow in `eval/tactical_cases/README.md`: *play (or replay) to the IG decision point → F6 → paste the `CurrentInfo` JSON → set `expect.fires_hotel` to the known-correct call.* (IG-skip cases only become meaningful once Task 12 wires the IG-optional variant; until then they test the always-fire baseline.)

- [ ] **Step 2: Implement `eval/tactical_suite.py`.**

For each `known_move` case: send the case's `request` (F6-dump shape) through `js_engine/query_move.js` with player `RL_Eval` + the candidate weights, parse `aiclicks`, and check whether the Infusion Grid (`Hotel`) `USE_ABILITY` is present vs `expect.fires_hotel`. Print PASS/FAIL per case + a summary; emit `looks_forced` cases to `eval/backlog_action_space.md`. Return nonzero only if a previously-passing case regresses (compare to a stored `eval/tactical_baseline.json`).
```python
"""O7 tactical regression suite: fast move-query checks (Steam stdin/stdout) on curated IG positions."""
import argparse, glob, json, os, subprocess, sys

def query(dave_exe, request_path, weights, player="RL_Eval"):
    # query_move.js spawns dave's PrismataAI.exe, injects the player block + EmitDiagnostics,
    # sends the Steam request on stdin, returns {aiclicks, aivisits, aiargmax, aichosen}.
    out = subprocess.run(["node", "c:/libraries/PrismataAI/js_engine/query_move.js",
                          "--request", request_path, "--player", player,
                          "--weights", weights, "--dave-exe", dave_exe],
                         capture_output=True, text=True, timeout=120)
    return json.loads(out.stdout.strip().splitlines()[-1])

def fires_hotel(resp, hotel_id):
    return any(c.get("_id") == hotel_id and c.get("_type") in ("inst", "inst shift")
              for c in resp.get("clicks", []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--cases", default="eval/tactical_cases")
    args = ap.parse_args()
    results = {}
    for cf in sorted(glob.glob(os.path.join(args.cases, "*.json"))):
        case = json.load(open(cf))
        if case["bucket"] != "known_move":
            continue
        # write the case request (F6-dump shape) to a temp file for query_move.js
        tmp = cf + ".request.json"; json.dump(case["request"], open(tmp, "w"))
        resp = query(args.dave_exe, tmp, args.weights)
        got = fires_hotel(resp.get("aiclicks", []), case.get("hotel_inst_id"))
        ok = (got == case["expect"]["fires_hotel"])
        results[case["name"]] = ok
        print(f"[{'PASS' if ok else 'FAIL'}] {case['name']} (fires_hotel={got}, want={case['expect']['fires_hotel']})")
    n_pass = sum(results.values())
    print(f"tactical: {n_pass}/{len(results)} pass")

if __name__ == "__main__":
    main()
```
> The `Hotel` click-shape (`inst`/`inst shift` `USE_ABILITY` on the IG instance id) must be confirmed against a real `query_move.js` response on an IG state; adjust `fires_hotel` accordingly. The `hotel_inst_id` is recorded per case when it is curated (from the F6 dump's instance ids).

- [ ] **Step 3: Run on a curated IG state, confirm it classifies fire-vs-skip; commit.**
```bash
cd c:/libraries/PrismataAI && git add eval/tactical_suite.py eval/tactical_cases/
git commit -m "feat(eval): O7 tactical regression suite (IG fire/skip move-query checks)"
```

---

## Task 11: 116-unit off-book reachability audit → `RL_Explore` filter (Prereq §10.7)

**Repo:** `PrismataAI-dave-master` + a script. **File:** `eval/offbook_audit.py` (main repo) driving the engine.

**Why:** Spec §10.7 / §6.2 — a finite scriptable check that gates widening **axis-2** (OB-off + buy-filter-widen). It does **not** block axis-1 (IG). **This whole task is a parallel track** — it can run concurrently with Tasks 12–14 (the first IG-optional campaign) and need not be on the critical path. Off-book buy reachability is decided by the union across the 5 ActionBuy partials, each gated by `shouldNotBuy` (5 vetoes: filter, post-chill attack-cost, out-of-sync, buy-limit, `canAffordToActivate`), `TechHeuristic` producer caps, and (off) the opening book. Wild Drone / Doomed Drone are already known unbuildable off-book.

> **`eval/offbook_template.json` (the probe base state):** produce it once — run `PrismataAI.exe --dump-features <any mid-game state.json> out.json` (or take a turn-3+ `gameState` from a saved self-play game), and save the `gameState` object as `eval/offbook_template.json`. `build_states(unit)` mutates a deep copy of it per unit (raise all resource pools high, set turn ≥ 3, ensure the unit + tech producers are buyable, OB off). Validate by running the probe on 2–3 known units (e.g. a plain attacker = reachable, Wild Drone = unreachable) before the full 116-unit sweep.

- [ ] **Step 1: Choose the audit method (static + probe hybrid).**

Decision (resolves recon open question): a **`--suggest`-driven probe** is the most faithful and lowest-risk. For each of the 116 units, construct a minimal mid-game state (turn ≥ 3, OB off, the unit available in the card set, ample resources of every colour) and ask the buy partials (via a dedicated `RL_Explore` player whose ActionBuy slot enumerates all 5 buy partials with OB removed) whether **any** whole-turn child buys the unit. A unit is **reachable** if it appears in at least one emitted buy across a small battery of resource/board states; otherwise it is **unbuildable off-book** and goes on the `RL_Explore` filter exclusion list (or flags a needed buy-filter widening).

- [ ] **Step 2: Add an `RL_Explore` player + a `--probe-buys` engine hook.**

In `config.txt` add an `RL_Explore` player using the existing buy combos with `BuyOpeningBook` removed from the ability/buy chain (OB-off), 5-variant ability portfolio. In `source/standalone/main.cpp`, add a `--probe-buys <state.json> <out.json>` hook that loads the state, runs the `RL_Explore` root iterator's `generateNextChild` to enumerate all whole-turn children, and emits the set of distinct `BUY` card-type ids across them. (This reuses the iterator directly — no search — so it lists exactly what the generator can propose.)

- [ ] **Step 3: Implement `eval/offbook_audit.py`.**

Loop over the 116 units (`training/data/unit_index.json`), build a battery of probe states per unit (vary colour resources high; turn 3–6; with/without a relevant producer on board), run `--probe-buys`, and record reachable/unreachable. Write `eval/offbook_reachability.json` (per-unit verdict + which probe states reached it) and `eval/rl_explore_filter.json` (the exclusion list = units never reachable). Assert Wild Drone + Doomed Drone are in the unreachable set (a known-answer sanity check).
```python
"""116-unit off-book buy reachability audit -> RL_Explore filter. Gates RL widening axis-2."""
import argparse, json, os, subprocess, sys

def probe(dave_bin, state_path, out_path):
    subprocess.run([os.path.join(dave_bin, "PrismataAI.exe"), "--probe-buys", state_path, out_path],
                   cwd=dave_bin, check=True, timeout=120)
    return set(json.load(open(out_path)).get("buyable_units", []))

def build_states(unit_name):
    """Return a list of minimal gameState dicts (turn>=3, OB off, high resources, `unit_name`
    in the card set, varied producers on board). Construct from a base template the user supplies
    once at eval/offbook_template.json; this function fills resources/turn/card-set per unit."""
    base = json.load(open("eval/offbook_template.json"))
    states = []
    for turn, res in ((3, "high_all"), (5, "high_red"), (5, "high_blue")):
        s = json.loads(json.dumps(base)); s["turn_hint"] = turn; s["force_unit"] = unit_name; s["res"] = res
        states.append(s)
    return states

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--unit-index", default="c:/libraries/PrismataAI/training/data/unit_index.json")
    args = ap.parse_args()
    units = json.load(open(args.unit_index))           # list/dict of 116 canonical names
    names = units if isinstance(units, list) else list(units)
    verdict = {}
    for u in names:
        reached = False
        for i, st in enumerate(build_states(u)):
            sp = f"/tmp/probe_{u}_{i}.json"; json.dump({"gameState": st}, open(sp, "w"))
            if u in probe(args.dave_bin, sp, sp + ".out"):
                reached = True; break
        verdict[u] = reached
    unreachable = [u for u, r in verdict.items() if not r]
    json.dump(verdict, open("eval/offbook_reachability.json", "w"), indent=2)
    json.dump({"exclude": unreachable}, open("eval/rl_explore_filter.json", "w"), indent=2)
    for known in ("Wild Drone", "Doomed Drone"):
        assert known in unreachable, f"sanity fail: {known} should be unbuildable off-book"
    print(f"unreachable off-book: {len(unreachable)}/{len(names)}")

if __name__ == "__main__":
    main()
```
> `eval/offbook_template.json` (a minimal valid `gameState` the engine accepts) and the exact `--probe-buys` state-construction must be produced once against a real engine load; the probe is only as good as the states it builds. This task **gates axis-2 only** — it can run in parallel with the axis-1 campaign and need not block Tasks 12–14.

- [ ] **Step 4: Run, eyeball the unreachable list, commit.**
```bash
cd c:/libraries/PrismataAI && git add eval/offbook_audit.py eval/offbook_reachability.json eval/rl_explore_filter.json
git commit -m "feat(eval): off-book reachability audit -> RL_Explore filter (gates axis-2)"
cd c:/libraries/PrismataAI-dave-master && git add source/standalone/main.cpp bin/asset/config/config.txt
git commit -m "feat(ai): --probe-buys hook + RL_Explore player for off-book audit"
```

---

## Task 12: Infusion-Grid-optional config + forced-set card-pool wiring (Prereq §10.8)

**Repo:** `PrismataAI-dave-master`. **Files:**
- Modify: `bin/asset/config/config.txt` (IG-optional variant + iterator)
- Modify: `source/engine/GameState.cpp`, `source/testing/Tournament.cpp` (forced-card-set), `source/standalone/main.cpp` (verify `--suggest`)

**Why:** Spec §6.1 — the first RL campaign. Config-only IG-optional variant (a portfolio ability variant where `Hotel` is in the `ActivateUtility` filter → both "fire IG" and "skip IG" whole-turn children → net picks). Plus **forced-set curriculum** (spec §6, S1): force Infusion Grid into the random card set of every self-play AND eval game (vs ~7.6% by chance). Forced-set support does **not** exist in `Tournament.cpp` — it must be added in C++.

- [ ] **Step 1: Add the IG-optional ability variant (config-only).**

In `bin/asset/config/config.txt`:
1. New filter after `Ability_Filter_Live` (line ~66):
```json
    "Ability_Filter_Live_NoIG" :
    {
        "default"    : false,
        "cards"      : ["Drake", "Grenade Mech", "Odin", "Hotel"]
    },
```
2. New ActivateUtility partial (near line 121) using that filter:
```json
    "AbilityActivateUtilityNoIG" : { "type":"ActionAbility_ActivateUtility", "filter":"Ability_Filter_Live_NoIG"},
```
3. New ability variant `V5_CS_NoIG`. **The `ActivateUtility` reference is nested two levels down** (verified): `V5_CS → V5_ACEasy → V5_ACDefault`, and `V5_ACDefault` (config.txt:91) is `["AbilityEconomyDefault", "AbilityAttackDefaultLive", "AbilityActivateUtilityLive", "AbilityFrontlineGKWill", "AbilitySnipeGKWill", "AbilityChillGKWill", "AbilityAvoidAttackWaste"]`. So define the NoIG chain mirroring that nesting, swapping only `AbilityActivateUtilityLive` → `AbilityActivateUtilityNoIG`:
```json
    "V5_ACDefault_NoIG" : { "type":"ActionAbility_Combination", "combination": ["AbilityEconomyDefault", "AbilityAttackDefaultLive", "AbilityActivateUtilityNoIG", "AbilityFrontlineGKWill", "AbilitySnipeGKWill", "AbilityChillGKWill", "AbilityAvoidAttackWaste"] },
    "V5_ACEasy_NoIG"    : { "type":"ActionAbility_Combination", "combination": ["V5_ACDefault_NoIG", "BuyOpeningBook"] },
    "V5_CS_NoIG"        : { "type":"ActionAbility_Combination", "combination": ["V5_ACEasy_NoIG", "AvoidBreach_SolveChill", "AbilityAvoidDefenseWaste"] },
```
(`V5_CS` = `[V5_ACEasy, AvoidBreach_SolveChill, AbilityAvoidDefenseWaste]` and `V5_ACEasy` = `[V5_ACDefault, BuyOpeningBook]` — config.txt:95,98 — so `V5_CS_NoIG` is the exact analogue with IG suppressed.)
4. New iterator with the NoIG variant added to the ability slot (6 variants now):
```json
    "HardIterator_5var_IGopt_Root" : { "type":"PPPortfolio", "PartialPlayers": [ ["DefenseSolver"], ["V5_CS2", "V5_CS", "V5_CSNF", "V5_CSClickNC", "V5_CSClickNF", "V5_CS_NoIG"], ["BuyEconTech", "BuyTechEcon", "BCGAttack_Root", "BCGWill_Root", "BCGDef_Root"], ["BreachGreedyKnapsack"] ] },
```
5. Repoint `RL_SelfPlay`, `RL_Eval`, and `RL_Eval_iter0` `RootMoveIterator` to `HardIterator_5var_IGopt_Root` (keep `MoveIterator` as the interior `HardIterator_5var`).

- [ ] **Step 2: Verify both whole-turn children appear (stdin/stdout move query).**

Pick an IG state (a curated Task-10 case where `Hotel` is in play and red is legal). Query via the helper (Task 10 Step 0b), with `EmitDiagnostics:true` so the root children are visible:
```bash
node c:/libraries/PrismataAI/js_engine/query_move.js --request <ig_case.json> --player RL_Eval \
  --weights neural_weights_mixed_35prop.bin --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe
```
Confirm the response shows the search now has both a "fire IG" and a "skip IG" root child (`aivisits` length grew vs the 5-variant baseline, and on at least one IG state the chosen move differs from always-fire). If IG still always fires, re-check that `"Hotel"` resolves and that `V5_CS_NoIG` is actually in the iterator slot.

- [ ] **Step 3: Add forced-card-set support in C++ (failing → passing).**

In `source/engine/GameState.cpp`, overload/extend `setStartingState` to accept forced unit names placed deterministically before random fill:
```cpp
void GameState::setStartingState(const PlayerID startPlayer, const CardID numDominionCards,
                                 const std::vector<std::string> & forcedCards)
{
    for (size_t c(0); c<CardTypes::GetBaseSetCardTypes().size(); ++c)
        addBuyableCardType(CardTypes::GetBaseSetCardTypes()[c]);

    std::vector<size_t> pool;
    for (size_t c(0); c<CardTypes::GetDominionCardTypes().size(); ++c)
        pool.push_back(c);

    // Place forced cards first (remove from pool), then random-fill the remainder.
    size_t placed = 0;
    for (const std::string & nm : forcedCards)
    {
        if (placed >= numDominionCards) break;
        if (!CardTypes::CardTypeExists(nm)) continue;
        const CardType ct = CardTypes::GetCardType(nm);
        addBuyableCardType(ct);
        for (size_t i = 0; i < pool.size(); ++i)
            if (CardTypes::GetDominionCardTypes()[pool[i]] == ct) { std::swap(pool[i], pool.back()); pool.pop_back(); break; }
        placed++;
    }
    for (size_t c(placed); c<numDominionCards; ++c)
    {
        size_t r = Random::Int(pool.size());
        addBuyableCardType(CardTypes::GetDominionCardTypes()[pool[r]]);
        std::swap(pool[r], pool.back()); pool.pop_back();
    }

    if (CardTypes::CardTypeExists("Drone"))    addCard(startPlayer, CardTypes::GetCardType("Drone"), 6, CardCreationMethod::Manual, 0, 0);
    if (CardTypes::CardTypeExists("Engineer")) addCard(startPlayer, CardTypes::GetCardType("Engineer"), 2, CardCreationMethod::Manual, 0, 0);
    if (CardTypes::CardTypeExists("Drone"))    addCard(getEnemy(startPlayer), CardTypes::GetCardType("Drone"), 7, CardCreationMethod::Manual, 0, 0);
    if (CardTypes::CardTypeExists("Engineer")) addCard(getEnemy(startPlayer), CardTypes::GetCardType("Engineer"), 2, CardCreationMethod::Manual, 0, 0);
    beginPhase(startPlayer, Phases::Swoosh);
}
```
Keep the original 2-arg signature as a wrapper: `setStartingState(p, n) { setStartingState(p, n, {}); }` (declare both in `GameState.h`).

In `source/testing/Tournament.cpp`: read an optional `"ForcedCards"` string array into `std::vector<std::string> _forcedCards;` (declare in `Tournament.h`), and change the `state.setStartingState(Players::Player_One, _randomCards)` call (line ~213, both single- and multi-thread loops) to `state.setStartingState(Players::Player_One, _randomCards, _forcedCards)`.

- [ ] **Step 4: Verify forced-set works.**

Add a block forcing Infusion Grid:
```json
    {"run":false, "type":"Tournament", "name":"RL_ForcedIG_Smoke", "rounds":2, "Seed":55, "Threads":1, "RandomCards":8, "ForcedCards":["Hotel"], "saveReplays":"asset/replays/forced_ig", "players":[{"name":"RL_SelfPlay","group":1},{"name":"RL_SelfPlay","group":1}]},
```
Run `Prismata_Testing.exe`, then confirm every saved replay's card set contains `Hotel`/Infusion Grid:
```bash
node -e "const z=require('zlib'),fs=require('fs'),p=require('path');const d=process.argv[1];let ok=0,bad=0;for(const f of fs.readdirSync(d)){const r=JSON.parse(f.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p.join(d,f))):fs.readFileSync(p.join(d,f)));const md=JSON.stringify(r.deckInfo.mergedDeck);(md.includes('Infusion Grid')||md.includes('Hotel'))?ok++:bad++;}console.log('with IG',ok,'without',bad);" \
  c:/libraries/PrismataAI-dave-master/bin/asset/replays/forced_ig
```
Expected: `without 0`.

- [ ] **Step 5: Commit (engine, two commits).**
```bash
cd c:/libraries/PrismataAI-dave-master
git add bin/asset/config/config.txt
git commit -m "feat(config): Infusion-Grid-optional ability variant + HardIterator_5var_IGopt_Root"
git add source/engine/GameState.cpp source/engine/GameState.h source/testing/Tournament.cpp source/testing/Tournament.h
git commit -m "feat(testing): forced-card-set curriculum (ForcedCards) for self-play + eval"
```

---

## Task 13: N-calibration sweep + non-degeneracy check (Prereq §10.9)

**Repo:** `PrismataAI/` (driver) + `config.txt`. **File:** `eval/calibrate_n.py`.

**Why:** Spec §3 / §9 — set `N` (MaxTraversals) by calibration **before** iter-0, not by feel. Sweep `N ∈ {100,256,512,1k,2k,5k}` with the frozen net; pick the **smallest N that passes the non-degeneracy check**: game-length within 2σ of the human-1800 baseline; P0/P1 win-rate ∈ [0.35,0.65]; root visit-entropy above a floor; win-rate vs the 100k-sim deployment net not catastrophically low. `N` must be comfortably > root branching (≤30 for IG-optional) so the mandatory initial expansion isn't most of the budget.

- [ ] **Step 1: Add per-N self-play + a vs-deployment block to `config.txt`.**

For each candidate N, a self-play block (`RL_SelfPlay` clone with that `MaxTraversals`, `Threads:1`, `Seed` fixed, `ForcedCards:["Hotel"]`, `saveReplays`) and an A/B block vs `DSNN_Mixed35_5var` (the 100k-sim deployment net). Name them `RL_Cal_N100`, `RL_Cal_N256`, … and `RL_Cal_vs_deploy_N512` etc. (Reuse one player per N via separate player defs `RL_SelfPlay_N100`…)

- [ ] **Step 2: Implement `eval/calibrate_n.py`.**

Drives the sweep: for each N, run the self-play block, extract replays → V2 (Task 5), compute (a) mean/σ game-length vs the human-1800 baseline (precompute the human baseline once from `human_1800_v2.h5` turn counts), (b) P0/P1 win-rate from the labels, (c) root visit-entropy (requires the `--suggest` response to emit per-child visit counts — add a `visits` array to the `--suggest`/dump JSON, or compute entropy from a `--probe-buys`-style root dump), (d) win-rate vs the deployment net. Emit `eval/n_calibration.json` and print the recommended smallest passing N.
```python
"""N-calibration: smallest MaxTraversals passing the non-degeneracy check (spec §3/§9)."""
import argparse, json, math, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from wilson import win_rate

NS = [100, 256, 512, 1000, 2000, 5000]
LEN_SIGMA = 2.0
WR_BAND = (0.35, 0.65)
ENTROPY_FLOOR = 0.5   # nats; tune from the human baseline

def human_baseline_len(h5_path):
    import h5py, numpy as np
    f = h5py.File(h5_path, "r")
    tp = f["total_plies"][:] if "total_plies" in f else None
    if tp is None: return (60.0, 15.0)
    return float(tp.mean()), float(tp.std())

def degenerate(metrics, base_mu, base_sd):
    if abs(metrics["mean_len"] - base_mu) > LEN_SIGMA * base_sd: return "game_length"
    if not (WR_BAND[0] <= metrics["p0_wr"] <= WR_BAND[1]): return "p0_winrate"
    if metrics["root_entropy"] < ENTROPY_FLOOR: return "root_entropy"
    if metrics["wr_vs_deploy"] < 0.20: return "catastrophic_vs_deploy"
    return None

def metrics_from_h5(sp_h5, root_entropy, wr_vs_deploy):
    import h5py, numpy as np
    f = h5py.File(sp_h5, "r")
    plies = f["total_plies"][:] if "total_plies" in f else np.array([f["label_A"].shape[0]])
    lab = f["label_A"][:]
    return {"mean_len": float(plies.mean()),
            "p0_wr": float((lab == 1.0).mean() + 0.5 * (lab == 0.5).mean()),
            "root_entropy": float(root_entropy),
            "wr_vs_deploy": float(wr_vs_deploy)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--human-h5", required=True, help="human_1800_v2.h5 for the length baseline")
    ap.add_argument("--out", default="eval/n_calibration.json")
    args = ap.parse_args()

    base_mu, base_sd = human_baseline_len(args.human_h5)
    report = {"baseline_len": [base_mu, base_sd], "per_N": {}, "recommended_N": None}

    for N in NS:
        # 1) self-play: flip RL_Cal_N{N} run:true (exportTrainingV2 on), run Prismata_Testing from bin/, flip back.
        subprocess.run([os.path.join(args.dave_bin, "Prismata_Testing.exe")],
                       cwd=args.dave_bin, check=True, timeout=36000)
        sp_dir = os.path.join(args.dave_bin, f"asset/training/rl_cal_N{N}")   # C++ exportTrainingV2 dir
        sp_jsonl, sp_h5 = f"/tmp/cal_N{N}.jsonl", f"/tmp/cal_N{N}.h5"
        # 2) concat C++ V2 JSONL shards -> vectorize -> H5  (no JS extractor; Task 5 emits V2 directly)
        with open(sp_jsonl, "wb") as outf:
            for f in glob.glob(os.path.join(sp_dir, "*.jsonl")):
                outf.write(open(f, "rb").read())
        subprocess.run(["python", "c:/libraries/PrismataAI/training/vectorize_v2.py",
                        "--input", sp_jsonl, "--output", sp_h5,
                        "--schema", "c:/libraries/PrismataAI/training/schema_v2.json"], check=True)
        # 3) root entropy + wr-vs-deploy
        root_entropy = read_mean_root_entropy(args.dave_exe, N)
        wr_vs_deploy = read_vs_deploy_wr(args.dave_bin, N)
        m = metrics_from_h5(sp_h5, root_entropy, wr_vs_deploy)
        m["degenerate_reason"] = degenerate(m, base_mu, base_sd)
        report["per_N"][N] = m

    for N in NS:                                # smallest N that passes AND is comfortably > branching (<=30)
        if report["per_N"][N]["degenerate_reason"] is None and N >= 100:
            report["recommended_N"] = N; break

    json.dump(report, open(args.out, "w"), indent=2)
    print("recommended_N =", report["recommended_N"])

if __name__ == "__main__":
    main()
```
The two read helpers (place above `main()`):
```python
def shannon_entropy(visits):
    tot = float(sum(visits))
    if tot <= 0: return 0.0
    import math
    return -sum((v/tot) * math.log(v/tot) for v in visits if v > 0)

def read_mean_root_entropy(dave_exe, N, battery="eval/calib_states"):
    # Query the seeded battery of states via the stdin/stdout move helper (Task 10 Step 0b);
    # the response carries aivisits[] (root child visit counts) when EmitDiagnostics:true.
    import glob, json, subprocess
    ents = []
    for s in glob.glob(os.path.join(battery, "*.json")):
        out = subprocess.run(["node", "c:/libraries/PrismataAI/js_engine/query_move.js",
                              "--request", s, "--player", f"RL_SelfPlay_N{N}",
                              "--weights", "neural_weights_mixed_35prop.bin", "--dave-exe", dave_exe],
                             capture_output=True, text=True, timeout=120)
        resp = json.loads(out.stdout.strip().splitlines()[-1])
        ents.append(shannon_entropy(resp.get("aivisits", [])))
    return sum(ents) / max(1, len(ents))

def read_vs_deploy_wr(dave_bin, N):
    # Reuse run_eval.parse_tournament_stdout on the RL_Cal_vs_deploy_N{N} block output.
    import subprocess
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from run_eval import parse_tournament_stdout
    p = subprocess.run([os.path.join(dave_bin, "Prismata_Testing.exe")], cwd=dave_bin,
                       capture_output=True, text=True, timeout=36000)
    res = parse_tournament_stdout(p.stdout + p.stderr, f"RL_Cal_vs_deploy_N{N}")
    r = res.get(f"RL_SelfPlay_N{N}", {"wins": 0, "draws": 0, "games": 1})
    return (r["wins"] + 0.5 * r["draws"]) / max(1, r["games"])
```
Root visit-entropy uses the **stdin/stdout `aivisits`** extension (Task 10 Step 0a) — the single engine dependency shared by Tasks 10 and 13. The `eval/calib_states/` battery is ~20 seeded F6-dump states spanning turn numbers / resources / IG availability.

- [ ] **Step 3: Run the sweep, record the recommended N, set it on the RL players.**

Update `RL_SelfPlay` / `RL_Eval` / calibration-derived blocks' `MaxTraversals` to the recommended N. Commit `eval/n_calibration.json` + the config change.
```bash
cd c:/libraries/PrismataAI && git add eval/calibrate_n.py eval/n_calibration.json
git commit -m "feat(eval): N-calibration sweep + non-degeneracy check"
cd c:/libraries/PrismataAI-dave-master && git add bin/asset/config/config.txt
git commit -m "feat(config): set RL MaxTraversals=N from calibration"
```

---

## Task 14: Freeze the HP tuple + run the first IG-optional campaign (Prereq §10.10 + §12)

**Repo:** `PrismataAI/`. **Files:** `eval/rl_campaign.md` (frozen HP tuple + decision rule), `eval/run_iteration.ps1` (one-iteration driver), `eval/render_dashboard.py`.

**Why:** Spec §10.10 / §11 / §12 — freeze `(N, τ, K, ε, W, rehearsal fraction+decay, gate margin, rollback margin, eval N, target effect size)` before iter-1; any change = a new campaign. Then run the gated loop on the IG-optional axis per the §12 decision rule.

- [ ] **Step 1: Write the frozen HP tuple.**

`eval/rl_campaign.md` records the locked values (N from Task 13; τ=1.0; K=6; ε=0.25; W=5; rehearsal start 0.30 → floor 0.10, decay 0.07/iter; gate margin = CI-lower > 0.50; rollback margin Y = 0.03 on the general pool; eval N per anchor sized to the target effect size E; **pre-register E** = the smallest IG fire/skip-driven win-rate gain worth AWS spend, e.g. +5pp → ~600 games/anchor). Include the §12 decision-rule pseudocode verbatim and the kill criteria (≥3 flat iterations + clean false-negative triage).

Also record in `eval/rl_campaign.md`:

**Heuristic-change discipline (spec §7):** during this first proof-of-life campaign, **freeze** the engine/config except the RNG fix, the temperature/root-exploration sampler, the IG-optional variant, and correctness bugs that invalidate a run. RL iterations change **only the net** on a frozen, resolved-config-hash-pinned config. KEEP-style heuristic *bugs* (dominated misplays) may be fixed programmatically, but each such fix is A/B'd with the *fixed* net, then merged + re-anchored (re-run iter-0 wide-untrained) — never changed mid-campaign. Maintain a changelog mapping every win-rate point to one `(resolved-config-hash, net-hash)` delta.

**False-negative triage checklist (spec §9 — run before declaring no-go):**
1. Was the new action (IG skip) in the root candidate set often enough? (action-coverage, Task 7 Step 6b)
2. Did temperature actually sample non-argmax? (sampled-vs-argmax sidecar, Task 5 Step 5)
3. Labels pass inversion/scale tests? (Task 6)
4. Did training change predictions on self-play positions? (compare net value pre/post on a fixed batch)
5. Does exported `.bin` match PyTorch? (export-parity, Task 8)
6. Did eval load the intended net? (manifest net-hash + contamination checks, Task 7)
7. Was eval statistically powered? (sequential N reached target effect size, Task 7)
8. Was self-play non-degenerate at N? (Task 13 metrics)
9. Did rehearsal overwhelm the RL signal? (vary human fraction)
10. Target-up but general-down (overfit, not no-learning)?

- [ ] **Step 2: Write the one-iteration driver.**

`eval/run_iteration.ps1` (PowerShell — native env). Each stage aborts the run on failure (`$ErrorActionPreference='Stop'`); the WeightsFile repoint is a small Python edit of `config.txt`'s `RL_Eval` block (`json`-safe in-place rewrite). Skeleton:
```powershell
param([int]$K = 1, [int]$N = 512, [int]$Window = 5)
$ErrorActionPreference = 'Stop'
$dave = 'c:/libraries/PrismataAI-dave-master'; $bin = "$dave/bin"; $train = 'c:/libraries/PrismataAI/training'

# 1) self-play (C++ tournament: RL_SelfPlay self-play, ForcedCards Hotel, fixed N, exportTrainingV2 on)
& "$bin/Prismata_Testing.exe"                      # the RL_SelfPlay_iter block is run:true with exportTrainingV2
# 2) concat C++ V2 shards -> vectorize -> this iteration's H5
Get-Content "$bin/asset/training/rl_iter$K/*.jsonl" | Set-Content "$train/data/selfplay_iter$K.jsonl"
python "$train/vectorize_v2.py" --input "$train/data/selfplay_iter$K.jsonl" --output "$train/data/selfplay_iter$K.h5" --schema "$train/schema_v2.json"
# 3) low-LR few-epoch SWA fine-tune over the sliding window + human rehearsal
$window = (1..$K | Select-Object -Last $Window | ForEach-Object { "$train/data/selfplay_iter$_.h5" })
python "$train/train.py" --model deepsets --property-table "$train/property_table.json" `
  --train-file $window[-1] --val-file "$train/data/human_1800_v2.h5" `
  --rl-mode --selfplay-files $window --human-file "$train/data/human_1800_v2.h5" `
  --replay-window $Window --rl-iteration $K --epochs 6 --lr 1e-5 --swa-start-epoch 3 `
  --device xpu --output-dir "$train/models/rl_iter$K"
# 4) export -> .bin
python "$train/export_weights_v2.py" "$train/models/rl_iter$K/best_model.pt" "$bin/asset/config/neural_weights_rl_iter$K.bin" --property-table "$train/property_table.json"
# 5) export-parity GATE (abort on fail)
python "c:/libraries/PrismataAI/tools/parity/dump_value_batch.py" --states-dir "$bin/asset/training/parity_states" --weights "$bin/asset/config/neural_weights_rl_iter$K.bin" --dave-bin $bin
# 6) fast O7 tactical leading indicator
python "c:/libraries/PrismataAI/eval/tactical_suite.py" --dave-exe "$bin/PrismataAI.exe" --weights "neural_weights_rl_iter$K.bin"
# 7) repoint RL_Eval.WeightsFile -> the new .bin, then run the 3-anchor eval
python -c "import json,re,io; p=r'$bin/asset/config/config.txt'; s=open(p).read(); s=re.sub(r'(\"RL_Eval\"\s*:\s*\{[^}]*\"WeightsFile\"\s*:\s*\")[^\"]+', r'\g<1>neural_weights_rl_iter$K.bin', s); open(p,'w').write(s)"
python "c:/libraries/PrismataAI/eval/run_eval.py" --iteration $K --weights "neural_weights_rl_iter$K.bin" --parent-weights "neural_weights_rl_iter$($K-1).bin" --dave-bin $bin --orig-exe "$bin/PrismataAI.exe.ORIG" --pools forced general --out "c:/libraries/PrismataAI/eval/manifests"
# 8) action-coverage + dashboard line, then print the §12 decision from the manifest
python "c:/libraries/PrismataAI/eval/action_coverage.py" --selfplay-jsonl-dir "$bin/asset/training/rl_iter$K" --dave-exe "$bin/PrismataAI.exe" --weights "neural_weights_rl_iter$K.bin" --manifest "c:/libraries/PrismataAI/eval/manifests/eval_iter_$K.json"
python "c:/libraries/PrismataAI/eval/render_dashboard.py" --manifests "c:/libraries/PrismataAI/eval/manifests"
```
A human reviews the manifest + dashboard and makes the promote/reject/inconclusive call (the gate is human, per §2). `eval/render_dashboard.py` reads `eval/manifests/*.json` and prints a per-iteration table (win-rate + CI per anchor, IG fire/skip rate, game-length, export-parity, outcome) — write it as a thin reader (≈40 lines); not required for the go/no-go but the spec's §5 dashboard.

- [ ] **Step 3: Run iteration 0 (offline batch-RL de-risk, spec §8.5-O4) and iteration 1.**

Iteration 0 = generate one fixed self-play dataset on the IG-optional config, train once (no loop), eval — a clean positive signal with zero poisoning risk that also validates the whole pipeline. Then run iteration 1 through the driver. Record manifests under `eval/manifests/`.

- [ ] **Step 4: Measure throughput before any AWS spend (spec §8).**

From the iteration-0/1 runs, record games/hour at the chosen N, NN-evals/sec, CPU utilization, and eval games/hour into `eval/rl_campaign.md`. The £400 is sized against measured throughput, not assumption.

- [ ] **Step 5: Commit.**
```bash
cd c:/libraries/PrismataAI && git add eval/rl_campaign.md eval/run_iteration.ps1 eval/action_coverage.py eval/render_dashboard.py eval/manifests/
git commit -m "feat(eval): freeze HP tuple + one-iteration driver + iter-0/1 IG-optional campaign"
```

---

## Escalation paths (spec §14) — DOCUMENTED, NOT BUILT

Record in `eval/rl_campaign.md` under "Escalation": if the §8 kill-criteria trigger (≥3 flat iterations with a clean false-negative triage), escalate in order **before** spending AWS or abandoning value-only RL:
- **O6 — candidate-level policy head, then PUCT.** A head over just the ≤~30 whole-turn portfolio candidates (not the full action space), trained on the MCTS visit distribution over those candidates; turn PUCT on at the root. Large effort. **Do not build now.**
- **O3 — distillation bootstrap.** Periodically run the net at high sims (10k–50k) on a position batch and train the value net to predict the deep-search backed-up value (MSE target). Invoke only if O2's deep-label diagnostic confirms shallow search is the binding bottleneck. **Do not build now.**

Also note the §13 decision status: O1/O2/O4 are folded into the iter-0 de-risking (Task 14 Step 3 covers O4; O1 high-sim early data and O2 deep-label reference batch are cheap optional guards to add if iteration-0 is flat). O5 (dynamic sims) applies to axis-2+, not axis-1. O8 (opponent pool) is AWS-scale. O9–O12 declined.

---

## Self-review (spec coverage map)

| Spec §10 prerequisite | Task(s) |
|---|---|
| 1. RNG fix | Task 1 |
| 2. Temperature + root-exploration sampler (+ unit test first) | Tasks 2, 3 |
| 3. `RL_SelfPlay` config (5-variant + IG-optional + fixed sims + flags) | Tasks 4, 12 |
| 4. Self-play data export (DSNN self-play; C++ V2 exporter, inference-parity; sampled+argmax) | Task 5 |
| 5. Replay buffer + human-only rehearsal in train.py | Task 6 |
| 6. Eval harness (3 anchors, CIs, sequential, manifest, 6s/12s val, export-parity) | Tasks 7, 8, 9 |
| §5 O7 tactical suite | Task 10 |
| 7. 116-unit off-book reachability audit → RL_Explore | Task 11 |
| 8. IG-optional config + forced-set wiring | Task 12 |
| 9. N-calibration + non-degeneracy check | Task 13 |
| 10. Freeze HP tuple; first campaign = IG-optional | Task 14 |
| §14 escalation paths (O6/O3) | Documented, not built |

**Banked decisions honored:** engine_v1 only; cValue 0.3; 5-variant portfolio; human_1800_v2 exact-match-clean; BCE labels [0,1] (win 1.0/draw 0.5/loss 0.0); argmax for eval, temperature self-play-only; STEAMAI = `.ORIG`; fixed-sims; gated single-iteration; native Windows.

**Architecture decisions baked in (post-review):** self-play training data is exported **entirely in C++** (`SelfPlayV2Exporter`, inference-parity features) — *not* via the JS replay path; a C++↔JS-extractor parity test keeps it consistent with the human rehearsal corpus. Single-state move queries reuse the standalone's **one-shot Steam stdin/stdout protocol** (`query_move.js` over `steam_ai.js`) — *not* a new `--suggest` CLI; root visit-entropy comes from an optional `aivisits` field added to the responder's stdout.

**Known interfaces to confirm during execution (flagged inline):** the exact instance-field names of `state_adapter._instToRichUnit` (the C++ exporter must match them — gated by the Step-6 parity test); `Tournament::printResults`/`matchup_clean.js` parse regexes (verify against real runs — Task 7 Step 5); the `Hotel` `USE_ABILITY` click-shape in a `query_move.js` response; the dave Steam-responder's `Move`→clicks converter + the `Player_UCT` visit/argmax accessors (Tasks 5, 10); `eval/offbook_template.json` + `--probe-buys` state construction (Task 11).
