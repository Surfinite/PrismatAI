# RL Campaign Log — iteration ledger + accepted-limitations register

> **What this is.** The per-iteration HUMAN record the campaign's epistemics depend on, plus the living
> register of accepted limitations and open items. `rl_campaign.md` §5 mandates "a changelog mapping
> every win-rate point to exactly one (config-hash, net-hash) delta" — this file is that changelog.
> The MACHINE record lives elsewhere (`eval/manifests/eval_iter_<K>.json`, the dashboard,
> `training/models/rl_iter_<K>/run_metadata.json` lineage stamps); this file records what the machine
> cannot: the decision, the reasoning, and the anomalies. Append-only; never rewrite old entries —
> correct them with a dated note.
>
> **Reading order for a new maintainer:** `eval/rl_campaign.md` (the contract: frozen v4 tuple, the
> collapse/promote-unless-collapse policy, anchors) → `eval/rl_runbook.md` (what each stage does) →
> `eval/README.md` (eval harness + statistics) → this file (what has actually happened and what is
> accepted-broken) → the reframe design spec
> `docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md` + the audit trail in
> `docs/superpowers/plans/` (2026-06-09 … 06-14, historical).

---

## Iteration entries

Template (copy for each iteration; one entry per `run_iteration.ps1 -K <K>` attempt, including failed
or abandoned attempts):

```markdown
### Iteration K=<k> — <date> — <PROMOTED | ITERATED | INVALIDATED | ABORTED stage N> [Phase 0|1]

- **Regime:** v4 "proof-of-life" (tuple_version 4) — systems pipeline validation, no axis under test.
- **Parent / generator:** <parent_bin name + sha256 prefix> (Phase 0 = fixed v221, no promotion).
- **Candidate:** neural_weights_rl_iter<k>.bin <sha256 prefix> (warm-started, 6 ep @ 1e-5, no SWA,
  W=2, rehearsal 0.10 elite, on <n> self-play records / <g> general games).
- **Config identity:** dave config.txt @ <git short-sha>, campaign_frozen.json @ <git short-sha>
- **Manifest:** eval/manifests/eval_iter_<k>.json — **collapse: <True|False|None>**
- **Headline numbers:** origin (cand vs v221) <w>W/<d>D/<n> = <x>% (CI <lo>–<hi>); masterbot (cand
  vs MasterBot_SWF) <w>W/<n> = <x>% (CI <lo>–<hi>). (Narrow/steam not run — checkpoint-only in v4.)
- **Watch-stats (rl_campaign §1b):** prediction-movement fixed-probe mean|dP| <x> (floor 0.001 —
  below = null update); self-play probe <x>; val-acc candidate <x>% vs parent <x>% (tripwire Δ <x>pp);
  game-length median <x> (band [25,60]); self-play P0 win-rate <x> (non-degeneracy band [0.35,0.65]);
  late sampled fraction <x>.
- **Decision + reasoning (the load-bearing paragraph):** <why promote/iterate/abort — what evidence
  moved you, what you discounted as noise, what you pre-commit to checking next iteration. Phase 0:
  NOT a promotion candidate (fixed generator) — the question is "did the loop run and produce a
  non-degenerate net", never "did RL improve the net">
- **Anomalies / deviations from runbook:** <anything — reruns, manual steps, flaky gates, config edits>
- **Data disposition:** rl_iter_<k>/ <kept in window | quarantined → where + why>
```

### Iteration K=1 — 2026-06-16 — ITERATED (Phase 0, fixed generator — NOT promoted)

- **Regime:** v4 "proof-of-life" (tuple_version 4) — systems pipeline validation, no axis under test.
- **Parent / generator:** `neural_weights_mixed_v221.bin` (22cc647…); fixed generator (Phase 0, no promotion).
- **Candidate:** `neural_weights_rl_iter1.bin` (warm-started from v221, 6 epochs @ 1e-5, no SWA, W=2,
  rehearsal 0.10 elite, on **37,899** self-play records / 1,032 general games).
- **Config identity:** dave config.txt @ v4 (`d319ef62` driver); campaign_frozen.json v4 (`ca937706`+calib).
- **Manifest:** `eval/manifests/eval_iter_1.json` — **collapse: False** (no abort).
- **Headline numbers:** origin (cand vs v221) **47W/1D/96 = 49.5%** (CI 0.40–0.59); masterbot (cand vs the
  AB SWF MasterBot) **56W/96 = 58.3%** (CI 0.48–0.68). (Narrow/steam not run — checkpoint-only in v4.)
- **Watch-stats:** prediction-movement fixed-probe mean|dP| **0.0172** (NON-NULL — training moved the net;
  3.9% winner-flips), self-play probe 0.0138; val-acc candidate **71.6%** vs parent 71.8% (−0.2pp, tripwire
  quiet); game length median **37** / mean 39.8 / **max 200** (one turn-cap game); self-play P0 win-rate
  **0.344** (P2 ≈ 64%); IG argmax mean 0.359, dist {0:?,1:12,2:1} (battery); root entropy 1.87.
- **Decision + reasoning:** This is the Phase-0 **validation** run, not a promotion candidate (fixed
  generator). The loop is validated **end-to-end on real data**: a genuine non-null candidate (dP≈0.017,
  vs the deliberate `rounds:4` pre-smoke null of 0.0 caused by records<batch-512), a sane eval (origin
  ≈ even with v221 as expected for one fixed-gen step; masterbot ~58%; the harness self-match check was
  exactly 50% in the pre-smoke), and all gates behaving (parity ALL PASS, val-acc tripwire quiet, collapse
  correctly False). Calibrated `prediction_movement_floor`=0.001 and `game_length_band`=[25,60] into the
  frozen tuple from this run.
- **Anomalies / deviations:** (1) **stage-1.5 stale-archive bug caught + fixed** (`d319ef62`): the cleanup
  glob `sp_*` missed the `general_`-prefixed archive, so the run-after-the-`rounds:4`-smoke collided on
  Move-Item *after* self-play completed; recovered by reusing the intact 37,899-record self-play data +
  `-ResumeFrom 2` (no self-play re-run). (2) `rounds:4` pre-smoke produced a NULL candidate (≈280 records
  < batch 512 → 0 optimizer steps) — expected, validated the null-update detector; full run used 516
  rounds. (3) P0 win-rate 0.344 is marginally below the [0.35,0.65] non-degeneracy band — a stronger P2
  advantage than the ~57% baseline (audit-known, set/strength-dependent), data still non-degenerate.
  (4) `render_dashboard.py` still prints the stale v3 verdict/forced/narrow/steam columns — cosmetic
  (the manifest's `collapse` is the source of truth); flagged for the Task-14 doc/dashboard pass.
- **Data disposition:** `rl_iter_1/` kept in window (parent-generated). The `rounds:4` smoke + recovery
  artifacts are preserved in `training/data/_orphans/rl_iter_1_*`.

### Iteration K=2 — 2026-06-17 — PROMOTED (Phase 1, first promoting iteration)

- **Regime:** v4 "proof-of-life" (tuple_version 4); first **Phase-1** promoting iteration.
- **Parent / generator:** `neural_weights_mixed_v221.bin` (22cc647…) — still the generator (nothing
  promoted before K=2). W=2 window = iter_1 + iter_2, both v221-generated (coherent).
- **Candidate:** `neural_weights_rl_iter2.bin` (cb457e8…) — warm-started from v221, 6 ep @ 1e-5, no SWA,
  W=2, rehearsal 0.10 elite, on **37,606** self-play records / 1,032 general games. **First self-play
  generated with the stalemate draw rule (StalemateThreshold:40) live.**
- **Config identity:** dave config.txt @ `3663b5b7` (v4 + stalemate enabled); campaign_frozen.json @
  `46a5dddc` (v4 + stalemate-freeze). [run-time, pre-promote — promotion advances both.]
- **Manifest:** `eval/manifests/eval_iter_2.json` — **collapse: False**.
- **Headline numbers:** origin (cand vs v221) **52W/1D/96 = 54.7%** (CI 0.45–0.64; paired 0.49–0.60);
  masterbot (cand vs the AB SWF MasterBot) **60W/0D/96 = 62.5%** (CI 0.53–0.72). **Both up vs K=1**
  (49.5% / 58.3%) — the candidate now beats v221 on the origin anchor.
- **Watch-stats:** prediction-movement fixed-probe mean|dP| **0.0201** (NON-NULL; 4.64% winner-flips),
  self-play probe 0.0175 (2.39% flips); val-acc candidate **71.6%** vs parent 71.8% (−0.2pp, tripwire
  quiet); **game length max 105 / median 36 / mean 37.9 — ZERO 200-cap games (vs 3 in K=1): the
  stalemate rule fired + trimmed on real self-play data** (~210 records in the trimmed band); export-parity
  ALL PASS (worst ~1e-6); IG argmax mean 0.385, dist {0:24,1:15}; ig_contrast_pairs 29; root entropy 1.87.
  Self-play P0 win-rate not separately recomputed (H5 carries the discounted `label_A`); ~0.34 expected
  (set/strength-dependent, audit-known); candidate non-degeneracy confirmed by winning both seats in eval.
- **Decision + reasoning:** **PROMOTED** per the frozen promote-unless-collapse policy — collapse False
  (origin 54.7% ≫ abort 0.35), val-acc tripwire quiet, parity PASS, prediction-movement non-null. This is
  the first candidate to BEAT v221 on origin (54.7% > 50%) AND lift the masterbot trend (58.3→62.5%) — a
  genuine one-iteration gain. CAVEAT: the per-iteration origin CI is wide [0.45,0.64] and is non-trivially
  powered only at the **checkpoint cadence (K=3–5, `run_checkpoint.ps1`)** — treat +5pp as encouraging,
  confirm at the checkpoint; do NOT over-read a single iteration. Parent advanced v221 → rl_iter2; K=3 now
  generates with rl_iter2.
- **Anomalies / deviations:** none. First run with the stalemate rule live — clean (no 200-cap games).
- **Data disposition:** `rl_iter_2/` kept in window (v221-generated). `rl_iter_1/` slides out of the
  window after K=2.

### Iteration K=3 — 2026-06-17 — PROMOTED (Phase 1, second promoting iteration)

- **Regime:** v4 "proof-of-life" (tuple_version 4); second **Phase-1** promoting iteration — and the
  FIRST candidate trained from a PROMOTED (non-v221) parent, closing the promoting loop.
- **Parent / generator:** `neural_weights_rl_iter2.bin` (cb457e8…) — the K=2-promoted parent (NOT v221).
  W=2 window = iter_2 (v221-generated) + iter_3 (rl_iter2-generated) — mixed-generation off-policy window.
- **Candidate:** `neural_weights_rl_iter3.bin` (76eedbb4…) — warm-started from rl_iter2, 6 ep @ 1e-5, no
  SWA, W=2, rehearsal 0.10 elite, on **37,162** self-play records / 1,032 general games (Seed 5603).
- **Config identity:** dave config.txt @ `fe41ed8b` (K=2 repoint); campaign_frozen.json @ `03f73bf2`
  (K=2 promote). [run-time, pre-promote — promotion advances both to dave `ad55d68a` / this main commit.]
- **Manifest:** `eval/manifests/eval_iter_3.json` — **collapse: False**.
- **Headline numbers:** origin (cand vs v221) **50W/0D/96 = 52.1%** (CI 0.42–0.62; paired 0.45–0.59);
  masterbot (cand vs the AB SWF MasterBot) **56W/0D/96 = 58.3%** (CI 0.48–0.68; paired 0.50–0.67). Both
  settled back from K=2's peak (54.7% / 62.5%) but remain favorable (origin still > 50% vs v221).
- **Watch-stats:** prediction-movement fixed-probe mean|dP| **0.0095** (NON-NULL; 1.90% winner-flips),
  self-play probe 0.0077 (0.98% flips); val-acc candidate **71.6%** vs parent 71.6% (0.0pp, tripwire
  quiet); **game length max 75 / median 36 / mean 37.2 — ZERO 200-cap games (37,162 records): the
  stalemate rule held again, even tighter than K=2 (max 105)**; export-parity ALL PASS (worst 8.4e-06);
  IG argmax mean 0.385, dist {0:25,1:13,2:1}; ig_contrast_pairs 37; root entropy 1.869. Self-play P0
  win-rate not separately recomputed (H5 carries the discounted `label_A`).
- **Decision + reasoning:** **PROMOTED** per promote-unless-collapse — collapse False (origin 52.1% ≫
  abort 0.35), val-acc tripwire quiet (71.6 == 71.6), parity PASS, prediction-movement non-null. This is
  the SECOND consecutive promotion and the FIRST candidate generated by a promoted parent (rl_iter2, not
  v221) — it validates the loop CLOSES (the parent advances; the next candidate trains from the advanced
  parent). Both anchors dipped vs K=2's peak (origin 54.7→52.1, masterbot 62.5→58.3), but the moves sit
  well inside the wide per-iter CIs (origin [0.42,0.62] overlaps all of K=1/2/3) — per-iteration NOISE,
  not a powered signal. Cumulative over the permanent v221 origin: **+2.1pp at K=3 vs +4.7pp at K=2.**
  CAVEAT: per-iter evals are underpowered (±~10pp); do NOT over-read the K=2→K=3 dip. **Pre-commit: run
  the powered checkpoint (`run_checkpoint.ps1`, 768+ origin games) by K=5 to resolve whether the
  cumulative v221→rl_iter2→rl_iter3 improvement is real** — per-iter cells are a harm screen; the
  checkpoint is the answer-producing measurement.
- **Anomalies / deviations:** **VSCode auto-restarted (an IDE update) mid-iteration, during the stage-7
  eval.** The restart killed the pwsh driver AND the background-task completion notification — but the
  eval orchestrator (`run_eval.py`, PID 41260) + the tournament engine were orphaned-yet-survived and
  completed the eval + finalized the manifest normally (96+96 games, 0 missing, collapse written).
  Recovered WITHOUT recompute: (a) a manual watcher polled the manifest to `complete:true` (replacing the
  dead notification); (b) the restart-skipped stage 8 (action_coverage telemetry + dashboard) was
  backfilled by running the two scripts directly — non-gating in v4; (c) `promote_candidate.ps1 -K 3`
  ran clean (lineage sha OK, preflight 19/19). Integrity intact — candidate + parity artifacts were
  already on disk pre-restart.
- **Data disposition:** `rl_iter_3/` kept in window (rl_iter2-generated). `rl_iter_2/` slides out of the
  W=2 window after K=3 (window for K=4 = iter_3 + iter_4).

### Iteration K=4 — 2026-06-17 — PROMOTED (Phase 1, third promoting iteration)

- **Regime:** v4 "proof-of-life" (tuple_version 4); third **Phase-1** promoting iteration.
- **Parent / generator:** `neural_weights_rl_iter3.bin` (76eedbb4…) — the K=3-promoted parent.
  W=2 window = iter_3 (rl_iter2-generated) + iter_4 (rl_iter3-generated).
- **Candidate:** `neural_weights_rl_iter4.bin` (67dec168…) — warm-started from rl_iter3, 6 ep @ 1e-5, no
  SWA, W=2, rehearsal 0.10 elite, on **37,603** self-play records / 1,032 general games (Seed 5604).
- **Config identity:** dave config.txt @ `ad55d68a` (K=3 repoint); campaign_frozen.json @ `e571b306`
  (K=3 promote). [run-time, pre-promote — promotion advances both to dave `1e7a2ff8` / this main commit.]
- **Manifest:** `eval/manifests/eval_iter_4.json` — **collapse: False**.
- **Headline numbers:** origin (cand vs v221) **48W/0D/96 = 50.0%** (CI 0.40–0.60; paired 0.45–0.55);
  masterbot (cand vs the AB SWF MasterBot) **60W/0D/96 = 62.5%** (CI 0.53–0.72; paired 0.55–0.70). Origin
  is EXACTLY even with v221; masterbot is back to the K=2 peak.
- **Watch-stats:** prediction-movement fixed-probe mean|dP| **0.0114** (NON-NULL; 2.15% winner-flips),
  self-play probe 0.0102 (1.22% flips); val-acc candidate **71.5%** vs parent 71.6% (−0.1pp, tripwire
  quiet); **game length max 87 / median 36 / mean 37.6 — ZERO 200-cap games (37,603 records)**;
  export-parity ALL PASS (worst 6.59e-06); IG argmax mean 0.333, dist {0:26,1:13}; ig_contrast_pairs 33;
  root entropy 1.880. Self-play P0 win-rate not separately recomputed (H5 carries discounted `label_A`).
- **Decision + reasoning:** **PROMOTED** per promote-unless-collapse — collapse False (origin 50.0% ≫
  abort 0.35), val-acc tripwire quiet (71.5 vs 71.6), parity PASS, prediction-movement non-null. THIRD
  consecutive promotion. **⚠️ ORIGIN-ANCHOR TREND worth flagging: across the three promoting iterations
  the origin win-rate (vs the PERMANENT v221) has drifted DOWN monotonically — 54.7 → 52.1 → 50.0 — i.e.
  the cumulative advantage over v221 has decayed from +4.7pp (K=2) to ~0pp (K=4), while the masterbot
  absolute-strength anchor stayed healthy (62.5 / 58.3 / 62.5).** All per-iter origin CIs overlap 50% and
  each other (n=96, ±~10pp), so the decline is NOT statistically resolved — it is consistent with both
  regression-to-the-mean NOISE and genuine promote-unless-collapse drift (off-policy W=2 fine-tuning on a
  moving parent slowly forgetting the v221-relative edge). This is precisely the ambiguity the powered
  checkpoint exists to resolve. **DECISION: pause the blind K→K+1 cadence and run the powered checkpoint
  (`run_checkpoint.ps1`, 768+ origin games vs v221) on rl_iter4 NOW** (we are inside the K=3–5 window) —
  the per-iter cells cannot tell us whether 3 promotions bought any real cumulative gain; spending two
  more ~2.5 hr iterations before measuring would compound that blindness. Owner to decide regime/policy
  response (continue / adjust N / revisit promote-unless-collapse) FROM the powered result.
- **Anomalies / deviations:** none — clean full run, stage 8 ran normally (no restart; manifest carries
  action_coverage). NOTE: the K=3-vs-K=4 self-heal log line ("stale lock from a dead PID — reclaiming
  K=3 pid=39108") at K=4 start was the EXPECTED `.iteration.lock` reclaim after the K=3 VSCode-restart
  killed that driver — working as designed.
- **Data disposition:** `rl_iter_4/` kept in window (rl_iter3-generated). `rl_iter_3/` slides out of the
  W=2 window after K=4 (window for K=5 = iter_4 + iter_5).

### CHECKPOINT @ K=4 lineage head — 2026-06-17 — the powered v221-relative read

- **What / why:** the FIRST powered checkpoint (`run_checkpoint.ps1`), triggered at K=4 (inside the
  K=3–5 cadence) because the per-iter origin cells had drifted 54.7 → 52.1 → 50.0 and the per-iter ±10pp
  resolution could not say whether that was real regression or noise. Evaluates the promoted lineage head
  `neural_weights_rl_iter4.bin` (67dec168…) vs the PERMANENT v221 origin at 192 rounds/block.
- **Manifest:** `eval/manifests/eval_iter_ckpt_k4.json` (dashboard row `ckpt_k4`). The per-iter
  `eval_iter_4.json` remains the 96-game cell; this is the 384-game powered cell.
- **Powered numbers (384 games/anchor, ~±5pp):** origin (vs v221) **201W/0D/384 = 52.3%** (CI 0.47–0.57);
  masterbot (vs MasterBot_SWF) **258W/1D/384 = 67.3%** (CI 0.62–0.72). **B8 cumulative-forgetting guard:**
  lineage val-acc **71.5%** vs the FIXED v221 constant 71.8% (within 5pp — no forgetting). collapse False.
- **Verdict:** the per-iter origin "decline" was **NOISE, not regression** — the powered origin read is
  **52.3% (CI 0.47–0.57)**: the lineage is at-least-parity and probably slightly ahead of v221 (the CI
  grazes 50). Masterbot is clearly and increasingly strong (67.3%, well above 50 and higher than any
  per-iter cell). No collapse, no forgetting → **the loop is healthy.** Honest caveat: the v221-relative
  gain after 3 promotions is **MODEST (~+2pp powered, CI includes 0)** — consistent with "proof-of-life"
  (a working, non-degenerate, slightly-improving loop), not a large RL win. Per-iter origin cells are
  confirmed too noisy to read individually (as designed); THIS powered cell is the go/no-go evidence.
- **Operational notes (both recovered, no data impact):** (1) the first checkpoint attempt (11:57) died
  at 55 min on a **transient Windows file-lock** on the engine's periodic HTML progress-write (FATAL
  `HTMLTable` append on an existing file, exit 0xC0000409); the `finally` cleanly restored config (rounds
  → 48, no drift); the re-run completed. Durable fix if it recurs: a Defender exclusion on the dave `bin`
  dir. (2) the checkpoint was first launched with `-Iteration 4`, which **clobbered the per-iter
  `eval_iter_4.json`**; restored it (eval cells from the committed record; `action_coverage` regenerated
  from the intact K=4 self-play — deterministic stats matched: ig_present_turns 566, ig_contrast_pairs 33)
  and re-homed the checkpoint to `eval_iter_ckpt_k4.json`. Use `-Iteration 0` (timestamped) for future
  checkpoints to avoid the per-iter name collision.

### Iteration K=5 — 2026-06-18 — PROMOTED (Phase 1 — FIRST MA-axis iteration)

- **Regime:** v4 "proof-of-life", now with the **MA axis OPEN** (re-anchor row in the decisions table:
  IG_Only + Ability_Filter_Live_NoIG extended with Mobile Animus; MaxChildren 40→80). FIRST iteration
  whose self-play + eval action space includes the IG×MA count cross-product.
- **Parent / generator:** `neural_weights_rl_iter4.bin` (67dec168…) — generated the K=5 self-play with MA open.
- **Candidate:** `neural_weights_rl_iter5.bin` (808bf5ec…) — warm-started from rl_iter4, 6 ep @ 1e-5, no SWA,
  W=2, rehearsal 0.10 elite, on **37,432** self-play records / 1,032 general games (Seed 5605).
- **Config identity:** dave config.txt @ MA-open + K=4 repoint; campaign_frozen.json parent=rl_iter4 (pre-promote).
- **Manifest:** `eval/manifests/eval_iter_5.json` — **collapse: False**.
- **Headline numbers:** origin (cand vs v221) **49W/0D/96 = 51.0%** (CI 0.41–0.61; paired 0.46–0.56);
  masterbot (cand vs MasterBot_SWF) **59W/0D/96 = 61.5%** (CI 0.51–0.71; paired 0.53–0.70). Both essentially
  flat vs K=4 (50.0% / 62.5%) — opening MA did NOT move the per-iter numbers, exactly as the prep widening
  control predicted (v221≈iter4 on MA → widening, not learning, is the lever; per-iter is underpowered anyway).
- **Watch-stats:** prediction-movement fixed-probe mean|dP| **0.00967** (NON-NULL > floor 0.001; 1.66% flips),
  self-play probe 0.00793 (0.64% flips); val-acc candidate **71.4%** vs parent 71.5% (−0.1pp, tripwire quiet);
  game length median **36** / mean 36.3 / max 95 — **ZERO 200-cap games** (37,432 records); export-parity PASS
  (worst 6.1e-05). **P0 self-play win-rate 0.317** — marginally BELOW the [0.35,0.65] non-degeneracy band (see
  anomalies). **MA coverage (crude, from replays): ~7.5% of self-play games involve Mobile Animus** (the proper
  ma_present/ma_feasible_max stamp is IG-only today; a real distribution is deferred to a coverage-tool/exporter pass).
- **Decision + reasoning:** **PROMOTED** per promote-unless-collapse — collapse False (origin 51.0% ≫ 0.35),
  val-acc tripwire quiet, parity PASS, prediction-movement non-null. The first MA-open candidate is at parity
  vs v221 (51.0%) and strong vs MasterBot (61.5%); no degradation from opening MA. Consistent with the
  pre-registered expectation that the MA gain (if any) is modest and shows at the powered checkpoint, not in a
  single per-iter cell. **P0 wr 0.317** treated as the audit-known P2 seat advantage (K=1 was 0.344; MA is
  symmetric so it cannot create seat bias), NOT a degenerate generator (median length 36, 0 cap games, both
  seats win substantially) — non-blocking, but flagged to watch across K=6–8. **MA coverage ~7.5%** is modest:
  if the checkpoint shows no MA gain, low coverage + "widening does the work" is the likely explanation, and a
  forced-MA curriculum block is the (not-yet-added) contingency lever.
- **Anomalies / deviations:** (1) P0 self-play win-rate 0.317 < band lower bound 0.35 — accepted P2-advantage
  regime, watch the trend. (2) MA coverage measured crudely (cardName scan over replays); a rigorous MA-click
  distribution needs the ma_present exporter stamp or a replay-click parser — deferred (non-gating).
- **Data disposition:** `rl_iter_5/` kept in window (rl_iter4-generated). `rl_iter_4/` slides out after K=5.

### Iteration K=6 — 2026-06-18 — PROMOTED (Phase 1, MA axis, 2nd MA-open iteration)

- **Regime:** v4 proof-of-life, MA axis open. First candidate generated by an MA-trained parent (rl_iter5).
- **Parent / generator:** `neural_weights_rl_iter5.bin` (808bf5ec…). W=2 window = iter_5 + iter_6 (both MA-open).
- **Candidate:** `neural_weights_rl_iter6.bin` (01fa8b83…) — 6 ep @ 1e-5, no SWA, W=2, rehearsal 0.10 elite,
  **36,918** records / 1,032 games (Seed 5606).
- **Manifest:** `eval/manifests/eval_iter_6.json` — **collapse: False**.
- **Headline:** origin (vs v221) **46W/0D/96 = 47.9%** (CI 0.38–0.58; paired 0.42–0.54 — straddles 0.5 = at
  parity within noise); masterbot **57W/0D/96 = 59.4%** (CI 0.49–0.69; paired 0.51–0.68). Slight dip vs K=5
  (51.0/61.5), inside the overlapping per-iter CIs — noise, not signal (the checkpoint resolves it).
- **Watch-stats:** prediction-movement fixed 0.0084 (non-null; 1.03% flips), self-play 0.0077; val-acc 71.4 vs
  71.4 (tripwire quiet); game length median 35 / mean 35.8 / max 64 — 0 cap; export-parity PASS (1.22e-04,
  within combined atol+rtol). **P0 self-play wr 0.336** — recovered toward the ~0.34 baseline (K=5 was 0.317),
  confirming that dip was set-variation, not a degenerating trend.
- **Decision + reasoning:** **PROMOTED** (promote-unless-collapse) — collapse False, tripwire quiet, parity
  PASS, movement non-null. origin at parity (47.9%, CI∋0.5), masterbot strong. Per-iter origin now bounces
  51.0→47.9 (MA-open), same noise band as the pre-MA campaign (50–55) — read the powered checkpoint, not cells.
- **Anomalies / deviations:** none (P0 wr recovered to 0.336, in regime).
- **Data disposition:** `rl_iter_6/` kept in window (rl_iter5-generated). `rl_iter_5/` slides out after K=6.

### Iteration K=7 — 2026-06-18 — PROMOTED (Phase 1, MA axis, 3rd MA-open iteration)

- **Parent / generator:** `neural_weights_rl_iter6.bin` (01fa8b83…). Candidate `neural_weights_rl_iter7.bin`
  (23803283…) — 6 ep @ 1e-5, no SWA, W=2, rehearsal 0.10 elite, **37,268** records / 1,032 games (Seed 5607).
- **Manifest:** `eval/manifests/eval_iter_7.json` — **collapse: False**.
- **Headline:** origin (vs v221) **44W/0D/96 = 45.8%** (CI 0.36–0.56; paired 0.39–0.52 — grazes 0.5);
  masterbot **56W/0D/96 = 58.3%** (CI 0.48–0.68; paired 0.50–0.66).
- **Watch-stats:** prediction-movement fixed 0.00757 (non-null; 1.27% flips), self-play 0.00563; val-acc 71.3
  vs 71.4 (tripwire quiet); game length median 35 / mean 36.1 / max 75 — 0 cap; parity PASS (1.22e-04). P0 wr
  **0.342** (continued recovery: 0.317→0.336→0.342).
- **Decision + reasoning:** **PROMOTED** (promote-unless-collapse) — collapse False, tripwire quiet, parity
  PASS, movement non-null. **⚠️ TREND FLAG: origin vs v221 across the 3 MA-open iters = 51.0→47.9→45.8**
  (gentle monotonic decline through parity), with prediction-movement also shrinking (0.0097→0.0084→0.0076 =
  lineage converging). This is the SAME shape the pre-MA campaign showed (54.7→52.1→50.0, powered-checkpoint-
  resolved as NOISE @ 52.3%), and the masterbot ABSOLUTE anchor corroborates **no real degradation**
  (61.5→59.4→58.3, still strong). Not over-reading 3 underpowered 96-game cells; **the K=8 powered checkpoint
  is the arbiter** — central question now: is the MA lineage at parity vs v221, or has promote-unless-collapse
  drifted it slightly below (the off-policy W=2 hazard)? Pre-commit: if the checkpoint origin is < ~0.45
  powered (real sub-v221 drift), STOP promoting + reassess; if ~parity (à la K=4's 52.3%), it was noise.
- **Anomalies / deviations:** none (gates green; the origin trend is a watch item, not an abort condition).
- **Data disposition:** `rl_iter_7/` kept in window (rl_iter6-generated). `rl_iter_6/` slides out after K=7.

---

## Campaign-level decisions (one line per (config-hash, net-hash) delta — rl_campaign §5)

| Date | What changed | Why | Where recorded |
|---|---|---|---|
| 2026-06-11 | Tuple FROZEN: N=1000, τ=0.7, K=12, ε=0/εlate=0.05, c=0.3, Threads:8, mix 43+21, W=5, parent=v221 | regime v2 post-audit | `campaign_frozen.json`, rl_campaign §1 |
| 2026-06-12 | Stage-1.5 archive (sidecars+replays per iteration) | future-schema re-extraction + forensics | rl_campaign §1e |
| 2026-06-12 | Third audit (design-level) delivered; pre-iter-1 changes recommended | loop is mechanically green but as frozen is a null-iteration generator (signal ≪ eval resolution); fixed seeds freeze the card-set universe; no promotion policy | `docs/superpowers/plans/2026-06-12-rl-loop-design-audit-FINDINGS.md` |
| 2026-06-12 | **J1 DECIDED (a, upper)**: self-play rounds 344 general + 172 forced (~1032 games/iter, ⅔:⅓ kept); DROP SWA (deploy final-epoch weights); rehearsal 0.10 with tripwire-gated raise; lr stays 1e-5 | raise the training dose ~8×/iter (~470 optimizer steps vs 78) with zero new instability levers; lr raise held as next lever if the prediction-movement probe reads null | this table; audit §1.1/§3 |
| 2026-06-12 | **J2 DECIDED (a)**: promote-unless-harm (promote every candidate unless REJECT / 4.5-tripwire / reproduced-harm signal); powered lineage eval vs fixed v221 origin, 768–1024 games, every 3–5 iterations | iterations compound (the actual RL mechanism); per-iteration eval becomes a harm screen; the checkpoint eval is the campaign's answer-producing measurement | audit §1.4 |
| 2026-06-12 | **J3 DECIDED (a, upper)**: per-iteration eval = iter0/general rounds 192 (384 games) + iter0/forced rounds 96 (192 games) ONLY; narrow → 256 games once per promotion; steam → 100 games at checkpoints; ADD `RL_Eval_origin` (permanently v221) at checkpoints | decision anchor gets ±5.0pp; non-gating anchors stop burning per-iteration hours; cumulative d_rl semantics restored via origin player | audit §1.4, drl-03 |
| 2026-06-12 | **J4 DECIDED (a + split-seed eval)**: self-play Seeds derived from K (e.g. 5500+K / 5600+K, stamped in meta+manifest); eval general pool split 2×rounds:96 at fixed Seeds 2026/2027 (192+192 games) | coverage grows each iteration; fixed two-seed eval panel keeps comparability + partial set-generalization | audit §2 |
| 2026-06-13 | **J5 DECIDED**: targeted IG-ε — at roots whose children span ≥2 IG click counts, with prob ε_IG=0.25 play the most-visited child at a NON-argmax count; `EpsilonLate` → 0; τ/K unchanged; verified per-iteration by the IG-contrast watch-stat (worklist B6) | on-axis counterfactuals (~0.4/forced game vs εlate's ~1-in-32-games) at lower off-axis label-corruption cost; deviation = searched whole-turn sibling, not a random click | audit §1.2/§1.3; owner confirmed 06-13 |
| 2026-06-12 | **J6 DECIDED (b)**: tactical suite → telemetry-only while local (remove the stage-6 hard abort; keep running + recording vs baseline) | consistent with detect-harm philosophy; the axis may not even be IG at AWS scale | audit §5 |
| 2026-06-13 | **REGIME v3 RE-FREEZE IMPLEMENTED** (all J1–J7 + worklist; tuple_version 2, two-tier): rounds 344+172, seeds base+K, EpsilonIG 0.25 / EpsilonLate 0, NO SWA, rehearsal 0.10 elite, iter0-only per-iteration eval (192+384, 2 panels), origin/narrow/steam re-cadenced, promote-unless-harm, sha-pinned parent | third-audit remediation; campaign is run-ready | this file (pre-campaign state); commits main 461f58dc / dave 1eba023c |
| 2026-06-13 | **is_blocking frozen-unit feature skew FIXED** (caught by the new B3 gate fixtures; engine-side, both exporter + inference) | the fifth v2.2.1-class silent skew; frozen blockers must read is_blocking=0 like the training data | dave 1eba023c; three-way gate 7 states green |
| 2026-06-13 | **Rehearsal corpus → ELITE cut (owner proposal)**: SLICE of `human_1800_v2.h5` (provenance inherited — no DB eligibility, no re-extraction): per-game min(H5 rating stamps) ≥2000 + replay-JSON `timeInfo` increment ≥45s, random-sampled ~5k games/~150k records. Measured pool: 23,303 games at 2000+ (1,558 of them absent from replays.db — ladder-DB codes; tc read from `replays_archive/` JSONs, present for every H5 code by construction); ≥19,365 confirmed at 45s+ (~530k records). Val set/tripwire UNCHANGED (human_val_1700) | removes anchor-pulls-toward-weaker-play (same logic as the MB-fleet exclusion); fewer clock blunders = cleaner labels; doubles as the C6 RAM fix; HP-tier → in the pre-K1 re-freeze | worklist C6 |
| 2026-06-12 | **J7 DECIDED (a)**: two-tier tuple — HP knobs (N, τ, K, ε, c, schedule) = new-campaign tier; scale knobs (rounds, seed policy, eval n) = re-anchor-only tier; encode in campaign_frozen.json | future volume tuning stays cheap and legal | audit §6, selfplay-06 |
| 2026-06-14 | **REFRAME to proof-of-life (tuple v4)**: drop IG-measurement (EpsilonIG→0 / forced-Hotel block unused / no IG verdict-pool); restore EpsilonLate=0.05; NoIG interior iterator (`HardIterator_5var_NoIG`, M1 fixed cheaply); W 5→2; anchors = origin + `MasterBot_SWF` same-path AB (steam retired); collapse boolean + promote-unless-collapse (no REJECT/REVIEW); two-phase run (fixed-generator smoke → promoting loop). **IG over-click logged as fixed-by-action-space-widening (audit C1)** — no axis under test | the IG premise collapsed for the IG axis (C1); owner reframes the loop as a GENERAL DSNN-improvement / fix-MasterBot-mistakes framework, IG is proof-of-life | **`docs/superpowers/specs/2026-06-14-rl-loop-proof-of-life-reframe-design.md`** (+ impl plan `…-implementation.md`); `campaign_frozen.json` v4; main 67992a9e |
| 2026-06-16 | **`render_dashboard.py` v3 stale-columns RESOLVED** (Task 13b): the dashboard now renders the v4 `collapse` / `origin(vs v221)` / `masterbot(vs SWF-AB)` / `ig(sp/argmax)` columns; the verdict/iter0/forced/narrow/steam columns flagged in the K=1 entry are gone | the K=1 entry's anomaly (4) | main 67992a9e; the K=1 entry's anomaly (4) is now closed |
| 2026-06-16/17 | **Stalemate draw rule SHIPPED** (`selfplay_stalemate_threshold:40`, SCALE-tier): self-play **and** eval end a frozen game early as a 0.5 draw when the board `(owner,cardType)` multiset is unchanged for 40 plies; self-play also trims the frozen tail from the training shard (kept-length stamped). Engine rebuilt (TournamentGame/SelfPlayV2Exporter/Tournament), `engine_*_exe_sha256` re-pinned, a6 + three-way re-run UNCHANGED (no GameState/feature/value change). Frozen + preflight-asserted. **Validated live on K=2: max game length 105 plies, ZERO 200-cap games (vs 3 in K=1).** | data quality + speed (the 3 Phase-0 cap-draws were ~70% frozen junk); mirrors the SWF "Claim Draw" stalemate ladder's binding kill-cutoff | spec/plan `docs/superpowers/{specs,plans}/2026-06-16-selfplay-stalemate-draw-policy*`; main `46a5dddc` / dave `3663b5b7` |
| 2026-06-17 | **PROMOTED iter-2 → parent** (net-hash delta: `neural_weights_mixed_v221.bin` → `neural_weights_rl_iter2.bin`, sha `cb457e8…`): the FIRST Phase-1 promotion. origin 54.7% / masterbot 62.5% (both up vs K=1 49.5/58.3); val-acc 71.6%, tripwire quiet | promote-unless-collapse: collapse False + tripwire quiet + parity PASS | the K=2 entry above; `eval/promote_candidate.ps1 -K 2`; this main promote commit / dave `fe41ed8b` |
| 2026-06-17 | **PROMOTED iter-3 → parent** (net-hash delta: `neural_weights_rl_iter2.bin` → `neural_weights_rl_iter3.bin`, sha `76eedbb4…`): SECOND Phase-1 promotion + first candidate trained from a PROMOTED (non-v221) parent — the promoting loop closes. origin 52.1% / masterbot 58.3% (down from K=2's 54.7/62.5 but inside the wide per-iter CIs; cumulative +2.1pp origin over v221); val-acc 71.6%, tripwire quiet. **Survived a mid-iteration VSCode auto-restart** (orphaned `run_eval.py` finished the eval; stage-8 telemetry backfilled directly) | promote-unless-collapse: collapse False + tripwire quiet + parity PASS | the K=3 entry above; `eval/promote_candidate.ps1 -K 3`; this main promote commit / dave `ad55d68a` |
| 2026-06-17 | **PROMOTED iter-4 → parent** (net-hash delta: `neural_weights_rl_iter3.bin` → `neural_weights_rl_iter4.bin`, sha `67dec168…`): THIRD Phase-1 promotion. origin 50.0% / masterbot 62.5%. **Origin trend across the 3 promotions = 54.7→52.1→50.0 (cumulative gain over v221 decayed +4.7pp → ~0pp) — within per-iter noise but motivating a POWERED CHECKPOINT before continuing**; val-acc 71.5%, tripwire quiet | promote-unless-collapse: collapse False + tripwire quiet + parity PASS | the K=4 entry above; `eval/promote_candidate.ps1 -K 4`; this main promote commit / dave `1e7a2ff8` |
| 2026-06-17 | **CHECKPOINT @ K=4 lineage head** (powered, 384g/anchor): origin (vs v221) **52.3%** CI 0.47–0.57; masterbot (vs SWF-AB) **67.3%** CI 0.62–0.72; B8 lineage val-acc 71.5% vs fixed-v221 71.8% (no forgetting); collapse False. **Resolves the per-iter origin drift (54.7→52.1→50.0) as NOISE** — lineage ≥ parity vs v221, clearly strong vs MasterBot. Modest v221-relative gain (~+2pp, CI∋0) = proof-of-life healthy → continue | first powered checkpoint (run_checkpoint.ps1) per the K=3–5 cadence | the CHECKPOINT entry above; `eval/manifests/eval_iter_ckpt_k4.json` |
| 2026-06-17 | **Engine rebuild + re-pin** (dave `50977510`): the FORCE_DSNN **Steam deploy path** gains a `use_dsnn.txt` **`weights=`** key (self-describing per-checkpoint bundles, no env var) AND its interior iterator `HardIterator_5var` → **`HardIterator_5var_NoIG`** — the deployed bot now plays the campaign's trained/measured NoIG-interior action space (root IG-subset 0..N + no interior IG auto-fire), closing the RL-vs-deployed asymmetry. `engine_*_exe_sha256` RE-PINNED (testing `c9fb0a64…`, prismataai `58478ec6…`). a6 (0.998/0.001/1.000/0.000) + three-way **UNCHANGED** (FORCE_DSNN is never used in self-play/eval → no measurement affected); `--test-dsnnconfig`/`--test-stalemate` PASS; preflight 19/19 | enable repeatable per-checkpoint Steam bundles + deploy fidelity to the measured action space | this main commit; dave `50977510`; builder `eval/build_steam_bundle.ps1` |
| 2026-06-18 | **DOC CORRECTION (not a config/net delta): `label_A` is NOT ply-discounted.** It is the **raw game outcome** (`outcome_p0`; P0 win=1.0 / loss=0.0 / draw=0.5) stamped **identically on every ply** (`vectorize_v2.py::compute_labels`: `label_a = float(outcome_p0)`); the RL loop trains on **strategy A** (`train.py` default; `run_iteration.ps1` passes no override). The phrasing **"H5 carries the discounted `label_A`"** in the **K=1–K=4 iteration entries above** (and the now-fixed `CLAUDE.md` gotcha) is **WRONG**. Consequence for reading those entries: **nothing measured changes** — eval/checkpoint win-rates are C++ tournament OUTCOMES, not training labels — only the *interpretation* "late-game decisions carry discounted credit" is **retracted**; every ply receives full-weight outcome credit. To read self-play P0 win-rate from an H5, dedupe to one record/game (`ply_index==0`), NOT a record-weighted `label_A` mean (the mismatch is per-game record-count weighting, not discounting; cf. `eval/calibrate_n.py::metrics_from_h5`). | owner caught the doc error 2026-06-18; verified in code (`vectorize_v2.py:320-321`) | this row; `CLAUDE.md:303` fixed (this main commit) |
| 2026-06-18 | **RE-ANCHOR — MA axis OPENED (config-only; K=5 onward).** Extended the subset/Click filter `IG_Only` → `["Infusion Grid","Mobile Animus"]` AND the NoIG interior exclusion `Ability_Filter_Live_NoIG` → `[...,"Mobile Animus"]` (the validated 2-filter edit, handoff §4.4) so the existing `HardIterator_5var_IGsubset_Root` (subsetFilter `IG_Only`) + `HardIterator_5var_NoIG` interior now branch on the **IG×MA count cross-product** — the net chooses MA fire-count 0..N at root; interior never auto-fires MA (replaces the forced-MA-sac "Mistake 2"). **Shared-origin:** all three RL players (`RL_SelfPlay`/`RL_Eval`/`RL_Eval_origin`) share the action space, so the collapse/origin guard stays valid (same iterator) and the origin anchor reads the **pure LEARNING delta** (both sides have MA-widening); the widening+learning absolute read comes from the fixed-iterator `MasterBot_SWF` anchor + a one-off widening control. **`MaxChildren` 40→80** on the same three players — combinatorics probe found the worst realistic board {IG=3,MA=2} = **60** post-dedup root children > the old cap 40 (the cap would bind + longest-first emission would silently drop the conservative low-click candidates, biasing data toward over-firing); 60 < N/10=100 so **N=1000 unchanged → NOT a new campaign** (`MaxChildren` is observe-only/scale, not in the frozen tuple). No engine rebuild (config-only; `engine_sha` pin valid); **preflight 19/19 PASS**. Pre-declared **MIE for MA = ≥5pp** (the K=8 checkpoint sized/pooled accordingly). Prep evidence: §4.1 iter4 MA-fire `{0:12,1:6,2:3}` non-degenerate; widening control v221 `{0:11,1:7,2:3}` ≈ iter4 (widening does the work, RL nudges 4/21). | open the next action-space axis per the proof-of-life→general-improvement plan | this row; dave `config.txt` 5-line diff (IG_Only + Ability_Filter_Live_NoIG + MaxChildren×3); driver `eval/run_iteration.ps1 -K 5` (chain wrapper `eval/run_phase1_loop.ps1`) |

---

## Pre-campaign state (2026-06-13 — REGIME v3 IMPLEMENTED, run-ready)

All J1–J7 decisions + the 29-item mechanical worklist are IMPLEMENTED (main `461f58dc..`, dave
`1eba023c..`): 218/218 tests, preflight **15/15**, A6 orientation check live-validated
(0.998/0.001/1.000/0.001), C7 stage-3 dry run green (2.7 min, no-SWA, elite corpus), A4 rounds-CSV
+ J5 sampler live-smoked (2-round self-play). **First real run: `eval/run_iteration.ps1 -K 1`**,
then promote-unless-harm per the §3 policy, checkpoint at K=3–5.

**Discovery during implementation (B3):** extending the three-way gate's fixtures to
frozen/damaged/lifespan/IG states immediately caught a REAL silent feature skew — `is_blocking`
was 1 on FROZEN units in both C++ legs while the faithful JS engine (= training data) says 0; the
old code comment claiming "the SWF keeps frozen units blocking-mode" was wrong. Fixed engine-side
(V2Record + NeuralNet inference gated on `Card::isFrozen()`); the fifth skew of the v2.2.1 class.
Inference on frozen states changes marginally vs all pre-fix numbers (same precedent as v2.2.1).

**Deferred one-off measurements (owner to schedule):** B4 (the 128-game cross-path bound for the
steam yardstick — until then steam is trend-only, README documents the delta as unbounded) and B7
(the (N,c) discrimination re-probe at c=0.15/N=4000 — the retired v3 §1f UCB-indifference-band
probe rule named it the first experiment if checkpoint trends looked exploration-starved; the v4
escalation levers are §6 O6/O3).

---

## Accepted limitations & open items (living register)

The canonical list of things known-imperfect and deliberately tolerated. Seeded 2026-06-12 from the
Jun-11 resolution table + the Jun-12 audit; **review at every promotion decision** — an accepted
limitation whose preconditions changed is a bug. One line each; details at the pointer.

| Item | Status / rationale | Pointer |
|---|---|---|
| **F-SKEW-1 RETRACTED** — the deep-audit's "6th silent skew" (fragile `is_blocking` on a hand-built fixture) | **REPORTED THEN RETRACTED as a false positive.** C++ `isFrozen` is CORRECT (live rule = chill ≥ currentHP); **do NOT change it.** (The genuine v2.2.1-class skew — frozen blockers reading is_blocking=1 — was the SEPARATE Jun-13 B3 fix below; this retraction is the audit's later hand-built-fixture false alarm.) | `docs/superpowers/plans/2026-06-13-rl-loop-deep-audit-FINDINGS.md` |
| **Draw/stagnation rule OPEN (engine-side, brainstorm-first)** | 3 of 1,032 Phase-0 games hit the 200-turn cap = genuine DRAWS (the audit's "no stagnation detection"). A 3-fold-repetition rule OR mirroring the SWF client's conditional "Offer Draw" is a NEW design decision to **brainstorm** — out of scope for the v4 config/Python/PS reframe | replays `training/data/rl_iter_1/replays/general/game_{0171,0383,0818}.json.gz` |
| **Self-play P2 advantage ~64% (P0 wr 0.344, marginally below [0.35,0.65])** | NOTED, not blocking — audit-known, set/strength-dependent; the data is non-degenerate (sane mean, not all draws) | K=1 entry anomaly (3); rl_campaign §1b |
| Counterfactual blindness of value-only RL (no signal on unplayed branches); v4 EpsilonLate=0.05 is the general late-exploration compromise | ACCEPTED with watch-stats (game-length/seat non-degeneracy, late sampled fraction). The durable fix is the O6 policy head + PUCT (named, deferred) | rl_campaign §1b/§6 |
| Outcome reproducibility at Threads:8 does not exist (card-set sequence only) | ACCEPTED — per-iteration replay/sidecar archive is the forensic substitute | rl_campaign §1d |
| Self-play seeds | DECIDED 06-13 (J4): derive from base+K (fresh sets per iteration). v4: one general block at base 5600 | preflight frozen_tuple |
| iid Wilson pooled CI + paired per-card-set CI | paired CI (A4 rounds CSV + wilson.paired_round_ci) reported in every manifest cell alongside the pooled Wilson; the v4 collapse signal reads the win-rate point estimate, not a CI bound | eval/README.md stats section |
| ~~Automated verdict is detect-harm only~~ | **SUPERSEDED by v4 (2026-06-14):** there is no REJECT/REVIEW verdict — a boolean `collapse` (origin general WR < 0.35) is the only abort signal; promotion = promote-unless-collapse via promote_candidate.ps1 | rl_campaign §3 |
| Tactical suite (ktink_t9 knife-edge, telemetry-only) | **SUPERSEDED by v4:** the stage-6 tactical suite was IG-specific and REMOVED with the IG axis — no tactical gate runs | rl_runbook (no stage 6) |
| Stage-5 parity gate pins export+forward arithmetic ONLY (not feature extraction) | tol now 1e-4 + stratified sample + honest scope docs (B2); extraction pinned by the three-way gate | rl_runbook stage 5 |
| A6 maxPlayer-negation seam | BUILT 06-13 (B1): eval/a6_orientation_check.py — 4 decided-game states, both seats, engine airootwinrate must side with the outcome; live-validated. v4 (Task 10): **auto-run at preflight** (`correctness_gates`) + the engine-exe sha pin (`engine_sha`) so an unrecorded rebuild can't silently flip the sign before an unattended night | rl_campaign A6 / §2 |
| Three-way feature gate fixtures | EXTENDED 06-13 (B3): + frozen/damaged/lifespan/IG elite states — which CAUGHT and fixed the frozen-blocker is_blocking skew. Still not covered: engine-native self-play sidecars (no JS leg by construction) | test_three_way_feature_parity.py |
| unit_index.json missing ⇒ silent globals-only net on config path | ACCEPTED-Low (file git-tracked; loop never touches it); preflight check recommended | audit 06-12 §5 |
| In-tree IG auto-fire bias (T3-5/T4-9): non-root tree nodes still auto-fire IG | ACCEPTED known limitation | Jun-10 audit |
| Engine variant-count assert absent (campaign shape policy lives in preflight, not engine) | SKIPPED — owner decision | verification doc T3-6 |
| H2 "identical players ≈ 50%" self-match preflight gate | SKIPPED — owner decision (per-seat columns landed instead) | verification doc |
| Book entry-validity drift vs cardLibrary: partial entry drop silent; full-empty warns once | ACCEPTED (N-12) | verification doc |
| Hard-abort guards make every referenced weights file a startup dependency (rename ⇒ brick) | ACCEPTED (N-11) — preflight check 5 covers driver runs | verification doc |
| tau-probe producer script ad-hoc (artifact committed, producer not) | OPEN-Low (N-9) | verification doc |
| ~~Steam anchor cross-path delta effectively unbounded; draw/n conventions differ~~ | **SUPERSEDED by v4:** steam (the 2016 cross-path binary) is RETIRED — the absolute-strength anchor is now the SAME-PATH AB `MasterBot_SWF`, so the cross-path-delta caveat no longer applies | rl_campaign §6; README anchors |
| Base+8 (RandomCards:8) only, self-play AND eval — real sets span Base+5..11 | ACCEPTED scope limit: conclusions are Base+8-scoped | audit 06-12, rl-design-07 |
| Manual-rerun export clobber | CLOSED 06-13: parent is sha-content-pinned (preflight parent_sha) + driver guards candBin != parent_bin + promote_candidate.ps1 verifies fresh re-export == on-disk bin | preflight check 15 |
| Training seed | PINNED 06-13 (2026000+K via the driver) | run_iteration stage 3 |
| Stage-8 coverage | FIXED 06-13 (C8): generator-vs-candidate semantics note + IG telemetry. v4: coverage is **telemetry-only** (no axis under test) and stage 8 is **non-fatal** — `ig_contrast_pairs` is recorded but no longer a gating watch-stat | action_coverage.py; rl_runbook stage 8 |

---

*Maintenance: this file is the durable home for (a) iteration entries, (b) the decision table, (c) the
limitations register. When an audit/fix doc dispositions an item, update the register line here and
point at the doc — do not let the canonical status live in a doc labelled "historical record".*
