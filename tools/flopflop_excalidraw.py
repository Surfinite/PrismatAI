"""Generate flopflop Excalidraw stats dashboard.

Layout mirrors spiritfryer_stats.excalidraw: 1350px wide, dark header,
6 KPI cards, sections for rating/opponents/units/activity.
"""
import json, uuid, random

W = 1350
CHAR_W = 0.62  # Helvetica char-width ratio
elements = []

def _id():
    return str(uuid.uuid4())[:8]

def rect(x, y, w, h, fill="#ffffff", stroke="#e0e0e0", radius=0, opacity=100):
    elements.append({
        "type": "rectangle", "id": _id(), "x": x, "y": y,
        "width": w, "height": h, "angle": 0, "strokeColor": stroke,
        "backgroundColor": fill, "fillStyle": "solid", "strokeWidth": 1,
        "roughness": 0, "opacity": opacity, "groupIds": [], "roundness": {"type": 3} if radius else None,
        "seed": random.randint(1, 999999), "version": 1, "isDeleted": False,
        "boundElements": None, "updated": 1, "link": None, "locked": False,
    })

def text(x, y, txt, size=14, color="#333333", bold=False, align="left", width=None):
    if width is None:
        width = max(len(line) for line in txt.split("\n")) * size * CHAR_W + 20
    elements.append({
        "type": "text", "id": _id(), "x": x, "y": y,
        "width": width, "height": size * 1.4 * txt.count("\n") + size * 1.4,
        "angle": 0, "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "roughness": 0, "opacity": 100,
        "groupIds": [], "roundness": None, "seed": random.randint(1, 999999),
        "version": 1, "isDeleted": False, "boundElements": None, "updated": 1,
        "link": None, "locked": False,
        "text": txt, "fontSize": size, "fontFamily": 2,
        "textAlign": align, "verticalAlign": "top",
        "containerId": None, "originalText": txt, "autoResize": True,
    })

def line(x1, y1, x2, y2, color="#e0e0e0", width=1):
    elements.append({
        "type": "line", "id": _id(), "x": x1, "y": y1,
        "width": abs(x2 - x1), "height": abs(y2 - y1), "angle": 0,
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": width, "roughness": 0, "opacity": 100,
        "groupIds": [], "roundness": None, "seed": random.randint(1, 999999),
        "version": 1, "isDeleted": False, "boundElements": None, "updated": 1,
        "link": None, "locked": False,
        "points": [[0, 0], [x2 - x1, y2 - y1]],
        "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
        "startArrowhead": None, "endArrowhead": None,
    })

def ellipse(x, y, w, h, fill="#ffffff", stroke="#e0e0e0"):
    elements.append({
        "type": "ellipse", "id": _id(), "x": x, "y": y,
        "width": w, "height": h, "angle": 0, "strokeColor": stroke,
        "backgroundColor": fill, "fillStyle": "solid", "strokeWidth": 1,
        "roughness": 0, "opacity": 100, "groupIds": [], "roundness": {"type": 2},
        "seed": random.randint(1, 999999), "version": 1, "isDeleted": False,
        "boundElements": None, "updated": 1, "link": None, "locked": False,
    })

# ======= HEADER =======
rect(0, 0, W, 80, fill="#1b1b2f", stroke="#1b1b2f")
text(30, 18, "FLOPFLOP", size=36, color="#ffffff", bold=True)
text(W - 450, 22, "Prismata Stats Profile", size=28, color="#a0a0c0")
text(W - 450, 55, "5,563 games  |  Aug 2020 - Feb 2026", size=13, color="#707090")

# ======= KPI CARDS =======
kpi_y = 105
kpi_h = 85
kpi_w = 185
kpi_gap = 22
kpis = [
    ("5,563", "Rated Games", "#d0bfff"),
    ("2214", "Peak Rating", "#a5d8ff"),
    ("50.9%", "Win Rate", "#b2f2bb"),
    ("221 hrs", "Play Time", "#ffec99"),
    ("15", "Best Streak", "#ffc9c9"),
    ("107", "Opponents", "#e5dbff"),
]
kpi_x = 65
for val, label, color in kpis:
    rect(kpi_x, kpi_y, kpi_w, kpi_h, fill=color, stroke=color, radius=8)
    text(kpi_x + 10, kpi_y + 12, val, size=30, color="#1b1b2f", bold=True)
    text(kpi_x + 10, kpi_y + 55, label, size=13, color="#555555")
    kpi_x += kpi_w + kpi_gap

# ======= RATING SECTION =======
sec_y = 265
rect(0, sec_y, 780, 240, fill="#fafafa", stroke="#e8e8e8")
text(20, sec_y + 12, "Rating Trajectory", size=18, color="#1b1b2f", bold=True)
line(20, sec_y + 38, 760, sec_y + 38, color="#e0e0e0")

# Quarterly data
quarters = [
    ("2020-Q3", 2013, 2074, 93), ("2021-Q1", 2106, 2135, 27),
    ("2022-Q1", 2011, 2124, 100), ("2022-Q4", 2027, 2162, 25),
    ("2023-Q1", 2087, 2214, 201), ("2023-Q4", 2077, 2164, 248),
    ("2024-Q1", 2107, 2183, 1006), ("2024-Q2", 2090, 2174, 523),
    ("2024-Q3", 2067, 2168, 477), ("2024-Q4", 2106, 2192, 587),
    ("2025-Q1", 2103, 2171, 639), ("2025-Q2", 2053, 2130, 349),
    ("2025-Q3", 2080, 2130, 328), ("2025-Q4", 2099, 2181, 343),
    ("2026-Q1", 2103, 2168, 519),
]

# Draw mini chart
chart_x, chart_y, chart_w, chart_h = 30, sec_y + 50, 720, 120
min_r, max_r = 1900, 2250
for i, (q, avg, peak, n) in enumerate(quarters):
    bx = chart_x + i * (chart_w // len(quarters))
    # Peak dot
    py = chart_y + chart_h - (peak - min_r) / (max_r - min_r) * chart_h
    ellipse(bx + 8, py - 3, 6, 6, fill="#6c5ce7", stroke="#6c5ce7")
    # Avg dot
    ay = chart_y + chart_h - (avg - min_r) / (max_r - min_r) * chart_h
    ellipse(bx + 8, ay - 3, 6, 6, fill="#00b894", stroke="#00b894")
    # Label
    if i % 3 == 0:
        text(bx - 2, chart_y + chart_h + 5, q, size=9, color="#999999")

# Legend
text(30, sec_y + chart_h + 70, "● Peak  ● Avg", size=11, color="#555555")
text(200, sec_y + 50, "Peak: 2,214  |  Current: ~2,128  |  Career avg: 2,088", size=13, color="#555555")
text(200, sec_y + 70, "First 100 games: 2,016 → Last 100: 2,132 (+116)", size=12, color="#777777")

# Rating right-side summary
rect(800, sec_y, W - 800, 240, fill="#f0f0ff", stroke="#e0e0e8")
text(815, sec_y + 12, "Rating Tiers", size=16, color="#1b1b2f", bold=True)
line(815, sec_y + 36, W - 20, sec_y + 36, color="#d0d0e0")
tier_data = [
    ("vs Under 1800", "87.0%", 228, 262),
    ("vs 1800-1999", "69.3%", 912, 1316),
    ("vs 2000-2199", "46.3%", 1361, 2938),
    ("vs 2200-2399", "31.4%", 323, 1029),
]
for i, (tier, wr, w_ct, total) in enumerate(tier_data):
    ty = sec_y + 48 + i * 28
    text(815, ty, tier, size=13, color="#555555")
    text(980, ty, wr, size=13, color="#1b1b2f", bold=True)
    text(1040, ty, f"({w_ct}/{total})", size=11, color="#999999")

# Position
text(815, sec_y + 168, "P1: 49.5%  |  P2: 52.3%", size=13, color="#555555")
text(815, sec_y + 190, "Up: 32.6% | Even: 49.4% | Down: 70.9%", size=11, color="#777777")
text(815, sec_y + 210, "Career: +116 rating points", size=12, color="#00b894")

# ======= OPPONENTS SECTION =======
opp_y = sec_y + 260
rect(0, opp_y, W, 310, fill="#ffffff", stroke="#e8e8e8")
text(20, opp_y + 12, "Top Opponents", size=18, color="#1b1b2f", bold=True)
line(20, opp_y + 38, W - 20, opp_y + 38, color="#e0e0e0")

opponents = [
    ("Homeless", 1440, "44%", 2132),
    ("Kolento", 354, "33%", 2242),
    ("Punf", 326, "28%", 2238),
    ("chole", 212, "42%", 2142),
    ("Weill", 206, "60%", 2044),
    ("AlexanderJohan", 204, "62%", 1952),
    ("powfordamage", 169, "72%", 1920),
    ("jamberine", 164, "31%", 2216),
    ("TheSystem", 157, "64%", 1970),
    ("307th", 147, "37%", 2211),
    ("Hey", 137, "61%", 1989),
    ("Yujiri", 109, "59%", 2006),
]

# Two columns
col_w = 640
for i, (name, games, wr, avg_r) in enumerate(opponents):
    col = i // 6
    row = i % 6
    ox = 30 + col * col_w
    oy = opp_y + 50 + row * 40

    # WR bar background
    rect(ox, oy, 260, 26, fill="#f5f5f5", stroke="#e8e8e8", radius=4)
    # WR bar fill
    wr_val = int(wr.replace('%', ''))
    bar_w = int(260 * wr_val / 100)
    bar_color = "#b2f2bb" if wr_val >= 50 else "#ffc9c9" if wr_val < 40 else "#ffec99"
    rect(ox, oy, bar_w, 26, fill=bar_color, stroke=bar_color, radius=4)
    text(ox + 6, oy + 4, f"{name}", size=13, color="#1b1b2f", bold=True)
    text(ox + 175, oy + 4, f"{wr}", size=13, color="#333333", bold=True)
    text(ox + 210, oy + 6, f"({games}g)", size=10, color="#777777")
    text(ox + 280, oy + 4, f"~{avg_r}", size=12, color="#999999")

# Notable scalps box
text(30, opp_y + 300 - 28, "Notable: Beat Kolento (2338), Wonderboat (2336), 8-2 vs Elyot", size=12, color="#6c5ce7")

# ======= HEAD-TO-HEAD vs KNOWN PLAYERS =======
h2h_y = opp_y + 320
rect(0, h2h_y, W, 200, fill="#fafafa", stroke="#e8e8e8")
text(20, h2h_y + 12, "Head-to-Head vs Notable Players", size=18, color="#1b1b2f", bold=True)
line(20, h2h_y + 38, W - 20, h2h_y + 38, color="#e0e0e0")

h2h = [
    ("Homeless", "635-804", "44%"),
    ("Kolento", "117-236", "33%"),
    ("jamberine", "51-112", "31%"),
    ("coffeeyay", "29-39", "43%"),
    ("Msven", "32-68", "32%"),
    ("307th", "54-91", "37%"),
    ("SpiritFryer", "53-47", "53%"),
    ("Weill", "123-81", "60%"),
    ("chole", "89-123", "42%"),
    ("TheSystem", "100-57", "64%"),
    ("Elyot", "8-2", "80%"),
    ("Surfinite", "31-5", "86%"),
    ("Wonderboat", "13-32", "29%"),
    ("Steel", "24-31", "44%"),
]
cols = 3
col_w = (W - 60) // cols
for i, (name, record, wr) in enumerate(h2h):
    col = i % cols
    row = i // cols
    hx = 30 + col * col_w
    hy = h2h_y + 50 + row * 30
    wr_val = int(wr.replace('%', ''))
    wr_color = "#00b894" if wr_val >= 50 else "#e17055" if wr_val < 40 else "#fdcb6e"
    text(hx, hy, name, size=13, color="#333333")
    text(hx + 130, hy, record, size=13, color="#555555")
    text(hx + 220, hy, wr, size=14, color=wr_color, bold=True)

# ======= UNITS SECTION =======
unit_y = h2h_y + 210
rect(0, unit_y, W // 2, 290, fill="#ffffff", stroke="#e8e8e8")
text(20, unit_y + 12, "Best Units (min 15 games)", size=16, color="#1b1b2f", bold=True)
line(20, unit_y + 36, W // 2 - 20, unit_y + 36, color="#e0e0e0")

best_units = [
    ("Tatsu Nullifier", "62.5%", 104),
    ("Scorchilla", "56.8%", 398),
    ("Tyranno Smorcus", "54.8%", 354),
    ("Plasmafier", "54.6%", 854),
    ("Galvani Drone", "54.2%", 485),
    ("Frost Brooder", "53.8%", 504),
    ("Trinity Drone", "53.7%", 464),
    ("Polywall", "53.6%", 504),
    ("Mega Drone", "53.5%", 503),
    ("Vivid Drone", "53.5%", 492),
]
for i, (unit, wr, n) in enumerate(best_units):
    uy = unit_y + 46 + i * 23
    text(30, uy, unit, size=12, color="#333333")
    text(200, uy, wr, size=12, color="#00b894", bold=True)
    text(260, uy, f"({n})", size=10, color="#999999")

rect(W // 2, unit_y, W // 2, 290, fill="#fff8f8", stroke="#e8e8e8")
text(W // 2 + 20, unit_y + 12, "Worst Units (min 15 games)", size=16, color="#1b1b2f", bold=True)
line(W // 2 + 20, unit_y + 36, W - 20, unit_y + 36, color="#e0e0e0")

worst_units = [
    ("Valkyrion", "43.4%", 159),
    ("Oxide Mixer", "45.1%", 517),
    ("Redeemer", "46.1%", 477),
    ("Nitrocybe", "46.6%", 487),
    ("Xaetron", "46.6%", 506),
    ("Gaussite Symbiote", "46.9%", 467),
    ("Shiver Yeti", "46.9%", 501),
    ("Antima Comet", "47.1%", 501),
    ("Nivo Charge", "47.2%", 504),
    ("Lancetooth", "47.3%", 188),
]
for i, (unit, wr, n) in enumerate(worst_units):
    uy = unit_y + 46 + i * 23
    text(W // 2 + 30, uy, unit, size=12, color="#333333")
    text(W // 2 + 200, uy, wr, size=12, color="#e17055", bold=True)
    text(W // 2 + 260, uy, f"({n})", size=10, color="#999999")

# ======= ACTIVITY SECTION =======
act_y = unit_y + 300
rect(0, act_y, W, 250, fill="#fafafa", stroke="#e8e8e8")
text(20, act_y + 12, "Activity & Patterns", size=18, color="#1b1b2f", bold=True)
line(20, act_y + 38, W - 20, act_y + 38, color="#e0e0e0")

# Year bars
years = [(2020, 97), (2021, 33), (2022, 176), (2023, 486), (2024, 2593), (2025, 1659), (2026, 519)]
max_games = 2593
bar_area_x = 30
bar_area_y = act_y + 50
bar_h = 22
for i, (year, count) in enumerate(years):
    by = bar_area_y + i * 28
    bw = int(350 * count / max_games)
    color = "#6c5ce7" if year == 2024 else "#a29bfe"
    rect(bar_area_x + 50, by, bw, bar_h, fill=color, stroke=color, radius=4)
    text(bar_area_x, by + 3, str(year), size=13, color="#555555")
    text(bar_area_x + 55 + bw, by + 3, str(count), size=12, color="#333333")

# Activity stats right side
ast_x = 480
text(ast_x, act_y + 50, "Sessions: 752  |  Avg: 7.4 games/session", size=13, color="#555555")
text(ast_x, act_y + 75, "Longest session: 64 games (Sep 24, 2025, ~3.8 hrs)", size=12, color="#555555")
text(ast_x, act_y + 100, "Active days: 542  |  Avg: 10.3 games/day", size=13, color="#555555")
text(ast_x, act_y + 125, "Peak day: 79 games (Sep 24, 2025)", size=12, color="#555555")
text(ast_x, act_y + 155, "Evening (18-24): 43.9%  |  Night (0-6): 37.7%", size=13, color="#555555")
text(ast_x, act_y + 180, "Weekday spread: very even (12.8-16.8%)", size=12, color="#777777")

# Streaks
text(ast_x, act_y + 210, "Best streak: 15W  |  Worst streak: 14L", size=13, color="#555555")

# ======= GAME STYLE SECTION =======
style_y = act_y + 260
rect(0, style_y, W, 120, fill="#ffffff", stroke="#e8e8e8")
text(20, style_y + 12, "Play Style Indicators", size=18, color="#1b1b2f", bold=True)
line(20, style_y + 38, W - 20, style_y + 38, color="#e0e0e0")

style_items = [
    "Avg game: 10.0 min  |  Night owl (81.6% of games 6PM-6AM UTC)",
    "Better in longer games: 51.7% WR at 7-12min vs 42.4% under 3min",
    "Top units: Tatsu Nullifier, Scorchilla, Tyranno Smorcus — aggressive disruption specialist",
    "131 unique units seen  |  Biggest upset: beat jamberine outrated by 335 points",
]
for i, item in enumerate(style_items):
    text(30, style_y + 48 + i * 18, item, size=12, color="#555555")

# ======= FOOTER =======
foot_y = style_y + 130
rect(0, foot_y, W, 40, fill="#1b1b2f", stroke="#1b1b2f")
text(30, foot_y + 10, "Generated from 5,563 rated games  |  Discord: No messages  |  Data: expert_replays.json + FlopFlopCodes.txt", size=12, color="#707090")

# ======= WRITE OUTPUT =======
doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "flopflop_excalidraw.py",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}

out_path = "tools/flopflop_stats.excalidraw"
with open(out_path, "w") as f:
    json.dump(doc, f)
print(f"Wrote {len(elements)} elements to {out_path}")
