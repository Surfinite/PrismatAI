#include "MoveIterator_AbilitySubset.h"
#include "AllPlayers.h"
#include "CanonicalOrderComparator.h"
#include "MoveIterator_AllAbility.h"   // for MoveLengthComparator

using namespace Prismata;

MoveIterator_AbilitySubset::MoveIterator_AbilitySubset(const PlayerID playerID)
    : m_hasFilter(false)
    , m_currentMove(0)
{
    _playerID = playerID;
    _hasMoreMoves = false;
}

void MoveIterator_AbilitySubset::setInnerPortfolio(const MoveIteratorPtr & inner)
{
    m_innerPortfolio = inner;
}

void MoveIterator_AbilitySubset::setSubsetFilter(const CardFilter & filter)
{
    m_subsetFilter = filter;
    m_hasFilter = true;
}

void MoveIterator_AbilitySubset::setBuyLimits(const BuyLimits & buyLimits)
{
    if (m_innerPortfolio)
    {
        m_innerPortfolio->setBuyLimits(buyLimits);
    }
}

void MoveIterator_AbilitySubset::setState(const GameState & state)
{
    _state = state;

    PRISMATA_ASSERT(state.getActivePlayer() == _playerID, "Player to move doesn't match move iterator playerID");

    reset();
}

void MoveIterator_AbilitySubset::reset()
{
    m_allMoves.clear();
    m_movesPerformed.clear();
    m_currentMove = 0;

    buildAllMoves();

    // sort longest-move-first to match MoveIterator_AllAbility ordering conventions
    std::sort(m_allMoves.begin(), m_allMoves.end(), MoveLengthComparator());

    _hasMoreMoves = !m_allMoves.empty();
}

// --------------------------------------------------------------------------------------
// Core: cross-product (inner portfolio variant-sequence) X (IG subset 0..N).
// For each variant sequence we drive the per-phase partial players ourselves so we can
// inject the IG activations between ACTION_ABILITY and ACTION_BUY, then re-run BUY+BREACH
// FRESH on the post-IG state (the consistency point).
// --------------------------------------------------------------------------------------
void MoveIterator_AbilitySubset::buildAllMoves()
{
    PRISMATA_ASSERT(m_innerPortfolio, "AbilitySubset has no inner portfolio");

    MoveIterator_PPPortfolio * portfolio = dynamic_cast<MoveIterator_PPPortfolio *>(m_innerPortfolio.get());
    PRISMATA_ASSERT(portfolio != nullptr, "AbilitySubset inner iterator must be a PPPortfolio");
    if (portfolio == nullptr)
    {
        return;
    }

    // Sizes of each phase's variant list (the inner portfolio odometer dimensions).
    std::vector<size_t> phaseSizes(PPPhases::NUM_PHASES, 0);
    for (size_t phase(0); phase < PPPhases::NUM_PHASES; ++phase)
    {
        phaseSizes[phase] = portfolio->numPartialPlayers(phase);
        PRISMATA_ASSERT(phaseSizes[phase] > 0, "Inner portfolio phase %d has no partial players", (int)phase);
        if (phaseSizes[phase] == 0)
        {
            return;
        }
    }

    const Action endPhase(_playerID, ActionTypes::END_PHASE, 0);

    // Odometer over the inner portfolio's per-phase variant indices.
    std::vector<size_t> idx(PPPhases::NUM_PHASES, 0);
    bool done = false;
    while (!done)
    {
        PPSequence sequence = portfolio->getSequence(idx);

        // ---- Phase 0 (DEFENSE) + Phase 1 (ACTION_ABILITY, IG excluded) on a base copy ----
        GameState baseState(_state);
        Move baseMove;   // defense + (IG-excluded) ability moves -- shared prefix for all subsets

        if (baseState.getActivePlayer() == _playerID && baseState.getActivePhase() == Phases::Defense)
        {
            sequence[PPPhases::DEFENSE]->getMove(baseState, baseMove);
        }

        if (baseState.getActivePlayer() == _playerID && baseState.getActivePhase() == Phases::Action)
        {
            sequence[PPPhases::ACTION_ABILITY]->getMove(baseState, baseMove);
        }

        // If for some reason we are no longer in the action phase (e.g. ability ended it),
        // we cannot inject IG; just finish this sequence as-is via a single (k=0) path below.
        const bool inActionPhase = (baseState.getActivePlayer() == _playerID && baseState.getActivePhase() == Phases::Action);

        // ---- Enumerate the IG subsets {0,1,...,N} on the post-ability base state ----
        m_subsetMoves.clear();
        if (inActionPhase && m_hasFilter)
        {
            enumerateSubsets(baseState);
        }

        // Always include the empty (k=0) subset so the base behaviour (fire no IG) is present.
        // enumerateSubsets pushes the empty move itself, but guard for the not-in-action case.
        if (m_subsetMoves.empty())
        {
            m_subsetMoves.push_back(Move());
        }

        // ---- For each IG subset, re-run BUY + BREACH fresh on the post-IG state ----
        for (const Move & igSubset : m_subsetMoves)
        {
            GameState igState(baseState);
            Move fullMove(baseMove);

            // Apply the IG activations (these are all legal on baseState by construction).
            if (igSubset.size() > 0)
            {
                igState.doMove(igSubset);
                fullMove.addMove(igSubset);
            }

            // BUY (does NOT end the phase by itself) then explicit END_PHASE -- mirrors Player_PPSequence.
            if (igState.getActivePlayer() == _playerID && igState.getActivePhase() == Phases::Action)
            {
                sequence[PPPhases::ACTION_BUY]->getMove(igState, fullMove);

                PRISMATA_ASSERT(igState.isLegal(endPhase), "Should be able to end phase after action+IG buy");
                igState.doAction(endPhase);
                fullMove.addAction(endPhase);
            }

            // BREACH (only present if firing IG / earlier play left a breach pending).
            if (igState.getActivePlayer() == _playerID && igState.getActivePhase() == Phases::Breach)
            {
                sequence[PPPhases::BREACH]->getMove(igState, fullMove);
            }

            // Must end in CONFIRM, exactly like the PPPortfolio invariant.
            PRISMATA_ASSERT(igState.getActivePhase() == Phases::Confirm,
                            "AbilitySubset sequence did not end in CONFIRM phase");
            if (igState.getActivePhase() != Phases::Confirm)
            {
                continue;
            }

            igState.doAction(endPhase);
            fullMove.addAction(endPhase);

            // exact-Move dedup
            if (std::find(m_movesPerformed.begin(), m_movesPerformed.end(), fullMove) == m_movesPerformed.end())
            {
                m_movesPerformed.push_back(fullMove);
                m_allMoves.push_back(fullMove);
            }
        }

        // ---- advance the inner-portfolio odometer (least-significant phase first) ----
        size_t carryPhase = PPPhases::NUM_PHASES;
        while (carryPhase > 0)
        {
            const size_t p = carryPhase - 1;
            idx[p] = (idx[p] + 1) % phaseSizes[p];
            if (idx[p] != 0)
            {
                break;  // no carry, odometer advanced
            }
            --carryPhase;   // rolled over -> carry to next more-significant phase
        }
        if (carryPhase == 0)
        {
            done = true;    // all dimensions rolled over -> exhausted
        }
    }
}

// --------------------------------------------------------------------------------------
// Subset enumeration: reuse MoveIterator_AllAbility's recurse/isomorphic machinery but
// RESTRICTED to filter-matching cards. Produces the set of distinct IG-activation Moves
// (including the empty "fire nothing" move). Bounded at N+1 outcomes for N identical IGs.
// IG ("Hotel") is a non-targeting utility ability so we only handle the non-target branch.
// --------------------------------------------------------------------------------------
void MoveIterator_AbilitySubset::enumerateSubsets(const GameState & postAbilityState)
{
    m_subsetMoves.clear();
    m_subsetStack.clear();
    m_isoCardSets.clear();
    m_subsetState = postAbilityState;

    processFilteredIsomorphicCards(m_subsetState);
    m_currentIsoIndex = std::vector<size_t>(m_isoCardSets.size(), 0);

    recurseSubset(0);

    // include the empty subset (fire zero IG)
    m_subsetMoves.push_back(Move());
}

void MoveIterator_AbilitySubset::processFilteredIsomorphicCards(const GameState & state)
{
    std::vector<CardID> abilityCardIDs;

    for (const auto & cardID : state.getCardIDs(_playerID))
    {
        const Card & card = state.getCardByID(cardID);

        // must have a (non-target) activated ability and not already be assigned/tapped
        if (!card.getType().hasAbility() || card.getType().hasTargetAbility() || (card.getStatus() == CardStatus::Assigned))
        {
            continue;
        }

        // RESTRICT to filter-matching cards only (e.g. IG / "Hotel"). The IG_Only filter
        // is {default:false, cards:["Hotel"]} so operator[] is TRUE only for Hotel.
        if (!m_subsetFilter[card.getType()])
        {
            continue;
        }

        abilityCardIDs.push_back(cardID);
    }

    std::sort(abilityCardIDs.begin(), abilityCardIDs.end(), CanonicalOrderComparator(state));

    for (const auto & cardID : abilityCardIDs)
    {
        bool found = false;
        for (auto & isoCardSet : m_isoCardSets)
        {
            if (isoCardSet.isIsomorphic(state, cardID))
            {
                found = true;
                isoCardSet.add(cardID);
                break;
            }
        }

        if (!found)
        {
            m_isoCardSets.push_back(IsomorphicCardSet());
            m_isoCardSets.back().add(cardID);
        }
    }
}

bool MoveIterator_AbilitySubset::subsetTerminal(size_t isoIndex) const
{
    if (isoIndex >= m_isoCardSets.size())
    {
        return true;
    }

    if (m_currentIsoIndex[isoIndex] > m_isoCardSets[isoIndex].size())
    {
        return true;
    }

    return false;
}

void MoveIterator_AbilitySubset::recurseSubset(size_t isoIndex)
{
    if (subsetTerminal(isoIndex))
    {
        return;
    }

    const std::vector<CardID> & cardIDs = m_isoCardSets[isoIndex].getCardIDs();
    const size_t cardIndex = m_currentIsoIndex[isoIndex];

    if (cardIndex < cardIDs.size())
    {
        const CardID useCardID = cardIDs[cardIndex];
        const Action useAbility(_playerID, ActionTypes::USE_ABILITY, useCardID);

        // IG is non-targeting; only fire if legal (pays red, has HP to selfsac, etc.)
        if (m_subsetState.isLegal(useAbility))
        {
            m_subsetState.doAction(useAbility);
            m_subsetStack.addAction(useAbility);

            // record this subset (fire 1..cardIndex+1 of this iso set, plus whatever earlier sets fired)
            m_subsetMoves.push_back(m_subsetStack);

            m_currentIsoIndex[isoIndex]++;

            // recurse: fire one more of this same iso type
            recurseSubset(isoIndex);

            // unroll
            const Action undoAbility(_playerID, ActionTypes::UNDO_USE_ABILITY, useCardID);
            m_subsetState.doAction(undoAbility);
            m_subsetStack.popAction();
            m_currentIsoIndex[isoIndex]--;
        }
    }

    // recurse: skip the rest of this iso type, move on to the next
    recurseSubset(isoIndex + 1);
}

bool MoveIterator_AbilitySubset::generateNextChild(GameState & child, Move & movePerformed)
{
    movePerformed.clear();

    if (!hasMoreMoves())
    {
        return false;
    }

    child = _state;
    movePerformed = m_allMoves[m_currentMove++];
    child.doMove(movePerformed);

    if (m_currentMove >= m_allMoves.size())
    {
        _hasMoreMoves = false;
    }

    return true;
}

MoveIteratorPtr MoveIterator_AbilitySubset::clone()
{
    MoveIterator_AbilitySubset * temp = new MoveIterator_AbilitySubset(_playerID);

    if (m_innerPortfolio)
    {
        temp->setInnerPortfolio(m_innerPortfolio->clone());
    }
    if (m_hasFilter)
    {
        temp->setSubsetFilter(m_subsetFilter);
    }

    return MoveIteratorPtr(temp);
}

std::string MoveIterator_AbilitySubset::getDescription()
{
    return "MoveIterator_AbilitySubset";
}
