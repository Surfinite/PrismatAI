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
> kill/escalation rules) → `eval/rl_runbook.md` (what each stage does) → `eval/README.md` (eval harness
> + statistics) → this file (what has actually happened and what is accepted-broken) → the audit
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

*(No iterations run yet. The first real entry should be `-K 1` — but see "Pre-campaign state" below:
the 2026-06-12 audit recommends pre-iter-1 changes that would re-freeze parts of the tuple first.)*

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
| 2026-06-13 | **Rehearsal corpus → ELITE cut (owner proposal)**: SLICE of `human_1800_v2.h5` (provenance inherited — no DB eligibility, no re-extraction): per-game min(H5 rating stamps) ≥2000 + replay-JSON `timeInfo` increment ≥45s, random-sampled ~5k games/~150k records. Measured pool: 23,303 games at 2000+ (1,558 of them absent from replays.db — ladder-DB codes; tc read from `replays_archive/` JSONs, present for every H5 code by construction); ≥19,365 confirmed at 45s+ (~530k records). Val set/tripwire UNCHANGED (human_val_1700) | removes anchor-pulls-toward-weaker-play (same logic as the MB-fleet exclusion); fewer clock blunders = cleaner labels; doubles as the C6 RAM fix; HP-tier → in the pre-K1 re-freeze | worklist C6 |
| 2026-06-12 | **J7 DECIDED (a)**: two-tier tuple — HP knobs (N, τ, K, ε, c, schedule) = new-campaign tier; scale knobs (rounds, seed policy, eval n) = re-anchor-only tier; encode in campaign_frozen.json | future volume tuning stays cheap and legal | audit §6, selfplay-06 |

---

## Pre-campaign state (2026-06-12)

Mechanics ALL GREEN (216/216 tests, preflight 10/10, parent bit-identical both repos, baselines
sha-verified). The 2026-06-12 audit's §1.5/§11 list the pre-`-K 1` decisions the owner has not yet
made: promotion policy pre-registration, eval-budget re-allocation, training-dose increase
(SWA/rehearsal/rounds), per-iteration self-play seeds, promotion script + sha-pinned parent, the A6
orientation test, and a full-size stage-3 dry run. Record each decision in the table above when made.

---

## Accepted limitations & open items (living register)

The canonical list of things known-imperfect and deliberately tolerated. Seeded 2026-06-12 from the
Jun-11 resolution table + the Jun-12 audit; **review at every promotion decision** — an accepted
limitation whose preconditions changed is a bug. One line each; details at the pointer.

| Item | Status / rationale | Pointer |
|---|---|---|
| Counterfactual blindness of value-only RL (no signal on unplayed branches); εlate=0.05 ≈ 0.69 dev/game is the chosen compromise | ACCEPTED with watch-stats (d_rl, late sampled fraction) — but see audit §1.2: quantified on the IG axis this is ~single-digit counterfactuals/iter | rl_campaign §1b; audit 06-12 §1.2 |
| Outcome reproducibility at Threads:8 does not exist (card-set sequence only) | ACCEPTED — per-iteration replay/sidecar archive is the forensic substitute | rl_campaign §1d |
| Self-play + eval card sets FIXED across iterations (Seeds 55/56/2026) | **UNDECIDED — surfaced 2026-06-12**; either derive seeds from K or document fixed-panel rationale | audit 06-12 §2 |
| iid Wilson on colour-swap-paired games; no per-set scores emitted; draws=half-win | ACCEPTED Jun-10 ("no per-set scores exist") — rationale challenged: per-seat columns proved the HTML is editable; paired CI is the free power upgrade | audit 06-12 §7, rl-design-05 |
| Automated verdict is detect-harm only (P(REJECT|parity)=2.1%, |−5pp|=18%); all real decisions human | ACCEPTED by design — but no promotion policy is pre-registered (open) | rl_campaign §3; audit 06-12 §1.4 |
| ktink_t9 tactical case permanently un-armed (11 PASS / 3 FAIL knife-edge @3s) | ACCEPTED — budget-dependent; never gates | verification doc N-5; rl_runbook stage 6 |
| Tactical armed-case stability screened only under the parent, single-shot @3s | OPEN — majority re-run / deployment-budget re-baseline recommended | audit 06-12 §5 |
| Stage-5 parity gate pins export+forward arithmetic ONLY (not feature extraction), tol 1e-3 vs 1e-6 floor | OPEN — docs overstate scope; tighten + stratify recommended | audit 06-12 §5 |
| A6 maxPlayer-negation seam has no end-to-end orientation test | OPEN (~2h fix recommended pre-iter-1); wrong comment at UCTSearch.cpp:374 | rl_campaign A6; audit 06-12 §5 |
| Three-way feature gate fixture: no is_frozen / lifespan / damaged-HP / IG states | OPEN — add 3–5 fixture states | audit 06-12 §5 |
| unit_index.json missing ⇒ silent globals-only net on config path | ACCEPTED-Low (file git-tracked; loop never touches it); preflight check recommended | audit 06-12 §5 |
| In-tree IG auto-fire bias (T3-5/T4-9): non-root tree nodes still auto-fire IG | ACCEPTED known limitation | Jun-10 audit |
| Engine variant-count assert absent (campaign shape policy lives in preflight, not engine) | SKIPPED — owner decision | verification doc T3-6 |
| H2 "identical players ≈ 50%" self-match preflight gate | SKIPPED — owner decision (per-seat columns landed instead) | verification doc |
| Book entry-validity drift vs cardLibrary: partial entry drop silent; full-empty warns once | ACCEPTED (N-12) | verification doc |
| Hard-abort guards make every referenced weights file a startup dependency (rename ⇒ brick) | ACCEPTED (N-11) — preflight check 5 covers driver runs | verification doc |
| tau-probe producer script ad-hoc (artifact committed, producer not) | OPEN-Low (N-9) | verification doc |
| Steam anchor cross-path delta effectively unbounded (16-game check); draw/n conventions differ from C++ anchors | OPEN — trend use only | audit 06-12 §5, steam-07 |
| Base+8 (RandomCards:8) only, self-play AND eval — real sets span Base+5..11 | ACCEPTED scope limit: conclusions are Base+8-scoped | audit 06-12, rl-design-07 |
| Manual-rerun export clobber (same-K re-run overwrites the iter bin) | OPEN — promote script + sha pin recommended | audit 06-12 §4, ops-promote-01 |
| Training seed unpinned (candidate irreproducible) | OPEN-Low | audit 06-12 §3 |
| Stage-8 coverage reads the FORCED slice only and describes the PARENT's behaviour | OPEN — doc or widen deliberately | audit 06-12 §8, docs-03 |

---

*Maintenance: this file is the durable home for (a) iteration entries, (b) the decision table, (c) the
limitations register. When an audit/fix doc dispositions an item, update the register line here and
point at the doc — do not let the canonical status live in a doc labelled "historical record".*
