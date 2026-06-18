"""Build eval/ma_battery/ from F6 clipboard dumps (the MA / IG+MA axis sanity + combinatorics states).

An F6 dump is NOT a self-contained JSON document. It is a multi-section text blob:
    "CurrentInfo"   : { mergedDeck, gameState, aiParameters, aiPlayerName }   <-- the live (action-phase) state
    "TurnStartInfo" : { ... }                                                 <-- turn-start snapshot (ignored here)
    <trailing plain-text "VOU [UIName] chN hpM val=..." debug lines>          <-- engine static unit valuations

This converter brace-matches the CurrentInfo object out of the blob (string-aware), writes the inner
request object ({mergedDeck, gameState, aiParameters, aiPlayerName}) as a clean query_move-ready
*.json into eval/ma_battery/, and parses the trailing VOU lines into a <name>.vou.json sidecar (a free
diagnostic: the engine's static value-of-unit at that state, useful to sanity-check the net's MA-count
choice against keep-MA vs sac-MA->Rhino).

Usage:
    python eval/build_ma_battery.py            # build from the default F6 dump list -> eval/ma_battery/
    python eval/build_ma_battery.py --inspect  # also print gameState instance schema of the first state
"""
import argparse
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRATCH = os.path.join(REPO, "docs", "scratch")
OUT = os.path.join(HERE, "ma_battery")

# The owner-provided F6 dumps. MA-only (16, 2 games) + IG+MA (5: 1 "max realistic" + 4 awkward-game).
DEFAULT_GLOBS = [
    "cPvQ3-thNwH_MA*.txt",
    "RY8WE-GMets_MA*.txt",
    "4+q6a-Y8Ak7_IGMA*.txt",
    "kTRQv-OFEm0_IGMA*.txt",
]


def extract_balanced(text, key):
    """Return the balanced {...} object that follows `"<key>"` in text (string/escape aware), or None."""
    i = text.find('"' + key + '"')
    if i < 0:
        return None
    b = text.find("{", i)
    if b < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j in range(b, len(text)):
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[b:j + 1]
    return None


VOU_RE = re.compile(r"VOU \[([^\]]+)\] ch(\d+) hp(\d+) val=([0-9.eE+-]+)")


def parse_vou(text):
    """Parse the trailing 'VOU [UIName] chN hpM val=X' debug lines into a list of dicts (deduped-ordered)."""
    out = []
    for m in VOU_RE.finditer(text):
        out.append({"unit": m.group(1), "charge": int(m.group(2)),
                    "hp": int(m.group(3)), "val": float(m.group(4))})
    return out


def count_owned(gamestate):
    """Best-effort per-unit instance counts from the gameState. Returns {} if the schema isn't recognized;
    the authoritative MA/IG read is query_move's aivisits, this is only a human-facing battery sanity report."""
    counts = {}
    for key in ("cards", "table"):
        seq = gamestate.get(key)
        if not isinstance(seq, list):
            continue
        for inst in seq:
            if not isinstance(inst, dict):
                continue
            name = inst.get("name") or inst.get("UIName") or inst.get("cardName")
            if name:
                counts[name] = counts.get(name, 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true", help="print the first gameState's instance schema")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    files = []
    for g in DEFAULT_GLOBS:
        files.extend(sorted(glob.glob(os.path.join(SCRATCH, g))))
    if not files:
        raise SystemExit(f"no F6 dumps matched under {SCRATCH}")

    print(f"building {OUT} from {len(files)} F6 dumps\n")
    first = True
    rows = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        text = open(f, encoding="utf-8", errors="replace").read()
        obj_str = extract_balanced(text, "CurrentInfo")
        if obj_str is None:
            raise SystemExit(f"{name}: no CurrentInfo object")
        obj = json.loads(obj_str)
        if "gameState" not in obj or "mergedDeck" not in obj:
            raise SystemExit(f"{name}: CurrentInfo missing gameState/mergedDeck")
        gs = obj["gameState"]

        if a.inspect and first:
            first = False
            print(f"[inspect] {name} gameState keys: {list(gs.keys())}")
            for key in ("cards", "table"):
                seq = gs.get(key)
                if isinstance(seq, list) and seq:
                    print(f"[inspect]   {key}[0] = {json.dumps(seq[0])[:300]}")
            print()

        out_path = os.path.join(OUT, name + ".json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        vou = parse_vou(text)
        if vou:
            with open(os.path.join(OUT, name + ".vou.json"), "w", encoding="utf-8") as fh:
                json.dump(vou, fh, indent=2)
        owned = count_owned(gs)
        ig = owned.get("Hotel", 0) + owned.get("Infusion Grid", 0)
        ma = owned.get("Mobile Animus", 0)
        rows.append((name, gs.get("phase"), gs.get("turn"), obj.get("aiPlayerName"),
                     ig, ma, len(vou)))

    print(f"{'state':30s} {'phase':8s} {'turn':>4s} {'mover':10s} {'IG':>3s} {'MA':>3s} {'VOU':>4s}")
    for r in rows:
        print(f"{r[0]:30s} {str(r[1]):8s} {str(r[2]):>4s} {str(r[3]):10s} {r[4]:>3d} {r[5]:>3d} {r[6]:>4d}")
    print(f"\nwrote {len(rows)} battery states + VOU sidecars -> {OUT}")


if __name__ == "__main__":
    main()
