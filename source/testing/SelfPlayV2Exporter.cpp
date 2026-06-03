#include "SelfPlayV2Exporter.h"
#include "V2Record.h"

#include <cstdio>
#include <fstream>
#include <filesystem>
#include <string>

namespace Prismata
{

void SelfPlayV2Exporter::capture(const GameState & state, int plyIndex)
{
    _records.push_back(buildV2RecordJSON(state, plyIndex));
}

bool SelfPlayV2Exporter::finalize(PlayerID winner, int totalPlies, int gameId)
{
    if (_records.empty())
    {
        return false;
    }

    // outcome from P0's perspective: P0 win = 1.0, draw / no-winner = 0.5, P1 win = 0.0.
    const double outcomeP0 = (winner == Players::Player_One) ? 1.0
                           : (winner == Players::Player_None) ? 0.5
                           : 0.0;

    // Format outcome as a clean numeric literal (1.0 / 0.5 / 0.0).
    char outBuf[32];
    std::snprintf(outBuf, sizeof(outBuf), "%.1f", outcomeP0);

    std::error_code ec;
    std::filesystem::create_directories(_outDir, ec);
    if (ec)
    {
        return false;
    }

    char filename[64];
    std::snprintf(filename, sizeof(filename), "selfplay_%04d.jsonl", gameId);
    const std::string path = _outDir + "/" + filename;

    std::ofstream out(path, std::ios::binary);
    if (!out)
    {
        return false;
    }

    for (const std::string & rec : _records)
    {
        // buildV2RecordJSON emits a compact object ending in '}' (no trailing
        // whitespace). Inject the two game-level fields before the closing brace.
        if (rec.empty() || rec.back() != '}')
        {
            continue;   // defensive: skip a malformed record rather than corrupt the line
        }
        out.write(rec.data(), static_cast<std::streamsize>(rec.size() - 1));   // up to but not incl. '}'
        out << ",\"outcome_p0\":" << outBuf
            << ",\"total_plies\":" << totalPlies
            << "}\n";
    }

    return out.good();
}

} // namespace Prismata
