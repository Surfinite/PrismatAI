# Meta-Review — RL Self-Play Loop Design Spec

> Plan: `2026-06-02-rl-selfplay-loop-design.md` · 6 external reviews · 2026-06-02
> Updated plan: `2026-06-02-rl-selfplay-loop-design-v2.md`

## A.1 — Review summary table

| Reviewer | Sentiment | Key focus | Unique insight |
|---|---|---|---|
| **R1** | Mixed-positive (most thorough) | Eval statistics / decision rule; value-only false-negative as a *measurement* problem | "A flat *local* result must not be read as a true negative" + add a §12 quantitative decision rule |
| **R2** | Mixed-positive | Eval methodology; root-sampling robustness; manifests/dashboard; export parity | Per-iteration **export-parity test** (PyTorch vs C++ `.bin`); candidate-level policy head as the cheap fallback |
| **R3** | Mixed-positive | Shallow-search label quality (false-negative); N-calibration | **High-sim data / deep-label reference batch**; distillation bootstrap; offline-RL iteration-0 |
| **R4** | Mixed (some shaky ML) | Search-depth collapse; statistical gating; P2 calibration | Dynamic sims budget; *(P2 residual-margin labels — rejected, see A.6)* |
| **R5** | Mixed-positive (concise) | Search-vs-action exploration; rehearsal anchoring | "Set N by measuring the 7s-AI's traversals ÷ 3–4"; rehearsal as a *gravity well* |
| **R6** | Mixed-positive | Same value-only/exploration gap; symmetry; multithread RNG | DeepSets symmetry question *(inapplicable — see A.6)*; tie-break RNG determinism |

**Overall:** unanimous that the *architecture, eval design (esp. the wide-untrained anchor), widening curriculum, and heuristic-change discipline are excellent and should be preserved.* Unanimous that the **#1 risk is a false-negative from value-only MCTS without a policy prior / root exploration**, compounded by under-specified eval statistics and an unprincipled sims budget.

## A.2 — Consensus points (ranked by reviewer count)

1. **[6/6] Value-only MCTS without a policy prior under-explores; visit-count temperature is "result diversity," not "search diversity."** UCB1 + small cValue concentrates visits, so the τ-sampler only reshuffles a narrow band. **Need root-level exploration injection** (ε-uniform over root candidates / Dirichlet-style root noise / forced root expansion so every candidate gets ≥1 visit). *This is the single highest-signal item.* (R1-C1, R2-#3, R3-3.1/3.2, R4-Sev1, R5-Q4, R6-3.1)
2. **[6/6] The sims budget `N` is unprincipled** — needs a calibration procedure + a concrete non-degeneracy check run *before* iteration 0. (R1-#2, R2, R3-4.1/4.4, R4, R5-Q2, R6-3.3)
3. **[6/6] Rehearsal anchoring** — drop/heavily-down-weight MasterBot-fleet from *value targets*; human-only anchor at a *named* fraction (~30% → decay); MB → coverage/val only. (R1-C5, R2-#6, R3-3.4/7.1, R4-Sev4/Removal, R5-#3, R6-3.4)
4. **[≥5] Eval statistics under-specified** — confidence intervals, target effect size, N-per-anchor, paired card sets + colour balancing, sequential testing, an "inconclusive" gate outcome, and a quantitative go/no-go rule replacing "any measurable improvement." (R1-C4/#5/#15, R2-#1, R4-Change2, R6, R3)
5. **[4/6] Make IG-optional the *first* RL campaign, not bare 5-variant first** — the supervised net already encodes the 5-variant space, so a bare run risks an ambiguous flat result. (R2-#4, R3-3.2, R5-Q3, R6-3.2)
6. **[≥4] Per-iteration manifest + dashboard + action-coverage / IG-usage instrumentation** (resolved-config-hash, net-hash, seeds, IG fire/skip rate, root entropy, game-length, loss-by-source). (R1-#3/#10, R2-dashboard/manifest, R3-4.5/6.3, R6)
7. **[2/6 + code] Label-scale notation `+1/−1/0.5` is inconsistent** — pick one scale + add label-inversion/scale tests. (R2-#2, R3-7.1) — **and the codebase confirms the fix, see A.4.**
8. **[≥3] Promote the forced-set curriculum into the spec body**; force IG into every self-play + eval game to make the per-unit signal measurable. (R1-C6/#9, R2-§6, R3)
9. **[≥3] Gate handling** — add an "inconclusive" outcome + sequential testing; primary comparison = candidate vs current promoted net; don't require beating *every* anchor; add a rollback rule; resolve the "accept-all at AWS" tension. (R1-C2/C10, R2-#7, R4-Removal, R5, R6)
10. **[2–3] Dynamic sims budget** — scale `N` with branching factor as the action space widens (constant search depth). (R4-Sev2/Add, R5, R6)
11. **[2] Export-parity test** (PyTorch ↔ C++ `.bin`) per iteration. (R2-§10, R3)
12. **[2] STEAMAI eval path differs from the C++ tournament** — report separately + cross-path sanity check. (R1-C8, R2-nit)

## A.3 — Outlier points worth keeping

- **High-sim data / "deep-label reference batch" (R3-5.1, 4.2).** Generate a few deep-search games; train on shallow labels but measure loss on deep labels → directly tells you if shallow search is the bottleneck. **High merit** — the cleanest false-negative guard. → Consider.
- **Offline/batch-RL iteration-0 (R3-5.4).** Train on a fixed self-play dataset with *no loop* first; if the net improves, that's a positive signal with zero poisoning risk before building loop infra. **High merit, cheap.** → Consider.
- **Distillation bootstrap (R1-A5, R3-5.3).** Train value on high-sim visit-count soft targets — a no-policy-head way to distil deep search into the value function. **High merit, more work.** → Consider.
- **Candidate-level policy head (R2-B).** If value-only flatlines, a policy *over the ≤25 portfolio candidates* (not the full action space) enables PUCT cheaply. **The right documented fallback.** → Consider (document, don't build).
- **Tactical/blunder regression suite (R2, R3-4.3).** Fixed hand-labelled known-weakness positions as a fast leading indicator. → Consider.

## A.4 — Category breakdown (with codebase reality-checks)

🏗️ **Architecture & Design**
- *Root exploration injection (consensus #1).* **Feasible & correct.** Code-check: the portfolio yields ≤25 candidates and `MaxChildren=40`, so *all* root candidates are generated; UCB1 with `cValue=0.3` still under-visits low-value children, so the reviewers' concern is real. ε-uniform / forced ≥1-visit / root value-perturbation are all implementable in `UCTSearch.cpp`. **Agree — Must-do.**
- *Make IG-optional the first campaign (consensus #5).* **Agree.** The spec already names IG-optional as widening axis-1 (§6.1, config-only, verified feasible — `ActivateUtility` takes a `CardFilter`; adding `Hotel` to a filter copy suppresses it). The change is to fold it into iteration 0/1 rather than running bare 5-variant first. **Must-do.**
- *Candidate-level policy head fallback (R2-B).* Sound; the model has no policy head today and PUCT is off. A *candidate-level* head is far cheaper than full action encoding. **Consider (document as fallback).**

⚠️ **Risks & Concerns**
- *Label-scale `+1/−1/0.5` (consensus #7).* **Confirmed a real error.** Code-check: the supervised pipeline uses **probability scale [0,1]** — `outcome_p0 = 1.0 − result`, draws → 0.5, **BCE loss requires labels in [0,1]** (per CLAUDE.md), and the net maps value→`(v+1)/2`∈[0,1] for UCT. The spec's mixed `+1/−1/0.5` is wrong. **Fix to win=1.0/draw=0.5/loss=0.0 + add inversion/scale tests. Must-do.**
- *Shallow-search label quality / false-negative (consensus #1,#2).* **Agree it's the central risk.** Mitigated by root exploration (M1), N-calibration (M5), high-sim/deep-label diagnostics (Consider), and — critically — by R1's framing: a flat *local* result is uninformative, not a true negative. **Must-do (decision-rule §12) + Should-do (triage checklist).**
- *Pipeline built for playout self-play (R1-nit, R3-assumption).* **Confirmed.** `fleet_v3/v4` and `SelfPlayDataExport` were exercised with `HardestAI`/playout self-play, **not** DSNN(UCT+NN) self-play. Promote from prereq to a **§9 risk. Should-do.**
- *Self-play stalls / turn cap (R5).* Code-check: the C++ engine has a **flat 200-turn limit but no stagnation detection** (CLAUDE.md) — infinite games are bounded, but long degenerate games are possible. **Add position-sampling caps + note the limit. Should-do.**

🗑️ **Removals / Simplifications**
- *Remove MB-fleet from training value targets (consensus #3).* **Agree** — keep human-only rehearsal anchor; MB → val/coverage-diagnostic or ≤5% low-weight. **Must-do.**
- *Remove the hybrid label notation (R2,R3).* **Agree — Must-do** (see above).
- *"Graduate to accept-all at AWS if gating stalls" is contested* (R1, R4 want it gone; R2, R5 want a *relaxed* gate). **Resolve (A.5).**

➕ **Additions / Features**
- Manifest + dashboard + action-coverage metrics (consensus #6) — **Must-do.**
- Export-parity test (consensus #11) — code-check: the parity harness already exists from the DSNN-port audit (verified |Δ|≤1.3e-6); cheap to run per-iteration. **Should-do.**
- Forced-set in the spec body + force IG into eval (consensus #8) — **Should-do.**
- Kill criteria / no-improvement termination (R1,R3) — **Should-do.**
- Tactical regression suite, high-sim/deep-label diagnostics, offline-RL-iter-0 — **Consider.**

🔄 **Alternative Approaches**
- ε-uniform vs Dirichlet vs Q-perturbation root noise — all variants of consensus #1; recommend starting with **ε-uniform over root candidates** (simplest, seedable, no policy prior needed). R4's `cpp` snippet adds Gaussian/Dirichlet to root Q — viable but more invasive; ε-uniform first.
- Two-stage training (R4-Alt2) vs mixed-batch rehearsal — **prefer mixed-batch** (literature norm; two-stage risks oscillation). Lean no.
- Continuous async loop (R5) / opponent pool (R2-D) — **AWS-scale**, not proof-of-life.

✅ **Confirmed good** — see A.7.

🔧 **Implementation Details & Nits**
- τ schedule numeric (step, K≈6–8) + float math for `visits^(1/τ)` (R1,R2,R5) — **Should-do.**
- SWA params (start epoch, window, LR-schedule interaction) (R1,R3,R6) — **Should-do.** Note: SWA's benefit needs a non-flat (cyclic/decay) collection LR; the spec's "flat LR" undercuts it.
- Resolved-config-hash (post-parser), not source-JSON hash (R1) — **fold into the manifest. Should-do.**
- Build via solution target (`/t:Prismata_Standalone:Rebuild;Prismata_Testing:Rebuild`, skip GUI) — **code-check: this is what's used and is correct;** R4's raw-`.vcxproj` build is the anti-pattern CLAUDE.md warns against (incremental relink). **Reject R4's snippet (nit).**

📦 **Dependencies & Integration**
- Throughput measurement before AWS (R2-#10) — games/hour, NN-evals/sec, shard write rate. Self-play is CPU-bound (confirmed). **Should-do (cheap, gates the £400).**
- Multithread RNG / search tie-break determinism (R6-3.8) — code-check: `Random::Seed` mixes `thread::id`; MCTS tie-breaking also uses RNG. Full determinism needs single-thread + the thread-hash removed. **Already a prereq (§10.1); strengthen wording. Should-do.**

🔮 **Future Considerations**
- Candidate-level policy head (R2-B); sim-budget curriculum (R3-6.4); intrinsic-motivation exploration (R3-6.1); asymmetric/phase temperature (R1-A4, R3-6.5). All **post-proof-of-life.**

## A.5 — Conflicts & contradictions

1. **Relax the gate (R2, R5) vs keep gating strict / never accept-all (R1, R4).** *Resolution:* all four actually agree gating *stays* for the proof-of-life; the disagreement is the threshold and the AWS fallback. **Recommendation:** keep gating; primary comparison = candidate vs current promoted net (don't require beating *every* anchor every iter); add an **"inconclusive"** outcome + **sequential testing**; define "stall" = inconclusive after the max eval N; add a **rollback** rule. Replace "graduate to accept-all if gating stalls" with *"if gating stalls, first increase eval N / diagnose power; accept-all is an AWS option only after the loop is validated and eval is the bottleneck, with automated rollback."* This satisfies R1/R4 (gate stays, stall ≠ drop-the-gate) and R2/R5 (gate isn't rigidly "beat-by-margin-or-die").
2. **Rehearsal in training (spec) vs rehearsal val-only / 100%-on-policy (R5-Alt).** *Resolution:* at small local self-play volume, 100%-on-policy risks catastrophic forgetting; **keep human rehearsal in training** (the forgetting guard) *and* keep human full-coverage in val. Reject val-only as primary.
3. **N magnitude: ~800 AlphaZero-style (R1, R3) vs "7s-traversals ÷ 3–4" ≈ tens of thousands (R5).** *Resolution:* this disagreement *is* the argument for **calibration (M5)** — don't guess; pick the smallest N that passes the non-degeneracy check empirically. (Code-check: deployed budget is `MaxTraversals=100k` OR 7s; the A/B averaged ~5.7s, so 7s ≈ up to 100k traversals — R5's ÷3–4 gives ~25–33k, which is high for volume self-play; calibration resolves it.)

## A.6 — Recommended plan changes

### Must-do
- **M1. Root exploration injection for self-play** (ε-uniform over root candidates during the τ=1 phase, and/or force ≥1 visit per root candidate). Temperature alone is insufficient without a policy prior. [all] — §3.
- **M2. Make IG-optional widening the first RL campaign** (fold into iter-0/1; don't run bare 5-variant first). [R2,R3,R5,R6] — §2/§6/§8.
- **M3. Fix label scale → probability [0,1] (win 1.0 / draw 0.5 / loss 0.0, BCE), per the actual pipeline; add label-inversion + scale unit tests.** [R2,R3 + code] — §4.
- **M4. Quantitative eval / go-no-go rule:** target effect size, N-per-anchor, Wilson/Clopper-Pearson CIs, paired card sets + colour balancing, draw=0.5 in win-rate math, sequential testing + "inconclusive", new **§12 decision-rule pseudocode**. [R1,R2,R4] — §5/§8/§12.
- **M5. N-calibration + concrete non-degeneracy check before iter-0** (game-length vs human baseline; P0/P1 ∈ [0.35,0.65]; root entropy; win-rate vs deep search; smallest non-degenerate N). [all] — §3/§9.
- **M6. Rehearsal: human-only value anchor at a named fraction (~30% iter-1 → decay to ~10–15%); drop MB-fleet from training value targets** (val/coverage or ≤5% low-weight); name the forgetting monitor. [all] — §4.
- **M7. Per-iteration manifest + dashboard + action-coverage/IG-usage instrumentation** (resolved-config-hash + net-hash + seeds + games/positions + eval CIs + IG fire/skip + root entropy + game-length + loss-by-source). [R1,R2,R3,R6] — §5/§7/§11.

### Should-do
- **S1.** Promote forced-set curriculum into the spec body; force IG into every self-play + eval game for axis-1. [R1,R2,R3] — §6.
- **S2.** Per-iteration export-parity test (PyTorch ↔ C++ `.bin`; harness exists). [R2,R3] — §10/§5.
- **S3.** Resolve the gate per A.5 (inconclusive outcome, sequential testing, primary=vs-current, rollback, reword AWS-accept-all). [R1,R2,R4,R5,R6] — §5.
- **S4.** Numeric τ schedule (step, K≈6–8; float math). [R1,R2,R5,R6] — §3.
- **S5.** SWA params (start epoch, window, non-flat collection LR). [R1,R3,R6] — §4.
- **S6.** Promote "pipeline built for playout self-play" to a §9 risk + add a false-negative triage checklist. [R1,R2,R3] — §9.
- **S7.** Single eval path per anchor + cross-path sanity check (STEAMAI/JS vs C++). [R1,R2] — §5.
- **S8.** Position-sampling controls (cap/stratify) + note the 200-turn limit / no stagnation detection. [R2,R5 + code] — §4.
- **S9.** Freeze the HP tuple before iter-1 (N, τ, K, W, rehearsal fraction, gate/rollback margins); changes = new campaign. [R1] — §10/§11.
- **S10.** Kill criteria for the local phase (≥3 flat iters + flat deep-label/dashboard → terminate/diagnose). [R1,R3] — §8.
- **S11.** Throughput measurement before AWS (games/hr, NN-evals/s, shard write). [R2] — §8.

### Consider (pick-list — see plan §13)
C1 high-sim data for early iterations · C2 deep-label reference batch · C3 distillation bootstrap · C4 offline-RL iteration-0 · C5 dynamic sims budget (scale N with branching) · C6 candidate-level policy-head fallback (document) · C7 tactical/blunder regression suite · C8 opponent pool (AWS) · C9 forced-diversity schedule · C10 two-stage training · C11 intrinsic-motivation bonus · C12 asymmetric/phase temperature.

### Reject (with reason)
- **R-rej1. P2 residual-margin labels (subtract 0.43/0.57) [R4-Change3].** Incompatible with the pipeline: BCE on [0,1] win-prob + the `(v+1)/2` UCT mapping; the net *should* learn the P1/P2 asymmetry from balanced data, not have a base-rate subtracted (double-counts + breaks the target range). The valid kernel — **colour-balance training batches** — is folded into M4.
- **R-rej2. Rehearsal val-only / 100% on-policy [R5-Alt].** Catastrophic-forgetting risk at small local volume; human rehearsal in training is the guard (M6). (Human coverage also in val — both.)
- **R-rej3. Build raw `Prismata_Testing.vcxproj` directly [R4-nit].** Anti-pattern (CLAUDE.md: individual `.vcxproj` may not relink); the solution-target build (skip GUI) is correct and used.
- **R-rej4. Symmetrization / data augmentation [R6-3.7].** Inapplicable: Prismata has no board symmetry, and the DeepSets net is already unit-permutation-invariant — no free augmentation.
- **R-rej5. R4's specific `MaxTraversals = old×(1+γ·log M)` formula.** The *principle* (scale sims with branching) is C5; the specific log formula is arbitrary — adopt the principle, not the formula.

## A.7 — What stays (reviewer-confirmed strengths — do not modify)

- **Gated single-iteration loop** (all) — the right proof-of-life shape.
- **Three-anchor eval, esp. the wide-untrained iter-0 control** (all) — universally cited as the sharpest element; preserve exactly.
- **Action-space-widening curriculum + "RL only learns what the iterator emits"** (all) — load-bearing, correct.
- **IG as the first widening axis** (all) — clean discrete signal (now folded into iter-0/1 per M2).
- **KEEP/OPEN heuristic-change discipline + one-change-per-measured-point** (all) — keep verbatim.
- **Fixed-sims self-play budget** (all) — reproducibility; non-negotiable.
- **RNG fix as a hard prerequisite** (R1,R2) — keep first.
- **Argmax preserved for eval/deploy; temperature self-play-only** (R1) — correct scoping.
- **Exact-match-clean human anchor + provenance hygiene + FORCE_DSNN isolation** (R1,R3,R4) — the detail-work that makes results real.
- **Native-Windows / no-WSL pragmatism + spend-free-local-first cost philosophy** (R1,R4,R6).
