# RL Self-Play Loop — Proof-of-Life Reframe (Design Spec)

> Date: 2026-06-14. Status: DESIGN (approved in brainstorm; implementation plan to follow).
> Supersedes the IG-axis framing of `eval/rl_campaign.md` (regime v3) for the *next* run.
> Source audit: `docs/superpowers/plans/2026-06-13-rl-loop-deep-audit-FINDINGS.md`.
> Living contract after implementation: `eval/rl_campaign.md` + `eval/campaign_frozen.json` (v4).

## 1. Goal & framing

Reframe the loop from a **scientific** campaign ("does RL learn the IG decision?") to a **systems
milestone**: *the data → train → export → eval loop runs end-to-end, unattended, and produces a
non-degenerate net.* The deliverable is a working, trustworthy machine plus measured throughput —
**not** a win-rate claim on any axis.

This is defensible because the audit (finding C1) showed the IG over-click was **already fixed by the
action-space widening** (the IG-subset root iterator makes even the untrained v221 pick the correct
count), not by RL. So we **log the IG over-click as a completed action-space fix**, keep the IG-subset
in the candidate, and remove all IG-*measurement* machinery. There is no axis under test.

**Discipline that keeps it honest:** report results as "the loop works / the net is non-degenerate,"
never as "RL improved the net." The moment the latter is claimed, the dropped measurement findings
(H1/H5/M7/M8…) come back.

## 2. Scope

**In scope.** Strip IG-measurement machinery; fix the interior IG policy (NoIG interior); add a
same-path absolute strength anchor (SWF-faithful AB MasterBot); relax gating to proof-of-life level;
the cheap pre-launch safety fixes; a two-phase run (fixed-generator smoke → promoting loop); new frozen
tuple + doc updates.

**Out of scope (deferred).** Policy head + PUCT (the durable fix for value-only MCTS and for richer
action spaces — §10); off-policy buffer correction beyond shrinking W; varying card-set size; the
MasterBot-mistakes axis curriculum; any "RL improved the net" measurement. The eval/deploy tie-break
asymmetry fix is deferred (cheap, do it when consolidating IG for deployment).

## 3. Two-phase run

**Phase 0 — fixed-generator pipeline smoke.** Run 1–2 iterations with **v221 frozen as the generator
(no promotion)**. Validates the entire pipeline (self-play → vectorize → train → export → parity →
eval) and measures throughput. Because the generator never moves, the drift (H2) and off-policy (H4)
hazards are nullified for the smoke. Success = it completes, the candidate is non-degenerate, and we
have throughput numbers. (One iteration validates the pipeline; a second confirms the replay-window /
multi-iteration mechanics.)

**Phase 1 — promoting loop.** Separate session, **promotion on (promote-unless-collapse)**, run N
iterations unattended, bounded by the strength tripwire (abort-on-collapse). This is the actual
self-improvement loop; the goal remains "it runs and doesn't degenerate," now with a moving generator.

## 4. The new regime — `campaign_frozen.json` v4

Bump `tuple_version` to **4** (also closes the audit's tuple_version-vs-regime mismatch). Changes vs
regime v3:

| Knob | v3 (IG axis) | v4 (proof-of-life) | Why |
|---|---|---|---|
| Self-play mix | ⅔ general (344) + ⅓ forced-Hotel (172) | **general only, rounds 516** (drop the forced block; general 344→516) | not measuring IG; 516 rounds = 1032 games/iter, preserving the J1 training dose |
| `EpsilonIG` | 0.25 | **0** | IG-specific exploration removed |
| `EpsilonLate` | 0 (retired) | **0.05** | general, controllable late exploration (small, bounded label cost) |
| `TemperatureTau`/`K` | 0.7 / 12 | **0.7 / 12** (unchanged) | opening diversity |
| `EpsilonUniform` | 0 | 0 | τ carries opening exploration |
| `N` (MaxTraversals) | 1000 | 1000 | unchanged |
| `UCTConstant` | 0.3 | 0.3 | unchanged |
| Replay window `W` | 5 | **2** | with a moving generator, track the current net (H4); was 5 |
| Rehearsal | 0.10 elite | **0.10 elite** (unchanged) | working knob, harmless tax (audit) |
| Threads | 8 | 8 | unchanged |
| Card sets | Base+8 | Base+8 | unchanged (vary later) |
| Train schedule | 6 ep / 1e-5 / no-SWA | same | unchanged |

The v3 tuple is preserved in git; optionally snapshot it as `campaign_frozen_ig_v3.json` for one-click
reference.

## 5. Candidate config (dave-master `config.txt`)

The candidate players (`RL_SelfPlay` generator, `RL_Eval` candidate-at-eval, `RL_Eval_origin` = v221
reference) all share one iterator shape:

- **Root iterator:** `HardIterator_5var_IGsubset_Root` — **KEEP** (the action-space fix; net chooses the
  IG count per turn).
- **Interior `MoveIterator`:** **CHANGE** `HardIterator_5var` (auto-fires IG) → a **NoIG interior
  variant** (never auto-fires IG in lookahead). Rationale (per the brainstorm): "always-fire" collapses
  the hold-vs-fire distinction; "never-fire interior + per-turn root re-decision" gives a sensible
  reactive IG policy (hold until the root sees a reason to fire) at **zero combinatorial cost** (same
  branching, no interior enumeration). This is the **correct general default for every optional ability**
  we open up: *root chooses it; interior never force-fires it.* Upgrades audit finding M1 from "accepted"
  to "fixed (cheap way)."
- `c=0.3`; `SelfPlaySampling:true` (generator only); eval players at the deployment budget
  (`TimeLimit:7000`, `MaxTraversals:100000`). Candidate KEEPS its waste-avoid partials (measured
  beneficial/neutral; owner decision).

**Self-play blocks:** collapse the two-block (general + forced) structure to **one** general block
(Threads:8, no `ForcedCards`, rounds 516, Seed `base+K`). This touches the driver (stage 1 runs one
block), preflight (frozen_tuple checks one block), and the concat step (one export dir) — see §9.

## 6. Baseline & anchors (closes audit M9)

The loop currently has **no trustworthy external absolute-strength anchor** (steam is cross-path and
uses a different draw convention). Fix: run **the live MasterBot config through the same C++ tournament
runner** as the candidate.

**New player: `MasterBot_SWF` (the faithful 2016-MasterBot reconstruction in the strong engine).**
- **SWF-faithful, AB search:** narrow auto-fire iterator (NO IG-subset — the real bot auto-fires), the
  SWF ability variants **including Odin** in `Ability_Filter`, the SWF opening books
  (`LiveOpeningBook2`=50, `DefaultOpeningBook`=4), the SWF buy tree (already ported, `dave@09c5436`),
  **playout eval**. **Strip** the local waste-avoid partials and IG-subset.
- ⚠️ **VERIFY before building:** that the live MasterBot uses **AB** (Stack Alpha-Beta / HPS), not UCT —
  confirm from the decompiled client (`AIThreadHandler`/`NewIterator_Root` routing). The whole point is
  faithfulness; do not guess. If the SWF actually routes to UCT, use that instead.

**Anchor set (per iteration; non-gating, small-N):**
| Anchor | Opponent | Role | N |
|---|---|---|---|
| `origin` | `RL_Eval_origin` = v221, **same iterator as the candidate** (NoIG interior + IG-subset root) | relative — "did the lineage move from its start"; the **collapse/abort signal** | 96 |
| `masterbot` | `MasterBot_SWF` (faithful AB), same C++ path & draw convention | absolute external strength trend | 96 |

**Dropped anchors:** `iter0` (candidate-vs-parent verdict — no verdict under proof-of-life),
`narrow` (IG iterator-gap isolation — not measuring IG), `steam` (cross-path 2016 binary — replaced by
the same-path `MasterBot_SWF`; keep the 2016 binary only as an occasional cross-path sanity check, not a
primary anchor). The clean-attribution control `HardestAIUCT` is parked for the future "did the *net*
help" measurement.

## 7. Gate changes (`eval/run_iteration.ps1`)

| Stage | Now (v3) | v4 (proof-of-life) |
|---|---|---|
| 0 preflight | asserts config == frozen | **Keep**; update to the v4 tuple + one-block self-play; **add the M2 "self-play block uses RL_SelfPlay" check**; **add a6 + three-way + engine-exe-sha sub-checks** (M4/M5) |
| 1 self-play | two blocks | **one** general block |
| 4.5 val-acc tripwire | abort if >3pp below parent | **Keep** as a cheap "training broke" canary |
| 4.6 prediction-movement | informational | **Promote to the first-class success readout** (near-null fixed-probe \|dP\| = the loop learned nothing = the night's failure signal) |
| 5 export-parity | parity only | **Keep**; a6 + three-way are now preflight gates (M5) |
| 6 tactical | telemetry | **Drop** (IG-specific) |
| 7 eval | 4 anchors + REJECT/REVIEW verdict | **Replace:** run `origin` + `masterbot` (192 games), **non-gating**, **abort only on collapse** (win-rate vs origin < **0.35**) |
| promotion | promote-unless-harm | **Phase 0: none.** **Phase 1: promote-unless-collapse** (promote unless the abort fired, val-acc collapsed, or self-play degenerate) |

## 8. Pre-launch must-dos (so an unattended night can't be silently wasted)

1. **Automate the catastrophic-silent-failure gates** (audit M4/M5): a6 orientation check + three-way
   feature parity run automatically at preflight, and **sha-pin the engine exe** in `campaign_frozen.json`
   so a stale/rebuilt binary is caught (a silent sign-flip or feature skew would poison the whole night).
2. **M2 preflight check:** assert the self-play block's `players[]` actually reference `RL_SelfPlay`
   (+ `SelfPlaySampling:true` + the IG-subset root iterator).
3. **Unattended-robustness fixes:** host-kill leaving `run:true`/drifted seed (config-recovery on next
   launch or a recovery note), lockfile PID-liveness, and the narrow-anchor-overwrites-manifest bug is
   moot (narrow dropped).

## 9. Success / abort criteria (pre-registered)

**Success of a run =** loop completes its iterations unattended **AND** prediction-movement is non-null
(fixed-probe mean \|dP\| above a small floor) **AND** self-play is non-degenerate (game length within
band of the human baseline; per-seat win-rate ∈ [0.35, 0.65]; not all draws) **AND** strength stays
within band of origin (no sustained drop below the abort threshold).

The numeric thresholds left soft here — the prediction-movement floor and the game-length band — are
**calibrated from the Phase 0 smoke** (the first real values these quantities take), then frozen into
the v4 contract before Phase 1. This is deliberate (we have no clean self-play H5 to set them from yet),
not an open TODO.

**Abort a run if:** any stage crashes; val-acc collapses (>3pp below parent at stage 4.5); win-rate vs
origin < 0.35 at stage 7; or self-play is degenerate.

## 10. The forward-looking note (why this is just step one)

The general mechanism for "the search genuinely reasons about optional abilities at *every* node"
(needed when "never-force interior" stops being good enough, and for richer action spaces where
per-ability heuristics don't scale) is a **candidate policy head + PUCT** (audit H5 / §14 O6). It is the
durable fix for both value-only-MCTS under-exploration and the interior-optionality problem, tractable
because the portfolio iterator already supplies a small candidate set. **Deferred** until proof-of-life
is done; named here so the proof-of-life choices (NoIG interior, no policy) are understood as the cheap
interim, not the destination.

## 11. Documentation plan

One unambiguous current contract; the IG work preserved as reference without competing with it:
- **`campaign_frozen.json`** → v4 tuple (old archived in git / optional `_ig_v3.json` snapshot).
- **`eval/rl_campaign.md` / `eval/rl_runbook.md` / `eval/README.md`** → rewrite to the v4 regime + the
  new gate/anchor set; add an **"IG axis — worked example (regime v3)"** appendix as the next-axis
  template (the reusable thing is the axis-measurement *framework*, not the IG specifics).
- **`eval/campaign_log.md`** → append a v4 reframe decision entry (append-only ledger already preserves
  the J1–J7 IG decisions).
- The audit FINDINGS doc is already updated (C1 reframed, F-SKEW-1 retracted).

## 12. Open verification items (resolve during planning)

1. **AB vs UCT** for the live MasterBot — confirm from the decompiled client before building `MasterBot_SWF`.
2. Whether dave-master already has an AB SWF-faithful player block or one must be assembled (and whether
   AB is wired to drive the SWF iterator chain).
3. **Interior NoIG iterator** — confirm it assembles cleanly from the existing `_NoIG` partials
   (`V5_CS_NoIG` etc.) as a non-root `MoveIterator`, and update the preflight `iterator_shape` check.
4. **Throughput** — measured in Phase 0 (games/hour at N=1000, train min/epoch, eval games/hour) to size
   the Phase 1 overnight N.

## 13. Audit-finding disposition under this reframe

- **Dropped (IG-measurement-specific):** C1 (accepted/completed), H1, H5, M6, M7, M8, ig_contrast_pairs,
  verdict-excludes-forced-pool, tau-probe-unrepresentative. M1 **fixed** (NoIG interior).
- **Nullified for Phase 0 (revisit for Phase 1):** H2 (promote drift), H4 (off-policy buffer; mitigated
  by W=2). H3 (val-acc blind to strength) → addressed by the per-iteration game anchors.
- **Addressed now:** M9 (no external strength signal → `MasterBot_SWF` same-path anchor); M2/M4/M5
  (preflight checks + automation + exe sha-pin); unattended-robustness ops findings; prediction-movement
  promoted to the success metric.
- **Deferred (named):** policy head + PUCT (§10); tie-break eval/deploy asymmetry; varying card-set size.

## 14. Risks

- **AB-vs-UCT wrong** → an unfaithful absolute anchor. Mitigation: verify from the SWF first (§12.1).
- **NoIG interior under-values future IG fires** → mildly suboptimal lookahead. Bounded: the root
  re-decides each turn; strictly better than always-fire; the policy head is the real fix later.
- **Promote-unless-collapse still drifts in Phase 1** → bounded by the per-iteration origin abort
  (< 0.35) — coarser than a powered gate, but it catches collapse within one iteration, which is all
  proof-of-life needs.
- **One-block self-play refactor** touches driver/preflight/concat → contained but real; validate in the
  Phase 0 smoke before the overnight run.
