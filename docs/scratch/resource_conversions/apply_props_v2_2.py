"""Migrate training/property_table.json: split base_attack -> auto_attack/click_attack,
add frontline. (feature_revision v2.2)

- Removes `base_attack` (verified == auto_receive_A + click_receive_A for all 116 units).
- Appends `auto_attack`  (beginOwnTurnScript.receive A-count, guaranteed each turn),
          `click_attack` (abilityScript.receive A-count, optional ability),
          `frontline`    (1 if the unit is `undefendable` = the game's Frontline keyword:
                          the attacker may direct damage onto it; the engine's defense
                          solver branches on isFrontline()).

Non-destructive source conventions match build_feature_table.py (digits/int=gold,
G/B/C/H/A letter-count; only `A` is relevant here). Writes training/property_table.json
in place (git is the backup). Run from repo root: python docs/scratch/resource_conversions/apply_props_v2_2.py
"""
import json

PT   = "training/property_table.json"
LIB  = "bin/asset/config/cardLibrary.jso"
REV  = "v2.2-frontline-atksplit"

lib = json.load(open(LIB))
by_disp = {c.get("UIName", k): c for k, c in lib.items() if isinstance(c, dict)}

def acount(s):
    return s.count("A") if isinstance(s, str) else 0

def attack_split(c):
    bt = c.get("beginOwnTurnScript") if isinstance(c.get("beginOwnTurnScript"), dict) else {}
    ab = c.get("abilityScript")      if isinstance(c.get("abilityScript"), dict)      else {}
    return acount(bt.get("receive", "")), acount(ab.get("receive", ""))

pt = json.load(open(PT))
names = pt["property_names"]
assert "base_attack" in names, "base_attack not present — already migrated?"
ba_idx = names.index("base_attack")

new_names = names[:ba_idx] + names[ba_idx + 1:] + ["auto_attack", "click_attack", "frontline"]

for disp, rec in pt["units"].items():
    props = rec["properties"]
    old_ba = props[ba_idx]
    c = by_disp.get(disp, {})
    auto_a, click_a = attack_split(c)
    frontline = 1 if c.get("undefendable") else 0
    # Integrity: the split must exactly reconstruct the removed base_attack.
    assert auto_a + click_a == old_ba, f"{disp}: auto+click ({auto_a}+{click_a}) != base_attack ({old_ba})"
    rec["properties"] = props[:ba_idx] + props[ba_idx + 1:] + [auto_a, click_a, frontline]
    assert len(rec["properties"]) == len(new_names)

pt["property_names"]  = new_names
pt["num_properties"]  = len(new_names)
pt["feature_revision"] = REV

json.dump(pt, open(PT, "w"), indent=1)
print(f"OK: num_properties -> {pt['num_properties']} (removed base_attack; +auto_attack,click_attack,frontline)")
print(f"feature_revision = {REV}")
# Spot-checks
def row(u):
    p = pt["units"][u]["properties"]; n = new_names
    return {k: p[n.index(k)] for k in ("auto_attack", "click_attack", "frontline")}
for u in ("Centrifuge", "Hannibull", "Thunderhead", "Wild Drone", "Polywall", "Rhino", "Steelsplitter"):
    print(f"  {u:14s} {row(u)}")
nf = sum(1 for r in pt["units"].values() if r["properties"][new_names.index("frontline")])
print(f"frontline units: {nf}  (expect 7)")
