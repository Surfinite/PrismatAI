#include "Random.h"

#include <atomic>
#include <chrono>
#include <functional>
#include <random>
#include <thread>

namespace
{
    std::atomic<uint64_t> g_baseSeed(
        static_cast<uint64_t>(std::chrono::high_resolution_clock::now().time_since_epoch().count()));
    std::atomic<uint64_t> g_seedSequence(0);

    uint64_t mixSeed(uint64_t x)
    {
        x += 0x9e3779b97f4a7c15ULL;
        x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
        x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
        return x ^ (x >> 31);
    }

    uint64_t nextThreadSeed()
    {
        const uint64_t sequence = g_seedSequence.fetch_add(1, std::memory_order_relaxed);
        return mixSeed(g_baseSeed.load(std::memory_order_relaxed) + sequence);
    }

    std::mt19937_64 & engine()
    {
        thread_local std::mt19937_64 rng(nextThreadSeed());
        return rng;
    }
}

namespace Prismata
{
namespace Random
{
    void Seed(uint64_t seed)
    {
        g_baseSeed.store(seed, std::memory_order_relaxed);
        g_seedSequence.store(0, std::memory_order_relaxed);
        // Seed the engine deterministically with mixSeed(seed). Do NOT route through
        // nextThreadSeed() here: the thread_local engine is lazily constructed on the
        // first engine() call (consuming sequence 0 via its constructor), which would
        // double-bump the sequence counter and seed with mixSeed(seed+1) instead. The
        // stream must be a pure function of the seed, so seed directly.
        engine().seed(mixSeed(seed));
    }

    size_t Int(size_t exclusiveMax)
    {
        PRISMATA_ASSERT(exclusiveMax > 0, "Random::Int called with exclusiveMax 0");

        std::uniform_int_distribution<size_t> dist(0, exclusiveMax - 1);
        return dist(engine());
    }

    double Real01()
    {
        std::uniform_real_distribution<double> dist(0.0, 1.0);
        return dist(engine());
    }
}
}
