---
title: "Prime-Defender Keep-Value + Half-Turn Clock + Multi-Turn Heal — DESIGN"
date: 2026-06-25
status: DESIGN APPROVED (brainstorm complete) — ready for implementation plan
owner: Surfinite
scope: "Three coupled value-model changes in the JS eval model. OUT: the C++ port into Heuristics, and global R / future-flow tuning (both deferred to their own work)."
builds_on:
  - docs/scratch/gen_our_numbers_v2.js                              # the functional value model (ours())
  - docs/superpowers/specs/2026-06-24-defense-eval-pipeline-design.md # the eval harness this is measured in
  - docs/superpowers/plans/2026-06-24-defense-eval-audit-findings.md  # the §5/divergence signal that motivated this
engine_target: "JS eval model only — gen_our_numbers_v2.js + eval/defense/. C++ port deferred."
---

# Prime-Defender Keep-Value + Half-Turn Clock + Multi-Turn Heal — DESIGN

## 0. Motivation

The defense-eval run showed `ours` over-chumps reusable blockers (Walls) and under-chumps spent-economy /
charge units (Engineers, ch2-Rhinos), because the value model counts an **attacker's** perpetual stream but only
a **blocker's** one-soak body — so it has no reason to *keep* a reusable Wall. The fix is a **prime-defender
keep-value** that credits the one surviving anchor its perpetual *absorb*, built on a **half-turn clock** that
also makes `ATK` fall out of `BV` cleanly, plus a **multi-turn heal** extension so healers value correctly.

These three are coupled (the keep-value and the heal both ride the half-turn clock), so they ship as one spec.

## 1. The half-turn clock (foundation)

Time is measured in **half-turns** (one defense phase apart): my defense phases land on t = 0, 2, 4…; my attacks
land on the opponent's defense phases t = 1, 3, 5… (a half-turn later — that offset is *why* an attack is worth
less than a block at the moment of production).

- **`R_HALF = √(4/3) ≈ 1.1547`**, per-half-turn discount **`d = 1/R_HALF ≈ 0.8660`**, `d² = 0.75`.
- **`P = 1/(1−d²) = 4`** — the full-turn block perpetuity, **unchanged** (the existing `geomPerp(1)=4` machinery
  stays; every "once per full turn" stream still sums to 4).
- **`ATK` becomes derived: `ATK = BV·d = BV / R_HALF ≈ 1.905`** (down from the standalone `2.0`). The "pending
  attacker-producer derivation" now falls out of the clock: one attack-point = one block-HP realized a half-turn
  later.

**Code (`gen_our_numbers_v2.js`):** add `const R_HALF = Math.sqrt(4/3)`; replace `const ATK = 2.0` with
`const ATK = BV / R_HALF`. Nothing else in the constants/perpetuity machinery changes. Regenerate
`our_numbers_v2.md`; the only ripple is every attacker's *attack component* scaling ≈ ×0.95 (blockers, economy,
charge/lifespan structure untouched). Eyeball the re-sorted ordering (it barely moves).

## 2. The keep-value term — REVISED (2026-06-26, post-design-review)

> The original §2 below the line ("prime-only credit, subtract from the prime") was **superseded** during the
> design review. The final model adds one more term — an **untouched below-max healer** also earns its future
> absorb (a healer banks deferred absorb by climbing whether or not it's this turn's prime), **room-capped** so a
> *near-maxed* healer is dumped rather than preserved. Every probe (cases 1,2a,2b,3,4,6,7,8,9,10 + the @11-dump,
> @11-with-EM-keep, maxed-dump, and 14-damage boards) lands under this model and against an unbounded brute-force
> oracle. The decomposition is owner-derived: **chump-rule = "what I lose if it dies"; prime-rule = the one thing
> the chump rule misses, the future absorb a *surviving anchor* provides on later turns.**

**The objective (`ours` mode only):**

```
loss = Σ_dead V(unit)                                   # chump rule: full value lost on death (incl. §3a heal-climb)
     + primeLoss(prime)                                 # the surviving prime's partial-damage cost (0 non-fragile; body-delta healer)
     − futureAbsorb(prime)                              # PRIME credit, uncapped (P−1) — only a TRULY surviving prime
     − Σ_{untouched below-max healers h} futureAbsorb(h) · min(1, room_h / heal_h)   # UNTOUCHED-healer credit, room-capped
```

```
futureAbsorb(unit) = sustainableAbsorb · BV · factor
   sustainableAbsorb = HP−1 (non-fragile, repairs to full) | heal (fragile healer) | 0 (fragile non-healer)
   factor            = (P−1)=3 (permanent)                          # P·d² = 4·0.75; first future absorb is the NEXT
                                                                    # defense phase (2 half-turns out) — already "delayed"
                     | Σ_{k=1}^{life−1} d^(2k) (doomed: 0.75@life2, 2.05@life5, →3)   # doomed anchors finitely then expires
   room              = max − HP                                     # room ≤ 0 (maxed) ⇒ untouched credit 0  ("dump it")
```

**The two rules, in plain terms:**
- **Prime credit (`futureAbsorb(prime)`, uncapped):** only the designated anchor absorbs each turn, so only the
  surviving prime earns its perpetual absorb. Non-fragile units and **maxed** healers earn this *only* as the
  prime. The `(P−1)` factor already encodes the one-defense-phase delay (the prime's *next* absorb is next turn) —
  do **not** delay it further (extra delay breaks EM-vs-Xaetron@5: that case keeps the Xaetron precisely because
  EM and Xaetron carry *equal, undelayed* 26.4 that cancels, leaving the chump rule to decide).
- **Untouched-healer credit (room-capped):** a **below-max** fragile healer banks deferred absorb by climbing even
  when untouched, so it earns its future absorb *either way* (prime **or** untouched). The `min(1, room/heal)` cap
  mirrors the §3a chump-loss cap: a healer with a full heal of room (`room ≥ heal`) banks efficiently → full
  credit → leave it to climb; a near-maxed healer (`room < heal`) wastes most of its heal climbing → reduced
  credit → it gets dumped (primed) instead. The **prime** credit is *not* room-capped (it's the steady-state
  perpetual rate of the eventual anchor — a flow, independent of today's HP).

**Why this is exactly right and not double-counting** (the long-running worry, resolved): the untouched-healer
credit must *equal* the prime credit when `room ≥ heal` (both `futureAbsorb`) **on purpose** — so the healer is
valued identically whether it is this turn's prime or untouched, making its anchor value **prime-neutral**. In any
comparison where the healer survives in both options its credit **cancels** and never tilts the prime choice; it
only stops cancelling when one option *chumps* the healer — exactly when it should bite (don't throw away your
anchor). The residual overlap (the same heal appears as "growth" in the chump term and "absorb" in the credit) is
a bounded magnitude artifact that never flips a decision across the full probe set. The **size of the alternate
prime** is handled automatically — the alternate's *own* credit is in the comparison, so a big alternate (EM, 26.4)
makes "keep the near-maxed healer untouched, prime the EM" win, while a small alternate (Wall, 13.2) makes "dump
the healer" win, with no change to the untouched term.

**Where it enters:**
- `eval/defense/defense_value.js` gains `futureAbsorb(view)` and `untouchedHealerCredit(view)` (= `futureAbsorb ·
  min(1, room/heal)`, 0 for non-healers / maxed healers). (Name the prime helper `futureAbsorb`; keep the old name
  `primeAbsorbCredit` as an alias if convenient.)
- `eval/defense/defense_sim.js`'s `ours`-mode objective becomes the formula above. Only a *truly surviving* prime
  earns `futureAbsorb`; a dying last-blocker (relabeled a chump) earns 0. The untouched-healer term is summed over
  every below-max healer that is **neither chumped nor the prime**.
- **B&B soundness:** the credit is a (board-bounded) negative term, so `defense_sim`'s `negFloor` must bound the
  **best-possible** total credit any branch completion can subtract — both the single best `futureAbsorb(prime)`
  **and** the untouched-healer credits of below-max healers not yet fixed — else pruning can drop a true optimum.
  **Re-validate the modified B&B against the unbounded brute-force oracle** (the prototype oracle in
  `docs/scratch`-style enumeration; ship an oracle cross-check test).
- **`cpp` mode is untouched** — it must stay a faithful `DamageLoss_WillCost` replica so the validation gate still
  passes and the baseline is unaffected. Verify `cpp`-mode `solveDefense` is byte-identical to the pre-change
  output on a battery of boards.

**Finding A — symmetric human credit (`compare.js`), MANDATORY.** The credit lives in `solveDefense` (the AI's
loss); `compare.js` must apply the **same** credits to the *human's* assignment or regret is corrupted (an
identical human defense would score regret 13.2 instead of 0). Subtract `futureAbsorb(human's surviving prime)`
and the room-capped credits of the human's untouched below-max healers from `humanLossOurs`.

**Finding B — tripwire on the chump-loss component.** Post-credit, legitimate min-losses go strongly negative
(−26 … −53 when good anchors survive), so the flat `loss < −0.3` tripwire would fire constantly. Carry the
chump-loss component (`Σ_dead V + primeLoss`, pre-credit) separately and run the value-sanity tripwire on **that**
(it stays ≥ ~0 outside the known doomed-nudge/undef band), not on the post-credit loss.

---

_Superseded original §2 (kept for provenance): a **prime-only** credit subtracted from the surviving prime,
`minimize [ Σ chump-loss − primeAbsorbCredit(surviving prime) ]`. Correct for Wall-vs-Rhino but it over-primed
below-max healers (it lacked the untouched-healer term) and double-counted nothing only because it credited too
little; the revised model above is the converged design._

## 3. Multi-turn heal — two distinct mechanisms

**(a) Chump-loss for healers — discounted climb to max (capped).** Replace the one-heal soak
`min(currentHP + heal, max)` with the full discounted multi-turn climb a kept healer makes:

> `effectiveSoakHP = currentHP + Σ_{t≥1} (heal gained at turn t, cumulative-capped at max) · d^(2t)`;
> value contribution `= effectiveSoakHP · BV`.

Worked: **Xaetron@5** (heal 4, max 12) → `5 + 4·d²(0.75) + 3·d⁴(0.5625) = 9.69` → **21.3** (vs one-heal 19.7).
**Xaetron@2** → `2 + 4·0.75 + 4·0.5625 + 2·0.4219 = 8.1` → **17.8** (vs 13.2). Deeply-damaged healers get the
bigger correction, bounded by `max·BV`. **Lives in** `gen_our_numbers_v2.js` `coreValue` (the `soakHP = min(...)`
line). It is a chump-loss change, so it flows everywhere static `V` is used.

**(b) Prime-absorb perpetual heal — uncapped (the §2 `futureAbsorb`).** A healer *as the prime* sustains
`heal`/turn forever via the `sustainableAbsorb = heal` branch — **not** capped by max, because it's a rate, not a
fill. So a maxed Xaetron is a strong anchor (`heal·BV·(P−1)`) even though its chump-loss soak is "just" `max·BV`.
A healer can carry **both**: a capped climb in its chump-loss AND, if chosen prime, the uncapped perpetual-heal
credit. The **untouched** below-max healer earns the *same* `futureAbsorb` but **room-capped** by
`min(1, room/heal)` (§2) — mirroring this §3a climb cap exactly: both are limited by how much the healer can
actually bank toward max this turn.

## 4. Architecture, acceptance tests, and the report filter

**File map:**

| File | Change |
|---|---|
| `docs/scratch/gen_our_numbers_v2.js` | §1 `R_HALF` + derived `ATK`; §3a healer soak → discounted climb-to-max. Regenerate `our_numbers_v2.md`. |
| `eval/defense/defense_value.js` | new `futureAbsorb(view)` (§2, incl. doomed-finite factor) + `untouchedHealerCredit(view)` (room-capped). |
| `eval/defense/defense_sim.js` | `ours` objective → §2 formula (prime credit + room-capped untouched-healer credit); extend `negFloor` to bound BOTH credits. `cpp` untouched. Oracle cross-check test. |
| `eval/defense/compare.js` | **Finding A:** apply the same credits to the human's assignment (`humanLossOurs`). |
| `eval/defense/metrics.js` | **Finding B:** tripwire on the chump-loss component; §4 report decision-relevance filter on the two diagnostic tables (with healer exception). |
| `eval/defense/*.test.js` | the acceptance cases + regression guards + the existing-test updates below. |

**Acceptance tests** (unit tests on `solveDefense`, `ours` mode; numbers pinned against the prototype — all verified
against the unbounded brute-force oracle):
1. **Wall + ch2-Rhino, 4 dmg → prime Wall, chump Rhino** (headline flip).
2a. **Engineer + 2×Wall + ch2-Rhino, 5 dmg → chump a Wall** (keep Engineer + Rhino — model refuses to over-chump
    the Engineer; the Engineer's 1 HP doesn't spare a Wall).
2b. **Engineer + 2×Wall + ch2-Rhino, 3 dmg → chump the Engineer** (forced chump → sacrifice the spent-econ unit).
3. **EM + 5-life Doomed Mech, 9 dmg → prime Mech** and 4. **EM + 2-life Doomed Mech, 9 dmg → prime EM** — the two
   **differ** (doomed-finite factor).
6. **Wall + Xaetron@3, 2 dmg → prime Wall, Xaetron untouched** (leave the healer to climb).
7. **5 Husk + Wall + Xaetron@8, 7 dmg → chump 5 husks, prime Wall, Xaetron untouched** (climb the healer with a
   throwaway anchor; validated optimal by the 20-turn siege simulation: 50 vs 57 vs 100 husks).
8. **EM + Xaetron@5, 9 dmg → prime Xaetron, chump EM** (keep the higher-V healer; equal future-absorb cancels).
9. **5 Husk + Wall + Xaetron@12, 7 dmg → prime Xaetron** (maxed → dump it; untouched credit 0 at max).
10. **Steelsplitter + Wall, 4 dmg → keep Steelsplitter, chump Wall** (equal sustain → chump-loss decides).
11. **Xaetron@11 + 4×Wall + Husk, 12 dmg → prime Xaetron (dump)** — room-cap: near-maxed healer (room 1 < heal 4)
    is dumped, NOT preserved by over-chumping Walls.
12. **Xaetron@11 + EM + 3×Wall + 3×Husk, 14 dmg → prime EM, Xaetron untouched** — same near-maxed Xaetron, but a
    *big* alternate prime (EM) flips it to "keep the healer topping off" (alternate-prime-size handled automatically).

**Existing tests that MUST be updated** (behavior changes intentionally):
- `defense_value.test.js`: Xaetron heal-climb numbers — body@8 26.3→**24.1**, body@5 19.7→**21.21**; loss Xaetron@3
  absorbs 2 →**2.55**; loss Xaetron@10 absorbs 2 →**1.1**.
- `defense_sim.test.js`: `Wall vs Xaetron@3, 2 dmg` prime flips Wall→ stays **Wall** (was asserting Wall already —
  re-pin loss); `5 Husk + Wall + Xaetron@8, 7 dmg` now **chumps the husks, primes the Wall** (was "keep Xaetron
  untouched, chump husks" — re-assert prime=Wall + Xaetron untouched + new loss).

**Regression guards (must NOT change):**
- Steelsplitter-vs-Wall and EM-vs-Xaetron@5@9 (equal sustain → chump-loss keeps the higher-V unit).
- `value_model.test.js` units unchanged (Wall 6.6, EM 11, Husk 2.2, IG 8.9, Photonic 4.6, Doomwall 8.7 — the ATK
  change doesn't touch pure blockers / token-sac units).
- The `cpp` validation gate (`solveDefense` `cpp` mode byte-identical; gate still 1234/1235).

**Report decision-relevance filter (`metrics.js`):** exclude a position from the **divergence** and
**tie-break-skew** tables when `incoming ≤ max_unit(survivable absorb) + Σ(lifespan-1 HP)` — no real unit must die,
so the prime choice is cosmetic — **except keep any position where the prime (human's OR ours') is a healer**
(the perpetual-heal credit makes the choice consequential and we need to verify healer-prime selection). The
headline regret / zero-regret / exact-match counts stay over the **full** corpus; only the two diagnostic tables
get the filter.

**Validation:** re-run `node eval/defense/compare.js <codes> <out>`, regenerate `report.md`. Success = the Wall
over-chump and Rhino under-chump divergences **shrink**, and zero-regret **rises** above the corrected baseline
(82.7%), with the regression guards and the `cpp` gate unchanged.

## 5. Out of scope (deferred)

- The **C++ port** of all three changes into `Heuristics` (after the JS model is validated against the human data).
- **Global R / future-flow tuning** (e.g. a defense-context discount on economy/attack) — its own pass, after this.
- Per-unit "fudge" corrections — only the principled changes above; chase aggregate regret, not per-unit perfection
  (Prismata's efficiency curve is intentionally uneven).
