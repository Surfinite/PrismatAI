"""Win-rate (draw = half a win) and 95% Wilson score interval — iid only.

This is the COMPLETE statistics surface of the RL eval harness. The C++ tournament's
HTML statsTable emits only aggregate Wins/Loss/Draw/Games per player — it does NOT emit
per-card-set scores, so per-set (clustered / colour-swap-paired) analysis is not possible
from the data we parse, and no sequential-testing machinery is wired anywhere.

(The former decisive / decisive_gate / clustered_ci helpers were dead code with zero live
callers that misled readers into thinking paired/sequential statistics existed — removed
2026-06-10 per the RL-loop audit.)
"""
import math

Z95 = 1.959963984540054


def win_rate(wins, draws, n):
    """Seat-independent win rate counting a draw as half a win."""
    if n <= 0:
        return 0.0
    return (wins + 0.5 * draws) / n


def wilson_ci(p, n, z=Z95):
    """95% Wilson score interval (iid) for a proportion p observed over n trials."""
    if n <= 0:
        return (0.0, 1.0)
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))
