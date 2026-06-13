#include "MoveSampler.h"

#include <cmath>
#include <limits>

namespace
{
    constexpr double kArgmaxTauThreshold = 1e-6;

    std::vector<size_t> eligible(const std::vector<size_t> & visits)
    {
        std::vector<size_t> elig;
        for (size_t i = 0; i < visits.size(); ++i)
        {
            if (visits[i] > 0) { elig.push_back(i); }
        }
        return elig;
    }

    // Uniform pick from a non-empty vector given u in [0,1).
    size_t uniformPick(const std::vector<size_t> & v, double u)
    {
        size_t k = (size_t)(u * (double)v.size());
        if (k >= v.size()) { k = v.size() - 1; }  // guard u == nextafter(1.0)
        return v[k];
    }

    // Most-visited among elig; ties broken UNIFORMLY via u3 (A1 — the old first-wins
    // tie-break composed with longest-move-first child ordering into an over-click bias).
    size_t argmaxEligible(const std::vector<size_t> & visits, const std::vector<size_t> & elig,
                          double u3)
    {
        size_t maxV = 0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            if (visits[elig[i]] > maxV) { maxV = visits[elig[i]]; }
        }
        std::vector<size_t> ties;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            if (visits[elig[i]] == maxV) { ties.push_back(elig[i]); }
        }
        return uniformPick(ties, u3);
    }
}

namespace Prismata
{
namespace MoveSampler
{
    size_t argmaxIndex(const std::vector<size_t> & visits, double u3)
    {
        const std::vector<size_t> elig = eligible(visits);
        if (elig.empty()) { return 0; }
        return argmaxEligible(visits, elig, u3);
    }

    size_t sampleRootIndex(const std::vector<size_t> & visits,
                           double tau, double epsilon, double u1, double u2, double u3)
    {
        // Collect eligible candidates (visited at least once).
        const std::vector<size_t> elig = eligible(visits);
        if (elig.empty()) { return 0; }

        // epsilon-uniform branch.
        if (u1 < epsilon)
        {
            return uniformPick(elig, u2);
        }

        // Near-zero temperature => argmax (most visited; uniform tie-break).
        if (tau <= kArgmaxTauThreshold)
        {
            return argmaxEligible(visits, elig, u3);
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
        // pow() overflows to +inf for small tau (large invTau) at realistic visit counts,
        // making the inverse-CDF scan silently return elig.back(). Degenerate to argmax,
        // which is the intended behavior as tau -> 0. Also covers the degenerate total==0 case.
        if (!std::isfinite(total) || total <= 0.0) { return argmaxEligible(visits, elig, u3); }

        double target = u2 * total;
        double cum = 0.0;
        for (size_t i = 0; i < elig.size(); ++i)
        {
            cum += w[i];
            if (target < cum) { return elig[i]; }
        }
        return elig.back();  // floating-point fallthrough
    }

    size_t sampleRootIndexLate(const std::vector<size_t> & visits,
                               const std::vector<int> & igCounts,
                               double epsilonIG, double epsilonLate,
                               double u1, double u2, double u3)
    {
        const std::vector<size_t> elig = eligible(visits);
        if (elig.empty()) { return 0; }

        const size_t a = argmaxEligible(visits, elig, u3);

        // Targeted IG deviation (J5): an on-axis counterfactual — the most-visited
        // candidate at a DIFFERENT IG click count than the argmax's. Fires only when
        // the IG decision is actually LIVE at this root (>= 2 distinct counts among
        // eligible candidates). igCounts size is the caller's contract.
        if (u1 < epsilonIG && igCounts.size() == visits.size())
        {
            const int argmaxCount = igCounts[a];
            size_t bestV = 0;
            for (size_t i = 0; i < elig.size(); ++i)
            {
                const size_t c = elig[i];
                if (igCounts[c] != argmaxCount && visits[c] > bestV) { bestV = visits[c]; }
            }
            if (bestV > 0)
            {
                std::vector<size_t> other;
                for (size_t i = 0; i < elig.size(); ++i)
                {
                    const size_t c = elig[i];
                    if (igCounts[c] != argmaxCount && visits[c] == bestV) { other.push_back(c); }
                }
                return uniformPick(other, u2);
            }
            // No eligible candidate at a different count: the IG decision is not live at
            // this root; play argmax. (Deliberately does NOT fall into the epsilonLate
            // band — the u1 < epsilonIG mass is reserved for the targeted mechanism.)
            return a;
        }

        // Legacy uniform late deviation (EpsilonLate; frozen 0 under regime v3).
        if (u1 < epsilonIG + epsilonLate)
        {
            return uniformPick(elig, u2);
        }

        return a;
    }
}
}
