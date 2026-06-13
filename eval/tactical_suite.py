"""O7 tactical regression suite for the RL self-play DSNN (Infusion-Grid CLICK COUNT).

PURPOSE
-------
Curated tactical positions where the RIGHT move is known. Each case is replayed through
dave's PrismataAI.exe responder via js_engine/query_move.js (UCT + NeuralNet eval, the real
deploy path), and we assert a tactical property of the returned move -- specifically the
COUNT of Infusion Grid (display name "Infusion Grid", engine codename "Hotel") self-sac
USE_ABILITY clicks.

WHY A COUNT (not a binary fire/skip)
------------------------------------
Infusion Grid self-sacs a 4HP unit -> four 1HP Husks, paying 1 red, for defensive
granularity. The decision is not fire-vs-skip but HOW MANY IGs to self-sac (usually 1 is
correct, not all). The deployed greedy root iterator `HardIterator_5var_Root` over-clicks
(fires every legal IG). The widened `HardIterator_5var_IGsubset_Root` (a
MoveIterator_AbilitySubset) emits one root child per IG-click count {0..N}, so the net can
choose the count. The count metric is therefore ONLY meaningful under the widened iterator
-- hence the CLI defaults below point at HardIterator_5var_IGsubset_Root / HardIterator_5var.

Two buckets:
  * "known_move"   -- run the case, compute count_ig_clicks(resp), compare to
                      expect.ig_click_count, print PASS/FAIL.
  * "looks_forced" -- NOT a pass/fail gate; appended to eval/backlog_action_space.md as a
                      watch-list (expect is null / unknown). Informational only.

REGRESSION SEMANTICS
--------------------
Exit nonzero ONLY if a case that MATCHED its expected count in eval/tactical_baseline.json
now differs (a true regression). If the baseline file is absent, the current run IS the
baseline -> exit 0 (and you may persist it with --write-baseline). New cases not in the
baseline never gate.

IG CLICK SHAPE -- CONFIRMED ON A REAL IG STATE (ktink_t9_ig, Jun 4 2026)
-----------------------------------------------------------------------
Empirically verified against replay KtInk-pMiQf P1 turn-9 (docs/scratch/ktink_t9_action_request.json):
the responder emits an Infusion-Grid self-sac (USE_ABILITY) click as
    {"type": "inst clicked" | "inst shift clicked",
     "args": {"cardName": "Infusion Grid", "health": 4, ...}}     <- ability-use; args is a DICT
A BUY of Infusion Grid is a DIFFERENT click and must NOT be counted:
    {"type": "card clicked" | "card shift clicked", "args": "Infusion Grid"}   <- args is a STRING
IMPORTANT NAME NOTE: in this real F6 dump the ability click reports args.cardName ==
"Infusion Grid" (the DISPLAY name), NOT the codename "Hotel" that the engine source
(Card.cpp:933) emits for internal-name decks. The live F6 dump carries display names which the
responder echoes back, so we match EITHER name (see IG_NAMES) to be robust across both paths.

SHIFT-BATCHING CAVEAT: a single "inst shift clicked" can in principle batch several identical
IG self-sacs into one click object, which this counter would under-count as 1. The curated
cases are chosen so this is unambiguous: ktink_t9_ig fires exactly one "inst clicked" IG
ability-use (count 1, verified). If a future case shows shift-batching that conflates counts,
that limitation must be revisited (the response as emitted does not carry a per-click
multiplicity).

CASE FORMAT (eval/tactical_cases/*.json)
----------------------------------------
{
  "name": str,
  "bucket": "known_move" | "looks_forced",
  "request": { "mergedDeck": [...], "gameState": {...}, "aiParameters": {...} },  # F6 CurrentInfo
  "root_iterator": str | absent,   # per-case override; falls back to --root-iterator
  "move_iterator": str | absent,   # per-case override; falls back to --move-iterator
  "expect": { "ig_click_count": int,            # asserted COUNT (null expect = informational)
              "ig_feasible_max": int | absent } # optional curated denominator override
            | null,
  "note": str
}

FEASIBLE-MAX REPORTING (count k of feasible m)
----------------------------------------------
Each case's result is reported as `count k of feasible m`, mirroring the engine's
ig_feasible_max stamp (dave@6037382): m = min(ready IGs of the mover, attainable red).
Priority: an explicit `expect.ig_feasible_max` in the case file wins; otherwise m is computed
from the case's request gameState + mergedDeck (the response carries no state), but ONLY when
the state is already in the action phase — a pre-swoosh defense-phase dump would undercount
(red pool zeroed, last turn's assigned producers unreset), so we report m as unknown ("?")
there rather than a wrong number; curate `expect.ig_feasible_max` for such cases.
m never gates pass/fail — the gate stays count == expect.ig_click_count.
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

# Default iterators: the count metric is ONLY meaningful with the widened IGsubset root that
# emits one root child per IG-click count {0..N}. The narrow HardIterator_5var_Root fires-all.
DEFAULT_ROOT_ITER = "HardIterator_5var_IGsubset_Root"
DEFAULT_MOVE_ITER = "HardIterator_5var"

# Infusion Grid identifier. Card.cpp:933 emits the engine CODENAME ("Hotel") for internal-name
# decks; live F6 dumps carry the DISPLAY name ("Infusion Grid") which the responder echoes back.
# We accept either so the counter works on both the live and internal-name paths. ("Hotel" kept
# per the original task spec.)
HOTEL_NAME = "Hotel"
IG_NAMES = ("Infusion Grid", HOTEL_NAME)


def count_ig_clicks(resp):
    """Count Infusion-Grid self-sac (USE_ABILITY) clicks in the responder's aiclicks.

    An IG ability-use click is:
        {"type": "inst clicked" | "inst shift clicked", "args": {"cardName": <IG>, ...}}
    where <IG> is the display name "Infusion Grid" or the codename "Hotel" (see IG_NAMES).
    BUYS of Infusion Grid -- {"type": "card clicked"|"card shift clicked", "args": "<IG>"}
    (args is a STRING) -- are NOT IG self-sacs and are deliberately excluded.

    LIMITATION: a single "inst shift clicked" can in principle batch multiple identical IG
    self-sacs into one click object; the emitted response carries no per-click multiplicity, so
    such a batch counts as 1. Curated cases are chosen so this is unambiguous (see module docstring).
    """
    clicks = (resp or {}).get("aiclicks") or []
    n = 0
    for c in clicks:
        if not isinstance(c, dict):
            continue
        if c.get("type") not in ("inst clicked", "inst shift clicked"):
            continue
        args = c.get("args")
        if isinstance(args, dict) and args.get("cardName") in IG_NAMES:
            n += 1
    return n


def _red_in_mana(mana):
    """Count red ('C') in a client mana/script code string (digits = gold; letters repeat)."""
    return str(mana).count("C") if mana is not None else 0


def feasible_max_for_case(case):
    """Best-effort ig_feasible_max for a tactical case: min(ready IGs, attainable red).

    Mirrors the engine stamp (dave-master TournamentGame computeIGFeasibleMax):
      ready IG       = mover-owned IG instance, alive, role 'default' (ability not yet
                       used), constructionTime == 0, delay == 0;
      attainable red = mover's red pool + red ('C') in the abilityScript receive of the
                       mover's READY click-ability units (no current card produces red on
                       click — all red production is beginOwnTurnScript — so this term is
                       0 today; kept for engine-definition parity). Ability red COSTS and
                       charge bookkeeping are ignored, exactly like the engine stamp.

    Priority:
      1. explicit `expect.ig_feasible_max` in the case file (curated override);
      2. computed from request.gameState + request.mergedDeck, ONLY when the state is
         already in the action phase (the decision point). For a pre-swoosh defense-phase
         dump the red pool is zeroed and assigned producers have not reset, so a naive
         computation would undercount — return None (unknown) instead.

    Returns int, or None when unknown."""
    override = (case.get("expect") or {}).get("ig_feasible_max")
    if override is not None:
        return int(override)

    req = case.get("request") or {}
    gs = req.get("gameState") or {}
    if gs.get("phase") != "action":
        return None

    mover = int(gs.get("turn", 0))  # client gameState: "turn" = active player index
    mana = gs.get("whiteMana") if mover == 0 else gs.get("blackMana")
    attainable_red = _red_in_mana(mana)

    # cardName -> red in abilityScript receive (mergedDeck receive uses the client mana code;
    # it may also be a bare int = gold, which contains no red).
    ability_red = {}
    has_click_ability = set()
    for entry in req.get("mergedDeck") or []:
        script = entry.get("abilityScript")
        if not isinstance(script, dict):
            continue
        name = entry.get("name")
        has_click_ability.add(name)
        recv = script.get("receive")
        if isinstance(recv, str):
            ability_red[name] = _red_in_mana(recv)

    ready_igs = 0
    for inst in gs.get("table") or []:
        if inst.get("owner") != mover or inst.get("deadness") != "alive":
            continue
        if inst.get("role") != "default":
            continue
        if int(inst.get("constructionTime", 0)) != 0 or int(inst.get("delay", 0)) != 0:
            continue
        name = inst.get("cardName")
        if name in IG_NAMES:
            ready_igs += 1
        if name in has_click_ability:
            attainable_red += ability_red.get(name, 0)

    return min(ready_igs, attainable_red)


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
    """Write the case request to a temp file, shell out to query_move.js, return parsed response.

    Per-case root_iterator / move_iterator override the CLI fallback. query_move.js prints its
    response as PRETTY-PRINTED (multi-line) JSON, so we json.loads the whole stdout -- never
    splitlines()[-1].
    """
    root_iter = case.get("root_iterator", root_iter)
    move_iter = case.get("move_iterator", move_iter)
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
        return parse_response(p.stdout)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def parse_response(stdout):
    """Robustly parse query_move.js stdout (pretty-printed multi-line JSON) into the response object.

    query_move.js writes JSON.stringify(response, null, 2) -- a single multi-line JSON object,
    optionally with surrounding whitespace. Try the whole buffer first; fall back to slicing from
    the first '{' to its matching '}'. Do NOT use splitlines()[-1] (it breaks on pretty JSON)."""
    s = stdout.strip()
    if not s:
        raise RuntimeError("query_move.js produced empty stdout")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    if start == -1:
        raise RuntimeError(f"query_move.js stdout has no JSON object:\n{s[-800:]}")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start:i + 1])
    raise RuntimeError(f"query_move.js stdout: no balanced JSON object:\n{s[-800:]}")


def write_backlog(forced_cases):
    """Emit the looks_forced watch-list to eval/backlog_action_space.md (overwrites)."""
    lines = [
        "# Action-Space Backlog (looks_forced tactical cases)",
        "",
        "Auto-generated by `eval/tactical_suite.py`. These are positions where the move",
        "*looks* forced / has no known-correct IG-click count yet (not a pass/fail gate).",
        "They are informational input to the Infusion-Grid count axis.",
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
    ap = argparse.ArgumentParser(description="O7 tactical regression suite (Infusion-Grid CLICK COUNT).")
    ap.add_argument("--player", default="RL_Eval", help="injected player name (default: RL_Eval)")
    ap.add_argument("--weights", default="neural_weights_mixed_v221.bin",
                    help="candidate weights file (resolved by the responder under asset/config/)")
    ap.add_argument("--dave-exe",
                    default=r"c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe",
                    help="path to dave's PrismataAI.exe responder")
    ap.add_argument("--root-iterator", default=DEFAULT_ROOT_ITER,
                    help="fallback root iterator; the IG count metric needs the widened IGsubset root")
    ap.add_argument("--move-iterator", default=DEFAULT_MOVE_ITER, help="fallback move iterator")
    ap.add_argument("--time-limit", type=int, default=3000, help="UCT TimeLimit ms per query")
    ap.add_argument("--timeout", type=int, default=90000, help="per-query wall timeout ms")
    ap.add_argument("--write-baseline", action="store_true",
                    help="write current known_move results to tactical_baseline.json and exit 0")
    args = ap.parse_args()

    # C3/ops-toctou-07: contamination guards at TIME OF USE — stage 6 runs hours after the
    # stage-0 sentinel check, and this protocol path is exactly what use_dsnn.txt hijacks.
    assert not os.environ.get("PRISMATA_FORCE_DSNN"), "PRISMATA_FORCE_DSNN set - tactical contamination"
    _sentinel = os.path.join(os.path.dirname(os.path.abspath(args.dave_exe)), "use_dsnn.txt")
    assert not os.path.exists(_sentinel), f"use_dsnn.txt present ({_sentinel}) - tactical contamination"

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
    print(f"  player={args.player} weights={args.weights} "
          f"default_iter={args.root_iterator}/{args.move_iterator}\n")

    for c in known:
        name = c.get("name", c.get("_file", "?"))
        expect = (c.get("expect") or {}).get("ig_click_count")
        feasible = feasible_max_for_case(c)  # int | None (never gates pass/fail)
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

        got = count_ig_clicks(resp)
        passed = (expect is None) or (got == expect)
        results[name] = {
            "ig_click_count": got,
            "expect_ig_click_count": expect,
            "ig_feasible_max": feasible,  # int | None (unknown); reporting only, never gates
            "passed": passed,
            "n_clicks": len(resp.get("aiclicks") or []),
            "aivisits_len": len(resp.get("aivisits") or []),
            "aiargmax": resp.get("aiargmax"),
            "aichosen": resp.get("aichosen"),
        }
        status = "PASS" if passed else "FAIL"
        want = "n/a" if expect is None else expect
        feas = "?" if feasible is None else feasible
        print(f"  [{status}] {name} (count {got} of feasible {feas}, want={want}) "
              f"[clicks={results[name]['n_clicks']}, visits={results[name]['aivisits_len']}, "
              f"argmax={results[name]['aiargmax']}, chosen={results[name]['aichosen']}]")

        # Regression = matched its expected count in baseline, now differs.
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
        # First run with no baseline: persist it so the regression gate has a reference next time.
        with open(BASELINE_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
        print(f"No baseline present -> wrote this run as the baseline "
              f"({os.path.relpath(BASELINE_PATH, REPO)}); exit 0.")
        return 0

    if regressions:
        print(f"REGRESSION: {len(regressions)} previously-matching case(s) now differ: "
              f"{', '.join(regressions)}")
        return 1
    print("No regressions vs baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
