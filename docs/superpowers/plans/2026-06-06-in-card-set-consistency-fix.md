# PROMPT: fix `in_card_set` (and audit ALL) train/inference feature consistency → retrain

> Paste this into a fresh session. SEPARATE track from the v2.2 RL-prep handoff
> (`2026-06-06-v22-rl-prep-continuation.md`) — don't collide on its files. Two repos:
> main `c:/libraries/PrismataAI` (`feature/production-vectors`), engine
> `c:/libraries/PrismataAI-dave-master` (`dave-master-jsonclean`). Verify both branches before any commit.

## The bug (confirmed this session)
The DSNN supply feature `in_card_set` (3rd of `[p0_supply, p1_supply, in_card_set]`) is computed with
**inconsistent conventions** across the corpora used to train `neural_weights_mixed_v22.bin` (and the
35-prop model):

| source | `in_card_set` | matches inference? |
|---|---|---|
| **C++ inference** `NeuralNet.cpp:581-591` (iterates `numCardsBuyable()`, sets 1 for ALL incl. base) | base+advanced | — |
| MB train (`matchup_clean.js:1402` passes `config.cardSet` = full deck) | base+advanced | ✓ |
| Human train (`extract_training_jsengine.js` passes `buildAdvancedCardSet`) | advanced-only | ✗ |
| C++ self-play exporter `V2Record.cpp:153` (`!isBaseSet()?1:0`) | advanced-only | ✗ |

**DECISION (user-approved): standardize on `base+advanced` = the C++ inference convention** (all buyable
units, base included, get `in_card_set=1`). Base units are always buyable so the flag is low-information,
but it MUST be consistent train↔inference. (Note `matchup_clean.js:2790` builds an advanced-only set but
:1402 extracts with the full deck — confirm that latent inconsistency isn't biting.)

> **Convention precision (critical — see Task 1):** the correct set is **`base + advanced randomizer,
> CREATED-TOKENS EXCLUDED`** = exactly `numCardsBuyable()` (Husk, Gauss Charge, etc. are NOT buyable and
> must NOT be marked `in_card_set=1`). Do NOT use the full `mergedDeck` (it pulls tokens in → a new,
> opposite-direction skew). `V2Record.cpp:153 → inSet=1` is correct because its loop is already over
> `numCardsBuyable()` (tokens already excluded). The JS extractor must build the same buyable set.
>
> **Why consistency, not removal:** `in_card_set` is low-information (base units are always buyable),
> so dropping it is defensible — but that's a 116×3→116×2 schema change + bigger retrain. We choose
> *unify the convention* (keep the flag) as the minimal, pragmatic fix.
>
> **MB already confirmed (this session, 2026-06-06):** `fleet_v3_v2`, `fleet_v4_v2`, AND `local_mbvmb_v2`
> all mark `in_card_set` = base+advanced (~19, base included) — they MATCH inference, so **no MB
> re-extraction for `in_card_set`** (keep the ~88 GB `masterbot_fleet*` replays untouched). Task 3's
> broader sweep must still check MB for the OTHER feature groups.

## Tasks
1. **Fix the human JS extractor.** In `js_engine/extract_training_jsengine.js`, replace `buildAdvancedCardSet`
   with a **`buildBuyableCardSet` = base + advanced randomizer, CREATED-TOKENS EXCLUDED** (== the set
   `numCardsBuyable()` would yield). Do NOT naively use the full `mergedDeck` (it includes created tokens
   like Husk/Gauss Charge → over-marks → a new opposite-direction skew). Verify `training_example.js:48`
   then marks base units `in_card_set=1` AND tokens `0`.
   - **Cheap insurance:** `buildAdvancedCardSet`'s comment falsely claims it "matches MB's config.cardSet
     semantics." Spend 2 min understanding WHY it went advanced-only (was there an earlier intent before a
     flip?) — the decision is base+advanced regardless, but it guards against a third hidden assumption.
2. **Fix the C++ self-play exporter.** `PrismataAI-dave-master/source/ai/V2Record.cpp:153`:
   `const int inSet = (!ct.isBaseSet()) ? 1 : 0;` → `const int inSet = 1;` (loop is already over
   `numCardsBuyable()`, so this = base+advanced, matching inference). Rebuild dave (x64/v145, both
   targets). Run an `RL_SelfPlay` self-play smoke with `exportTrainingV2` → confirm a record's `supply`
   now marks base units (Drone/Engineer/…) `in_card_set=1`.
3. **THOROUGH train↔inference consistency audit (the "never again" part).** For EVERY feature group —
   `static_properties` (37), `instance_features` (10), `supply` (3 incl. supply REMAINING semantics, not
   just in_card_set), `globals` (15) — verify the FOUR producers compute it identically: the human JS
   extractor (`training_example.js`/`state_adapter.js`), the MB extractor (`matchup_clean.js`), the C++
   self-play exporter (`V2Record.cpp`), and **C++ inference** (`NeuralNet.cpp` ~470-635). The decisive
   check: take ≥3 shared states, run the JS extractor AND `PrismataAI.exe --dump-features` on each, and
   **diff the resulting feature vectors element-by-element** (instances sorted, supply dict, globals) —
   any divergence is a latent skew like this one. (Ultracode: a Workflow fanning out one verifier per
   feature group + an adversarial "find a state that diverges" agent is a good fit here.) Produce a
   per-feature consistency table; fix any other divergence found before retraining.
4. **Re-extract BOTH affected human corpora (train AND val).** With the fixed extractor:
   - **Train:** `final_training_codes_1800.txt` → `human_1800_v2.jsonl` → `vectorize_v2.py` → `human_1800_v2.h5`.
   - **Val (do NOT skip):** `human_val_1700_json.txt` → `human_val_1700_v2.jsonl` → `human_val_1700_v2.h5`.
     The val was rebuilt 2026-06-06 but is still **advanced-only** (`card_set≈8.2`); measuring a base+advanced
     model on an advanced-only val is itself a skew. Re-extract it in the SAME step. (Both auto-emit 15-global/v2.2.)
   - **MB:** for `in_card_set`, MB is ALREADY base+advanced (confirmed `fleet_v3_v2`/`fleet_v4_v2`/`local_mbvmb_v2`)
     → **no MB re-extraction.** Task 3's sweep still checks MB for the other feature groups; only re-extract MB
     if THAT finds a divergence (full per-click replays exist: `masterbot_fleet_v3/replays/`).
   - **Sanity after:** new `human_1800_v2.h5` + `human_val_1700_v2.h5` should both show `card_set≈19` /
     base-in-set (matching MB + inference), NOT 8.
5. **Retrain on fully-matching data.** Recipe as v2.2 BUT **switch the `--val-file` to the human val**
   (deliberate change — `train.py` takes a SINGLE `--val-file` that drives early-stopping/SWA selection;
   the MB val `local_mbvmb_v2` structurally CANNOT see the production-vector / ability-rich-unit payoff,
   the human val can). Report the MB val as a **secondary post-train** number (separate eval pass), not the
   selection criterion:
   `--train-file data/fleet_v3_v2.h5 --extra-train-files data/fleet_v4_v2.h5 data/human_1800_v2.h5
   --val-file data/human_val_1700_v2.h5 --property-table property_table.json --streaming --epochs 100
   --batch-size 512 --lr 3e-4 --patience 100 --label-strategy A --device xpu` (num-workers default 2 —
   do NOT use 4, RAM crash). The human val is disjoint from `human_1800` train (verified, 0 overlap).
   Export SWA → `.bin` → **full C++↔PyTorch parity**
   (`compare_parity_deepsets.py <dumps> --pt swa_model.pt --bin <new.bin>`, worst |Δ|<1e-3). Bump
   `feature_revision` to e.g. `v2.2.1` (schema unchanged; data-consistency fix). Commit the `.bin` in MAIN
   `bin/asset/config/` (tracked) + working copy to dave-master. Re-point `RL_SelfPlay`/`RL_Eval`/
   `RL_Eval_iter0` → the new `.bin`. This supersedes `neural_weights_mixed_v22.bin` as the RL init.
6. **Final verification.** Confirm the post-fix corpus stats show human AND MB both base+advanced; re-run
   the JS↔C++ dump-features parity on a shared state and confirm `in_card_set` (and all features) agree
   end-to-end. Note the supersession in `docs/dsnn-feature-schema.md` changelog.

## Task 7 (FIRST-CLASS — the durable outcome; do it, don't defer)
Add a committed **three-way feature-parity test** (`training/tests/` or `eval/`): on ≥3 fixed shared states,
assert that **(a) the human JS extractor, (b) the C++ self-play exporter, AND (c) C++ INFERENCE
(`--dump-features`)** all produce the same feature vectors (static/instance/supply/globals) within
integer/1e-6 tolerance. The existing `test_selfplay_export_parity.py` only covers C++↔JS-extractor —
**the missing leg is vs C++ INFERENCE, which is the exact side that bit us here.** This is what makes
Task 3's audit STAY fixed: it catches the next schema/extractor/exporter drift BEFORE it poisons a
multi-hour train. Treat completion of this test as the gate that closes the whole work item.

## Why this matters / scope
v2.2 impact is modest (base flag is low-info; MB majority already matches inference; only ~12% human
skewed) — don't panic, but it's a real data-consistency bug worth a clean retrain. The RL-critical piece is
task 2 (the self-play exporter must match inference before RL self-play, else the loop trains on
advanced-only but evaluates base+advanced). Engine entry-point reminder: self-play = `Prismata_Testing.exe`
+ a config block (V2Record/SelfPlayV2Exporter); `PrismataAI.exe` = the Steam responder for the JS eval
helpers only.
