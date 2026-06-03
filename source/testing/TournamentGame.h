#pragma once

#include "Prismata.h"
#include "rapidjson/document.h"
#include "ReplaySerializer.h"
#include "SelfPlayV2Exporter.h"
#include <memory>

namespace Prismata
{

class TournamentGame
{
    Game            _game;
    std::string     _playerNames[2];
    std::string     _discardReason;
    size_t          _playerTotalTimeMS[2];
    size_t          _maxTimeMS[2];
    bool            _discarded;

    // Optional replay capture. When non-empty, playGame() constructs a
    // ReplaySerializer and drives it entirely from the harness: it captures the
    // initial state, replays each completed Move on a GameState clone (one
    // snapshot per action, off the think-timer), records turn boundaries, and
    // finalizes at end. Dave's engine (Game / GameState) is unmodified.
    std::string                       _replaySaveDir;
    int                               _replayGameIndex = 0;
    std::unique_ptr<ReplaySerializer> _serializer;

    // Optional DeepSets V2 training-data capture (RL self-play). When the dir is
    // non-empty, playGame() snapshots a V2 record at each turn-start (the same
    // GameState the value net evaluates), then backfills outcome at game end.
    std::string                         _exportV2Dir;
    int                                 _exportV2GameId = 0;
    std::unique_ptr<SelfPlayV2Exporter> _v2Exporter;

public:

    TournamentGame(const GameState & initialState, const std::string & p1name, PlayerPtr p1, const std::string & p2name, const PlayerPtr p2);

    void playGame(size_t updateIntervalSec = 0);

    bool wasDiscarded() const;
    const std::string & getDiscardReason() const;
    const std::string & getPlayerName(const PlayerID player) const;
    const GameState & getFinalGameState() const;
    const size_t getTotalTimeMS(const PlayerID player) const;
    const size_t getMaxTimeMS(const PlayerID player) const;

    // Enable per-action replay capture for this game. dir = output directory
    // (created if missing); gameIndex feeds the game_NNNN.json.gz filename.
    void setReplaySaveDir(const std::string & dir, int gameIndex)
    {
        _replaySaveDir = dir;
        _replayGameIndex = gameIndex;
    }

    // Enable per-turn DeepSets V2 training-record export for this game. dir =
    // output directory (created if missing); gameId feeds selfplay_<gameId>.jsonl.
    void setExportTrainingV2(const std::string & dir, int gameId)
    {
        _exportV2Dir = dir;
        _exportV2GameId = gameId;
    }
};

}
