#include "SelfPlayV2Exporter.h"
#include "V2Record.h"

#include <cstdio>
#include <fstream>
#include <filesystem>
#include <string>

#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"

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

    std::error_code ec;
    std::filesystem::create_directories(_outDir, ec);
    // Only fail if the directory genuinely isn't there afterward: create_directories
    // can set ec spuriously on an already-existing dir (MSVC edge case / concurrent
    // first-writers). is_directory is the source of truth.
    if (ec && !std::filesystem::is_directory(_outDir))
    {
        fprintf(stderr, "[SelfPlayV2Exporter] create_directories failed: %s (%s)\n",
                _outDir.c_str(), ec.message().c_str());
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

    // Backfill the two game-level fields via a robust parse-then-reserialize, so we
    // depend on no string-layout contract (where the record ends, trailing chars).
    // outcome_p0 is added as a double so it serializes as a float that vectorize_v2
    // ingests via float(outcome_p0).
    for (const std::string & rec : _records)
    {
        rapidjson::Document doc;
        doc.Parse(rec.c_str());
        if (doc.HasParseError())
        {
            // Surface a bad record rather than silently dropping it.
            fprintf(stderr, "[SelfPlayV2Exporter] skipping malformed record in game %d\n", gameId);
            continue;
        }

        rapidjson::Value outcomeMember;
        outcomeMember.SetDouble(outcomeP0);
        doc.AddMember("outcome_p0", outcomeMember, doc.GetAllocator());
        doc.AddMember("total_plies", totalPlies, doc.GetAllocator());

        rapidjson::StringBuffer buffer;
        rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
        doc.Accept(writer);
        out << buffer.GetString() << "\n";
    }

    return out.good();
}

} // namespace Prismata
