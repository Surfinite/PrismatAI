#pragma once

#include <limits>
#include <vector>

#include "Timer.h"
#include "GameState.h"
#include "UCTSearchParameters.hpp"
#include "UCTSearchResults.hpp"
#include "UCTNode.h"
#include "UCTMemoryPool.hpp"
#include "Eval.h"
#include "GraphViz.hpp"

namespace Prismata
{

class Game;
class Player;

class UCTSearch
{
    UCTSearchParameters     _params;
    UCTSearchResults        _results;
    Timer                   _searchTimer;
    UCTNode                 _rootNode;

    GameState               _initialState;

    // Root diagnostics from the most recent REAL move selection (allowSampling==true).
    // Win-rate / description calls (allowSampling==false) never touch these.
    std::vector<size_t>     _lastRootVisits;   // per-root-child visit counts
    int                     _lastChosenIdx = -1;
    int                     _lastArgmaxIdx = -1;
    bool                    _rootTruncated = false;   // MaxChildren cap bound at the root + iterator had more (candidates dropped)
    double                  _lastRootWinRate = 0.5;   // chosen root child's backed-up win rate, MAXPLAYER perspective
                                                      // (B1/A6 2026-06-13: the end-to-end orientation signal — a maxPlayer
                                                      // sign flip in NeuralNet::evaluateValue inverts this)

public:

    UCTSearch(const UCTSearchParameters & params);

    // UCT-specific functions
    UCTNode &           UCTNodeSelect(UCTNode & parent);
    double              traverse(UCTNode & node);
    void                uct(GameState & state, size_t depth, const int lastPlayerToMove);
    UCTNode *           getBestRootNode(bool allowSampling);
    std::vector<int>    rootChildIGClickCounts();   // per-root-child Infusion-Grid click counts (J5 targeted exploration)
    double              getBestRootWinRate();
    void                computeRootPriors();

    bool                searchShouldStop();
    void                updateResults(bool forceUpdate = false);
    void                doSearch(const GameState & initialState, Move & move);
    
    // Move and Child generation functions
    void                generateChildren(UCTNode & node, GameState & state);
    void                makeMove(UCTNode & node, GameState & state);

    // Utility functions
    const PlayerID      getPlayerToMove(UCTNode & node, const GameState & state) const;
    bool          searchTimeOut();
    bool          isRoot(UCTNode & node) const;
    bool          isTerminalState(GameState & state, const size_t & depth) const;
    void                updateState(UCTNode & node, GameState & state, bool isLeaf);
    void                setMemoryPool(UCTMemoryPool * pool);
    UCTSearchResults &  getResults();
    const UCTNode &     getRootNode();

    // Root diagnostics accessors (populated only on real move selection).
    const std::vector<size_t> & lastRootVisits() const { return _lastRootVisits; }
    int                 lastChosenIdx() const { return _lastChosenIdx; }
    int                 lastArgmaxIdx() const { return _lastArgmaxIdx; }
    bool                rootTruncated() const { return _rootTruncated; }
    double              lastRootWinRate() const { return _lastRootWinRate; }

    // graph printing functions
    void                printSubTree(const UCTNode & node, GameState state, std::string filename, size_t maxDepth);
    void                printSubTreeGraphViz(const UCTNode & node, GraphViz::Graph & g, GameState state, size_t maxDepth, size_t depth);
    std::string         getNodeIDString(const UCTNode & node);

    std::string         getDescription();

};
}