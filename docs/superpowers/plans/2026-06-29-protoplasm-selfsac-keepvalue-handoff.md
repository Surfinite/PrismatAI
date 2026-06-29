---
title: "Protoplasm / self-sac & fragile keep-value — INVESTIGATION HAND-OFF"
date: 2026-06-29
status: INVESTIGATION (root cause diagnosed; fix direction sketched + evidence; DESIGN DISCUSSION still required before implementing)
owner: Surfinite
scope: "JS defense-eval value model only (gen_our_numbers_v2.js + eval/defense/). The prime-defender keep-value shipped; this fixes a class it gets wrong. C++ port still deferred."
builds_on:
  - docs/superpowers/specs/2026-06-25-prime-defender-keep-value-design.md   # the shipped keep-value model (§2)
  - docs/superpowers/plans/2026-06-26-prime-defender-keep-value.md           # the implementation plan (7 tasks, all shipped)
  - eval/defense/results/report.md                                          # the 5000-game corpus where the divergence shows
---

# Protoplasm / self-sac & fragile keep-value — INVESTIGATION HAND-OFF

> Fresh session: the prime-defender keep-value feature SHIPPED and validated (zero-regret 82.7%→84.2%, cpp gate
> byte-identical). The owner then spotted a real gap from `report.md`: **Protoplasm is not selected as the prime
> defender on turns where it should be — the model chumps/sacs it away.** Your job is NOT to blindly implement a
> fix — the owner flagged this needs **design discussion**. Your job is to (1) absorb the diagnosis below, (2) be
> ready to discuss the fix direction + open questions, (3) implement once the owner has settled the model. Do the
> design conversation FIRST (use `superpowers:brainstorming` if it helps). Then plan + implement subagent-driven
> exactly like the shipped feature (`writing-plans` → `subagent-driven-development`, TDD, oracle cross-check, cpp
> untouched, commit per task on `feature/production-vectors`, do NOT push without the owner asking).

## 0. The problem in one paragraph

The shipped keep-value model credits a surviving prime its **perpetual future-absorb** (`futureAbsorb =
sustainableAbsorb·BV·factor`). For a **self-sac burst unit like Protoplasm** (4HP fragile, click = self-sac for 4
attack) this is doubly wrong: its **4-attack burst is dropped entirely** by the chump-term's `max(block,burst)`,
and as a fragile non-healer its **`futureAbsorb` is 0**, so it earns no prime credit. Meanwhile a **Wall** earns a
large `futureAbsorb` (13.2) even though a *prompt* Wall is cheap to rebuy. Net: the model prefers to keep a Wall as
the anchor and **chump the Protoplasm**, where humans (and even the faithful C++ baseline) keep the Protoplasm as
the prime and chump the Walls. The owner's leading hypothesis is "add the burst as a benefit the prime defender
gets," and the evidence below supports that **plus** a prompt-rebuy discount on cheap blockers.

## 1. Context — the shipped keep-value model (what you're modifying)

**The `ours`-mode defense objective** (`eval/defense/defense_sim.js::solveDefense`, validated against an unbounded
brute-force oracle):

```
loss = Σ_dead V(unit)                                      # chump rule — full value lost on death
     + primeLoss(prime)                                    # the surviving prime's partial-damage cost
     − futureAbsorb(prime)                                 # PRIME credit (uncapped perpetual absorb)
     − Σ_{untouched below-max healers} untouchedHealerCredit(h)   # room-capped, survival credit
```

`futureAbsorb(view)` (`eval/defense/defense_value.js`):
```
sustainableAbsorb = HP−1 (non-fragile, repairs) | heal (fragile HEALER) | 0 (fragile NON-healer)   ← the trap
factor            = (P−1)=3 (permanent) | Σ_{k=1}^{life−1} d²ᵏ (doomed)
```
So **every fragile non-healer gets `futureAbsorb = 0`** — Protoplasm, Colossus, Scorchilla, Forcefield all earn
zero prime keep-value. That is the central trap (see §4 thread B).

**The per-unit value `V` / `ours()`** lives in `docs/scratch/gen_our_numbers_v2.js`. A self-sac unit is valued
`v = max(block, burst) + opt` (`coreValue`, the `if ((ab && ab.selfsac) || (bt && bt.selfsac))` branch). For
Protoplasm `block 8.7 > burst 7.62`, so **the burst is dropped**; `V = 8.9` (≈ a 4HP fragile blocker).

**Where credits are applied symmetrically:** `compare.js` (Finding A) subtracts the same credits from the human's
loss; `metrics.js` runs the tripwire on the chump-loss component (Finding B). Any new credit MUST be applied to
BOTH the AI (`defense_sim.js`) and the human (`compare.js`) or regret breaks. `cpp` mode must stay untouched.

## 2. The exact card

**Protoplasm** — internal key **`Pixieflower`**. `toughness=4`, `fragile=true`, `defaultBlocking=1`,
`abilityScript={"receive":"AAAA","selfsac":true}` (click → sacrifice self, deal **4 attack**). No charge, no
lifespan, no `beginOwnTurnScript`. `ours()` ⇒ `v=8.9, block=8.7, atk=0.2, burst=7.62` (burst = 4·ATK = 4·1.905).

Related self-sac / fragile units (for the unifying question, §8):
| Unit | internal | HP | fragile | ability | `ours` V | futureAbsorb | note |
|---|---|--:|---|---|--:|--:|---|
| Protoplasm | Pixieflower | 4 | yes | selfsac receive AAAA (4 atk) | 8.9 | **0** | burst dropped; fragile→0 |
| Infusion Grid | Hotel | 4 | **no** | selfsac create 4 Husks | 8.9 | **19.8** | spurious perpetual (it sacs!) |
| Nitrocybe | Nitrocybe | 1 | no | selfsac receive A (1 atk) | 2.4 | 0 | (hp−1=0) |
| Photonic Fibroid | — | 2 | no | begin-selfsac 2 atk | 4.6 | (n/a, auto) | |
| Colossus | Colossus | 8 | yes | click receive AAA (3 atk, NOT sac) | 34.95 | **0** | block+click; fragile→0 |
| Scorchilla | Rocket Artillery | 3 | yes | click receive AAA delay 3 | 10.97 | **0** | block+click/3; fragile→0 |
| Forcefield | — | 2 | yes | pure block (designer 3.75 in cpp) | — | **0** | corpus over-chumped (ai-only 2302) |

## 3. Diagnosis — empirical (run on the committed model)

### 3a. The owner's minimal example battery — this is the test oracle for any fix
Boards (PD = the prime defender the owner says is correct in most cases):

| # | board | incoming | WANT prime | CURRENT model | status |
|---|---|--:|---|---|---|
| 1 | Husk + Rhino(ch2) + Protoplasm | 2 | Rhino | **Rhino** | ✅ already correct |
| 2 | 2×Husk + Wall + Protoplasm | 4 | Wall | **Wall** | ✅ already correct |
| 3 | 2×Husk + Wall + Protoplasm | 6 | **Protoplasm** | Wall (chumps Proto) | ❌ |
| 4 | 3×Husk + Protoplasm | 3 | Protoplasm | **Protoplasm** | ✅ (only feasible prime) |
| 5 | Infusion Grid + Protoplasm | 7 | **Protoplasm** (close) | Infusion Grid (chumps Proto) | ❌ |

(Examples 1/2/4 already pass — a fix must NOT break them. The burst, modeled as a *survival* credit, **cancels**
in 1/2 because Protoplasm survives in both compared options; that's why they're already right and must stay right.)

### 3b. The corpus smoking gun (`+cvBx-rRItc`)
From `eval/defense/results/records.jsonl.gz` (gunzip + filter by `id.replay.includes('cvBx')`):

- **step 167, incoming 9, board = 2 Engineer + 2 Wall + 2 Protoplasm:**
  - HUMAN: prime **Protoplasm**, chump 2 Walls (loss_ours 19.8)
  - OURS:  prime **Wall**, chump 1 Wall + **1 Protoplasm** (loss 2.3) → **regret 17.5**
  - CPP (faithful old engine): prime **Protoplasm**, chump 2 Walls — **agrees with the human**
- **step 181, incoming 11:** human primes Protoplasm; OURS chumps everything incl. the Protoplasm (prime=null), regret 2.9.

**The headline:** on this class our new keep-value model is a **regression vs the C++ baseline** (cpp gets it
right, ours wrong). That is why `report.md` shows Protoplasm `human-only chumped = 0, ai-only = 579` — humans
essentially never chump it; we do. (Same diagnostic flagged Forcefield 2302/173 and Protoplasm — see §8.)

### 3c. Why the model chumps the Protoplasm (the loss arithmetic, step 167)
- OURS pick (chump 1 Wall + 1 Proto, prime Wall): `V(Wall 6.6) + V(Proto 8.9) − futAbs(Wall 13.2) = 2.3`.
- HUMAN pick (chump 2 Walls, prime Proto): `V(2·Wall 13.2) + primeLoss(Proto@4→1 6.6) − futAbs(Proto 0) = 19.8`.
- The model thinks the human play is 17.5 worse because: Protoplasm-as-prime earns **0** (burst invisible), the
  chumped Protoplasm forfeits its burst for **free** (not penalized), and keeping a **Wall** earns **13.2**.

## 4. Root causes — TWO coupled threads

**Thread A — self-sac units are mis-valued (Protoplasm AND Infusion Grid, opposite directions):**
- A1. The **burst is dropped**: `V = max(block, burst)` instead of crediting the burst when the unit *survives and
  sacs*. A self-sac unit's optimal use is **block once (as prime) then sac next action phase** → it provides
  block **and** burst, not `max`.
- A2. Self-sac units get the **wrong `futureAbsorb`**: a consumed unit is NOT a perpetual anchor. Fragile self-sac
  (Protoplasm) → 0 (under). Non-fragile self-sac (Infusion Grid) → 19.8 perpetual (spurious over — it converts to
  Husks, it does not block 3/turn forever). Both should instead earn their **one-shot production** (burst 7.62 /
  convert 7.8) as a survival credit.
- A3. A self-sac prime's **`primeLoss` should be ~0** ("free absorb"): the HP it loses absorbing is HP it would
  have sacrificed anyway. Currently `primeLoss(Proto@4→1) = 6.6` over-charges it.

**Thread B — fragile non-healers earn 0 keep-value, and prompt blockers earn too much:**
- B1. `sustainableAbsorb = 0` for every fragile non-healer → Protoplasm/Colossus/Scorchilla/Forcefield earn **no
  prime credit**, so the model over-chumps them. (Forcefield's corpus over-chump is the same trap.)
- B2. **Prompt/rebuyable blockers (Wall, Husk) earn their full `futureAbsorb` (Wall 13.2)** even though a prompt
  unit is cheap to replace during the same action phase. The owner's note: *"Wall being prompt can die and be
  rebought during the action phase of the same turn, so it doesn't matter if we chump it to a fragile-prime."* This
  over-credit is what makes the model cling to Walls and chump Protoplasms.

Protoplasm hits A1+A2+A3 **and** is on the losing side of B2. Example 3 and step 167 do **not** flip from the
Thread-A fixes alone — the Wall's 13.2 dominates — they need **B2** too (verified below).

## 5. Fix direction + evidence (what each example needs)

The owner asked: *"Do we just need to add the burst attack in as a benefit that the prime defender gets?"* Evidence
says: that is necessary but **not sufficient** for the hard cases; pair it with the prompt-rebuy discount.

**Candidate model (to be debated, not yet decided):**
1. **Self-sac keep-value = one-shot production, as a SURVIVAL credit.** Replace a self-sac unit's `futureAbsorb`
   with its burst/convert value (Protoplasm 7.62, IG 7.8), credited when the unit **survives the defense phase**
   (prime OR untouched) and forfeited when chumped. Keep the chump-term `V` as the block floor (drop the
   `max(block,burst)`; the burst now lives in the survival credit so it isn't double-counted). [A1+A2]
2. **Self-sac prime `primeLoss` = 0** (free absorb). [A3]
3. **Prompt-rebuy discount** on cheap blockers' `futureAbsorb` (Wall, Husk, …): a prompt unit's perpetual-anchor
   credit should be scaled down (it's cheaply replaced). [B2] — this is the bigger/thornier change; needs a
   principled "is this unit cheaply rebuyable" signal (build-time 0/1? buy cost? a `prompt` flag?).

**Hand-checked outcomes** (controller's scratch math; reproduce + pin before trusting):
- **Example 5 (IG vs Proto, 7):** with (1)+(2) — IG and Proto both earn ~7.6–7.8 survival credit, Proto's free
  primeLoss makes them ~tied (IG 1.1 vs Proto 1.28) → a small **attack-burst > token-burst** optionality tips it to
  Protoplasm (matches "close, lean Proto"). (1) alone is enough here; (3) not needed.
- **Example 3 (2Husk+Wall+Proto, 6) and step 167:** flip to prime-Protoplasm **only** once the Wall's `futureAbsorb`
  is discounted (B2). With Wall futAbs ≈ halved, ex-3 gives prime-Proto −1.02 vs chump-Proto +2.3 ✓; step 167 gives
  human-play −2.04 vs ours-play +1.28 ✓. Without B2 the Wall's 13.2 keeps winning.
- **Examples 1/2/4:** unaffected (the survival credit cancels; the prime choice is decided by the other units).

So the **minimal** change is (1)+(2); the **complete** fix for the Wall-heavy cases needs (3). Confirm whether the
owner wants to ship (1)+(2) first (helps IG-class + the close cases) and tackle (3) as a follow-up, or do both.

## 6. Open questions for the design discussion (the owner's calls)

1. **Survival credit vs prime-only.** Should the self-sac burst be credited on any survival (prime or untouched),
   or only when it's the prime? (Untouched Protoplasm can still be sacced, so survival-credit is physically right —
   but does it ever cause an untouched self-sac unit to be over-kept? Check.)
2. **Does the chump-term `V` change at all?** The owner *revised away* from a chump-loss change after looking at
   `+cvBx-rRItc`. The candidate keeps `V` = block floor and moves the burst into a survival credit (so chumping a
   self-sac unit forfeits the burst implicitly). Confirm this matches the owner's intent (vs. literally
   `V = block + burst`).
3. **`max(block,burst)` vs `block + burst`.** Is `max` ever right for a self-sac unit? (It was meant as "keep it as
   a blocker OR sac it." But a one-soak fragile unit isn't a good perpetual blocker, so `block` and `burst` are
   sequential, not exclusive.) Decide the per-unit `ours()` value too (it feeds Q-comparison + other tooling).
4. **Prompt-rebuy discount (B2): how to identify "cheap/prompt"?** Build-time ≤ 1? A small buy-cost threshold? A
   curated set {Wall, Husk, Drone, Engineer}? And how much to discount (the magnitude that flips ex-3/step-167
   without breaking the shipped Wall-vs-Rhino / EM-vs-Xaetron cases). This is the riskiest piece — it touches every
   board with a Wall.
5. **Optionality magnitude.** The current `OPT_SELFSAC_ATK=0.2 / OPT_SELFSAC_TOKEN=0.1` opt bonuses — do they
   survive, or fold into the survival credit? The atk-vs-token tip in ex-5 may want a slightly larger atk premium.
6. **Infusion Grid's spurious 19.8.** Independently of Protoplasm, IG's non-fragile `futureAbsorb=19.8` is wrong
   (it self-sacs). Fixing A2 corrects it — but verify IG isn't relied on as a "good anchor" anywhere in the
   shipped 12-example battery (it isn't — IG only appears as case 9's relative, all fine).

## 7. The unifying fragile question — Colossus / Scorchilla / Forcefield (LOOK AFTER PROTOPLASM)

The owner will look at Colossus and Scorchilla next, *"if they aren't also corrected by whatever change we need to
make for Protoplasm."* They are **fragile click-attackers, NOT self-sac** (block + perpetual click stream), so
Thread A (self-sac) does NOT apply, but **Thread B1 does** — they earn `futureAbsorb = 0` because they're fragile.
Hypotheses to check (do NOT start until the owner provides Colossus/Scorchilla examples):
- Colossus V=34.95 is already large (block 17.5 + atk 17.45), so its high chump-cost may protect it from being
  chumped even with 0 prime credit — it may be FINE. Scorchilla (V=10.97) is more exposed.
- **Forcefield over-chump (corpus ai-only 2302 vs human 173) is the cleanest B1 case** (fragile *pure* blocker,
  futAbs 0). A principled fragile keep-value (a fragile unit still re-blocks next turn, just without repairing —
  maybe `(HP−1)·BV·(P−1)` discounted, or a flat fragile anchor value) might fix Protoplasm's block-side,
  Forcefield, Colossus, and Scorchilla together. Worth probing whether ONE fragile-keep-value change subsumes the
  Protoplasm block-side (leaving only the burst as the self-sac-specific add).

## 8. How to reproduce / where things are

- **Committed model:** `docs/scratch/gen_our_numbers_v2.js` (per-unit `ours()`), `eval/defense/defense_value.js`
  (`futureAbsorb`, `untouchedHealerCredit`, `V`, `body`, `loss`, `unitView`), `eval/defense/defense_sim.js`
  (`solveDefense` — the B&B + the objective + the `−H` trick), `eval/defense/compare.js` (human-side credits),
  `eval/defense/metrics.js` (tripwire + divergence tables).
- **Run a board:** `dv.unitView({cardName:'Protoplasm', owner:0, health:4})`, `sim.solveDefense(units, incoming,
  'ours')`. There is a ready research harness in the session scratchpad: `proto_research.js` (enumerates every
  one-prime option with the loss breakdown + the best prime=Protoplasm option) — copy its pattern.
- **Corpus position:** `gzip -dc eval/defense/results/records.jsonl.gz | node -e "...filter id.replay/​step..."`
  (see §3b). The provenance/codes: `training/data/human_elite_2000_45s_v2.provenance.json`.
- **Re-run the corpus** after a fix (≈2 min): extract `selected_codes` → a file, then
  `node eval/defense/compare.js <codes> eval/defense/results`. Success = Protoplasm `human-only` divergence shrinks
  AND zero-regret does not drop below 84.2% AND the cpp gate column is unchanged.
- **Tests:** `node --test eval/defense/*.test.js` (Node 24 — glob, not a bare dir). 58 currently pass.

## 9. Hard constraints (must not break)

- **The shipped 12-example acceptance battery** (`eval/defense/defense_sim.test.js`) + the **brute-force oracle
  cross-check** (60-board battery) must still pass. Any objective change must keep the **B&B == oracle** invariant
  — update the oracle to the new objective and re-validate. (The oracle is the safety net; never tune the B&B to
  the oracle, fix the model.)
- **`cpp` mode byte-identical** (the gate). All new terms gate on `mode==='ours'`.
- **Finding A symmetry:** any new survival/burst credit applied to the AI in `defense_sim.js` MUST be applied to the
  human in `compare.js` or regret is corrupted (identical defense → regret 0).
- **Finding B:** the tripwire reads `chumpLossComponent`; large negative credited losses are by design.
- Examples 1/2/4 (Protoplasm already-correct) must remain correct.

## 10. Deferred-but-related (from the shipped feature's final review)

- New corpus over-chump clusters already logged for tuning: **Forcefield 2302/173, Protoplasm 579/0, Nitrocybe
  1048/57**. Protoplasm is this hand-off; Forcefield/Nitrocybe are likely the same Thread-B1 fragile trap and may
  fall out of the same fix.
- `metrics.js` hard-requires the scratch generator at load (coupling note for the eventual C++/CI port).

## 11. KICKOFF PROMPT (paste into a fresh session)

```
Resume the Protoplasm / self-sac keep-value investigation. Read
docs/superpowers/plans/2026-06-29-protoplasm-selfsac-keepvalue-handoff.md (full diagnosis, the example battery,
the corpus smoking gun at +cvBx-rRItc step 167, the two root-cause threads, and the candidate fix). Do NOT
implement yet — the owner wants to settle the model first. Start a design discussion (superpowers:brainstorming)
on: (1) self-sac burst as a survival credit + free prime absorb, (2) the prompt-rebuy discount on Wall/Husk
keep-value, (3) whether one fragile-keep-value change subsumes the block side for Protoplasm/Forcefield/Colossus/
Scorchilla. Once the owner settles it, plan it (writing-plans) and implement subagent-driven (TDD, oracle
cross-check, cpp untouched, commit per task on feature/production-vectors, do not push without asking). The
shipped 12-example battery + the brute-force oracle + the cpp gate must stay green.
```
