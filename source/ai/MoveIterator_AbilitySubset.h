#pragma once

#include "Common.h"
#include "GameState.h"
#include "MoveIterator.h"
#include "MoveIterator_PPPortfolio.h"
#include "PartialPlayer.h"
#include "PartialPlayerSequence.h"
#include "CardFilter.h"
#include "IsomorphicCardSet.h"

namespace Prismata
{

// MoveIterator_AbilitySubset
// ---------------------------
// A ROOT-only move generator that lets the value net choose HOW MANY filter-matching
// utility abilities to fire (e.g. Infusion Grid / "Hotel" selfsac-clicks: 0, 1, ... N)
// by emitting each count as a distinct candidate child.
//
// It wraps an inner MoveIterator_PPPortfolio (the normal whole-turn generator) whose
// ACTION_ABILITY variant does NOT auto-fire the filtered card (so the subset enumerator
// owns those clicks). For each (inner variant-sequence) X (IG-subset k in 0..N) pair it:
//   1. runs DEFENSE + ACTION_ABILITY partial players (no IG fired),
//   2. inserts the k IG USE_ABILITY activations during the ACTION phase, then
//   3. RE-RUNS the ACTION_BUY + BREACH partial players FRESH on the post-IG state
//      (firing IG spends red, sacrifices a blocker and creates Husks -- buys/breach must
//       see the mutated state; cached inner-portfolio buy/breach moves must NOT be reused
//       for a different IG subset).
// Every emitted child ends in Phases::Confirm (the portfolio invariant). Exact-Move dedup
// collapses (variant, subset) pairs that yield identical moves.
class MoveIterator_AbilitySubset : public MoveIterator
{
    MoveIteratorPtr     m_innerPortfolio;       // resolved 'include' -- a MoveIterator_PPPortfolio (kept for clone)
    CardFilter          m_subsetFilter;         // which cards the subset branches on (e.g. IG_Only -> "Hotel")
    bool                m_hasFilter;

    std::vector<Move>   m_allMoves;             // fully materialized children (whole turns ending in Confirm)
    std::vector<Move>   m_movesPerformed;       // exact-Move dedup set
    size_t              m_currentMove;

    // ---- subset (IG) enumeration over filter-matching cards only ----
    std::vector<IsomorphicCardSet>  m_isoCardSets;      // iso sets restricted to filter-matching ability cards
    std::vector<size_t>             m_currentIsoIndex;
    std::vector<Move>               m_subsetMoves;       // distinct IG-activation Moves on a given post-ability state
    Move                            m_subsetStack;
    GameState                       m_subsetState;       // scratch state used during subset recursion

    void buildAllMoves();
    void enumerateSubsets(const GameState & postAbilityState);  // fills m_subsetMoves for this state
    void processFilteredIsomorphicCards(const GameState & state);
    void recurseSubset(size_t isoIndex);
    bool subsetTerminal(size_t isoIndex) const;

public:

    MoveIterator_AbilitySubset(const PlayerID playerID);

    void setInnerPortfolio(const MoveIteratorPtr & inner);
    void setSubsetFilter(const CardFilter & filter);

    virtual void            reset();
    virtual void            setState(const GameState & state);
    virtual void            setBuyLimits(const BuyLimits & buyLimits);

    virtual bool            generateNextChild(GameState & child, Move & movePerformed);
    virtual std::string     getDescription();
    virtual MoveIteratorPtr clone();
};

}
