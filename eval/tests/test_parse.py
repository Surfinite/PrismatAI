import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_eval import parse_tournament_stdout, parse_matchup_seatindep


# ---- Step 5: parse_tournament_stdout against the REAL HTML statsTable ----
# Captured 2026-06-03 from tests/Tournament_AB_5var_Smoke_2026-06-03_23-41-36.html
# (Prismata_Testing.exe, dave-master-jsonclean). Columns: Player, Score, Games, Wins, Loss, Draw,...
REAL_STATS_HTML = (
    '<div id="statsTableDiv"><table cellpadding=2 border=1 rules=all '
    'style="font: 12px/1.5em Verdana" id="statsTable" class="tablesorter">\n'
    '<thead><th width="120">Player</th><th width="80">Score</th><th width="80">Games</th>'
    '<th width="80">Wins</th><th width="80">Loss</th><th width="80">Draw</th>'
    '<th width="80">Turns</th><th width="80">Turns/G</th><th width="80">MS/Turn</th>'
    '<th width="80">Max MS</th></thead>\n'
    '<tr><td>DSNN_Mixed35_5var_F1s</td><td>0.5</td><td>4</td><td>2</td><td>2</td><td>0</td>'
    '<td>77</td><td>19.25</td><td>955.429</td><td>1073</td></tr>\n'
    '<tr><td>DSNN_M35_1s_c03</td><td>0.5</td><td>4</td><td>2</td><td>2</td><td>0</td>'
    '<td>77</td><td>19.25</td><td>956.909</td><td>1071</td></tr>\n'
    '</table></div>\n'
)


def test_parse_tournament_html_statstable():
    res = parse_tournament_stdout(REAL_STATS_HTML, "AB_5var_Smoke")
    assert res == {
        "DSNN_Mixed35_5var_F1s": {"wins": 2, "draws": 0, "games": 4},
        "DSNN_M35_1s_c03":       {"wins": 2, "draws": 0, "games": 4},
    }


def test_parse_tournament_html_with_draws():
    # synthetic row with draws to confirm the Draw column maps to 'draws'
    html = (
        '<table id="statsTable">'
        '<tr><td>CandNet</td><td>0.6</td><td>100</td><td>55</td><td>35</td><td>10</td></tr>'
        '<tr><td>ParentNet</td><td>0.4</td><td>100</td><td>35</td><td>55</td><td>10</td></tr>'
        '</table>'
    )
    res = parse_tournament_stdout(html, "x")
    assert res["CandNet"] == {"wins": 55, "draws": 10, "games": 100}
    assert res["ParentNet"] == {"wins": 35, "draws": 10, "games": 100}


# ---- A7: parse_matchup_seatindep reads the seat-INDEPENDENT identity rate, NOT the seat tally ----
# REAL emitted format, verified 2026-06-11 against matchup_clean.js (labelWith + the [Parallel]
# tally printer): player names normalize to upper-case DAVEAI/STEAMAI, the per-side difficulty
# keeps its exact argv case, identities print as 'Player A [DAVEAI[RL_Eval]]'.
REAL_MATCHUP_STDERR = """\
[Parallel] ========== TALLY ==========
[Parallel] Games:    200 (4 workers)
[Parallel] White:    110 (55.0%)
[Parallel] Black:    86 (43.0%)
[Parallel] Draws:    4
[Parallel] Invalid:  0
[Parallel] Avg turns: 21
[Parallel] --- Pair Results (A=initially White, B=initially Black) ---
[Parallel] Player A [DAVEAI[RL_Eval]] sweeps (2-0): 30
[Parallel] Player B [STEAMAI[HardestAI]] sweeps (2-0): 24
[Parallel] Splits (1-1):  46
[Parallel] Invalid pairs:  0
[Parallel] --- Win Rates (seat-independent) ---
[Parallel] Player A [DAVEAI[RL_Eval]]: 53.9%
[Parallel] Player B [STEAMAI[HardestAI]]: 46.1%
[Parallel] ================================
"""


def test_parse_matchup_seatindep_picks_candidate_identity():
    # candidate label 'RL_Eval' (run_eval CANDIDATE_PLAYER default) must substring-match the
    # white identity 'Player A [DAVEAI[RL_Eval]]' -> 53.9%, NOT the 55.0% White seat tally.
    p, n, extra = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "RL_Eval", games=200)
    assert abs(p - 0.539) < 1e-9
    assert n == 200
    # steam-07: the seat tally yields the valid-game count + draw convention
    assert extra["valid_games"] == 200 and extra["draws"] == 4
    assert "draws count against BOTH" in extra["draw_convention"]


def test_parse_matchup_seatindep_picks_steam_identity():
    p, n, _ = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "STEAMAI[HardestAI]", games=200)
    assert abs(p - 0.461) < 1e-9
    assert n == 200


def test_parse_matchup_seatindep_not_the_white_seat():
    # the White seat tally is 55.0% but the candidate's seat-independent rate is 53.9%.
    p, _, _ = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "RL_Eval", games=200)
    assert p != 0.55


def test_parse_matchup_seatindep_label_is_case_sensitive():
    # exact-case contract: the injected difficulty is 'RL_Eval'; a wrong-case label must NOT match.
    p, _, _ = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "rl_eval", games=200)
    assert p is None


def test_parse_matchup_seatindep_serial_pair_path():
    # serial (--parallel 1) path emits the same labels with the [Pair] prefix.
    txt = (
        "[Pair] --- Win Rates (seat-independent) ---\n"
        "[Pair] Player A [DAVEAI[RL_Eval]]: 61.0%\n"
        "[Pair] Player B [STEAMAI[HardestAI]]: 39.0%\n"
        "[Pair] ================================\n"
    )
    p, n, extra = parse_matchup_seatindep(txt, "RL_Eval", games=128)
    assert abs(p - 0.61) < 1e-9 and n == 128
    assert extra == {}   # no seat tally in this snippet -> no valid-games correction


def test_parse_matchup_seatindep_invalid_games_shrink_n():
    # steam-07: matchup's printed rate is wins/validGames — with invalid games present the
    # CI's n must be the VALID count (White+Black+Draws), not the requested Games line.
    txt = (
        "[Parallel] Games:    200 (4 workers)\n"
        "[Parallel] White:    100 (54.3%)\n"
        "[Parallel] Black:    80 (43.5%)\n"
        "[Parallel] Draws:    4\n"
        "[Parallel] Invalid:  16\n"
        "[Parallel] --- Win Rates (seat-independent) ---\n"
        "[Parallel] Player A [DAVEAI[RL_Eval]]: 54.3%\n"
    )
    p, n, extra = parse_matchup_seatindep(txt, "RL_Eval", games=200)
    assert abs(p - 0.543) < 1e-9
    assert n == 184 and extra["valid_games"] == 184


def test_parse_matchup_seatindep_absent_block_returns_none():
    # no --player-switch -> no seat-independent block -> candidate rate is None.
    txt = "[Parallel] White: 70 (70.0%)\n[Parallel] Games: 100\n"
    p, n, _ = parse_matchup_seatindep(txt, "RL_Eval", games=100)
    assert p is None and n == 100


# F-08 regression: the PRE-FIX mis-wired anchor put the 2016 baseline in BOTH seats
# (--player SteamAI => playerBlack = playerWhite), so both identities were STEAMAI[HardestAI]
# and the candidate never played. That output must yield NO candidate parse (None), which
# build_manifest records as an error on the steam anchor (covered in test_run_eval_main).
OLD_MISWIRED_BOTH_SEATS_STDERR = """\
[Parallel] --- Win Rates (seat-independent) ---
[Parallel] Player A [STEAMAI[HardestAI]]: 51.0%
[Parallel] Player B [STEAMAI[HardestAI]]: 49.0%
[Parallel] ================================
"""


def test_parse_matchup_old_miswired_both_seats_yields_no_candidate():
    p, n, _ = parse_matchup_seatindep(OLD_MISWIRED_BOTH_SEATS_STDERR, "RL_Eval", games=200)
    assert p is None
    assert n == 200  # no Games line in the block -> falls back to the requested count
