"""Per-iteration RL eval. Wilson CIs, REJECT/REVIEW/INCOMPLETE verdict, incremental manifest.

Anchors (one path each):
  1. iter0  : candidate vs the PARENT promoted net (the RL_Eval_iter0 player is repointed to the
              current parent, v221) on the IG-optional config (C++ tournament). Its GENERAL
              (unforced-sets) pool is the ONLY automated verdict input; its forced pool informs
              the human IG judgment but does not gate.
  2. narrow : candidate vs RL_Narrow (same v221 net + budget + c, NON-IG HardIterator_5var_Root —
              isolates the iterator variable; C++ tournament)                     [non-gating yardstick]
  3. steam  : candidate (DaveAI + injected RL_Eval block + --candidate-weights) vs the genuine
              2016 MasterBot at its permanent home c:/libraries/prismata_baselines/masterbot2016/
              (matchup_clean.js, --player-switch)                                 [non-gating yardstick]
All eval players run at the DEPLOYMENT budget (TimeLimit:7000/MaxTraversals:100000), NOT the self-play N (A1).

VERDICT (2026-06-10, replaces the old GO gate): the old rule (d_rl >= +5pp AND forced
ci_lower > 0.5) was statistically incoherent at 128 games — an observed +5pp needed 58.7% to
fire, so P(GO | true +5pp) ~ 13%. "Prove improvement" is replaced by "rule out harm" + human
judgment:
  REJECT     iff the general-pool anchor completed AND its 95% Wilson ci_upper < 0.5
             (the candidate is statistically proven worse than the parent);
  REVIEW     iff it completed and ci_upper >= 0.5 (everything else is a human call);
  INCOMPLETE iff the general anchor is missing/errored (can't certify not-worse).
d_rl, d_reg, all WRs and CIs remain recorded as INFORMATION (d_reg now carries a CI); nothing
auto-promotes.

INCREMENTAL MANIFEST: the manifest is (re)written atomically (temp file + os.replace) after
EVERY completed pool/anchor, carrying "complete": false and "anchors_completed": [...] until
the final write — a killed run can no longer erase hours of tournament results (Jun-8 failure).

PROVENANCE (active): before any block flips on, Players.<candidate>.WeightsFile in the dave
config.txt must equal basename(--weights) (hard abort otherwise). Each C++ anchor's stderr is
captured and must contain the engine's "AIParameters: created per-player NeuralNet from
<...candidate.bin>" load line; the result is stamped "engine_confirmed_load" per anchor and a
completed-but-unconfirmed anchor hard-fails (after being recorded for the post-mortem).

STATS NOTE: CIs are iid Wilson only (eval/wilson.py). Per-set / colour-swap-paired analysis
would require per-card-set scores the tournament HTML does not emit.

PARSE-FORMAT NOTE (validated Step 5, 2026-06-03): the C++ tournament's STDOUT only emits a
seat-symmetric *score matrix* (player x player score, plus TotalScore) and a "Games completed"
line -- it does NOT carry Wins/Loss/Draw/Games per player. The canonical per-player W/L/D/Games
table is written to the HTML results file (tests/Tournament_<name>_<date>.html, table id="statsTable").
run_cpp_tournament() therefore reads that HTML file and parse_tournament_stdout() parses its
statsTable rows. A stdout score-matrix fallback is retained for diagnostics.
"""
import argparse, hashlib, json, os, subprocess, sys, time, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wilson import win_rate, wilson_ci


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


def run_cpp_tournament(dave_bin, block_name, stderr_out=None):
    """Run Prismata_Testing.exe (executes every run:true Benchmarks block) and return the
    per-player {wins,draws,games} for `block_name`, read from that block's HTML statsTable.
    The caller is responsible for having flipped exactly the desired block(s) to run:true.

    stderr_out: optional list — receives the subprocess's full stderr text (the engine prints
    its per-player NeuralNet load confirmations there; see engine_confirmed_load). The HTML/
    stdout parse path is unchanged."""
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


# Steam anchor binaries (F-08 rewiring, 2026-06-11):
#   white = the RL candidate: DaveAI (dave-master engine_v1 Steam-protocol exe) with the
#           matchup runner's injected RL_Eval player block (5var+IGsubset iterators, c=0.3,
#           WeightsFile from --candidate-weights);
#   black = the genuine 2016 MasterBot at its PERMANENT HOME (owner directive) — outside both
#           repos and the Steam dir, so the use_dsnn.txt contamination guard (which checks the
#           exe's own directory) passes without modification. sha256
#           0A70B198342B998650D98CF2F1CF74E9C478D50F4E9918FB49E09286B64A41FC, 721,920 bytes.
DAVE_MATCHUP_EXE = "c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe"
MASTERBOT2016_EXE = "c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe"


def run_steam(orig_exe, candidate_label, games, pool_args, think_ms=7000,
              dave_exe=DAVE_MATCHUP_EXE):
    """matchup_clean.js: RL candidate (white: DaveAI + injected RL_Eval block; candidate
    weights threaded via pool_args ["--candidate-weights", <bin basename>]) vs the 2016
    MasterBot (black: SteamAI/HardestAI on orig_exe via --steam-exe-b), --player-switch.
    Returns (win_rate_p in [0,1], n). A7: parse the SEAT-INDEPENDENT per-identity win-rate.
    A8: the STEAMAI yardstick uses a FIXED games count (no sequential escalation).

    Verified emitted candidate label (matchup_clean.js labelWith, 2026-06-11): the white
    player normalizes to 'DAVEAI' and the difficulty keeps its exact argv case, so the
    seat-independent line is:  [Parallel] Player A [DAVEAI[RL_Eval]]: 53.9%
    -> candidate_label 'RL_Eval' (exact case) substring-matches it and nothing else."""
    cmd = ["node", "c:/libraries/PrismataAI/js_engine/matchup_clean.js",
           "--games", str(games), "--parallel", "4", "--player-switch", "--think-time", str(think_ms),
           "--player-white", "DaveAI", "--steam-difficulty-white", "RL_Eval",
           "--player-black", "SteamAI", "--steam-difficulty-black", "HardestAI",
           "--dave-exe", dave_exe,
           "--steam-exe-b", orig_exe] + pool_args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=72000)
    return parse_matchup_seatindep(p.stderr, candidate_label, games)


def parse_matchup_seatindep(text, candidate_label, games):
    """A7: read the '--- Win Rates (seat-independent) ---' block and return (candidate win_rate
    fraction, n). Returns (None, games) if the block is absent (e.g. no --player-switch) or if
    no line in the block carries the candidate_label (e.g. the pre-fix SteamAI-both-seats
    mis-wiring, where both identity labels were STEAMAI[HardestAI]).

    Verified line format (matchup_clean.js, both [Pair] and [Parallel] paths, 2026-06-11):
        [Parallel] Player A [DAVEAI[RL_Eval]]: 53.9%
        [Parallel] Player B [STEAMAI[HardestAI]]: 46.1%
    Matching is exact-case SUBSTRING against the captured label ('Player A [DAVEAI[RL_Eval]]'),
    so candidate_label='RL_Eval' must match the injected difficulty's case exactly. The caller
    MUST pass a candidate_label unique enough that it is NOT a substring of the opponent's
    identity label (the match takes the FIRST matching line and stops).

    NOTE: deliberately ignores the '[Parallel] White:/Black:/Draws:' seat tally -- for a switched
    candidate the seat tally is NOT the candidate's win rate (A7)."""
    p = None
    n = games
    block = re.search(r"Win Rates \(seat-independent\)(.*?)(?:={5,}|\Z)", text, re.S)
    scope = block.group(1) if block else text
    for m in re.finditer(r"^\s*\[(?:Pair|Parallel)\]\s+(.+?):\s+([\d.]+)%\s*$", scope, re.M):
        label, rate = m.group(1).strip(), float(m.group(2))
        if candidate_label and candidate_label in label:
            p = rate / 100.0
            break
    mg = re.search(r"\[(?:Pair|Parallel)\]\s+Games:\s+(\d+)", text)
    if mg:
        n = int(mg.group(1))
    return (p, n)


# ---------------------------------------------------------------------------
# Provenance + manifest persistence
# ---------------------------------------------------------------------------

# AIParameters.cpp prints this to STDERR when it constructs a per-player NeuralNet:
#   "AIParameters: created per-player NeuralNet from asset/config/<weights file>"
ENGINE_LOAD_MARKER = "created per-player NeuralNet from"


def engine_confirmed_load(stderr_text, weights_basename):
    """True iff the engine's stderr confirms it actually constructed a per-player NeuralNet
    from the candidate weights file (load marker AND the candidate basename on the SAME line —
    the basename elsewhere in stderr noise is not a confirmation)."""
    for line in (stderr_text or "").splitlines():
        if ENGINE_LOAD_MARKER in line and weights_basename in line:
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
# since 2026-06-10 nothing gates on them — see the module docstring's VERDICT section.
E_EFFECT = 0.05   # (info) +5 pp -- the smallest IG-driven gain judged worth AWS spend.
Y_REG    = 0.03   # (info) regression tolerance once used by the retired d_reg gate.
HEADLINE_POOL = "forced"   # the IG-widened axis (d_rl info); the dashboard renders one cell per anchor.
VERDICT_RULE = ("REJECT iff iter0/general (candidate vs parent, unforced sets) completed AND "
                "Wilson95 ci_upper < 0.5; REVIEW iff completed and ci_upper >= 0.5; INCOMPLETE "
                "iff that anchor is missing/errored. All deltas are information only — "
                "promotion is a HUMAN call.")

# Anchor C++ tournament blocks (must exist run:false in config.txt; group1=RL_Eval candidate):
#   iter0  -> vs RL_Eval_iter0 (repointed to the PARENT promoted net, v221):
#             general pool = the verdict input; forced pool = d_rl information.
#   narrow -> vs RL_Narrow (iterator-only variable; dave@09c5436) : non-gating trajectory yardstick.
ANCHOR_BLOCKS = {
    "iter0":  {"forced": "RL_Eval_iter0_forced",  "general": "RL_Eval_iter0_general"},
    "narrow": {"forced": "RL_Eval_narrow_forced", "general": "RL_Eval_narrow_general"},
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


def run_anchor_block(dave_bin, block_name, candidate_player=CANDIDATE_PLAYER, weights_basename=None):
    """Flip ONE anchor block run:true, run Prismata_Testing.exe, parse the candidate's W/L/D from its
    HTML statsTable, flip back (in a finally). Returns a FLAT anchor dict
    {block,candidate,wins,draws,games,win_rate,ci:[lo,hi]} the dashboard can render directly, or an
    {block,error,...} dict if the candidate row / W/L/D could not be parsed (degraded stdout fallback).

    When weights_basename is given, the engine's stderr is checked for the per-player NeuralNet
    load confirmation and the result is stamped "engine_confirmed_load" (active provenance;
    build_manifest hard-fails a completed-but-unconfirmed anchor)."""
    set_block_run(dave_bin, block_name, True)
    stderr_sink = []
    try:
        results = run_cpp_tournament(dave_bin, block_name, stderr_out=stderr_sink)
    finally:
        set_block_run(dave_bin, block_name, False)
    confirmed = (engine_confirmed_load("".join(stderr_sink), weights_basename)
                 if weights_basename else None)
    cand = results.get(candidate_player)
    if not cand or cand.get("wins") is None:
        out = {"block": block_name,
               "error": f"no W/L/D for candidate '{candidate_player}' (degraded score-matrix fallback?)",
               "raw_players": sorted(results)}
        if confirmed is not None:
            out["engine_confirmed_load"] = confirmed
        return out
    wins, draws, games = cand["wins"], cand["draws"], cand["games"]
    p = win_rate(wins, draws, games)
    lo, hi = wilson_ci(p, games)
    out = {"block": block_name, "candidate": candidate_player,
           "wins": wins, "draws": draws, "games": games, "win_rate": p, "ci": [lo, hi]}
    if confirmed is not None:
        out["engine_confirmed_load"] = confirmed
    return out


def compute_verdict(general_cell):
    """REJECT / REVIEW / INCOMPLETE non-inferiority verdict (2026-06-10; replaces the old GO
    boolean). general_cell = the iter0/general anchor dict (candidate vs parent, unforced sets):
      REJECT     iff it completed AND its 95% Wilson ci_upper < 0.5 (proven worse than parent);
      REVIEW     iff it completed and ci_upper >= 0.5 (human call on the recorded numbers);
      INCOMPLETE iff it is missing/errored (no automated verdict possible)."""
    if not (isinstance(general_cell, dict) and "win_rate" in general_cell and general_cell.get("ci")):
        return "INCOMPLETE"
    return "REJECT" if general_cell["ci"][1] < 0.5 else "REVIEW"


def _refresh_verdict(manifest):
    """Recompute verdict + information-only deltas from whatever anchors are recorded so far.
    Called before every incremental write so even a partial (killed-run) manifest carries a
    self-consistent verdict."""
    iter0_pools = manifest["anchors"].get("iter0", {}).get("pools", {})

    def _cell(pool):
        c = iter0_pools.get(pool)
        return c if isinstance(c, dict) and "win_rate" in c else None

    forced, general = _cell("forced"), _cell("general")
    manifest["verdict"] = compute_verdict(general)
    info = {"E": E_EFFECT, "Y": Y_REG,   # recorded metadata only — nothing gates on them
            "rule": VERDICT_RULE}
    if forced:   # information only (informs the human IG judgment; does NOT gate)
        info["d_rl_forced"] = forced["win_rate"] - 0.5
        info["forced_wr_ci"] = forced["ci"]       # Wilson CI on the forced WIN RATE (not the delta)
    if general:
        info["d_reg_general"] = general["win_rate"] - 0.5
        info["general_wr_ci"] = general["ci"]     # Wilson CI on the general WIN RATE (not the delta)
        info["general_ci_upper"] = general["ci"][1]
    manifest["verdict_inputs"] = info
    manifest["pools"] = {
        "forced":  {"role": "d_rl info (IG-widened axis vs parent; non-gating)",
                    **(forced or {"status": "unavailable"})},
        "general": {"role": "verdict pool (REJECT iff ci_upper<0.5) + d_reg info",
                    **(general or {"status": "unavailable"})},
    }
    manifest["decision"] = "(human call)"   # the driver computes inputs, never promotes.


def build_manifest(args, steam_available, run_anchor=run_anchor_block, steam_fn=None,
                   manifest_path=None):
    """Assemble the eval manifest dict, writing it to manifest_path INCREMENTALLY (atomic temp +
    os.replace) after every completed pool/anchor — a crash/kill leaves a readable partial
    manifest ("complete": false, "anchors_completed": [...]) instead of nothing. Injectable
    runners keep the orchestration + verdict logic unit-testable without the C++ engine:
    run_anchor(dave_bin, block, player, weights_basename) -> anchor-dict;
    steam_fn(orig_exe, label, games, pool_args, think_ms, dave_exe) -> (p, n)."""
    if steam_fn is None:
        steam_fn = run_steam
    weights_basename = os.path.basename(args.weights)
    # Active provenance pre-flight: the config must already point the candidate player at the
    # candidate net BEFORE any tournament flips on.
    verify_config_weights(args.dave_bin, args.candidate_player, weights_basename)
    wpath = os.path.join(args.dave_bin, "asset/config", args.weights)
    manifest = {
        "iteration": args.iteration,
        "candidate_weights": args.weights,
        "candidate_net_sha256": sha256(wpath),
        "parent_weights": args.parent_weights,
        "candidate_player": args.candidate_player,
        "eval_budget": "TimeLimit:7000/MaxTraversals:100000 (deployment-representative, A1)",
        "effect_size_E": E_EFFECT, "regression_tol_Y": Y_REG,   # recorded metadata; non-gating
        "complete": False,
        "anchors_completed": [],
        "anchors": {}, "pools": {},
        "notes": ("Verdict = rule-out-harm on iter0/general (candidate vs PARENT promoted net, "
                  "unforced sets): " + VERDICT_RULE + " narrow + steam are non-gating trajectory "
                  "yardsticks. CIs are iid Wilson (the tournament HTML emits no per-card-set "
                  "scores, so no paired/sequential statistics exist). Manifest is written "
                  "incrementally; 'complete': false means the run died mid-eval."),
    }
    _refresh_verdict(manifest)
    write_manifest(manifest, manifest_path)

    # --- C++ tournament anchors (one block per pool), driven by the ANCHOR_BLOCKS registry ---
    for anchor in ANCHOR_BLOCKS:
        per_pool = {}
        for pool in args.pools:
            block = ANCHOR_BLOCKS[anchor].get(pool)
            if not block:
                continue
            print(f"[{anchor}/{pool}] running block {block} ...", file=sys.stderr)
            cell = run_anchor(args.dave_bin, block, args.candidate_player, weights_basename)
            per_pool[pool] = cell
            # Headline cell = forced (the IG-widened d_rl axis); full breakdown under 'pools'.
            head = per_pool.get(HEADLINE_POOL) or next(iter(per_pool.values()), {})
            manifest["anchors"][anchor] = {**{k: v for k, v in head.items() if k != "pools"},
                                           "pools": per_pool}
            _refresh_verdict(manifest)
            write_manifest(manifest, manifest_path)   # incremental: persist after EVERY pool
            # Provenance hard-fail: a COMPLETED anchor whose engine stderr never confirmed the
            # candidate-net load is recorded (above) but must not be trusted.
            if "win_rate" in cell and cell.get("engine_confirmed_load") is False:
                raise RuntimeError(
                    f"provenance: block {block} completed but engine stderr never confirmed "
                    f"loading '{weights_basename}' for {args.candidate_player} "
                    f"(engine_confirmed_load=false; result recorded in the manifest but NOT "
                    "trusted — the engine may have evaluated the wrong net)")
        manifest["anchors_completed"].append(anchor)
        write_manifest(manifest, manifest_path)

    # --- steam anchor: matchup_clean.js fixed-N (A8), A7 seat-independent, GENERAL pool only ---
    # Non-gating yardstick. (forced-pool STEAMAI is unwired: matchup_clean.js ForcedCards
    # support is unverified.) Earlier anchors are already on disk, so a steam crash can no
    # longer erase them.
    if steam_available:
        print(f"[steam] matchup_clean.js candidate(DaveAI/RL_Eval) vs 2016 MasterBot "
              f"({args.steam_games} games) ...", file=sys.stderr)
        p, n = steam_fn(args.orig_exe, args.candidate_label, args.steam_games,
                        ["--candidate-weights", weights_basename], 7000,
                        os.path.join(args.dave_bin, "PrismataAI.exe"))
        if p is None:
            manifest["anchors"]["steam"] = {
                "error": "no seat-independent result parsed (check --player-switch / candidate label)",
                "games": n}
        else:
            lo, hi = wilson_ci(p, n)
            manifest["anchors"]["steam"] = {"win_rate": p, "games": n, "ci": [lo, hi],
                                            "pool": "general",
                                            "note": "A7 seat-independent, A8 fixed-N, non-gating"}
        manifest["anchors_completed"].append("steam")
    else:
        manifest["anchors"]["steam"] = {
            "status": "DEFERRED -- 2016 MasterBot baseline absent "
                      "(expected at c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe; "
                      "A8 STEAMAI trajectory yardstick)"}

    _refresh_verdict(manifest)
    manifest["complete"] = True
    write_manifest(manifest, manifest_path)
    return manifest


def main():
    ap = argparse.ArgumentParser(
        description="Per-iteration RL eval: 3 anchors (iter0/narrow/steam), Wilson CIs, "
                    "REJECT/REVIEW/INCOMPLETE verdict, incremental manifest.")
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--weights", required=True, help="candidate .bin filename (in dave bin/asset/config)")
    ap.add_argument("--parent-weights", default=None,
                    help="current promoted .bin (promotion-gate reference; that gate is a separate mechanism)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--orig-exe", default=MASTERBOT2016_EXE,
                    help="genuine 2016 MasterBot binary (STEAMAI baseline) at its permanent home; "
                         "steam anchor is DEFERRED if absent")
    ap.add_argument("--steam-games", type=int, default=200, help="A8: fixed modest N for the STEAMAI yardstick")
    ap.add_argument("--candidate-player", default=CANDIDATE_PLAYER,
                    help="config player repointed to the candidate net (group1 of each anchor block)")
    ap.add_argument("--candidate-label", default=CANDIDATE_PLAYER,
                    help="candidate identity label as it appears in matchup_clean.js output (A7)")
    ap.add_argument("--pools", nargs="+", default=["forced", "general"])
    ap.add_argument("--out", default="eval/manifests")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Contamination guards (spec §4 item 6): FORCE_DSNN / use_dsnn.txt would silently swap the net under
    # eval -- always fatal. A missing .ORIG only DEFERS the steam yardstick; it does NOT block the C++
    # iter0 (verdict) / narrow anchors (which need no .ORIG), so it is a soft skip, not an assert.
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - eval contamination"
    assert not os.path.exists(os.path.join(args.dave_bin, "use_dsnn.txt")), "use_dsnn.txt present - eval contamination"
    steam_available = os.path.exists(args.orig_exe)
    if not steam_available:
        print(f"WARNING: STEAMAI baseline absent ({args.orig_exe}) -- steam anchor DEFERRED", file=sys.stderr)

    path = os.path.join(args.out, f"eval_iter_{args.iteration}.json")
    manifest = build_manifest(args, steam_available, manifest_path=path)

    print(f"manifest -> {path}")
    vi = manifest.get("verdict_inputs", {})
    print(f"verdict={manifest.get('verdict')}  d_reg={vi.get('d_reg_general')} "
          f"(general wr ci {vi.get('general_wr_ci')})  d_rl={vi.get('d_rl_forced')} (info only)  "
          "-- REVIEW means the promotion DECISION is a human call.")


if __name__ == "__main__":
    main()
