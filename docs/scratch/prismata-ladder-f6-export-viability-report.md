# Viability Report — Automating client-authoritative Prismata gamestate export (F6 `CurrentInfo`)

**Date:** 2026-06-03
**Produced by:** prismata-ladder session (multi-agent investigation + adversarial verification across both repos)
**Companion to:** [`prismata-ladder-f6-export-viability-prompt.md`](./prismata-ladder-f6-export-viability-prompt.md)
**Question:** Can we programmatically export client-authoritative Prismata gamestates (the F6 dev-mode `CurrentInfo = {mergedDeck, gameState, aiParameters}`, display names) **at scale, without manual keypresses**, to validate the `js_engine`'s **state-identity** against the real AS3 client across the training corpus? This is an assessment only — **nothing was built.**

> **Repos:** `PrismataAI` (this repo: `js_engine/`, decompiled AS3 under `prismata_decompiled/scripts/`, docs, F6 dumps). `prismata-ladder` (sibling at `../prismata-ladder` or `C:/libraries/prismata-ladder`: the headless spectator stack — `prismata_amf3.py`, `headless_multi.py`, etc.).

---

## TL;DR — Verdict

**Do not build either automation path for corpus-scale state-identity validation.** One architectural fact decides it:

> The AS3 client — whether **playing or spectating** — computes the gamestate **locally** by replaying the click stream through its own engine. The server **never** sends a computed `GameState`. The only egress of a client-computed `CurrentInfo` is **F6 → OS clipboard**, gated behind a dev build.

Consequences:
- **Path 1 (live-spectator harvest of server states): not viable.** The wire carries *moves*, not states. There is no cheap live oracle.
- **Path 2 (automated F6 over historical replays): possible but not worth it.** It is a brittle, single-instance, foreground-focus-stealing **GUI keystroke macro** on **EOL Adobe AIR**, with a live-server dependency and unmeasured (~hundreds/hour, serial) throughput. The corpus is ~1.6M+ extraction points; the spend it protects is a deliberately small ~£400/$500-month go/no-go.
- **A third option is already built and adopted — the C++ engine parity gate** (RL plan Task 5 Step 6) — which gives broad, headless, fast JS-vs-C++ state-identity coverage. The only residual it can't close (AS3-client-truth on human-replay state patterns) is exactly what a **small, targeted manual F6 sample** addresses.

**Recommendation:** Keep state-identity validation as **(a)** the C++↔JS parity sweep over a random/stratified sample of human replay codes (headless, no client) + **(b)** a small set of *fresh* manual F6 dumps as the AS3 tiebreaker. Treat F6 as a scalpel, not a corpus-wide tool.

---

## Path 1 — Live-spectator harvesting — NOT VIABLE as a server-state oracle

**Finding (high confidence, verified in current source + cross-confirmed in Python):** the spectated AMF3 stream is **moves only**.

- A spectator runs the identical `MultiplayerGame` code path as a player (`Game.TYPE_OBSERVER`). The complete in-game server→client subscription set is clicks + turn-boundaries: `Click`, `ManyClicks`, `StartTurn`, `EndTurn`, `EndSwoosh`, `GameOver/Draw`, pause/grace — `MultiplayerGame.as:45-62`. The full `NetworkEvent.as` (1-251) constant list contains **no** `State`/`GameState`/`Snapshot`/`Resync` opcode.
- The client computes state locally: `networkClicked → analyzer.networkClick → recordClick → controller.processClick` (`MultiplayerGame.as:204-220`, `Analyzer.as:188-197`); `Game.gameState` is just `controller.state` (`Analyzer.as:80-83`) — the very object F6 serializes.
- **Mid-game join and reconnect also reconstruct locally** (this was the key loophole, and it's closed): `BeginGame` carries `commandInfo.commandList` (click *history*), and `constructInProgressGame → initializeAndPlayInitClicks` replays it from turn 0 (`RaidAnalyzer.as:88-97`, `Analyzer.as:161-169`, `GameInitializationInfo.as:146-150`). No state blob on the wire; reconnect (`SERVER_RECONNECTGAME`) routes through the same path.
- **Python cross-confirmation:** the headless spectator pool (`prismata-ladder/headless_multi.py`, `headless_client.py`) only does `tracker.clicks.append(click)` — zero F6/state code. The *only* place the repo gets a real `CurrentInfo` is `prismata_amf3.py`'s `StartTurn` handler (1496-1556), which **sends F6 to a co-located GUI Windows client and scrapes the clipboard** — i.e. the Path-2 mechanism on live games.

**Two implications that also bound F6 generally:**
1. Reconstructing state from the `commandList` in Python/JS would validate the JS engine **against itself** — useless as an independent oracle.
2. Even a spectator's F6 dump is the AS3 engine's **local recomputation**, not an independent server snapshot. F6 (either path) validates **JS-engine ≡ AS3-engine computation** — it cannot catch a bug present identically in both engines. True triangulation needs a *third* implementation (the C++ engine).

**Effort:** N/A — the desired data does not exist on the wire.

---

## Path 2 — Automated F6 over historical replays — POSSIBLE, NOT WORTH IT at corpus scale

**The within-replay loop is scriptable; the full unattended corpus pipeline is not.** Mechanism, re-verified against current source:

| Step | Mechanism | Source |
|---|---|---|
| Load by code | Server-mediated `Client.sayToServer("MenuReplay", code)` → `BeginMenuReplay` | `UIReplayCodePage.as:82`, `NetworkEvent.as:136`, `GameDispatcher.as:65` |
| Step a turn | `Shift+Right → Replayer2.nextTurn()`, **client-side & instant, no network** | `UIReplayControl.as:73-96`, `Replayer2.as:323-326` |
| F6 dump | Gated on `FlashBuildOptions.developerVersion`; fires from a real focused keypress → `Clipboard.generalClipboard.setData` | `UIKeyboard.as:122-135`, `Game.as:1226-1243` |

**No programmatic hook exists** for any of `watchReplay`/`nextTurn`/`copyGamestate`. The full `ExternalInterface.addCallback` inventory (Auth/Store/AIThreadHandler/Twitch/StartUp) exposes none, and `ExternalInterface` is unavailable in desktop AIR.

**The harness was actually built** — `PrismataAI/tools/capture_replay_states.py` (commit `e98787d`, 2026-02-25, "Phase 2: Add F6 ground truth capture tool"; source later **deleted**, only `tools/__pycache__/capture_replay_states.cpython-313.pyc` remains). It works **only** as a Win32 GUI macro: find the "Prismata" window → `SetForegroundWindow` (steal focus) → `SendInput` synthetic `F6`/`Shift+Right` → poll the OS clipboard with hash-and-wait. Its docstring requires a **human to load + rewind each replay** before the per-turn loop runs. Only ~5 dumps were ever captured with it (all by hand, see below).

**Platform hostility (all verified):**
- **EOL Adobe AIR 20**, Stage3D `renderMode=direct` → needs a **GPU-backed display, not truly headless** (`Prismata/META-INF/AIR/application.xml`).
- Dev mode disables load-balancing and forces a connection to a **dead `amazonAlpha` host** → requires an **admin/UAC hosts-file redirect** with a documented lockout incident (`docs/plans/2026-02-18-prismata-overlay-advisor.md:484-553`); `FlashBuildOptions.as:118-129`.
- **Live-server round-trip per replay load**; **single-session-per-account**; **single-instance** foreground-focus contention; **Steam may overwrite the patched SWF** on update.

**Throughput is an unmeasured estimate.** The only figure in-repo is the old plan's **~0.5s/turn → ~30s per 60-turn game**, and that plan scoped itself to **"10-20 test replays"** (`docs/plans/2026-02-25-replay-state-verification-plan.md:540`). With per-game manual load+rewind, the ~1.6M-record human corpus is a multi-hour human-supervised slog.

**Target format is trivial (the easy part).** `oracle_diff.js` consumes **only** `ci.gameState` (`oracle_diff.js:46`); it builds `initInfo` from the replay's own `deckInfo` and **never reads** `mergedDeck`/`aiParameters` from the dump. The F6 `gameState` matches the JS `State.toString()` shape **field-for-field** (15 scalar/array keys + a `table` of 23-field unit instances keyed by `instId`; `State.js:1657-1690`, `Inst.js:290-360`). **No name mapping needed** (display names throughout — unlike the older C++ path); only `timeRemainingMS` needs an ignore-rule (JS emits -1, F6 emits 0). Each F6 = one turn; full game coverage = `numTurns` dumps (~20-40 typical). **Reshaping is solved; the bottleneck is entirely *capture*.**

**Effort:**
- Resurrect the deleted tool to script the per-turn loop within a manually-loaded replay: **Small** (sufficient for spot-checks).
- Fully unattended corpus-scale exporter (add `MenuReplay` sniffer-injection load + `Home`-key auto-rewind + dedicated GPU Windows VM): **Medium build + brittle ongoing ops**; still a single-instance GUI macro on EOL middleware at low-hundreds states/hour, serial.

---

## ⚠️ How to read the existing F6 dumps (important)

The four dumps in `docs/scratch/` (`F6_test.txt`, `S1gfK-xUO5j.txt`, `VXGaI-n97ZU.txt`, `v+7VV-YOs41.txt`) are **NOT a representative sample.** They are AS3 ground-truth captures of **games that were known to have issues**, made on **2026-05-30** — the same day `oracle_diff.js` was added (`25a4c44`) and most faithfulness fixes landed (`43ea627`, `f0c4dfa`, `94c632c`, `d2363c5`, `8486153`…), with the campaign declared COMPLETE (`dad0183`). They were the verification set that *drove those fixes.*

Therefore:
- Running `oracle_diff.js` on them today: two diff clean (only the benign `timeRemainingMS` -1/0); **VXGaI shows a 2-unit diff** (Cryo Ray snipe ordering: `id=56` role/deadness/dead/health/target, `id=70` chill/disruptorIds). **Do not read this as a current/unknown bug.** It is most likely a **snapshot-alignment artifact** (oracle_diff auto-aligned to "after click 324 / end-swipe", and the F6 was captured mid-snipe between the source-click and the target-click) — pass an explicit `actionIndex` to force a stable phase-boundary comparison before ever calling it a bug — or at most a known hard case from the fix set.
- The legitimate takeaways from these dumps are only: **(1)** `oracle_diff.js` is a real, non-tautological field-by-field diff, and **(2)** the manual-F6 + `oracle_diff` loop is the **already-proven tool** that drove the recent fixes — evidence that *targeted manual F6 was sufficient even for active fix work*, and corpus-scale automation was never needed.
- These known-bad dumps tell you nothing about the **un-bugged majority** of the corpus. For regression confidence, sample *randomly/stratified* and capture *fresh* dumps.

---

## Third option (already adopted) — the C++ engine as oracle

The RL self-play plan already makes a **C++↔JS extractor parity test** the consistency gate (Task 5 Step 6, `docs/superpowers/plans/2026-06-03-rl-selfplay-loop-implementation.md`). The C++ `engine_v1` computes the exact `schema_v2` features for inference (`NeuralNet::dumpFeaturesJSON`, **parity-verified to 1.33e-6 vs PyTorch**) and is "the lineage the real client shells out to." Its `ReplayStepper` already steps **human** replays turn-by-turn and can dump per-turn state (`DoAnalyze` / `--validate-replay`) — **headless, fast, no GUI/clipboard/AIR**.

- **Cheap broad coverage:** JS-vs-C++ state-identity over arbitrarily many human replay codes, zero GUI automation.
- **Its one residual** (and the only honest reason to want F6): C++ is a *reimplementation* that could share a bug with JS, so it isn't literal AS3-client truth. Close that with a **small stratified F6 sample**, not corpus-scale F6.
- Cheaper invariant proxies already in use: recorded `clicksPerTurn.length` vs JS turns; "0 failed clicks". Replay-embedded S3 data is **not** a state oracle (it stores `commandList` + deck only).

---

## Proportionality

- **Corpus:** human = 61,267 ranked-1800+ codes → **1,648,072** per-turn records (the "~1800" is a rating filter, not a game count); +MasterBot 200K+200K games; **~13.47M** examples total. A manual ~20-state spot-check ≈ **1.3×10⁻⁵** coverage.
- **Spend de-risked:** a deliberately small **~£400/$500-month go/no-go** (supervised retrain only ~$15-30). The corpus is the value-net *initialization*, so silent corruption biases the whole signal — but the RL plan itself already classifies corpus-wide F6 automation as **"deferred — build only if the spot-check warrants it."**

---

## Recommendation (actionable)

1. **Broad, headless check:** run the **C++↔JS parity sweep** over a random/stratified sample of human replay codes. This is the backbone — it gives state-identity coverage at scale with no client.
2. **AS3 tiebreaker:** capture a **small set of *fresh* manual F6 dumps** on randomly-picked games (not the known-bad set) and diff with `oracle_diff.js` (add the `timeRemainingMS` ignore-rule). **Resurrect `capture_replay_states.py` from git `e98787d`** to make the per-turn loop painless within each manually-loaded replay.
3. **Do not build** the fully-unattended corpus-scale F6 exporter unless an *external* requirement appears (e.g. a paper needing exhaustive client-truth). If it does, the lowest-effort increment is the Medium build in Path 2, on a dedicated GPU Windows VM.
4. **Remember the ceiling:** F6 only proves JS ≡ AS3-client *computation*; a bug shared by both is invisible to it. The independent C++ engine is what gives triangulation — which is the deeper reason it, not F6, should be the primary gate.

---

## Evidence appendix (file:line)

**Path 1 / protocol (this repo, decompiled AS3):**
- `prismata_decompiled/scripts/client/NetworkEvent.as:48,106,108,122,124,136,148-150,164` — opcode constants; no State/Snapshot/Resync.
- `prismata_decompiled/scripts/client/MultiplayerGame.as:45-62` (subscriptions), `:107-114` (in-progress reconstruct), `:204-242` (clicks→processClick).
- `prismata_decompiled/scripts/mcds/engine/Analyzer.as:80-83` (gameState=controller.state), `:161-169` (commandList replay), `:188-197` (recordClick).
- `prismata_decompiled/scripts/mcds/engine/RaidAnalyzer.as:88-97`; `client/GameInitializationInfo.as:146-150`; `client/GameDispatcher.as:65,115,147`.
- `prismata_decompiled/scripts/starlingUI/UIKeyboard.as:122-135` (F6 gated on developerVersion).
- `prismata_decompiled/scripts/client/Game.as:215-216,224-226,1226-1243` (F6 → CurrentInfo → clipboard).
- `prismata_decompiled/scripts/client/FlashBuildOptions.as:50,118-129` (dev-mode patch target, dead-host, load-balancing).

**Path 2 / replay control + load (this repo):**
- `prismata_decompiled/scripts/starlingUI/game/UIReplayControl.as:41-45,56-97`; `client/Replayer2.as:318-348`.
- `prismata_decompiled/scripts/starlingUI/lobby/lobbyPages/UIReplayCodePage.as:79-83`; `client/Client.as:180-183` (URLReplay); `client/StartUp.as:315-329,597-609`.
- `tools/capture_replay_states.py` @ `git show e98787d` (deleted; `.pyc` in `tools/__pycache__/`).
- `docs/plans/2026-02-25-replay-state-verification-plan.md:25-33,540` (designed pipeline, ~0.5s/turn estimate, "10-20 replays").
- `docs/plans/2026-02-18-prismata-overlay-advisor.md:458-553` (patch confirmed working, hosts redirect, lockout incident, clipboard poll).

**Target format (this repo):**
- `js_engine/oracle_diff.js:24-33,35-46,85-106` (extract CurrentInfo; consume only gameState; scalar + per-instId table diff).
- `js_engine/State.js:1657-1690`, `js_engine/Inst.js:290-360` (JS serializer = F6 gameState shape).
- `docs/scratch/f6_parse.py`; dumps `docs/scratch/{F6_test,S1gfK-xUO5j,VXGaI-n97ZU,v+7VV-YOs41}.txt` (213-233 KB; ~87% static aiParameters that oracle_diff ignores; gameState ~26 KB).

**Live spectator (sibling repo `prismata-ladder`):**
- `prismata_amf3.py:338-345` (GAME_MSG_TYPES), `:1457-1493` (BeginGame mergedDeck/laneInfo), `:1496-1556` (StartTurn→F6→clipboard), `:1559-1579` (Click buy-tracking only), `:1117-1142` (`_send_f6_to_prismata`), `:1282-1309` (`_read_clipboard_win32`).
- `headless_client.py` / `headless_multi.py` — raw click append only; no F6/clipboard/state.

**Corpus / cost (this repo):**
- `docs/handoff-2026-05-31-resume-and-rerun.md:16-18`; `docs/deepsets-training-results.md:30,40`; `docs/superpowers/plans/2026-06-03-rl-selfplay-loop-implementation.md:520,592,606-608`; `docs/jsengine-faithfulness-results.md:9,18-23`.
