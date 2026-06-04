#pragma once

#include "Common.h"
#include "MoveIterator.h"
#include "GameState.h"
#include <math.h>
#include "UCTSearchParameters.hpp"

namespace Prismata
{


class UCTNode
{
    size_t                      _numVisits;         // total visits to this node
    double                      _numWins;           // wins from this node
    double                      _uctVal;            // previous computed UCT value
    double                      _policyPrior;       // PUCT policy prior (default 1.0 = uniform)

    PlayerID                    _playerWhoMoved;    // the player who made a move to generate this node
    Move                        _move;              // the move that generated this node

    MoveIteratorPtr             _moveIterator;
    size_t                      _maxChildren;

    std::vector<UCTNode>        _children;

    UCTNode *                   _parent;
    std::string                 _description;
    
public:

    UCTNode ();
    UCTNode (UCTNode * parent, const GameState & state, const PlayerID playerWhoMoved, const Move & move, const UCTSearchParameters & params, const char * desc = NULL);

    const size_t            numVisits()                 const;
    const size_t            numChildren()               const;

    // True iff child generation stopped because the MaxChildren cap bound while the move
    // iterator still had candidates to emit (i.e. root candidates were silently dropped in
    // the iterator's non-value-aware emission order).
    //
    // Semantics: in normal UCT (PUCT disabled — the default) children are generated LAZILY
    // during traverse(), not all upfront. After the search this reflects whether the iterator
    // had pending moves the LAST time generation stopped. The guard mirrors the exact stop
    // condition in generateNextChild() (`_children.size() >= _maxChildren`). For the IG
    // MoveIterator_AbilitySubset, _hasMoreMoves stays true while m_currentMove < m_allMoves
    // (precomputed in reset()), so hasMoreMoves() correctly reports pending-after-cap. For
    // IG-only this is moot (numChildren ~8 < 40 cap → never truncated) but is correct for
    // when the action-space filters widen and can approach/exceed MaxChildren.
    bool wasChildGenerationTruncated() const
    {
        return (_children.size() >= _maxChildren) && _moveIterator && _moveIterator->hasMoreMoves();
    }

    const double            numWins()                   const;
    const double            getUCTVal()                 const;
    const double            getPolicyPrior()            const;
    bool              hasChildren()               const;
    bool              hasChildrenToGenerate()     const;
    const PlayerID          getPlayerWhoMoved()         const;
    const GameState &       getState()                  const;
    std::vector<UCTNode> &  getChildren();

    std::string             getDescription()            const;

    UCTNode *               getParent()                 const;
    UCTNode &               getChild(const size_t & c);
    const UCTNode &         getChild(const size_t & c)  const;
    UCTNode &               mostVisitedChild();
    UCTNode &               bestUCTValueChild(bool maxPlayer, const UCTSearchParameters & params);

    void                    setUCTVal(double val);
    void                    setPolicyPrior(double prior);
    void                    incVisits();
    void                    addWins(double val);
    void                    setDescription(std::string & desc);

    

    const Move & getMove() const;

    int memoryUsed();

    void setMove(const Move & move);
    bool generateNextChild(const UCTSearchParameters & params);
    
    void generateAllChildren(const UCTSearchParameters & params);

    
    bool containsChildMove(const Move & move) const;
};
}