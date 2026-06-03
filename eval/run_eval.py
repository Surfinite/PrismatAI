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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iteration", type=int, required=True)
    ap.add_argument("--weights", required=True, help="candidate .bin filename (in dave bin/asset/config)")
    ap.add_argument("--parent-weights", default=None, help="current promoted .bin (primary gating comparison)")
    ap.add_argument("--dave-bin", required=True)
    ap.add_argument("--orig-exe", required=True)
    ap.add_argument("--steam-games", type=int, default=200, help="A8: fixed modest N for the STEAMAI yardstick")
    ap.add_argument("--pools", nargs="+", default=["forced", "general"])
    ap.add_argument("--out", default="eval/manifests")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    wpath = os.path.join(args.dave_bin, "asset/config", args.weights)

    # Contamination checks (spec 5).
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - eval contamination"
    assert not os.path.exists(os.path.join(args.dave_bin, "use_dsnn.txt")), "use_dsnn.txt present"
    assert os.path.exists(args.orig_exe), "STEAMAI .ORIG missing - would diff against the DSNN swap-in"

    manifest = {
        "iteration": args.iteration,
        "candidate_weights": args.weights,
        "candidate_net_sha256": sha256(wpath),
        "parent_weights": args.parent_weights,
        "eval_budget": "TimeLimit:7000/MaxTraversals:100000 (deployment-representative, A1)",
        "anchors": {}, "pools": {},
        # NOTE (A1): d_reg (the regression gate) must be computed from RL_Eval_iter0_general
        # (net_k vs pre-RL net, SAME config + SAME budget), NOT from the narrow DSNN_Mixed35_5var
        # baseline (different config @100k) - else a pure budget gap trips d_reg<-Y and blocks a GO.
        # Narrow + STEAMAI are trajectory yardsticks; do NOT gate on them.
        # The caller writes the per-anchor C++ tournament blocks (paired group1/group2, Seed, forced/general
        # pool) into config.txt before invoking, then maps run_cpp_tournament results into
        # manifest['anchors'][name]. STEAMAI anchor (A8) uses a FIXED steam-games N + clustered/Wilson CI
        # (NOT sequential). Only the candidate-vs-parent GATING comparison uses sequential_gate().
    }

    path = os.path.join(args.out, f"eval_iter_{args.iteration}.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"manifest -> {path}")


if __name__ == "__main__":
    main()
