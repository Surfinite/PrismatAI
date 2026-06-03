# External-Review Context — Multicore DSNN Play (Options A + B)

> Companion to the plan: `2026-06-03-multicore-dsnn-play-design.md`. Reviewers receive **both** documents.
> Reviewers have **no access to the codebase** — everything needed to judge the plan is here. The plan author has full codebase access and will validate every suggestion against the real code in a meta-review.

---

## 1. Reviewer Brief

You are reviewing a **design spec** for a C++ game-AI feature. You have two documents: this context doc and the plan. Your job is to **critically analyze the plan** — not rubber-stamp it.

Identify: weaknesses, risks, missing considerations, better alternatives, unnecessary complexity, things to remove, and things that are good and must be preserved. Suggest additions, future features, and architectural improvements. Be constructively critical and **specific** — reference section numbers from the plan. Your review feeds a synthesized meta-review.

You do **not** have the codebase. Flag where limited visibility forces you to assume something about the code, and state the assumption — the author will verify it.

### Review Output Format
1. **One-line verdict.**
2. **What's good** (keep as-is, and why).
3. **Concerns & risks** (ranked by severity).
4. **Suggested changes** (specific, actionable; cite plan §).
5. **Alternatives** (other approaches worth considering).
6. **Additions** (missing things that should be there).
7. **Removals** (things that shouldn't be there).
8. **Minor / nits.**
9. **Assumptions you're making** (where you lacked code visibility).

Don't soften criticism. The goal is to improve the plan.

---

## 2. Project Overview

**The project** is a standalone C++ engine + AI for **Prismata**, a turn-based, perfect-information strategy card game by Lunarch Studios. The engine fully simulates Prismata; the AI plays it via search (UCT/MCTS and alpha-beta) with several evaluation functions. The codebase originates from David Churchill's open-source `PrismataAI` (CC BY-NC-SA), extended by this project.

A key capability (per the engine's own README): the **Standalone** build produces an executable that **replaces the retail Prismata client's AI executable**, so a custom AI can be played against *inside the real game client*. The retail AI it replaces is colloquially the **MasterBot** (a.k.a. SteamAI; the original 2016 binary is preserved as `PrismataAI.exe.ORIG`).

This project trained a neural-net evaluator and wired it into the UCT searcher to make **"DSNN"** — a DeepSets neural-net value function + UCT/MCTS player. DSNN is deployed as the client drop-in. Recent (correctly-configured) testing puts **DSNN at roughly 50:50 win rate vs the MasterBot** (earlier docs citing a ~30-point deficit used wrong configs and are stale).

**This plan's problem:** the deployed DSNN move is computed on **one CPU thread**. The goal is to make a single move use **multiple cores**, for **stronger play at the same per-move latency** (the search is time-bounded — more cores = more search in the same think-time window, not a faster move).

- **Stage:** mature engine (~45k LOC of C++), actively extended. The AI/search subsystem is stable; a separate RL self-play effort is in flight (see §6).
- **Audience / constraints:** a **"hand it to friends"** Windows build — *not* a public release. Solo developer; cost-conscious; **Windows-only**, **x64-only**. No Linux/macOS target for this feature.

---

## 3. Architecture & Tech Stack

- **Language/build:** C++ (MSVC / Visual Studio, x64). GUI uses **SFML**; JSON via embedded **RapidJSON**. **No external ML runtime** — neural-net inference is a hand-rolled scalar forward pass in C++ (no SIMD/BLAS/GPU). Cross-platform CMake exists (for a Linux training/RL build) but the client drop-in is Windows-only.
- **Sub-projects** (from README): `Prismata_Engine` (game rules/sim), `Prismata_AI` (search + eval), `Prismata_GUI` (SFML), `Prismata_Standalone` (the client-replacement exe — *the target of this plan*), `Prismata_Testing` (tournaments/benchmarks).
- **The deployed AI ("DSNN"):** `Player_UCT` (UCT/MCTS) + `EvaluationMethods::NeuralNet` value eval + a "LiveHardestAI/HardIterator_Root" move generator (a portfolio of partial-player move enumerators). Built at runtime in `AITools.cpp` under a `FORCE_DSNN` override.
- **Live runtime model (critical):** the retail client **spawns the standalone exe once per turn**. The exe reads **one** game state (JSON on stdin), builds the player, computes **one** move, prints the move (JSON clicks) to stdout, and **exits**. There is **no persistent process, no cross-turn state, no thread pool** to reuse.

```
retail client ──(spawns, one per turn)──> PrismataAI.exe
   │  stdin: one JSON game state
   ▼
 main.cpp ─> AITools::InitializeAIAndGetAIMove ─> Player_UCT::getMove
   │            (FORCE_DSNN builds UCT+NeuralNet)      │
   │                                                   ▼
   │                                          UCTSearch::doSearch  (single-threaded loop,
   │                                          time-bounded ~10s; per-leaf NeuralNet eval)
   ▼
 stdout: one JSON move ─> process exits
```

- **Key decisions already made & why:**
  - *Hand-rolled scalar NN inference* — keeps the drop-in dependency-free and portable into the retail client; cost is no SIMD/BLAS acceleration.
  - *One-shot-per-move process* — dictated by the retail client's AI protocol (non-negotiable).
  - *Per-thread NeuralNet `clone()` for thread-safety* — the eval has reusable mutable scratch buffers, so concurrency is achieved by giving each thread its own cloned net (already used to run many tournament games concurrently).
  - *Search budget is wall-clock time*, not a fixed iteration count.

---

## 4. Codebase Map

Engine repo: `PrismataAI-dave-master` (branch `dave-master-jsonclean`). ~45,300 LOC across `source/`.

| Dir | Files (.cpp/.h/.hpp) | Role |
|---|---|---|
| `source/ai/` | 179 | search, eval, neural net, players, move iterators |
| `source/engine/` | 59 | game rules, `GameState`, RNG |
| `source/testing/` | 17 | tournament/benchmark runners |
| `source/standalone/` | 2 | the client-replacement exe (`main.cpp`) |
| `source/gui/` | 19 | SFML GUI |
| `source/rapidjson/` | 14 | vendored JSON |

**Files most relevant to the plan** (LOC):
- `source/ai/UCTSearch.cpp` (513) — the MCTS loop (`doSearch`), node selection, leaf eval, backprop.
- `source/ai/UCTNode.cpp` (253) / `UCTNode.h` — tree node: children stored **by value** in a `std::vector<UCTNode>`, raw `_parent` back-pointer, non-atomic visit/win counters.
- `source/ai/UCTSearchParameters.hpp` (135) — search config; `clone()/deepClone()` deep-copies move iterators **and the NeuralNet** (the per-thread isolation primitive).
- `source/ai/NeuralNet.cpp` (882) / `NeuralNet.h` — hand-rolled forward pass; per-instance `mutable ScratchBuffers _scratch`; `clone()` copies weights + fresh scratch; a singleton `Instance()` used only as a fallback.
- `source/ai/Player_UCT.cpp` (40) — rebuilds a `UCTSearch` each `getMove`.
- `source/ai/Player_RootParallelAlphaBeta.cpp` (232) — an **existing** root-parallel player using `std::async` fan-out over root children, for alpha-beta + playout eval (no NeuralNet branch). The structural template for Option A.
- `source/ai/AITools.cpp` (932) — builds the live DSNN player; `FORCE_DSNN` override; `use_dsnn.txt` sentinel + env-var overrides; the single wiring point for thread-count injection.
- `source/standalone/main.cpp` (230) — the one-shot entry; stdin→move→stdout; redirects stdout→stderr during search to keep the JSON line clean; has `--test-rng`/`--test-sampler`/`--dump-features` self-tests.
- `source/engine/Random.cpp` (66) — `thread_local mt19937_64`, seeded by an atomic sequence counter (thread-hash-free), seedable as a pure function of the seed.
- `source/testing/Tournament.cpp` — runs many **games** concurrently via `std::async` with `clone()`d players (the proven concurrency precedent); reads a `"Threads"` config.

---

## 5. Existing Patterns & Conventions

- **Style:** clang-format, Allman braces, 4-space indent, 120-col.
- **`PRISMATA_ASSERT` is a soft assert** — it *prints* and does **not** abort. Important: stray prints can corrupt the single-line JSON the client expects, so `main.cpp` redirects stdout→stderr during the search window and restores it before printing the move.
- **Thread-safety via `clone()` deep-copy discipline** — the established pattern. Tournaments already run `getMove` concurrently across game threads, each with a cloned player (→ cloned NeuralNet → private scratch). No locks on shared search state today because nothing is shared.
- **Config:** JSON `config.txt` parsed by `AIParameters`; per-player `WeightsFile`. Runtime overrides via env vars (`PRISMATA_FORCE_DSNN`, `PRISMATA_DSNN_WEIGHTS`) and a `use_dsnn.txt` sentinel file located next to the exe.
- **RNG:** `Prismata::Random` free functions over a `thread_local` engine; no global `rand()`.
- **Testing:** tournament/matchup harness with paired, colour-balanced games and (per the concurrent RL work) CI-based "positive beyond noise" comparisons; parity/oracle diff tooling; built-in `--test-*` self-tests in the standalone. No xUnit-style framework.

---

## 6. Current State & Known Issues

- **Works today:** DSNN runs end-to-end as the live client drop-in (sanctioned swap-in path); ~50:50 vs MasterBot; tournaments run many games concurrently without corruption.
- **The relevant limitation:** the per-move UCT search is **strictly single-threaded** — `UCTSearch::doSearch` has no `std::thread`/atomics/locks. This plan adds the first intra-move parallelism.
- **NN forward is scalar** (no SIMD/BLAS) — dominates per-traversal cost; relevant to Option C-style batching (which the plan rejects) and to how much extra search a core actually buys.
- **Concurrent RL self-play effort (in flight, same engine repo):** an RL self-play loop is *being implemented now* on `dave-master-jsonclean`, with uncommitted edits to `UCTSearch.cpp`, `UCTSearchParameters.hpp`, `AIParameters.cpp`, `config.txt` (temperature sampler, action-space widening, etc.). The **RNG was recently made thread-hash-free + seedable and is committed** — the plan's §4.3 reflects this. **Coordination point:** Option A also edits `UCTSearchParameters.hpp`; A's worktree should branch off after the RL engine edits land.
- **Reviewer caveat:** the plan's `file:line` citations are "as of audit" against a tree with in-flight RL edits, so exact line numbers are a moving target until RL lands; the *facts* were verified.

---

## 7. Context Specific to the Plan

- **Touched/depended-on code:** `UCTSearch`/`UCTNode`/`UCTSearchParameters` (the search and its config), `NeuralNet` (eval + clone), `AITools` (wiring + config), `standalone/main.cpp` (one-shot path + stdout redirect), `Random` (per-worker seeding), `Player_RootParallelAlphaBeta` (template for A), `Tournament` (concurrency precedent + the A/B harness).
- **Prior/related work:** no prior multicore-search attempt. The project has done extensive *parity* investigation (engine versions, opening books, partial-player variants) concluding DSNN is now ~parity with MasterBot under correct configs. A 5-variant ability portfolio (`HardIterator_5var_Root`) was recently validated as a single-tree strength improvement.
- **External systems:** the retail Prismata client (spawns the exe per turn); the concurrent RL training pipeline (shares the engine repo + RNG interface).
- **Performance/scale:** search is wall-clock-bounded (~10s/move live). Per-traversal cost ≈ one scalar NeuralNet forward. x64 build ⇒ the old x86 4 GB address-space cap does **not** apply, so per-thread NN weight copies are affordable. Target hardware: AMD Ryzen 7 5700X3D (8 physical cores / 16 threads, large 96 MB 3D V-cache).

---

## 8. Scope Boundaries

**Out of scope (don't suggest pulling these in):**
- RL self-play **throughput** — RL parallelizes by running ~8 single-threaded games at once (more on cloud), not by multicore-per-move.
- Self-play **data quality** as a success criterion.
- **Cross-turn tree persistence** — impossible: the process is one-shot per move.
- **x86**, **Linux/macOS** targets for the drop-in.
- Hand-rolled `__cpuid` core counting (Windows API is used instead).

**Fixed / non-negotiable (don't propose alternatives):**
- Windows-only, x64-only drop-in.
- One-shot-per-move process model.
- Three-gate, CI-based "positive beyond noise" success methodology (no hard numeric thresholds).
- A-first sequencing (ship/measure A before committing to B), with B gated on a prerequisite test + this review.
- For Option A: the **ensemble** variant (every worker explores all root children) and **merge by summed root-child visit counts**.

**Deliberately accepted trade-offs:**
- Option A is *variance reduction*, not deeper search — it is **not expected to meet** the "8×-multithreaded ≈ single-thread-at-8×-think-time" bar (that's precisely why Option B exists and is the bar-meeting design). A's value is being cheap, low-risk, shippable, and a measuring stick.
- Per-worker NeuralNet weight duplication (memory/clone cost) is accepted on x64.
- Multithreaded moves are non-deterministic run-to-run (RNG diverges per worker); single-thread mode stays reproducible for parity testing.

---

## 9. Success Criteria

CI-based, no hard thresholds; anchors = the narrow baseline `DSNN_Mixed35_5var` and the real MasterBot (`STEAMAI`/`.ORIG`).

1. **Pre-test (gates B):** single-thread think-time sweep 1×/2×/4×/8× (with the traversal cap raised so it doesn't clip 8×). If 8× think-time doesn't beat 1× beyond the CI, **neither A nor B is worth building**.
2. **Option A gate:** A@physical-cores beats single-thread at the same wall-clock, beyond noise; report the fraction of the 8×-think-time ceiling captured.
3. **Option B gate:** B@cores beats single-thread beyond noise **and** is meaningfully ahead of A; ideally approaches the 8× ceiling.
4. **Cross-cutting safety:** thread-safety **equivalence** (T1 ≈ T8 = no correctness regression) + a clean single-line-JSON output check under threads.

---

## 10. Key Questions for Reviewers

1. **A-vs-B strategy.** Given the user's bar is "≈ single-thread-at-8×-think-time" (which the plan argues only B meets), is building **A first** the right call (low-risk ship + measuring stick), or should the project **skip straight to B**? Is A at risk of being wasted effort if B is near-certain to be needed?
2. **Strength theory.** Is the plan's core claim sound — root-parallel (A) ≈ *variance reduction with an asymptotic ceiling set by single-tree depth*, tree-parallel (B) ≈ *deeper search that tracks the N×-think-time curve*? Are the illustrative magnitudes (A ≈ 2–4×, B ≈ 4–7× at N=8) defensible, or misleading?
3. **B's cost floor.** The plan claims the **node-storage refactor** (moving `std::vector<UCTNode>` by-value children + raw parent pointers to stable storage) is the irreducible prerequisite for sharing one tree, driving the 2–4 week estimate. Is there a cheaper partial tree-parallelization that avoids it? Is the estimate realistic?
4. **A's aggregation.** Is **ensemble + summed-visits** the right merge for root-parallel UCT, versus value-weighted voting, plurality, or summing values? Any failure mode (e.g. mis-keying equal-but-distinct moves)?
5. **Missed concurrency hazards.** Beyond the ones named (shared-NeuralNet scratch race, the `NeuralNet::Instance()` fallback, lazy static-init, virtual-loss tuning), is there a hazard the plan misses — especially given the **concurrent RL edits** to the same files?
6. **Is search even the bottleneck?** With DSNN now ~parity with MasterBot, will more search convert to strength, or is the value network the binding constraint (making the whole effort low-yield)?

---

## 11. Glossary

- **Prismata** — turn-based perfect-information strategy card game; the domain.
- **MasterBot / SteamAI / `.ORIG`** — the retail client's built-in AI (the strong baseline). `PrismataAI.exe.ORIG` is the preserved original binary.
- **Drop-in / swap-in** — replacing the retail client's AI executable with our standalone build so the AI plays inside the real client.
- **DSNN** — the deployed AI: DeepSets **neural-net value function** + **UCT/MCTS** search (`Player_UCT` + `EvaluationMethods::NeuralNet`).
- **UCT / MCTS** — Upper-Confidence-bound Tree search / Monte-Carlo Tree Search: iteratively select → expand a leaf → evaluate → back-propagate.
- **Traversal** — one MCTS iteration (one select-expand-eval-backprop cycle). Here each traversal evaluates one new leaf with one NeuralNet forward pass.
- **Think-time** — wall-clock budget per move (~10s live). The search loops until time (or a traversal cap) is hit.
- **Root-parallel (Option A)** — N independent search trees from the same root, run concurrently, results merged (here: sum root-child visit counts, pick the most-visited). An ensemble; reduces variance.
- **Tree-parallel (Option B)** — N threads grow **one** shared tree; **virtual loss** temporarily penalizes a node a thread is descending so other threads pick different branches (the "don't overlap the searches" coordinator). Deepens the single tree.
- **Virtual loss** — the transient penalty applied on descent and removed on backprop that spreads concurrent threads across the tree.
- **NeuralNet scratch buffers** — reusable per-instance mutable activation buffers; the reason two threads can't share one NeuralNet (each thread needs its own `clone()`).
- **`FORCE_DSNN` / `use_dsnn.txt`** — the override (env var or sentinel file next to the exe) that makes the standalone build the DSNN player; the proposed home for `threads` / `think_time` / `max_traversals` keys.
- **`UCTSearchParameters` / `deepClone()`** — search config object; its deep-clone forks the move iterators and the NeuralNet — the per-thread isolation primitive both options rely on.
- **MoveIterator / `HardIterator_Root` portfolio** — the move generator; the deployed portfolio is narrow (~5 buy variants), which is why Option A uses the ensemble (all-children) variant rather than splitting root children across threads.
- **OB (opening book)** — precomputed opening lines (context only; not central to this plan).
- **Physical vs logical cores** — the target CPU has 8 physical / 16 logical (SMT); the plan defaults thread count to physical because the workload is compute-bound scalar math and the large shared cache favors fewer, fatter workers.
