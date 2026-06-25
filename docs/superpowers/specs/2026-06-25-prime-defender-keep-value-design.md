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

## 2. The prime-defender keep-value term

A new term, **prime-only** and **absorb-only** (an attacker's future attacks are already in chump-loss `V`; a
non-prime surviving blocker is, by the model's same-prime-reused assumption, just a one-soak again):

> **`primeAbsorbCredit(unit) = sustainableAbsorb · BV · factor`**
>
> `sustainableAbsorb =`
> - **`HP − 1`** — non-fragile (absorbs HP−1, survives on 1, repairs to full next turn).
> - **`heal`** — fragile healer (absorbs `heal`, heals it back; **uncapped** — a sustained rate, not a fill).
> - **`0`** — fragile non-healer (can't sustain → no anchor value).
>
> `factor =`
> - **`P − 1 = 3`** — permanent unit. (The `−1` is the 2-half-turn discount: this turn's absorb is free because
>   the prime survives — `loss 0` already — so the credit is only the *future* perpetual absorb, whose first term
>   is the next defense phase, 2 half-turns out. `P·d² = 4·0.75 = 3 = P−1`.)
> - **`Σ_{k=1}^{life−1} d^(2k)`** — doomed unit with `life` turns left (it anchors finitely, then expires): 0.75
>   at life 2, 2.05 at life 5, → 3 as life → ∞.

By construction `sustainableAbsorb` makes Xaetron(heal 4) == Energy-Matrix(HP−1 = 4) — equal credit, so which of
*those* to keep falls to chump-loss.

**Where it enters — the eval sim's objective, `ours` mode ONLY:**
- `eval/defense/defense_value.js` gains `primeAbsorbCredit(unit)`.
- `eval/defense/defense_sim.js`'s `ours`-mode objective changes from `minimize Σ loss` to
  **`minimize [ Σ chump-loss − primeAbsorbCredit(the surviving prime) ]`**. Only a *truly surviving* prime earns
  it — a dying last-blocker (relabeled a chump) does not; chumps and untouched spares earn nothing (the prime-only
  restriction that keeps the magnitude bounded).
- **`cpp` mode is untouched** — it must stay a faithful `DamageLoss_WillCost` replica so the validation gate still
  passes and the baseline is unaffected. This is purely an `ours`-heuristic change.
- The credit is a *bounded negative* term on the chosen prime, so `defense_sim`'s branch-and-bound `negFloor`
  bound must include the **best-possible** `primeAbsorbCredit` among remaining candidates so it can never prune a
  true optimum.

The credit differentiates primes only when `sustainableAbsorb·factor` differs: it flips Wall(2)-vs-Rhino(1) and
the 5-life-vs-2-life Doomed Mech; it *cancels* for equal sustain (Steelsplitter(2)-vs-Wall(2),
EM(4)-vs-Xaetron(4)) → chump-loss decides, unchanged.

## 3. Multi-turn heal — two distinct mechanisms

**(a) Chump-loss for healers — discounted climb to max (capped).** Replace the one-heal soak
`min(currentHP + heal, max)` with the full discounted multi-turn climb a kept healer makes:

> `effectiveSoakHP = currentHP + Σ_{t≥1} (heal gained at turn t, cumulative-capped at max) · d^(2t)`;
> value contribution `= effectiveSoakHP · BV`.

Worked: **Xaetron@5** (heal 4, max 12) → `5 + 4·d²(0.75) + 3·d⁴(0.5625) = 9.69` → **21.3** (vs one-heal 19.7).
**Xaetron@2** → `2 + 4·0.75 + 4·0.5625 + 2·0.4219 = 8.1` → **17.8** (vs 13.2). Deeply-damaged healers get the
bigger correction, bounded by `max·BV`. **Lives in** `gen_our_numbers_v2.js` `coreValue` (the `soakHP = min(...)`
line). It is a chump-loss change, so it flows everywhere static `V` is used.

**(b) Prime-absorb perpetual heal — uncapped (already in §2).** A healer *as the prime* sustains `heal`/turn
forever via the `sustainableAbsorb = heal` branch — **not** capped by max, because it's a rate, not a fill. So a
maxed Xaetron is a strong anchor (`heal·BV·(P−1)`) even though its chump-loss soak is "just" `max·BV`. A healer
can carry **both**: a capped climb in its chump-loss AND, if chosen prime, the uncapped perpetual-heal credit.

## 4. Architecture, acceptance tests, and the report filter

**File map:**

| File | Change |
|---|---|
| `docs/scratch/gen_our_numbers_v2.js` | §1 `R_HALF` + derived `ATK`; §3a healer soak → discounted climb-to-max. Regenerate `our_numbers_v2.md`. |
| `eval/defense/defense_value.js` | new `primeAbsorbCredit(unit)` (§2 formula incl. the doomed-finite factor). |
| `eval/defense/defense_sim.js` | `ours` objective → `min[Σ chump-loss − primeAbsorbCredit(surviving prime)]`; extend `negFloor` to include the best-possible credit. `cpp` untouched. |
| `eval/defense/metrics.js` | §4 report decision-relevance filter on the two diagnostic tables (with healer exception). |
| `eval/defense/*.test.js` | the four acceptance cases + regression guards. |

**Acceptance tests** (unit tests on `solveDefense`, `ours` mode; exact numbers pinned at implementation after the
`ATK` change):
1. **Wall + ch2-Rhino, 4 dmg → keep the Wall as prime, chump the Rhino** (the headline flip).
2. **Engineer + 2×Wall + ch2-Rhino, 5 dmg → chump the Engineer**, keep the rest.
3. **EM + 5-life Doomed Mech, 9 dmg** and 4. **EM + 2-life Doomed Mech, 9 dmg** → the two outcomes **must
   differ**: the long-lived Mech is kept more readily as anchor than the short-lived one (the doomed-finite factor).

**Regression guards (must NOT change):**
- Steelsplitter-vs-Wall (equal sustain → chump-loss keeps the Steelsplitter).
- EM-vs-Xaetron@5 (equal sustain → chump-loss keeps the Xaetron).
- The `cpp` validation gate (still 1234/1235) and the value-sanity tripwire (still clean).

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
