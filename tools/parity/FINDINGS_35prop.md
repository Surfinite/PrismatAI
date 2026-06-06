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

## Loader allow-list fix (`dominionNames`) — 2026-05-31

Running this surfaced a soft-assert on `state_02`: `CardType::getCardType() error: Card name
not found: Mega Drone`. Root cause: the `--dump-features` hook loads cards via
`CardTypeData::InitFromCardLibraryFile` (the GUI/testing path), which admits a `.jso` entry
only if it's base-set or in a hardcoded `dominionNames[]` allow-list. That list was frozen
when the engine was open-sourced and never updated, so it silently dropped **12 ranked units
added since**: Arms Race, Bombarder, Colossus, Innervi Field, Manticore, Mega Drone, Mobile
Animus, Oxide Mixer, Photonic Fibroid, Tyranno Smorcus, Urban Sentry, Valkyrion. The real AI
path (`InitFromMergedDeckJSON`, used by matchup/self-play from the request's `mergedDeck`) was
never affected.

`dominionNames[]` matches the `.jso` **key = internal engine name** (e.g. Husk's key is
`"House"`; the literal `"Husk"` in the list is a dead no-op). All 12 missing units have
internal == display name, so they were added verbatim to `CardTypeData.cpp`. After an
incremental GUI-off rebuild (`Prismata_Standalone`, Release/x64), the miss is gone, `state_02`
now feeds Mega Drone's supply (idx 71) to the NN, and parity re-confirms **ALL PASS** (worst
2.02e-08; `state_02` logit 22.356 → 22.229 as the now-complete supply changes the input, with
C++ == PyTorch to 4.4e-10). `out35_state_02_constr_damage.json` regenerated post-fix.

## Final weights (SWA, 2026-06-01) — re-verified, deployment-faithful

The clean 100-epoch re-run completed with **no crash** (XPU `reserved` flat at 346 MB for
all 100 epochs — the per-epoch `empty_cache` fix held; `allocated` flat at 4 MB rules out a
leak). Best val_loss 0.3465 @ ep98; **SWA 0.3464 / 81.7% acc / brier 0.1166**. The SWA model
was exported to `bin/asset/config/neural_weights_mixed_35prop.bin`.

Re-ran this harness on the **final SWA weights** (`final35_state_*.json`,
`compare_parity_deepsets.py --pt …/deepsets_mixed_35prop_v2/swa_model.pt --bin …/neural_weights_mixed_35prop.bin`):
**ALL PASS**, worst `|value_cpp − value_torch| = 5.84e-07`; C++ == PyTorch == numpy to ~1e-6;
0 dropped; no card-not-found (the `dominionNames` fix holds). The shipped engine reproduces
the shipped model.

Note on the exporter round-trip: `export_weights_v2.py`'s synthetic *random* case "FAILED"
its absolute `tol=1e-4` at diff 8.5e-4 — but that case feeds `randn` noise yielding an
out-of-distribution logit ≈1793, where 8.5e-4 is ~5e-7 **relative** (float32 rounding), not a
weight error (the all-zeros case passed at 1.5e-8). On real states logits are ~[−6, 46] and
parity is <6e-7, so the real-state parity here is authoritative. `compare_parity_deepsets.py`
now takes optional `--pt`/`--bin` so it serves both interim and final references.

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
python compare_parity_deepsets.py out35_state_*.json
# 3. Tier A (feature build vs source state):
python tier_a_check.py states/state_01_turn1.json out35_state_01_turn1.json
```
