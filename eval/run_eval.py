"""Per-iteration RL "proof-of-life" eval. Wilson CIs, collapse-on-abort, incremental manifest.

Anchors (v4 proof-of-life set, both GENERAL pool only):
  1. origin    : candidate (RL_Eval) vs RL_Eval_origin — the PERMANENT v221 reference, never
                 repointed. The relative-drift anchor and the COLLAPSE/abort signal (C++ tournament,
                 block RL_PoL_origin).
  2. masterbot : candidate (RL_Eval) vs MasterBot_SWF — an Alpha-Beta Playout player (NO
                 NeuralNet, no WeightsFile). The absolute-strength trend (C++ tournament,
                 block RL_PoL_masterbot).
All eval players run at the DEPLOYMENT budget (TimeLimit:7000/MaxTraversals:100000), NOT the self-play N (A1).

COLLAPSE (2026-06-15, replaces the old REJECT/REVIEW/INCOMPLETE verdict): the proof-of-life loop
no longer pretends to certify improvement OR non-inferiority — it only aborts on a coarse,
point-estimate COLLAPSE against the permanent origin reference. compute_collapse(origin_general,
threshold) returns:
  True   iff the origin/general anchor completed (games>0) AND its win_rate < --abort-winrate
         (default 0.35) — the candidate has drifted badly enough vs v221 to halt the campaign;
  False  iff it completed and win_rate >= threshold;
  None   iff the origin anchor is missing/errored OR completed with ZERO games (can't decide).
This is an ABORT signal, NOT a powered gate — every WR and CI is still recorded as information.

INCREMENTAL MANIFEST: the manifest is (re)written atomically (temp file + os.replace) after
EVERY completed pool/anchor, carrying "complete": false and "anchors_completed": [...] until
the final write — a killed run can no longer erase hours of tournament results (Jun-8 failure).

PROVENANCE (active): before any block flips on, Players.<candidate>.WeightsFile in the dave
config.txt must equal basename(--weights) (hard abort otherwise). Each C++ anchor's stderr is
captured and must contain the engine's "AIParameters: created per-player NeuralNet from
<...candidate.bin>" load line; the result is stamped "engine_confirmed_load" per anchor and a
completed-but-unconfirmed anchor hard-fails (after being recorded for the post-mortem).
Opponent side: the origin anchor's opponent (RL_Eval_origin) is pinned to the PERMANENT origin
bin (--origin-weights), so the SAME stderr must also confirm that load (player-level,
engine_confirmed_parent_load) — a forgotten repoint would silently turn "candidate vs origin"
into "candidate vs something else". The masterbot opponent (MasterBot_SWF) is an AB Playout
player with NO NeuralNet, so there is NO opponent load line to confirm — its opponent-load check
is SKIPPED (opp_kind=None), not hard-failed.

STATS NOTE: CIs are iid Wilson only (eval/wilson.py). Where the per-game rounds CSV exists a
paired per-card-set CI is REPORTED alongside (it removes between-set variance the pooled CI
ignores).

PARSE-FORMAT NOTE (validated Step 5, 2026-06-03): the C++ tournament's STDOUT only emits a
seat-symmetric *score matrix* (player x player score, plus TotalScore) and a "Games completed"
line -- it does NOT carry Wins/Loss/Draw/Games per player. The canonical per-player W/L/D/Games
table is written to the HTML results file (tests/Tournament_<name>_<date>.html, table id="statsTable").
run_cpp_tournament() therefore reads that HTML file and parse_tournament_stdout() parses its
statsTable rows. A stdout score-matrix fallback is retained for diagnostics.
"""
import argparse, csv, hashlib, json, os, subprocess, sys, time, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wilson import win_rate, wilson_ci, paired_round_ci


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _latest_results_html(dave_bin, block_name):
    """Newest tests/Tournament_<block_name>_*.html under the dave bin dir."""
    pat = os.path.join(dave_bin, "tests", f"Tournament_{block_name}_*.html")
    files = sorted(glob.glob(pat), key=os.path.getmtime)
    return files[-1] if files else None


def run_cpp_tournament(dave_bin, block_name, stderr_out=None, rounds_csv_out=None):
    """Run Prismata_Testing.exe (executes every run:true Benchmarks block) and return the
    per-player {wins,draws,games} for `block_name`, read from that block's HTML statsTable.
    The caller is responsible for having flipped exactly the desired block(s) to run:true.

    stderr_out: optional list — receives the subprocess's full stderr text (the engine prints
    its per-player NeuralNet load confirmations there; see engine_confirmed_load).
    rounds_csv_out: optional list — receives the parsed rows of this run's per-game
    Tournament_<block>_*_rounds.csv (A4, 2026-06-13) if present and fresh; the raw material
    for the paired per-card-set CI."""
    before_run = time.time()
    p = subprocess.run([os.path.join(dave_bin, "Prismata_Testing.exe")],
                       cwd=dave_bin, capture_output=True, text=True, timeout=36000)
    if stderr_out is not None:
        stderr_out.append(p.stderr or "")
    if p.returncode != 0:
        raise RuntimeError(f"Prismata_Testing.exe exited {p.returncode}\nstderr: {p.stderr[-2000:]}")
    html_path = _latest_results_html(dave_bin, block_name)
    html_text = ""
    if html_path:
        # Guard against a stale HTML from a previous run masquerading as this run's result.
        if os.path.getmtime(html_path) < before_run:
            raise RuntimeError(
                f"HTML predates this run — block '{block_name}' may not have run: {html_path}")
        with open(html_path, encoding="utf-8", errors="replace") as f:
            html_text = f.read()
    else:
        print(f"WARNING: no results HTML found for block '{block_name}' — "
              "falling back to the stdout score-matrix (no W/L/D available)", file=sys.stderr)
    if rounds_csv_out is not None:
        csv_path = (html_path or "").replace(".html", "_rounds.csv")
        if csv_path and os.path.isfile(csv_path) and os.path.getmtime(csv_path) >= before_run:
            with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
                rounds_csv_out.extend(list(csv.DictReader(f)))
    # Prefer the canonical HTML statsTable; fall back to stdout score-matrix if absent.
    return parse_tournament_stdout(html_text or (p.stdout + p.stderr), block_name)


def parse_tournament_stdout(text, block_name):
    """Extract per-player Wins/Draws/Games. Returns {player_name: {'wins','draws','games'}}.

    Primary path: the HTML 'Overall Statistics' table (id="statsTable") whose columns are
    Player, Score, Games, Wins, Loss, Draw, ... -- rows look like:
        <tr><td>DSNN_Mixed35_5var_F1s</td><td>0.5</td><td>4</td><td>2</td><td>2</td><td>0</td>...
    Fallback path: the stdout score matrix (no W/L/D available there) -- parsed for player names
    + TotalScore only, with wins/draws left as None so the caller can detect the degraded case.
    """
    out = {}

    # --- Primary: HTML statsTable (canonical Wins/Loss/Draw/Games) ---
    block = re.search(r'id="statsTable".*?</table>', text, re.S)
    scope = block.group(0) if block else text
    row_re = re.compile(
        r"<tr><td>([^<]+)</td>"      # Player
        r"<td>[\d.eE+\-]+</td>"      # Score
        r"<td>(\d+)</td>"            # Games
        r"<td>(\d+)</td>"            # Wins
        r"<td>(\d+)</td>"            # Loss
        r"<td>(\d+)</td>"           # Draw
    )
    for m in row_re.finditer(scope):
        name, games, wins, _loss, draw = m.groups()
        out[name.strip()] = {"wins": int(wins), "draws": int(draw), "games": int(games)}
    if out:
        return out

    # --- Fallback: stdout score matrix (no W/L/D). Capture name + TotalScore only. ---
    # Final matrix rows look like:  "<player>  -  <score> ... <TotalScore>"
    for m in re.finditer(r"^(\S+)\s+(?:-|[\d.]+)(?:\s+(?:-|[\d.]+))*\s+([\d.]+)\s*$", text, re.M):
        name, total = m.group(1), m.group(2)
        if name in ("Games", "Playing", "Starting", "Tournament"):
            continue
        out[name] = {"wins": None, "draws": None, "games": None, "total_score": float(total)}
    return out


# ---------------------------------------------------------------------------
# Provenance + manifest persistence
# ---------------------------------------------------------------------------

# AIParameters.cpp prints this to STDERR when it constructs a per-player NeuralNet
# (PLAYER-LEVEL since A2, 2026-06-13 — the old file-level line could not distinguish WHICH
# player loaded a shared parent bin, so the N-2 guard structurally could not catch its own
# documented scenario, prov-06):
#   "AIParameters: created per-player NeuralNet from asset/config/<file> for player '<name>'"
ENGINE_LOAD_MARKER = "created per-player NeuralNet from"


def engine_confirmed_load(stderr_text, weights_basename, player=None):
    """True iff the engine's stderr confirms it constructed a per-player NeuralNet from the
    given weights file (marker AND basename on the SAME line). When `player` is given, the
    SAME line must also carry "for player '<player>'" — the (player, basename) PAIR is the
    confirmation, since many config players share the parent bin (prov-06)."""
    needle = "for player '%s'" % player if player else None
    for line in (stderr_text or "").splitlines():
        if ENGINE_LOAD_MARKER in line and weights_basename in line:
            if needle is None or needle in line:
                return True
    return False


def verify_config_weights(dave_bin, candidate_player, weights_basename):
    """Pre-flight provenance: assert Players.<candidate_player>.WeightsFile in the dave
    config.txt equals the candidate --weights basename BEFORE any tournament flips on.
    Hard abort with both values otherwise — the tournament would silently eval the wrong net
    (the candidate_net_sha256 stamp alone verifies nothing)."""
    path = _config_path(dave_bin)
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    player = cfg.get("Players", {}).get(candidate_player)
    if player is None:
        raise RuntimeError(f"provenance: player '{candidate_player}' not found in {path}")
    wf = player.get("WeightsFile")
    if wf != weights_basename:
        raise RuntimeError(
            f"provenance: config Players.{candidate_player}.WeightsFile={wf!r} != candidate "
            f"--weights basename {weights_basename!r} ({path}) — refusing to run: the "
            "tournament would evaluate the wrong net. Repoint the config (run_iteration.ps1 "
            "stage 7) or pass the matching --weights.")


def write_manifest(manifest, path):
    """Atomic-ish manifest write (temp file + os.replace) so a kill mid-write can't leave torn
    JSON. No-op when path is None (pure unit-test use of build_manifest)."""
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Anchor wiring (config-block flip -> C++ tournament -> parse -> Wilson CI)
# ---------------------------------------------------------------------------

# Frozen per eval/rl_campaign.md §1. group1 of every anchor block is the candidate (RL_Eval),
# repointed to the candidate .bin by run_iteration.ps1 stage 7.
CANDIDATE_PLAYER = "RL_Eval"
# E/Y are recorded METADATA only (historical pre-registered effect size / regression tolerance);
# nothing gates on them — kept for the manifest record.
E_EFFECT = 0.05   # (info) +5 pp -- the smallest IG-driven gain judged worth AWS spend.
Y_REG    = 0.03   # (info) regression tolerance once used by the retired d_reg gate.
HEADLINE_POOL = "general"   # v4 PoL anchors are general-only; the dashboard renders one cell per anchor.

# Anchor C++ tournament blocks (must exist run:false in config.txt; group1=RL_Eval candidate).
# A pool maps to a LIST of blocks whose results aggregate into one cell. v4 proof-of-life set:
#   origin    -> vs RL_Eval_origin (PERMANENTLY v221, never repointed — drl-03): the relative-
#                drift anchor + the COLLAPSE/abort signal. block RL_PoL_origin (general only).
#   masterbot -> vs MasterBot_SWF (AB Playout, NO NeuralNet): the absolute-strength trend.
#                block RL_PoL_masterbot (general only).
ANCHOR_BLOCKS = {
    "origin":    {"general": ["RL_PoL_origin"]},
    "masterbot": {"general": ["RL_PoL_masterbot"]},
}
# The pinned opponent each anchor's stderr must confirm (player-level), and the opp_kind that
# names the provenance source: "origin" resolves to --origin-weights; None means the opponent is
# a no-NeuralNet AB player (MasterBot_SWF) — there is NO opponent load line to confirm, so the
# opponent-load check is SKIPPED for it.
ANCHOR_OPPONENTS = {
    "origin":    ("RL_Eval_origin", "origin"),
    "masterbot": ("MasterBot_SWF", None),   # AB Playout opponent: no NeuralNet load line to confirm
}


def _config_path(dave_bin):
    return os.path.join(dave_bin, "asset", "config", "config.txt")


def set_block_run(dave_bin, block_name, run):
    """Flip ONE Tournament block's "run" flag in config.txt IN PLACE. Surgical line-level regex
    rewrite (NOT a json.load->json.dump reserialize, which would reformat every single-line block
    and produce a huge spurious diff) -- mirrors calibrate_n.set_block_run / run_iteration.ps1's
    Edit-Config. Re-parses the whole file as strict JSON afterwards so a bad edit fails loudly."""
    path = _config_path(dave_bin)
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    target = re.compile(r'"name"\s*:\s*"' + re.escape(block_name) + r'"')
    run_re = re.compile(r'("run"\s*:\s*)(true|false)')
    nv = "true" if run else "false"
    found = False
    for i, ln in enumerate(lines):
        if target.search(ln) and '"Tournament"' in ln:
            lines[i] = run_re.sub(lambda m: m.group(1) + nv, ln, count=1)
            found = True
    if not found:
        raise RuntimeError(f"block '{block_name}' (Tournament) not found in {path}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
    with open(path, "r", encoding="utf-8-sig") as f:
        json.load(f)  # strict-JSON sanity


def candidate_round_scores(csv_rows, candidate_player):
    """Per-round candidate scores from the A4 per-game CSV: each round = one shared card set
    played in both seat orders; score_r = (wins + 0.5*draws)/games_in_round in [0,1]. The raw
    material for the paired per-card-set CI (rl-design-05): pairing removes the between-set
    variance component the pooled iid Wilson CI ignores."""
    rounds = {}
    for row in csv_rows:
        try:
            r = int(row["round"])
        except (KeyError, TypeError, ValueError):
            continue
        won = 0.0
        if row.get("winner_seat") == "D":
            won = 0.5
        elif row.get("winner_seat") == "0" and row.get("white_name") == candidate_player:
            won = 1.0
        elif row.get("winner_seat") == "1" and row.get("black_name") == candidate_player:
            won = 1.0
        g, w = rounds.get(r, (0, 0.0))
        rounds[r] = (g + 1, w + won)
    return [w / g for g, w in rounds.values() if g > 0]


def run_anchor_block(dave_bin, block_name, candidate_player=CANDIDATE_PLAYER, weights_basename=None,
                     parent_basename=None, opponent_player=None):
    """Flip ONE anchor block run:true, run Prismata_Testing.exe, parse the candidate's W/L/D from its
    HTML statsTable, flip back (in a finally). Returns a FLAT anchor dict
    {block,candidate,wins,draws,games,win_rate,ci:[lo,hi](,paired_ci,rounds)} the dashboard can render
    directly, or an {block,error,...} dict if the candidate row / W/L/D could not be parsed.

    When weights_basename is given, the engine's stderr is checked for the per-player NeuralNet
    load confirmation — PLAYER-LEVEL since prov-06: the (candidate_player, weights_basename)
    pair must appear on one line — stamped "engine_confirmed_load". When parent_basename is
    given (N-2), the (opponent_player, parent_basename) pair must likewise confirm, stamped
    "engine_confirmed_parent_load". If the per-game rounds CSV (A4) is present, a paired
    per-card-set CI is stamped alongside the iid Wilson CI (REPORTED, not the verdict input)."""
    set_block_run(dave_bin, block_name, True)
    stderr_sink = []
    csv_rows = []
    try:
        results = run_cpp_tournament(dave_bin, block_name, stderr_out=stderr_sink,
                                     rounds_csv_out=csv_rows)
    finally:
        set_block_run(dave_bin, block_name, False)
    stderr_text = "".join(stderr_sink)
    confirmed = (engine_confirmed_load(stderr_text, weights_basename, candidate_player)
                 if weights_basename else None)
    parent_confirmed = (engine_confirmed_load(stderr_text, parent_basename, opponent_player)
                        if parent_basename else None)

    def _stamp(out):
        if confirmed is not None:
            out["engine_confirmed_load"] = confirmed
        if parent_confirmed is not None:
            out["engine_confirmed_parent_load"] = parent_confirmed
        return out

    cand = results.get(candidate_player)
    if not cand or cand.get("wins") is None:
        return _stamp({"block": block_name,
                       "error": f"no W/L/D for candidate '{candidate_player}' (degraded score-matrix fallback?)",
                       "raw_players": sorted(results)})
    wins, draws, games = cand["wins"], cand["draws"], cand["games"]
    p = win_rate(wins, draws, games)
    lo, hi = wilson_ci(p, games)
    cell = {"block": block_name, "candidate": candidate_player,
            "wins": wins, "draws": draws, "games": games, "win_rate": p, "ci": [lo, hi]}
    scores = candidate_round_scores(csv_rows, candidate_player)
    if scores:
        plo, phi = paired_round_ci(scores)
        cell["paired_ci"] = [plo, phi]
        cell["rounds"] = len(scores)
        cell["round_scores"] = scores   # raw per-set scores (multi-block pools re-pool these)
    return _stamp(cell)


def aggregate_pool_cells(cells):
    """Combine the per-block cells of one pool (e.g. the generalA/generalB seed panels) into a
    single cell: counts sum; the Wilson CI is recomputed on the pooled counts; the paired CI is
    recomputed over the UNION of per-round scores (rounds are independent across panels). Any
    errored sub-block makes the pool errored (a partial pool must not masquerade as complete).
    Provenance stamps AND-combine."""
    cells = list(cells)
    if len(cells) == 1:
        c = dict(cells[0])
        c.pop("round_scores", None)
        c["blocks"] = [cells[0].get("block")]
        return c
    if any("error" in c or "win_rate" not in c for c in cells):
        return {"blocks": [c.get("block") for c in cells],
                "error": "one or more sub-blocks errored",
                "sub_blocks": [{k: v for k, v in c.items() if k != "round_scores"} for c in cells]}
    wins = sum(c["wins"] for c in cells)
    draws = sum(c["draws"] for c in cells)
    games = sum(c["games"] for c in cells)
    p = win_rate(wins, draws, games)
    lo, hi = wilson_ci(p, games)
    out = {"blocks": [c.get("block") for c in cells], "candidate": cells[0].get("candidate"),
           "wins": wins, "draws": draws, "games": games, "win_rate": p, "ci": [lo, hi],
           "sub_blocks": [{k: v for k, v in c.items() if k != "round_scores"} for c in cells]}
    scores = [s for c in cells for s in c.get("round_scores", [])]
    if scores:
        plo, phi = paired_round_ci(scores)
        out["paired_ci"] = [plo, phi]
        out["rounds"] = len(scores)
    for key in ("engine_confirmed_load", "engine_confirmed_parent_load"):
        vals = [c.get(key) for c in cells if key in c]
        if vals:
            out[key] = all(vals)
    return out


def compute_collapse(origin_cell, threshold):
    """Point-estimate COLLAPSE/abort signal (v4; replaces REJECT/REVIEW/INCOMPLETE).
    origin_cell = the origin/general anchor dict (candidate vs the PERMANENT origin reference):
      True   iff it completed (games>0) AND its win_rate < threshold (drifted badly vs origin);
      False  iff it completed and win_rate >= threshold;
      None   iff it is missing/errored OR completed with ZERO games (can't decide).
    This is a COARSE abort signal, not a powered gate."""
    if not (isinstance(origin_cell, dict) and "win_rate" in origin_cell and origin_cell.get("games")):
        return None
    return origin_cell["win_rate"] < threshold


def _refresh_summary(manifest, threshold):
    """Recompute the collapse flag + information-only WR/CI summary from whatever anchors are
    recorded so far. Called before every incremental write so even a partial (killed-run)
    manifest carries a self-consistent collapse signal."""
    def _gen_cell(anchor):
        c = manifest["anchors"].get(anchor, {}).get("pools", {}).get("general")
        return c if isinstance(c, dict) and "win_rate" in c else None

    origin = _gen_cell("origin")
    masterbot = _gen_cell("masterbot")
    manifest["collapse"] = compute_collapse(origin, threshold)
    manifest["abort_winrate"] = threshold
    info = {"E": E_EFFECT, "Y": Y_REG}   # recorded metadata only — nothing gates on them
    if origin:   # the relative-drift anchor + the abort signal
        info["origin_win_rate"] = origin["win_rate"]
        info["origin_wr_ci"] = origin["ci"]
        if "paired_ci" in origin:
            info["origin_paired_ci"] = origin["paired_ci"]
    if masterbot:   # the absolute-strength trend
        info["masterbot_win_rate"] = masterbot["win_rate"]
        info["masterbot_wr_ci"] = masterbot["ci"]
        if "paired_ci" in masterbot:
            info["masterbot_paired_ci"] = masterbot["paired_ci"]
    manifest["summary"] = info
    manifest["pools"] = {
        "origin":    {"role": "relative-drift anchor vs the PERMANENT origin reference + the "
                              "collapse/abort signal (collapse iff win_rate<abort_winrate)",
                      **(origin or {"status": "unavailable"})},
        "masterbot": {"role": "absolute-strength trend vs MasterBot_SWF (AB Playout); non-gating",
                      **(masterbot or {"status": "unavailable"})},
    }


def build_manifest(args, run_anchor=run_anchor_block, manifest_path=None):
    """Assemble the eval manifest dict, writing it to manifest_path INCREMENTALLY (atomic temp +
    os.replace) after every completed pool/anchor — a crash/kill leaves a readable partial
    manifest ("complete": false, "anchors_completed": [...]) instead of nothing. The injectable
    runner keeps the orchestration + collapse logic unit-testable without the C++ engine:
    run_anchor(dave_bin, block, player, weights_basename, opp_basename, opponent_player) -> anchor-dict."""
    weights_basename = os.path.basename(args.weights)
    # The origin anchor's opponent (RL_Eval_origin) is pinned to the PERMANENT origin bin, so the
    # engine stderr must confirm that load too (player-level). The masterbot opponent is an AB
    # Playout player with NO NeuralNet -> no opponent load line to confirm (opp_kind=None).
    origin_basename = (os.path.basename(args.origin_weights)
                       if getattr(args, "origin_weights", None) else None)
    # Self-match guard: a candidate-vs-itself origin eval is vacuous (one stderr load line would
    # satisfy BOTH stamps). The caller should omit the origin anchor for a deliberate self-test.
    if origin_basename and origin_basename == weights_basename:
        raise RuntimeError(f"--weights and --origin-weights are the same file ({weights_basename}) "
                           "-- candidate-vs-itself origin eval is vacuous. Omit the origin anchor "
                           "(or --origin-weights) for a deliberate self-match.")
    # Active provenance pre-flight: the config must already point the candidate player at the
    # candidate net BEFORE any tournament flips on.
    verify_config_weights(args.dave_bin, args.candidate_player, weights_basename)
    wpath = os.path.join(args.dave_bin, "asset/config", args.weights)
    # A1 + preflight-gaps-06: record the ACTUAL eval budget from the live config, never a
    # hardcoded claim (the old literal could silently diverge from what actually ran).
    with open(_config_path(args.dave_bin), encoding="utf-8-sig") as f:
        _cfg_players = json.load(f).get("Players", {})
    _cand_cfg = _cfg_players.get(args.candidate_player, {})
    anchors_requested = list(getattr(args, "anchors", None) or ["origin", "masterbot"])
    unknown = [a for a in anchors_requested if a not in ANCHOR_BLOCKS]
    if unknown:
        raise RuntimeError(f"unknown anchor(s) {unknown}; known: {sorted(ANCHOR_BLOCKS)}")
    threshold = getattr(args, "abort_winrate", 0.35)
    manifest = {
        "iteration": args.iteration,
        "candidate_weights": args.weights,
        "candidate_net_sha256": sha256(wpath),
        "origin_weights": getattr(args, "origin_weights", None),
        "candidate_player": args.candidate_player,
        "anchors_requested": anchors_requested,
        "abort_winrate": threshold,
        "eval_budget": {"TimeLimit": _cand_cfg.get("TimeLimit"),
                        "MaxTraversals": _cand_cfg.get("MaxTraversals"),
                        "UCTConstant": _cand_cfg.get("UCTConstant"),
                        "source": "read from config.txt Players.%s at eval time (A1)" % args.candidate_player},
        "effect_size_E": E_EFFECT, "regression_tol_Y": Y_REG,   # recorded metadata; non-gating
        "complete": False,
        "anchors_completed": [],
        "anchors": {}, "pools": {},
        "notes": ("v4 proof-of-life eval: origin (candidate vs the PERMANENT origin reference) is "
                  "the relative-drift anchor + the COLLAPSE/abort signal (collapse iff its general "
                  "win_rate < abort_winrate); masterbot (candidate vs MasterBot_SWF, an AB Playout "
                  "player) is the absolute-strength trend. NO REJECT/REVIEW verdict — collapse is a "
                  "coarse abort, not a powered gate. CIs: pooled iid Wilson; where the per-game "
                  "rounds CSV exists a paired per-card-set CI is REPORTED alongside (it removes "
                  "between-set variance the pooled CI ignores). Manifest is written incrementally; "
                  "'complete': false means the run died mid-eval."),
    }
    _refresh_summary(manifest, threshold)
    write_manifest(manifest, manifest_path)

    # --- C++ tournament anchors, driven by the ANCHOR_BLOCKS registry (pool -> block LIST) ---
    for anchor in anchors_requested:
        opponent_player, opp_kind = ANCHOR_OPPONENTS.get(anchor, (None, None))
        # opp_kind="origin" -> confirm the opponent loaded the origin bin; None (AB MasterBot) ->
        # no opponent NeuralNet load line exists, so skip the opponent-load confirmation entirely.
        opp_basename = origin_basename if opp_kind == "origin" else None
        per_pool = {}
        for pool in args.pools:
            blocks = ANCHOR_BLOCKS[anchor].get(pool) or []
            cells = []
            for block in blocks:
                print(f"[{anchor}/{pool}] running block {block} ...", file=sys.stderr)
                cell = run_anchor(args.dave_bin, block, args.candidate_player, weights_basename,
                                  opp_basename, opponent_player)
                cells.append(cell)
                # Record-then-raise: persist the partial pool BEFORE any provenance hard-fail.
                per_pool[pool] = aggregate_pool_cells(cells)
                head = per_pool.get(HEADLINE_POOL) or next(iter(per_pool.values()), {})
                manifest["anchors"][anchor] = {**{k: v for k, v in head.items() if k != "pools"},
                                               "pools": per_pool}
                _refresh_summary(manifest, threshold)
                write_manifest(manifest, manifest_path)   # incremental: persist after EVERY block
                # Provenance hard-fail: a COMPLETED block whose engine stderr never confirmed the
                # candidate-net load is recorded (above) but must not be trusted.
                if "win_rate" in cell and cell.get("engine_confirmed_load") is False:
                    raise RuntimeError(
                        f"provenance: block {block} completed but engine stderr never confirmed "
                        f"loading '{weights_basename}' for player {args.candidate_player} "
                        f"(engine_confirmed_load=false; result recorded in the manifest but NOT "
                        "trusted — the engine may have evaluated the wrong net)")
                # Opponent-side hard-fail (player-level): the origin anchor's opponent must have
                # loaded the pinned origin net or the comparison itself is wrong. (Only stamped
                # when opp_basename is set, i.e. NOT for the no-NeuralNet masterbot opponent.)
                if "win_rate" in cell and cell.get("engine_confirmed_parent_load") is False:
                    raise RuntimeError(
                        f"provenance: block {block} completed but engine stderr never confirmed "
                        f"loading '{opp_basename}' for the anchor opponent {opponent_player} "
                        f"(engine_confirmed_parent_load=false; result recorded in the manifest but "
                        "NOT trusted — the comparison would be against the WRONG net)")
        manifest["anchors_completed"].append(anchor)
        write_manifest(manifest, manifest_path)

    _refresh_summary(manifest, threshold)
    manifest["complete"] = True
    write_manifest(manifest, manifest_path)
    return manifest


def main():
    ap = argparse.ArgumentParser(
        description="Per-iteration RL proof-of-life eval: 2 anchors (origin/masterbot), Wilson "
                    "CIs, collapse-on-abort (no REJECT/REVIEW verdict), incremental manifest.")
    ap.add_argument("--iteration", required=True,
                    help="iteration index (int) or checkpoint label (e.g. ckpt_20260613) — "
                         "used for the manifest filename + stamp only")
    ap.add_argument("--weights", required=True, help="candidate .bin filename (in dave bin/asset/config)")
    ap.add_argument("--parent-weights", default=None,
                    help="(vestigial in v4 — accepted but unused; v4 anchors do not use a 'parent' "
                         "opponent. Use --origin-weights for the origin anchor's opponent-load check.)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--candidate-player", default=CANDIDATE_PLAYER,
                    help="config player repointed to the candidate net (group1 of each anchor block)")
    ap.add_argument("--candidate-label", default=CANDIDATE_PLAYER,
                    help="(accepted for back-compat; unused in v4 — there is no matchup_clean.js anchor)")
    ap.add_argument("--pools", nargs="+", default=["general"])
    ap.add_argument("--anchors", nargs="+", default=["origin", "masterbot"],
                    help="which C++ anchors to run (v4 PoL set: origin = collapse signal; "
                         "masterbot = absolute trend). Known: %s" % sorted(ANCHOR_BLOCKS))
    ap.add_argument("--origin-weights", default=None,
                    help="the PERMANENT origin .bin (frozen origin_bin, v221) — required when the "
                         "origin anchor runs, for its opponent-load provenance check")
    ap.add_argument("--abort-winrate", type=float, default=0.35,
                    help="collapse threshold: collapse=True iff the origin/general win_rate is "
                         "below this (default 0.35). Coarse point-estimate abort, not a gate.")
    ap.add_argument("--out", default="eval/manifests")
    # Vestigial v3 args: accepted-and-ignored so the existing PowerShell drivers (run_iteration /
    # run_checkpoint) don't crash on an unrecognized flag. The steam/matchup anchor was removed
    # with the REJECT/REVIEW verdict — these no longer do anything.
    ap.add_argument("--orig-exe", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--steam-games", type=int, default=None, help=argparse.SUPPRESS)
    ap.add_argument("--run-steam", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Contamination guards (spec §4 item 6): FORCE_DSNN / use_dsnn.txt would silently swap the net
    # under eval -- always fatal.
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - eval contamination"
    assert not os.path.exists(os.path.join(args.dave_bin, "use_dsnn.txt")), "use_dsnn.txt present - eval contamination"
    if "origin" in (args.anchors or []) and not args.origin_weights:
        raise SystemExit("--origin-weights is required when the origin anchor runs "
                         "(the origin opponent's load is provenance-checked).")

    path = os.path.join(args.out, f"eval_iter_{args.iteration}.json")
    manifest = build_manifest(args, manifest_path=path)

    print(f"manifest -> {path}")
    s = manifest.get("summary", {})
    print(f"collapse={manifest.get('collapse')} (abort_winrate={manifest.get('abort_winrate')})  "
          f"origin={s.get('origin_win_rate')} (ci {s.get('origin_wr_ci')})  "
          f"masterbot={s.get('masterbot_win_rate')} (ci {s.get('masterbot_wr_ci')})  "
          "-- collapse=True means the candidate drifted badly vs origin; abort the campaign.")


if __name__ == "__main__":
    main()
