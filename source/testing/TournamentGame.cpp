#include "TournamentGame.h"
#include "Timer.h"

#include <iostream>

using namespace Prismata;

TournamentGame::TournamentGame(const GameState & initialState, const std::string & p1name, PlayerPtr p1, const std::string & p2name, const PlayerPtr p2)
    : _game(initialState, p1, p2)
    , _discarded(false)
{
    _playerNames[0] = p1name;
    _playerNames[1] = p2name;
    _playerTotalTimeMS[0] = 0;
    _playerTotalTimeMS[1] = 0;
    _maxTimeMS[0] = 0;
    _maxTimeMS[1] = 0;
}

void TournamentGame::playGame(size_t updateIntervalSec)
{
    Timer t;
    Timer updateTimer;
    updateTimer.start();

    // Optional replay capture. The serializer is constructed only when
    // setReplaySaveDir was called. Capture is done entirely here in the
    // tournament harness (see the per-action replay below) — Dave's engine
    // (Game / GameState) is unmodified, and nothing runs on the AI's
    // search/playout hot path. When disabled, none of this runs.
    if (!_replaySaveDir.empty())
    {
        // cardSet = the game's advanced (non-base) buyable units — the random
        // units that define the matchup — matching the JS matchup-format field.
        // Derived once from the initial buyable set; base-set units excluded.
        // (Purely informational metadata; the buy panel renders from the
        // per-state cards[] array, not this.)
        const GameState & init = _game.getState();
        std::vector<std::string> cardSet;
        for (CardID i = 0; i < init.numCardsBuyable(); ++i)
        {
            const CardType ct = init.getCardBuyableByIndex(i).getType();
            if (!ct.isBaseSet()) cardSet.push_back(ct.getUIName());
        }
        _serializer = std::make_unique<ReplaySerializer>(_playerNames[0], _playerNames[1], cardSet);
        _serializer->captureInitialState(init);
    }

    // Optional DeepSets V2 training-data export. Independent of replay capture:
    // it snapshots a per-turn record at each turn-start (the leaf the value net
    // evaluates) and backfills the game outcome at the end. plyIndex counts
    // captured player-turns (0-based) within this game.
    if (!_exportV2Dir.empty())
    {
        _v2Exporter = std::make_unique<SelfPlayV2Exporter>(_exportV2Dir);
    }
    int _v2PlyIndex = 0;

    while(!_game.gameOver())
    {
        PlayerID playerToMove = _game.getState().getActivePlayer();

        // V2 capture at turn-start: the current GameState is the turn-start
        // snapshot the active player's value net would evaluate. One record per
        // player-turn (not per action).
        if (_v2Exporter)
        {
            _v2Exporter->capture(_game.getState(), _v2PlyIndex);
            ++_v2PlyIndex;
        }

        // Snapshot the pre-move state when recording, so per-action frames can be
        // reconstructed off the think-timer below. Allocated only when recording;
        // this is per-turn (not per-search-node), so it is well off the AI hot path.
        std::unique_ptr<GameState> preMoveState;
        if (_serializer) { preMoveState = std::make_unique<GameState>(_game.getState()); }

        t.start();
        if (!_game.playNextTurn(false))
        {
            _discarded = true;
            _discardReason = "empty move from " + _playerNames[playerToMove] + " on turn " + std::to_string(_game.getState().getTurnNumber());
            // Serializer / V2 exporter are dropped without finalize on discard.
            _serializer.reset();
            _v2Exporter.reset();
            return;
        }

        double ms = t.getElapsedTimeInMilliSec();
        _playerTotalTimeMS[playerToMove] += ms;
        _maxTimeMS[playerToMove] = std::max((size_t)ms, _maxTimeMS[playerToMove]);

        // Per-action replay capture, OFF the think-timer (ms already recorded
        // above). Re-apply the move that was just played onto a clone of the
        // pre-move state, emitting one snapshot per action. This reproduces
        // exactly the states the real game passed through — Game::doMove applies
        // the same actions via GameState::doAction — without any engine-side hook.
        // Order matches the schema: per-action states first, then the trailing
        // turn boundary (which points past the last action and is harmless for
        // the scrubber).
        if (_serializer)
        {
            const Move & move = _game.getPreviousMove();
            for (ActionID a(0); a < move.size(); ++a)
            {
                const Action & action = move.getAction(a);
                preMoveState->doAction(action);
                _serializer->captureActionApplied(*preMoveState, action);
            }
            _serializer->recordTurnBoundary();
        }

        if (updateIntervalSec > 0 && updateTimer.getElapsedTimeInSec() >= updateIntervalSec)
        {
            std::cout << "  Playing " << _playerNames[0] << " vs " << _playerNames[1]
                      << ", turn " << _game.getState().getTurnNumber() << std::endl;
            updateTimer.start();
        }
    }

    // Finalize at end of game. Task 18 implements the actual gzip + write.
    if (_serializer)
    {
        const GameState & finalState = _game.getState();
        const PlayerID w = finalState.winner();
        const int winnerInt = (w == Players::Player_One) ? 0
                            : (w == Players::Player_Two) ? 1
                            : -1; // draw / no winner
        const int turns = static_cast<int>(finalState.getTurnNumber());
        _serializer->finalize(winnerInt, turns, _replaySaveDir, _replayGameIndex);
        _serializer.reset();
    }

    // Finalize the V2 training export: backfill outcome_p0 + total_plies (game
    // level) and write selfplay_<gameId>.jsonl. total_plies = engine turn number.
    if (_v2Exporter)
    {
        const GameState & finalState = _game.getState();
        _v2Exporter->finalize(finalState.winner(),
                              static_cast<int>(finalState.getTurnNumber()),
                              _exportV2GameId);
        _v2Exporter.reset();
    }
}

bool TournamentGame::wasDiscarded() const
{
    return _discarded;
}

const std::string & TournamentGame::getDiscardReason() const
{
    return _discardReason;
}

const std::string & TournamentGame::getPlayerName(const PlayerID player) const
{
    return _playerNames[player];
}

const GameState & TournamentGame::getFinalGameState() const
{
    return _game.getState();
}

const size_t TournamentGame::getTotalTimeMS(const PlayerID player) const
{
    return _playerTotalTimeMS[player];
}

const size_t TournamentGame::getMaxTimeMS(const PlayerID player) const
{
    return _maxTimeMS[player];
}
