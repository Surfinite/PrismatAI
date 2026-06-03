#pragma once

#include "Prismata.h"
#include <string>

namespace Prismata
{

// Build the per-state DeepSets "V2" training-record JSON from a turn-start GameState.
//
// The record is byte-shape-compatible with what js_engine/training_example.js
// extractTrainingExampleV2() emits, so vectorize_v2.py is the single source of
// truth for normalization. Emitting it here (from the same GameState the value
// net evaluates at inference) gives train/inference feature parity by construction.
//
// NOTE: the returned object intentionally OMITS the game-level fields
// "outcome_p0" and "total_plies" — those are backfilled by the exporter at game
// end (see SelfPlayV2Exporter::finalize). Everything else is per-turn-state.
std::string buildV2RecordJSON(const GameState & state, int plyIndex);

} // namespace Prismata
