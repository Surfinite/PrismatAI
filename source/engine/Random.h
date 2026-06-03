#pragma once

#include "Common.h"

#include <cstdint>

namespace Prismata
{
namespace Random
{
    void Seed(uint64_t seed);
    size_t Int(size_t exclusiveMax);
    double Real01();   // uniform double in [0, 1), from the seedable stream
}
}
