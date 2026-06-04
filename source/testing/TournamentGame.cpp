#include "TournamentGame.h"
#include "Timer.h"
#include "Player_UCT.h"

#include <iostream>
#include <memory>

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
    int plyIndex = 0;

    while(!_game.gameOver())
    {
        PlayerID playerToMove = _game.getState().getActivePlayer();

        // V2 capture at turn-start: the current GameState is the turn-start
        // snapshot the active player's value net would evaluate. One record per
        // player-turn (not per action).
        if (_v2Exporter)
        {
            _v2Exporter->capture(_game.getState(), plyIndex);
            ++plyIndex;
        }

        // Snapshot the pre-move state when recording OR exporting V2 records, so
        // per-action frames can be reconstructed off the think-timer below, and the
        // V2 exporter can count Infusion-Grid clicks on a pristine pre-move clone.
        // Allocated only when needed; this is per-turn (not per-search-node), so it
        // is well off the AI hot path.
        std::unique_ptr<GameState> preMoveState;
        if (_serializer || _v2Exporter) { preMoveState = std::make_unique<GameState>(_game.getState()); }

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

        // V2 move-stamp: backfill the move-derived fields onto the just-captured
        // turn-start record. Done HERE — after the move plays, BEFORE the serializer
        // block below mutates preMoveState. All under if (_v2Exporter), so normal
        // (non-export) play is unaffected.
        if (_v2Exporter)
        {
            const Move & move = _game.getPreviousMove();

            // Count Infusion-Grid (engine codename "Hotel") self-sac clicks by the
            // mover. Walk a SEPARATE local clone so each source instId is valid at
            // lookup time and preMoveState stays pristine for the serializer block.
            // Apply each action AFTER the check, so the lookup sees the source before
            // it is sacced/removed. Net out the rare UNDO of an IG ability.
            int igClicks = 0;
            // Hard guard: the IG walk dereferences preMoveState, which is allocated far
            // above (only when _serializer || _v2Exporter). It is always set when we get
            // here today, but the allocation and this deref are far apart with a
            // playNextTurn between them, so guard explicitly. PRISMATA_ASSERT is a SOFT
            // assert (prints, does not abort), so the if() — not the assert — is what
            // actually prevents a null deref.
            PRISMATA_ASSERT(preMoveState != nullptr, "preMoveState must be allocated when _v2Exporter is set");
            if (preMoveState)
            {
                GameState igWalk(*preMoveState);
                for (ActionID a(0); a < move.size(); ++a)
                {
                    const Action & action = move.getAction(a);
                    if (action.getPlayer() == playerToMove)
                    {
                        const ActionID type = action.getType();
                        if (type == ActionTypes::USE_ABILITY || type == ActionTypes::UNDO_USE_ABILITY)
                        {
                            const Card & src = igWalk.getCardByID(action.getID());
                            if (src.getType().getName() == "Hotel")
                            {
                                igClicks += (type == ActionTypes::USE_ABILITY) ? 1 : -1;
                            }
                        }
                    }
                    igWalk.doAction(action);
                }
            }
            if (igClicks < 0) { igClicks = 0; }

            // UCT root diagnostics from the mover (null-safe: -1 for non-UCT players).
            int sampledIdx = -1, argmaxIdx = -1;
            const PlayerPtr mover = _game.getPlayer(playerToMove);
            if (auto uct = std::dynamic_pointer_cast<Player_UCT>(mover))
            {
                sampledIdx = uct->lastChosenIdx();
                argmaxIdx  = uct->lastArgmaxIdx();
            }

            _v2Exporter->stampLastMove(igClicks, sampledIdx, argmaxIdx);
        }

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
        // total_plies = final getTurnNumber() (player-turn count). For a normally
        // completed game this equals the number of captured turn-start records.
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
