"""
Find games where a player owned at least one of every random set unit.

Scans training data JSONL files and checks each game state for players who
have (or had) all 8 random set units. Since units can die, we track the
union of all units ever owned across all states in the game.

Usage:
    python tools/find_all_random_bought.py [jsonl_file ...]

If no files given, scans all known training data locations.
"""

import json
import sys
import os
from collections import defaultdict

BASE_SET = {
    "Engineer", "Drone", "Conduit", "Blastforge", "Animus",
    "Forcefield", "Gauss Cannon", "Wall", "Steelsplitter", "Tarsier", "Rhino"
}


def get_random_units(card_set):
    """Extract the random set units (non-base-set) from a card_set list."""
    return set(card_set) - BASE_SET


def get_player_unit_names(units_list):
    """Get unique unit names from a player's unit list."""
    return {u["name"] for u in units_list}


def scan_file(filepath):
    """Scan a JSONL file for games where a player owned all random set units."""
    print(f"\nScanning: {filepath}")
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  File size: {file_size_mb:.1f} MB")

    # Per-game tracking: {replay_code: {random_units, p0_ever_owned, p1_ever_owned, metadata}}
    games = defaultdict(lambda: {
        "random_units": None,
        "p0_ever_owned": set(),
        "p1_ever_owned": set(),
        "p0_name": "",
        "p1_name": "",
        "p0_rating": 0,
        "p1_rating": 0,
        "result": None,
        "max_turn": 0,
    })

    line_count = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            if line_count % 100000 == 0:
                print(f"  ...processed {line_count:,} states ({len(games):,} games)")

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            code = record.get("replay_code", "")
            state = record.get("state", {})
            if not state or not code:
                continue

            game = games[code]

            # Set random units from card_set (only need to do once per game)
            if game["random_units"] is None:
                card_set = state.get("card_set", [])
                game["random_units"] = get_random_units(card_set)
                game["p0_name"] = record.get("p0_name", "")
                game["p1_name"] = record.get("p1_name", "")
                game["p0_rating"] = record.get("p0_rating") or record.get("rating_p0", 0)
                game["p1_rating"] = record.get("p1_rating") or record.get("rating_p1", 0)
                game["result"] = record.get("result")

            turn = record.get("turn", 0)
            if turn > game["max_turn"]:
                game["max_turn"] = turn

            # Track units ever owned by each player (intersect with random set only)
            random = game["random_units"]
            p0_units = get_player_unit_names(state.get("p0_units", []))
            p1_units = get_player_unit_names(state.get("p1_units", []))
            game["p0_ever_owned"].update(p0_units & random)
            game["p1_ever_owned"].update(p1_units & random)

    print(f"  Total: {line_count:,} states, {len(games):,} games")

    # Find matches
    matches = []
    for code, game in games.items():
        random = game["random_units"]
        if not random or len(random) < 5:
            # Skip games with very few random units (base-set-only or weird formats)
            continue

        num_random = len(random)

        for player_idx, (owned, name, rating) in enumerate([
            (game["p0_ever_owned"], game["p0_name"], game["p0_rating"]),
            (game["p1_ever_owned"], game["p1_name"], game["p1_rating"]),
        ]):
            count = len(owned)
            missing = random - owned
            if count == num_random:
                winner = game["result"]
                won = (winner == player_idx) if winner is not None else None
                matches.append({
                    "replay_code": code,
                    "player": name,
                    "player_idx": player_idx,
                    "rating": rating,
                    "opponent": game["p1_name"] if player_idx == 0 else game["p0_name"],
                    "opp_rating": game["p1_rating"] if player_idx == 0 else game["p0_rating"],
                    "won": won,
                    "num_random": num_random,
                    "units_owned": sorted(owned),
                    "game_length": game["max_turn"],
                })
            elif count >= num_random - 1:
                # Near misses (missed by 1 unit) - track for stats
                pass

    return matches, games


def main():
    default_files = [
        "c:/libraries/prismata-replay-parser/training_data.jsonl",
        "c:/libraries/prismata-replay-parser/expert_1500_training_data.jsonl",
        "c:/libraries/prismata-replay-parser/community_training_data.jsonl",
    ]

    files = sys.argv[1:] if len(sys.argv) > 1 else default_files
    files = [f for f in files if os.path.exists(f)]

    if not files:
        print("No training data files found!")
        return

    all_matches = []
    total_games = 0
    near_misses_total = 0

    for filepath in files:
        matches, games = scan_file(filepath)
        all_matches.extend(matches)
        total_games += len(games)

        # Count near misses (owned all but 1)
        for code, game in games.items():
            random = game["random_units"]
            if not random or len(random) < 5:
                continue
            num_random = len(random)
            for owned in [game["p0_ever_owned"], game["p1_ever_owned"]]:
                if len(owned) == num_random - 1:
                    near_misses_total += 1

    # Deduplicate by replay_code + player (in case same game in multiple files)
    seen = set()
    unique_matches = []
    for m in all_matches:
        key = (m["replay_code"], m["player_idx"])
        if key not in seen:
            seen.add(key)
            unique_matches.append(m)

    print(f"\n{'='*70}")
    print(f"RESULTS: Searched {total_games:,} games across {len(files)} file(s)")
    print(f"{'='*70}")

    if unique_matches:
        print(f"\nFound {len(unique_matches)} instance(s) where a player owned ALL random set units:\n")
        for i, m in enumerate(unique_matches, 1):
            won_str = "WON" if m["won"] else ("LOST" if m["won"] is not None else "???")
            print(f"  {i}. {m['player']} ({m['rating']:.0f}) vs {m['opponent']} ({m['opp_rating']:.0f})")
            print(f"     Replay: {m['replay_code']}")
            print(f"     Result: {won_str} | Game length: {m['game_length']} turns | Random units: {m['num_random']}")
            print(f"     Units owned: {', '.join(m['units_owned'])}")
            print()
    else:
        print("\nNo games found where a player owned ALL random set units.")

    print(f"Near misses (owned all but 1): {near_misses_total:,}")
    print()

    # Stats: distribution of how many random units were owned
    print("Distribution of max random units owned per player-game:")
    dist = defaultdict(int)
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            # Re-scan is expensive, so skip this for now
            pass
    # (Distribution would require a second pass - skip for efficiency)


if __name__ == "__main__":
    main()
