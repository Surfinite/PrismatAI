#pragma once

#include <vector>
#include <cstddef>

namespace Prismata
{
namespace MoveSampler
{
    // Selects an index into `visits` for self-play root-move sampling.
    //   - Only candidates with visits > 0 are eligible.
    //   - With probability `epsilon` (when u1 < epsilon): sample UNIFORMLY over eligible candidates.
    //   - Otherwise: sample proportional to visits^(1/tau) (floating point).
    //   - tau <= 1e-6 degenerates to argmax (most-visited) over eligible candidates.
    // u1, u2 are uniform draws in [0,1). Deterministic given inputs (unit-testable; no RNG, no engine).
    // Returns 0 if there are no eligible candidates (caller guarantees >=1 in practice).
    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2);
}
}
