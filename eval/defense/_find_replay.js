'use strict';

// _find_replay.js — resolve a replay CODE to its archive path.
// Mirrors js_engine/oracle_diff.js's findFile fallback: try the URL-encoded
// filename (+ -> %2B, @ -> %40) first, then the raw code, each with .json.gz.
// Unlike oracle_diff (which returns a maybe-missing path), this THROWS a clear
// error if neither file exists. Shared by the defense-eval State-A/B/lookup tasks.

const fs = require('fs');
const path = require('path');

function find(archiveDir, code) {
    const enc = code.replace(/\+/g, '%2B').replace(/@/g, '%40');
    const candidates = [
        path.join(archiveDir, enc + '.json.gz'),
        path.join(archiveDir, code + '.json.gz'),
    ];
    for (const fp of candidates) {
        if (fs.existsSync(fp)) return fp;
    }
    throw new Error(`replay code "${code}" not found in ${archiveDir} (tried: ${candidates.join(', ')})`);
}

module.exports = { find };
