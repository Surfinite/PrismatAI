#include "AITools.h"

#include "AIParameters.h"
#include "PrismataAssert.h"
#include "Game.h"
#include "Timer.h"
#include "Player_UCT.h"   // dynamic_cast for optional aivisits diagnostics

#include <cstdlib>   // std::getenv (FORCE_DSNN env override)
#include <fstream>   // std::ifstream (FORCE_DSNN sentinel-file check)

using namespace Prismata;

std::string AITools::InitializeAI(const std::string & initString)
{
    std::stringstream aistring;
    aistring << "{\"aiversion\":\"" << __DATE__ << " " << __TIME__ << "\", ";
    double jsonParseElapsed = 0;
    double cardInitElapsed = 0;
    double playerInitElapsed = 0;

    Timer t;
    t.start();

    try
    {
        // The initString must be properly formatted JSON
        rapidjson::Document document;
        bool parsingFailed = document.Parse(initString.c_str()).HasParseError();
        PRISMATA_ASSERT(!parsingFailed, "JSON Parsing of AI Parameters failed");
        jsonParseElapsed = t.getElapsedTimeInMilliSec();
        t.start();

        // The initString must contain a 'mergedDeck' array and an 'aiParameters' object
        PRISMATA_ASSERT(document.HasMember("mergedDeck"), "Init String does not contain a 'mergedDeck' variable");
        PRISMATA_ASSERT(document.HasMember("aiParameters"), "Init String does not contain an 'aiParameters' variable");

        Prismata::InitFromMergedDeckJSON(document["mergedDeck"]);
        cardInitElapsed = t.getElapsedTimeInMilliSec();
        t.start();

        // A12: load our config-defined (widened) iterator/partial/filter DEFINITIONS first (NO players,
        // so no eager NN weight loads), then merge the per-request SWF blob ON TOP without resetting, so
        // an injected player referencing a config-only iterator (HardIterator_5var_Root /
        // HardIterator_5var) resolves by name on the Steam-protocol path. Falls back to the old
        // blob-only behaviour if config.txt isn't found.
        std::string cfgPath = "asset/config/config.txt";
        {
            const std::string exeDir = NeuralNet::getExecutableDir();   // same mechanism --dump-features uses
            if (!exeDir.empty())
            {
                std::ifstream cfgTest(exeDir + "/" + cfgPath);
                if (cfgTest.good()) { cfgPath = exeDir + "/" + cfgPath; }
            }
        }
        // parseConfigDefsForMerge returns true only after it successfully reset the singleton and loaded
        // our config defs (no players). On a missing OR unparseable config.txt it returns false WITHOUT
        // resetting, so we fall back to the old blob-only path (parseJSONValue, which resets) -- this also
        // closes the gap where a config.txt *parse* error previously left the singleton un-reset before merge.
        if (AIParameters::Instance().parseConfigDefsForMerge(cfgPath))
        {
            AIParameters::Instance().parseJSONValueNoReset(document["aiParameters"]);  // merge the blob on top
        }
        else
        {
            AIParameters::Instance().parseJSONValue(document["aiParameters"]);          // fallback: blob only (old behaviour)
        }
        playerInitElapsed = t.getElapsedTimeInMilliSec();

        aistring << "\"aiinitcomment\":\"AI Initialization Successful\", ";
    }
    catch (std::exception e)
    {
        aistring << "\"aiinitcomment\":\"" << e.what() << "\", ";
    }
    
    aistring << "\"aiparsetimes\":[" << (int)jsonParseElapsed << ", " << (int)cardInitElapsed << ", " << (int)playerInitElapsed << "], ";
    aistring << "\"aiinfo\":\"" << CardTypes::GetAllCardTypes().size() << " units, " << AIParameters::Instance().getPlayerNames().size() << " AI players\"}"; 
    return aistring.str();
}

GameState AITools::GetStateFromInitString(const std::string & inputString)
{
    rapidjson::Document document;
    bool parsingFailed = document.Parse(inputString.c_str()).HasParseError();
    
    PRISMATA_ASSERT(!parsingFailed, "JSON Parsing of AI Parameters failed");
    PRISMATA_ASSERT(document.HasMember("gameState"), "AI Parameters does not contain a 'gameState' variable");

    const GameState initialState(document["gameState"]);

    return initialState;
}

std::string AITools::GetAIMove(const std::string & aiParamsString)
{
    Timer t;
    t.start();
    std::stringstream aistring;
    aistring << "{";

    rapidjson::Document document;
    bool parsingFailed = document.Parse(aiParamsString.c_str()).HasParseError();
    
    PRISMATA_ASSERT(!parsingFailed, "JSON Parsing of AI Parameters failed");
    PRISMATA_ASSERT(document.HasMember("gameState"), "AI Parameters does not contain a 'gameState' variable");
    PRISMATA_ASSERT(document.HasMember("aiPlayerName"), "AI Parameters does not contain an 'aiPlayerName' variable");

    std::stringstream comment;
    std::string clickString = "[]";

    bool airesign = false;
    Move m;

    try
    {
        // check if the incoming message is an error test
        if (document.HasMember("ErrorType") && document["ErrorType"].IsString())
        {
            const std::string & errorType = document["ErrorType"].GetString();

            PerformAIError(errorType);
        }

        const GameState initialState(document["gameState"]);

        PlayerPtr aiPlayer = AIParameters::Instance().getPlayer(initialState.getActivePlayer(), document["aiPlayerName"].GetString());

        // --- FORCE_DSNN override -------------------------------------------------
        // If env PRISMATA_FORCE_DSNN is set, ignore the requested AI player and run
        // UCT + NeuralNet using neural_weights_mixed_35prop.bin (override via env
        // PRISMATA_DSNN_WEIGHTS). Think time = the requested player's TimeLimit, but
        // 7000 -> 10000, so the in-game "7s Master Bot" (aiPlayerName HardestAI)
        // thinks ~10s: a timeable tell that the DSNN is active, plus a slightly
        // stronger opponent. The "3s" bot (HardAI, 3000) stays 3s. When the env var
        // is unset, aiPlayer keeps the value above and behavior is byte-identical.
        // Trigger: env var PRISMATA_FORCE_DSNN set, OR a sentinel file 'use_dsnn.txt'
        // sitting next to the executable (drop-in friendly -- no env var, no Steam).
        const char * forceEnv = std::getenv("PRISMATA_FORCE_DSNN");
        bool forceDSNN = (forceEnv != nullptr && forceEnv[0] != '\0');
        if (!forceDSNN)
        {
            const std::string exeDir = NeuralNet::getExecutableDir();
            if (!exeDir.empty())
            {
                std::ifstream sentinel(exeDir + "/use_dsnn.txt");
                forceDSNN = sentinel.good();
            }
        }
        if (forceDSNN)
        {
            const PlayerID activePlayer = initialState.getActivePlayer();
            const std::string requestedName = document["aiPlayerName"].GetString();

            // Read the requested player's TimeLimit from the parsed aiParameters.
            int requestedTimeLimit = 7000;
            if (document.HasMember("aiParameters") && document["aiParameters"].IsObject())
            {
                const rapidjson::Value & ap = document["aiParameters"];
                if (ap.HasMember("Players") && ap["Players"].IsObject()
                    && ap["Players"].HasMember(requestedName.c_str())
                    && ap["Players"][requestedName.c_str()].IsObject()
                    && ap["Players"][requestedName.c_str()].HasMember("TimeLimit")
                    && ap["Players"][requestedName.c_str()]["TimeLimit"].IsInt())
                {
                    requestedTimeLimit = ap["Players"][requestedName.c_str()]["TimeLimit"].GetInt();
                }
            }
            const int dsnnTimeLimit = (requestedTimeLimit == 7000) ? 10000 : requestedTimeLimit;

            const char * weightsEnv = std::getenv("PRISMATA_DSNN_WEIGHTS");
            const std::string weightsName = (weightsEnv && weightsEnv[0] != '\0')
                                          ? std::string(weightsEnv)
                                          : std::string("neural_weights_mixed_35prop.bin");

            NeuralNetPtr nn = std::make_shared<NeuralNet>();
            const bool nnOk = nn->loadWeights("asset/config/" + weightsName) || nn->loadWeights(weightsName);

            // HardIterator(_Root) match the tested DSNN_MBonly config and are
            // registered by InitializeAI from the request's aiParameters blob.
            MoveIteratorPtr rootI1 = AIParameters::Instance().getMoveIterator(Players::Player_One, "HardIterator_Root");
            MoveIteratorPtr rootI2 = AIParameters::Instance().getMoveIterator(Players::Player_Two, "HardIterator_Root");
            MoveIteratorPtr moveI1 = AIParameters::Instance().getMoveIterator(Players::Player_One, "HardIterator");
            MoveIteratorPtr moveI2 = AIParameters::Instance().getMoveIterator(Players::Player_Two, "HardIterator");

            if (nnOk && rootI1 && rootI2 && moveI1 && moveI2)
            {
                nn->buildCardTypeMapping();

                UCTSearchParameters params;
                params.setMaxPlayer(activePlayer);
                params.setTimeLimit((size_t)dsnnTimeLimit);
                params.setMaxTraversals(100000);
                params.setMaxChildren(40);
                params.setRootMoveIterator(Players::Player_One, rootI1);
                params.setRootMoveIterator(Players::Player_Two, rootI2);
                params.setMoveIterator(Players::Player_One, moveI1);
                params.setMoveIterator(Players::Player_Two, moveI2);
                params.setEvalMethod(EvaluationMethods::NeuralNet);
                params.setNeuralNet(nn);

                aiPlayer = PlayerPtr(new Player_UCT(activePlayer, params));

                fprintf(stderr, "FORCE_DSNN: '%s' -> UCT+NeuralNet, weights=%s, timeLimit=%dms\n",
                        requestedName.c_str(), weightsName.c_str(), dsnnTimeLimit);
            }
            else
            {
                fprintf(stderr, "FORCE_DSNN: could NOT build DSNN player (nnOk=%d, iterators=%d); "
                        "falling back to requested '%s'\n",
                        (int)nnOk, (int)(rootI1 && rootI2 && moveI1 && moveI2), requestedName.c_str());
            }
        }
        // --- end FORCE_DSNN override --------------------------------------------

        airesign = PlayerShouldResign(initialState, initialState.getActivePlayer());

        aiPlayer->getMove(initialState, m);  

        // we are returning a JSON notation string with two objects, "aiclicks" and "aicomment"
        // "aiclicks" is an array of click objects
        clickString = AITools::GetClickString(m, initialState);
        aistring << "\"aicomment\":\"AI Move Successfully Found\", ";

        // Optional UCT root diagnostics. Strictly gated on aiParameters.EmitDiagnostics==true,
        // so normal play (flag absent) is byte-identical. Only meaningful for Player_UCT.
        bool emitDiagnostics = false;
        if (document.HasMember("aiParameters") && document["aiParameters"].IsObject())
        {
            const rapidjson::Value & ap = document["aiParameters"];
            if (ap.HasMember("EmitDiagnostics") && ap["EmitDiagnostics"].IsBool())
            {
                emitDiagnostics = ap["EmitDiagnostics"].GetBool();
            }
        }
        if (emitDiagnostics)
        {
            Player_UCT * uctPlayer = dynamic_cast<Player_UCT *>(aiPlayer.get());
            if (uctPlayer != nullptr)
            {
                const std::vector<size_t> & visits = uctPlayer->lastRootVisits();
                aistring << "\"aivisits\": [";
                for (size_t i = 0; i < visits.size(); ++i)
                {
                    aistring << (i ? ", " : "") << visits[i];
                }
                aistring << "], ";
                aistring << "\"aiargmax\": " << uctPlayer->lastArgmaxIdx() << ", ";
                aistring << "\"aichosen\": " << uctPlayer->lastChosenIdx() << ", ";
            }
        }
    }
    catch (std::exception e)
    {
        fprintf(stderr, "C++ AI: AI Exception caught, returning empty move\n");

        comment.clear();
        comment << e.what();
        clickString = "[]";
    }
    
    double elapsed = t.getElapsedTimeInMilliSec();

    aistring << "\"airesign\":" << (airesign ? "true" : "false") << ", ";
    aistring << "\"aithinktime\":" << (int)elapsed << ", ";
    aistring << "\"aimovesize\":" << m.size() << ", ";
    aistring << "\"aiclicks\": " << clickString << "}";

    return aistring.str();
}

bool AITools::PlayerShouldResign(const GameState & state, const PlayerID playerID)
{
    // RL self-play / eval decision (frozen for the first campaign): the AI does NOT resign.
    // Games play to a real terminal / turn-cap so win-rate eval is unbiased and self-play value
    // targets are ground-truth. (A generic Playout-player verdict is unreliable for a strong NN,
    // and the playout is costly.) Flip ENABLE_RESIGNATION to re-enable the null-safe playout
    // criterion below. Applied identically to candidate and anchors on the standalone path.
    static const bool ENABLE_RESIGNATION = false;
    if (!ENABLE_RESIGNATION) { return false; }

    const PlayerID enemyID = state.getEnemy(playerID);

    EvaluationType selfScore = Eval::WillScoreSum(state, playerID);
    EvaluationType enemyScore = Eval::WillScoreSum(state, enemyID);

    std::cout << "Self Score: " << selfScore << "\n";
    std::cout << "Enemy Score: " << enemyScore << "\n";

    // if the enemy has less than 1.5 times as much as us, then we shouldn't resign yet
    if (selfScore * 1.3 >= enemyScore)
    {
        return false;
    }

    // set our own player as a decent player
    PlayerPtr p1 = AIParameters::Instance().getPlayer(0, (playerID == 0) ? "Playout" : "PlayoutBuyNothing");
    PlayerPtr p2 = AIParameters::Instance().getPlayer(1, (playerID == 1) ? "Playout" : "PlayoutBuyNothing");

    // If the playout players aren't registered for this request (e.g. an aiParameters blob that
    // doesn't define "Playout"/"PlayoutBuyNothing"), don't run the resignation playout -- skip it
    // rather than dereferencing a null player. Default: do not resign.
    if (!p1 || !p2)
    {
        fprintf(stderr, "PlayerShouldResign: playout players not registered; skipping resignation check\n");
        return false;
    }

    // play the game out
    Game g(state, p1, p2);
    g.play();

    std::cout << "Winner: " << g.getState().winner() << "\n";

    // resign if the dummy player beats us from here
    return (g.getState().winner() == enemyID);
}

// Called by the ActionScript client to initialize the AI and return a move from a given state
// inputString is in JSON format and consists of 4 top level parts:
// ---------------------------------------------------------------------------------------------
// mergedDeck: The initialization info for all the cards
// aiParameters: The initialization info for the ai
// gameState: The current game state we want to get a move for
// aiPlayerName: The AI player name we want to get a move for, which is defined in aiParameters
//
// AIThreadHandler::getExeMoveRequestString() returns the proper string to pass into here
std::string AITools::InitializeAIAndGetAIMove(const std::string & inputString)
{
    std::stringstream aiResponse;
    
    rapidjson::Document document;
    bool parsingFailed = document.Parse(inputString.c_str()).HasParseError();

    // we can call the normal initialization function on this since it contains a superset of the init info
    std::string initString = AITools::InitializeAI(inputString);
    initString.back() = ',';
    aiResponse << initString;
    
    // then we can call the normal get AI move because it also contains a superset of that info
    // there's a slight performance overhead in parsing the json twice but it's nicer to re-use all the code
    std::string moveString = AITools::GetAIMove(inputString);
    moveString[0] = ' ';

    aiResponse << moveString;

    return aiResponse.str();
}

void AITools::PerformAIError(const std::string & errorType)
{
    fprintf(stderr, "C++ AI: Performing AI Error: %s\n", errorType.c_str());

    if (errorType == "DivideByZero")
    {
        /*int a = 12;
        int b = 4;
        b = b - 1;
        a = a - b*4;

        int x = 20/a;
        a = x;
        std::cout << x << "\n";*/
    }
    else if (errorType == "AssertFalse")
    {
        PRISMATA_ASSERT(false, "C++ AI: This is an error test, asserting false!");
    }
    else if (errorType == "StackOverflow")
    {
        int b[1000];
        b[2]++;

        PerformAIError("StackOverflow");
    }
    else if (errorType == "FillHeapMemory")
    { 
        std::vector<int> bigVector(100000000, 3);
    }
    else if (errorType == "InfiniteLoop")
    {
        int sum = 0;

        while (true)
        {
            sum += sum + 1;
        }

        std::cout << sum << "\n";
    }
    else if (errorType == "VectorIndexOutOfRange")
    {
        std::vector<int> vec(100, 42);

        fprintf(stderr, "Reading vector out of bounds...\n");
        int test = vec[111];

        fprintf(stderr, "Writing vector out of bounds...\n");
        vec[666] = 7;

        fprintf(stderr, "Printing vec from out of bounds...\n");
        fprintf(stderr, "Vec[666] = %d\n", vec[666234432]);
    }
}
 
std::string AITools::GetTypeString(const PlayerID player, const GameState & state) 
{
    std::stringstream ss;

    for (size_t cb(0); cb<state.numCardsBuyable(); ++cb)
    {
        CardID cards = state.numCardsOfType(player, state.getCardBuyableByIndex(cb).getType());

        if (cards > 0)
        {
            ss << (int)player << " " << (int)cards << " " << state.getCardBuyableByIndex(cb).getType().getName() << std::endl;
        }
    }

    return ss.str();
}

std::string AITools::GetClickString(const Move & move, const GameState & state) 
{
    Move noUndoMove = move;//StripUndoActions(move, state);

    if (noUndoMove.size() == 0)
    {
        return "[]";
    }

    GameState copy(state);
    std::stringstream ss;

    ss << "[" << "\n";
    for (size_t a(0); a<noUndoMove.size(); ++a)
    {
        ss << "    " << GetClickString(noUndoMove.getAction(a), copy);
        ss << (a < noUndoMove.size() - 1 ? "," : "") << "\n";
        copy.doAction(noUndoMove.getAction(a));
    }
    ss << "]";

    return ss.str();
}

Move AITools::StripUndoActions(const Move & m, const GameState & state)
{
    Move noUndo;

    const CardType droneType = CardTypes::CardTypeExists("Drone") ? CardTypes::GetCardType("Drone") : CardTypes::None;

    std::vector<bool> undone(m.size(), false);
    for (size_t i(0); i < m.size(); ++i)
    {
        const Action & a = m.getAction(i);

        if (undone[i])
        {
            continue;
        }

        if (a.getShift() || a.getType() != ActionTypes::USE_ABILITY)
        {
            continue;
        }

        // let the drones untap, looks nice that way
        if (state.getCardByID(a.getID()).getType() == droneType)
        {
            continue;
        }

        for (size_t j(i+1); j < m.size(); ++j)
        {
            if (undone[j])
            {
                continue;
            }

            const Action & b = m.getAction(j);

            if (b.getType() == ActionTypes::UNDO_USE_ABILITY && b.getID() == a.getID() && b.getType())
            {
                undone[i] = true;
                undone[j] = true;
                break;
            }
        }
    }

    for (size_t i(0); i < m.size(); ++i)
    {
        if (!undone[i])
        {
            noUndo.addAction(m.getAction(i));
        }
    }

    // test to see if we get the same state from the stripped and normal versions
    GameState normalTest(state);
    GameState strippedTest(state);

    // do the normal moves
    for (size_t i(0); i < m.size(); ++i)
    {
        if (normalTest.isLegal(m.getAction(i)))
        {
            normalTest.doAction(m.getAction(i));
        }
    }

    for (size_t i(0); i < noUndo.size(); ++i)
    {
        if (strippedTest.isLegal(noUndo.getAction(i)))
        {
            strippedTest.doAction(noUndo.getAction(i));
        }
        else
        {
            // if the stripped move isn't legal then we can't use this undo sequence
            return m;
        }
    }

    // if the resulting states are perfectly isometric we can return the move with no undos
    if (strippedTest.isIsomorphic(normalTest))
    {
        return noUndo;
    }
    // otherwise we have to return the original move
    else
    {
        return m;
    }
}

std::string AITools::GetClickString(const Action & a, const GameState & state) 
{
    std::stringstream ss;
    const std::string shift = a.getShift() ? " shift " : " ";
    const std::string instPrefix = "{\"type\":\"inst" + shift + "clicked\", \"args\":";

    if (a.getType() == ActionTypes::ASSIGN_BLOCKER)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::ASSIGN_BREACH)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::BUY)
    {
        ss << "{\"type\":\"card" << shift << "clicked\", \"args\":\"" << state.getCardBuyableByID(a.getID()).getType().getName() << "\"}";
    }
    else if (a.getType() == ActionTypes::END_PHASE)
    {
        ss << "{\"type\":\"space clicked\"}";
    }
    else if (a.getType() == ActionTypes::USE_ABILITY)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::UNDO_USE_ABILITY)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::ASSIGN_FRONTLINE)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::CHILL)
    {
        //ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "},";
        ss << instPrefix << state.getCardByID(a.getTargetID()).toJSONString() << "}";
    }
	else if (a.getType() == ActionTypes::SNIPE)
	{
		//ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "},";
		ss << instPrefix << state.getCardByID(a.getTargetID()).toJSONString() << "}";
	}
    else if (a.getType() == ActionTypes::UNDO_CHILL)
    {
        ss << instPrefix << state.getCardByID(a.getID()).toJSONString() << "}";
    }
    else if (a.getType() == ActionTypes::WIPEOUT)
    {
        ss << "{\"type\":\"space clicked\"}";
    }
    else
    {
        PRISMATA_ASSERT(false, "Unknown action to clickstring type with id: %d", (int)a.getType());
    }
    
    return ss.str();
}

Move AITools::GetMoveFromClickString(const std::string & clickString, const PlayerID player, const GameState & state)
{
    rapidjson::Document document;
    bool parsingFailed = document.Parse(clickString.c_str()).HasParseError();

    PRISMATA_ASSERT(!parsingFailed, "Parsing of click string failed");
    PRISMATA_ASSERT(document.IsArray(), "Click string should be array");

    GameState currentState(state);
    Move move;

    for (size_t i(0); i < document.Size(); ++i)
    {
        PRISMATA_ASSERT(document[i].IsObject(), "Click must be an object");

        const rapidjson::Value & click = document[i];

        Action action = GetActionFromClickJSON(click, player, currentState, clickString, state);

        PRISMATA_ASSERT(currentState.isLegal(action), "Action from GetActionFromClickJSON not legal %s\n\n%s", action.toString().c_str(), AITools::GetClickString(action, currentState).c_str());

        currentState.doAction(action);
        move.addAction(action);
    }

    return move;
}

Action AITools::GetActionFromClickJSON(const rapidjson::Value & click, const PlayerID player, const GameState & state, const std::string & clickString, const GameState & originalState)
{
    PRISMATA_ASSERT(click.IsObject(), "Click is not an object");
    PRISMATA_ASSERT(click.HasMember("type") && click["type"].IsString(), "Click does not have a type string");

    const std::string & type = click["type"].GetString();
    
    if (type == "inst clicked")
    {
        PRISMATA_ASSERT(click.HasMember("args") && click["args"].IsObject(), "inst click does not have an args object");
        
        Card card(click["args"]);
        int isomorphicCardID = FindIsomorphicCardID(card, state);

        PRISMATA_ASSERT(isomorphicCardID != -1, "No isomorphic card was found: %s\n%s", card.toJSONString().c_str(), clickString.c_str());
        
        return state.getClickAction(state.getCardByID((CardID)isomorphicCardID));        
    }
    else if (type == "inst shift clicked")
    {
        PRISMATA_ASSERT(click.HasMember("args") && click["args"].IsObject(), "inst click does not have an args object");
        
        Card card(click["args"]);
        int isomorphicCardID = FindIsomorphicCardID(card, state);

        PRISMATA_ASSERT(isomorphicCardID != -1, "No isomorphic card was found: %s\n%s", card.toJSONString().c_str(), clickString.c_str());

        Action action = state.getClickAction(state.getCardByID((CardID)isomorphicCardID));
        action.setShift(true);

        return action;
    }
    else if (type == "card clicked")
    {
        PRISMATA_ASSERT(click.HasMember("args") && click["args"].IsString(), "card clicked does not have an args string");
        const std::string & cardTypeName = click["args"].GetString();
        PRISMATA_ASSERT(CardTypes::CardTypeExists(cardTypeName), "Card type of card clicked doesn't exist: %s", cardTypeName.c_str());

        return Action(player, ActionTypes::BUY, CardTypes::GetCardType(cardTypeName).getID());
    }
    else if (type == "space clicked")
    {
        return Action(player, ActionTypes::END_PHASE, 0);
    }
    else
    {
        PRISMATA_ASSERT(false, "Unknown click type: %s", type.c_str());
    }

    PRISMATA_ASSERT(false, "Click conversion failed: %s", type.c_str());

    return Action();
}

int AITools::FindIsomorphicCardID(const Card & card, const GameState & state)
{
    for (const auto & cardID : state.getCardIDs(card.getPlayer()))
    {
        if (state.getCardByID(cardID).isIsomorphic(card))
        {
            return cardID;
        }
    }

    for (const auto & cardID : state.getKilledCardIDs(card.getPlayer()))
    {
        if (state.getCardByID(cardID).isIsomorphic(card))
        {
            return cardID;
        }
    }
    
    return -1;
}

void AITools::PredictEnemyNextTurn(GameState & state, bool solveDefense)
{
    const int startingPhase = state.getActivePhase();
    const PlayerID player = state.getActivePlayer();
    const PlayerID enemy = state.getInactivePlayer();
    Move moves[2] = {Move(), Move()};
    moves[0].clear();
    moves[1].clear();

    // we start on the active player's turn and assume that we will be sending over the current amount of attack
    const Action endPhase(player, ActionTypes::END_PHASE, 0);

    PartialPlayer_Defense_Solver defensePlayersSolve[2] = {  PartialPlayer_Defense_Solver(Players::Player_One, &Heuristics::DamageLoss_AttackValue), 
                                                                    PartialPlayer_Defense_Solver(Players::Player_Two, &Heuristics::DamageLoss_AttackValue)};

    if (state.getActivePhase() == Phases::Defense)
    {
        defensePlayersSolve[player].getMove(state, moves[player]);
        state.doAction(endPhase);
    }

    // if it's the action phase we just want to pass and do nothing else, let the calling function decide how much we've attacked for
    if (state.getActivePhase() == Phases::Action)
    {
        PRISMATA_ASSERT(state.isLegal(endPhase), "We should be able to end here");
        state.doAction(endPhase);
    }
        
    // if we've gone to the breach phase, call the knapsack breacher to get a good idea on what we would have done during breach
    if (state.getActivePhase() == Phases::Breach)
    {
        PartialPlayer_Breach_GreedyKnapsack breachPartialPlayers[2] = {PartialPlayer_Breach_GreedyKnapsack(0, true), PartialPlayer_Breach_GreedyKnapsack(1, true)};
        
        // calling getMove actually advances the passed-in state, so we don't need to worry about getting the moves and re-doing them
        breachPartialPlayers[player].getMove(state, moves[player]);
    }
    
    PRISMATA_ASSERT(state.getActivePhase() == Phases::Confirm, "We should be at the confirm phase now");
    state.doAction(endPhase);

    PRISMATA_ASSERT(state.isGameOver() || state.getActivePlayer() == enemy, "It should be the enemy's turn now");

    if (state.isGameOver())
    {
        return;
    }

    // if the enemy has to block, run a greedy knapsack minimzing the attack they lose due to blocking
    if (state.getActivePhase() == Phases::Defense)
    {
        PartialPlayer_Defense_GreedyKnapsack defensePlayersKnapsack[2] = {   PartialPlayer_Defense_GreedyKnapsack(Players::Player_One, &Heuristics::DefenseHeuristicSaveAttackers), 
                                                                                    PartialPlayer_Defense_GreedyKnapsack(Players::Player_Two, &Heuristics::DefenseHeuristicSaveAttackers)};

        if (solveDefense)
        {
            defensePlayersSolve[enemy].getMove(state, moves[enemy]);
        }
        else
        {
            defensePlayersKnapsack[enemy].getMove(state, moves[enemy]);
        }
    }

    // Thread-local prediction players avoid repeated construction without sharing mutable partial-player state across threads.
    static thread_local PPPtr predictionPlayers[2] = { GetPredictionPlayer(0), GetPredictionPlayer(1) };

    PRISMATA_ASSERT(state.getActivePhase() == Phases::Action, "Should be enemy action phase right now");

    // simulate the enemy's next action phase
    predictionPlayers[enemy]->getMove(state, moves[enemy]); 
}

// calculate how much loss player would incur if he got wiped out (all blockers die)
double AITools::CalculateWipeoutLoss(GameState & state, const PlayerID player)
{
    double wipeoutLoss = 0;
    for (const auto & cardID : state.getCardIDs(player))
    {
        const Card & card = state.getCardByID(cardID);

        // if the card can currently block, add the loss from it taking full damage
        if (card.canBlock())
        {
            double cardDeathLoss = Heuristics::DamageLoss_WillCost(card, state, card.currentHealth());
            wipeoutLoss += cardDeathLoss;
        }
    }

    return wipeoutLoss;
}

double AITools::CalculateEnemyNextTurnDefenseLoss(GameState & state)
{
    const int startingPhase = state.getActivePhase();
    const PlayerID player = state.getActivePlayer();
    const PlayerID enemy = state.getInactivePlayer();
    Move moves[2] = {Move(), Move()};
    moves[0].clear();
    moves[1].clear();
    
    // precompute the loss the enemy would incur if he was wiped out
    double wipeoutLoss = CalculateWipeoutLoss(state, enemy);

    // we start on the active player's turn and assume that we will be sending over the current amount of attack
    const Action endPhase(player, ActionTypes::END_PHASE, 0);

    // if it's the action phase we just want to pass and do nothing else, let the calling function decide how much we've attacked for
    if (state.getActivePhase() == Phases::Action)
    {
        PRISMATA_ASSERT(state.isLegal(endPhase), "We should be able to end here");
        state.doAction(endPhase);
    }
        
    // if we've gone to the breach phase, call the knapsack breacher to get a good idea on what we would have done during breach
    if (state.getActivePhase() == Phases::Breach)
    {
        PartialPlayer_Breach_GreedyKnapsack breachPartialPlayers[2] = {PartialPlayer_Breach_GreedyKnapsack(0, true), PartialPlayer_Breach_GreedyKnapsack(1, true)};
        
        // calling getMove actually advances the passed-in state, so we don't need to worry about getting the moves and re-doing them
        breachPartialPlayers[player].getMove(state, moves[player]);
        
        return wipeoutLoss + breachPartialPlayers[player].getTotalBreachDamageLoss();

        state.doAction(endPhase);
    }

    PRISMATA_ASSERT(state.getActivePhase() == Phases::Confirm, "We should be at the confirm phase now");
    state.doAction(endPhase);
    PRISMATA_ASSERT(state.isGameOver() || state.getActivePlayer() == enemy, "It should be the enemy's turn now");

    // if the enemy has to block, run a greedy knapsack minimzing the attack they lose due to blocking
    if (state.getActivePhase() == Phases::Defense)
    {
        BlockIterator blockIterator(state, &Heuristics::DamageLoss_WillCost);
        blockIterator.solve();

        return blockIterator.getMinLossScore();
    }
    // if the wipeout killed them
    else if (state.numCards(enemy) == 0)
    {
        return wipeoutLoss;
    }
    else
    {
        return 0;
    }
}

PPPtr AITools::GetPredictionPlayer(const PlayerID player)
{
    std::vector<PPPtr> combo;

    // assume they activate and attack with all
    combo.push_back(PPPtr(new PartialPlayer_ActionAbility_EconomyDefault(player)));
    combo.push_back(PPPtr(new PartialPlayer_ActionAbility_AttackDefault(player, CardFilter())));

    // assume they snipe your highest hp defender
    combo.push_back(PPPtr(new PartialPlayer_ActionAbility_SnipeGreedyKnapsack(player, Heuristics::SnipeHighestDefense)));

    return PPPtr(new PartialPlayer_ActionAbility_Combination(player, combo));
}

void AITools::TestParseJSONString(const std::string & jsonString)
{
    rapidjson::Document document;
    bool parsingFailed = document.Parse(jsonString.c_str()).HasParseError();

    if (parsingFailed)
    {
        int errorPos = document.GetErrorOffset();

        std::stringstream ss;
        ss << std::endl << "JSON Parse Error: " << document.GetParseError() << std::endl;
        ss << "Error Position:   " << errorPos << std::endl;
        ss << "Error Substring:  " << jsonString.substr(errorPos-15, 25) << std::endl;

        PRISMATA_ASSERT(!parsingFailed, "Error parsing JSON config file: %s", ss.str().c_str());
    }
}

bool AITools::PurchaseIsOutOfSync(const PlayerID player, const CardType type, const GameState & state)
{
    TurnType delay = std::max(type.getAbilityScript().getDelay(), type.getBeginOwnTurnScript().getDelay());

    if (delay < 2)
    {
        return false;
    }

    if (state.numCardsOfType(player, type) == 0)
    {
        return false;
    }

    // so there must exist at least one card fo this type for this player which has a delay or is under construction
    for (const auto & cardID : state.getCardIDs(player))
    {
        const Card & card = state.getCardByID(cardID);

        if (card.getType() != type)
        {
            continue;
        }

        const TurnType cardDelay = std::max(card.getConstructionTime(), card.getCurrentDelay());

        if (type.getConstructionTime() != cardDelay)
        {
            return true;
        }
    }

    return false;
}

size_t AITools::NumResonatorsReady(const CardType type, const GameState & state, const PlayerID player, const TurnType maxConstructionTime)
{
    size_t resonatorsFound = 0;
    for (const auto & resonateToID : type.getResonateToIDs())
    {
        const CardType resonatorType = CardType(resonateToID);

        // if we have one of the resonator cards
        if (state.numCardsOfType(player, resonatorType) > 0)
        {
            // find it and make sure it's build time 1 or less
            for (const auto & cardID : state.getCardIDs(player))
            {
                const Card & card = state.getCardByID(cardID);
                if (card.getType() == resonatorType && card.getConstructionTime() <= maxConstructionTime)
                {
                    resonatorsFound++;
                }
            }
        }
    }

    return resonatorsFound;
}

Resources AITools::GetReceiveFromResonators(const CardType type, const GameState & state, const PlayerID player, const TurnType maxConstructionTime)
{
    Resources contribution;
    for (const auto & resonateToID : type.getResonateToIDs())
    {
        const CardType resonatorType = CardType(resonateToID);

        // if we have one of the resonator cards
        if (state.numCardsOfType(player, resonatorType) > 0)
        {
            // find it and make sure it's build time 1 or less
            for (const auto & cardID : state.getCardIDs(player))
            {
                const Card & card = state.getCardByID(cardID);
                if (card.getType() == resonatorType && card.getConstructionTime() <= maxConstructionTime)
                {
                    contribution.add(resonatorType.getBeginOwnTurnScript().getResonateEffect().getReceive());
                }
            }
        }
    }

    return contribution;
}

Resources AITools::GetReceiveFromResonatees(const CardType type, const GameState & state, const PlayerID player, const TurnType maxConstructionTime)
{
    Resources receive;
    size_t numResonatees = NumResonateesReady(type, state, player, maxConstructionTime);

    for (size_t r(0); r < numResonatees; ++r)
    {
        receive.add(type.getBeginOwnTurnScript().getResonateEffect().getReceive());
    }

    return receive;
}

size_t AITools::NumResonateesReady(const CardType type, const GameState & state, const PlayerID player, const TurnType maxConstructionTime)
{
    size_t resonateesFound = 0;
    for (const auto & resonateFromID : type.getResonateFromIDs())
    {
        const CardType resonateeType = CardType(resonateFromID);

        // if we have one of the resonator cards
        if (state.numCardsOfType(player, resonateeType) > 0)
        {
            // find it and make sure it's build time 1 or less
            for (const auto & cardID : state.getCardIDs(player))
            {
                const Card & card = state.getCardByID(cardID);
                if (card.getType() == resonateeType && card.getConstructionTime() <= maxConstructionTime)
                {
                    resonateesFound++;
                }
            }
        }
    }

    return resonateesFound;
}
