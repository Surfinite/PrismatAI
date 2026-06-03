# Hand-off prompt — viability of automated F6 gamestate export

> Paste the section below into a fresh **prismata-ladder** workspace session (it has the headless-spectator / AMF3-sniffer code). It is a *viability assessment*, not a build task — we will only build this if the verdict is favourable and we actually need it.

---

## Goal

Assess the **feasibility, approach, and rough effort** of programmatically exporting **client-authoritative Prismata gamestates** — the same JSON an F6 dev-mode dump produces (`CurrentInfo` = `{mergedDeck, gameState, aiParameters}`, card names as display names) — **at scale and without manual keypresses**. Do **not** build it yet. Produce a written verdict.

## Why we want it (the use case)

Over in the PrismataAI repo, the DeepSets value net's training corpus (human + MasterBot) is produced by replaying recorded games through our **JS engine** (`js_engine`) and extracting per-turn feature records (`training_example.js::extractTrainingExampleV2`). The JS engine is validated as **click-faithful** (the faithfulness campaign drove ~8,700 replay asserts down to 33, all client-side recording bugs). What that does *not* fully prove is **state-identity**: that the JS engine's *computed gamestate* matches the real AS3 client's at every extraction point. An assert-clean replay could still land on a subtly-wrong state, which would silently corrupt the training corpus — and we're about to spend real money (AWS RL self-play) on a net trained on it.

We already have the diff tool: `js_engine/oracle_diff.js` compares the JS engine's replayed state against an **F6 client dump** at a given point. It just needs *client dumps to diff against*. A handful of manual F6 dumps is the cheap spot-check we'll do first. **This task is about whether the F6-dump side can be automated** so we could, if needed, validate state-identity across a large, representative sample of the corpus (and/or harvest an independent validation set) instead of ~20 hand-dumped states.

## What you have to work with (prismata-ladder infra)

- **Headless spectator stack** already running for prismata.live: `headless_client.py` / `headless_multi.py` (login + session; note the server sends a `Moved` load-balancing redirect during login that must be handled), `prismata_amf3.py` (the canonical AMF3 protocol sniffer — formerly `prismata_sniffer.py`), `spectator_bridge.py`, `ws_broadcast.py`. Spectator accounts like `PrismataLiveBot` (Client7).
- **Replay data:** historical games are on S3 (`saved-games-alpha.s3...`, code → `.json.gz`) as **commandList + deck**, i.e. the click sequence and initial state — **not** per-turn computed states.
- **F6 / dev-mode:** F6 copies the client's *locally-computed* `CurrentInfo` JSON to the clipboard. It requires the SWF dev-mode patch (single byte at decompressed offset `0x1580196`: `0x27`→`0x26`) plus a hosts entry to bypass load-balancing.

## The core technical uncertainty to resolve

The AS3 client **computes the gamestate locally** by replaying the commandList; the server/S3 stores the commandList, not the per-turn states. So "get the client's authoritative state at turn N" means *running the client's engine*. That splits into two very different paths — assess **both**:

1. **Live-spectator harvesting (states pushed by the server).** When the headless spectator watches a **live** game, does `prismata_amf3.py` receive **server-authoritative per-turn gamestate snapshots**, or only moves/clicks (which would still need local computation)? If the server pushes full states, we can harvest client-truth states from live ladder games cheaply — an *independent* JS-engine validation set (not the historical 1800 corpus, but real-client states across real play). Determine: what exactly does the spectated AMF3 stream contain per turn, and can it be reshaped into the F6 `CurrentInfo` shape `oracle_diff.js` expects?

2. **Automated F6 over historical replays (drive the real client).** To validate the *actual* corpus replays, the real AIR/Flash client must replay each code and dump state per turn. Assess whether the client can be **scripted headlessly/automatically**: load a replay by code, advance to each turn-start, trigger the F6 clipboard dump, capture it — and at what throughput. Consider the AIR runtime automation surface, clipboard polling, whether the dev-mode patch + hosts setup can run unattended, and whether replays can be stepped programmatically (vs. only via the UI).

## Questions to answer

1. **Live path:** Does the spectated AMF3 stream carry full per-turn gamestates (server-authoritative)? If yes, sketch the harvest → `CurrentInfo`-shape pipeline and its rough cost. If no (moves only), say so — that kills the "cheap live oracle" idea.
2. **Replay path:** Is automated F6 over historical replay codes feasible at all? Via what mechanism (scripted AIR client / UI automation / other)? Rough throughput (states/hour) and reliability.
3. **Effort/verdict per path:** small / medium / large, with the main risks. Is there a third option we're missing?
4. **Recommendation:** for the goal of *validating JS-engine state-identity on the training corpus*, which path (if any) is worth building — or is manual F6 spot-checking the only sensible move and automation not worth it?

## Deliverable

A short written **viability report** (verdict + per-path effort + recommendation). **No implementation.** We decide whether to build based on your report and the results of the manual spot-check happening in parallel.
