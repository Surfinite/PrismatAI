import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_eval import parse_tournament_stdout


# ---- Step 5: parse_tournament_stdout against the REAL HTML statsTable ----
# Captured 2026-06-03 from tests/Tournament_AB_5var_Smoke_2026-06-03_23-41-36.html
# (Prismata_Testing.exe, dave-master-jsonclean). Columns: Player, Score, Games, Wins, Loss, Draw,...
# (v4: the steam/matchup_clean.js anchor — and its parse_matchup_seatindep — were removed with
# the REJECT/REVIEW verdict; only the C++ tournament HTML statsTable parsing remains.)
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
        '<tr><td>OriginNet</td><td>0.4</td><td>100</td><td>35</td><td>55</td><td>10</td></tr>'
        '</table>'
    )
    res = parse_tournament_stdout(html, "x")
    assert res["CandNet"] == {"wins": 55, "draws": 10, "games": 100}
    assert res["OriginNet"] == {"wins": 35, "draws": 10, "games": 100}
