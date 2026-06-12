#include "Tournament.h"
#include "TestingConfig.h"
#include "Timer.h"
#include "PrismataAI.h"
#include "Random.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"

#include <iostream>
#include <iomanip>
#include <ctime>
#include <sstream>
#include <chrono>
#include <future>
#include <thread>
using namespace Prismata;

Tournament::Tournament(const rapidjson::Value & tournamentValue)
    : _totalGamesPlayed(0)
    , _discardedGames(0)
    , _updateIntervalSec(0)
    , _randomCards(8)
    , _threads(1)
{
    PRISMATA_ASSERT(tournamentValue.HasMember("name"), "Tournament has no name");
    PRISMATA_ASSERT(tournamentValue.HasMember("rounds"), "Tournament has no rounds number");
    PRISMATA_ASSERT(tournamentValue.HasMember("players"), "Tournament has no players");

    JSONTools::ReadString("name", tournamentValue, _name);
    JSONTools::ReadInt("rounds", tournamentValue, _rounds);
    JSONTools::ReadInt("RandomCards", tournamentValue, _randomCards);
    JSONTools::ReadInt("UpdateIntervalSec", tournamentValue, _updateIntervalSec);
    JSONTools::ReadInt("Threads", tournamentValue, _threads);
    _threads = std::max<size_t>(1, _threads);

    _seed = 0;
    JSONTools::ReadInt("Seed", tournamentValue, _seed);   // 0 = time-based (default)

    if (tournamentValue.HasMember("saveReplays") && tournamentValue["saveReplays"].IsString())
    {
        _saveReplaysDir = tournamentValue["saveReplays"].GetString();
    }

    if (tournamentValue.HasMember("exportTrainingV2") && tournamentValue["exportTrainingV2"].IsString())
    {
        _exportTrainingV2Dir = tournamentValue["exportTrainingV2"].GetString();
    }

    if (tournamentValue.HasMember("ForcedCards") && tournamentValue["ForcedCards"].IsArray())
    {
        for (size_t i(0); i < tournamentValue["ForcedCards"].Size(); ++i)
        {
            if (tournamentValue["ForcedCards"][i].IsString())
            {
                _forcedCards.push_back(tournamentValue["ForcedCards"][i].GetString());
            }
        }
    }

    PRISMATA_ASSERT(tournamentValue["players"].Size() >= 2, "Tournament has less than 2 players");

    for (size_t i(0); i < tournamentValue["players"].Size(); ++i)
    {
        _players.push_back(tournamentValue["players"][i]["name"].GetString());
        _playerGroups.push_back(tournamentValue["players"][i]["group"].GetInt());
    }

    // Replay provenance meta (RC-3): serialized once here, embedded as the
    // top-level "meta" object of every replay this tournament writes. Additive
    // keys — viewers ignore them. Built with rapidjson (not string concat) so
    // the tournament name is JSON-escaped.
    if (!_saveReplaysDir.empty())
    {
        rapidjson::Document meta(rapidjson::kObjectType);
        auto & a = meta.GetAllocator();
        rapidjson::Value name(_name.c_str(), static_cast<rapidjson::SizeType>(_name.size()), a);
        meta.AddMember("tournament", name, a);
        // Seed:0 = time-based / non-reproducible — omit rather than stamp a misleading 0.
        // (At Threads>1 even a nonzero seed governs only the card-set sequence — §1d.)
        if (_seed != 0) { meta.AddMember("seed", static_cast<uint64_t>(_seed), a); }
        meta.AddMember("threads", static_cast<unsigned>(_threads), a);
        rapidjson::StringBuffer buf;
        rapidjson::Writer<rapidjson::StringBuffer> w(buf);
        meta.Accept(w);
        _replayMetaJson.assign(buf.GetString(), buf.GetSize());
    }
}

void Tournament::run()
{
    auto time = std::time(nullptr);
    auto tm = *std::localtime(&time);

    std::stringstream startDate;
    startDate << std::put_time(&tm, "%Y-%m-%d_%H-%M-%S");
    _date = startDate.str();

    if (_seed != 0)
    {
        Random::Seed(_seed);
        if (_threads > 1)
        {
            fprintf(stderr, "[Tournament] Seed set but Threads=%zu>1; the seed applies to the main "
                            "thread only (worker threads seed independently) -- only Threads:1 is "
                            "reproducible.\n", _threads);
        }
    }

    _totalGames = std::vector<int>(_players.size(), 0);
    _totalWins = std::vector<int>(_players.size(), 0);
    _totalDraws = std::vector<int>(_players.size(), 0);
    _seatGames[0] = std::vector<int>(_players.size(), 0);
    _seatGames[1] = std::vector<int>(_players.size(), 0);
    _seatWins[0] = std::vector<int>(_players.size(), 0);
    _seatWins[1] = std::vector<int>(_players.size(), 0);
    _totalTurns = std::vector<int>(_players.size(), 0);
    _totalPlayouts = std::vector<int>(_players.size(), 0);
    _totalTimeMS = std::vector<int>(_players.size(), 0);
    _maxTimeMS = std::vector<int>(_players.size(), 0);
    _numGames = std::vector< std::vector<int> >(_players.size(), std::vector<int>(_players.size(), 0));
    _wins = std::vector< std::vector<int> >(_players.size(), std::vector<int>(_players.size(), 0));
    _draws = std::vector< std::vector<int> >(_players.size(), std::vector<int>(_players.size(), 0));
    _turns = std::vector< std::vector<int> >(_players.size(), std::vector<int>(_players.size(), 0));

    size_t totalGamesExpected = 0;
    for (size_t p1(0); p1 < _players.size(); ++p1)
    {
        for (size_t p2(p1 + 1); p2 < _players.size(); ++p2)
        {
            if (_playerGroups[p1] != _playerGroups[p2])
            {
                totalGamesExpected += 2;
            }
        }
    }
    totalGamesExpected *= _rounds;

    std::cout << "\nStarting tournament " << _name << ": " << _rounds << " rounds, "
              << _players.size() << " players, " << totalGamesExpected
              << " games, " << _threads << " thread" << (_threads == 1 ? "" : "s")
              << ", updates every " << _updateIntervalSec << " seconds" << std::endl;

    Timer t;
    t.start();
    _timeElapsed.start();

    if (_threads == 1)
    {
        for (size_t r(0); r < _rounds; ++r)
        {
            GameState state;
            state.setStartingState(Players::Player_One, _randomCards, _forcedCards);

            for (size_t p1(0); p1 < _players.size(); ++p1)
            {
                for (size_t p2(p1 + 1); p2 < _players.size(); ++p2)
                {
                    if (_playerGroups[p1] == _playerGroups[p2])
                    {
                        continue;
                    }

                    PlayerPtr w1 = AIParameters::Instance().getPlayer(Players::Player_One, _players[p1]);
                    PlayerPtr b1 = AIParameters::Instance().getPlayer(Players::Player_Two, _players[p2]);
                    PlayerPtr w2 = AIParameters::Instance().getPlayer(Players::Player_One, _players[p2]);
                    PlayerPtr b2 = AIParameters::Instance().getPlayer(Players::Player_Two, _players[p1]);

                    TournamentGame g1(state, _players[p1], w1, _players[p2], b1);
                    TournamentGame g2(state, _players[p2], w2, _players[p1], b2);

                    // H3: record which SLOT sat which seat so results are credited
                    // by slot index, not by (ambiguous) name lookup.
                    g1.setPlayerSlots((int)p1, (int)p2);
                    g2.setPlayerSlots((int)p2, (int)p1);

                    // One shared id per game keeps game_NNNN.json.gz and
                    // selfplay_NNNN.jsonl index-paired (replay-audit O1).
                    if (!_saveReplaysDir.empty() || !_exportTrainingV2Dir.empty())
                    {
                        const int gid1 = _artifactGameCounter.fetch_add(1);
                        const int gid2 = _artifactGameCounter.fetch_add(1);
                        if (!_saveReplaysDir.empty())
                        {
                            g1.setReplaySaveDir(_saveReplaysDir, gid1);
                            g2.setReplaySaveDir(_saveReplaysDir, gid2);
                            g1.setReplayMeta(_replayMetaJson);
                            g2.setReplayMeta(_replayMetaJson);
                        }
                        if (!_exportTrainingV2Dir.empty())
                        {
                            g1.setExportTrainingV2(_exportTrainingV2Dir, gid1);
                            g2.setExportTrainingV2(_exportTrainingV2Dir, gid2);
                        }
                    }

                    playGame(g1, t);
                    playGame(g2, t);
                }
            }
        }
    }
    else
    {
        std::vector<std::future<TournamentGame>> games;

        auto printUpdate = [&]()
        {
            printResults();
            writeHTMLResults();
            std::cout << std::endl << std::flush;
            t.start();
        };

        auto maybePrintUpdate = [&]()
        {
            if (_updateIntervalSec > 0 && t.getElapsedTimeInSec() >= _updateIntervalSec)
            {
                printUpdate();
            }
        };

        auto finishGame = [&](TournamentGame & game)
        {
            if (game.wasDiscarded())
            {
                discardTournamentGameResult(game);
                maybePrintUpdate();
                return;
            }

            parseTournamentGameResult(game);
            _totalGamesPlayed++;

            if (_updateIntervalSec == 0)
            {
                printUpdate();
            }
            else
            {
                maybePrintUpdate();
            }
        };

        auto collectFinishedGames = [&]()
        {
            bool collected = false;
            for (size_t i(0); i < games.size();)
            {
                if (games[i].wait_for(std::chrono::milliseconds(0)) == std::future_status::ready)
                {
                    TournamentGame game = games[i].get();
                    finishGame(game);
                    games.erase(games.begin() + i);
                    collected = true;
                }
                else
                {
                    ++i;
                }
            }

            return collected;
        };

        auto waitForGameSlot = [&]()
        {
            while (games.size() >= _threads)
            {
                if (!collectFinishedGames())
                {
                    maybePrintUpdate();
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                }
            }
        };

        auto submitGame = [&](const GameState & state, const size_t whiteIndex, const size_t blackIndex)
        {
            waitForGameSlot();
            games.emplace_back(std::async(std::launch::async, [this, state, whiteIndex, blackIndex]()
            {
                return playGame(state, whiteIndex, blackIndex);
            }));
        };

        for (size_t r(0); r < _rounds; ++r)
        {
            GameState state;
            state.setStartingState(Players::Player_One, _randomCards, _forcedCards);

            for (size_t p1(0); p1 < _players.size(); ++p1)
            {
                for (size_t p2(p1 + 1); p2 < _players.size(); ++p2)
                {
                    if (_playerGroups[p1] == _playerGroups[p2])
                    {
                        continue;
                    }

                    submitGame(state, p1, p2);
                    submitGame(state, p2, p1);
                }
            }
        }

        while (!games.empty())
        {
            if (!collectFinishedGames())
            {
                maybePrintUpdate();
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
    }

    printResults();
    writeHTMLResults();
    std::cout << std::endl << "Tournament complete" << std::endl;
}

TournamentGame Tournament::playGame(const GameState & state, const size_t whiteIndex, const size_t blackIndex) const
{
    PlayerPtr white = AIParameters::Instance().getPlayer(Players::Player_One, _players[whiteIndex]);
    PlayerPtr black = AIParameters::Instance().getPlayer(Players::Player_Two, _players[blackIndex]);

    TournamentGame game(state, _players[whiteIndex], white, _players[blackIndex], black);
    game.setPlayerSlots((int)whiteIndex, (int)blackIndex);   // H3: credit results by slot, not name
    // One shared id per game keeps game_NNNN.json.gz and selfplay_NNNN.jsonl
    // index-paired even at Threads>1 (replay-audit O1).
    if (!_saveReplaysDir.empty() || !_exportTrainingV2Dir.empty())
    {
        const int gid = _artifactGameCounter.fetch_add(1);
        if (!_saveReplaysDir.empty())
        {
            game.setReplaySaveDir(_saveReplaysDir, gid);
            game.setReplayMeta(_replayMetaJson);
        }
        if (!_exportTrainingV2Dir.empty())
        {
            game.setExportTrainingV2(_exportTrainingV2Dir, gid);
        }
    }
    game.playGame();

    return game;
}

void Tournament::playGame(TournamentGame & game, Timer & updateTimer)
{
    game.playGame(_updateIntervalSec);

    if (game.wasDiscarded())
    {
        discardTournamentGameResult(game);

        if (_updateIntervalSec == 0 || updateTimer.getElapsedTimeInSec() >= _updateIntervalSec)
        {
            printResults();
            writeHTMLResults();
            std::cout << std::endl << std::flush;
            updateTimer.start();
        }

        return;
    }

    parseTournamentGameResult(game);

    _totalGamesPlayed++;

    if (_updateIntervalSec == 0 || updateTimer.getElapsedTimeInSec() >= _updateIntervalSec)
    {
        printResults();
        writeHTMLResults();
        std::cout << std::endl << std::flush;
        updateTimer.start();
    }
}

void Tournament::discardTournamentGameResult(const TournamentGame & game)
{
    _discardedGames++;
    std::cout << "Discarded game: " << game.getPlayerName(0) << " vs " << game.getPlayerName(1)
              << " (" << game.getDiscardReason() << ")" << std::endl;
}

void Tournament::parseTournamentGameResult(const TournamentGame & game)
{
    int winnerID = game.getFinalGameState().winner();
    int loserID = (game.getFinalGameState().winner() + 1) % 2;

    // H3: credit results by the SLOT indices recorded at dispatch. The old
    // getPlayerIndex(name) lookup returned the FIRST name match, so same-name
    // self-match blocks (RL_Cal_N*, RL_Step2_Smoke, RL_SelfPlay_General) collapsed
    // all credit onto slot 0 and slot 1 showed 0 games / -nan(ind).
    int playerIndex[2] = {game.getPlayerSlot(0), game.getPlayerSlot(1)};
    if (playerIndex[0] < 0 || playerIndex[1] < 0)
    {
        // Fallback for games not dispatched through run() (none today).
        playerIndex[0] = getPlayerIndex(game.getPlayerName(0));
        playerIndex[1] = getPlayerIndex(game.getPlayerName(1));
    }
    if (playerIndex[0] < 0 || playerIndex[1] < 0
        || playerIndex[0] >= (int)_players.size() || playerIndex[1] >= (int)_players.size())
    {
        fprintf(stderr, "FATAL: Tournament::parseTournamentGameResult: unattributable game '%s' vs '%s' "
                        "(slots %d, %d of %zu). Aborting.\n",
                game.getPlayerName(0).c_str(), game.getPlayerName(1).c_str(),
                playerIndex[0], playerIndex[1], _players.size());
        abort();
    }

    // H2: per-seat tallies (seat 0 = Player_One / first, seat 1 = Player_Two / second).
    _seatGames[0][playerIndex[0]]++;
    _seatGames[1][playerIndex[1]]++;

    _maxTimeMS[playerIndex[0]] = std::max(_maxTimeMS[playerIndex[0]], (int)game.getMaxTimeMS(0));
    _maxTimeMS[playerIndex[1]] = std::max(_maxTimeMS[playerIndex[1]], (int)game.getMaxTimeMS(1));
    _totalTimeMS[playerIndex[0]] += game.getTotalTimeMS(0);
    _totalTimeMS[playerIndex[1]] += game.getTotalTimeMS(1);
    _totalGames[playerIndex[0]]++;
    _totalGames[playerIndex[1]]++;
    _numGames[playerIndex[0]][playerIndex[1]]++;
    _numGames[playerIndex[1]][playerIndex[0]]++;
    _totalTurns[playerIndex[0]] += game.getFinalGameState().getTurnNumber()/2;
    _totalTurns[playerIndex[1]] += game.getFinalGameState().getTurnNumber()/2;
    _turns[playerIndex[0]][playerIndex[1]] += game.getFinalGameState().getTurnNumber();
    _turns[playerIndex[1]][playerIndex[0]] += game.getFinalGameState().getTurnNumber();


    // case of a draw
    if (winnerID == Players::Player_None)
    {
        _draws[playerIndex[0]][playerIndex[1]]++;
        _draws[playerIndex[1]][playerIndex[0]]++;
        _totalDraws[playerIndex[0]]++;
        _totalDraws[playerIndex[1]]++;
    }
    else
    {
        // case of a non-draw
        int winnerIndex = playerIndex[winnerID];
        int loserIndex = playerIndex[loserID];

        _totalWins[winnerIndex]++;
        _wins[winnerIndex][loserIndex]++;
        _seatWins[winnerID][winnerIndex]++;   // H2: winnerID IS the winning seat (0 = first, 1 = second)
    }
}

#include "HTMLTable.h"
void Tournament::writeHTMLResults()
{
    std::string filename = "tests/Tournament_" + _name + "_" + _date + ".html";

    std::string assertLevel = "No Asserts";

#ifdef PRISMATA_ASSERT_NORMAL
    assertLevel = "Normal Asserts";
#endif

#ifdef PRISMATA_ASSERT_ALL
    assertLevel = "All Asserts";
#endif
    
    std::stringstream ss;
    double timeElapsed = _timeElapsed.getElapsedTimeInMilliSec();

    ss << "<table cellpadding=2 rules=all style=\"font: 12px/1.5em Verdana; border: 1px solid #cccccc;\">\n";
    ss << "<tr><td width=150><b>Tournament Name</b></td><td width=200 align=right>" << _name << "</td></tr>\n";
    ss << "<tr><td><b>Date Started</b></td><td align=right>" << _date << "</td></tr>\n";
    ss << "<tr><td><b>AI Compiled</b></td><td align=right>" << __DATE__ << " " __TIME__ << "</td></tr>";
    ss << "<tr><td><b>Assert Level</b></td><td align=right>" << assertLevel << "</td></tr>";
    ss << "<tr><td><b>Tournament Rounds</b></td><td align=right>" << _rounds << "</td></tr>\n";
    ss << "<tr><td><b>Time Elapsed</b></td><td align=right>" << getTimeStringFromMS(timeElapsed) << "</td></tr>\n";
    ss << "<tr><td><b>Games Played</b></td><td align=right>" << _totalGamesPlayed << " (" << (1000.0 * _totalGamesPlayed / timeElapsed) << "/s)</td></tr>\n";
    ss << "<tr><td><b>Games Discarded</b></td><td align=right>" << _discardedGames << "</td></tr>\n";
    ss << "</table>\n<br><br>\n";

    FILE * f = fopen(filename.c_str(), "w");
    // L-09 family: unchecked fopen null-derefed on the first fprintf when tests/ is
    // missing, and ss.str() was passed as the fprintf FORMAT string.
    if (!f)
    {
        fprintf(stderr, "FATAL: Tournament::writeHTMLResults: could not open '%s' for write "
                        "(missing tests/ directory?). Aborting.\n", filename.c_str());
        abort();
    }
    fprintf(f, "<html>\n<head>\n");
    fprintf(f, "<script type=\"text/javascript\" src=\"javascript/jquery-1.10.2.min.js\"></script>\n<script type=\"text/javascript\" src=\"javascript/jquery.tablesorter.js\"></script>\n<link rel=\"stylesheet\" href=\"javascript/themes/blue/style.css\" type=\"text/css\" media=\"print, projection, screen\" />\n");
    fprintf(f, "</head>\n");
    fprintf(f, "%s", ss.str().c_str());
    fclose(f);

    HTMLTable stats("Overall Statistics");
    // H2: "P1 W/G" / "P2 W/G" = per-seat wins/games as Player_One (first player) and
    // as Player_Two (second player). Their games sum to the Games column.
    stats.setHeader({"Player", "Score", "Games", "Wins", "Loss", "Draw", "P1 W/G", "P2 W/G", "Turns", "Turns/G", "MS/Turn", "Max MS"});
    stats.setColWidth({120, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80});

    for (size_t p(0); p < _players.size(); ++p)
    {
        size_t col = 0;
        stats.setData(p, col++, getDisplayName(p));
        stats.setData(p, col++, _totalGames[p] == 0 ? 0.0 : (_totalWins[p] + 0.5*_totalDraws[p])/_totalGames[p]);
        stats.setData(p, col++, _totalGames[p]);
        stats.setData(p, col++, _totalWins[p]);
        stats.setData(p, col++, _totalGames[p] - _totalWins[p] - _totalDraws[p]);
        stats.setData(p, col++, _totalDraws[p]);
        stats.setData(p, col++, std::to_string(_seatWins[0][p]) + "/" + std::to_string(_seatGames[0][p]));
        stats.setData(p, col++, std::to_string(_seatWins[1][p]) + "/" + std::to_string(_seatGames[1][p]));
        stats.setData(p, col++, _totalTurns[p]);
        stats.setData(p, col++, _totalGames[p] == 0 ? 0.0 : (double)_totalTurns[p] / _totalGames[p]);
        stats.setData(p, col++, _totalTurns[p] == 0 ? 0.0 : (double)_totalTimeMS[p] / _totalTurns[p]);
        stats.setData(p, col++, _maxTimeMS[p]);
    }

    HTMLTable turnTable("Bot vs. Bot Avg Turns Per Game");
    HTMLTable tableWinPerc("Bot vs. Bot Score Table (row score vs. column)");
    std::vector<std::string> header = {""};
    for (size_t p(0); p < _players.size(); ++p)
    {
        header.push_back(getDisplayName(p));
    }
    header.push_back("Total");
    turnTable.setHeader(header);
    tableWinPerc.setHeader(header);

    std::vector<size_t> colWidth(header.size(), 120);
    turnTable.setColWidth(colWidth);
    tableWinPerc.setColWidth(colWidth);

    for (size_t r(0); r < _players.size(); ++r)
    {
        size_t col = 0;
        turnTable.setData(r, col, getDisplayName(r));
        tableWinPerc.setData(r, col, getDisplayName(r));
        col++;

        for (size_t p(0); p < _players.size(); ++p)
        {
            if (r == p)
            {
                turnTable.setData(r, col, "-");
                tableWinPerc.setData(r, col, "-");
            }
            else
            {
                turnTable.setData(r, col, _numGames[r][p] == 0 ? 0 : (double)_turns[r][p] / _numGames[r][p]);
                tableWinPerc.setData(r, col, _numGames[r][p] == 0 ? 0 : ((double)_wins[r][p] + 0.5*_draws[r][p]) / _numGames[r][p]);
            }

            col++;
        }

        turnTable.setData(r, col, _totalTurns[r]);
        tableWinPerc.setData(r, col, _totalGames[r] == 0 ? 0 : ((double)_totalWins[r] + 0.5*_totalDraws[r]) / _totalGames[r]);
        col++;
    }

    stats.appendHTMLTableToFile(filename, "statsTable");
    tableWinPerc.appendHTMLTableToFile(filename, "winPercentageTable");
    turnTable.appendHTMLTableToFile(filename, "totalScoreTable");
}

void Tournament::printResults()
{
    std::stringstream ss;

    size_t colWidth = 10;
    for (size_t i(0); i < _players.size(); ++i)
    {
        colWidth = std::max(colWidth, getDisplayName(i).length() + 2);
    }

    ss << std::endl << std::endl;

    const size_t totalScoreCol = colWidth + _players.size()*colWidth;   // where each row's TotalScore lands

    std::stringstream header;
    for (size_t i(0); i < _players.size(); ++i)
    {
        while (header.str().length() < (i+1)*colWidth) header << " ";
        header << getDisplayName(i);
    }

    // H2: per-seat stats columns (wins/games as first player and as second player)
    while (header.str().length() < totalScoreCol) header << " ";
    header << "TotalScore";
    while (header.str().length() < totalScoreCol + 12) header << " ";
    header << "P1-W/G";
    while (header.str().length() < totalScoreCol + 22) header << " ";
    header << "P2-W/G";

    std::cout << header.str() << std::endl;
    ss << header.str() << std::endl;

    for (size_t i(0); i < _players.size(); ++i)
    {
        std::stringstream line;
        line << getDisplayName(i); while (line.str().length() < colWidth) line << " ";

        for (size_t j(0); j < _players.size(); ++j)
        {
            if (_playerGroups[i] != _playerGroups[j])
            {
                line << _wins[i][j] + (0.5*_draws[i][j]) ;
            }
            else
            {
                line << "-";
            }

            while (line.str().length() < colWidth + (j+1)*colWidth) line << " ";
        }

        line << _totalWins[i] + (0.5*_totalDraws[i]);
        while (line.str().length() < totalScoreCol + 12) line << " ";
        line << _seatWins[0][i] << "/" << _seatGames[0][i];
        while (line.str().length() < totalScoreCol + 22) line << " ";
        line << _seatWins[1][i] << "/" << _seatGames[1][i];
        line << std::endl;
        ss << line.str();
        std::cout << line.str();
    }

    const double elapsedSec = _timeElapsed.getElapsedTimeInSec();
    const double gamesPerSec = elapsedSec > 0 ? _totalGamesPlayed / elapsedSec : 0.0;

    std::stringstream rate;
    rate << std::fixed << std::setprecision(2) << gamesPerSec;

    std::stringstream threadRate;
    threadRate << std::fixed << std::setprecision(2) << (gamesPerSec / _threads);

    std::cout << "Games completed: " << _totalGamesPlayed << " (" << rate.str() << "/s, " << threadRate.str() << "/s/thread)";
    if (_discardedGames > 0)
    {
        std::cout << ", discarded: " << _discardedGames;
    }
    std::cout << std::endl << std::flush;
}

int Tournament::getPlayerIndex(const std::string & playerName) const
{
    for (size_t i(0); i < _players.size(); ++i)
    {
        if (_players[i].compare(playerName) == 0)
        {
            return i;
        }
    }

    return -1;
}

std::string Tournament::getDisplayName(const size_t playerIndex) const
{
    // H3: same-name self-match blocks are legitimate (slot attribution handles the
    // accounting); suffix the group so two identically-named rows stay readable.
    for (size_t i(0); i < _players.size(); ++i)
    {
        if (i != playerIndex && _players[i] == _players[playerIndex])
        {
            return _players[playerIndex] + " (g" + std::to_string(_playerGroups[playerIndex]) + ")";
        }
    }

    return _players[playerIndex];
}


std::string Tournament::getTimeStringFromMS(const size_t ms)
{
    size_t totalSec = ms / 1000;

    size_t sec = totalSec % 60;
    size_t min = (totalSec / 60) % 60;
    size_t hour = (totalSec / 3600);

    std::stringstream ss;
    if (hour > 0)
    {
        ss << hour << "h ";
    }
    if (min > 0)
    {
        ss << min << "m ";
    }

    ss << sec << "s";
    return ss.str();
}
