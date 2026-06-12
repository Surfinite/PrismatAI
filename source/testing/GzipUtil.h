#pragma once

#include <string>
#include "miniz/miniz.h"

namespace Prismata
{

// Wrap `data` as a standard gzip (.gz) stream: 10-byte gzip header + raw
// DEFLATE body (miniz) + CRC32 + ISIZE footer. Browsers' DecompressionStream
// ('gzip') and python's gzip module read this directly (they key on the
// 0x1f 0x8b magic). Returns an empty string on compression failure.
//
// Shared by ReplaySerializer (game_NNNN.json.gz) and SelfPlayV2Exporter
// (parity sidecar sp_*.json.gz). Header-only so no vcxproj edit is needed;
// the miniz implementation (miniz.c) is already compiled into the testing
// project for the replay serializer.
inline std::string gzipCompress(const std::string & data)
{
    size_t deflatedLen = 0;
    // window_bits = -15 => raw deflate (no zlib header); level 9; same params
    // miniz's own zip writer uses for stored entries.
    const mz_uint flags = tdefl_create_comp_flags_from_zip_params(9, -15, MZ_DEFAULT_STRATEGY);
    void * deflated = tdefl_compress_mem_to_heap(data.data(), data.size(), &deflatedLen, flags);
    if (!deflated) { return std::string(); }

    std::string out;
    out.reserve(deflatedLen + 18);

    const unsigned char header[10] = { 0x1f, 0x8b, 0x08, 0x00, 0, 0, 0, 0, 0x00, 0xff };
    out.append(reinterpret_cast<const char *>(header), 10);
    out.append(static_cast<const char *>(deflated), deflatedLen);
    mz_free(deflated);

    const mz_ulong crc = mz_crc32(MZ_CRC32_INIT,
                                  reinterpret_cast<const unsigned char *>(data.data()),
                                  data.size());
    auto appendLE = [&out](mz_uint32 v) {
        const char b[4] = { char(v & 0xff), char((v >> 8) & 0xff),
                            char((v >> 16) & 0xff), char((v >> 24) & 0xff) };
        out.append(b, 4);
    };
    appendLE(static_cast<mz_uint32>(crc));                       // CRC32 of uncompressed data
    appendLE(static_cast<mz_uint32>(data.size() & 0xffffffffu)); // ISIZE mod 2^32
    return out;
}

} // namespace Prismata
