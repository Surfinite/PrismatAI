"""Analyze + convert F6 'CurrentInfo' clipboard dumps into query_move.js request files for the
IG battery.

For each .txt dump it:
  - extracts the CurrentInfo object (brace-match),
  - determines the ACTIVE player (gameState.turn: 0=white/P0, 1=black/P1; numTurns = real turn #),
  - checks IG-decidability: active player owns >=1 ready (built, alive, not-yet-used) Infusion Grid
    AND has red ('C') available to pay the self-sac,
  - dedups on the canonical gameState (logically-identical states, even if not byte-identical),
  - writes the valid, unique ones as {mergedDeck, gameState, aiParameters} request JSONs.

Usage:
  python eval/f6_to_request.py <indir> [--out <dir>] [--write]
    (no --write => analysis report only; --write => emit request JSONs for VALID+UNIQUE states)
"""
import argparse
import glob
import hashlib
import io
import json
import os

IG_NAMES = {"Infusion Grid", "Hotel"}


def extract_currentinfo(txt):
    i = txt.find("{")
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(txt)):
        c = txt[j]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            instr = not instr
            continue
        if instr:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(txt[i:j + 1])
    raise ValueError("no balanced object")


def ready_igs(gs, active):
    """IGs owned by the active player that are built, alive, and not blocking (so still abilitiable)."""
    out = []
    for c in gs.get("table", []):
        if c.get("cardName") in IG_NAMES and c.get("owner") == active \
                and int(c.get("constructionTime", 0)) == 0 \
                and c.get("deadness", "alive") == "alive" and not c.get("dead", False) \
                and int(c.get("health", 1)) > 0:
            out.append(c)
    return out


def analyze(path):
    ci = extract_currentinfo(io.open(path, encoding="utf-8-sig").read())
    gs = ci["gameState"]
    active = int(gs.get("turn", 0))          # 0=white/P0, 1=black/P1
    mana = (gs.get("whiteMana") if active == 0 else gs.get("blackMana")) or ""
    has_red = "C" in mana
    igs = ready_igs(gs, active)
    # canonical state hash for logical-dup detection
    h = hashlib.md5(json.dumps(gs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    return dict(path=path, ci=ci, gs=gs, active=active, side=("white/P0" if active == 0 else "black/P1"),
                mana=mana, has_red=has_red, n_ready_ig=len(igs), real_turn=gs.get("numTurns"),
                phase=gs.get("phase"), state_hash=h,
                valid=(gs.get("phase") == "action" and len(igs) >= 1 and has_red))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indir")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_battery"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.indir, "*.txt")))
    rows = [analyze(f) for f in files]

    # logical-dup groups (same gameState)
    by_hash = {}
    for r in rows:
        by_hash.setdefault(r["state_hash"], []).append(r)
    dup_groups = {h: rs for h, rs in by_hash.items() if len(rs) > 1}

    print(f"{'file':22s} {'realT':>5s} {'active':>9s} {'phase':>7s} {'redC':>4s} {'rdyIG':>5s} {'valid':>5s} {'stateHash':>12s}")
    print("-" * 84)
    for r in rows:
        print(f"{os.path.basename(r['path']):22s} {str(r['real_turn']):>5s} {r['side']:>9s} "
              f"{r['phase']:>7s} {('Y' if r['has_red'] else 'n'):>4s} {r['n_ready_ig']:>5d} "
              f"{('YES' if r['valid'] else '—'):>5s} {r['state_hash']:>12s}")

    print("\n=== logical-duplicate groups (identical gameState) ===")
    if dup_groups:
        for h, rs in dup_groups.items():
            print(f"  {h}: {[os.path.basename(x['path']) for x in rs]}")
    else:
        print("  none")

    invalid = [r for r in rows if not r["valid"]]
    print("\n=== invalid (excluded) states ===")
    for r in invalid:
        why = []
        if r["phase"] != "action":
            why.append(f"phase={r['phase']}")
        if r["n_ready_ig"] < 1:
            why.append("no ready IG owned by active")
        if not r["has_red"]:
            why.append("no red (C) in active mana")
        print(f"  {os.path.basename(r['path']):22s} -> {', '.join(why)}")

    if a.write:
        os.makedirs(a.out, exist_ok=True)
        written = 0
        seen = set()
        for r in rows:
            if not r["valid"] or r["state_hash"] in seen:
                continue
            seen.add(r["state_hash"])
            ci = r["ci"]
            req = {"mergedDeck": ci["mergedDeck"], "gameState": ci["gameState"],
                   "aiParameters": ci["aiParameters"]}
            base = os.path.splitext(os.path.basename(r["path"]))[0]
            outp = os.path.join(a.out, base + ".json")
            io.open(outp, "w", encoding="utf-8").write(json.dumps(req, indent=2))
            written += 1
        print(f"\nWROTE {written} unique valid request JSON(s) to {a.out}")


if __name__ == "__main__":
    main()
