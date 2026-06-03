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
# Line shapes per the harness spec + memory (DSNN vs SteamAI ~46.1%).
REAL_MATCHUP_STDERR = """\
[Parallel] White: 110 (55.0%)
[Parallel] Black: 86 (43.0%)
[Parallel] Draws: 4 (2.0%)
[Parallel] Games: 200
[Parallel] --- Win Rates (seat-independent) ---
[Parallel] DaveAI(RL_Eval): 53.9%
[Parallel] SteamAI(HardestAI): 46.1%
==========================================
"""


def test_parse_matchup_seatindep_picks_candidate_identity():
    # candidate is the DaveAI(RL_Eval) identity; must get 53.9%, NOT the 55.0% White seat tally.
    p, n = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "DaveAI(RL_Eval)", games=200)
    assert abs(p - 0.539) < 1e-9
    assert n == 200


def test_parse_matchup_seatindep_picks_steam_identity():
    p, n = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "SteamAI(HardestAI)", games=200)
    assert abs(p - 0.461) < 1e-9
    assert n == 200


def test_parse_matchup_seatindep_not_the_white_seat():
    # the White seat tally is 55.0% but the candidate's seat-independent rate is 53.9%.
    p, _ = parse_matchup_seatindep(REAL_MATCHUP_STDERR, "DaveAI(RL_Eval)", games=200)
    assert p != 0.55


def test_parse_matchup_seatindep_serial_pair_path():
    # serial path uses [Pair] instead of [Parallel].
    txt = (
        "[Pair] --- Win Rates (seat-independent) ---\n"
        "[Pair] DaveAI(RL_Eval): 61.0%\n"
        "[Pair] SteamAI(HardestAI): 39.0%\n"
    )
    p, n = parse_matchup_seatindep(txt, "DaveAI(RL_Eval)", games=128)
    assert abs(p - 0.61) < 1e-9 and n == 128


def test_parse_matchup_seatindep_absent_block_returns_none():
    # no --player-switch -> no seat-independent block -> candidate rate is None.
    txt = "[Parallel] White: 70 (70.0%)\n[Parallel] Games: 100\n"
    p, n = parse_matchup_seatindep(txt, "DaveAI(RL_Eval)", games=100)
    assert p is None and n == 100
