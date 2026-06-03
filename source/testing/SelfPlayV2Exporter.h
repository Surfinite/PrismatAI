#pragma once

#include "Prismata.h"
#include <string>
#include <utility>
#include <vector>

namespace Prismata
{

// Accumulates per-turn DeepSets "V2" training records during a single self-play
// game, then backfills the game-level outcome and writes one JSON object per line
// to <outDir>/selfplay_<gameId>.jsonl.
//
// The per-state record (everything except outcome_p0/total_plies) comes from
// buildV2RecordJSON() — the same GameState the value net evaluates — so training
// features are byte-identical to inference features by construction.
class SelfPlayV2Exporter
{
    std::string              _outDir;
    std::vector<std::string> _records;   // per-turn V2 JSON (without outcome), ply order

    // Raw-state parity sidecar. Parallel to _records: one (plyIndex, toJSONString())
    // per captured turn. finalize() writes these to a sibling parity_states/ dir as
    // sp_<gameId>_<plyIndex>.json. Each file is the exact bare-doc state shape that
    // PrismataAI.exe --dump-features consumes, feeding the C++<->PyTorch value
    // export-parity harness (tools/parity/compare_parity_35prop.py) at scale.
    std::vector<std::pair<int, std::string>> _rawStates;

public:

    explicit SelfPlayV2Exporter(const std::string & outDir)
        : _outDir(outDir)
    {
    }

    // Stash a turn-start record. Called once per player-turn at the same leaf the
    // value net is queried. plyIndex is the 0-based ply index within the game.
    void capture(const GameState & state, int plyIndex);

    // Backfill outcome_p0 + total_plies into every stashed record and write the
    // JSONL file. outcome_p0 = (winner==Player_One ? 1.0 : Player_None ? 0.5 : 0.0).
    // Returns true on a successful write.
    bool finalize(PlayerID winner, int totalPlies, int gameId);
};

} // namespace Prismata
