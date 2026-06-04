"""O7 tactical regression suite for the RL self-play DSNN.

PURPOSE
-------
Curated tactical positions where the RIGHT move is known (or where the action space
*looks* forced and we want to keep an eye on it). Each case is replayed through dave's
PrismataAI.exe responder via js_engine/query_move.js (UCT + NeuralNet eval, the real
deploy path), and we assert a tactical property of the returned move -- specifically
whether the Infusion Grid (engine codename "Hotel") USE_ABILITY click fires.

Two buckets:
  * "known_move"   -- run the case, classify fires_hotel(resp), compare to expect.fires_hotel,
                      print PASS/FAIL.
  * "looks_forced" -- NOT run as a pass/fail gate; appended to eval/backlog_action_space.md
                      as a watch-list of positions where the iterator may be pinning the move
                      (relevant once Task 12 wires the IG-optional iterator).

REGRESSION SEMANTICS
--------------------
Exit nonzero ONLY if a case that PASSED in eval/tactical_baseline.json now FAILS (a true
regression). If the baseline file is absent, the current run IS the baseline -> exit 0
(and we offer to write it via --write-baseline). New cases not in the baseline never gate.

HOTEL CLICK SHAPE -- NEEDS CONFIRMATION ON A REAL IG STATE (DEFERRED)
--------------------------------------------------------------------
The dave-line responder's GetClickString (AITools.cpp:521) emits USE_ABILITY clicks as
    {"type":"inst clicked"|"inst shift clicked", "args": <Card.toJSONString()>}
where args carries "cardName" = the card's INTERNAL/engine name (e.g. "Hotel" for the
Infusion Grid) but NO instance id. So fires_hotel() detects the IG ability by
type in {"inst clicked","inst shift clicked"} AND args.cardName == "Hotel".

NOTE: the originating task spec described a {_type,_id} wire shape with _id matching a
hotel_inst_id; this responder does NOT emit instance ids on its clicks, so we match by
card name instead and keep hotel_inst_id in the schema for forward-compat. The EXACT
Hotel ability click shape must still be CONFIRMED on a real Infusion-Grid decision
(no such curated case exists yet -- real cases come from the user's own DSNN games and
only become meaningful for IG-SKIP after Task 12). Until then this suite validates the
MECHANISM plus the always-fire baseline. If a real IG case shows a different shape,
update HOTEL_NAME / fires_hotel() accordingly.

CASE FORMAT (eval/tactical_cases/*.json)
----------------------------------------
{
  "name": str,
  "bucket": "known_move" | "looks_forced",
  "request": { "mergedDeck": [...], "gameState": {...}, "aiParameters": {...} },  # F6 CurrentInfo
  "expect": { "fires_hotel": true|false } | null,
  "hotel_inst_id": int | null,   # forward-compat; unused by name-based detection
  "note": str
}
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CASES_DIR = os.path.join(HERE, "tactical_cases")
BASELINE_PATH = os.path.join(HERE, "tactical_baseline.json")
BACKLOG_PATH = os.path.join(HERE, "backlog_action_space.md")
QUERY_MOVE = os.path.join(REPO, "js_engine", "query_move.js")

# Infusion Grid engine codename (see cardLibrary.jso: "Hotel"). The responder's click
# args.cardName uses this internal name. CONFIRM on a real IG state (see module docstring).
HOTEL_NAME = "Hotel"


def fires_hotel(resp, hotel_inst_id=None):
    """True iff the returned move contains an Infusion Grid ("Hotel") USE_ABILITY click.

    Matches the dave-line responder click shape (AITools.cpp GetClickString):
        {"type": "inst clicked" | "inst shift clicked", "args": {"cardName": "Hotel", ...}}
    The responder does not emit per-click instance ids, so hotel_inst_id is accepted for
    forward-compat but detection is by cardName. NEEDS CONFIRMATION on a real IG case.
    """
    clicks = (resp or {}).get("aiclicks") or []
    for c in clicks:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type", "")
        if ctype not in ("inst clicked", "inst shift clicked"):
            continue
        args = c.get("args")
        if isinstance(args, dict) and args.get("cardName") == HOTEL_NAME:
            return True
    return False


def load_cases():
    cases = []
    if not os.path.isdir(CASES_DIR):
        return cases
    for fn in sorted(os.listdir(CASES_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(CASES_DIR, fn)
        with open(path, encoding="utf-8") as f:
            case = json.load(f)
        case["_file"] = fn
        cases.append(case)
    return cases


def query(case, player, weights, dave_exe, time_limit, timeout, root_iter, move_iter):
    """Write the case request to a temp file, shell out to query_move.js, return parsed response."""
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="tactical_req_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(case["request"], f)
        cmd = [
            "node", QUERY_MOVE,
            "--request", tmp,
            "--player", player,
            "--weights", weights,
            "--dave-exe", dave_exe,
            "--root-iterator", root_iter,
            "--move-iterator", move_iter,
            "--time-limit", str(time_limit),
            "--timeout", str(timeout),
        ]
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                           timeout=timeout / 1000.0 + 30)
        if p.returncode != 0:
            raise RuntimeError(f"query_move.js exited {p.returncode}: {p.stderr.strip()[-800:]}")
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"query_move.js stdout not JSON: {e}\n{p.stdout[-800:]}")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def write_backlog(forced_cases):
    """Emit the looks_forced watch-list to eval/backlog_action_space.md (overwrites)."""
    lines = [
        "# Action-Space Backlog (looks_forced tactical cases)",
        "",
        "Auto-generated by `eval/tactical_suite.py`. These are positions where the move",
        "*looks* forced by the iterator (not a pass/fail gate). They become meaningful for",
        "Infusion-Grid optionality once Task 12 wires the IG-optional iterator.",
        "",
    ]
    if not forced_cases:
        lines.append("_(none)_")
    for c in forced_cases:
        lines.append(f"- **{c.get('name', c.get('_file', '?'))}** "
                     f"({c.get('_file', '?')}): {c.get('note', '').strip()}")
    with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="O7 tactical regression suite (Infusion Grid / 'Hotel' firing).")
    ap.add_argument("--player", default="RL_Eval", help="injected player name (default: RL_Eval)")
    ap.add_argument("--weights", default="neural_weights_mixed_35prop.bin",
                    help="candidate weights file (resolved by the responder under asset/config/)")
    ap.add_argument("--dave-exe",
                    default=r"c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe",
                    help="path to dave's PrismataAI.exe responder")
    ap.add_argument("--root-iterator", default="HardIterator_5var_Root")
    ap.add_argument("--move-iterator", default="HardIterator_5var")
    ap.add_argument("--time-limit", type=int, default=3000, help="UCT TimeLimit ms per query")
    ap.add_argument("--timeout", type=int, default=90000, help="per-query wall timeout ms")
    ap.add_argument("--write-baseline", action="store_true",
                    help="write current known_move results to tactical_baseline.json and exit 0")
    args = ap.parse_args()

    cases = load_cases()
    known = [c for c in cases if c.get("bucket") == "known_move"]
    forced = [c for c in cases if c.get("bucket") == "looks_forced"]

    write_backlog(forced)

    if not known:
        print("tactical_suite: no known_move cases found in", CASES_DIR)
        print("  (looks_forced cases emitted to", os.path.relpath(BACKLOG_PATH, REPO) + ")")
        return 0

    baseline = {}
    if os.path.exists(BASELINE_PATH):
        with open(BASELINE_PATH, encoding="utf-8") as f:
            baseline = json.load(f)

    results = {}
    regressions = []
    print(f"tactical_suite: {len(known)} known_move case(s), {len(forced)} looks_forced "
          f"(-> {os.path.relpath(BACKLOG_PATH, REPO)})")
    print(f"  player={args.player} weights={args.weights} iter={args.root_iterator}/{args.move_iterator}\n")

    for c in known:
        name = c.get("name", c.get("_file", "?"))
        expect = (c.get("expect") or {}).get("fires_hotel")
        try:
            resp = query(c, args.player, args.weights, args.dave_exe,
                         args.time_limit, args.timeout, args.root_iterator, args.move_iterator)
        except Exception as e:
            print(f"  ERROR  {name}: {e}")
            results[name] = {"error": str(e)}
            # An error on a previously-passing case counts as a regression.
            if baseline.get(name, {}).get("passed") is True:
                regressions.append(name)
            continue

        got = fires_hotel(resp, c.get("hotel_inst_id"))
        passed = (expect is None) or (got == expect)
        results[name] = {
            "fires_hotel": got,
            "expect_fires_hotel": expect,
            "passed": passed,
            "n_clicks": len(resp.get("aiclicks") or []),
            "aivisits_len": len(resp.get("aivisits") or []),
            "aiargmax": resp.get("aiargmax"),
            "aichosen": resp.get("aichosen"),
        }
        status = "PASS" if passed else "FAIL"
        exp_str = "(no expectation)" if expect is None else f"expect={expect}"
        print(f"  {status}  {name}: fires_hotel={got} {exp_str} "
              f"[clicks={results[name]['n_clicks']}, visits={results[name]['aivisits_len']}, "
              f"argmax={results[name]['aiargmax']}, chosen={results[name]['aichosen']}]")

        # Regression = was passing in baseline, now failing.
        if baseline.get(name, {}).get("passed") is True and not passed:
            regressions.append(name)

    n_pass = sum(1 for r in results.values() if r.get("passed") is True)
    n_fail = sum(1 for r in results.values() if r.get("passed") is False)
    n_err = sum(1 for r in results.values() if "error" in r)
    print(f"\nSummary: {n_pass} PASS, {n_fail} FAIL, {n_err} ERROR (of {len(known)} known_move)")

    if args.write_baseline:
        with open(BASELINE_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
        print(f"Wrote baseline -> {os.path.relpath(BASELINE_PATH, REPO)}")
        return 0

    if not baseline:
        print("No baseline present -> treating this run as the baseline (exit 0). "
              "Re-run with --write-baseline to persist it.")
        return 0

    if regressions:
        print(f"REGRESSION: {len(regressions)} previously-passing case(s) now fail: "
              f"{', '.join(regressions)}")
        return 1
    print("No regressions vs baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
