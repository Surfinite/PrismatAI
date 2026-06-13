#include "Prismata.h"
#include "PrismataAI.h"
#include "NeuralNet.h"
#include "MoveSampler.h"
#include "DsnnConfig.h"
#include "V2Record.h"
#include "Random.h"
#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"
#include "Move.h"
#include "Action.h"
#include "Constants.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <stdio.h>
#include <random>
#include <set>

#ifdef WIN32
    #include <Windows.h>
    #include <io.h>
    #define DUP(fd) _dup(fd)
    #define DUP2(fd1, fd2) _dup2(fd1, fd2)
    #define FILENO(fp) _fileno(fp)
    #define CLOSE(fd) _close(fd)
#else
    #include <unistd.h>
    #define DUP(fd) dup(fd)
    #define DUP2(fd1, fd2) dup2(fd1, fd2)
    #define FILENO(fp) fileno(fp)
    #define CLOSE(fd) close(fd)
#endif

using namespace Prismata;

void printVersionInfo()
{
    std::stringstream ss;
    ss << "C++ AI compiled on: " << __DATE__ << " at " << __TIME__ << std::endl;
 
    printf("%s", ss.str().c_str());
}

int main(int argc, char *argv[])
{
#ifdef WIN32
    // disables pop up box on crash
    DWORD dwMode = SetErrorMode(SEM_NOGPFAULTERRORBOX);
    SetErrorMode(dwMode | SEM_NOGPFAULTERRORBOX);
#endif

    // --- Parity oracle (offline harness): dump DeepSets features + value for a fixed state ---
    // Usage: Prismata_Standalone --dump-features <stateJson> <outJson> [weightsBin]
    // Run from bin/ so the relative asset paths resolve. Not part of the AI move protocol.
    if (argc >= 4 && std::string(argv[1]) == "--dump-features")
    {
        const std::string statePath   = argv[2];
        const std::string outPath     = argv[3];
        const std::string weightsPath = (argc >= 5) ? argv[4] : "asset/config/neural_weights_mbonly.bin";

        std::ifstream sin(statePath);
        if (!sin.is_open())
        {
            fprintf(stderr, "dump-features: cannot open state file %s\n", statePath.c_str());
            return 1;
        }
        std::string stateStr((std::istreambuf_iterator<char>(sin)), std::istreambuf_iterator<char>());
        sin.close();

        // Load the 116-unit training card library (matches the NN unit_index + property_table).
        // Resolve relative to the executable so --dump-features works from any working dir.
        std::string cardLibPath = "asset/config/cardLibrary.jso";
        {
            const std::string exeDir = NeuralNet::getExecutableDir();
            if (!exeDir.empty())
            {
                std::ifstream clTest(exeDir + "/" + cardLibPath);
                if (clTest.good()) { cardLibPath = exeDir + "/" + cardLibPath; }
            }
        }
        Prismata::InitFromCardLibrary(cardLibPath);

        rapidjson::Document doc;
        if (doc.Parse(stateStr.c_str()).HasParseError())
        {
            fprintf(stderr, "dump-features: JSON parse error in %s\n", statePath.c_str());
            return 1;
        }
        const rapidjson::Value & gs = doc.HasMember("gameState") ? doc["gameState"] : doc;
        const GameState state(gs);

        if (!NeuralNet::Instance().loadWeights(weightsPath))
        {
            fprintf(stderr, "dump-features: failed to load weights %s\n", weightsPath.c_str());
            return 1;
        }
        NeuralNet::Instance().buildCardTypeMapping();
        NeuralNet::Instance().dumpFeaturesJSON(state, outPath);
        return 0;
    }

    // --- Off-book buy-reachability probe (axis-2 audit, search-FREE) ---
    // Usage: PrismataAI.exe --probe-buys <stateJson> <outJson> [iteratorName]
    // Collects the distinct BUY unit codenames purchasable off-book from the given state.
    // Two modes selected by iteratorName:
    //   "AllBuy" (default): EXHAUSTIVE structural reachability -- for every buyable card in
    //            the set, report it if a single BUY is legal (in-set + affordable + supply).
    //            Mirrors MoveIterator_AllBuy::processBuyableCards' numBuyable>0 test. This is
    //            position-independent (any legally-buyable unit is reported) and is what the
    //            116-unit axis-2 audit consumes.
    //   <named PPPortfolio, e.g. "HardIterator_Root">: drive that config iterator's
    //            (OB-off) whole-turn enumeration and collect the BUY codenames it EMITS --
    //            i.e. what the deployed AI's heuristic buy partials actually choose
    //            (need-driven, position-dependent).
    // Writes {"buyable_units":[...]} (codenames, sorted) to outJson. Mirrors --dump-features'
    // card-library + state load. Not part of the AI move protocol.
    if (argc >= 4 && std::string(argv[1]) == "--probe-buys")
    {
        const std::string statePath = argv[2];
        const std::string outPath   = argv[3];
        const std::string iterName  = (argc >= 5) ? argv[4] : "AllBuy";

        std::ifstream sin(statePath);
        if (!sin.is_open())
        {
            fprintf(stderr, "probe-buys: cannot open state file %s\n", statePath.c_str());
            return 1;
        }
        std::string stateStr((std::istreambuf_iterator<char>(sin)), std::istreambuf_iterator<char>());
        sin.close();

        // Load the 116-unit training card library (resolve relative to the exe like --dump-features).
        std::string cardLibPath = "asset/config/cardLibrary.jso";
        std::string cfgPath     = "asset/config/config.txt";
        {
            const std::string exeDir = NeuralNet::getExecutableDir();
            if (!exeDir.empty())
            {
                std::ifstream clTest(exeDir + "/" + cardLibPath);
                if (clTest.good()) { cardLibPath = exeDir + "/" + cardLibPath; }
                std::ifstream cfgTest(exeDir + "/" + cfgPath);
                if (cfgTest.good()) { cfgPath = exeDir + "/" + cfgPath; }
            }
        }
        Prismata::InitFromCardLibrary(cardLibPath);

        // Load config DEFINITIONS (iterators/partials/filters; no Players -> no NN weight loads)
        // so the named iterator resolves. main()'s normal Steam path loads this inside
        // InitializeAIAndGetAIMove, which this offline hook never reaches, so do it explicitly.
        if (!AIParameters::Instance().parseConfigDefsForMerge(cfgPath))
        {
            fprintf(stderr, "probe-buys: could not load config defs from %s\n", cfgPath.c_str());
            return 1;
        }

        rapidjson::Document doc;
        if (doc.Parse(stateStr.c_str()).HasParseError())
        {
            fprintf(stderr, "probe-buys: JSON parse error in %s\n", statePath.c_str());
            return 1;
        }
        const rapidjson::Value & gs = doc.HasMember("gameState") ? doc["gameState"] : doc;
        const GameState state(gs);

        const PlayerID player = state.getActivePlayer();
        std::set<std::string> buyable;
        size_t childCount = 0;

        if (iterName == "AllBuy")
        {
            // Exhaustive structural reachability: a unit is off-book reachable iff a single
            // BUY of it is legal from this state (in the buyable set + affordable + supply>0).
            // This is exactly the numBuyable>0 test in MoveIterator_AllBuy::processBuyableCards,
            // without enumerating the (combinatorially explosive) whole-turn buy cross-product.
            for (CardID i(0); i < state.numCardsBuyable(); ++i)
            {
                const CardType type = state.getCardBuyableByIndex(i).getType();
                const Action buy(player, ActionTypes::BUY, type.getID());
                if (state.isLegal(buy))
                {
                    buyable.insert(type.getName());
                    ++childCount;
                }
            }
        }
        else
        {
            // Drive the named config iterator's whole-turn enumeration (heuristic buy partials).
            MoveIteratorPtr iter = AIParameters::Instance().getMoveIterator(player, iterName);
            iter->setState(state);   // PPPortfolio::setState calls reset() internally
            iter->reset();           // explicit, mirrors the canonical drive loop

            GameState child;
            Move move;
            while (iter->generateNextChild(child, move))
            {
                ++childCount;
                for (size_t a(0); a < move.size(); ++a)
                {
                    const Action & act = move.getAction(a);
                    if (act.getType() == ActionTypes::BUY)
                    {
                        buyable.insert(state.getCardBuyableByID(act.getID()).getType().getName());
                    }
                }
            }
        }

        rapidjson::Document out;
        out.SetObject();
        rapidjson::Document::AllocatorType & alloc = out.GetAllocator();
        rapidjson::Value arr(rapidjson::kArrayType);
        for (const std::string & name : buyable)
        {
            rapidjson::Value v;
            v.SetString(name.c_str(), (rapidjson::SizeType)name.size(), alloc);
            arr.PushBack(v, alloc);
        }
        out.AddMember("buyable_units", arr, alloc);

        std::ofstream fout(outPath, std::ios::binary);
        if (!fout)
        {
            fprintf(stderr, "probe-buys: cannot open output file %s\n", outPath.c_str());
            return 1;
        }
        rapidjson::StringBuffer sb;
        rapidjson::Writer<rapidjson::StringBuffer> writer(sb);
        out.Accept(writer);
        fout << sb.GetString();
        fout.close();

        fprintf(stderr, "probe-buys: iterator=%s children=%zu distinct-buyable=%zu -> %s\n",
                iterName.c_str(), childCount, buyable.size(), outPath.c_str());
        return fout.good() ? 0 : 1;
    }

    // --- RNG determinism self-test ---
    // Usage: PrismataAI.exe --test-rng    (prints PASS/FAIL, returns 0/1)
    if (argc >= 2 && std::string(argv[1]) == "--test-rng")
    {
        // NOTE: must stay identical to mixSeed() in source/engine/Random.cpp (test isolation).
        auto mixSeed = [](uint64_t x) -> uint64_t {
            x += 0x9e3779b97f4a7c15ULL;
            x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
            x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
            return x ^ (x >> 31);
        };
        const uint64_t S = 123456789ULL;
        std::mt19937_64 ref(mixSeed(S));
        std::uniform_int_distribution<size_t> dist(0, 1000000 - 1);
        Prismata::Random::Seed(S);
        bool pureFnOfSeed = true;
        for (int i = 0; i < 8; ++i)
        {
            size_t expected = dist(ref);
            size_t got = Prismata::Random::Int(1000000);
            if (got != expected) { pureFnOfSeed = false; break; }
        }
        Prismata::Random::Seed(S);
        size_t a = Prismata::Random::Int(1000000);
        Prismata::Random::Seed(S);
        size_t b = Prismata::Random::Int(1000000);
        bool reproducible = (a == b);
        bool ok = pureFnOfSeed && reproducible;
        printf("--test-rng: pureFnOfSeed=%d reproducible=%d => %s\n",
               (int)pureFnOfSeed, (int)reproducible, ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }

    // --- use_dsnn.txt parser self-test (FORCE_DSNN drop-in config; see AITools.cpp) ---
    // Usage: PrismataAI.exe --test-dsnnconfig    (prints PASS/FAIL, returns 0/1)
    if (argc >= 2 && std::string(argv[1]) == "--test-dsnnconfig")
    {
        bool ok = true;
        auto check = [&](bool cond, const char * msg){ if (!cond) { ok = false; printf("  FAIL: %s\n", msg); } };

        Prismata::DsnnConfig d = Prismata::parseDsnnConfig("");
        check(d.thinkTimeMs < 0 && d.maxTraversals < 0, "empty file -> all defaults");

        // BOM + CRLF + comment + case-insensitive keys + spaces + unknown keys ignored
        std::string s = "\xEF\xBB\xBF# friend build\r\nThink_Time = 2500\r\nmax_traversals=0\ngarbageline\nthreads=8\n";
        Prismata::DsnnConfig c = Prismata::parseDsnnConfig(s);
        check(c.thinkTimeMs == 2500, "think_time=2500 (BOM/CRLF/case/space tolerated)");
        check(c.maxTraversals == 0, "max_traversals=0 (uncapped)");

        Prismata::DsnnConfig e = Prismata::parseDsnnConfig("think_time=notanumber\nmax_traversals=50\n");
        check(e.thinkTimeMs < 0 && e.maxTraversals == 50, "bad numeric tolerated per-key");

        Prismata::DsnnConfig f = Prismata::parseDsnnConfig("think_time=-3\nmax_traversals=-1\n");
        check(f.thinkTimeMs < 0 && f.maxTraversals < 0, "negative values behave as unset");

        printf("--test-dsnnconfig: %s\n", ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }

    // --- Move sampler self-test ---
    if (argc >= 2 && std::string(argv[1]) == "--test-sampler")
    {
        using Prismata::MoveSampler::sampleRootIndex;
        using Prismata::MoveSampler::sampleRootIndexLate;
        using Prismata::MoveSampler::argmaxIndex;
        bool ok = true;
        auto check = [&](bool cond, const char * msg){ if (!cond) { ok = false; printf("  FAIL: %s\n", msg); } };

        // (A) Uniform visits, tau=1, eps=0 -> proportional == uniform; u2 picks the bucket.
        std::vector<size_t> uni = {1,1,1,1};
        check(sampleRootIndex(uni, 1.0, 0.0, 0.5, 0.00, 0.0) == 0, "uniform u2=0.00 -> idx0");
        check(sampleRootIndex(uni, 1.0, 0.0, 0.5, 0.99, 0.0) == 3, "uniform u2=0.99 -> idx3");

        // (B) tau->0 => argmax regardless of u2 (eps=0).
        std::vector<size_t> skew = {10,1,1};
        check(sampleRootIndex(skew, 1e-9, 0.0, 0.5, 0.99, 0.0) == 0, "tau~0 -> argmax idx0");

        // (C) eps=1, u1=0 forces uniform branch over eligible.
        check(sampleRootIndex(skew, 1.0, 1.0, 0.0, 0.99, 0.0) == 2, "eps=1 uniform u2=0.99 -> idx2");

        // (D) visits {4,1}, tau=1, eps=0 => p0=0.8 cut at u2=0.8.
        std::vector<size_t> v41 = {4,1};
        check(sampleRootIndex(v41, 1.0, 0.0, 0.5, 0.79, 0.0) == 0, "v41 u2=0.79 -> idx0");
        check(sampleRootIndex(v41, 1.0, 0.0, 0.5, 0.81, 0.0) == 1, "v41 u2=0.81 -> idx1");

        // (E) zero-visit candidates are ineligible.
        std::vector<size_t> z = {0, 5, 0};
        check(sampleRootIndex(z, 1.0, 0.0, 0.5, 0.50, 0.0) == 1, "only idx1 eligible");

        // (F) empty input -> 0 (contract fallback).
        std::vector<size_t> empt;
        check(sampleRootIndex(empt, 1.0, 0.0, 0.5, 0.5, 0.0) == 0, "empty -> 0");

        // (G) tiny tau with large visits must NOT overflow into elig.back(); must pick argmax.
        std::vector<size_t> big = {500, 1, 1};
        check(sampleRootIndex(big, 0.001, 0.0, 0.5, 0.99, 0.0) == 0, "tiny-tau large-visits -> argmax idx0");

        // (H) A1 uniform tie-break: visits {5,5,1} ties on {0,1}; u3 splits them 50/50.
        std::vector<size_t> tie = {5,5,1};
        check(argmaxIndex(tie, 0.25) == 0, "tie u3=0.25 -> idx0");
        check(argmaxIndex(tie, 0.75) == 1, "tie u3=0.75 -> idx1");
        check(sampleRootIndex(tie, 1e-9, 0.0, 0.5, 0.5, 0.75) == 1, "tau~0 tie u3=0.75 -> idx1");

        // (I) J5 targeted IG deviation: visits {9,8,7}, igCounts {2,2,1}; argmax idx0 (count 2);
        //     u1 < epsIG must pick the most-visited DIFFERENT-count child = idx2 (count 1).
        std::vector<size_t> vIG = {9,8,7};
        std::vector<int>    cIG = {2,2,1};
        check(sampleRootIndexLate(vIG, cIG, 0.25, 0.0, 0.10, 0.5, 0.0) == 2, "epsIG fires -> different-count idx2");
        check(sampleRootIndexLate(vIG, cIG, 0.25, 0.0, 0.90, 0.5, 0.0) == 0, "u1 >= epsIG -> argmax idx0");

        // (J) J5 not-live root (all counts equal): targeted branch cannot fire; argmax even when u1 < epsIG.
        std::vector<int> cFlat = {1,1,1};
        check(sampleRootIndexLate(vIG, cFlat, 0.25, 0.0, 0.10, 0.99, 0.0) == 0, "counts flat -> argmax (no random fallback)");

        // (K) layered EpsilonLate band: u1 in [epsIG, epsIG+epsLate) -> uniform over eligible via u2.
        check(sampleRootIndexLate(vIG, cIG, 0.10, 0.20, 0.15, 0.99, 0.0) == 2, "epsLate band uniform u2=0.99 -> idx2");

        // (L) late argmax tie-break parity with argmaxIndex (same u3).
        std::vector<int> cTie = {0,1,0};
        check(sampleRootIndexLate(tie, cTie, 0.0, 0.0, 0.9, 0.5, 0.75) == argmaxIndex(tie, 0.75), "late argmax == argmaxIndex at same u3");

        printf("--test-sampler: %s\n", ok ? "PASS" : "FAIL");
        return ok ? 0 : 1;
    }

    // --- DeepSets V2 training-record dump (single state) ---
    // Usage: PrismataAI.exe --dump-v2-record <stateJson> <outJson>
    // Emits the per-state V2 record (WITHOUT outcome_p0/total_plies) for the given
    // state, using the SAME GameState the value net evaluates. Run from bin/ so the
    // relative cardLibrary path resolves. Not part of the AI move protocol.
    if (argc >= 4 && std::string(argv[1]) == "--dump-v2-record")
    {
        const std::string statePath = argv[2];
        const std::string outPath   = argv[3];

        std::ifstream sin(statePath);
        if (!sin.is_open())
        {
            fprintf(stderr, "dump-v2-record: cannot open state file %s\n", statePath.c_str());
            return 1;
        }
        std::string stateStr((std::istreambuf_iterator<char>(sin)), std::istreambuf_iterator<char>());
        sin.close();

        // Load the 116-unit training card library (matches NN unit_index + property_table).
        std::string cardLibPath = "asset/config/cardLibrary.jso";
        {
            const std::string exeDir = NeuralNet::getExecutableDir();
            if (!exeDir.empty())
            {
                std::ifstream clTest(exeDir + "/" + cardLibPath);
                if (clTest.good()) { cardLibPath = exeDir + "/" + cardLibPath; }
            }
        }
        Prismata::InitFromCardLibrary(cardLibPath);

        rapidjson::Document doc;
        if (doc.Parse(stateStr.c_str()).HasParseError())
        {
            fprintf(stderr, "dump-v2-record: JSON parse error in %s\n", statePath.c_str());
            return 1;
        }
        const rapidjson::Value & gs = doc.HasMember("gameState") ? doc["gameState"] : doc;
        const GameState state(gs);

        const std::string rec = buildV2RecordJSON(state, 0);

        std::ofstream out(outPath, std::ios::binary);
        if (!out)
        {
            fprintf(stderr, "dump-v2-record: cannot open output file %s\n", outPath.c_str());
            return 1;
        }
        out << rec;
        return out.good() ? 0 : 1;
    }

    Random::Seed((uint64_t)time(NULL));
    
    // get the input line from stdin
    std::string inputLine;
    std::getline(std::cin, inputLine);

    // if the input string is 'version' print to stdout
    if (inputLine == "version")
    {
        printVersionInfo();
        return 0;
    }

    bool debugPrintToFile = false;

    if (debugPrintToFile)
    {
        // test print the line we got to a file for debugging
        std::ofstream fout("stdin_contents.txt", std::ofstream::out);
        fout << inputLine;
        fout.close();
    }

    // Redirect stdout to stderr during init/search so engine-internal printfs
    // (e.g. "Base set has 11 cards" from CardTypes.cpp) don't corrupt the
    // JSON response on stdout. The matchup runner parses our stdout as JSON.
    fflush(stdout);
    int savedStdout = DUP(FILENO(stdout));
    DUP2(FILENO(stderr), FILENO(stdout));

    // initialize, compute the move, and print the resulting move
    std::string moveString = AITools::InitializeAIAndGetAIMove(inputLine);

    // Restore stdout for the JSON response
    fflush(stdout);
    DUP2(savedStdout, FILENO(stdout));
    CLOSE(savedStdout);

    // remove newlines from the resulting string so it counts as one line for stdout
    for (size_t i(0); i < moveString.size(); ++i)
    {
        #ifdef WIN32
        if (moveString[i] == '\n' || moveString[i] == '\r\n')
        #else
        if (moveString[i] == '\n')
        #endif
        {
            moveString[i] = ' ';
        }
    }

    if (debugPrintToFile)
    {
        std::ofstream fout("stdout_move_string.txt", std::ofstream::out);
        fout << moveString;
        fout.close();
    }
    
    std::cout << moveString << "\n";

    return 0;
}
