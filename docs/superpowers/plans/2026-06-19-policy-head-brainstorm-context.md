# Policy-head brainstorm context — synthesis from the MA-axis run + Dave/Campbell publications

> **Purpose.** Feed a policy-head brainstorm (a separate session has already done policy-head research —
> merge this with that). This doc synthesizes (a) *why* a policy head is on the table now (the value-only
> ceiling, empirically), (b) the directly-relevant findings from Dave Churchill / Rory Campbell's Prismata
> publications, and (c) the design space + the **engine plumbing that already exists** + the open questions.
> Written 2026-06-19 after running the Mobile-Animus (MA) action-space axis end-to-end.
>
> **Run details are NOT duplicated here** — every per-iteration number, gate, and commit is in
> `eval/campaign_log.md` (K=1–8 entries + the K=4 and K=8 checkpoint entries + the decisions table). The
> campaign contract + the parked O6/O3 escalation framing is `eval/rl_campaign.md` (§6, §1a). The papers are
> cached at `.parity_tmp/papers/*.txt` (originals: davechurchill.ca/publications).
>
> **Engine = `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`).** This repo's `source/`
> is the indicted engine_v2 — ignore it. File:line refs below are dave-master, verified this session.

---

## 1. Why a policy head is on the table — the value-only ceiling (empirical)

The campaign is a **value-only** RL self-play loop: a DeepSets value net evaluates leaf states; high-level
search is **UCB1 MCTS** (no policy prior). We opened two action-space axes as value-only-RL targets — Infusion
Grid (IG) click-count, then Mobile Animus (MA) fire-count — by widening the root iterator so the net *chooses*
the count via search.

**Both axes converged to ~parity over the v221 baseline.** Powered checkpoints (the answer-producing
measurement, 384 games/anchor):

| checkpoint | origin vs v221 | masterbot (abs) | B8 forgetting |
|---|---|---|---|
| K=4 (pre-MA, 3 promotions) | 52.3% [0.47,0.57] | 67.3% | none |
| K=8 (post-MA, 7 promotions, 4 MA-open) | 53.6% (paired [0.502,0.571]) | 63.8% | none |

Statistically indistinguishable. Per-iter origin oscillates around parity (IG era 54.7/52.1/50.0; MA era
51.0/47.9/45.8/52.1). MA integrated cleanly (no collapse, no forgetting) but bought **no powered ≥5pp gain**
(the pre-declared MIE was *indeterminate* at 384 games — can neither prove nor reject +5pp; proving it needs
~780 origin games).

**Honest caveat (do not over-read):** IG and MA are the **same class of axis** — a low-base-rate self-sac fire
COUNT, ~7.5% self-play coverage, tiny LR updates (prediction-movement ~0.008). Two flat/indeterminate nulls
from a *shared mechanism* are closer to **one data point than two**. So the value-only-per-axis line is **not
yet proven exhausted**, and this checkpoint cannot distinguish "MA is genuinely neutral" from "MA was
under-covered / under-trained." The recommended **disambiguator before committing to a policy head** is one
coverage-controlled crux iteration (a forced-MA curriculum block + lr 1e-5→3e-5, powered ≥780/anchor). If
*that* is still flat → defensible STOP for value-only-per-axis → **the policy head becomes the well-motivated
pivot.** Treat the policy head as the **hypothesized next platform**, strongly motivated, pending the crux.

---

## 2. What the publications say that bears on a policy head

Four papers (all Prismata, all Churchill-lineage). The value net we run (`v221` → `rl_iter8`) is the **direct
descendant** of #2/#3.

1. **HPS (AIIDE 2015)** + **GAIP (Game AI Pro 3)** — Hierarchical Portfolio Search = *the action space a policy
   would prior over.* A turn = a "Move" (ordered action sequence). HPS reduces the exponential action space to
   a **portfolio cross-product**: per phase (Defense / Ability / Buy / Breach), several "partial players"
   each propose a sub-move; candidate whole-turn moves = the cross-product (their example: 2×3×3×2 = 36). A
   high-level search (Alpha-Beta or UCT) runs over those ≤~36 candidates. **Our deployed candidate set** =
   the `HardIterator_5var` portfolio (1 defense × 5 ability × 5 buy × 1 breach = 25 variant-sequences, ×
   IG-count × MA-count, deduped, capped at `MaxChildren`). **This portfolio output — not the raw click
   sequence — is the natural policy action space.**

2. **Campbell & Churchill, "ML State Evaluation in Prismata" (AIIDE 2019 ws)** + **3. R. Campbell MSc thesis** —
   the value net. Learns P(win) ∈ [-1,1] (sigmoid) from a turn-start state; **label = eventual game outcome,
   stamped on every state, no discount** (== our `label_A`). State rep: unit-type counts + resources +
   player-to-move (ours is richer: per-instance DeepSets tokens + 15 globals). Trained on 500k MasterBot
   self-play games (15M samples); replaced the playout eval; won ~66% vs the resource heuristic, ~59% vs
   playout. **Three findings that drive the policy decision:**
   - **(2a) Diminishing returns + a generator-insensitive fixed point.** They *explicitly proposed* iterating
     self-play on a stronger-each-time generator (our loop) and predicted diminishing returns (thesis §7.1).
     Exp 3 *measured* that value models trained on different-strength generators are "quite similar"
     (Medium→Master 82%, Master→Master 89%). **→ our origin ≈ parity across both IG and MA is that fixed
     point. The value-only loop has a ceiling — exactly as predicted.**
   - **(2b) THE KEY CAUTIONARY TALE — a direct-prediction policy FAILED (thesis §7.2 "Card Buy Learning").**
     They tried to learn MasterBot's *buy decisions* directly (predict a one-hot array of units to buy). It
     failed: *"a single incorrectly predicted one-hot value could lead to a vastly different choice of which
     unit to purchase, and advantage in Prismata is highly sensitive to mistakes."* **→ a policy must be a
     PRIOR that guides search (search corrects a wrong prior), NOT a hard action selector.** This is the single
     most important design constraint for the brainstorm.
   - **(2c) The named successor (thesis §7.3).** A policy network "like AlphaGo / AlphaStar" to "learn to
     actually play," not just evaluate — they were "confident it would yield a strong AI agent."

---

## 3. The engine plumbing that ALREADY EXISTS (verified this session) — this changes the effort estimate

The PUCT *consumer* is **already built** in dave-master. The policy-head project is therefore much more
"train + export + stamp the target + tune" than "build the search from scratch."

**Built (the search side):**
- `UCTSearch.cpp:79` — `if (_params.usePUCT())` branch: generates *all* root children up front and computes
  policy priors (vs the lazy UCB1 expansion).
- `UCTSearch.cpp:294–315` — the **PUCT selection formula** is implemented: `Q(s,a) + c · P(s,a) · √N_parent /
  (1 + N_child)`; unvisited children use Q = 0.5 (neutral). `c` reuses `cValue()`.
- `UCTNode::getPolicyPrior()` — per-node prior storage, consumed by the formula above.
- `UCTSearch.cpp:379–405` — the net is queried for **policy + value** at the root (`NeuralNet::NeuralOutput`
  has a `.policy` field); the per-child prior is derived and softmaxed across children (see the representation
  below).
- **Uniform-prior fallback** (`UCTSearch.cpp:14`, :375): with no policy (or no net), priors are uniform → PUCT
  degrades gracefully to a UCB-variant. (CLAUDE.md "Known Issues" notes a `UsePUCT` flag + "don't enable until
  policy >30%" — that guidance predates this DSNN; the plumbing is real in dave-master.)

**The policy representation the engine ASSUMES (concrete — `UCTSearch.cpp:383–405`):**
> `output.policy` is a vector of **per-unit-TYPE logits** (indexed by `nn.getUnitIndex(cardType)`). For each
> root child (candidate move), `score = Σ policy[unitIdx]` over the **BUY actions** in that move; then
> **softmax across children** → the priors fed to PUCT.

So the engine's built-in policy = **a buy-affinity prior over unit types**, with a candidate's prior =
softmax(sum of its bought units' logits). This is **BUY-only** — it does *not* prior over ability / defense /
breach / IG-count / MA-count choices. (The papers say buying is "the main strategic decision making in
Prismata," so buy-only is a well-motivated first cut — and being a softmaxed prior corrected by search, it
sidesteps the §7.2 fragility by construction.)

**Missing (the producer + the training target):**
- **The DSNN has no policy head.** The DSN2 `.bin` carries value-head tensors only (`NeuralNet.cpp:305–306`
  `value_head.0/1/2`); `output.policy` is currently empty/uniform. Adding a policy head needs:
  `model_deepsets.py` (a new head emitting per-unit-type logits), `export_weights_v2.py` + the DSN2 header /
  tensor list, and `NeuralNet.cpp` to read the tensors and populate `output.policy`.
- **Self-play does not stamp the visit DISTRIBUTION.** `SelfPlayV2Exporter` stamps `argmax_idx`,
  `sampled_idx`, `root_children`, `root_truncated`, `ig_click_count`, `ig_feasible_max` per move — but **not the
  per-child visit vector** (`SelfPlayV2Exporter.h:38`). An AlphaZero visit-distribution target would need a
  new stamp. (But see §4: a *supervised* buy-policy target is already derivable from `argmax_idx`.)

**Net effort reframing:** rl_campaign §6 rates O6 "large," but with the search consumer already built, the
critical path is: policy head in the model → export/reader → a training target → joint loss → flip `usePUCT`
+ tune `c`. The search math + node plumbing is done. **Verify the above end-to-end first** — it's the highest-
leverage thing the brainstorm can confirm.

---

## 4. Design decisions for the brainstorm

1. **What does the policy prior over?** The engine already commits to **per-unit-type BUY logits → softmax over
   candidates.** Decide whether to (a) keep buy-only (simplest, covers the dominant strategic axis, matches the
   built plumbing), or (b) extend to the ability / fire-count axes (covers MA/IG/Drake — the action-space axes
   this campaign has been opening — but needs a richer policy output + a different candidate-prior derivation).
   Note the tension: the campaign's *recent* work (IG/MA fire counts) is exactly what a buy-only policy does
   **not** cover.
2. **Output shape vs the dynamic candidate set.** AlphaZero priors over a *fixed* action vocabulary; here the
   candidates are a *dynamic, deduped, MaxChildren-capped, longest-first* portfolio cross-product. The engine
   sidesteps this elegantly by priors over a **fixed unit-type vocabulary** and deriving candidate priors by
   summation — a clean trick worth keeping. If extending to ability/fire-count axes, solve the dynamic-set
   mapping (options: fixed grid over portfolio components; per-(state,candidate) scorer; per-phase factored).
3. **Training target.** Two routes:
   - **Supervised (cheap, data already exists):** the self-play `argmax_idx`/`sampled_idx` already identify the
     chosen candidate per turn → its bought unit types give a `(state → bought-types)` target with NO new
     stamp. Train the buy-policy to match the lineage's own choices (a prior, not a selector). This is the
     thesis §7.2 idea **reframed safely as a prior** (search corrects it).
   - **AlphaZero (needs a stamp):** record the **root visit distribution** in self-play and train the policy to
     match it (cross-entropy). Stronger in principle; requires the `SelfPlayV2Exporter` change above.
4. **Architecture & loss.** Shared DeepSets trunk + two heads (value + policy), AlphaZero-style? Joint loss
   (MSE value + CE policy + L2). How does it interact with W=2 replay window, rehearsal 0.10, lr 1e-5?
5. **Search tuning.** PUCT `c` (currently `cValue()`=0.3 is the UCB1 constant — PUCT `c` likely wants
   re-tuning); root-only vs full-tree PUCT; how PUCT changes the `MaxChildren`/breadth story (PUCT generates
   *all* children up front — interacts with the `MaxChildren=80` cap + the longest-first truncation).
6. **Does a policy head fix what value-only couldn't?** Hypothesis: concentrating sims on net-preferred
   candidates = effectively deeper search on the right moves → beats value-only at a fixed budget, and is the
   durable fix for the documented saturated-position discrimination weakness (M10 / mKPSu / the DbS6q
   knife-edge) and for genuinely-wide R-allocation / interior optionality (the things `MaxChildren` and the
   NoIG-interior currently paper over — rl_campaign §1a/§5).
7. **Eval methodology + POWER (the campaign's recurring hard lesson).** Pre-declare an MIE; power the
   checkpoint to it (≥780 games for +5pp; ~2180 for +3pp); read the **paired per-card-set CI** (≈30–40% tighter
   than pooled Wilson) and/or SPRT; pool 384-game reads of a fixed net. Per-iter 96-game cells are ±10pp =
   harm screens only.

---

## 5. Constraints / realities a policy design must respect

- **Action space** = portfolio cross-product (dynamic, deduped, `MaxChildren=80`, longest-first emission;
  PUCT generates all children up front so truncation interacts directly with the prior).
- **Value net** = DeepSets (per-instance tokens + 37 static props + 10 instance props = 79/token; 15 globals;
  value head 303-wide). Efficient native C++ inference (the papers' frugally-deep single-core CPU path is *not*
  ours — we are not speed-bound the way they were, which is why our richer per-instance rep is viable where
  their isomorphism-class rep was abandoned for speed, thesis §5.4.2).
- **`label_A` = raw undiscounted game outcome** per ply (corrected this session; CLAUDE.md:303 + campaign_log
  decisions table). A policy target is separate (visit dist or chosen-candidate buys).
- **Throughput** ~3h/iteration (self-play ~82 min dominates); eval power is the binding measurement constraint.
- **Engine changes need a rebuild + re-pin** (`engine_*_exe_sha256` in `campaign_frozen.json`; a6 + three-way
  gates re-run) — a policy head touches NeuralNet.cpp + the exporter, so plan the re-pin.
- **Any HP change = a NEW campaign** (re-anchor + re-baseline). A policy head + PUCT is unambiguously a new
  campaign / new tuple.

---

## 6. Pointers

| Thing | Where |
|---|---|
| All run numbers / gates / commits (K=1–8 + 2 checkpoints + decisions table) | `eval/campaign_log.md` |
| Campaign contract + O6/O3 escalation framing | `eval/rl_campaign.md` §6, §1a |
| Papers (text + pdf) | `.parity_tmp/papers/{aiide2019ws_prismata, RoryCampbell_Thesis_MSc, aiide15_churchill_prismata, prismata_gaip3}.*` |
| PUCT consumer (search side, BUILT) | `dave: source/ai/UCTSearch.cpp` :79, :294–315, :379–405; `UCTNode` getPolicyPrior |
| Policy representation assumed by the engine (per-unit-type buy logits → softmax) | `dave: source/ai/UCTSearch.cpp:383–405` |
| DSNN reader / DSN2 header (value head only today) | `dave: source/ai/NeuralNet.cpp` :233–306 |
| Self-play move stamps (argmax/chosen/count — NO visit dist) | `dave: source/testing/SelfPlayV2Exporter.{h,cpp}` |
| Model + export (where a policy head is added) | `training/model_deepsets.py`, `training/export_weights_v2.py` |
| The action-space-axis template (how IG/MA were opened) | `docs/superpowers/plans/2026-06-18-MA-abilitysubset-axis-handoff.md` |
| The other session's policy-head research | held by owner — **merge with this doc** |

---

## TL;DR for the brainstorm

1. Value-only RL on action-space axes (IG, MA) has plateaued at ~parity over v221 — the Campbell/Churchill
   "generator-insensitive fixed point," as predicted. (Caveat: 2 axes of the same class ≈ 1 data point; a
   coverage+lr crux iteration should confirm before fully committing.)
2. The literature's named successor is a **policy network**, and it tells us the **failure mode to avoid**: a
   direct buy-predictor is fragile (§7.2) → build a **prior over portfolio candidates that search corrects**,
   not a selector.
3. **The engine already has the PUCT consumer + a concrete assumed policy representation** (per-unit-type buy
   logits, softmaxed across candidates). The missing pieces are the **DSNN policy head (producer)** and the
   **training target** (cheap supervised-on-chosen-buys, or AlphaZero visit-distribution needing an exporter
   stamp). That makes this far less than a from-scratch build.
4. Biggest open design call: **buy-only policy (matches the built plumbing + the papers' "buying is the main
   decision")** vs **extending to the ability/fire-count axes** (covers the MA/IG work but needs a richer
   output). And, as always: **power the eval to a pre-declared MIE.**
