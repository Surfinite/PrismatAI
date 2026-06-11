"""Unit tests for the ig_feasible_max binning (eval/action_coverage.py selfplay_ig_rate)
and the tactical-suite `count k of feasible m` denominator (eval/tactical_suite.py
feasible_max_for_case). Engine source of the stamp: dave-master@6037382."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from action_coverage import selfplay_ig_rate
from tactical_suite import feasible_max_for_case


# ---------------------------------------------------------------------------
# selfplay_ig_rate: feasible-max binning over synthetic JSONL records
# ---------------------------------------------------------------------------

def write_jsonl(tmp_path, records, name="selfplay_0000.jsonl"):
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return p


def test_pair_and_normalized_binning(tmp_path):
    records = [
        # ig_present turns with the stamp: pairs (1,2), (1,2), (0,2), (2,2), (0,0)
        {"ig_present": 1, "ig_click_count": 1, "ig_feasible_max": 2},
        {"ig_present": 1, "ig_click_count": 1, "ig_feasible_max": 2},
        {"ig_present": 1, "ig_click_count": 0, "ig_feasible_max": 2},
        {"ig_present": 1, "ig_click_count": 2, "ig_feasible_max": 2},
        {"ig_present": 1, "ig_click_count": 0, "ig_feasible_max": 0},  # excluded from norm view
        # non-IG turn: ignored entirely
        {"ig_present": 0, "ig_click_count": 0, "ig_feasible_max": 0},
    ]
    write_jsonl(tmp_path, records)
    out = selfplay_ig_rate(str(tmp_path))

    # backward-compatible raw keys keep their meanings
    assert out["ig_present_turns"] == 5
    assert out["ig_click_dist_selfplay"] == {"0": 2, "1": 2, "2": 1}
    assert out["mean_ig_clicks_selfplay"] == (1 + 1 + 0 + 2 + 0) / 5

    # pair distribution over stamped ig_present turns
    assert out["ig_feasible_pair_dist"] == {"0/0": 1, "0/2": 1, "1/2": 2, "2/2": 1}
    assert out["ig_feasible_turns"] == 5

    # normalized view: feasible_max == 0 excluded; ratios 0.5, 0.5, 0.0, 1.0
    assert out["ig_feasible_positive_turns"] == 4
    assert out["ig_click_norm_mean"] == (0.5 + 0.5 + 0.0 + 1.0) / 4
    assert out["ig_click_norm_dist"] == {"0.00": 1, "0.50": 2, "1.00": 1}

    assert out["ig_feasible_missing_records"] == 0
    assert out["ig_feasible_invariant_violations"] == 0


def test_old_records_fallback_to_raw_view(tmp_path):
    records = [
        # old exporter records: no ig_feasible_max
        {"ig_present": 1, "ig_click_count": 1},
        {"ig_present": 1, "ig_click_count": 0},
        # one new record alongside
        {"ig_present": 1, "ig_click_count": 1, "ig_feasible_max": 1},
    ]
    write_jsonl(tmp_path, records)
    out = selfplay_ig_rate(str(tmp_path))

    # raw view covers ALL ig_present turns (old + new)
    assert out["ig_present_turns"] == 3
    assert out["ig_click_dist_selfplay"] == {"0": 1, "1": 2}

    # feasible views cover only the stamped record; the 2 old ones are flagged
    assert out["ig_feasible_turns"] == 1
    assert out["ig_feasible_pair_dist"] == {"1/1": 1}
    assert out["ig_feasible_missing_records"] == 2


def test_all_old_records_yields_empty_feasible_views(tmp_path):
    records = [{"ig_present": 1, "ig_click_count": 2}] * 3
    write_jsonl(tmp_path, records)
    out = selfplay_ig_rate(str(tmp_path))
    assert out["ig_feasible_turns"] == 0
    assert out["ig_feasible_pair_dist"] == {}
    assert out["ig_click_norm_mean"] is None
    assert out["ig_click_norm_dist"] == {}
    assert out["ig_feasible_missing_records"] == 3


def test_invariant_violation_counted_not_fatal(tmp_path):
    write_jsonl(tmp_path, [{"ig_present": 1, "ig_click_count": 3, "ig_feasible_max": 1}])
    out = selfplay_ig_rate(str(tmp_path))
    assert out["ig_feasible_invariant_violations"] == 1
    assert out["ig_feasible_pair_dist"] == {"3/1": 1}


def test_pair_dist_keys_sorted_numerically(tmp_path):
    records = [
        {"ig_present": 1, "ig_click_count": 10, "ig_feasible_max": 10},
        {"ig_present": 1, "ig_click_count": 2, "ig_feasible_max": 10},
        {"ig_present": 1, "ig_click_count": 2, "ig_feasible_max": 3},
    ]
    write_jsonl(tmp_path, records)
    out = selfplay_ig_rate(str(tmp_path))
    # numeric (k, m) order, not lexicographic ("10/10" < "2/10" lexicographically)
    assert list(out["ig_feasible_pair_dist"]) == ["2/3", "2/10", "10/10"]


# ---------------------------------------------------------------------------
# feasible_max_for_case: tactical-case denominator
# ---------------------------------------------------------------------------

def make_case(table, white_mana="BBCCA", phase="action", mover=0, merged_extra=(), expect=None):
    merged = [
        {"name": "Infusion Grid", "abilityCost": "C",
         "abilityScript": {"create": [["Husk", "own", 4, 0]], "selfsac": True}},
        {"name": "Animus", "beginOwnTurnScript": {"receive": "CC"}},  # begin-turn red: NOT click red
        {"name": "Drone", "abilityScript": {"receive": "1"}},         # click gold: no red
    ]
    merged.extend(merged_extra)
    return {
        "expect": expect,
        "request": {
            "mergedDeck": merged,
            "gameState": {
                "phase": phase,
                "turn": mover,
                "whiteMana": white_mana,
                "blackMana": "",
                "table": table,
            },
        },
    }


def ig(owner=0, role="default", deadness="alive", ct=0, delay=0, name="Infusion Grid"):
    return {"cardName": name, "owner": owner, "role": role, "deadness": deadness,
            "constructionTime": ct, "delay": delay}


def test_red_pool_binds():
    # 4 ready IGs, but whiteMana RR -> feasible 2 (the owner-spec motivating example)
    case = make_case([ig(), ig(), ig(), ig()], white_mana="CC")
    assert feasible_max_for_case(case) == 2


def test_ready_ig_count_binds():
    # 1 ready IG, plenty of red
    case = make_case([ig()], white_mana="CCCC")
    assert feasible_max_for_case(case) == 1


def test_not_ready_instances_excluded():
    table = [
        ig(),                          # ready
        ig(ct=1),                      # under construction
        ig(role="assigned"),           # ability already used
        ig(role="sellable"),           # just-bought
        ig(deadness="dead"),           # dead
        ig(delay=1),                   # delayed
        ig(owner=1),                   # opponent's
    ]
    case = make_case(table, white_mana="CCCC")
    assert feasible_max_for_case(case) == 1


def test_zero_ready_igs_is_zero():
    case = make_case([ig(ct=1)], white_mana="CCCC")
    assert feasible_max_for_case(case) == 0


def test_click_producible_red_added():
    # Synthetic click-red producer (none exists in the real library; engine-definition parity):
    # 2 ready IGs, red pool 1, one ready producer with receive "CC" -> attainable 3 -> min = 2
    producer = {"cardName": "RedClicker", "owner": 0, "role": "default", "deadness": "alive",
                "constructionTime": 0, "delay": 0}
    case = make_case([ig(), ig(), producer], white_mana="C",
                     merged_extra=({"name": "RedClicker", "abilityScript": {"receive": "CC"}},))
    assert feasible_max_for_case(case) == 2
    # ...and an ASSIGNED producer contributes nothing: pool 1 binds via min(2, 1) = 1
    producer_used = dict(producer, role="assigned")
    case2 = make_case([ig(), ig(), producer_used], white_mana="C",
                      merged_extra=({"name": "RedClicker", "abilityScript": {"receive": "CC"}},))
    assert feasible_max_for_case(case2) == 1


def test_begin_turn_red_not_click_producible():
    # Animus (beginOwnTurnScript CC) must NOT add click-attainable red: pool C binds at 1
    animus = {"cardName": "Animus", "owner": 0, "role": "default", "deadness": "alive",
              "constructionTime": 0, "delay": 0}
    case = make_case([ig(), ig(), animus], white_mana="C")
    assert feasible_max_for_case(case) == 1


def test_codename_hotel_counts_as_ig():
    case = make_case([ig(name="Hotel")], white_mana="C")
    assert feasible_max_for_case(case) == 1


def test_non_action_phase_returns_unknown():
    case = make_case([ig()], phase="defense")
    assert feasible_max_for_case(case) is None


def test_expect_override_wins():
    # override beats both the phase guard and the computed value
    case = make_case([ig()], phase="defense", expect={"ig_click_count": 1, "ig_feasible_max": 3})
    assert feasible_max_for_case(case) == 3
    case2 = make_case([ig(), ig()], white_mana="CC", expect={"ig_feasible_max": 1})
    assert feasible_max_for_case(case2) == 1


def test_mover_is_black_uses_black_mana():
    table = [ig(owner=1), ig(owner=1)]
    case = make_case(table, mover=1)
    case["request"]["gameState"]["blackMana"] = "C"
    assert feasible_max_for_case(case) == 1


def test_real_ktink_case_feasible_two():
    """The curated real case: 2 ready IGs, whiteMana BBCCA (2 red) -> feasible 2; expect stays 1."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tactical_cases", "ktink_t9_ig.json")
    if not os.path.exists(path):
        import pytest
        pytest.skip("ktink_t9_ig.json not present")
    with open(path, encoding="utf-8") as f:
        case = json.load(f)
    assert feasible_max_for_case(case) == 2
    assert (case.get("expect") or {}).get("ig_click_count") == 1
