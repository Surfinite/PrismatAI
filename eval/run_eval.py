"""Per-iteration RL eval. Sequential testing (gating only), Wilson CIs, manifest.

Anchors (one path each):
  1. iter0  : wide-untrained iter-0 weights on the IG-optional config (C++ tournament)  [regression-gate ref, A1]
  2. narrow : DSNN_Mixed35_5var (C++ tournament)                                          [trajectory yardstick]
  3. steam  : STEAMAI / PrismataAI.exe.ORIG (matchup_clean.js, --player-switch)           [trajectory yardstick, DEFERRED live]
All eval players run at the DEPLOYMENT budget (TimeLimit:7000/MaxTraversals:100000), NOT the self-play N (A1).

A4 NOTE: for the paired colour-swap pools, the card-set-level clustered_ci() is the statistically
correct interval and should be used once per-set scores are parsed; the iid wilson_ci is the
conservative fallback.

PARSE-FORMAT NOTE (validated Step 5, 2026-06-03): the C++ tournament's STDOUT only emits a
seat-symmetric *score matrix* (player x player score, plus TotalScore) and a "Games completed"
line -- it does NOT carry Wins/Loss/Draw/Games per player. The canonical per-player W/L/D/Games
table is written to the HTML results file (tests/Tournament_<name>_<date>.html, table id="statsTable").
run_cpp_tournament() therefore reads that HTML file and parse_tournament_stdout() parses its
statsTable rows. A stdout score-matrix fallback is retained for diagnostics.
"""
import argparse, hashlib, json, os, subprocess, sys, time, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wilson import win_rate, wilson_ci, decisive, decisive_gate, clustered_ci

SEQ = [128, 256, 512]


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


def run_cpp_tournament(dave_bin, block_name):
    """Run Prismata_Testing.exe (executes every run:true Benchmarks block) and return the
    per-player {wins,draws,games} for `block_name`, read from that block's HTML statsTable.
    The caller is responsible for having flipped exactly the desired block(s) to run:true."""
    before_run = time.time()
    p = subprocess.run([os.path.join(dave_bin, "Prismata_Testing.exe")],
                       cwd=dave_bin, capture_output=True, text=True, timeout=36000)
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


def run_steam(orig_exe, candidate_label, games, pool_args, think_ms=7000):
    """matchup_clean.js: RL candidate (DaveAI w/ candidate weights) vs STEAMAI/.ORIG, --player-switch.
    Returns (win_rate_p in [0,1], n). A7: parse the SEAT-INDEPENDENT per-identity win-rate.
    A8: the STEAMAI yardstick uses a FIXED games count (no sequential escalation)."""
    cmd = ["node", "c:/libraries/PrismataAI/js_engine/matchup_clean.js",
           "--games", str(games), "--parallel", "4", "--player-switch", "--think-time", str(think_ms),
           "--player", "SteamAI", "--steam-difficulty", "HardestAI",
           "--dave-exe", orig_exe] + pool_args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=72000)
    return parse_matchup_seatindep(p.stderr, candidate_label, games)


def parse_matchup_seatindep(text, candidate_label, games):
    """A7: read the '--- Win Rates (seat-independent) ---' block and return (candidate win_rate
    fraction, n). Returns (None, games) if the block is absent (e.g. no --player-switch).

    The caller MUST pass a candidate_label unique enough that it is NOT a substring of the
    opponent's identity label (the match takes the FIRST matching line and stops).

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


def sequential_gate(run_fn):
    """Escalate 128->256->512 for the GATING comparison; stop when decisive_gate.
    Final look uses full alpha. Returns (wins,draws,n,outcome).

    A8: ONLY the candidate-vs-parent promotion gate uses this escalation. The STEAMAI / narrow
    yardsticks use a fixed N + a CI (clustered_ci preferred, wilson_ci fallback)."""
    wins = draws = n = 0
    for i, target in enumerate(SEQ):
        add = target - n
        w, d, _ = run_fn(add)
        wins += w
        draws += d
        n = target
        final = (i == len(SEQ) - 1)
        if decisive_gate(wins, draws, n, final_look=final):
            return wins, draws, n, "decisive"
    return wins, draws, n, "inconclusive"


# ---------------------------------------------------------------------------
# Anchor wiring (config-block flip -> C++ tournament -> parse -> Wilson CI)
# ---------------------------------------------------------------------------

# Frozen per eval/rl_campaign.md §1. group1 of every anchor block is the candidate (RL_Eval),
# repointed to the candidate .bin by run_iteration.ps1 stage 7.
CANDIDATE_PLAYER = "RL_Eval"
E_EFFECT = 0.05   # pre-registered effect size (+5 pp) -- the smallest IG-driven gain worth AWS spend.
Y_REG    = 0.03   # regression tolerance on the GENERAL pool (no material regression vs iter-0).
HEADLINE_POOL = "forced"   # the IG-widened axis (d_rl); the dashboard renders one cell per anchor.

# Anchor C++ tournament blocks (must exist run:false in config.txt; group1=RL_Eval candidate):
#   iter0  -> vs RL_Eval_iter0 (wide-untrained)  : GATES (A1) -- d_rl=forced, d_reg=general.
#   narrow -> vs DSNN_Mixed35_5var               : trajectory yardstick only.
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


def run_anchor_block(dave_bin, block_name, candidate_player=CANDIDATE_PLAYER):
    """Flip ONE anchor block run:true, run Prismata_Testing.exe, parse the candidate's W/L/D from its
    HTML statsTable, flip back (in a finally). Returns a FLAT anchor dict
    {block,candidate,wins,draws,games,win_rate,ci:[lo,hi]} the dashboard can render directly, or an
    {block,error,...} dict if the candidate row / W/L/D could not be parsed (degraded stdout fallback)."""
    set_block_run(dave_bin, block_name, True)
    try:
        results = run_cpp_tournament(dave_bin, block_name)
    finally:
        set_block_run(dave_bin, block_name, False)
    cand = results.get(candidate_player)
    if not cand or cand.get("wins") is None:
        return {"block": block_name,
                "error": f"no W/L/D for candidate '{candidate_player}' (degraded score-matrix fallback?)",
                "raw_players": sorted(results)}
    wins, draws, games = cand["wins"], cand["draws"], cand["games"]
    p = win_rate(wins, draws, games)
    lo, hi = wilson_ci(p, games)
    return {"block": block_name, "candidate": candidate_player,
            "wins": wins, "draws": draws, "games": games, "win_rate": p, "ci": [lo, hi]}


def build_manifest(args, steam_available, run_anchor=run_anchor_block, steam_fn=None):
    """Assemble the eval manifest dict. Factored out of main() (no I/O, injectable runners) so the
    orchestration + decision logic is unit-testable without the C++ engine. run_anchor(dave_bin,
    block, player)->anchor-dict; steam_fn(orig_exe,label,games,pool_args,think_ms)->(p,n)."""
    if steam_fn is None:
        steam_fn = run_steam
    wpath = os.path.join(args.dave_bin, "asset/config", args.weights)
    manifest = {
        "iteration": args.iteration,
        "candidate_weights": args.weights,
        "candidate_net_sha256": sha256(wpath),
        "parent_weights": args.parent_weights,
        "candidate_player": args.candidate_player,
        "eval_budget": "TimeLimit:7000/MaxTraversals:100000 (deployment-representative, A1)",
        "effect_size_E": E_EFFECT, "regression_tol_Y": Y_REG,
        "anchors": {}, "pools": {},
        "notes": ("iter0 anchor GATES (A1: d_rl=forced pool, d_reg=general pool); narrow + steam are "
                  "trajectory yardsticks only. CIs are iid Wilson (A4 clustered_ci pending per-card-set "
                  "score parsing). The candidate-vs-parent promotion gate (sequential_gate, A3) is a "
                  "SEPARATE mechanism with no config block here. The decision is a HUMAN call."),
    }

    # --- iter0 + narrow anchors: one C++ tournament block per pool ---
    for anchor in ("iter0", "narrow"):
        per_pool = {}
        for pool in args.pools:
            block = ANCHOR_BLOCKS[anchor].get(pool)
            if not block:
                continue
            print(f"[{anchor}/{pool}] running block {block} ...", file=sys.stderr)
            per_pool[pool] = run_anchor(args.dave_bin, block, args.candidate_player)
        # Headline cell = the decision-relevant pool (forced = IG-widened axis); full breakdown under 'pools'.
        head = per_pool.get(HEADLINE_POOL) or next(iter(per_pool.values()), {})
        manifest["anchors"][anchor] = {**{k: v for k, v in head.items() if k != "pools"}, "pools": per_pool}

    # --- steam anchor: matchup_clean.js fixed-N (A8), A7 seat-independent, GENERAL pool only ---
    # (forced-pool STEAMAI is unwired: matchup_clean.js ForcedCards support is unverified.)
    if steam_available:
        print(f"[steam] matchup_clean.js vs STEAMAI ({args.steam_games} games) ...", file=sys.stderr)
        p, n = steam_fn(args.orig_exe, args.candidate_label, args.steam_games, [], 7000)
        if p is None:
            manifest["anchors"]["steam"] = {
                "error": "no seat-independent result parsed (check --player-switch / candidate label)",
                "games": n}
        else:
            lo, hi = wilson_ci(p, n)
            manifest["anchors"]["steam"] = {"win_rate": p, "games": n, "ci": [lo, hi],
                                            "pool": "general", "note": "A7 seat-independent, A8 fixed-N"}
    else:
        manifest["anchors"]["steam"] = {
            "status": "DEFERRED -- PrismataAI.exe.ORIG absent (A8 STEAMAI trajectory yardstick)"}

    # --- §3 decision inputs: d_rl from iter0/forced, d_reg from iter0/general (A1) ---
    iter0_pools = manifest["anchors"].get("iter0", {}).get("pools", {})

    def _cell(pool):
        c = iter0_pools.get(pool)
        return c if isinstance(c, dict) and "win_rate" in c else None

    forced, general = _cell("forced"), _cell("general")
    go = {"E": E_EFFECT, "Y": Y_REG,
          "rule": "GO iff CI_lower(d_rl) > 0 AND d_rl >= E AND d_reg(general) >= -Y"}
    if forced:
        go["d_rl_forced"] = forced["win_rate"] - 0.5
        go["d_rl_ci"] = forced["ci"]
        go["ci_lower_gt_half"] = forced["ci"][0] > 0.5
        go["d_rl_ge_E"] = (forced["win_rate"] - 0.5) >= E_EFFECT
    if general:
        go["d_reg_general"] = general["win_rate"] - 0.5
        go["d_reg_ge_negY"] = (general["win_rate"] - 0.5) >= -Y_REG
    go["computable"] = all(k in go for k in ("ci_lower_gt_half", "d_rl_ge_E", "d_reg_ge_negY"))
    go["GO_suggested"] = bool(go["computable"] and go.get("ci_lower_gt_half")
                              and go.get("d_rl_ge_E") and go.get("d_reg_ge_negY"))

    manifest["pools"] = {
        "forced":  {"role": "d_rl (IG-widened axis vs iter0)",  **(forced or {"status": "unavailable"})},
        "general": {"role": "d_reg (regression guard vs iter0)", **(general or {"status": "unavailable"})},
    }
    manifest["go_signal"] = go
    manifest["decision"] = "(human call)"   # faithful to the spec: the driver computes inputs, never promotes.
    return manifest


def main():
    ap = argparse.ArgumentParser(
        description="Per-iteration RL eval: 3 anchors (iter0/narrow/steam), Wilson CIs, GO inputs, manifest.")
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--weights", required=True, help="candidate .bin filename (in dave bin/asset/config)")
    ap.add_argument("--parent-weights", default=None,
                    help="current promoted .bin (promotion-gate reference; that gate is a separate mechanism)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--orig-exe", required=True,
                    help="PrismataAI.exe.ORIG (STEAMAI 2016 baseline); steam anchor is DEFERRED if absent")
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
    # eval -- always fatal. A missing .ORIG only DEFERS the steam yardstick; it does NOT block the gating
    # iter0/narrow anchors (which need no .ORIG), so it is a soft skip, not an assert.
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - eval contamination"
    assert not os.path.exists(os.path.join(args.dave_bin, "use_dsnn.txt")), "use_dsnn.txt present - eval contamination"
    steam_available = os.path.exists(args.orig_exe)
    if not steam_available:
        print(f"WARNING: STEAMAI baseline absent ({args.orig_exe}) -- steam anchor DEFERRED", file=sys.stderr)

    manifest = build_manifest(args, steam_available)

    path = os.path.join(args.out, f"eval_iter_{args.iteration}.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest -> {path}")
    go = manifest["go_signal"]
    print(f"GO_suggested={go.get('GO_suggested')} (computable={go.get('computable')})  "
          f"d_rl={go.get('d_rl_forced')}  d_reg={go.get('d_reg_general')}  -- DECISION is a human call.")


if __name__ == "__main__":
    main()
