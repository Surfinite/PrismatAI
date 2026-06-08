"""Scan Discord exports for replay codes, score them by community reaction signal.

Looks at every message containing a replay code, gathers reactions on that message,
the surrounding discussion (next N messages in the same channel within a time
window), and enthusiasm keywords. Scores each mention, aggregates per replay code,
and writes JSON + Markdown review lists.

Usage:
    python tools/find_notable_replays.py \
        --exports-dir c:/libraries/prismata-replay-parser/discord_exports_full \
        --output-dir docs/notable-replays \
        --top-n 100
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

# 5-5 replay code. Allowed chars: alnum + '+' + '@'. Disallow adjacent same-class
# chars to avoid matching inside a longer token. Real codes always contain at
# least one uppercase letter AND at least one digit — filtering on that kills
# English-phrase false positives like "skill-based" or "wombo-combo".
REPLAY_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9+@\-])([A-Za-z0-9+@]{5}-[A-Za-z0-9+@]{5})(?![A-Za-z0-9+@\-])"
)


def looks_like_real_code(code: str) -> bool:
    return bool(re.search(r"[A-Z]", code) and re.search(r"[0-9]", code))

# Reaction signal. Positive emojis/custom-emoji names we've seen in the community.
POSITIVE_REACTION_NAMES = {
    # Standard unicode (via .code field in export)
    "thumbsup", "fire", "100", "exploding_head", "mind_blown", "star",
    "trophy", "clap", "eyes", "heart", "heart_eyes", "star_struck",
    "ok_hand", "raised_hands", "muscle", "sparkles", "tada",
    "chart_with_upwards_trend", "crown",
    # Common community custom emoji (case-insensitive match below)
    "pog", "poggers", "pogchamp", "gg", "based", "chef", "chefkiss",
    "galaxy_brain", "bigbrain", "thinktank", "sicko", "gigachad",
    "hype", "kappa", "yeehaw",
}
NEGATIVE_REACTION_NAMES = {
    "thumbsdown", "cringe", "facepalm", "yikes", "sadge", "pepehands",
    "rip", "nothankyou",
}

# Enthusiasm keywords in surrounding discussion. Word-boundary matched, lowercase.
ENTHUSIASM_WORDS = {
    "nice", "cool", "sick", "insane", "amazing", "crazy", "clean", "wild",
    "wow", "omg", "holy", "legendary", "epic", "beautiful", "brilliant",
    "incredible", "nuts", "awesome", "wonderful", "fantastic", "mindblown",
    "mindblowing", "godlike", "broken", "clutch", "clever", "impressive",
    "masterclass", "mustwatch", "hype", "crispy", "nasty", "filthy",
    "disgusting", "gigabrained", "bigbrain", "galaxybrain", "pog", "poggers",
}
ENTHUSIASM_PHRASES = [
    "must watch", "must-watch", "cool game", "great game", "good game",
    "crazy game", "best game", "amazing game", "wild game",
    "holy shit", "no way", "oh my god", "check this out", "what a game",
    "banger", "instant classic",
]

# Messages to look ahead after the replay post, and time window.
LOOKAHEAD_MESSAGES = 12
LOOKAHEAD_MINUTES = 45
# Lookbehind: include the poster's own recent messages as preface context
# (they may introduce the replay with relevant framing the LLM should see).
LOOKBEHIND_MESSAGES = 5
LOOKBEHIND_SECONDS = 120


def parse_ts(ts: str) -> datetime:
    # Discord export format: "2018-01-16T05:43:52.302+00:00"
    # Python 3.11+ handles this directly; be defensive on older Pythons.
    return datetime.fromisoformat(ts)


def iter_messages(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    channel = data.get("channel", {}).get("name", path.stem)
    for msg in data.get("messages", []):
        yield channel, msg


def score_reactions(reactions):
    pos = neg = total = 0
    breakdown = []
    for r in reactions or []:
        emoji = r.get("emoji", {}) or {}
        name = (emoji.get("code") or emoji.get("name") or "").lower()
        count = int(r.get("count", 0))
        # Regional-indicator emoji are single letters — people spell out words
        # by stacking them. They're not endorsements; don't count in totals at all.
        if name.startswith("regional_indicator"):
            continue
        total += count
        if name in POSITIVE_REACTION_NAMES or any(p in name for p in ("pog", "hype", "gg", "brain", "chef", "fire")):
            pos += count
        elif name in NEGATIVE_REACTION_NAMES or "cringe" in name or "sad" in name:
            neg += count
        breakdown.append({"name": name, "count": count})
    return {"positive": pos, "negative": neg, "total": total, "breakdown": breakdown}


def count_enthusiasm(text: str) -> int:
    if not text:
        return 0
    low = text.lower()
    hits = 0
    # Word-boundary single words
    for word in ENTHUSIASM_WORDS:
        hits += len(re.findall(rf"\b{re.escape(word)}\b", low))
    for phrase in ENTHUSIASM_PHRASES:
        if phrase in low:
            hits += 1
    return hits


def replay_url(code: str) -> str:
    return f"https://prismata.live/replay/{quote(code, safe='-')}"


def collect_mentions(exports_dir: Path, since_dt: datetime | None = None):
    """Yield one record per replay-code mention."""
    mentions = []
    for path in sorted(exports_dir.glob("*.json")):
        messages = list(iter_messages(path))
        if not messages:
            continue
        # Pre-parse timestamps once
        parsed = []
        for ch, m in messages:
            try:
                ts = parse_ts(m["timestamp"])
            except Exception:
                ts = None
            parsed.append((ch, m, ts))

        for i, (channel, msg, ts) in enumerate(parsed):
            if since_dt and ts and ts < since_dt:
                continue
            content = msg.get("content") or ""
            codes = [c for c in REPLAY_CODE_RE.findall(content) if looks_like_real_code(c)]
            if not codes:
                continue
            unique_codes = list(dict.fromkeys(codes))
            author = (msg.get("author") or {}).get("nickname") or (msg.get("author") or {}).get("name") or "?"

            # Lookbehind: the poster's own preface messages within LOOKBEHIND_SECONDS.
            preface = []
            behind_cutoff = ts - timedelta(seconds=LOOKBEHIND_SECONDS) if ts else None
            for j in range(i - 1, max(-1, i - 1 - LOOKBEHIND_MESSAGES), -1):
                _, m0, ts0 = parsed[j]
                a0 = (m0.get("author") or {}).get("nickname") or (m0.get("author") or {}).get("name") or "?"
                if a0 != author:
                    break
                if behind_cutoff and ts0 and ts0 < behind_cutoff:
                    break
                preface.append(m0)
            preface.reverse()

            # Gather lookahead window: same channel, next N messages within time window
            window_end = ts + timedelta(minutes=LOOKAHEAD_MINUTES) if ts else None
            window = []
            for j in range(i + 1, min(i + 1 + LOOKAHEAD_MESSAGES, len(parsed))):
                _, m2, ts2 = parsed[j]
                if window_end and ts2 and ts2 > window_end:
                    break
                window.append(m2)

            reactions = score_reactions(msg.get("reactions"))
            enthusiasm = count_enthusiasm(content)
            for m0 in preface:
                enthusiasm += count_enthusiasm(m0.get("content") or "")
            for m2 in window:
                enthusiasm += count_enthusiasm(m2.get("content") or "")
                # Reactions on discussion messages count half
                r2 = score_reactions(m2.get("reactions"))
                reactions["positive"] += r2["positive"] * 0.5
                reactions["total"] += r2["total"] * 0.5

            distinct_discussants = {
                ((m2.get("author") or {}).get("nickname") or (m2.get("author") or {}).get("name") or "?")
                for m2 in window
            }
            distinct_discussants.discard(author)

            for code in unique_codes:
                mentions.append({
                    "code": code,
                    "channel": channel,
                    "author": author,
                    "timestamp": msg.get("timestamp"),
                    "message_id": msg.get("id"),
                    "content": content.strip(),
                    "reactions": reactions,
                    "enthusiasm_hits": enthusiasm,
                    "discussion_messages": len(window),
                    "distinct_discussants": sorted(distinct_discussants),
                    "preface": [
                        {
                            "timestamp": m0.get("timestamp"),
                            "content": (m0.get("content") or "").strip(),
                        }
                        for m0 in preface
                        if (m0.get("content") or "").strip()
                    ],
                    "window": [
                        {
                            "author": ((m2.get("author") or {}).get("nickname")
                                       or (m2.get("author") or {}).get("name") or "?"),
                            "timestamp": m2.get("timestamp"),
                            "content": (m2.get("content") or "").strip(),
                        }
                        for m2 in window
                        if (m2.get("content") or "").strip()
                    ],
                })
    return mentions


def score_mention(m: dict) -> float:
    r = m["reactions"]
    return (
        3.0 * r["positive"]
        + 0.5 * max(0, r["total"] - r["positive"] - r["negative"])
        - 2.0 * r["negative"]
        + 1.2 * m["enthusiasm_hits"]
        + 0.4 * len(m["distinct_discussants"])
        + 0.15 * m["discussion_messages"]
    )


def aggregate_by_code(mentions):
    by_code = defaultdict(list)
    for m in mentions:
        by_code[m["code"]].append(m)
    results = []
    for code, items in by_code.items():
        items.sort(key=score_mention, reverse=True)
        total_score = sum(score_mention(it) for it in items)
        results.append({
            "code": code,
            "url": replay_url(code),
            "mention_count": len(items),
            "total_score": round(total_score, 2),
            "best_score": round(score_mention(items[0]), 2),
            "mentions": items,
        })
    results.sort(key=lambda r: (r["best_score"], r["total_score"]), reverse=True)
    return results


def write_markdown(results, out_path: Path, top_n: int):
    lines = ["# Notable Replays — Discord-Mined Candidates", ""]
    lines.append(f"Generated from {len(results)} unique replay codes mentioned in Discord. Top {min(top_n, len(results))} shown, sorted by best-mention score.\n")
    lines.append("**Score components:** `3*positive_reactions + 0.5*other_reactions + 1.2*enthusiasm_keywords + 0.4*distinct_discussants + 0.15*discussion_messages - 2*negative_reactions`\n")
    for rank, r in enumerate(results[:top_n], 1):
        best = r["mentions"][0]
        lines.append(f"## {rank}. `{r['code']}` — score {r['best_score']} ({r['mention_count']} mention(s))")
        lines.append(f"[replay]({r['url']}) — posted by **{best['author']}** in #{best['channel']} on {best['timestamp']}")
        lines.append("")
        rx = best["reactions"]
        if rx["total"]:
            emoji_summary = ", ".join(f"{b['name']}×{b['count']}" for b in rx["breakdown"][:6])
            lines.append(f"**Reactions:** {emoji_summary} (pos={rx['positive']:.1f}, neg={rx['negative']:.1f})")
        if best["enthusiasm_hits"]:
            lines.append(f"**Enthusiasm keywords:** {best['enthusiasm_hits']} hit(s)")
        if best["distinct_discussants"]:
            lines.append(f"**Discussants:** {', '.join(best['distinct_discussants'])}")
        lines.append("")
        if best.get("preface"):
            lines.append("Preface (same author, <2 min prior):")
            for p in best["preface"]:
                snippet = p["content"].replace("\n", " ")[:200]
                lines.append(f"- {snippet}")
            lines.append("")
        lines.append(f"> {best['content'][:400]}")
        if best["window"]:
            lines.append("")
            lines.append("Follow-up (first 4):")
            for w in best["window"][:4]:
                snippet = w["content"].replace("\n", " ")[:200]
                lines.append(f"- **{w['author']}:** {snippet}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exports-dir", type=Path,
                    default=Path("c:/libraries/prismata-replay-parser/discord_exports_full"))
    ap.add_argument("--output-dir", type=Path, default=Path("docs/notable-replays"))
    ap.add_argument("--top-n", type=int, default=100)
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="Drop mentions with best_score below this before writing.")
    ap.add_argument("--since", type=str, default=None,
                    help="Only keep mentions posted on or after this date (YYYY-MM-DD). "
                         "Output filenames get a _since-YYYY-MM-DD suffix.")
    args = ap.parse_args()

    since_dt = None
    suffix = ""
    if args.since:
        since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        suffix = f"_since-{args.since}"

    if not args.exports_dir.is_dir():
        raise SystemExit(f"Exports dir not found: {args.exports_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[find_notable_replays] scanning {args.exports_dir}"
          + (f" (since {args.since})" if since_dt else ""))
    mentions = collect_mentions(args.exports_dir, since_dt=since_dt)
    print(f"  found {len(mentions)} code mentions")
    results = aggregate_by_code(mentions)
    print(f"  {len(results)} unique replay codes")
    results = [r for r in results if r["best_score"] >= args.min_score]
    print(f"  {len(results)} after min-score {args.min_score}")

    json_path = args.output_dir / f"notable_replays{suffix}.json"
    md_path = args.output_dir / f"notable_replays{suffix}.md"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    write_markdown(results, md_path, args.top_n)
    print(f"  wrote {json_path}")
    print(f"  wrote {md_path}")


if __name__ == "__main__":
    main()
