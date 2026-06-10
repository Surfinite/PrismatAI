#pragma once

#include "PrismataAI.h"
#include "../engine/Prismata.h"
#include "BuyLimits.h"
#include <map>
#include <vector>

namespace Prismata
{

struct DominionState
{
    std::string Name = "Default";
    int RandomCards = 0;
};

class AIParameters
{   
    rapidjson::Value                        _rootValue;
    
    std::vector<std::string>                _playerKeyNames;
    std::vector<std::string>                _partialPlayerKeyNames;
    std::vector<std::string>                _stateKeyNames;
    std::vector<std::string>                _moveIteratorKeyNames;
    std::vector<std::string>                _openingBookKeyNames;
    std::vector<std::string>                _filterKeyNames;
    std::vector<std::string>                _buyLimitKeyNames;

    std::map<std::string, PPPtr>            _partialPlayerMap[2];
    std::map<std::string, PlayerPtr>        _playerMap[2];
    std::map<std::string, MoveIteratorPtr>  _moveIteratorMap[2];
    std::map<std::string, OpeningBook>      _openingBookMap[2];
    std::map<std::string, size_t>           _openingBookRawEntryCounts;     // entry count as DEFINED in the JSON, before current-library validity filtering
    std::map<std::string, CardFilter>       _cardFilters;
    std::map<std::string, BuyLimits>        _buyLimits;
    std::map<std::string, GameState>        _stateMap;
    std::map<std::string, DominionState>    _dominionStates;

    std::vector<std::string>                _playerNames;
    std::vector<std::string>                _partialPlayerNames;
    std::vector<std::string>                _stateNames;

    size_t                                  _partialPlayerParses;
    size_t                                  _playerParses;
    size_t                                  _moveIteratorParses;

    const rapidjson::Value & findCardFilter(const std::string & filterName, const rapidjson::Value & rootValue);
    const rapidjson::Value & findPlayer(const std::string & playerName, const rapidjson::Value & rootValue);
    const rapidjson::Value & findPartialPlayer(const std::string & playerName, const rapidjson::Value & rootValue);
    const rapidjson::Value & findMoveIterator(const std::string & iteratorName, const rapidjson::Value & rootValue);

    void                parseFilters(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parseBuyLimits(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parseOpeningBooks(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parsePartialPlayers(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parseMoveIterators(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parsePlayers(const std::string & keyName, const rapidjson::Value & rootValue);
    void                parseStates(const std::string & keyName, const rapidjson::Value & rootValue);

    // Parses all AI-parameter sections from rootValue into the CURRENT singleton (NO reset).
    // addHumanPlayers: append the two Player_GUI "Human" entries (true only for the full reset path).
    // doParsePlayers:  parse the "Players" section (false to load defs only -- avoids eager NN weight loads).
    void                parseSections(const rapidjson::Value & rootValue, bool addHumanPlayers, bool doParsePlayers);
    
    CardFilter          parseCardFilter(const std::string & filterVariable, const rapidjson::Value & root);
    PPPtr               parsePartialPlayer(const PlayerID player, const std::string & playerVariable, const rapidjson::Value & root);
    PlayerPtr           parsePlayer(const PlayerID player, const std::string & playerVariable, const rapidjson::Value & root);
    MoveIteratorPtr     parseMoveIterator(const PlayerID player, const std::string & iteratorVariable, const rapidjson::Value & root);

    static GameState    GetStateFromVariable(const std::string & stateVariable, const rapidjson::Value & root);
    
    AIParameters();

public:

    static AIParameters & Instance();

    void                parseJSONValue(const rapidjson::Value & rootValue);
    void                parseJSONString(const std::string & jsonString);
    void                parseFile(const std::string & filename);

    // A12: merge a per-request blob (incl. its Players) ON TOP of the current singleton WITHOUT resetting.
    void                parseJSONValueNoReset(const rapidjson::Value & rootValue);
    // A12: reset, then load DEFINITIONS ONLY (no Players -> no eager NN weight loads) from a config file.
    // On file open/parse failure, prints a stderr warning and returns false WITHOUT resetting (caller can
    // fall back to blob-only). Returns true after a successful reset + defs load.
    bool                parseConfigDefsForMerge(const std::string & filename);

    PlayerPtr           getPlayer(const PlayerID player, const std::string & playerName);
    PPPtr               getPartialPlayer(const PlayerID player, const std::string & playerName);
    MoveIteratorPtr     getMoveIterator(const PlayerID player, const std::string & iteratorName);
    GameState           getState(const std::string & stateName);

    const std::vector<std::string> & getStateNames() const;
    const std::vector<std::string> & getPlayerNames() const;
    const std::vector<std::string> & getPartialPlayerNames() const;

};
}