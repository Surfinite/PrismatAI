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
public:

    // Move-derived stamp fields backfilled into a record AFTER its turn's move is
    // played (the turn-start record is captured BEFORE the action-phase move exists):
    //   igClickCount - # of Infusion-Grid (codename "Hotel") self-sac USE_ABILITY
    //                  clicks the active player made in the move actually played.
    //   igFeasibleMax- the max # of IG clicks the mover COULD have made this turn:
    //                  min(ready Hotel count, attainable red), evaluated at decision
    //                  time (the mover's Action-phase entry — see TournamentGame's
    //                  computeIGFeasibleMax for the exact definition). Invariant:
    //                  igClickCount <= igFeasibleMax. 0 when no ready IGs.
    //   sampledIdx   - root child index the search chose after temperature/eps
    //                  sampling (Player_UCT::lastChosenIdx), or -1 if not a UCT mover.
    //   argmaxIdx    - most-visited root child index (Player_UCT::lastArgmaxIdx), or -1.
    //   rootChildren - number of root children the search actually had
    //                  (Player_UCT::rootChildren), or 0 if not a UCT mover.
    //   rootTruncated- whether the MaxChildren cap bound at the root AND the iterator still
    //                  had candidates (Player_UCT::rootTruncated); observe-only telemetry.
    struct MoveStamp { int igClickCount = 0; int igFeasibleMax = 0; int sampledIdx = -1; int argmaxIdx = -1; int rootChildren = 0; bool rootTruncated = false; };

private:

    std::string              _outDir;
    std::vector<std::string> _records;   // per-turn V2 JSON (without outcome), ply order

    // Move-derived stamps, kept strictly 1:1 with _records (one default entry pushed
    // per capture(); set by stampLastMove() after the turn's move plays). finalize()
    // backfills these three fields into each record by index.
    std::vector<MoveStamp> _moveStamps;

    // Raw-state parity sidecar. Parallel to _records: one (plyIndex, toJSONString())
    // per captured turn. finalize() writes these to a sibling parity_states/ dir as
    // sp_<gameId>_<plyIndex>.json. Each file is the exact bare-doc state shape that
    // PrismataAI.exe --dump-features consumes, feeding the C++<->PyTorch value
    // export-parity harness (tools/parity/compare_parity_deepsets.py) at scale.
    std::vector<std::pair<int, std::string>> _rawStates;

public:

    explicit SelfPlayV2Exporter(const std::string & outDir)
        : _outDir(outDir)
    {
    }

    // Stash a turn-start record. Called once per player-turn at the same leaf the
    // value net is queried. plyIndex is the 0-based ply index within the game.
    void capture(const GameState & state, int plyIndex);

    // Set the move-derived fields on the most-recently-captured record. Called once
    // per player-turn AFTER the action-phase move is played (see TournamentGame).
    // No-op if no record has been captured yet.
    void stampLastMove(int igClickCount, int igFeasibleMax, int sampledIdx, int argmaxIdx, int rootChildren, bool rootTruncated);

    // Backfill outcome_p0 + total_plies into every stashed record and write the
    // JSONL file. outcome_p0 = (winner==Player_One ? 1.0 : Player_None ? 0.5 : 0.0).
    // Returns true on a successful write.
    bool finalize(PlayerID winner, int totalPlies, int gameId);
};

} // namespace Prismata
