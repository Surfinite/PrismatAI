"""Win-rate (draw = half a win), 95% Wilson score interval (iid), and the paired
per-card-set CI (2026-06-13, rl-design-05).

The pooled iid Wilson interval is the VERDICT statistic. Since the A4 engine change the
tournament also emits a per-game rounds CSV (Tournament_<name>_<date>_rounds.csv), so the
eval design's intrinsic pairing — one card set per round, played in both seat orders —
is finally analyzable: paired_round_ci() computes a normal-approximation CI on the mean
per-round (= per-set) candidate score, which removes the between-set variance component
the pooled interval ignores. It is REPORTED alongside the Wilson CI (manifest key
"paired_ci"), never the verdict input, until validated against real runs.

(History: clustered/sequential helpers were removed 2026-06-10 as dead code when no
per-set scores existed; the A4 CSV re-opened the paired analysis — see the third audit's
rl-design-05/stats-05.)
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


def paired_round_ci(round_scores, z=Z95):
    """95% normal-approximation CI on the MEAN per-round candidate score.

    round_scores: one score per round/card set in [0,1] (e.g. 0, 0.5, 1 for a
    colour-swap pair: lost both, split, won both; draws contribute 0.25 per game).
    Treats rounds (sets) as the iid unit — the correct exchangeable unit under the
    paired design — so within-pair correlation cannot narrow the interval the way it
    silently does for the pooled per-game Wilson CI (stats-05).

    Normal approximation (z, not t): at the campaign's n_rounds (>= 64) the difference
    from a t interval is < 0.4% of the half-width; below ~30 rounds treat the interval
    as indicative only. Returns (0.0, 1.0) for fewer than 2 rounds.
    """
    n = len(round_scores)
    if n < 2:
        return (0.0, 1.0)
    mean = sum(round_scores) / n
    var = sum((s - mean) ** 2 for s in round_scores) / (n - 1)
    half = z * math.sqrt(var / n)
    return (max(0.0, mean - half), min(1.0, mean + half))
