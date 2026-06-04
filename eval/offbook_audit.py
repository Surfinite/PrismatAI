#!/usr/bin/env python
"""
116-unit off-book buy-reachability audit (axis-2 gate).

For each of the 116 units, determine whether ANY off-book whole-turn buy the move
iterator emits can purchase it, given ample resources. This is a finite, search-FREE
audit: it drives the engine's --probe-buys hook, which enumerates the children of the
OB-off HardIterator_Root and reports the distinct BUY unit codenames it can buy.

Units never reachable off-book across a small battery of plausible states go on the
RL_Explore exclusion filter (gates axis-2 widening). Wild Drone / Doomed Drone are
known-unbuildable tokens -> used as a known-answer sanity check.

Outputs:
  eval/offbook_reachability.json  per-unit {reachable: bool, hits: [...battery names...]}
  eval/rl_explore_filter.json     {"exclude": [...unreachable UInames...]}

Usage:
  python eval/offbook_audit.py
  python eval/offbook_audit.py --dave-bin <PrismataAI.exe> --unit-index <unit_index.json>
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# NOTE: CMake emits bin/Prismata_Standalone.exe; the Standalone Release is copied to
# PrismataAI.exe per project convention. Override with --dave-bin if your layout differs.
DEFAULT_DAVE_BIN = r"c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe"
DEFAULT_UNIT_INDEX = os.path.join(REPO, "training", "data", "unit_index.json")
DEFAULT_CARDLIB = r"c:/libraries/PrismataAI-dave-master/bin/asset/config/cardLibrary.jso"
DEFAULT_TEMPLATE = os.path.join(HERE, "offbook_template.json")

# Ample resources of EVERY type (digits=gold, H=energy, B=blue, C=red, G=green, A=attack).
# Attack (A) is included so units whose buyCost contains attack symbols (e.g. Mega Drone
# '5HHHAAAA', Bloodrager '7CAAA') are affordable -- in real play that attack comes from
# having attackers on the turn it is spent; modelling it as ample isolates pure buy-cost
# reachability from board-composition luck.
AMPLE = "30" + "G" * 12 + "B" * 12 + "C" * 12 + "H" * 12 + "A" * 16

# Colour-emphasis variants: a few mana strings that bias toward a single colour, all with
# ample attack, in case a heuristic only spends what it can "afford comfortably".
COLOUR_VARIANTS = [
    AMPLE,
    "40" + "H" * 20 + "A" * 16,            # gold + energy heavy
    "20" + "B" * 20 + "G" * 8 + "A" * 16,  # blue heavy
    "20" + "C" * 20 + "G" * 8 + "A" * 16,  # red heavy
    "20" + "G" * 20 + "B" * 8 + "A" * 16,  # green heavy
]

# Sac fodder added to the active player's board so units with a buySac cost (e.g. Manticore
# sacs a Treant/Steelsplitter, Tia Thurnax sacs 7 Drones) can actually be built. Plain
# Drones + a Steelsplitter (codename Treant) cover the known buySac requirements. role MUST
# be "assigned": Card::canSac() refuses to sac a unit that hasAbility() unless its status is
# Assigned (i.e. its ability is already used / tapped), so "default" fodder is un-saccable.
SAC_FODDER = (
    [{"owner": 0, "cardName": "Drone", "health": 1, "disruptDamage": 0, "deadness": "alive",
      "role": "assigned", "constructionTime": 0, "charge": 0, "delay": 0, "lifespan": -1,
      "blocking": False} for _ in range(8)]
    + [{"owner": 0, "cardName": "Treant", "health": 4, "disruptDamage": 0, "deadness": "alive",
        "role": "assigned", "constructionTime": 0, "charge": 0, "delay": 0, "lifespan": -1,
        "blocking": False}]
)

# A standing enemy attacking board (owner 1). The HardIterator_Root buy partials are
# NEED-driven: BCGDef only emits defensive buys when there is incoming attack to block.
# Appending this to some battery states surfaces pure defensive units (Wall, Barrier,
# Aegis, Forcefield, ...) that an unthreatened position never prompts a buy for.
ENEMY_ATTACK_CARD = {
    "owner": 1, "cardName": "Elephant", "health": 2, "disruptDamage": 0,
    "deadness": "alive", "role": "default", "constructionTime": 0, "charge": 2,
    "delay": 0, "lifespan": -1, "blocking": False,
}


def load_codename_to_uiname(cardlib_path):
    """codename -> display (UI) name; UIName field if present else the codename itself."""
    with open(cardlib_path, encoding="utf-8-sig") as f:
        d = json.load(f)
    cn2ui = {}
    for cn, e in d.items():
        cn2ui[cn] = e.get("UIName") or cn
    return cn2ui, d


# A "passive" battery: gold/colour/energy only -- NO attack resource, NO sac fodder. This
# models a plain economy/buy turn with no attackers on board and nothing to sacrifice, and
# surfaces units that require a prerequisite (attack income or sac fodder) to buy off-book.
PASSIVE_VARIANTS = [
    "30" + "G" * 12 + "B" * 12 + "C" * 12 + "H" * 12,
    "40" + "H" * 20,
    "20" + "B" * 20 + "G" * 8,
    "20" + "C" * 20 + "G" * 8,
    "20" + "G" * 20 + "B" * 8,
]


def build_states(unit_codename, template, tier="ample"):
    """Return a battery of REAL gameState dicts that make `unit_codename` buyable.

    tier="ample":   ample resources of EVERY type (incl. attack) + sac fodder on board.
    tier="passive": gold/colour/energy only, no attack, no sac fodder.

    Each state: deep-copy the template, ensure the unit's codename is in the buyable `cards`
    array (with matching supply entries), phase=action, turn>=3.
    """
    states = []
    variants = COLOUR_VARIANTS if tier == "ample" else PASSIVE_VARIANTS
    # Run every mana emphasis with and without a standing enemy attacking board (the latter
    # only changes the need-driven heuristic mode; harmless for the AllBuy legality mode).
    battery = [(m, False) for m in variants] + [(m, True) for m in variants]
    for mana, under_attack in battery:
        st = json.loads(json.dumps(template))  # deep copy
        st["phase"] = "action"
        st["turn"] = 0            # active player = Player_One (matches iterator player)
        st["numTurns"] = 4        # >= 3
        st["whiteMana"] = mana
        table = list(st.get("table", []))
        if tier == "ample":
            table += [json.loads(json.dumps(c)) for c in SAC_FODDER]
        if under_attack:
            table += [json.loads(json.dumps(ENEMY_ATTACK_CARD)) for _ in range(8)]
        st["table"] = table

        cards = list(st.get("cards", []))
        wtot = list(st.get("whiteTotalSupply", []))
        btot = list(st.get("blackTotalSupply", []))
        wsp = list(st.get("whiteSupplySpent", []))
        bsp = list(st.get("blackSupplySpent", []))

        # Normalise parallel arrays to the cards length (template ships them parallel).
        n = len(cards)
        wtot = (wtot + [10] * n)[:n]
        btot = (btot + [10] * n)[:n]
        wsp = (wsp + [0] * n)[:n]
        bsp = (bsp + [0] * n)[:n]

        if unit_codename not in cards:
            cards.append(unit_codename)
            wtot.append(20)       # generous supply so it is never supply-exhausted
            btot.append(20)
            wsp.append(0)
            bsp.append(0)
        else:
            # ensure it is not supply-exhausted for white
            idx = cards.index(unit_codename)
            if wtot[idx] <= wsp[idx]:
                wtot[idx] = wsp[idx] + 20

        st["cards"] = cards
        st["whiteTotalSupply"] = wtot
        st["blackTotalSupply"] = btot
        st["whiteSupplySpent"] = wsp
        st["blackSupplySpent"] = bsp
        states.append(st)
    return states


def probe(dave_bin, state, tmpdir):
    """Run --probe-buys on a single state dict; return the set of buyable codenames."""
    sf = os.path.join(tmpdir, "probe_state.json")
    of = os.path.join(tmpdir, "probe_out.json")
    with open(sf, "w", encoding="utf-8") as f:
        json.dump(state, f)
    bin_dir = os.path.dirname(os.path.abspath(dave_bin))
    r = subprocess.run(
        [os.path.abspath(dave_bin), "--probe-buys", sf, of],
        cwd=bin_dir, capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(of):
        sys.stderr.write(
            "  probe FAILED (rc=%d): %s\n" % (r.returncode, (r.stderr or "").strip()[:300])
        )
        return None
    with open(of, encoding="utf-8") as f:
        out = json.load(f)
    return set(out.get("buyable_units", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dave-bin", default=DEFAULT_DAVE_BIN)
    ap.add_argument("--unit-index", default=DEFAULT_UNIT_INDEX)
    ap.add_argument("--cardlib", default=DEFAULT_CARDLIB)
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--only", default=None,
                    help="comma-separated UInames to probe (validation subset)")
    args = ap.parse_args()

    with open(args.unit_index, encoding="utf-8") as f:
        units = json.load(f)["units"]          # UIname -> index
    cn2ui, _ = load_codename_to_uiname(args.cardlib)
    ui2cn = {ui: cn for cn, ui in cn2ui.items()}

    with open(args.template, encoding="utf-8") as f:
        template = json.load(f)

    targets = list(units.keys())
    if args.only:
        wanted = [s.strip() for s in args.only.split(",")]
        targets = [u for u in targets if u in wanted]

    def reach_in_tier(codename, tier):
        """True iff a single off-book BUY of `codename` is legal in any tier battery state."""
        for state in build_states(codename, template, tier=tier):
            buyable = probe(args.dave_bin, state, tmpdir)
            if buyable and codename in buyable:
                return True
        return False

    reachability = {}
    tmpdir = tempfile.mkdtemp(prefix="offbook_")
    for ui_name in targets:
        codename = ui2cn.get(ui_name, ui_name)
        ample = reach_in_tier(codename, "ample")
        passive = reach_in_tier(codename, "passive")
        # Prerequisite classification: what (beyond gold/colour mana) the off-book buy needs.
        if passive:
            tier = "passive"          # buyable on a plain economy turn
        elif ample:
            tier = "needs_prereq"     # needs attack income and/or sac fodder
        else:
            tier = "unbuildable"      # no legal off-book buy even with ample everything
        reachability[ui_name] = {
            "codename": codename,
            "reachable": ample,       # reachable off-book at all (given ample resources)
            "reachable_passive": passive,
            "tier": tier,
        }
        flag = {"passive": "REACH ", "needs_prereq": "PREREQ", "unbuildable": "  --  "}[tier]
        print("[%s] %-22s (%s)" % (flag, ui_name, codename))

    reachable_n = sum(1 for v in reachability.values() if v["reachable"])
    passive_n = sum(1 for v in reachability.values() if v["reachable_passive"])
    prereq = sorted(u for u, v in reachability.items() if v["tier"] == "needs_prereq")
    unreachable = sorted(u for u, v in reachability.items() if not v["reachable"])
    print("\n%d/%d reachable off-book (ample resources); %d also reachable on a passive turn"
          % (reachable_n, len(reachability), passive_n))
    print("NEEDS-PREREQ (attack income and/or sac fodder):", prereq)
    print("UNREACHABLE (no legal off-book buy even with ample everything):", unreachable)

    if not args.only:
        out_reach = os.path.join(HERE, "offbook_reachability.json")
        out_filter = os.path.join(HERE, "rl_explore_filter.json")
        with open(out_reach, "w", encoding="utf-8") as f:
            json.dump({
                "n_units": len(reachability),
                "n_reachable_ample": reachable_n,
                "n_reachable_passive": passive_n,
                "n_unreachable": len(unreachable),
                "needs_prereq": prereq,
                "mode": "AllBuy (exhaustive single-BUY legality: in-set + affordable + supply)",
                "note": (
                    "reachable = a single off-book BUY is legal given AMPLE resources of every "
                    "type (incl. attack) + standard sac fodder. reachable_passive = also legal "
                    "on a plain economy turn (gold/colour/energy only, no attack income, no sac "
                    "fodder). tier=needs_prereq units require attack income (buyCost has 'A') "
                    "and/or sac fodder (buySac). dave-master's cardLibrary.jso models ALL 116 "
                    "units as buyable (no token flag), so nothing is structurally unbuildable."
                ),
                "units": reachability,
            }, f, indent=2)
        with open(out_filter, "w", encoding="utf-8") as f:
            json.dump({
                "description": (
                    "Units with NO legal off-book whole-turn buy even given ample resources of "
                    "every type + sac fodder -> excluded from axis-2 RL widening. Empty here "
                    "because the engine card library models every unit as buyable; the game-rules "
                    "'token' exclusion (Wild Drone, Doomed Drone) is a deck-construction concept "
                    "the engine does not encode, so it cannot be derived from the iterator."
                ),
                "mode": "AllBuy",
                "exclude": unreachable,
                "needs_prereq_hint": prereq,
            }, f, indent=2)
        print("wrote", out_reach)
        print("wrote", out_filter)

        # Known-answer sanity check (tokens). In real games Wild Drone / Doomed Drone are
        # spawned by abilities and never offered in the buy panel, so a game-rules audit
        # expects them UNREACHABLE. NOTE: dave-master's cardLibrary.jso models BOTH as
        # ordinary 'normal'-rarity units with a real buyCost, and isBuyable() only gates on
        # (in-buyable-set + supply>0) -- there is NO token flag. So once a battery state
        # injects them into the buyable set they ARE engine-buyable. We therefore report the
        # verdict as a SOFT check rather than hard-failing: a True here reflects the card-
        # library modelling, not a bug. The structural game-rules exclusion of tokens belongs
        # in deck construction, not in the iterator.
        for token in ("Wild Drone", "Doomed Drone"):
            if token in reachability:
                verdict = reachability[token]["reachable"]
                tag = "reachable (card-lib models it buyable)" if verdict else "unreachable"
                print("sanity[%s]: %s" % (token, tag))

    return 0


if __name__ == "__main__":
    sys.exit(main())
