# DSNN Feature Schema (DeepSets) — authoritative reference

The input contract for the DeepSets value net (`PrismataDeepSets`). This is the single prose
home for "what the model sees"; the machine-readable source of truth is
[`training/schema_v2.json`](../training/schema_v2.json) + [`training/property_table.json`](../training/property_table.json).

- **`schema_version`: `v2`** — the *architecture generation* (DeepSets per-instance tokens, vs the
  legacy flat `PNET` / `state_dim=1785`). It does **not** bump for additive feature columns.
- **`feature_revision`: `v2.2`** — the *feature-set* revision (see Changelog). The de-facto
  machine version is the dims (`token_dim` / `num_static_properties` / `num_global_features`) +
  `unit_index_hash`, all carried in `schema_v2.json` and mirrored in the DSN2 `.bin` header, and
  checked by the parity harness. There is **no DSNN "v3"** — that would overstate an additive change.

## Token layout

Each alive table instance becomes one token; tokens are sum-pooled per player (DeepSets).

```
token = [ unit_embedding(32) | static_properties(37) | instance_state(10) ]   = token_dim 79
```

- **`unit_embedding`** — a learned 32-d embedding per unit type (116 units, `unit_index.json`).
- **`static_properties` (37)** — per-unit-TYPE constants from `property_table.json` (NOT in the H5;
  applied at model time via the property-table buffer, indexed by unit id). Baked into the `.bin`.
- **`instance_state` (10)** — per-INSTANCE live state, in the H5 / computed in C++ at inference:
  `owner, is_constructing, turns_until_ready, is_blocking, ability_used, current_hp, hp_fraction,
  is_frozen, lifespan_remaining, stamina_remaining`.

Two side pathways feed the value head alongside the pooled tokens:
- **`supply` (116 × 3)** — `[p0_supply, p1_supply, in_card_set]` per unit type → supply encoder.
- **`globals` (15)** — per-STATE features (below), in the H5 / computed in C++.

Value head input = `p0_pool(128) | p1_pool(128) | supply_pool(32) | globals(15)` = **303**.

## The 37 static properties (`property_table.json`)

Sourced from `cardLibrary.jso`. Generator: `docs/scratch/resource_conversions/build_feature_table.py`
(+ `apply_props_v2_2.py` for the v2.2 split/frontline). Mana codes: bare digits/int = gold,
`G`=green, `B`=blue, `C`=red, `H`=energy, `A`=attack.

| Group | Properties |
|---|---|
| Buy cost | `buy_cost_{gold,green,blue,red,energy}` |
| Stats | `base_health, fragile, default_blocking, base_build_time, base_lifespan, has_ability, max_stamina` |
| **Attack (v2.2 split)** | **`auto_attack`** (beginOwnTurnScript.receive A-count, guaranteed each turn), **`click_attack`** (abilityScript.receive A-count, optional). Replaces the old conflated `base_attack` (== auto+click, verified for all 116). |
| Production (auto) | `auto_{gold,green,blue,red,energy}` (beginOwnTurnScript.receive) |
| Production (click) | `click_{gold,green,blue,red,energy}` (abilityScript.receive) |
| Chill | `chill_amount` (targetAmount when targetAction==disrupt) |
| Click cost | `click_cost_{gold,green,blue,red,energy}, click_cost_hp` (abilityCost / HPUsed) |
| Sac / self-sac | `click_selfsac, auto_selfsac, click_sac_units` (abilitySac), `buy_sac_units` (buySac) |
| Regen | `hp_regen` (HPGained) |
| **Frontline (v2.2)** | **`frontline`** = 1 if the unit is `undefendable` — the game's **Frontline** keyword (the attacker may direct damage onto it rather than the defender choosing what dies). Engine-load-bearing: the AI's own defense/breach solver branches on `CardType::isFrontline()` (`AvoidBreachBuyIterator`, `FrontlineGreedyKnapsack`). 7 units: Wild/Galvani Drone, Shredder, Polywall, Thunderhead, Iceblade Golem, Hannibull. |

**Deliberately NOT featurized (Tier 3 — left to the board + embedding):** `create` (unit spawning —
value flips with owner; 5+ units create *for the opponent*, e.g. Valkyrion/Blood Pact/Redeemer/Arms
Race; created units appear on the board anyway), `destroy`/snipe/netherfy (conditional),
`needs` (prerequisites), `resonate`/`goldResonate` (board-conditional production; 4 units —
Savior/Resophore/Amporilla/Antima Comet). Rationale: see
`docs/scratch/resource_conversions/PHASE_AB_FEATURE_PLAN.md`. Candidate presence-bits
(`creates_units`/`destroys_units`) are deferred to the **O6 candidate policy head**, where they
discriminate move candidates (a clean re-architecture boundary, so no warm-start cost to adding them then).

## The 15 global features (`globals`)

Order (must match `vectorize_v2.py::vectorize_globals` AND `NeuralNet.cpp`):

```
p0_{gold,blue,red,green,energy,attack}, p1_{gold,blue,red,green,energy,attack},
turn_number, active_player, under_attack
```

- Resources/attack are clamp-normalized (`normalization_caps` in `schema_v2.json`).
- **`under_attack` (v2.2)** — 1 if the **active player faces incoming attack** (the opponent's
  attack > 0), else 0. Binary, unnormalized. Disambiguates the mixed turn-start snapshot: ~50% of
  training snapshots are pre-swoosh **Defense** states (R/B/E not yet generated = 0 — looks like a
  depleted Action state); `under_attack` tells the net which it is. Derived from existing fields
  (`p0_attack`/`p1_attack`/`active_player`), so it required **re-vectorize, not re-extraction**. See
  `project_mb_full_replays_snapshot_normalization` memory (status quo is train==inference consistent;
  this flag is the cheap representational fix, normalization deferred).

## File contract (where each piece lives)

| File | Holds |
|---|---|
| `training/schema_v2.json` | dims, feature lists, `feature_revision`, normalization caps (machine source of truth) |
| `training/property_table.json` | the 37 static props per unit (baked into the `.bin`) |
| `training/vectorize_v2.py` | builds the 15-d `globals` (+ instance/supply) into the H5 |
| `training/model_deepsets.py` | `PrismataDeepSets` (`num_properties=37`, value head 303, token 79) |
| `training/export_weights_v2.py` | PyTorch → DSN2 `.bin`; self-check derives `num_global` from the value-head width |
| `PrismataAI-dave-master/source/ai/NeuralNet.cpp` | C++ inference: builds the 15 globals (incl. `under_attack`) per-state; static props read from the `.bin` header (no per-prop C++ edit) |

**Parity:** the DSN2 header is dim-driven, so the static-prop count flows automatically; only the
`globals` construction is hand-written in both Python and C++ and must stay in lockstep. Verified for
v2.2: dump-features → `under_attack`=1 (defense) / 0 (action); export self-check numpy==pytorch (2e-7).

## Changelog

| feature_revision | date | dims (static / global / token / valhead) | change |
|---|---|---|---|
| v2.0 | 2026-05 | 13 / 14 / 55 / 302 | initial DeepSets per-instance schema |
| v2.1 | 2026-05-31 | 35 / 14 / 77 / 302 | +22 production-vector props (auto/click split, chill, costs, sac/selfsac, regen) |
| **v2.2** | **2026-06-05/06** | **37 / 15 / 79 / 303** | `base_attack`→`auto_attack`+`click_attack`; +`frontline`; +`under_attack` global |

v2.2 retrain (mixed: fleet_v3_v2+fleet_v4_v2+human_1800_v2, val local_mbvmb_v2, 100ep SWA@80, XPU)
tracks the `mixed_35prop` baseline near-identically (clean A/B: same data/seed/recipe) — val loss a
hair lower in ~60/77 epochs, accuracy a wash. Expected: the MB-flavoured val can't measure the
production-vector payoff (MB never plays the ~14 ability-rich units); the payoff target is RL +
the tactical/strength evals.
