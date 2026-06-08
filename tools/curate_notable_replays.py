"""Use Claude to curate the Discord-mined replay candidates.

Takes notable_replays.json (ranked list produced by find_notable_replays.py),
asks Claude Opus 4.7 to judge each entry for inclusion, write a spoiler-free
hook, and assign a category. Emits curated_replays.md + curated_replays.json.

Usage:
    python tools/curate_notable_replays.py \
        --input docs/notable-replays/notable_replays.json \
        --output-dir docs/notable-replays \
        --top-n 150
"""

import argparse
import json
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """You are curating a "notable replays" list for the Prismata strategy game community.

You will receive Discord-mined candidates: each is a replay code someone posted, plus the surrounding chat context (what they said, what the author said beforehand, replies, reactions). Your job is to judge each one and produce a clean curated list.

For EACH candidate, decide:

1. **include** (boolean): should this replay be in the curated "notable" list?
   - INCLUDE: genuine recommendations ("this game is crazy", "check this out"), famous matchups or tournament finals, interesting strategic discussions tied to the game, noteworthy plays referenced by multiple people, analysis posts where someone breaks down what happened.
   - EXCLUDE: joke/meme posts, replays mentioned as side-context (e.g., "I played this earlier, anyway..."), lists of tournament match codes dumped without commentary, replays where the discussion is off-topic or low-signal, spammy strings of codes, anything where the author is complaining or the tone is negative without insight.
   - When in doubt, lean EXCLUDE. The goal is a hand-picked list, not a comprehensive index.

2. **category** (one of):
   - "notable-game" — a single game flagged as interesting/fun/crazy
   - "tournament" — a tournament final, league match, or competitive set
   - "strategy-analysis" — someone breaks down the game mechanically
   - "famous-moment" — specific clutch/meme play the community remembers
   - "skip" — use this when include=false

3. **hook** (string, max 18 words): a spoiler-free one-liner that tells someone why they might want to watch, without revealing the outcome, the winning player, or specific decisive plays. Channel-flavor like "messy Apollo slugfest" or "blitz brawl down to the last unit" is great. Avoid naming specific units if they give away the game plan unless they're central to the hook.

4. **reason** (string, max 20 words): a brief justification of your include/exclude choice, for the human reviewer.

Output format: a single JSON object with one key "results", whose value is an array of objects in the SAME ORDER as the input, each with keys: code, include, category, hook, reason. No prose, no markdown, just the JSON."""


def build_user_prompt(candidates: list[dict]) -> str:
    trimmed = []
    for c in candidates:
        best = c["mentions"][0]
        trimmed.append({
            "code": c["code"],
            "score": c["best_score"],
            "channel": best["channel"],
            "author": best["author"],
            "timestamp": best["timestamp"][:10] if best.get("timestamp") else None,
            "reactions": {
                "positive": round(best["reactions"]["positive"], 1),
                "total": round(best["reactions"]["total"], 1),
                "breakdown": best["reactions"]["breakdown"][:6],
            },
            "enthusiasm_hits": best["enthusiasm_hits"],
            "distinct_discussants": best["distinct_discussants"],
            "content": best["content"][:500],
            "preface": [p["content"][:250] for p in best.get("preface", [])],
            "window": [
                {"author": w["author"], "text": w["content"][:250]}
                for w in best.get("window", [])[:6]
            ],
        })
    return (
        f"Judge these {len(trimmed)} candidates. Return the JSON described in the system prompt.\n\n"
        + json.dumps(trimmed, ensure_ascii=False, indent=1)
    )


def call_claude(client: anthropic.Anthropic, candidates: list[dict]) -> list[dict]:
    user_prompt = build_user_prompt(candidates)
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    # Strip any accidental markdown fences
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
        stripped = stripped.strip()
    data = json.loads(stripped)
    print(f"  Claude usage: input={response.usage.input_tokens} output={response.usage.output_tokens}")
    return data["results"]


def write_markdown(curated: list[dict], candidates_by_code: dict[str, dict], out_path: Path):
    order = {
        "famous-moment": 0,
        "strategy-analysis": 1,
        "notable-game": 2,
        "tournament": 3,
        "skip": 99,
    }
    included = [c for c in curated if c.get("include")]
    included.sort(key=lambda c: (order.get(c.get("category", "skip"), 50), -candidates_by_code[c["code"]]["best_score"]))

    from urllib.parse import quote
    lines = [
        "# Curated Notable Replays",
        "",
        f"Hand-picked from {len(curated)} Discord-mined candidates by Claude Opus 4.7. {len(included)} replays recommended.",
        "",
    ]
    current_cat = None
    for c in included:
        cat = c.get("category", "other")
        if cat != current_cat:
            lines.append(f"## {cat.replace('-', ' ').title()}")
            lines.append("")
            current_cat = cat
        cand = candidates_by_code[c["code"]]
        best = cand["mentions"][0]
        code = c["code"]
        url = f"https://prismata.live/replay/{quote(code, safe='-')}"
        date = (best["timestamp"] or "")[:10]
        lines.append(f"- **`{code}`** — {c['hook']}")
        lines.append(f"  [replay]({url}) · posted by {best['author']} in #{best['channel']} on {date} · score {cand['best_score']}")
        lines.append("")

    excluded = [c for c in curated if not c.get("include")]
    if excluded:
        lines.append("---")
        lines.append("")
        lines.append(f"## Excluded ({len(excluded)})")
        lines.append("")
        lines.append("<details><summary>Show reasons</summary>")
        lines.append("")
        for c in excluded:
            lines.append(f"- `{c['code']}` — {c.get('reason', '(no reason)')}")
        lines.append("")
        lines.append("</details>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("docs/notable-replays/notable_replays.json"))
    ap.add_argument("--output-dir", type=Path, default=Path("docs/notable-replays"))
    ap.add_argument("--top-n", type=int, default=150,
                    help="How many of the top-scored candidates to send to Claude.")
    ap.add_argument("--batch-size", type=int, default=50,
                    help="Candidates per API call (keeps output under max_tokens).")
    args = ap.parse_args()

    candidates = json.loads(args.input.read_text(encoding="utf-8"))[: args.top_n]
    candidates_by_code = {c["code"]: c for c in candidates}
    print(f"[curate] loaded {len(candidates)} candidates from {args.input}")

    client = anthropic.Anthropic()
    curated: list[dict] = []
    for i in range(0, len(candidates), args.batch_size):
        batch = candidates[i : i + args.batch_size]
        print(f"[curate] batch {i // args.batch_size + 1}: candidates {i + 1}-{i + len(batch)}")
        results = call_claude(client, batch)
        if len(results) != len(batch):
            print(f"  WARN: got {len(results)} results for {len(batch)} candidates")
        curated.extend(results)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem.replace("notable_replays", "curated_replays")
    json_path = args.output_dir / f"{stem}.json"
    md_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(curated, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(curated, candidates_by_code, md_path)

    included = sum(1 for c in curated if c.get("include"))
    print(f"[curate] {included}/{len(curated)} recommended")
    print(f"  wrote {json_path}")
    print(f"  wrote {md_path}")


if __name__ == "__main__":
    main()
