"""Win-rate (draw=0.5) and Wilson score interval (95%), plus decisive-vs-0.5 tests.

Provides four decision helpers for the RL self-play eval harness:

  * win_rate / wilson_ci  : point estimate (draw = half a win) + 95% Wilson interval.
  * decisive()            : naive "CI excludes 0.5" peeking test. Use for the FINAL
                            asymmetric GO signal (the family-wise ~10-12% Type-I from
                            peeking at 128/256/512 is tolerable for a one-way GO).
  * decisive_gate()  (A3) : STRICTER group-sequential boundary (Pocock constant-z) for
                            the candidate-vs-current-net PROMOTION gate, where a false
                            positive would poison the replay buffer.
  * clustered_ci()   (A4) : card-set-level (cluster) CI that respects the negative
                            within-pair correlation of the colour-swap design. This is
                            the statistically-correct interval for the paired pools;
                            the iid wilson_ci is the conservative fallback.
"""
import math
import statistics

Z95 = 1.959963984540054
# Pocock-style constant-z boundary for 3 looks (~nominal alpha' = 0.022 per look).
Z_POCOCK_3LOOK = 2.289


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


def decisive(wins, draws, n, boundary=0.5):
    """True iff the 95% iid Wilson CI excludes the boundary (default 0.5).

    Use for the FINAL asymmetric GO signal, NOT for the promotion gate (use
    decisive_gate for that — it controls the inflated peeking error rate)."""
    p = win_rate(wins, draws, n)
    lo, hi = wilson_ci(p, n)
    return lo > boundary or hi < boundary


def decisive_gate(wins, draws, n, boundary=0.5, final_look=False):
    """Stricter decision for the PROMOTION gate (candidate vs current net).

    Interim looks use the Pocock constant-z boundary (nominal alpha' ~ 0.022); the final
    look may use full 95% alpha. Use this for gating; use decisive() for the final
    asymmetric GO signal."""
    p = win_rate(wins, draws, n)
    z = Z95 if final_look else Z_POCOCK_3LOOK
    lo, hi = wilson_ci(p, n, z=z)
    return lo > boundary or hi < boundary


def clustered_ci(set_scores, z=Z95):
    """Cluster (card-set-level) CI for the paired colour-swap design.

    set_scores: list of per-card-set win-rate scores in [0,1] (each = the candidate's
    seat-independent score on one card set, draws=0.5). Returns (mean, lo, hi) using a
    normal interval on the across-set mean (SE = std/sqrt(k)). This respects the within-
    set colour-swap pairing that iid Wilson ignores."""
    k = len(set_scores)
    if k == 0:
        return (0.0, 0.0, 1.0)
    m = sum(set_scores) / k
    if k == 1:
        return (m, 0.0, 1.0)
    sd = statistics.stdev(set_scores)
    half = z * sd / (k ** 0.5)
    return (m, max(0.0, m - half), min(1.0, m + half))
