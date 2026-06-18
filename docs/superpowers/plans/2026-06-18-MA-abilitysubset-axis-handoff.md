# Handoff — Add Mobile Animus to the AbilitySubset (the "MA axis") + RL

> **Purpose.** Resume the work of opening **Mobile Animus (MA)** as the next RL action-space axis,
> the same way Infusion Grid (IG) was opened. Written 2026-06-18 for a fresh session (the prior
> session ran low on context). Everything below is **adversarially verified against the live engine
> code this session** (file:line cited) — trust it over older docs/memory where they conflict;
> several long-standing characterizations were found wrong and are corrected in §9.
>
> **Engine repo:** `c:/libraries/PrismataAI-dave-master` (branch `dave-master-jsonclean`) — the LIVE
> engine. **This** repo (`c:/libraries/PrismataAI`, `feature/production-vectors`) = training/eval/docs.
> The indicted `source/` here is engine_v2 — DO NOT use it.

---

## 0. RESUME HERE — the ordered plan

1. **(recommended) Sanity-test the net's MA-count choices on game states FIRST** (§4.1). Cheap,
   config-only, no RL. Goal (owner's words): confirm the iter4 net **does not collapse to "always 0
   clicks" nor stick to "always click all"** when MA is a 0..N root choice. De-risks before spending
   RL compute.
2. **Combinatorics probe** (§4.2): measure the post-dedup ROOT candidate count with `{IG, MA}` to see
   whether `MaxChildren=40` binds. Config-only (no rebuild) via `query_move` diagnostics, or a
   scratch `--test-subset-count` probe.
3. **N-calibration** (§4.3, owner asked): re-tune self-play N (`MaxTraversals`) and/or `MaxChildren`
   for the wider IG×MA root, holding the "root children ≲ N/10" depth rule. Reuses the existing
   `RL_Cal_N*` apparatus.
4. **Open MA for RL** (§4.4): the exact config edits, the campaign-change decision (candidate-only vs
   shared-with-origin action space), then run the promoting loop and **checkpoint** to validate.
   Curriculum = **MA first, alone** (§5).

Do **NOT** add a targeted MA-epsilon (see §3.5 — the IG targeted-ε idea was abandoned because the net
made reasonable subset choices on its own; rely on the frozen general `EpsilonLate=0.05`).

---

## 1. Current campaign state (PAUSED)

- **RL regime v4 "proof-of-life", PAUSED at parent `neural_weights_rl_iter4.bin`** (sha `67dec168…`).
- Promotions so far: K=2/K=3/K=4 all promoted (origin vs v221: 54.7 / 52.1 / 50.0 per-iter; powered
  **checkpoint @ K=4 = origin 52.3% [0.47–0.57], masterbot 67.3%**, B8 no-forgetting). Loop is healthy
  with a **modest (~+2pp powered) v221-relative gain** — proof-of-life as designed. Owner paused to pick
  the next axis (this is it: MA).
- Single source of truth: `eval/campaign_frozen.json` (tuple_version 4). Key pins: `parent_bin`
  rl_iter4, `parent_bin_sha256` 67dec168…, `candidate_root_iterator` `HardIterator_5var_IGsubset_Root`,
  `candidate_interior_iterator` `HardIterator_5var_NoIG`, `engine_testing_exe_sha256` c9fb0a64…,
  `engine_prismataai_exe_sha256` 58478ec6…. Logbook: `eval/campaign_log.md`. Runbook: `eval/rl_runbook.md`.
- Operate the loop via `eval/run_iteration.ps1 -K <K>` → `eval/promote_candidate.ps1 -K <K>`;
  powered read via `eval/run_checkpoint.ps1` (**always `-Iteration 0`** — `-Iteration K` clobbers the
  per-iter manifest).

### This session's commits (baseline the next session inherits)
- **dave** (`c:/libraries/PrismataAI-dave-master`): `ad55d68a` (K=3 repoint), `1e7a2ff8` (K=4 repoint),
  `50977510` (FORCE_DSNN `use_dsnn.txt weights=` key + NoIG-interior fix for Steam bundles),
  `344e716c` (config: drop redundant "Hotel" from IG filters). **HEAD = 344e716c.**
- **main** (`c:/libraries/PrismataAI`): `e571b306` (K=3 promote), `dc96a772` (K=4 promote),
  `5f380b10` (checkpoint record), `d94908b9` (re-pin engine shas), `830fa26e` (steam-bundle builder
  `eval/build_steam_bundle.ps1` + runbook refresh), `6b1825d0` (CLAUDE.md status). **HEAD = 6b1825d0.**
- All commits LOCAL (not pushed; owner pushes to the `PrismatAlpha` fork on request).
- Working trees are clean. The campaign config is at rest (preflight 19/19; `run:false`, anchor rounds 48).

---

## 2. What MA is + why it's the next axis (VERIFIED)

**Mobile Animus** (`cardLibrary.jso:941-952`, internal key literally `"Mobile Animus"`):
- rarity `normal` → **supply 10** (so several can be on board → a COUNT/subset axis is meaningful).
- `buyCost 4`; `beginOwnTurnScript {receive:"C"}` = **passive 1 red/turn** (it's a red generator).
- `abilityCost "2"` (2 GOLD); `abilityScript {create:[["Elephant",own,1,0]], selfsac:true}` =
  **pay 2 gold + SELFSAC (sacrifices ITSELF) → create 1 Rhino** (codename `Elephant`/UIName `Rhino`).

**MA is FORCE-FIRED today** (this is "Mistake 2"; the over-click). It is in **neither**
`Ability_Filter_Live` nor `Ability_Filter_Live_NoIG`, so `ActivateUtility` greedily selfsacs it in
**every** ability variant — there is **no "don't fire MA" candidate at all**. (`isUtilityCard(MA)`=true:
`PartialPlayer_ActionAbility_ActivateUtility.cpp:70-98`; greedy fire loop :32-67; filter-exclusion gate
:40-44.) Opening MA in the AbilitySubset replaces the forced sac with a net-chosen **count 0..N** — the
same shape that fixed IG. **This is a clean force-fired→choice fix** (the strongest category; cf. §6 for
why Drake/GM are a different, deferred case).

---

## 3. How the AbilitySubset works (VERIFIED — so you don't re-derive)

File: `source/ai/MoveIterator_AbilitySubset.cpp` (+ `.h`); parsed in `AIParameters.cpp:1166-1180`.

### 3.1 It is a ROOT-only cross-product, buy re-run FRESH per click-count
`buildAllMoves()` (`:64-193`) iterates the **inner portfolio's per-phase variant odometer** ×
**the subset click-count grid**. For each (variant-sequence) × (fire-count k): run DEFENSE +
ACTION_ABILITY (subset units excluded from auto-fire), enumerate fire-counts 0..N, apply k fires, then
**RE-RUN ACTION_BUY + BREACH FRESH on the post-fire state** (the "consistency point", design comment
`:58-62`, buy re-run `:128-149` esp. `:144`). So a "fire k" candidate's buy correctly sees the spent
resources + changed board. Exact-Move dedup `:169-173`. Emits **longest-move-first** (`:52-53`).

### 3.2 Inner portfolio = 25 variant-sequences
The root's inner portfolio is `HardIterator_5var_NoIG_Root` (`config.txt:210`):
`1 defense (DefenseSolver) × 5 ability (V5_*_NoIG) × 5 buy (BuyEconTech,BuyTechEcon,BCG{Attack,Will,Def}_Root) × 1 breach` = **25**. The net ranks the (ability × buy × click-count) cross-product, deduped.
**Interior** iterator (`HardIterator_5var_NoIG`, `config.txt:213`) = `1×1×5×1 ≤ 5` — iterator-bounded,
so `MaxChildren` only ever binds at the ROOT.

### 3.3 Multiple subset units → automatic per-type count cross-product
`processFilteredIsomorphicCards` (`:217-262`) builds one iso-set per distinct ability type; `recurseSubset`
(`:279-318`) recurses across iso-sets → it enumerates the full **IG-count × MA-count** grid automatically.
So adding MA to the subset filter is sufficient; no code change for the enumeration.

### 3.4 Only NON-TARGETING abilities
`:226` skips `hasTargetAbility()` cards. MA's ability is a non-target selfsac-create → **qualifies**. (This
is also why Drake/GM are fine to enumerate — all non-targeting — but see §6.)

### 3.5 IG-epsilon history — do NOT repeat for MA
Regime v3 had a targeted `EpsilonIG=0.25` to force IG counterfactuals. It was **dropped to 0 in v4**
because the net made reasonable IG-count choices just from being in the subset. Owner: same expectation
for MA — **no targeted MA-ε; keep the frozen general `EpsilonLate=0.05`.** The §4.1 sanity test is exactly
to confirm "makes reasonable choices on its own" before committing.

---

## 4. The steps in detail

### 4.1 Sanity-test the net's MA-count choices on game states (DO FIRST)
**Goal:** feed the iter4 net states where MA-firing is the decision, with MA in the subset, and confirm
the MA-count argmax/visit distribution **varies sensibly across states** — NOT all-0 (collapse) and NOT
always-max (stick). Owner is explicit that "correct play" in these states is unclear; we only need the
non-degenerate signal.

**Inputs:** the owner's 16 F6 dumps (2 games) in `docs/scratch/`:
`cPvQ3-thNwH_MA1.txt … MA12.txt` and `RY8WE-GMets_MA1.txt … MA4.txt` (~270–306 KB each).
- ⚠️ **They are NOT plain JSON** (parser hits "Extra data" at char ~14 — likely the F6 clipboard wrapper
  or concatenated objects). **Characterize the format first** (head the file). F6 dumps are historically
  **pre-swoosh DEFENSE phase** (per memory + `docs/og-masterbot-mistakes-research.md`); the AbilitySubset
  needs to reach the ACTION phase. Either (a) the iterator resolves DEFENSE→ACTION itself (it runs defense
  first), or (b) convert to an action-phase cppstate via the research-doc method: replay through the JS
  `Analyzer` + `replay_exporter.stateToCppJSON`. Confirm whether MA is on-board + it's the owner's turn in
  each.

**Mechanism (config-only, do NOT touch the campaign config):** create a TEST subset filter + root iterator
(mirror the IG wiring; e.g. filter `MA_Test_Subset = {Infusion Grid, Mobile Animus}` + iterator
`HardIterator_5var_MASubset_Root = {type:AbilitySubset, include:HardIterator_5var_NoIG_Root,
subsetFilter:MA_Test_Subset}`), then drive each state through:
```
node js_engine/query_move.js --request <state.json> --player <name> \
     --weights neural_weights_rl_iter4.bin \
     --dave-exe c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe \
     --root-iterator HardIterator_5var_MASubset_Root
```
`query_move` adds `EmitDiagnostics` → response carries `aivisits` / `aiargmax` / `aichosen` per root child.
Map the chosen child to its MA-count (how many `USE_ABILITY` on MA it contains). For a cleaner read also
exclude MA from the TEST interior (a test copy of `Ability_Filter_Live_NoIG` + MA), else the interior
auto-fires MA in the rollouts and biases the value. **Better tool:** extend `eval/action_coverage.py`'s
`--battery` path (it already does exactly this for IG over `eval/ig_battery/`) to an `ma_battery/` built
from these states — it reports `mean_ig_clicks_argmax` / `ig_click_dist_argmax` style stats per unit.
**Success = a non-degenerate MA-count distribution across the 16 states.**

### 4.2 Combinatorics probe (decides config-only vs C++)
Measure the **post-dedup ROOT candidate count** with the `{IG, MA}` subset on a small sweep (typical /
heavy-resource / multi-unit-at-supply states). The raw `25 × ∏(feasible_i+1)` badly overstates it
(exact-Move dedup `:169-173` + per-position feasibility usually 1–2 per axis). The **only** place the cap
binds is the root (§3.2). Two ways:
- **Config-only:** raise `MaxChildren` high on the test player and read `aivisits.length` from `query_move`
  diagnostics = the true post-dedup count.
- **Exact:** a scratch `--test-subset-count` probe in the `--test-*` idiom (`source/standalone/main.cpp`,
  like `--test-stalemate`) that builds the iterator and prints `buildAllMoves()` size + per-axis counts.
  This is a rebuild → use the **scratch-dir copy** so the pinned campaign exe is untouched (re-pin only if
  you fold it into a real build).

**Decision rule (from the prior session's handoff):** keep root children **≲ N/10** to preserve depth (at
self-play N=1000 that's ~100). If worst-case ≤ ~80–100 → **raise `MaxChildren`** (config-only; safe because
the subset is root-only and the interior is iterator-bounded ≤5) + bump N proportionally. If it balloons
(200+) → don't brute-force; build **value-aware truncation** + fix the longest-first emission order
(`:52-53`) so truncation stops dropping the low-click ("don't fire") candidates (a C++ change + re-pin).
⚠️ The cap binding at all is a CORRECTNESS issue, not just depth: longest-first keeps the most-click
candidates and silently drops the conservative ones → train on biased data. Set `MaxChildren` above the
measured worst case.

### 4.3 N-calibration (owner asked — yes, do it after adding MA)
The wider IG×MA root changes the breadth/depth tradeoff, so re-validate the search budget. Apparatus
exists: `eval/calibrate_n.py` + the `RL_Cal_N{100,256,512,1000,2000,5000}` tournament blocks
(`config.txt:328-335`) and `RL_Cal_vs_deploy_N*` (:335+). Re-run the (N) sweep **with MA in the subset**
(matched seeds), read self-play P0 win-rate + game length + the root-truncation rate, and pick N (and
`MaxChildren`) so the root isn't truncation-starved. Note: scale knobs (rounds, N, MaxChildren) are the
"re-anchor" tier in `campaign_frozen.json` — change deliberately + log it. (Historical (N,c) probe context:
`eval/rl_campaign.md` §1f; `project_cvalue_sweep_result_2026_06_02`.)

### 4.4 Open MA for RL — exact config edits + the campaign-change decision
**The IG wiring you are mirroring** (all in `c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt`):
- `IG_Only` (`:73-77`) = `{default:false, cards:["Infusion Grid"]}` — used by BOTH the AbilitySubset
  `subsetFilter` (root branches on it) AND `AbilityActivateUtilityClickNoIG` (`:118`, the **Click**
  ability variants' exclusion).
- `Ability_Filter_Live_NoIG` (`:67-71`) = `["Drake","Grenade Mech","Odin","Infusion Grid"]` — used by
  `AbilityActivateUtilityNoIG` (`:100`, the **Live/non-Click** ability variants' exclusion).
- So IG is (a) the subset axis AND (b) excluded from auto-fire in **both** the Click and Live variants.

**To open MA the same way, MA must be: in the subset filter + excluded from BOTH Click and Live auto-fire.**
Minimal edits:
1. Add `"Mobile Animus"` to the **subset filter** → covers root branching AND the Click-variant exclusion
   (since `IG_Only` is also the Click filter). Either extend `IG_Only` → `["Infusion Grid","Mobile Animus"]`
   (note the name `IG_Only` then becomes stale — consider renaming to e.g. `Subset_IGMA` and updating the 2
   references at `:118` and the AbilitySubset def `:211`), OR make a new filter + repoint.
2. Add `"Mobile Animus"` to **`Ability_Filter_Live_NoIG`** (`:70`) → covers the Live-variant exclusion.
   (Names resolve by internal name OR UIName — `CardTypes.cpp:78,93` — and MA's key == display == "Mobile
   Animus", so one entry suffices.)
3. Preflight: run `eval/preflight_config.py`. `iterator_shape` asserts the iterator *structure/names* (not
   filter contents), so it should pass; but **this is a deliberate campaign-identity change** — update
   `campaign_frozen.json` if it grows a subset-filter assertion, add an `eval/campaign_log.md` entry, and
   treat it as a re-anchor.

**DESIGN DECISION (resolve before running the loop): candidate-only vs shared-with-origin action space.**
`RL_SelfPlay`/`RL_Eval`/`RL_Eval_origin` (`config.txt:263,264,267`) ALL use `HardIterator_5var_IGsubset_Root`
with `IG_Only`. If you edit `IG_Only` in place, the **origin (v221) also gains the MA axis** → the origin
anchor measures "iter4-net-on-IG+MA vs v221-net-on-IG+MA" (both nets on the new action space). If instead
you make a new filter/iterator and point only the candidate players at it (leaving `RL_Eval_origin` on
`IG_Only`), you measure "iter4+MA-axis vs v221-without". Pick deliberately — it changes what the origin
drift means. (No rebuild either way; config-only.)

Then: run `eval/run_iteration.ps1 -K 5` … promote-unless-collapse … **checkpoint** (`run_checkpoint.ps1
-Iteration 0`) to get the powered read on whether the MA axis moved the needle. **MA-first, alone** (§5).

---

## 5. Curriculum decision (settled this session)

**Open MA FIRST, by itself, as the single-axis validation** of the whole "open an action-space gap →
powered gain" thesis — because that thesis is **not yet validated** (rl_iter4 already has IG open and is
only ~+2pp powered over v221). If MA's checkpoint shows a real powered gain → thesis validated → then add
others. If not → cheapest place to learn the lever isn't paying off before sinking more axes in. Per-axis
**behavioral** attribution is cheap (the action_coverage MA-click telemetry, every iteration); only the
**strength** read needs the ~3 hr checkpoint, at the normal K=3–5 cadence. Batching axes risks masking a
regression in a modest/noisy regime → avoid.

---

## 6. Buy-side: what to expect for generator buys when MA fires (VERIFIED)

(Full analysis: this session's workflow; the buy path matters because the AbilitySubset re-runs the buy
fresh on the post-MA-sac state.)

- **`TechHeuristic` cannot buy MA.** It is hardcoded to exactly three generators — **Conduit (green),
  Blastforge (blue), Animus (red)** — by literal string lookup
  (`PartialPlayer_ActionBuy_TechHeuristic.cpp:57-69`, buys ≤1/call `:294-311`). Mode is `ElyotFormula`
  (the only one wired). Guards: Action phase + ≥4 gold (`:16-26`); turn-2 gold gates `:106-117`; per-color
  caps from dominion-cost math `:194-201` (the `EconLimits` min at `:204-206` is **dead** on the live path —
  `BuyTech_Elyot` has no `buyLimits`). It runs **LATE** in every buy variant → spends **leftover** gold.
- **`BuyGK_Filter` is a DENY-list** (`config.txt:26-42`; polarity proven `CardFilter.cpp:168-173` +
  `GreedyKnapsack.cpp:142-151`). It lists `Animus` (`:29`) → base Animus is BLOCKED from the knapsack
  (bought only by TechHeuristic). **`Mobile Animus` is NOT on it → the GreedyKnapsack CAN already buy MA
  today.**
- **The "merry-go-round" has two separable rebuy legs** on a post-MA-sac state:
  - (a) **base Animus** via TechHeuristic — lowered red income loosens the `rIncome < maxAnimus` gate
    (`:226`) → desirable replacement of lost red. **Don't guard this.**
  - (b) **another Mobile Animus** via GreedyKnapsack — possible because MA isn't deny-listed. **This is the
    churn risk.**
- **The buy-limit cap is BOARD-COUNT, not whole-game** (owner asked): checked as
  `state.numCardsOfType(player,type) >= limit` (`Sequence.cpp:40-41`, `GreedyKnapsack.cpp:166-167`;
  `numCardsOfType` = live owned count, drops on sac, `GameState.cpp:1684`). So `DefaultLimits ['Mobile
  Animus',1]` (`config.txt:82`, currently **orphaned/unwired**) would **NOT** stop the sac→rebuy churn —
  after MA saces, the count is 0, so a rebuy is allowed. It only prevents *stacking* 2+ MA on board.
- **Net read:** opening the subset is **plausibly neutral-to-positive** for the merry-go-round — it removes
  the FORCED sac (the net can pick fire-0 and keep MA). The only config-only HARD block on leg (b) is
  deny-listing MA in `BuyGK_Filter` (blunt — kills all knapsack MA buys). There is **no cumulative
  "buy ≤1 per game" mechanism** in the engine. Recommendation: rely on fire-0 + RL; add the
  `DefaultLimits` wire-up only if you separately want to cap MA *stacking* (`AbilitySubset.setBuyLimits`
  `:27-33` forwards limits to the inner portfolio, so an iterator-level `"buyLimits":"DefaultLimits"`
  would propagate — same mechanism as `RedRush`/`GreenBlue` at `config.txt:217-219`).

---

## 7. Deferred / parked (NOT for this MA pass)

- **Drake + Grenade Mech as further subset units.** Owner wants them eventually (they're rare, supply 4 →
  count matters; current handling is all-or-nothing via the **Click vs Live** ability variants, NOT a value
  heuristic). **Blocked on:** owner wants to research **what the 5 "Click" variants actually do** before
  pulling units out of them. Drake's ability **saccs a Blastforge** (`abilitySac:[["Brooder"]]`) for +2
  attack; GM(`Blade`) saccs a Blastforge for 3 Pixies, cost 1 — different KIND from MA's selfsac, so treat
  separately. **Odin is OUT** (legendary, supply 1 → a 0..N count = the existing binary → pointless).
- The combinatorics probe (§4.2) should include Drake/GM when they come (they drive the cross-product), but
  for the MA-only pass measure `{IG, MA}`.

---

## 8. Reference card (verified file:line)

| Thing | Location |
|---|---|
| AbilitySubset core / buy re-run / iso-cross-product / hasTargetAbility / longest-first | `dave: source/ai/MoveIterator_AbilitySubset.cpp` :64-193, :128-149, :201-318, :226, :52-53; setBuyLimits :27-33 |
| AbilitySubset config parse | `dave: source/ai/AIParameters.cpp:1166-1180` |
| Subset root iterator (campaign) | `config.txt:211` `HardIterator_5var_IGsubset_Root` (include `:210` NoIG_Root, subsetFilter `IG_Only`) |
| Interior iterator | `config.txt:213` `HardIterator_5var_NoIG` |
| Subset/Click filter | `config.txt:73-77` `IG_Only`; Click ability var filter `:118` `AbilityActivateUtilityClickNoIG` |
| Live (non-Click) interior exclusion | `config.txt:67-71` `Ability_Filter_Live_NoIG`; var filter `:100` `AbilityActivateUtilityNoIG` |
| RL players (root/interior) | `config.txt` RL_SelfPlay `:263`, RL_Eval `:264`, RL_Eval_origin `:267` |
| MA card | `cardLibrary.jso:941-952` (selfsac create Elephant/Rhino, cost 2g, receive C) |
| MA force-fire path | `dave: source/ai/PartialPlayer_ActionAbility_ActivateUtility.cpp` :32-67, :40-44, :70-98 |
| Name resolution (internal OR UIName) | `dave: source/engine/CardTypes.cpp:78,93` |
| TechHeuristic | `dave: source/ai/PartialPlayer_ActionBuy_TechHeuristic.cpp` :57-69, :294-311, :226, :106-117, :194-201 |
| Buy tree / BuyGK_Filter (deny) / DefaultLimits | `config.txt` BuyEconTech `:181`, BuyTechEcon `:183`, BCG*_Root `:187-189`, BuySafeguard `:184`/`:190`, BuyGK_Filter `:26-42` (Animus `:29`), DefaultLimits `:82` (orphaned), EconLimits `:83` |
| Buy-limit = board-count | `Sequence.cpp:40-41`, `GreedyKnapsack.cpp:166-167`, `GameState.cpp:1684` |
| N-calibration | `eval/calibrate_n.py`; `config.txt:328-335` `RL_Cal_N*`; `MaxChildren=40`+N/10 (`UCTNode.cpp:54`) |
| query_move (diagnostics) | `js_engine/query_move.js` (`--root-iterator`/`--move-iterator`/`--weights`/`--dave-exe`; emits `aivisits`/`aiargmax`/`aichosen`) |
| IG battery (template for MA battery) | `eval/ig_battery/`; coverage tool `eval/action_coverage.py --battery` |
| Steam bundle (per checkpoint) | `eval/build_steam_bundle.ps1 -Label <name>` → `C:/libraries/DSNN_steam_bundles/<name>/` (self-verifying; engine `dave@50977510`+ uses `use_dsnn.txt weights=` + NoIG interior) |

---

## 9. Corrections made this session (use the VERIFIED column; older docs/memory have the LEFT)

| Earlier/assumed (WRONG) | Verified (USE THIS) |
|---|---|
| "MA is never fired" / "already value-evaluated" | **MA is FORCE-FIRED** every variant (not excluded anywhere); ActivateUtility greedily selfsacs it. |
| "Drake/GM are evaluated by a GreedyKnapsack value-heuristic" | **No value heuristic touches them.** They're all-or-nothing via the **Click vs Live** ability variants (greedy fire-all vs excluded). |
| "Drake's click is free / gains attack" | Drake **saccs a Blastforge** for +2 attack (`abilitySac:[["Brooder"]]`); GM saccs a Blastforge for 3 Pixies. |
| "BuyGK_Filter is an allow-list" | **DENY-list.** Listed units (Animus, Conduit, Blastforge, Steelforge, Drone, Engineer…) are BLOCKED from the knapsack; MA is NOT listed → knapsack CAN buy MA. |
| "DefaultLimits caps total MA bought; wire it to guard the merry-go-round" | Cap is **board-count** (max simultaneously owned) → does NOT stop sac→rebuy churn (count resets to 0 on sac). |
| "Conduit = energy" / TechHeuristic config-driven | Conduit = **GREEN**, Blastforge=BLUE, Animus=RED; TechHeuristic generator set is **literally hardcoded** to those 3 strings. |
| IG filter listed both "Hotel" + "Infusion Grid" | Redundant (resolve to same type); cleaned to `["Infusion Grid"]` this session (dave `344e716c`). |
| CLAUDE.md "parent = rl_iter2" | Parent is **rl_iter4** (campaign_frozen.json is the source of truth). |

---

## 10. Owner preferences / guardrails (carry forward)
- Push only to the `PrismatAlpha` fork, only when asked; never upstream. Commits stay local otherwise.
- `config.txt` = strict JSON, **NO BOM**, surgical edits only. `campaign_log.md` append-only.
- Token/Workflow/model cost is **not** a constraint (cost-conscious = AWS only). Ultracode on → use
  Workflow + adversarial verification for substantive engine questions (it caught real errors this session).
- Prefer **small, code-provable, low-regression** AI fixes; willing to call a play a wash. Don't force a fix.
- Two sessions must not edit `dave config.txt` concurrently (a parallel session's unsolicited
  `IG_Drake_Subset` scaffolding was removed this session, dave `344e716c`).
