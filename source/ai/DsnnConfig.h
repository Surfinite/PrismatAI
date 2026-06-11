#pragma once

#include <string>

namespace Prismata
{
    // Configuration parsed from use_dsnn.txt -- the FORCE_DSNN drop-in sentinel file
    // (see the FORCE_DSNN override in AITools.cpp). The file's PRESENCE next to the
    // executable activates the DSNN override; its CONTENTS are optional key=value
    // overrides, so an EMPTY file keeps every default.
    struct DsnnConfig
    {
        int  thinkTimeMs   = -1;    // <0 = unset (requested TimeLimit, 7000->10000); 0 = no time cap
        long maxTraversals = -1;    // <0 = unset (100000); 0 = uncapped
    };

    // Pure parser: tolerant of UTF-8 BOM, CRLF, blank/# lines; case-insensitive keys;
    // unknown keys and bad numeric values are skipped (that key keeps its default).
    // Implementation lives in AITools.cpp so no new .cpp needs adding to the
    // generated vcxprojs.
    DsnnConfig parseDsnnConfig(const std::string & contents);

    // File wrapper: parseDsnnConfig(file contents); missing/unreadable file -> defaults.
    DsnnConfig loadDsnnConfig(const std::string & path);
}
