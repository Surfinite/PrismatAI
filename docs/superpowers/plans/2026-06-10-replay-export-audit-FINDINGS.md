# C++ Replay Export — Audit Findings + Future-Schema Data-Sufficiency (2026-06-10)

> ## ✅ RESOLUTION STATUS (2026-06-12 — added after the fact; the body below is the unmodified historical record)
>
> The §0 recommended change set is implemented (dave + main repos; engine rebuilt; scratch-validated
> end-to-end: 263/263 gz sidecars valid, 8/8 replay↔shard pairs same-game at Threads:8, turn-start
> rule 34/34, parity gate ALL PASS on .gz at 1.17e-06, preflight 9/9, repo tests 214/214).
>
> | Item | Status | Notes |
> |---|---|---|
> | §0.1 archive parity sidecars per iteration | **DONE + gzipped (owner request)** | exporter writes `sp_*.json.gz` (shared `GzipUtil.h`) into PER-export-dir `<dir>_parity` (adversarial review caught a blocker in the first cut: the shared sibling dir let the two same-launch regime-v2 blocks overwrite each other's `sp_0000_*`); `run_iteration.ps1` stage 1.5 archives both flat (slice-prefixed `general_`/`forced_`) into `rl_iter_<K>/parity_states/`, with same-K re-run orphan-move; stage 5 reads the archive; `dump_value_batch.py` reads .gz + stem-dedupes + cleans its inflate scratch; `calibrate_n.py` clears per-block + legacy dirs |
> | §0.2 saveReplays on RL self-play, per-iteration dirs | **DONE** | both regime-v2 blocks save replays (two live dirs — per-Tournament counters); stage 1.5 archives to `rl_iter_<K>/replays/{general,forced}/`; leftovers orphan-moved to `training/data/_orphans/`, never deleted |
> | §0.3 trailing `turnBoundaries` sentinel (V1/RC-1) | **DONE (writer + bundle generator)** | dropped at finalize; `len(turnBoundaries)==turns` now matches the JS convention. Ladder `/replay/local` clamp was already DONE (ladder `ed58edb`) and is now back-ported into the main-repo generator `js_engine/build_viewer_bundle.js` so a bundle regen can't revert it. `replay_to_html.js` deliberately not patched (legacy per owner — fine on post-fix replays, next-turn crash only on the 676 pre-fix sentinel replays) |
> | §0.4 provenance stamp (RC-3) | **DONE (v1 subset)** | `formatVersion:1` + `gameIndex` + `savedAtUtc` + `meta{tournament,seed,threads}`. NOT included: engine rev + per-player WeightsFile (the ladder TODO's full ask) — iteration identity comes from the archive dir; extend if needed |
> | §0.5 finalize() return checked | **DONE** | failure now logged loudly (R7) |
> | §0.5 HUD charge gate (F3) | **DONE** | gates on CURRENT charges (mirrors Card.cpp:681 + StateHelper); the false beginTurn-refresh comment removed |
> | F6 sniper `*` pMA gate | **DONE** | Apollo-only (SWF pMA ground truth); Deadeye=netherfy, outside both sides' count paths |
> | O1 replay↔V2 counter pairing | **DONE** | ONE shared per-game id; verified 8/8 at Threads:8 |
> | R11 equivalence tripwire | **DONE (better form)** | per-move end-state fingerprint compare (turn/player/phase/counts/resources) — a diverged replay is dropped loudly, never written corrupt |
> | §0.5 numTurns off-by-one (F2) | **DOCUMENTED, deliberately NOT changed** | emitting `+1` would corrupt `GameState::initFromJSON` re-extraction (the parser consumes `numTurns` as the engine turn number). Consumers MUST use the explicit `turn` field, never `numTurns` parity — documented in oracle_diff.md |
> | **Outstanding from §4 (owner to decide — see the implementation summary)** | — | mid-turn `damage` parser discard (F3-§3, turn-start unaffected); policy-alternatives stamping (F5/S2); deadness coarse (F5); mana letter-order cosmetic (F4); memory/deflate level on 200-turn games (R8/RC-9); manual-rerun overwrite outside the orchestrator (O2 residual); old 676 replays unmigrated; ladder-viewer clamp (separate workspace) |

> **Scope.** Full audit of the `--save-replays` C++ snapshot serializer in PrismataAI-dave-master
> (`source/testing/ReplaySerializer.{h,cpp}` + `TournamentGame`/`Tournament` hooks, merge `c8dad50`),
> plus the owner's strategic question: *can past self-play be re-used for supervised training of a
> FUTURE feature schema?* Method: lead-auditor full code read → 4 parallel investigators
> (re-application correctness; field fidelity vs JS engine/SWF; future-schema sufficiency;
> consumers/sizing) → empirical experiments in the isolated scratch bin. Raw agent output:
> `eval/_audit_scratch/replay_audit_results.json`. Empirical artifacts: `eval/_audit_scratch/`
> (perfA/perfB runs, `game_0000_cpp.html` render test).

---

## 0. Bottom line

**The serializer itself is sound — the capture mechanism is *exactly* faithful** (verified three
independent ways, §2). One real consumer-facing bug exists (the trailing `turnBoundaries` sentinel
crashes next-turn navigation in all three viewers, §4-V1), plus a handful of display-only HUD
derivation deltas vs the SWF and some ops gaps (no provenance stamp, counter clobber on re-runs,
silent finalize failure).

**On the strategic question — the RL loop today does NOT retain enough to re-extract training data
for a future schema** (High, §3-S1). The only artifact that survives an iteration is the V2 JSONL/H5,
which freezes the *current* feature definitions (`is_frozen` = binary, construction/delay folded,
HP collapsed, no phase, no sellable, dead units dropped, no action sequence). The two artifacts that
*would* allow future re-extraction both exist but are not retained:

- the **parity sidecars** (`sp_*.json`) — engine-native turn-start `GameState::toJSONString()`
  designed to round-trip through the C++ parser and feed `--dump-v2-record` (i.e. ANY future
  exporter) — are **deleted at every Stage-1** (`run_iteration.ps1:134`);
- **replays are not enabled** on the RL self-play blocks (`RL_Step2_Smoke`/`RL_Cal_N*` have
  `exportTrainingV2` but no `saveReplays`).

**Replay→re-extraction is accurate and verified end-to-end for value training** (§3-S2): replay
`states[]` parse directly through `GameState::initFromJSON`; turn-start states are recoverable by
the rule `states[p==0 ? 0 : turnBoundaries[p]−1]`; verified **34/34 plies** (my run) and **96/96
plies** (independent agent) identical to the V2 exporter's records across turn number, active
player, all resources, attack, and the full alive-instance multiset; every v2.2.1 instance feature
and all 15 globals are exactly derivable from the replay fields.

**Performance: enabling `saveReplays` during self-play is effectively free** (§5): a same-seed
identical-games A/B measured the overhead *below ambient noise* (the replay arm finished 12 s
*faster* over 16 games); static analysis bounds it well under 1% of an N=256 turn; ~45–56 KB
gzipped per game (~100 MB per 2,000-game iteration).

### Recommended (do-not-implement-here) change set, in order

1. **Archive the parity sidecars per iteration** instead of deleting them — replace the
   `Remove-Item "$parityStates/sp_*.json"` at `run_iteration.ps1:134` with a move into
   `training/data/rl_iter_$K/parity_states/` (keep wiping the live dir pre-run; `sp_<game>_<ply>`
   names restart per run and would silently overwrite). This alone makes every future schema
   re-extractable via the already-existing `--dump-v2-record` path. (~300 KB/game uncompressed;
   gzip if it matters.)
2. **Enable `saveReplays` on the RL self-play block, into per-iteration dirs**
   (`asset/replays/rl_iter_K/`, set by the orchestrator like the H5 layout). Do NOT just add a
   stage-1 clear — replays are the iteration's forensic record. Cost ~100 MB / 2k games.
3. **One-line serializer fix**: drop the trailing `turnBoundaries` entry equal to `states.Size()`
   in `finalize()` (§4-V1) — it crashes next-turn navigation in `/replay/local`,
   `replay_to_html.js`, and `build_replay_viewer.js`. (Optionally also clamp in the viewers.)
4. **Stamp provenance into the replay header** (additive keys: formatVersion, engine rev, seed,
   iteration label, per-player WeightsFile/N) — the ladder viewer's own TODO
   (`page.tsx:16-18`) already asks for exactly this; zero consumer changes needed.
5. Smaller fixes: check `finalize()`'s return (currently ignored — silent replay loss); fix the
   dead HUD charge gate (§4-F3); add `numTurns` to `GameState::toJSONString()` so sidecars carry
   the turn number (today only recoverable from the `sp_*_<ply>` filename); if cross-referencing
   replay↔shard by index ever matters at Threads>1, unify the two game counters (§4-O1).

---

## 1. What the export actually is (for the record)

Snapshot-based, harness-driven, engine-untouched. After each real turn, `TournamentGame` re-applies
the just-played `Move` action-by-action on a clone of the pre-move state (off the think-timer) and
serializes one frame per action (`TournamentGame.cpp:157-175`). Output:
`<dir>/game_NNNN.json.gz` (miniz raw-deflate + hand-built gzip wrapper — byte-level verified,
CRC32/ISIZE correct) containing `{replay, p0, p1, winner(0/1/-1), winnerName, turns, cardSet,
states[], actions[], turnBoundaries[]}`. Each state: mana strings, turn/numTurns/phase/glassBroken,
buy-panel supply arrays, `table[]` of 15 per-instance fields (synthetic monotonic `instId` remap
over the engine's recycled CardID slots — previously verified 0-reuse over 2.25M instances), plus
display-only HUD fields (attack/chill potentials, gold estimates) ported from `StateHelper.js` /
`replay_exporter.js`. `actions[]` are `Action::toHistoryString()` numeric tuples
(`"player type id targetId"`) carrying RAW recycled CardIDs (documented; display-only today).

## 2. Core correctness — CLEARED (the strongest result of this audit)

**Capture-by-re-application reproduces the real game trajectory exactly.** Three independent proofs:

1. **By construction** (code): `Game::playNextTurn` = `getMove` + `doMove` only; `doMove` applies
   the recorded Move solely via `GameState::doAction` (`Game.cpp:36-81`) — the identical call the
   harness re-runs on the clone. Action resolution is **RNG-free** (the engine's only `Random::`
   call is the card-set draw in `setStartingState`, `GameState.cpp:2079`, pre-capture). **Every**
   phase transition, including `beginTurn`, runs *inside* `doAction`'s END_PHASE/WIPEOUT cascade
   (`GameState.cpp:687/756/1329-1444`) — nothing auto-advances outside it, so the clone cannot miss
   transitions. `GameState` is a value-type deep copy; `Player::getMove` takes `const GameState&`.
2. **Empirically (this audit, same-seed paired run)**: for game 0 of the perfB run, all **34/34**
   V2 turn-start records match the replay state at `turnBoundaries[p]−1` on turn number, active
   player, all 5 resources both players, attack, and the alive-instance multiset.
3. **Empirically (independent agent, pre-existing rl_smoke replays)**: 3 games / 96 plies,
   zero mismatches; card sets and winner↔outcome_p0 also match.

`states[0]` is the post-first-`beginTurn` initial state and equals V2 ply 0. The **turn-start index
rule** for any re-extraction consumer: **ply p → `states[p==0 ? 0 : turnBoundaries[p]−1]`**, and
`actions[i]` is the action that produced `states[i]`. Caveat (Low): the equivalence is never
runtime-asserted (the replay loop ignores `doAction`'s return) — an engine change that broke it
would be silent; a cheap defense is asserting the re-applied final state hash equals the live one.

## 3. The strategic question — data sufficiency for a future schema

### S1 (High) — As deployed, no future-proof artifact survives an iteration
`run_iteration.ps1` keeps only `selfplay_iter_K.jsonl` + `.h5`; the sidecars are deleted at Stage-1;
the RL blocks don't save replays. The V2 record bakes in current definitions — irreversibly
collapsed relative to the engine state: chill **amount** (binary `is_frozen` only,
`V2Record.cpp:96`), construction-vs-delay split (`max()` only, :79), health-vs-damage split,
role granularity incl. sellable, phase, dead units (filtered), targeting, and the per-action move
sequence. **If the schema evolves, past self-play cannot be re-extracted — it would have to be
regenerated with the old weights, which is expensive and (think-time/threading) not exactly
reproducible.** Recommendation: §0 items 1–2. Keep the JSONL as the *label+telemetry* carrier
(outcome, ig/sampled/argmax/root stamps — things states can't hold) paired with archived states as
the *feature* source.

### S2 — "Full replay → re-extract" is accurate for VALUE training (verified), with three caveats
The C++ state parser consumes replay states directly (`GameState::initFromJSON` ignores unknown
top-level keys; `cardName`=UIName resolves via `GetCardType` name-or-UIName matching;
role/disruptDamage/charge/delay/lifespan/constructionTime/health/deadness all consumed; mana strings
parse; `numTurns` parsed). All 15 globals + every v2.2.1 instance feature are exactly derivable.
Outcome labels are self-contained (`winner` 0=white=P0). Caveats:
1. **Turn-start states only.** The parser silently **discards `damage`** (`Card.cpp:167` — empty
   branch) and never restores targeting state, so MID-TURN re-extraction (e.g. defense-phase states
   with partially-damaged non-fragile blockers — 11 such frames in the sample game, all mid-turn)
   would be corrupted. Turn-boundary states are clean (damage resets at `beginTurn`).
2. **Policy targets are partially recoverable.** `actions[]` tuples are machine-parseable (better
   than the docs imply) but carry raw recycled CardIDs that don't map onto a re-parsed state. Two
   unverified recovery routes exist (whole-game deterministic re-simulation; per-action state
   diffing — the replay has one state per action). **Root alternatives / sampled-vs-argmax are
   permanently lost** unless stamped at generation (the JSONL stamps only the scalar indices, not
   the move list they index).
3. Fields unrecoverable from *every* artifact: causeOfDeath granularity, the raw
   `m_abilityUsedThisTurn` flag (the `role` field carries the v2.2.1-equivalent signal),
   pending-target state. None is used by any current or proposed feature.

### S3 — Artifact comparison (per ~30-turn self-play game)

| Artifact | Granularity | Size | Future-schema re-extraction | Retained today? |
|---|---|---|---|---|
| V2 JSONL | turn-start, current features | ~11 KB | **No** (schema-frozen) | **Yes** |
| Parity sidecar `sp_*.json` | turn-start, engine-native state | ~300 KB raw (~31-39 files) | **Yes — designed for it** (`--dump-v2-record`); needs `numTurns` fix or filename-ply | **No — deleted each iteration** |
| Replay `game_*.json.gz` | **per-action** states + outcome + metadata | ~45–56 KB gz | **Yes** (turn-start rule verified; mid-turn caveat) + human-viewable | **Not enabled** for RL blocks |

## 4. Audit findings (severity-ordered)

### V1 (Medium) — Trailing `turnBoundaries` sentinel breaks next-turn in ALL three viewers
The serializer pushes a boundary after every turn including the last → `turnBoundaries[-1] ==
states.length` (sample: 31 boundaries / 352 states, last = 352). JS-produced replays never contain
this (the JS writer pushes *before* each turn). The shipped ladder bundle's `nextTurn()`
(`prismata-engine.js:9205-9214`) takes the sentinel unclamped → `states[352]` = undefined →
TypeError + wedged index; `replay_to_html.js:1000-1008` and `build_replay_viewer.js:1297-1304` have
the identical pattern. The in-code comment "harmless for the scrubber"
(`TournamentGame.cpp:162-164`) is **wrong**, and `oracle_diff.md` never checked boundaries.
*Fix:* pop the final boundary in `finalize()` if `== states.Size()` (also restores
`boundaries.length == turns`, the JS convention); clamp in viewers as defense. Existing 676 replays
only matter if turn-scrubbed.

### F2 (Medium) — `numTurns` is off-by-one vs the JS/SWF convention; parity relation inverted
C++ emits `getTurnNumber()` (first state `(turn 0, numTurns 0)`); JS replays satisfy
`turn == (numTurns+1) % 2`, C++ satisfies `turn == numTurns % 2`. Currently inert (the viewer
renders from the explicit `turn` field) — and *internally* consistent with the V2 exporter's
`turn_number` (good for re-extraction) — but any consumer deriving the active player from
`numTurns` parity gets the wrong player on C++ replays (the ladder code documents this exact trap
at `PuzzleController.ts:57-59`). *Fix:* emit `+1` to match, or document loudly + never use parity.

### F3 (Medium) — HUD charge gate is dead code; depleted charge units over-counted vs the SWF
`abilityUsable` gates on `usesCharges() && getStartingCharge() < getChargeUsed()` — unsatisfiable
(`usesCharges` = startingCharge>0; `chargeUsed` is constant 1), and its justifying comment
("beginTurn refreshes m_currentCharges") is false (`Card::beginTurn` never writes charges; the
engine's own gate at `Card.cpp:681` uses **current** charges, as do StateHelper.js/SWF). Effect:
`maxAttack`/`oppAttackPotential` overstate by up to +7 per depleted Tia Thurnax vs what the live
client shows. **Display-only** (re-extraction never reads HUD fields) but it is a number in the
replay that is wrong vs the live derivation. *Fix:* gate on `c.getCurrentCharges()`.

### O1 (Medium) — Threads>1: `game_NNNN.json.gz` and `selfplay_NNNN.jsonl` can be DIFFERENT games
Two independent atomics (`Tournament.h:19-20`); adjacent `fetch_add`s (`Tournament.cpp:290,294`) can
interleave across workers. Threads:1 is guaranteed aligned (verified empirically on rl_smoke).
Latent today (all dual-export blocks are Threads:1) — but becomes live the moment the (recommended)
Threads:8 self-play flip lands with replays enabled. *Fix:* one shared counter, or stamp the game id
inside both artifacts (the provenance block of §0.4 covers this).

### O2 (Medium) — Replay dirs: counter resets per run + silent truncate-overwrite + nothing clears them
Same class as the V2-shard E8 findings. `run_iteration.ps1`/`calibrate_n.py` clear shards and
sidecars but know nothing of replay dirs. *Fix:* per-iteration dirs (§0.2); never a blanket clear.

### O3 (Medium) — No provenance/version stamp in the replay header
Header carries only p0/p1 names ("RL_SelfPlay" vs "RL_SelfPlay" in self-play!) — no engine rev,
seed, weights, N, iteration, or format version. The ladder viewer's TODO explicitly requests
player-config fields. Same provenance gap class as the RL-loop audit's P-1. *Fix:* §0.4.

### Low / cleared (compact)
- **finalize() bool ignored** (`TournamentGame.cpp:194`) — disk/compression failure loses the
  replay silently. One-line check + stderr line.
- **Memory**: whole-game rapidjson DOM until finalize — ~18–25 MB per typical game; worst-case
  200-turn-limit game ~60–260 MB, transient deflate spike on top; only matters if several monster
  games finalize concurrently at Threads:8. No cap/flush; acceptable on the x64 build — consider
  level-6 deflate if 200-turn games become common.
- **Mana strings**: same format family, **not byte-identical** to JS (`HBCGA` letter order vs JS
  `HGBCA`; empty pool `""` vs `"0"`). Semantically equivalent; both parse; cosmetic only.
- **Sniper "*" suffix — UPGRADED after ladder-workspace review (Low → same class as F3, user-visible).**
  The C++ `maxSnipers`/`oppSnipers` count every ready snipe unit (`ReplaySerializer.cpp:206-209`, no
  `potentiallyMoreAttack` gate — not exposed via CardType, as the code comment admits), and the
  ladder viewer renders a `*` on the midline attack number whenever they are nonzero
  (`BoardRenderer.ts` `getPlayerAttack` :78/:87 → `formatAtk` ~:1085-1090, mirroring SWF
  `UIAttackDefenseLayer.getAttackText`). The live client (StateHelper.js:174-176/:416-419, per SWF
  card data) counts only `potentiallyMoreAttack` snipers. Ranked snipe units: **Apollo has
  `potentiallyMoreAttack:1` (matches), Kinetic Driver does NOT** (90.bin) — so a board with a ready
  Kinetic Driver and no Apollo shows `[N*]` in C++ replays where the live client shows `[N]`.
  Display-only; fix = gate on a small hardcoded pMA set (only 2 ranked snipe units) or plumb the
  flag through CardType. Note: the sniper count also sits inside the dead F3 charge gate, but that
  overlap is **vacuous on current data**: no unit on either side's sniper-count path uses charges.
  Precision (after a follow-up probe): **Deadeye Operative** — a charge-3 "sniper" in game terms —
  is NOT a `targetAction:"snipe"` unit; its ability is the dedicated `abilityNetherfy` flag (dave
  codename "Nether Warrior"), which the C++ engine special-cases into a conditional destroy-script
  (kill 1 non-blocking enemy Drone, `CardTypeInfo.cpp:84-95`) with no targetAbility, and which the
  JS/SWF sniper-count path never inspects (StateHelper counts only `TARGETACTION_SNIPE` + pMA;
  Deadeye has no pMA in 90.bin — consistent, since killing a non-blocking Drone cannot raise
  attack-through). So Deadeye is excluded from `maxSnipers`/`oppSnipers` on BOTH sides, by different
  mechanisms, and contributes nothing to any other HUD field (destroy effect: no attack/gold
  receive). The ranked `targetAction:"snipe"` set is exactly {Apollo (pMA), Kinetic Driver (no
  pMA)}; the dead charge gate's real blast radius stays confined to attack amounts
  (Rhino +1 / Tia +7 / Sentinel +1 / Bombarder +3).
- **deadness** coarse alive/dead (documented; viewer-compatible; richer reasons deferred).
- **Discarded games**: both export streams drop without finalize — no orphan files; index gaps
  align at Threads:1 only.
- **Cleared as Non-issues**: gzip wrapper byte-correct (CRC/ISIZE verified); winner/draw/turn-limit
  mapping correct; `create_directories` race safe on MSVC; viewer field-by-field compatibility
  (every consumed key emitted; instId monotonicity assumption honored; 'breach'/'swoosh' phases
  handled — C++ replays actually render breach *better* than JS ones); supply arrays match the JS
  writer semantics exactly (max + spent; v2.2.1 "remaining" derivable identically);
  `blocking == Card::canBlock()` matches the JS `inst.blocking` truth table for alive units (the
  v2.2.1 semantics); `replay_to_html.js` and `build_replay_viewer.js` read `.json.gz` directly
  (render test passed this audit, 6.3 MB HTML, exit 0); C++ omits 4 instance fields the JS writer
  emits (cardType/isFragile/autoClicked/defaultBlocking) — viewer meta-fallback covers them;
  econ-estimate resonate port is *closer* to the SWF than the JS writer it ports.

## 5. Performance (empirical + static)

Same-seed A/B in the isolated scratch bin (`AUDIT_PERF_A/B`: RL_SelfPlay_N256 self-pair, rounds:8 →
16 games, Threads:1, ForcedCards Hotel, both arms exporting V2; B additionally `saveReplays`).
**Game-identity verified**: per-game (records, outcome, plies, card set) signatures identical across
arms. Wall-clock: A = 2m58s, B (with replays) = **2m46s** — the replay arm was *faster*, i.e. the
overhead is below ambient noise (concurrent workload on the box; at `TimeLimit:0` think cost is
CPU-bound). Static bound agrees: per turn the serializer re-applies ~12 actions + serializes ~12
states (linear scans) vs an N=256 UCT search doing two-orders-of-magnitude more action work; the
pre-move clone is already paid by the V2 exporter. Finalize deflate ≈ 0.2–1.4 s once per
multi-minute game. **Sizing** (from all 676 existing replays): mean 56 KB gz/game (123 B/state,
~110:1 ratio); projections: 128 games ≈ 6–7 MB; 2,000 ≈ ~100 MB; 10,000 ≈ ~500 MB per iteration.

## 6. Empirical appendix (all under `eval/_audit_scratch/`, owner artifacts untouched)

| Check | Result |
|---|---|
| Same-seed A/B (16 identical games, N256) | replay overhead < noise (B faster by 12 s); 16 replays mean 57 KB gz |
| V2↔replay turn-start alignment (game 0, 34 plies) | 34/34 exact (turn, active player, resources, attack, instances) |
| Agent cross-check (rl_smoke, 3 games, 96 plies) | 96/96 exact; winner↔outcome_p0 consistent |
| `replay_to_html.js` on a C++ `.json.gz` | renders (6.3 MB HTML, exit 0) |
| gzip wrapper | decompresses via python gzip; CRC32/ISIZE verified |

Also noted: the prior audit session's `Tournament_AUDIT_X1_*` runs (Jun-9 05:47–06:41, files in
`eval/_audit_scratch/`) most likely explain the E8-3 "missing parity-file prefix" anomaly from the
RL-loop audit — its empirical runs overlapped the sidecar dir's 07:20 mtime window.
