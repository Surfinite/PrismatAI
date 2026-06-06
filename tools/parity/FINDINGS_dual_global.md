# 14-AND-15-global model load support + dual PyTorch↔C++ value-parity — PASS

**Date:** 2026-06-06. Follows `FINDINGS_35prop.md` (35-prop, 14-global) and the v2.2 schema work
(`docs/dsnn-feature-schema.md`). Task A of `docs/superpowers/plans/2026-06-06-v22-rl-prep-continuation.md`.

## Problem

The v2.2 engine (`2346963`, +`under_attack` 15th global) hardcoded `num_global = 15` in three
load-bearing spots (`COMBINED` in `allocateScratchBuffers` + `evaluateValue`, and the
`dumpFeaturesJSON` globals loop). It could therefore load **only** 15-global (valhead 303) weights;
a 14-global (schema ≤v2.1, e.g. `neural_weights_mixed_35prop.bin`, valhead 302) `.bin` mis-built the
combined vector and the dump loop read one float past the 302-wide buffer — so `DSNN_Mixed35_*`
players and the non-gating narrow yardstick could not run on the v2.2 build.

## Fix (one build loads both)

`num_global` is now **derived from the value head's input width at load**, mirroring how
`num_properties` is header-driven:

```
num_global = val_linear1.in_dim − (encoder_hidden*2 + supply_hidden)        # NeuralNet.cpp loadWeights
COMBINED   = encoder_hidden*2 + supply_hidden + num_global                   # was "+ 15"
```

`val_linear1.in_dim` comes straight from the loaded `value_head.0.weight` shape (`shape[1]`), so it is
authoritative. The 14 base globals (p0/p1 resources+attack, turn, active_player) are emitted
unconditionally; the 15th (`under_attack`) is emitted **only `if (num_global >= 15)`**, so a 14-global
model sees the exact 302-wide vector it was trained on. `num_global` is stored on `DeepSetsConfig`
(set before `allocateScratchBuffers`; copied by the copy-ctor). **Scope:** this makes the engine load
either count; a *new* 16th global would still need hand-written C++ to construct it (only the count is
auto-derived, not the per-global formula).

Diff: `source/ai/NeuralNet.cpp` + `source/ai/NeuralNet.h`. Adversarially reviewed (init-ordering,
buffer sizing, the `>=15` guard, the dump off-by-one, the derivation formula) — no correctness bugs.

## Verdict — dual parity PASS

Engine load diagnostic now prints `num_global=15 (v2.2 +under_attack)` / `num_global=14 (base)`;
`dropped=0` on all states for both. Both generations tie out to PyTorch well under the 1e-3 value tol:

```
CASE 1 — v22 (15-global, valhead 303)   .pt=deepsets_mixed_v22/swa_model.pt  .bin=neural_weights_mixed_v22.bin
state                            N    val_cpp  val_torch    |dval|   verdict
out v22 state_01_turn1          19   0.074795   0.074795   6.27e-09   PASS
out v22 state_02_constr_damage  94   1.000000   1.000000   1.13e-07   PASS
out v22 state_03_charges_life   47  -0.968062  -0.968062   2.21e-07   PASS
out v22 state_04_high_resources 39  -0.463540  -0.463540   1.57e-07   PASS
out v22 state_05_late_large    121   1.000000   1.000000   0.00e+00   PASS
worst |value_cpp - value_torch| = 2.21e-07

CASE 2 — 35prop (14-global, valhead 302)  .pt=deepsets_mixed_35prop/best_model.pt  .bin=docs/scratch/deepsets_mixed_35prop.bin
state                            N    val_cpp  |cpp-torch| |cpp-numpy|  verdict
out35int state_01_turn1         19  -0.032990   1.75e-08    6.96e-08    PASS
out35int state_02_constr_damage 94   1.000000   4.44e-10    4.44e-10    PASS
out35int state_03_charges_life  47  -0.995892   1.46e-08    8.78e-09    PASS
out35int state_04_high_resources39  -0.892601   2.02e-08    7.67e-08    PASS
out35int state_05_late_large   121   1.000000   0.00e+00    0.00e+00    PASS
worst |value_cpp - value_torch| = 2.02e-08 ; worst |value_cpp - value_numpy| = 7.67e-08
```

The 14-global logits are **byte-identical to the pre-change `FINDINGS_35prop.md` baseline** (e.g.
state_02 22.229, state_05 49.481) — the fix does not perturb the 14-global numeric path; it only stops
emitting the (non-existent) 15th global. The 2.02e-08 worst matches the original 35-prop audit exactly.

## Reproduce

```bash
# Refresh the deploy copy from the freshly built standalone, then dump both generations:
cd c:/libraries/PrismataAI-dave-master/bin
cp Prismata_Standalone.exe PrismataAI.exe
for s in 01_turn1 02_constr_damage 03_charges_lifespan 04_high_resources 05_late_large; do
  ./PrismataAI.exe --dump-features ../tools/parity/states/state_${s}.json ../tools/parity/outv22_state_${s}.json  asset/config/neural_weights_mixed_v22.bin
  ./PrismataAI.exe --dump-features ../tools/parity/states/state_${s}.json ../tools/parity/out35int_state_${s}.json C:/libraries/PrismataAI/docs/scratch/deepsets_mixed_35prop.bin
done
cd c:/libraries/PrismataAI-dave-master/tools/parity
# CASE 1 (15-global):
python compare_parity_deepsets.py outv22_state_*.json \
  --pt C:/libraries/PrismataAI/training/models/deepsets_mixed_v22/swa_model.pt \
  --bin C:/libraries/PrismataAI-dave-master/bin/asset/config/neural_weights_mixed_v22.bin
# CASE 2 (14-global) — defaults point at the 35prop interim pair; no flags, no hand-patch:
python compare_parity_deepsets.py out35int_state_*.json
```

## Tooling: harness now first-class for both generations (RESOLVED)

The harness used to depend on `PrismataDeepSets()` defaults, which v2.2 bumped to 37-prop/15-global, so
it could no longer construct a 14-global reference model. Fixed in the follow-up commit:
- **`model_deepsets.py`** — added a `num_global` ctor param (default 15); `value_input_dim` is now
  `enc_h*2 + sup_h + num_global` (was a hardcoded `+15`). Backward-compatible.
- **`compare_parity_deepsets.py`** (renamed from `compare_parity_35prop.py`) — `load_model` now
  **infers** the full architecture (num_units, d_embed, num_properties, hidden dims, num_global) from the
  checkpoint's saved tensor shapes, so it builds the right model for ANY generation with no flags. Both
  CASE 1 (15-global) and CASE 2 (14-global, defaults) PASS through the tool with **no hand-patching**.

The numpy-over-`.bin` oracle (`export_weights_v2.numpy_forward`) was already generation-agnostic.

**Pre-existing test debt — RESOLVED (main@721d836):** `training/tests/test_model_deepsets.py` fed
14-global inputs (`make_batch(globals_dim=14)` + two inline `torch.rand(1,14)`) against the now-15-global
default model → 7/10 failed on HEAD (proven pre-existing, not caused by the parameterization). Fixed by
deriving the globals width from `model._num_global` at each call site (schema-agnostic; `under_attack` is
invariant under the mirror test's player-swap), `make_batch` default 14→15. **10/10 pass.**
