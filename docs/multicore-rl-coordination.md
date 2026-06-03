# Coordination: Multicore-live-play ↔ RL-self-play (shared engine)

> Date: 2026-06-04. Engine = `c:/libraries/PrismataAI-dave-master`, branch `dave-master-jsonclean`.
> Companions: RL plan `docs/superpowers/plans/2026-06-03-rl-selfplay-loop-implementation.md`;
> multicore spec `docs/scratch/2026-06-03-multicore-dsnn-play-design-v3.md`.
> Reference engine SHA for citations as of writing: **`9c64813`** (RL Tasks 1–5 + Task-7 eval config).

Two workstreams share one C++ engine. This note keeps them from stepping on each other and resolves "how do we keep the AI in sync."

## 1. What each workstream owns

- **RL self-play** (improves the AI). Owns: net training (`.bin` weights) **and the action space** — the move generator / iterators / config variants / new C++ partials it opens up (IG-optional, defense/breach branching, red buy-vs-click split, OB-off filters, …). Lives on the **tournament/config path**: `config.txt` players + `Benchmarks` tournaments + `SelfPlayDataExport`/`V2Record` + `train.py`. Never triggers the live `FORCE_DSNN` path.
- **Multicore live play** (improves the search). Owns: multi-core-per-move search for the **user-facing drop-in** (`PrismataAI.exe` via `use_dsnn.txt` + `FORCE_DSNN`). Lives on the **live path**: `AITools.cpp` wiring, new `Player_RootParallelUCT`/`CpuInfo`/`use_dsnn.txt` parser (Option A), optional tree-parallel `UCTNode`/`UCTSearch` (Option B). Forces argmax; never runs the RL sampler/exporter.

They **compose**: the live exe loads whatever net + uses whatever iterator you point it at. The multicore work parallelises the search; the RL work supplies the net and the candidate set the search chooses among.

## 2. "Keeping the AI in sync" — the model that makes it a non-problem

The AI = **net (`.bin`) + action-space (iterators/partials/config)**. Both live on **one branch**, so there is nothing to merge *across* branches. Shipping a stronger AI to friends is a **wiring + data** update on that one branch, not a code-port:

1. RL validates a widening (e.g. IG-optional) → GO. The widened iterator (e.g. `HardIterator_5var_IGopt_Root`) + any new C++ partials are already in the shared tree, and a retrained `.bin` exists.
2. To give friends that AI: point the **live path's `RootMoveIterator`** (`AITools.cpp` FORCE_DSNN params, or the live `aiParameters`) at the **validated** widened iterator, and ship the **matching** `neural_weights_*.bin`. The live multicore search then explores the wider candidate set at argmax.
3. That's it — same branch, same iterator definitions, same `.bin` files. No duplication, no cross-branch sync.

**Rule:** the net and the iterator must be **promoted together** — a net trained on a widened action space must be paired with that widened iterator on the live path (and vice-versa). Promote only RL-validated (post-GO) widenings to the live drop-in; keep unvalidated/experimental widenings out of friends' builds.

### ⚠️ 2a. REQUIRED WIRE (does not exist yet): make the live exe use OUR iterator, not the SWF's

**Current reality (verified `AITools.cpp:124–187`, `9c64813`):** the live `FORCE_DSNN` swap-in overrides the player type / eval / weights / think-time, but it resolves its **move iterator by name** — `getMoveIterator(..., "HardIterator_Root")` / `"HardIterator"` — out of the **per-request `aiParameters` (the SWF's blob)**. The standalone exe **does not load `config.txt`** at startup (only `InitFromCardLibrary`); the `AIParameters` singleton is populated per-request from the SWF. **So the live action space is the SWF's iterator, NOT ours.** Widening `config.txt` (RL's `HardIterator_5var_IGopt_Root`, etc.) has **zero effect on live play** until this is changed — shipping a new exe + `.bin` alone would run the new net over the *old* candidate set (net trained to widen, but the wider moves never generated).

**Required addition (owned by the live-drop-in / multicore workstream; NOT RL):**
1. **Load a bundled config at startup** in the live standalone so our iterator/partial/filter definitions (incl. widened ones → `V5_CS_NoIG` → `Ability_Filter_Live_NoIG`) are registered in `AIParameters::Instance()` (as the tournament exe already does via `parseFile`). Verify whether the per-request `parseJSONValue` **merges into** or **replaces** the registry, and order the load accordingly.
2. **Make `FORCE_DSNN` use a configurable iterator name** (e.g. a `use_dsnn.txt` `iterator=HardIterator_5var_IGopt_Root` key), defaulting to the latest RL-validated iterator — instead of the hardcoded `"HardIterator_Root"` lookup against the SWF blob.

Until (1)+(2) exist, **"promote a widening to friends" is not just a `.bin` swap** — it requires this wire. Track it as a prerequisite of the first live action-space promotion.

## 3. Shared engine surface (as of `9c64813`)

**RL-hot (RL is still editing these — re-verify line numbers; expect rebases):**
`source/ai/UCTSearch.cpp/.h`, `source/ai/UCTSearchParameters.hpp`, `source/ai/AIParameters.cpp`, `bin/asset/config/config.txt`, `source/standalone/main.cpp` (CLI hooks), and (RL Tasks 8–14) `source/engine/GameState.cpp` + `source/testing/Tournament.cpp` (forced-card-set), plus more CLI hooks in `main.cpp`.

**RL-stable (not on the RL roadmap — safe for multicore to build on):**
`source/ai/AITools.cpp` (the live FORCE_DSNN wiring — Option A's main edit site), `source/ai/UCTNode.cpp/.h`, `source/ai/NeuralNet.cpp/.h`, `source/ai/Player_UCT.cpp`. The RNG dependency the spec needs (seedable, thread-hash-free) is **already in-tree** (`source/engine/Random.cpp/.h`, RL Task 1).

## 4. The separation convention (recommended)

1. **One branch, one engine, one net.** Keep multicore on `dave-master-jsonclean`. Do active dev in a **git worktree** off it (merge back when stable). Do **not** maintain a long-lived parallel branch — that is what creates sync pain.
2. **Separate by code-path + runtime gate, not by branch.** The live feature activates only on the `FORCE_DSNN`/`use_dsnn.txt` path, which the RL pipeline never triggers → multicore is dormant in RL by construction.
3. **Option A needs no build flag.** It is additive (new files) + runtime-gated; the same `Prismata_standalone` binary serves both — the live drop-in is that build shipped *with* a `use_dsnn.txt`. It never activates in the RL pipeline.
4. **Option B gets a build flag.** B makes `UCTNode`/`UCTSearch` thread-safe (atomics/`deque`/lock-free backprop) — the *shared* search RL runs single-threaded. Gate B's changes behind a VS build configuration (e.g. `Release-UserFacing`) that defines `PRISMATA_TREEPARALLEL`. The **RL pipeline (`Prismata_Testing` + RL self-play `Prismata_standalone`) builds plain `Release`** → original node/search → the proven determinism + the Task 1–5 reviews stay valid. The **user-facing exe builds `Release-UserFacing`**. This is "a flag for the user-facing exe never used in the RL pipeline" — and B is precisely where it's needed.

## 5. Hard rules (protect the RL guarantees)

- **Live path forces argmax.** The live `FORCE_DSNN` path must never set `SelfPlaySampling:true` (the Task-3 sampler). It is off by default, so this holds by construction — but **assert it on the live path** so a future default change can't leak the sampler into friends' games (closes the spec's §3.1 / M7).
- **`Random::SeedThisThread()` is purely additive.** A new function; do **not** modify the existing `Random::Seed()`, which RL's proven move-for-move determinism depends on.
- **Any new `UCTSearchParameters` field must be copied by `clone()`/`deepClone()`.** RL relies on that fork (the sampler fields already are). "Ordered last" is layout hygiene; clone-membership is the correctness bit.
- **Do not let Option B's shared-search changes into the RL build.** Use the §4.4 build flag; if B is ever built into the RL path, **re-run the Task-4 determinism check** (byte-identical seeded self-play) before trusting RL results.
- **`config.txt` is shared + strict JSON.** Multicore's config-path keys (`SearchThreads`) are distinct from Tournament's `Threads` (spec §4.2) — keep them distinct. No comments anywhere in the file.

## 6. Sequencing

- **Read-only research (spec → plan) can start now** — zero conflict with the in-flight RL session. Re-pin all `file:line` citations to a named SHA (e.g. `9c64813`) since RL shifted numbers in the RL-hot files.
- **Implementation** (worktree, real edits) should branch off a **named** `dave-master-jsonclean` commit and **rebase onto latest RL + retest** before each milestone (spec §9). Option A first (clean); decide B on the §7 depth-prize + §8 gates.
- **Net/iterator promotion to friends** happens only after an RL GO for that widening (§2 rule).
