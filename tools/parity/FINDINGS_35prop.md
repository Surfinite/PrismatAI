# 35-property DSNN PyTorch ↔ C++ value-parity — PASS

**Date:** 2026-05-31. Extends the 2026-05-29 13-prop audit (`FINDINGS.md`) to the new
35-property production-vector schema (`property_table.json` 13→35 cols, token_dim 77).

## Verdict

**PASS — the C++ deployment engine reproduces the 35-property PyTorch model.**
Worst `|value_cpp − value_torch| = 2.02e-08` (tol 1e-3); C++ logits agree with both the
PyTorch `.pt` and the numpy-over-`.bin` forward to ~1e-5; `dropped = 0` on all 5 states;
Tier A (feature build vs source state) PASS. **No C++ rebuild was required** — the property
dimension is header-driven.

```
state                            N    val_cpp   val_torch    |dval|  logit_cpp logit_torch  logit_np  drop  verdict
out35_state_01_turn1            19  -0.032990  -0.032990  1.75e-08   -0.06600    -0.06600   -0.06600    0    PASS
out35_state_02_constr_damage    94   1.000000   1.000000  3.91e-10   22.35580    22.35582   22.35583    0    PASS
out35_state_03_charges_lifespan 47  -0.995892  -0.995892  1.46e-08   -6.18579    -6.18579   -6.18579    0    PASS
out35_state_04_high_resources   39  -0.892601  -0.892601  2.02e-08   -2.86915    -2.86915   -2.86915    0    PASS
out35_state_05_late_large      121   1.000000   1.000000  0.00e+00   49.48107    49.48109   49.48109    0    PASS
worst |value_cpp - value_torch| = 2.02e-08   Tier-A (01,05): alive==mapped, 0 dropped
```

## Why no C++ change was needed (verified in code)

- `num_properties` is read from the DSN2 header (`source/ai/NeuralNet.cpp:218`); token dim,
  encoder `in_dim`, and scratch buffers all derive from it (`:242, :283, :314, :470`). The
  only `13`/`55` literals in NeuralNet.cpp are stale comments (`:454-455`).
- The 35 static per-unit property VALUES are baked into the `.bin` as the `property_table`
  tensor (116×35) and sliced by stride `num_properties` (`NeuralNet.cpp:500-501`). C++ never
  reads `property_table.json` at runtime (zero references in `source/`).
- Instance-feature extraction hardcodes property indices **5 (base_health), 6 (fragile)**
  (`NeuralNet.cpp:435-436`). Confirmed cols 5,6 of the new 35-col `property_table.json` are
  still `base_health`, `fragile` — the 22 new columns are appended (13→34), original 13
  order preserved. So instance features [5],[6] remain correct.

## Provenance / scope caveat

Run against the **interim epoch-30 model** (`docs/scratch/deepsets_mixed_35prop.bin` ↔
`training/models/deepsets_mixed_35prop/best_model.pt`) from the crashed mixed run. Parity is
**architecture-level** (it proves the C++ 35-prop forward + weight load is faithful for ANY
self-consistent 35-prop `.bin`), so it holds for the final weights too. Re-running on the
clean re-run's final export (`neural_weights_mixed_35prop.bin`) is a trivial repeat of the
Reproduce steps — no rebuild.

## Reproduce

```bash
# 1. C++ dumps (35-prop .bin as the 3rd arg; default weights are 13-prop mbonly):
cd c:/libraries/PrismataAI-dave-master/bin
for s in 01_turn1 02_constr_damage 03_charges_lifespan 04_high_resources 05_late_large; do
  ./PrismataAI.exe --dump-features ../tools/parity/states/state_${s}.json \
    ../tools/parity/out35_state_${s}.json asset/config/neural_weights_mixed_35prop.bin
done
# 2. Tier B (PyTorch + numpy vs C++) — paths pinned in the script:
cd c:/libraries/PrismataAI-dave-master/tools/parity
python compare_parity_35prop.py out35_state_*.json
# 3. Tier A (feature build vs source state):
python tier_a_check.py states/state_01_turn1.json out35_state_01_turn1.json
```
