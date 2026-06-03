#include "MoveSampler.h"

#include <cmath>
#include <limits>

namespace Prismata
{
namespace MoveSampler
{
    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2)
    {
        // Collect eligible candidates (visited at least once).
        std::vector<size_t> elig;
        for (size_t i = 0; i < visits.size(); ++i)
        {
            if (visits[i] > 0) { elig.push_back(i); }
        }
        if (elig.empty()) { return 0; }

        // epsilon-uniform branch.
        if (u1 < epsilon)
        {
            size_t k = (size_t)(u2 * (double)elig.size());
            if (k >= elig.size()) { k = elig.size() - 1; }  // guard u2 == nextafter(1.0)
            return elig[k];
        }

        // Near-zero temperature => argmax (most visited; first-wins tie-break).
        if (tau <= 1e-6)
        {
            size_t best = elig[0];
            for (size_t i = 1; i < elig.size(); ++i)
            {
                if (visits[elig[i]] > visits[best]) { best = elig[i]; }
            }
            return best;
        }

        // Proportional to visits^(1/tau).
        const double invTau = 1.0 / tau;
        std::vector<double> w(elig.size());
        double total = 0.0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            double wi = std::pow((double)visits[elig[i]], invTau);
            w[i] = wi;
            total += wi;
        }
        if (total <= 0.0) { return elig[0]; }

        double target = u2 * total;
        double cum = 0.0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            cum += w[i];
            if (target < cum) { return elig[i]; }
        }
        return elig.back();  // floating-point fallthrough
    }
}
}
