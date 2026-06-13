#pragma once

#include <vector>
#include <cstddef>

namespace Prismata
{
namespace MoveSampler
{
    // Most-visited eligible index with a UNIFORM tie-break over the tied set (A1, 2026-06-13:
    // the old first-wins tie-break composed with the iterator's longest-move-first child order
    // to systematically resolve UCB-indifferent roots toward MORE IG clicks). u3 in [0,1) picks
    // among ties; deterministic given inputs. Only candidates with visits > 0 are eligible.
    // Returns 0 if there are no eligible candidates.
    size_t argmaxIndex(const std::vector<size_t> & visits, double u3);

    // Selects an index into `visits` for OPENING-regime self-play root sampling (turn < K).
    //   - Only candidates with visits > 0 are eligible.
    //   - With probability `epsilon` (when u1 < epsilon): sample UNIFORMLY over eligible candidates.
    //   - Otherwise: sample proportional to visits^(1/tau) (floating point).
    //   - tau <= 1e-6 degenerates to argmax (most-visited; uniform tie-break via u3).
    // u1, u2, u3 are uniform draws in [0,1). Deterministic given inputs (unit-testable; no RNG).
    // Returns 0 if there are no eligible candidates (caller guarantees >=1 in practice).
    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2, double u3);

    // LATE-regime self-play root selection (turn >= K): argmax with two layered exploration
    // mechanisms (J5, 2026-06-13).
    //   - argmax = most-visited eligible, uniform tie-break via u3 (== argmaxIndex(visits, u3),
    //     so the caller can recompute the argmax for stamping with the SAME u3).
    //   - TARGETED IG deviation: if u1 < epsilonIG AND the eligible candidates span >= 2 distinct
    //     igCounts, return the most-visited eligible candidate whose igCount differs from the
    //     argmax's igCount (ties among those broken uniformly via u2). This plays the search's
    //     best whole-turn line CONDITIONAL on a different IG click count — an on-axis
    //     counterfactual, not a random move.
    //   - UNIFORM late deviation: else if u1 < epsilonIG + epsilonLate, sample uniformly over
    //     eligible candidates via u2 (the legacy EpsilonLate mechanism; frozen 0 under regime v3).
    //   - Else: argmax.
    // igCounts must be the same length as visits. Deterministic given inputs (unit-testable).
    size_t sampleRootIndexLate(const std::vector<size_t> & visits,
                               const std::vector<int> & igCounts,
                               double epsilonIG, double epsilonLate,
                               double u1, double u2, double u3);
}
}
