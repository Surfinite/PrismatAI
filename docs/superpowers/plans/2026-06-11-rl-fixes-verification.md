# RL-Loop Post-Fix Verification Sweep (2026-06-11)

> ## ✅ RESOLUTION STATUS (2026-06-12 — added after the fact; the body below is the unmodified historical record)
>
> Everything below was addressed across main `427e53d..1a9788d` and dave `6e93480`+`eb52fa8` (all pushed
> to PrismatAlpha). Owner decisions where an item was deliberately NOT implemented are marked. Repo-wide
> tests: **214 passed / 0 failed**.
>
> | Item | Status | Where |
> |---|---|---|
> | **N-1** warmup-LR floor | **FIXED** | main `33f9988` — `resolve_warmup` rescales (peak LR 1e-6→1e-5, test-pinned) + `--swa-lr` (ps1 passes 5e-6) |
> | **N-2** parent-side provenance | **FIXED** | main `66b444f`+`b09d46b` — preflight pins ALL FOUR parent players; engine parent-load stamp per C++ anchor; candidate==parent guard |
> | **N-3** K>1 parent not promotion-tied | **FIXED** | main `66b444f` — ParentPt always = frozen `parent_pt`; promotion (editing campaign_frozen) is the only lineage mechanism |
> | **N-4** whole-game sampling risk | **SUPERSEDED (owner decision)** | regime v2: dave `d284538` + main `b7d299e` — K=12 + EpsilonLate=0.05 (early-noise/late-precision) + ⅔ general/⅓ forced mix; re-screen ALL PASS; measured 0.69 late deviations/game (vs v1's 40-46% non-argmax); risk + watch-stats documented in rl_campaign §1b |
> | **N-5** tactical gate vacuous | **FIXED** | main `037f0c0` — 4 armed human-agreement cases @ c=0.3 (1 under-click + 3 over-click sentinels); gate proven to fire both directions. NOTE: the 2 other click-positive candidates measured FLAKY (18%/33% false-fail @ 3s) and were dropped; ktink found to be a knife-edge (11 PASS/3 FAIL) and stays un-armed |
> | **N-6** A6 prose-only | **FIXED** | main `6afdb41` — `training/tests/test_perspective_roundtrip.py` (13 tests; v221 sides decided positions 97.5%, inversion would score ~2.5%); the C++ maxPlayer-negation boundary documented as not covered |
> | **N-7** baseline discontinuity | **DOCUMENTED** | main `b54cbd8` — rl_campaign §1c + CLAUDE.md port-landed note; c=0.3 retained on monotonicity |
> | **N-8** "rule out harm" wording | **FIXED** | main `b54cbd8` — "detect proven harm" + the power numbers (P(REJECT\|−5pp)≈18%, \|parity)≈2.1%) in run_eval/campaign/README |
> | **N-9** tau-probe producer script | **OPEN (Low)** | the artifact (`eval/tau_probe_n1000.json`) is committed; the producer remains ad-hoc |
> | **N-10** calibrate_n prose | **FIXED** | main `1a9788d` — header truth-up (screen-not-ranking, frozen N, Threads:8 effects); `n_calibration.json` committed as the superseded screen artifact |
> | **N-11** weights = startup dependency | **ACCEPTED** | by design (the X5b guard); preflight `reference_graph` covers driver runs |
> | **N-12** book entry-validity drift | **ACCEPTED** | partial drop stays silent; full-empty warns once; preflight `book_sizes` pins the campaign books |
> | §3.1 "≈600 games" claim | **FIXED** | `b54cbd8`/`c4bebe3` reframed (detect-harm bar, ~786 for +5pp) |
> | §3.2 A6 | **FIXED** | = N-6 |
> | §3.3 `any_root_truncated` uncommitted | **RESOLVED** | `n_calibration.json` now committed (1a9788d) and carries the cited keys |
> | §3.4 runbook use_dsnn overstatement | **FIXED** | now literally true: preflight check 9 `use_dsnn_sentinel` (stage 0) + run_eval re-assert |
> | §3.5 calibrate_n self-doc | **FIXED** | = N-10 |
> | OUTSTANDING: H2 per-seat output | **FIXED** | dave `6e93480` — `P1 W/G`/`P2 W/G` statsTable columns + stdout |
> | OUTSTANDING: H2 self-match sanity gate | **SKIPPED (owner decision)** | not implemented in any form |
> | OUTSTANDING: H3 same-name aliasing | **FIXED** | dave `6e93480` — results credited by SLOT index; same-name self-match blocks now legitimate (`Name (gN)` rows, no `-nan`); no duplicate-name guard needed |
> | OUTSTANDING: E7-2/E7-3/M-09 contamination | **FIXED** | main `1a9788d` — preflight check 9 covers stages 6/8 from stage 0 |
> | OUTSTANDING: M-11/B-* vectorize | **FIXED** | main `1a9788d` — STRICT zero-drop default (counters; missing `outcome_p0` = DROP, never 0.0; truncation detection live; temp+rename; `--allow-drops` forensic) |
> | OUTSTANDING: T3-6 residual soft-asserts | **FIXED (lookups)** / **SKIPPED (variant-count, owner decision: campaign shape policy lives in the preflight, not the engine)** | dave `6e93480` — getPlayer/getPartialPlayer/getMoveIterator → FATAL |
> | OUTSTANDING: low engine items (T3-9/10/11, T4-10, L-09, L-13) | **FIXED** | dave `6e93480` — incl.: UCTConstant now accepts integer JSON numbers; the "2 unmapped types" are the engine `None` sentinels (benign, now named) |
> | OUTSTANDING: E9 family | **FIXED** | seed-semantics doc (rl_campaign §1d); worker-RNG stream-0 collision fixed (dave `6e93480`); cal family ALL Threads:8 (dave `eb52fa8` — matched sets across the N-family; costs documented in calibrate_n header) |
> | OUTSTANDING: T4-6 query_move default | **FIXED** | main `427e53d` — defaults to the widened IGsubset root + echoes resolved iterators/c |
> | OUTSTANDING: artifact quarantine residue | **FIXED** | main `1a9788d` — `n_calibration.json` committed; 28 invalidated Jun-4→9 HTMLs → `bin/tests/_invalidated_jun4-9_crippled_window/` + README |
> | OUTSTANDING: E8 residue | **PARTIAL** | P-1 minimal lineage (window H5 `{path,bytes,sha256}` in run_metadata) FIXED in `1a9788d`; manual-rerun export clobber + shared parity-sidecar dir remain OPEN/PARKED (sidecar archiving = replay-feature scope per owner) |



> **What this is.** Independent verification that the fix session's ~21 commits (main `2654e21..98c2aae`,
> dave `26075fa..6037382`) actually resolve the issues in BOTH audit reports
> (`2026-06-09-rl-selfplay-loop-audit-FINDINGS.md`, `2026-06-10-…-independent.md`), and that the fixes
> themselves are sound. Method: both reports + all fix commits read; 6 parallel verifiers (training /
> eval-gate / engine guardrails / campaign tuple / SWF+anchors / outstanding-sweep+docs); empirical
> re-runs in the isolated scratch bin. Raw agent output: `eval/_audit_scratch/verify_fixes_final.json`.
> Report only — nothing was changed.

---

## 0. Bottom line

**The fix session did real, verifiable work: every Critical and High finding from both audits is
FIXED or honestly ACCEPTED-as-documented, and the fixes match the recommendations point-by-point.**
My empirical re-runs confirm the headline guards: a bad `WeightsFile` and a dangling opening book now
**FATAL+abort at parse time with named diagnostics** (previously: silent success / mid-run segfault);
`preflight_config.py` passes 8/8 against the live config; the campaign tuple is byte-consistent across
`campaign_frozen.json` / `config.txt` / preflight / docs; the v221 parent checkpoint is **bit-identical**
(16/16 tensors, max|Δ|=0) to the deployed bin.

**But the sweep found one new High that should be fixed before `-K 1`, and a handful of Mediums:**

1. **(High) The RL fine-tune's learning rate is pinned at the 1e-6 floor — the warm-started candidate
   will barely train.** The M-04 epoch fix correctly sizes an iteration to ~78–84 optimizer steps at
   campaign scale, but stage 3 doesn't override `--warmup-steps` (default **1000**): warmup never
   completes, so `lr = max(min_lr 1e-6, 1e-5·step/1000)` ≈ **1e-6 for the entire run** (and SWALR's
   `swa_lr = lr×0.1 = 1e-6 anyway`). Net effect: candidate ≈ parent, tripwire passes trivially, eval
   reads ~50%, every iteration returns REVIEW with no signal — a *null-iteration generator*, the
   mirror image of the E1 bug. Fix is one argv item (e.g. `--warmup-steps` ≈ 5–10% of total steps, and
   reconsider `swa_lr`). *(train.py:732-753, :907; run_iteration.ps1:226-231)*
2. **(Medium) Parent-side provenance is still unchecked.** Preflight's `parent_repin` pins only
   `RL_Eval`; `RL_Eval_iter0` (the verdict opponent), `RL_SelfPlay` (the data generator), and
   `RL_Narrow` get existence checks only. run_eval's engine-load verification covers the candidate
   seat only. After the first promotion, a forgotten manual repoint silently turns "candidate vs
   parent" into "candidate vs grandparent" — the exact Jun-8 failure class, one player over.
   *(preflight_config.py:345-357; run_eval.py:219-236)*
3. **(Medium) K>1 warm-start is not tied to promotion.** `run_iteration.ps1:73-79` auto-resolves the
   parent to iter-(K−1)'s SWA **even if that candidate was REJECTED** — lineage can absorb a rejected
   net. Parent resolution should come from the frozen/promotion record.
4. **(Medium) The whole-game sampling design carries an undocumented label-quality risk — and the τ
   choice is quantitatively a near-no-op.** τ=0.7 moves the median top-share only 0.141→0.159
   (near-uniform distributions are invariant under sharpening); the binding decision was **K=999**,
   making **40–46% of all moves non-argmax** (measured on the frozen-tuple rescreen) while candidates
   are evaluated/deployed at argmax/100k. Root cause of the flat visits: the UCT indifference radius
   at N=1000/c=0.3/k≈13 is ~9pp of win-prob — sampling∝visits there ≈ uniform among portfolio
   candidates. Mitigations are real (children are whole-turn portfolio moves; decisive positions DO
   concentrate — probe Q3 top-share 0.56; the 32-game rescreen passed), but games run **+4.7 turns
   longer (+3.7 SE)** than the MB baseline — consistent with noisier play. This is the opposite pole
   from both AlphaZero practice (τ→argmax after ~30 plies) and the audits' H4 recommendation
   (argmax + late-ε 0.05–0.1). Honest about being judgment-based; watch iter-1's d_rl and be ready to
   anneal τ late-game.
5. **(Medium) The IG tactical gate is currently vacuous.** The regenerated c=0.3 baseline records the
   single curated ground-truth case (`ktink_t9_ig`) as `passed:false`, and the suite gates only on
   baseline-passed cases — so the IG axis's one known-move check can never fail a candidate, even one
   that regresses on it. Honest (README documents the c/budget dependence) but worth knowing: the
   tactical stage is informational until something first passes at the frozen budget.
6. **(Medium) `rl_campaign.md` A6 (perspective round-trip) is documented as "a REQUIRED pre-iter-1
   gate" and implemented nowhere** — no stage, no preflight check, no test. A doc-only REQUIRED gate
   inside a "prerequisites mostly RESOLVED" doc is the same doc-vs-code gap pattern that produced E1.
7. **(Medium) Historical-baseline discontinuity is undocumented.** `09c5436` (SWF-faithful buy tree +
   4-entry book) changed partials consumed by **all** deployed players AND the Playout evaluator. The
   campaign correctly re-baselines forward (tuple frozen post-port; preflight asserts the post-port
   shape), but nothing records that every pre-Jun-10 number — including the cValue sweep that chose
   the frozen **c=0.3** — was measured against a different opponent.

**Dismissed:** the "protocol binaries are one commit stale" concern (raised by two verifiers from
mtimes) is **wrong** — direct string search inside all three exes shows every guard from both
guardrail commits present (built 23:21, committed 23:25). Binaries are current.

---

## 1. Status roll-up (union of both reports)

### FIXED — verified in code (and empirically where marked ⚡)

| Finding | Fix | Verification highlight |
|---|---|---|
| **C1/E1/F-01** random-init; no warm-start | `--init-weights` (2654e21/9e4f1b2/e344cef) | strict load, all 3 ckpt formats, **before** `AveragedModel`; `--rl-mode` hard-fails without init ("refusing to repeat" the E1 bug); run_metadata stamps it; parent `.pt` **bit-identical** to deployed v221 bin (16/16 tensors, SHA `22cc647e…` matches commit stamp); 9 tests |
| E1-2 `--resume` trap | mutual-exclusion + separate flag | as recommended |
| **M-03/E1-3** val leakage | `--val-file human_val_1700_v2.h5` | disjointness ground-truth-checked; v221's own 71.8% on the same file → apples-to-apples tripwire |
| **E1-6** no quality tripwire | stage 4.5 | aborts if candidate < parent − 3pp on held-out val, before parity/tactical/eval |
| **M-04/E1-4** epoch coupling | `num_samples = ceil(sp/(1−frac))` | correct; **but exposes the warmup-LR floor (new High)** |
| M-10 export self-test ignored | `sys.exit(1)` on verify failure | verified |
| **C3/T1-1/F-05** GO gate unsatisfiable | **REJECT/REVIEW/INCOMPLETE** non-inferiority verdict (2e73ecd) | nothing auto-promotes; REJECT only on `general ci_upper<0.5` (proven harm); E/Y demoted to metadata; honest iid-Wilson notes everywhere; 77/77 tests rewritten incl. an explicit inversion of the old contradiction-encoding test |
| **H6/T1-2** d_reg point estimate | gate is CI-based | verified |
| **H5/E5-1** dead statistics | **removed** + tripwire test | deliberate drop of clustered/sequential, documented |
| **F-07/NEW-2/M-14** manifest all-or-nothing; stage-7 no restore | incremental atomic writes per pool/anchor + crash tests; stage-7 try/finally with parent from `campaign_frozen.json` (98c2aae) | verified |
| **E6-1/L-12** dashboard | general(gate) column, † non-gating markers, corrected iter0/narrow/steam labels | verified |
| **H1/T3-1/F-04** silent empty/missing book | `FATAL … opening book 'X' not defined (referenced by partial player 'Y'). Aborting.` | ⚡ X5a re-run: parse-time abort (was: silent "Tournament complete") |
| **T3-2/H8/X5b** weights fail → segfault | `FATAL … could not load NeuralNet weights … Aborting.` + UCT value-path guard | ⚡ X5b re-run: parse-time abort (was: warning + SIGSEGV) |
| unknown **filter** (incl. subsetFilter path) | hard-fail (26075fa + d0ec633) | filterless partials remain legal (no false positives found) |
| **E3-1/M-E3/F-06** N three-way inconsistency; silent rewrite | `campaign_frozen.json` (N=1000, τ=0.7, K=999, ε=0, c=0.3, Threads:8) + run_iteration **asserts** (no rewrite) + preflight `frozen_tuple` | ⚡ preflight 8/8 PASS live; tuple byte-consistent everywhere |
| **H4** opening-only exploration | whole-game sampling (K=999) | fixed by a *different* mechanism than recommended — see new-concern #4 |
| **M-eps** ε=0.25 by guess | ε removed (0.0), documented as uncalibrated | verified |
| **T2/N3/M-01** Threads:1 export | Threads:8 frozen | verified (both audits' X3 runs validated this) |
| **F-09/M-SWF8** buy-tree divergence | SWF-faithful `BuyEconFast`/`BuyOneDrone`/`BuyEcon`/`BuyEconLimited` (09c5436) | verified vs SWF blob; **applies to all chains incl. deployed** — see new-concern #7 |
| **E4/M-13** 4-entry book | SWF 4-entry `DefaultOpeningBook` | verified |
| **E6/M-E6/M-07** narrow-anchor confound | **RL_Narrow** = v221 + narrow root at the same budget (single-variable) | verified; replaces 35prop in anchor path; minor residue in calibrate prose |
| **F-08/E7-4** steam anchor mis-wired | rewired: candidate (DaveAI/RL_Eval+IGsubset) vs `masterbot2016_exe` at a permanent home outside the Steam install; preflight verifies it exists | verified |
| **M-06/T4-4** query_move c=2.0 | injects `UCTConstant 0.3` + tactical re-baseline at tuned c | verified (re-baseline exposed the ktink FAIL — new-concern #5) |
| **M-E7a/E7-1 (candidate side)** | config-WeightsFile assert + per-anchor engine-load-line hard-fail | PARTIAL overall: sha256 still compared-to-nothing; no engine hash echo; **parent side unchecked** (new-concern #2) |
| **H7/X6-1** calibration as ranking | demoted to "screening only"; "FROZEN by judgment" | honest |
| Quarantine (training side) | `training/{data,models}/_quarantine/…`, bin renamed `.quarantined-jun8` | verified |
| CLAUDE.md engine_v2 scoping | SkipColorSwap + OB-parity paragraphs scoped (98c2aae) | verified |

### ACCEPTED — documented limitations (reasonable)
Per-card-set score emission → clustered/paired CI (Tournament.cpp untouched; honestly noted);
sequential 128→256→512 escalation (deliberately dropped); M-E3b label-budget gap (now folded into the
τ/K design — see #4); T4-3 truncation ordering + `root_truncated` consumer (cap never binds; observe-only);
T3-5/T4-9 in-tree IG auto-fire bias (known limitation).

### OUTSTANDING — not addressed (none individually blocking, listed for the backlog)
- **H2 + self-match gate**: still no per-seat (P0/P1) output anywhere, and no "identical players ≈ 50%"
  sanity preflight — both audits' top instrumentation recommendation. Engine-side (~10 lines) + a
  preflight block.
- **H3/L-10/NEW-3**: `getPlayerIndex` same-name aliasing — `RL_Cal_N*`/`RL_Step2` self-match blocks still
  corrupt their own HTML rows (`-nan`, W=L by construction); no duplicate-name guard.
- **E7-2/E7-3/M-09**: contamination guards still only in run_eval; stages 6 (tactical) and 8 (coverage)
  run the FORCE_DSNN-susceptible protocol path unguarded, and stage 6 runs *before* run_eval's asserts.
- **M-11/B-1/B-2/B-5 + B-3**: vectorize_v2 drop semantics unchanged (exit-0 at any drop rate; silent
  unknown-unit drops; missing-label→0.0; dead TRUNCATED warning).
- **T3-6 (partial)**: unknown **iterator/partial/player** names still soft-assert → UB (book/filter/
  weights are now hard); engine-side variant-count assert absent (preflight's `iterator_shape` covers it
  config-side pre-run — acceptable, but manual engine runs bypass it).
- Low engine items: T3-9 BOM substr crash, T3-10 parsePlayers wrong-map, T3-11 `UCTConstant` IsDouble
  trap (note: query_move now emits 0.3 — verified as a real double), T4-10 CardFilter off-by-one,
  L-09 HTML fopen/format hazard, L-13 unmapped-types line names nothing.
- E9 family: Seed-at-Threads>1 semantics undocumented in campaign docs; cross-thread-mode card-set
  divergence; first-worker RNG stream collision. (Also: `RL_Cal_N1000` flipped to Threads:8 while
  sibling cal blocks stay Threads:1 — a future N-sweep would lose cross-N set comparability.)
- T4-6: query_move's *default* root iterator is still the narrow one (all committed drivers override).
- Partial-quarantine residue: invalid Jun-4→9 `bin/tests` HTMLs and the superseded committed
  `n_calibration.json` (recommended_N=512 in worktree, 256 at HEAD) remain unmarked/uncommitted.
- E8 family residue: manual-rerun export clobber, shared parity-sidecar dir (calibrate_n still doesn't
  clear sidecars), replay-window lineage/per-iteration provenance record (P-1) — procedural not
  mechanical. *(Sidecar archiving is replay-feature scope — parked per the owner.)*

---

## 2. New concerns introduced or exposed by the fixes (full list)

| # | Sev | Concern | Evidence anchor |
|---|---|---|---|
| N-1 | **High** | **Warmup-LR floor**: stage 3 omits `--warmup-steps` (default 1000) → at ~78–84 total steps the whole fine-tune runs at `min_lr` 1e-6 (and `swa_lr`=1e-6) → candidate ≈ parent → null iterations | train.py:732-753, :907, :1232; ps1:226-231 |
| N-2 | Med | Parent-side provenance unchecked (`RL_Eval_iter0`/`RL_SelfPlay`/`RL_Narrow` not value-pinned; engine-load check covers candidate only) | preflight:345-357; run_eval:219-236 |
| N-3 | Med | K>1 parent = previous iter's SWA regardless of promotion outcome | ps1:73-79 |
| N-4 | Med | Whole-game τ=0.7 ≈ near-uniform play on ~half of turns (40–46% non-argmax overall); τ choice a near-no-op (0.141→0.159); games +4.7 turns (+3.7 SE); label-quality risk undocumented | tau_probe rows (recomputed); `eval/_calib_scratch/n1000_rescreen*` |
| N-5 | Med | Tactical gate vacuous: only curated IG case at baseline-FAIL → can never gate a regression | tactical_baseline.json; tactical_suite.py:386 |
| N-6 | Med | A6 perspective round-trip: "REQUIRED pre-iter-1 gate" exists only in prose | rl_campaign A6; no stage/preflight/test |
| N-7 | Med | Buy-tree port changed ALL chains (incl. deployed + Playout): pre-Jun-10 numbers vs a different opponent; frozen c=0.3 rests on a pre-port sweep; discontinuity undocumented | config consumption trace; doc grep |
| N-8 | Low | "Rule out harm" wording overclaims (the rule rules IN harm: P(REJECT\|true −5pp)=18% at n=128); automated verdict near-information-free at n=128 (P(REJECT\|parity)=2.1%) — all real decisions are human REVIEW against ±8.5pp CIs | run_eval:17; rl_campaign:163 |
| N-9 | Low | tau probe has no committed producer script; "pre-agreed" rule not pre-registered in-repo | grep tau_probe |
| N-10 | Low | calibrate_n.py prose contradicts frozen doctrine (smallest-N ranking + hand-edit instruction + false Threads:1 rationale); worktree n_calibration still says 512 | calibrate_n.py:2-5,:57,:66-67 |
| N-11 | Low | Hard-abort guards make every referenced weights file a startup dependency for all 61 players — the `.quarantined-*` rename convention could brick startup if a referenced bin is renamed (today safe; preflight check 5 covers driver runs) | AIParameters.cpp:38-41 |
| N-12 | Low | Book entry-validity drift vs cardLibrary: partial entry drop still silent; fully-emptied book is warn-once (not fail) on the merge path | d0ec633 |
| — | — | *Dismissed:* protocol-binary staleness (string-level proof: all guards present in all 3 exes; built 23:21, committed 23:25) | exe string grep |

## 3. `rl_runbook.md` / `rl_campaign.md` cross-check (user-requested)

**Verified accurate** against HEAD: the stage list (0–8 + 4.5), the frozen tuple table, the
verdict semantics, anchor names (`ANCHOR_BLOCKS` ↔ config blocks), book sizes (4/50), rehearsal
schedule (0.30→0.10 @ 0.07), W=5, the ktink caveat text, the rescreen numbers, dead-stats note.
**Mismatches (5):**
1. `rl_campaign.md` §4.7 still claims "≈600 games/anchor at p<0.05" — both audits corrected this
   (~786 games for 80% power at +5pp, one-sided α=0.025; 600 ≈ 67–78% depending on framing).
2. A6 perspective round-trip: "REQUIRED pre-iter-1 gate" — unimplemented (N-6).
3. §1a cites `any_root_truncated: false across all N, max 33` — present in no committed artifact
   (per-N artifacts and the rescreen JSON lack those keys; only scratch logs carry them).
4. `rl_runbook.md:28` "no use_dsnn.txt … anywhere on an exe path" overstates — the assert is
   run_eval-only, stage-7-time, dave_bin-only (stages 6/8 + matchup paths unguarded → E7-3).
5. calibrate_n.py's self-documentation contradicts the frozen doctrine (N-10).

## 4. Empirical appendix (this sweep)

| Check | Result |
|---|---|
| X5b re-run (bad WeightsFile, rebuilt exe, scratch) | `FATAL … could not load NeuralNet weights 'no_such_file.bin' for player 'AUDIT_BadW' … Aborting.` exit≠0 at parse (was SIGSEGV mid-run) |
| X5a re-run (dangling LiveOpeningBook2) | `FATAL … opening book 'LiveOpeningBook2' not defined (referenced by partial player 'BuyOpeningBook2'). Aborting.` (was silent success) |
| `preflight_config.py` vs live config | 8/8 PASS (json_bom, run_true, iterator_shape, book_sizes, reference_graph, frozen_tuple, parent_repin, existences) |
| tau probe recompute (41 states) | bimodal: median norm-entropy 0.984 / top-share 0.141 (near-ties), Q3 top-share 0.564, max 0.997 (peaked); τ=0.7 sharpens peaked states 0.87→0.95 and leaves uniform states uniform |
| v221 parent provenance | agent-verified: 16/16 tensors bit-identical to deployed bin; SHA matches commit stamp |

## 5. Suggested ordering for the remaining work (recommendations only)

1. **N-1 warmup-LR floor** — one argv change; without it the first campaign iterations are null.
2. **N-2 + N-3** — extend `parent_repin` to all v221-pinned players; tie K>1 parent resolution to the
   promotion record. (~15 lines total across preflight + ps1.)
3. **N-6** — implement or demote the A6 gate before `-K 1`.
4. **H2 + self-match preflight + H3** — the per-seat column and duplicate-name guard remain the
   cheapest unbuilt diagnostics; they would have saved a day of forensics once already.
5. Doc fixes (§3 items, N-10) + mark the invalid Jun-4→9 artifacts + commit the superseded
   n_calibration with its "screen-only" relabel.
6. Watch-list for iter-1: d_rl flatness (N-4), tactical informational-only status (N-5), and the
   E7-3 unguarded protocol stages.
