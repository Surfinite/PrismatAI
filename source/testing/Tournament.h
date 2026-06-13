#pragma once

#include "Prismata.h"
#include "rapidjson/document.h"
#include "TournamentGame.h"
#include "Timer.h"
#include <atomic>

namespace Prismata
{

class Tournament
{
    std::string                         _name;
    std::string                         _type;
    std::string                         _date;
    std::string                         _saveReplaysDir;   // empty = disabled
    std::string                         _exportTrainingV2Dir;   // empty = disabled
    // ONE id per game, shared by the replay (game_NNNN.json.gz) and the V2 export
    // (selfplay_NNNN.jsonl), so the two artifacts stay index-paired even at Threads>1
    // — the old independent counters could interleave across workers and pair
    // game_0007 with a different game's selfplay_0007 (replay-audit O1 fix).
    mutable std::atomic<int>            _artifactGameCounter{0};
    std::string                         _replayMetaJson;   // provenance object embedded in each replay (RC-3)
    size_t                              _rounds;
    size_t                              _totalGamesPlayed;
    size_t                              _discardedGames;
    size_t                              _updateIntervalSec;
    size_t                              _randomCards;
    size_t                              _threads;
    uint64_t                            _seed;   // "Seed":0 (or absent) = time-based / non-reproducible; any non-zero = fixed seed
    Timer                               _timeElapsed;

    std::vector<std::string>            _forcedCards;   // dominion cards forced into every game's card set (empty = none)
    std::vector<std::string>            _players;
    std::vector<std::string>            _stateDescriptions;
    std::vector<int>                    _playerGroups;
    std::vector<int>                    _totalGames;
    std::vector<int>                    _totalWins;
    std::vector<int>                    _totalDraws;
    std::vector<int>                    _seatGames[2];   // H2: [seat][slot] games as Player_One (seat 0) / Player_Two (seat 1)
    std::vector<int>                    _seatWins[2];    // H2: [seat][slot] wins  as Player_One (seat 0) / Player_Two (seat 1)
    std::vector<int>                    _totalPlayouts;
    std::vector<int>                    _totalTurns;
    std::vector<int>                    _maxTimeMS;
    std::vector<int>                    _totalTimeMS;
    std::vector< std::vector<int> >     _numGames;
    std::vector< std::vector<int> >     _wins;
    std::vector< std::vector<int> >     _draws;
    std::vector< std::vector<int> >     _turns;

    // A4 (2026-06-13): per-game records for the paired per-card-set analysis.
    // round == card-set id (both colour-swap games of a round share one set).
    // winnerSeat: 0 = Player_One/white won, 1 = Player_Two/black won, -1 = draw.
    // Appended only from parseTournamentGameResult (single collector thread).
    struct GameRecord { int round; int whiteSlot; int blackSlot; int winnerSeat; int turns; };
    std::vector<GameRecord>             _gameRecords;
    void writeRoundsCSV();

    int getPlayerIndex(const std::string & playerName) const;
    std::string getDisplayName(const size_t playerIndex) const;
    void parseResult(std::string & result);
    void parseTournamentGameResult(const TournamentGame & game);
    void discardTournamentGameResult(const TournamentGame & game);
    void playGame(TournamentGame & game, Timer & updateTimer);
    TournamentGame playGame(const GameState & state, const size_t whiteIndex, const size_t blackIndex, const int roundIndex) const;
    void writeHTMLResults();
    void printResults();
    std::string getTimeStringFromMS(const size_t ms);

public:

    Tournament(const rapidjson::Value & tournamentValue);
    void run();

    const std::string & getSaveReplaysDir() const { return _saveReplaysDir; }

};

}
