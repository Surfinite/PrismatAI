#pragma once

#include <map>
#include <utility>

namespace Prismata
{
// (owner, cardTypeID) -> count over live units. Plain ints so this header has no engine deps
// and is unit-testable in isolation.
typedef std::map<std::pair<int, int>, int> PopulationMultiset;

// Mirrors eval/stalemate.py StalemateTracker. PRIMARY signal: the population multiset unchanged
// across consecutive turn-start states. See the design spec
// (docs/superpowers/specs/2026-06-16-selfplay-stalemate-draw-policy-design.md).
struct StalemateTracker
{
    int threshold = 0;          // plies; <= 0 disables firing
    int noChangeCount = 0;
    int lastProgressPly = 0;
    bool havePrev = false;
    PopulationMultiset prevSig;

    // Feed one turn-start multiset at index plyIndex. Returns true iff stalled (>= threshold).
    bool observe(const PopulationMultiset & sig, int plyIndex)
    {
        if (!havePrev || sig != prevSig)
        {
            noChangeCount = 0;
            lastProgressPly = plyIndex;
        }
        else
        {
            ++noChangeCount;
        }
        prevSig = sig;
        havePrev = true;
        return threshold > 0 && noChangeCount >= threshold;
    }
};
}
