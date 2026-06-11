"""N-calibration: non-degeneracy SCREEN over MaxTraversals (spec §3/§9; A5).

ROLE (updated 2026-06-11 — N-10 truth-up): the campaign N is **FROZEN BY
JUDGMENT** at 1000 in `eval/campaign_frozen.json` (rl_campaign.md §1). This
driver does NOT pick the campaign N. Its output (`eval/n_calibration.json`,
incl. `recommended_N`) is a non-degeneracy SCREEN — evidence that a budget is
not degenerate — NOT a ranking, and NOT an instruction to retune. Do NOT
hand-edit RL_SelfPlay's MaxTraversals from its output: the stage-0 preflight
(`eval/preflight_config.py`) asserts the frozen tuple, and any change to N is
a NEW campaign (re-anchor + re-baseline, rl_campaign.md §1).

Sweep N in {100,256,512,1000,2000,5000} with the FROZEN production net; the
per-N non-degeneracy check:
  * game-length within 2 sigma of the human-1800 baseline,
  * P0 win-rate in [0.35, 0.65],
  * root visit-entropy above a floor (A5: the *effective* post-eps entropy, not raw),
  * win-rate vs the 100k-sim deployment net not catastrophically low (>= 0.20),
  * AND N comfortably > the root branching factor (IG-only ~8 children << MaxChildren=40),
    so the mandatory initial expansion is not most of the budget.

ADDENDUM A5 (effective-entropy + analytical eps sweep)
------------------------------------------------------
  * RAW aivisits (UCB1 counts) entropy is a SEARCH-HEALTH check -- it is NOT a
    self-play DIVERSITY measure. We label it search_health_entropy().
  * For DIVERSITY we compute the EFFECTIVE post-eps distribution actually sampled:
        p_temp[i] = visits[i]^(1/tau) / sum_j visits[j]^(1/tau)   (over eligible children, visits>0)
        p_eff     = (1-eps)*p_temp + eps*uniform                  (uniform = 1/k over those k)
    and report the Shannon entropy of p_eff (nats).
  * eps is the SOLE load-bearing exploration lever, so we SWEEP eps -- but ANALYTICALLY
    (no extra engine runs) from the recorded raw aivisits, over EPS_GRID at tau=1.0.
    Per N we report the effective-entropy-vs-eps curve and which eps first clears the
    floor. Do NOT freeze eps=0.25 by guess -- the curve informs the Task-14 freeze.

CO-INSTRUMENTATION (root_children / root_truncated)
---------------------------------------------------
The engine emits (gated by EmitDiagnostics, which query_move.js sets): aivisits (root
child visit counts), aiargmax, aichosen, and aitruncated (did the MaxChildren=40 cap drop
candidates). root_children = len(aivisits). We record per battery position, per N:
mean/max root_children and whether aitruncated was ever true. MaxChildren stays FROZEN at
40 -- this is OBSERVE-ONLY telemetry, NOT a co-tuned knob. The report must surface, for
the chosen N, that root_truncated is ~never true (IG-only ~8 children << 40) and that
root_children stays comfortably below 40 -- the observed branching/truncation data behind
the "N > branching factor" criterion.

  NOTE on the query_move.js diagnostics path: read_root_diagnostics() passes the per-N budget
  through to query_move.js (`--time-limit 0 --max-traversals N`, matching the RL_SelfPlay
  players' TimeLimit:0 + MaxTraversals:N pure-fixed-sims config), so the recorded aivisits and
  hence the search-health / effective-entropy curves are the GENUINE per-N visit shape -- NOT
  the 100k deployment budget. root_children / root_truncated remain iterator-driven and so are
  N-INDEPENDENT (that is expected and fine -- only the visit ENTROPY needed the per-N budget).
  The full sweep can additionally harvest per-N aivisits from the self-play V2 export's recorded
  stamps (the engine stamps argmax/chosen/rootChildren/rootTruncated per move) if a finer per-N
  entropy curve over many positions is needed; the query_move.js one-state path is the cheap smoke.

==============================================================================
HOW TO RUN THE FULL SWEEP (user-triggered -- this is a multi-hour compute run)
==============================================================================
This driver is committed WITHOUT running the full sweep and WITHOUT setting recommended_N.
To run it:
  1. Populate the battery: eval/calib_states/ must hold ~20 seeded F6-dump / replay states
     spanning turn numbers / resources / IG availability (pass --battery to override).
  2. Baseline H5 = training/data/human_1800_v2.h5 (pass --human-h5; NO hardcoded default
     path -- it is a required arg). The ENTROPY_FLOOR below is a starting value; tune it
     from the human baseline's effective entropy.
  3. The driver flips each RL_Cal_N{N} / RL_Cal_vs_deploy_N{N} config block to run:true,
     runs Prismata_Testing.exe, then flips it back. All blocks ship run:false. The WHOLE
     cal family runs Threads:8 (since 2026-06-11 — see THREADING below).
  4. Invoke (example):
       python eval/calibrate_n.py \
           --human-h5 training/data/human_1800_v2.h5 \
           --battery eval/calib_states \
           --dave-bin c:/libraries/PrismataAI-dave-master/bin \
           --weights neural_weights_mixed_v221.bin
  5. Output: eval/n_calibration.json (per-N metrics incl. the eps curve +
     root_children/root_truncated co-instrumentation + degenerate_reason, and
     recommended_N — a SCREEN verdict only; the campaign N stays frozen at
     campaign_frozen.json and MaxTraversals is never hand-edited from here).
  This driver does NOT set recommended_N for you on a partial run -- that is the user's call.

THREADING (2026-06-11: the whole cal family is Threads:8)
---------------------------------------------------------
  * Every RL_Cal_N* AND RL_Cal_vs_deploy_N* block now runs "Threads": 8. The old
    Threads:1 rationale for the self-play blocks ("per-record V2 export is
    single-thread-safe") was FALSE comfort: the Jun-10 audit X3-validated the V2
    export CLEAN at Threads:8, and worker-RNG collisions are gone since the
    per-seat/slot attribution engine commit (dave 6e93480).
  * MATCHED SETS (the comparability WIN): at Threads>1 the MAIN thread does only
    the card-set draws (workers play the games), so same-Seed blocks — the whole
    cal family shares Seed:4242 — draw the SAME card-set sequence across the
    N-family. Cross-N comparability IMPROVES vs Threads:1, where the game RNG
    interleaves with the set draws and each N's blocks see different sets.
    Runs are also ~5-8x faster in wall-clock.
  * COSTS: (1) game OUTCOMES are not cross-run reproducible — the Seed governs
    the main thread only; worker threads seed independently (the engine prints a
    warning at Threads>1). (2) Results are NOT comparable with the
    pre-2026-06-11 Threads:1 sweeps' per-set sequences (those interleaved the
    draws differently) — treat older n_calibration.json entries as a different
    measurement series.
"""
import argparse
import glob
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tactical_suite import parse_response  # noqa: E402  (robust pretty-JSON parser; DRY)
import run_eval  # noqa: E402  (run_cpp_tournament; parse_tournament_stdout/_latest_results_html used transitively)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
QUERY_MOVE = os.path.join(REPO, "js_engine", "query_move.js")

NS = [100, 256, 512, 1000, 2000, 5000]
EPS_GRID = [0.0, 0.05, 0.10, 0.15, 0.25, 0.35, 0.5]   # A5 analytical eps sweep at tau=1.0
LEN_SIGMA = 2.0
WR_BAND = (0.35, 0.65)
ENTROPY_FLOOR = 0.5   # nats; effective-entropy floor (tune from the human baseline)
WR_VS_DEPLOY_FLOOR = 0.20
# IG-only root action space is ~8 children; require N comfortably above it. MaxChildren=40
# is the hard cap (FROZEN). A budget that is mostly forced initial expansion is degenerate.
BRANCHING_FACTOR_GUESS = 30


def _read_dataset(f, key):
    """Read an h5py dataset to a numpy array, typed so static analysis doesn't choke.

    h5py.File.__getitem__ returns a Group | Dataset | Datatype union that Pyright cannot
    narrow, so `f[key][:]` trips reportIndexIssue/reportArgumentType. Asserting the Dataset
    type both narrows it for the type checker and gives a clear runtime error if a non-dataset
    key is ever passed. Runtime behavior is identical to the old `f[key][:]`."""
    import h5py
    ds = f[key]
    assert isinstance(ds, h5py.Dataset), f"{key} is not an h5py Dataset"
    return ds[:]


# ---------------------------------------------------------------------------
# A5 entropy core (pure -- unit-testable with no engine)
# ---------------------------------------------------------------------------

def _shannon(p):
    """Shannon entropy (nats) of a probability vector p (zeros ignored)."""
    return -sum(x * math.log(x) for x in p if x > 0.0)


def search_health_entropy(visits):
    """SEARCH-HEALTH entropy: Shannon entropy (nats) of the raw normalized visit counts.

    This is a search-health diagnostic (is the UCB1 tree spreading visits, or collapsing
    onto one child?). It is NOT a self-play diversity measure -- use effective_entropy()
    for diversity. Returns 0.0 for an empty / all-zero visit vector."""
    total = float(sum(v for v in visits if v > 0))
    if total <= 0.0:
        return 0.0
    p = [v / total for v in visits if v > 0]
    return _shannon(p)


def effective_entropy(visits, tau, eps):
    """A5 DIVERSITY entropy: Shannon entropy (nats) of the effective post-eps sampling dist.

        p_temp[i] = visits[i]^(1/tau) / sum_j visits[j]^(1/tau)   over eligible (visits>0) children
        p_eff     = (1-eps)*p_temp + eps*uniform                  uniform = 1/k over those k children

    This is the distribution self-play actually samples root children from, so its entropy
    is the real diversity signal (distinct from search_health_entropy on the raw counts).
    Returns 0.0 if there are no eligible (visits>0) children."""
    elig = [float(v) for v in visits if v > 0]
    k = len(elig)
    if k == 0:
        return 0.0
    if k == 1:
        # One eligible child: p_temp is degenerate; only eps-uniform can add entropy, but
        # uniform over k=1 is also a point mass -> entropy 0 regardless of eps.
        return 0.0
    inv_tau = 1.0 / tau
    powed = [v ** inv_tau for v in elig]
    z = sum(powed)
    p_temp = [x / z for x in powed]
    u = 1.0 / k
    p_eff = [(1.0 - eps) * pt + eps * u for pt in p_temp]
    return _shannon(p_eff)


def eps_curve(visits, tau=1.0, eps_grid=EPS_GRID, floor=ENTROPY_FLOOR):
    """Effective-entropy-vs-eps curve for one visit vector. Returns
    {"curve": {eps: H_eff}, "eps_clears_floor": first eps that reaches >= floor (or None)}."""
    curve = {round(e, 3): effective_entropy(visits, tau, e) for e in eps_grid}
    clears = next((e for e in eps_grid if curve[round(e, 3)] >= floor), None)
    return {"curve": curve, "eps_clears_floor": clears}


def aggregate_eps_curve(per_pos_visits, tau=1.0, eps_grid=EPS_GRID, floor=ENTROPY_FLOOR):
    """Mean effective-entropy-vs-eps curve over a list of per-position visit vectors.
    Returns {"curve": {eps: mean_H_eff}, "eps_clears_floor": first eps whose MEAN clears floor}."""
    if not per_pos_visits:
        return {"curve": {round(e, 3): 0.0 for e in eps_grid}, "eps_clears_floor": None}
    curve = {}
    for e in eps_grid:
        vals = [effective_entropy(v, tau, e) for v in per_pos_visits]
        curve[round(e, 3)] = sum(vals) / len(vals)
    clears = next((e for e in eps_grid if curve[round(e, 3)] >= floor), None)
    return {"curve": curve, "eps_clears_floor": clears}


# ---------------------------------------------------------------------------
# Human baseline game-length
# ---------------------------------------------------------------------------

def human_baseline_len(h5_path):
    """(mean, std) of human game length from the vectorized H5.

    vectorize_v2.py stores a per-record `total_plies` (uint16, verified present) = the
    game's total ply count, backfilled game-level. Records repeat per game, so we DEDUPE
    to one length per game before computing (mean, std): each game's records share the same
    (replay_code, total_plies), so we key on (replay_code, total_plies). This is the
    game-level distribution, not the record-weighted one (which over-weights long games)."""
    import h5py
    import numpy as np
    with h5py.File(h5_path, "r") as f:
        if "total_plies" not in f:
            raise RuntimeError(
                f"{h5_path} has no 'total_plies' dataset; vectorize_v2 length field missing")
        tplies = _read_dataset(f, "total_plies")
        codes = _read_dataset(f, "replay_codes") if "replay_codes" in f else None
    if codes is not None:
        seen = {}
        for c, t in zip(codes, tplies):
            key = (c.tobytes() if hasattr(c, "tobytes") else c, int(t))
            seen[key] = int(t)
        lengths = np.array(list(seen.values()), dtype=np.float64)
    else:
        lengths = np.asarray(tplies, dtype=np.float64)
    return float(lengths.mean()), float(lengths.std())


# ---------------------------------------------------------------------------
# Self-play metrics from a vectorized self-play H5
# ---------------------------------------------------------------------------

def metrics_from_h5(sp_h5):
    """Mean game length + P0 win-rate from a vectorized SELF-PLAY H5.

    Self-play V2 records carry NO replay_code (V2Record.cpp writes only ply_index /
    turn_number; outcome_p0 + total_plies are backfilled game-level), so we cannot dedupe
    by code. Instead we detect game boundaries via ply_index resetting to 0 (records are
    written in ply order, one selfplay_<id>.jsonl file per game, concatenated in order).
    Each game's length = its total_plies; its P0 outcome = label_A (== outcome_p0, with
    draw=0.5). P0 win-rate counts a draw as half a win, matching wilson.win_rate semantics."""
    import h5py
    import numpy as np
    with h5py.File(sp_h5, "r") as f:
        ply = _read_dataset(f, "ply_index")
        tplies = _read_dataset(f, "total_plies")
        label_a = _read_dataset(f, "label_A")   # == outcome_p0 (1.0 P0 win, 0.0 P0 loss, 0.5 draw)
    n = len(ply)
    if n == 0:
        return {"n_games": 0, "n_records": 0, "mean_game_length": 0.0, "p0_wr": 0.0}
    # Game starts where ply_index == 0.
    starts = np.where(np.asarray(ply) == 0)[0]
    if len(starts) == 0:
        starts = np.array([0])
    lengths = [float(tplies[i]) for i in starts]
    outcomes = [float(label_a[i]) for i in starts]   # one outcome per game (game-level label)
    return {
        "n_games": len(starts),
        "n_records": int(n),
        "mean_game_length": float(np.mean(lengths)) if lengths else 0.0,
        "p0_wr": float(np.mean(outcomes)) if outcomes else 0.0,
    }


# ---------------------------------------------------------------------------
# Battery -> root diagnostics (via query_move.js)
# ---------------------------------------------------------------------------

def _battery_states(battery_dir):
    return sorted(glob.glob(os.path.join(battery_dir, "*.json")))


def read_root_diagnostics(dave_exe, weights, player, battery_dir, n_traversals,
                          root_iter="HardIterator_5var_IGsubset_Root",
                          move_iter="HardIterator_5var",
                          tau=1.0, eps_grid=EPS_GRID, floor=ENTROPY_FLOOR,
                          timeout=90000):
    """Run query_move.js over each battery *.json state and aggregate root diagnostics.

    n_traversals is the per-N search budget (= MaxTraversals): we pass it to query_move.js
    as `--time-limit 0 --max-traversals n_traversals`, matching the RL_SelfPlay players'
    pure-fixed-sims config (TimeLimit:0 + MaxTraversals:N). The recorded aivisits -- and thus
    the search-health and effective-entropy curves -- are therefore the GENUINE per-N visit
    shape, NOT the 100k deployment budget query_move.js used to hardcode.

    Per position we collect: aivisits (-> search-health entropy + per-position eff-entropy
    curve via effective_entropy), root_children = len(aivisits), root_truncated =
    resp.get('aitruncated', False). root_children / root_truncated are iterator-driven and
    so N-INDEPENDENT (expected); only the visit entropy varies with n_traversals.

    Returns aggregates:
      mean_search_health_entropy, eps_curve (mean eff-entropy-vs-eps + eps_clears_floor),
      mean/max root_children, any_root_truncated, n_positions, per_position (raw)."""
    states = _battery_states(battery_dir)
    per_visits = []
    sh_entropies = []
    rchildren = []
    any_trunc = False
    per_position = []
    errors = []
    for st in states:
        try:
            resp = _query_one(dave_exe, weights, player, st, root_iter, move_iter,
                              n_traversals, timeout)
        except Exception as e:
            errors.append({"state": os.path.basename(st), "error": str(e)})
            continue
        visits = resp.get("aivisits") or []
        trunc = bool(resp.get("aitruncated", False))
        rc = len(visits)
        per_visits.append(visits)
        sh_entropies.append(search_health_entropy(visits))
        rchildren.append(rc)
        any_trunc = any_trunc or trunc
        per_position.append({
            "state": os.path.basename(st),
            "root_children": rc,
            "root_truncated": trunc,
            "search_health_entropy": search_health_entropy(visits),
            "eps_curve": eps_curve(visits, tau, eps_grid, floor),
            "aiargmax": resp.get("aiargmax"),
            "aichosen": resp.get("aichosen"),
        })
    agg = {
        "n_positions": len(per_visits),
        "mean_search_health_entropy": (sum(sh_entropies) / len(sh_entropies)) if sh_entropies else 0.0,
        "eps_curve": aggregate_eps_curve(per_visits, tau, eps_grid, floor),
        "mean_root_children": (sum(rchildren) / len(rchildren)) if rchildren else 0.0,
        "max_root_children": max(rchildren) if rchildren else 0,
        "any_root_truncated": any_trunc,
        "per_position": per_position,
    }
    if errors:
        agg["errors"] = errors
    return agg


def _query_one(dave_exe, weights, player, state_path, root_iter, move_iter,
               n_traversals, timeout):
    """Shell out to query_move.js for one state file; return the parsed response object.

    Passes the per-N budget as `--time-limit 0 --max-traversals n_traversals` so the engine
    searches at the genuine fixed-sims budget (TimeLimit:0 skips the time check; MaxTraversals
    caps the sims at N) instead of query_move.js's 100k deployment default. Reuses
    tactical_suite.parse_response (handles query_move.js's pretty-printed multi-line JSON --
    never splitlines()[-1])."""
    cmd = [
        "node", QUERY_MOVE,
        "--request", state_path,
        "--player", player,
        "--weights", weights,
        "--dave-exe", dave_exe,
        "--root-iterator", root_iter,
        "--move-iterator", move_iter,
        "--time-limit", "0",
        "--max-traversals", str(n_traversals),
        "--timeout", str(timeout),
    ]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       timeout=timeout / 1000.0 + 30)
    if p.returncode != 0:
        raise RuntimeError(f"query_move.js exited {p.returncode}: {p.stderr.strip()[-800:]}")
    return parse_response(p.stdout)


# ---------------------------------------------------------------------------
# Config-block flipping + running the C++ tournament
# ---------------------------------------------------------------------------

def _config_path(dave_bin):
    return os.path.join(dave_bin, "asset", "config", "config.txt")


def set_block_run(dave_bin, block_name, run):
    """Flip a single Benchmarks block's "run" flag in config.txt IN PLACE.

    Surgical line-level edit (regex on the matching block's single line), NOT a full
    json.load->json.dump reserialize -- the latter would reformat every single-line block in
    config.txt and produce a huge spurious diff. config.txt's convention is one Tournament
    block per line, so we find the line containing both `"name":"<block>"` and `"type":...
    "Tournament"` and rewrite only its `"run":<bool>` token. Validates the file still parses
    as strict JSON afterwards (utf-8-sig BOM-tolerant)."""
    import re
    path = _config_path(dave_bin)
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    target = re.compile(r'"name"\s*:\s*"' + re.escape(block_name) + r'"')
    run_re = re.compile(r'("run"\s*:\s*)(true|false)')
    new_val = "true" if run else "false"
    found = False
    for i, ln in enumerate(lines):
        if target.search(ln) and '"Tournament"' in ln:
            lines[i] = run_re.sub(lambda m: m.group(1) + new_val, ln, count=1)
            found = True
    if not found:
        raise RuntimeError(f"block '{block_name}' (Tournament) not found in {path}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
    # Sanity: file must still be strict JSON.
    with open(path, "r", encoding="utf-8-sig") as f:
        json.load(f)
    return found


def run_selfplay_block(dave_bin, N, vectorize_out, schema=None):
    """Flip RL_Cal_N{N} run:true, run Prismata_Testing.exe, flip back; concat the exported
    V2 shards -> vectorize_v2 -> H5 -> metrics_from_h5. Returns the metrics dict."""
    block = f"RL_Cal_N{N}"
    export_dir = os.path.join(dave_bin, "asset", "training", f"rl_cal_N{N}")
    # Clear stale shards from a prior/aborted run: the C++ export counter resets to 0 each
    # Prismata_Testing run, so leftover higher-numbered selfplay_*.jsonl would be wrongly
    # concatenated into this N's metrics (same class as the run_iteration.ps1 Stage-1 clear).
    for _stale in glob.glob(os.path.join(export_dir, "selfplay_*.jsonl")):
        os.remove(_stale)
    set_block_run(dave_bin, block, True)
    try:
        p = subprocess.run([os.path.join(dave_bin, "Prismata_Testing.exe")],
                           cwd=dave_bin, capture_output=True, text=True, timeout=36000)
        if p.returncode != 0:
            raise RuntimeError(f"Prismata_Testing.exe exited {p.returncode}\n{p.stderr[-1500:]}")
    finally:
        set_block_run(dave_bin, block, False)
    h5 = _vectorize_selfplay(export_dir, vectorize_out, schema)
    return metrics_from_h5(h5)


def _vectorize_selfplay(export_dir, out_prefix, schema=None):
    """Concat selfplay_*.jsonl shards in export_dir -> one JSONL -> vectorize_v2 -> H5.
    Returns the H5 path."""
    shards = sorted(glob.glob(os.path.join(export_dir, "selfplay_*.jsonl")))
    if not shards:
        raise RuntimeError(f"no selfplay_*.jsonl shards in {export_dir}")
    cat_jsonl = out_prefix + ".jsonl"
    with open(cat_jsonl, "w", encoding="utf-8") as out:
        for s in shards:
            with open(s, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        out.write(line if line.endswith("\n") else line + "\n")
    h5 = out_prefix + ".h5"
    cmd = [sys.executable, os.path.join(REPO, "training", "vectorize_v2.py"),
           "--input", cat_jsonl, "--output", h5]
    if schema:
        cmd += ["--schema", schema]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=7200)
    if p.returncode != 0:
        raise RuntimeError(f"vectorize_v2 exited {p.returncode}\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    return h5


def read_vs_deploy_wr(dave_bin, N):
    """Flip RL_Cal_vs_deploy_N{N} run:true, run Prismata_Testing.exe, flip back; parse the
    HTML statsTable (run_eval.parse_tournament_stdout) and return RL_SelfPlay_N{N}'s
    win-rate (draws=0.5) vs DSNN_Mixed35_5var. The orchestrator flips blocks; this driver
    drives the sweep."""
    from wilson import win_rate
    block = f"RL_Cal_vs_deploy_N{N}"
    player = f"RL_SelfPlay_N{N}"
    set_block_run(dave_bin, block, True)
    try:
        res = run_eval.run_cpp_tournament(dave_bin, block)
    finally:
        set_block_run(dave_bin, block, False)
    rec = res.get(player)
    if not rec or rec.get("wins") is None:
        return None
    return win_rate(rec["wins"], rec["draws"], rec["games"])


# ---------------------------------------------------------------------------
# Degeneracy decision
# ---------------------------------------------------------------------------

def degenerate(metrics, base_mu, base_sd):
    """Return the FIRST failing reason string, or None if the N passes the non-degeneracy
    check. metrics is the assembled per-N record (see main()).

    Gating criteria (A5 + spec):
      * game_length within LEN_SIGMA*base_sd of base_mu,
      * p0_wr in WR_BAND,
      * EFFECTIVE entropy can be pushed >= ENTROPY_FLOOR by SOME eps in the grid (i.e. the
        position is diverse-able); if NO eps clears it, the budget is too collapsed -> degenerate,
      * wr_vs_deploy >= WR_VS_DEPLOY_FLOOR (None = unknown -> not gated here),
      * N comfortably > the branching factor (N > BRANCHING_FACTOR_GUESS).
    any_root_truncated / max_root_children are RECORDED, not gated (co-instrument only);
    main() flags any_root_truncated separately."""
    N = metrics["N"]
    ml = metrics.get("mean_game_length")
    if ml is not None and base_sd > 0 and abs(ml - base_mu) > LEN_SIGMA * base_sd:
        return (f"game_length {ml:.1f} outside baseline {base_mu:.1f}+/-{LEN_SIGMA:.0f}sigma "
                f"({LEN_SIGMA * base_sd:.1f})")
    p0 = metrics.get("p0_wr")
    if p0 is not None and not (WR_BAND[0] <= p0 <= WR_BAND[1]):
        return f"p0_wr {p0:.3f} outside band {WR_BAND}"
    diag = metrics.get("diagnostics") or {}
    eps_clears = (diag.get("eps_curve") or {}).get("eps_clears_floor")
    if eps_clears is None:
        return f"effective entropy never clears floor {ENTROPY_FLOOR} for any eps in {EPS_GRID}"
    wr_dep = metrics.get("wr_vs_deploy")
    if wr_dep is not None and wr_dep < WR_VS_DEPLOY_FLOOR:
        return f"wr_vs_deploy {wr_dep:.3f} < floor {WR_VS_DEPLOY_FLOOR}"
    if N <= BRANCHING_FACTOR_GUESS:
        return f"N={N} not comfortably > branching factor {BRANCHING_FACTOR_GUESS}"
    return None


# ---------------------------------------------------------------------------
# Sweep driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="N-calibration sweep + non-degeneracy check (A5).")
    ap.add_argument("--baseline-h5", default=os.path.join(REPO, "training", "data", "fleet_v4_v2.h5"),
                    help="game-length baseline H5. MUST be a FULL-WIPEOUT corpus (MB self-play), NOT a "
                         "human corpus: human games end in RESIGNATION (lengths biased SHORT), while RL "
                         "self-play has resignation DISABLED and plays to wipeout (~5 turns longer). "
                         "Default: MB fleet_v4_v2 (mu~30.5, 2sigma~[16,45]).")
    ap.add_argument("--human-h5", default=None,
                    help="DEPRECATED alias for --baseline-h5 (back-compat). Do NOT pass a human corpus "
                         "here -- resignation bias makes the game-length band too strict (see --baseline-h5).")
    ap.add_argument("--battery", default=os.path.join(HERE, "calib_states"),
                    help="dir of seeded F6-dump/replay states (~20 spanning turn/resources/IG)")
    ap.add_argument("--dave-bin", default=r"c:/libraries/PrismataAI-dave-master/bin",
                    help="dir holding Prismata_Testing.exe / PrismataAI.exe / asset/config")
    ap.add_argument("--dave-exe", default=None,
                    help="responder exe for query_move.js (default: <dave-bin>/PrismataAI.exe)")
    ap.add_argument("--weights", default="neural_weights_mixed_v221.bin",
                    help="frozen production net (resolved under <dave-bin>/asset/config/)")
    ap.add_argument("--schema", default=os.path.join(REPO, "training", "schema_v2.json"))
    ap.add_argument("--ns", type=int, nargs="+", default=NS, help="N grid to sweep")
    ap.add_argument("--out", default=os.path.join(HERE, "n_calibration.json"))
    ap.add_argument("--scratch", default=os.path.join(HERE, "_calib_scratch"),
                    help="scratch dir for concatenated JSONL / vectorized H5 (untracked)")
    ap.add_argument("--diagnostics-only", action="store_true",
                    help="only run the battery diagnostics (no self-play / vs-deploy tournaments)")
    args = ap.parse_args()

    dave_exe = args.dave_exe or os.path.join(args.dave_bin, "PrismataAI.exe")
    os.makedirs(args.scratch, exist_ok=True)

    baseline_h5 = args.baseline_h5 if (args.baseline_h5 and os.path.exists(args.baseline_h5)) else args.human_h5
    if not baseline_h5 or not os.path.exists(baseline_h5):
        ap.error("no length-baseline H5 found; pass --baseline-h5 <MB full-wipeout corpus>")
    base_mu, base_sd = human_baseline_len(baseline_h5)
    print(f"length baseline ({os.path.basename(baseline_h5)}, full-wipeout MB): mu={base_mu:.2f} "
          f"sigma={base_sd:.2f} (2sigma band = "
          f"[{base_mu - LEN_SIGMA*base_sd:.1f}, {base_mu + LEN_SIGMA*base_sd:.1f}])")

    records = []
    for N in args.ns:
        print(f"\n=== N={N} ===")
        rec = {"N": N}
        player = f"RL_SelfPlay_N{N}"

        # Root diagnostics (battery; A5 effective-entropy + eps curve + co-instrument).
        # Pass the per-N budget so the recorded visit shape / entropy is GENUINELY per-N
        # (query_move.js searches at TimeLimit:0 + MaxTraversals:N, not the 100k default).
        diag = read_root_diagnostics(dave_exe, args.weights, player, args.battery, N)
        rec["diagnostics"] = diag
        print(f"  diag: search_health_H={diag['mean_search_health_entropy']:.3f} "
              f"eff_eps_clears={diag['eps_curve']['eps_clears_floor']} "
              f"root_children mean={diag['mean_root_children']:.1f} max={diag['max_root_children']} "
              f"any_truncated={diag['any_root_truncated']}")

        if not args.diagnostics_only:
            # Self-play -> V2 -> H5 -> metrics.
            try:
                m = run_selfplay_block(args.dave_bin, N,
                                       os.path.join(args.scratch, f"rl_cal_N{N}"),
                                       schema=args.schema)
                rec.update({"mean_game_length": m["mean_game_length"], "p0_wr": m["p0_wr"],
                            "n_games": m["n_games"], "n_records": m["n_records"]})
                print(f"  selfplay: n_games={m['n_games']} mean_len={m['mean_game_length']:.1f} "
                      f"p0_wr={m['p0_wr']:.3f}")
            except Exception as e:
                rec["selfplay_error"] = str(e)
                print(f"  selfplay ERROR: {e}")
            # Win-rate vs the deployment net.
            try:
                wr = read_vs_deploy_wr(args.dave_bin, N)
                rec["wr_vs_deploy"] = wr
                print(f"  wr_vs_deploy={wr}")
            except Exception as e:
                rec["vs_deploy_error"] = str(e)
                print(f"  vs_deploy ERROR: {e}")

        rec["degenerate_reason"] = degenerate(rec, base_mu, base_sd)
        if diag.get("any_root_truncated"):
            rec["WARNING_root_truncated"] = (
                f"root_truncated was TRUE for N={N} -- unexpected for IG-only (~8 children << 40)")
        print(f"  degenerate_reason={rec['degenerate_reason']}")
        records.append(rec)

    passing = [r for r in records if r.get("degenerate_reason") is None]
    recommended_N = min((r["N"] for r in passing), default=None)

    out = {
        "human_baseline": {"mean_game_length": base_mu, "std_game_length": base_sd},
        "config": {
            "NS": args.ns, "EPS_GRID": EPS_GRID, "LEN_SIGMA": LEN_SIGMA, "WR_BAND": list(WR_BAND),
            "ENTROPY_FLOOR": ENTROPY_FLOOR, "WR_VS_DEPLOY_FLOOR": WR_VS_DEPLOY_FLOOR,
            "BRANCHING_FACTOR_GUESS": BRANCHING_FACTOR_GUESS, "tau": 1.0,
        },
        "per_N": records,
        "recommended_N": recommended_N,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\n-> {args.out}")
    if recommended_N is not None:
        print(f"RECOMMENDED_N = {recommended_N} (smallest N passing the non-degeneracy check)")
    else:
        print("RECOMMENDED_N = None (no N passed -- inspect degenerate_reason per N)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
