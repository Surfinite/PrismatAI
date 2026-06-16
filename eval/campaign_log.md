# RL Campaign Log — iteration ledger + accepted-limitations register

> **What this is.** The per-iteration HUMAN record the campaign's epistemics depend on, plus the living
> register of accepted limitations and open items. `rl_campaign.md` §5 mandates "a changelog mapping
> every win-rate point to exactly one (config-hash, net-hash) delta" — this file is that changelog.
> The MACHINE record lives elsewhere (`eval/manifests/eval_iter_<K>.json`, the dashboard,
> `training/models/rl_iter_<K>/run_metadata.json` lineage stamps); this file records what the machine
> cannot: the decision, the reasoning, and the anomalies. Append-only; never rewrite old entries —
> correct them with a dated note.
>
> **Reading order for a new maintainer:** `eval/rl_campaign.md` (the contract: frozen tuple, verdict,
> kill/escalation rules) → `eval/rl_runbook.md` (what each stage does) → `eval/README.md` (eval harness + statistics) → this file (what has actually happened and what is accepted-broken) → the audit
> trail in `docs/superpowers/plans/` (2026-06-09 / 06-10 / 06-11 / 06-12, historical).

---

## Iteration entries

Template (copy for each iteration; one entry per `run_iteration.ps1 -K <K>` attempt, including failed
or abandoned attempts):

```markdown
### Iteration K=<k> — <date> — <PROMOTED | ITERATED | REJECTED | INVALIDATED | ABORTED stage N>

- **Parent:** <parent_bin name + sha256 prefix> (pt: <parent_pt sha prefix>)
- **Candidate:** neural_weights_rl_iter<k>.bin <sha256 prefix>
- **Config identity:** dave config.txt @ <git short-sha>, campaign_frozen.json @ <git short-sha>
- **Manifest:** eval/manifests/eval_iter_<k>.json — verdict: <REJECT|REVIEW|INCOMPLETE>
- **Headline numbers:** iter0/general <w>/<n> (CI <lo>–<hi>); d_rl(forced) <x>pp; d_reg <x>pp;
  narrow <x>%; steam <x>%  (record "not run" where applicable)
- **Watch-stats (rl_campaign §1b):** late sampled fraction <x> (expect ≈0.05); IG-feasible records
  <n>/<total>; IG click dist <…>; game length vs baseline <x>; tripwire Δval-acc <x>pp;
  prediction-movement probe mean|ΔV| <x> (if instrumented)
- **Decision + reasoning (the load-bearing paragraph):** <why promote/iterate/stop — what evidence
  moved you, what you discounted as noise, what you pre-commit to checking next iteration>
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
(the (N,c) discrimination re-probe at c=0.15/N=4000 — §1f names it the first experiment if
checkpoint trends look exploration-starved).

---

## Accepted limitations & open items (living register)

The canonical list of things known-imperfect and deliberately tolerated. Seeded 2026-06-12 from the
Jun-11 resolution table + the Jun-12 audit; **review at every promotion decision** — an accepted
limitation whose preconditions changed is a bug. One line each; details at the pointer.

| Item | Status / rationale | Pointer |
|---|---|---|
| Counterfactual blindness of value-only RL (no signal on unplayed branches); εlate=0.05 ≈ 0.69 dev/game is the chosen compromise | ACCEPTED with watch-stats (d_rl, late sampled fraction) — but see audit §1.2: quantified on the IG axis this is ~single-digit counterfactuals/iter | rl_campaign §1b; audit 06-12 §1.2 |
| Outcome reproducibility at Threads:8 does not exist (card-set sequence only) | ACCEPTED — per-iteration replay/sidecar archive is the forensic substitute | rl_campaign §1d |
| Self-play seeds | DECIDED 06-13 (J4): derive from base+K (fresh sets per iteration); eval panels stay FIXED 2-seed (2026/2027) — comparability + partial generalization | preflight frozen_tuple/anchor_blocks |
| iid Wilson pooled CI is the verdict statistic | paired per-card-set CI now BUILT (A4 rounds CSV + wilson.paired_round_ci, reported in every manifest cell); verdict switches to it only after validation on real runs | eval/README.md stats section |
| Automated verdict is detect-harm only | promotion policy NOW PRE-REGISTERED (J2 promote-unless-harm via promote_candidate.ps1; checkpoint origin evals carry the evidence) | rl_campaign §3 |
| ktink_t9 tactical case permanently un-armed (11 PASS / 3 FAIL knife-edge @3s) | ACCEPTED — budget-dependent; never gates | verification doc N-5; rl_runbook stage 6 |
| Tactical suite | DECIDED 06-13 (J6): telemetry-only while local (never aborts); a regression counts as harm only when REPRODUCED 3-5x | rl_runbook stage 6 |
| Stage-5 parity gate pins export+forward arithmetic ONLY (not feature extraction) | tol now 1e-4 + stratified sample + honest scope docs (B2); extraction pinned by the three-way gate | rl_runbook stage 5 |
| A6 maxPlayer-negation seam | BUILT 06-13 (B1): eval/a6_orientation_check.py — 4 decided-game states, both seats, engine airootwinrate must side with the outcome; live-validated; run after ANY engine change | rl_campaign A6 |
| Three-way feature gate fixtures | EXTENDED 06-13 (B3): + frozen/damaged/lifespan/IG elite states — which CAUGHT and fixed the frozen-blocker is_blocking skew. Still not covered: engine-native self-play sidecars (no JS leg by construction) | test_three_way_feature_parity.py |
| unit_index.json missing ⇒ silent globals-only net on config path | ACCEPTED-Low (file git-tracked; loop never touches it); preflight check recommended | audit 06-12 §5 |
| In-tree IG auto-fire bias (T3-5/T4-9): non-root tree nodes still auto-fire IG | ACCEPTED known limitation | Jun-10 audit |
| Engine variant-count assert absent (campaign shape policy lives in preflight, not engine) | SKIPPED — owner decision | verification doc T3-6 |
| H2 "identical players ≈ 50%" self-match preflight gate | SKIPPED — owner decision (per-seat columns landed instead) | verification doc |
| Book entry-validity drift vs cardLibrary: partial entry drop silent; full-empty warns once | ACCEPTED (N-12) | verification doc |
| Hard-abort guards make every referenced weights file a startup dependency (rename ⇒ brick) | ACCEPTED (N-11) — preflight check 5 covers driver runs | verification doc |
| tau-probe producer script ad-hoc (artifact committed, producer not) | OPEN-Low (N-9) | verification doc |
| Steam anchor cross-path delta effectively unbounded (16-game check); draw/n conventions differ from C++ anchors | OPEN — trend use only | audit 06-12 §5, steam-07 |
| Base+8 (RandomCards:8) only, self-play AND eval — real sets span Base+5..11 | ACCEPTED scope limit: conclusions are Base+8-scoped | audit 06-12, rl-design-07 |
| Manual-rerun export clobber | CLOSED 06-13: parent is sha-content-pinned (preflight parent_sha) + driver guards candBin != parent_bin + promote_candidate.ps1 verifies fresh re-export == on-disk bin | preflight check 15 |
| Training seed | PINNED 06-13 (2026000+K via the driver) | run_iteration stage 3 |
| Stage-8 coverage | FIXED 06-13 (C8): both slices + combined + explicit generator-vs-candidate semantics note + B6 ig_contrast_pairs watch-stat | action_coverage.py |

---

*Maintenance: this file is the durable home for (a) iteration entries, (b) the decision table, (c) the
limitations register. When an audit/fix doc dispositions an item, update the register line here and
point at the doc — do not let the canonical status live in a doc labelled "historical record".*
