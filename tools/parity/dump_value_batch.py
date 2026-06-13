"""Scale the C++<->PyTorch value export-parity harness to ~1000 self-play states.

Runs PrismataAI.exe --dump-features on each sampled self-play state JSON, then compares
against the matched PyTorch reference via compare_parity_deepsets.py. Exits nonzero if the
worst |value_cpp - value_torch| >= VALUE_TOL (1e-4 since 2026-06-13; measured floor ~1e-6).
SCOPE: pins weights-export + forward arithmetic only — the PyTorch reference consumes the
C++-extracted features, so extraction bugs pass BOTH sides identically; feature extraction
is pinned by training/tests/test_three_way_feature_parity.py (B2).

The 5-state harness (tools/parity/compare_parity_deepsets.py with the 5 final35_state_*.json
fixtures) only covers a handful of hand-picked positions. This driver fans the same
comparison out over hundreds-to-1000 real self-play states emitted by the
SelfPlayV2Exporter parity sidecar (sp_*.json.gz — gzipped since 2026-06-12; legacy raw
sp_*.json also accepted; run_iteration archives them per iteration into
training/data/rl_iter_<K>/parity_states/), giving a broad export-parity proof for an RL
candidate weight set before it is trusted.

State files are the bare-doc shape GameState::toJSONString() emits, which
PrismataAI.exe --dump-features consumes directly (no "gameState" wrapper needed);
.gz states are inflated into _batch_out/_inflated/ first.

MATCHED-TRIPLE RULE: --weights (the C++ --dump-features weights) MUST correspond to
--pt/--bin (the Python reference), or parity spuriously fails. Defaults use the interim
35-prop triple that the 5-state harness uses: --weights = the interim
docs/scratch/deepsets_mixed_35prop.bin, compared against compare_parity_deepsets.py's
interim defaults (ep30 .pt + interim .bin). For an RL candidate, pass
--weights candidate.bin --pt candidate.pt --bin candidate.bin so all three stay matched.

Usage (interim baseline proof — point --states-dir at an iteration's DURABLE archive;
the live <exportTrainingV2>_parity dirs are transient, archived/cleared per run):
  python tools/parity/dump_value_batch.py \
    --states-dir c:/libraries/PrismataAI/training/data/rl_iter_1/parity_states \
    --weights c:/libraries/PrismataAI/docs/scratch/deepsets_mixed_35prop.bin \
    --dave-bin c:/libraries/PrismataAI-dave-master/bin \
    --limit 1000
"""
import argparse
import glob
import gzip
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states-dir", required=True,
                    help="dir of self-play state JSONs (sp_*.json from the parity sidecar)")
    ap.add_argument("--weights", required=True,
                    help="weights .bin for the C++ --dump-features pass — pass an ABSOLUTE path "
                         "(the exe opens it literally / cwd-relative, NOT asset/config-relative)")
    ap.add_argument("--dave-bin", required=True,
                    help="dave engine bin/ dir (holds PrismataAI.exe + asset/)")
    ap.add_argument("--parity-dir", default="c:/libraries/PrismataAI-dave-master/tools/parity",
                    help="dir holding compare_parity_deepsets.py (dumps written to its _batch_out/)")
    ap.add_argument("--pt", default=None,
                    help="PyTorch .pt reference (passed through to compare_parity_deepsets.py)")
    ap.add_argument("--bin", default=None,
                    help="DSN2 .bin reference (passed through to compare_parity_deepsets.py)")
    ap.add_argument("--limit", type=int, default=1000,
                    help="max number of state JSONs to sample (default 1000)")
    args = ap.parse_args()

    # The sidecar exporter writes sp_*.json.gz since the 2026-06-12 replay-audit fixes
    # (gzipped, archived per iteration); accept legacy raw .json too. Dedupe by stem
    # (prefer .gz) so a dir holding both forms of one state never double-counts it.
    by_stem = {}
    for f in sorted(glob.glob(os.path.join(args.states_dir, "*.json"))):
        by_stem[f] = f
    for f in sorted(glob.glob(os.path.join(args.states_dir, "*.json.gz"))):
        by_stem[f[:-3]] = f   # stem 'x.json' -> prefer the .gz form
    all_states = sorted(by_stem.values())
    # B2 stratified sample (2026-06-13): the archive prefixes sidecars by slice
    # (general_sp_* / forced_sp_*) and the old sorted-prefix [:limit] took a ~100%
    # forced_ sample (alphabetical). Round-robin interleave the slices so the sample
    # covers BOTH data distributions; deterministic given the same dir contents.
    buckets = {}
    for f in all_states:
        prefix = os.path.basename(f).split("_sp_")[0] if "_sp_" in os.path.basename(f) else ""
        buckets.setdefault(prefix, []).append(f)
    states = []
    queues = [list(v) for _, v in sorted(buckets.items())]
    while len(states) < args.limit and any(queues):
        for q in queues:
            if q and len(states) < args.limit:
                states.append(q.pop(0))
    if not states:
        print(f"no state JSONs (.json / .json.gz) in {args.states_dir}", file=sys.stderr)
        sys.exit(2)

    # Write the per-state dumps into a dedicated subdir so they never get confused with
    # the committed harness fixtures (and are trivially gitignorable as build output).
    out_dir = os.path.join(args.parity_dir, "_batch_out")
    os.makedirs(out_dir, exist_ok=True)

    # PrismataAI.exe --dump-features reads plain files only: inflate .gz states into
    # a scratch subdir first and hand the exe the inflated path.
    inflate_dir = os.path.join(out_dir, "_inflated")
    os.makedirs(inflate_dir, exist_ok=True)

    exe = os.path.join(args.dave_bin, "PrismataAI.exe")
    dumps = []
    for i, s in enumerate(states):
        inflated = None
        if s.endswith(".gz"):
            inflated = os.path.join(inflate_dir, f"in_sp_{i:05d}.json")
            with gzip.open(s, "rb") as fz, open(inflated, "wb") as fo:
                fo.write(fz.read())
            s = inflated
        out = os.path.join(out_dir, f"out_sp_{i:05d}.json")
        r = subprocess.run([exe, "--dump-features", s, out, args.weights],
                           cwd=args.dave_bin,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if inflated is not None:
            os.remove(inflated)   # scratch only — don't leave ~1000 raw states on disk
        if r.returncode != 0:
            print(f"--dump-features failed (exit {r.returncode}) on {s}", file=sys.stderr)
            sys.exit(2)
        if not os.path.exists(out):
            print(f"--dump-features produced no output for {s}", file=sys.stderr)
            sys.exit(2)
        dumps.append(out)

    print(f"dumped {len(dumps)} states; invoking compare_parity_deepsets.py ...", file=sys.stderr)

    # compare_parity_deepsets.py takes the dumps as positional args. Passing ~1000 paths at
    # once overflows the Windows command-line length limit (WinError 206), so chunk the
    # dumps across several invocations and aggregate the pass/fail across all chunks. The
    # comparison is per-state and independent, so chunking does not change the verdict.
    ref_args = []
    if args.pt:
        ref_args += ["--pt", args.pt]
    if args.bin:
        ref_args += ["--bin", args.bin]

    import re
    CHUNK = 200  # ~200 * (path + space) stays well under the ~32 KB arg-length limit
    any_fail = False
    global_worst = 0.0
    nchunks = (len(dumps) + CHUNK - 1) // CHUNK
    for ci, start in enumerate(range(0, len(dumps), CHUNK)):
        chunk = dumps[start:start + CHUNK]
        cmd = [sys.executable, "compare_parity_deepsets.py"] + chunk + ref_args
        # Capture so we can aggregate a single global worst |dval| across all chunks,
        # while still streaming each chunk's table through to the console.
        r = subprocess.run(cmd, cwd=args.parity_dir,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = r.stdout or ""
        print(f"===== chunk {ci + 1}/{nchunks} ({len(chunk)} states) =====")
        print(out, end="")
        m = re.search(r"worst \|value_cpp - value_torch\| = ([0-9.eE+-]+)", out)
        if m:
            global_worst = max(global_worst, float(m.group(1)))
        if r.returncode != 0:
            any_fail = True

    print("=" * 78)
    print(f"AGGREGATE over {len(dumps)} self-play states "
          f"({nchunks} chunk(s) of <= {CHUNK}):")
    print(f"  global worst |value_cpp - value_torch| = {global_worst:.2e}  (tol 1e-03)")
    print(f"  overall: {'ALL PASS' if not any_fail else 'FAIL'}")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
