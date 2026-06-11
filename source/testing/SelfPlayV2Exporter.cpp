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

    // Keep the move-stamp vector strictly 1:1 with _records. A default entry is
    // pushed here so the three vectors stay aligned even if stampLastMove() is never
    // called for this record (e.g. a code path that skips stamping); finalize()
    // indexes _moveStamps by record index.
    _moveStamps.push_back(MoveStamp{});

    // Parity sidecar: stash the raw turn-start state in the exact bare-doc shape
    // that PrismataAI.exe --dump-features consumes. state.toJSONString() emits
    // {whiteMana, blackMana, turn, phase, cards, ...supply..., table}, which the
    // GameState(const rapidjson::Value&) constructor round-trips. finalize() writes
    // these out so the export-parity harness can be scaled to ~1000 self-play states.
    _rawStates.emplace_back(plyIndex, state.toJSONString());
}

void SelfPlayV2Exporter::stampLastMove(int igClickCount, int igFeasibleMax, int sampledIdx, int argmaxIdx, int rootChildren, bool rootTruncated)
{
    if (_moveStamps.empty()) return;
    _moveStamps.back() = MoveStamp{ igClickCount, igFeasibleMax, sampledIdx, argmaxIdx, rootChildren, rootTruncated };
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

    // Backfill the game-level fields (outcome_p0, total_plies) plus the per-record
    // move-derived fields (ig_click_count, sampled_idx, argmax_idx) via a robust
    // parse-then-reserialize, so we depend on no string-layout contract (where the
    // record ends, trailing chars). outcome_p0 is added as a double so it serializes
    // as a float that vectorize_v2 ingests via float(outcome_p0).
    //
    // Index with i (not a range-for) so we can read the parallel _moveStamps entry.
    // _moveStamps is 1:1 with _records, so i must advance for EVERY record — including
    // ones skipped on parse error — to keep the index aligned to the record processed.
    for (size_t i = 0; i < _records.size(); ++i)
    {
        const std::string & rec = _records[i];

        rapidjson::Document doc;
        doc.Parse(rec.c_str());
        if (doc.HasParseError())
        {
            // Surface a bad record rather than silently dropping it.
            fprintf(stderr, "[SelfPlayV2Exporter] skipping malformed record in game %d\n", gameId);
            continue;
        }

        auto & alloc = doc.GetAllocator();

        rapidjson::Value outcomeMember;
        outcomeMember.SetDouble(outcomeP0);
        doc.AddMember("outcome_p0", outcomeMember, alloc);
        doc.AddMember("total_plies", totalPlies, alloc);

        const MoveStamp & ms = _moveStamps[i];
        doc.AddMember("ig_click_count",  ms.igClickCount,  alloc);
        doc.AddMember("ig_feasible_max", ms.igFeasibleMax, alloc);
        doc.AddMember("sampled_idx",    ms.sampledIdx,   alloc);
        doc.AddMember("argmax_idx",     ms.argmaxIdx,    alloc);
        doc.AddMember("root_children",  ms.rootChildren, alloc);
        doc.AddMember("root_truncated", ms.rootTruncated, alloc);

        rapidjson::StringBuffer buffer;
        rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
        doc.Accept(writer);
        out << buffer.GetString() << "\n";
    }

    // Parity-states sidecar: write each stashed raw state to a sibling parity_states/
    // dir (e.g. asset/training/rl_smoke_v2 -> asset/training/parity_states) as
    // sp_<gameId>_<plyIndex>.json. These bare-doc state files feed the C++<->PyTorch
    // value export-parity harness (tools/parity/dump_value_batch.py +
    // compare_parity_deepsets.py). This does NOT alter the V2 JSONL output above.
    {
        const std::filesystem::path parityDir =
            std::filesystem::path(_outDir).parent_path() / "parity_states";

        std::error_code pec;
        std::filesystem::create_directories(parityDir, pec);
        if (pec && !std::filesystem::is_directory(parityDir))
        {
            fprintf(stderr, "[SelfPlayV2Exporter] parity create_directories failed: %s (%s)\n",
                    parityDir.string().c_str(), pec.message().c_str());
        }
        else
        {
            for (const auto & rs : _rawStates)
            {
                char spName[64];
                std::snprintf(spName, sizeof(spName), "sp_%04d_%04d.json", gameId, rs.first);
                const std::filesystem::path spPath = parityDir / spName;

                std::ofstream sp(spPath, std::ios::binary);
                if (sp)
                {
                    sp << rs.second;
                }
                else
                {
                    fprintf(stderr, "[SelfPlayV2Exporter] failed to write parity state %s\n",
                            spPath.string().c_str());
                }
            }
        }
    }

    const bool ok = out.good();

    // Clear accumulators so a second finalize() call cannot re-emit duplicate JSONL
    // lines or duplicate sp_<gameId>_*.json sidecar files (idempotent re-finalize).
    _records.clear();
    _moveStamps.clear();
    _rawStates.clear();

    return ok;
}

} // namespace Prismata
