"""Action-coverage metrics for the IG-optional axis -> merged into the eval manifest.
Self-play IG fire-rate from the C++ exporter's ig_legal/ig_fired stamps; argmax IG fire-rate +
root entropy from query_move.js (Task 10). RUNTIME DEFERRED until query_move.js exists."""
import argparse, glob, json, os, subprocess, math


def selfplay_ig_rate(jsonl_dir):
    legal = fired = 0
    for f in glob.glob(os.path.join(jsonl_dir, "*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if r.get("ig_legal"):
                legal += 1
                if r.get("ig_fired"):
                    fired += 1
    return {"ig_legal_turns": legal, "ig_fired": fired,
            "ig_fire_rate_selfplay": (fired / legal) if legal else None}


def argmax_ig_rate(dave_exe, weights, battery="eval/ig_battery"):
    legal = fired = 0
    ents = []
    for s in glob.glob(os.path.join(battery, "*.json")):
        out = subprocess.run(["node", "c:/libraries/PrismataAI/js_engine/query_move.js",
                              "--request", s, "--player", "RL_Eval",
                              "--weights", weights, "--dave-exe", dave_exe],
                             capture_output=True, text=True, timeout=120)
        resp = json.loads(out.stdout.strip().splitlines()[-1])
        legal += 1
        if any(c.get("_type") in ("inst", "inst shift") and c.get("_id") == json.load(open(s)).get("hotel_inst_id")
               for c in resp.get("aiclicks", [])):
            fired += 1
        v = resp.get("aivisits", [])
        if v:
            tot = float(sum(v))
            ents.append(-sum((x/tot)*math.log(x/tot) for x in v if x > 0))
    return {"ig_fire_rate_argmax": (fired / legal) if legal else None,
            "root_entropy_mean": (sum(ents)/len(ents)) if ents else None,
            "ig_legal_positions": legal}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selfplay-jsonl-dir", required=True)
    ap.add_argument("--dave-exe", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    with open(a.manifest) as f:
        m = json.load(f)
    m["action_coverage"] = {**selfplay_ig_rate(a.selfplay_jsonl_dir),
                            **argmax_ig_rate(a.dave_exe, a.weights)}
    with open(a.manifest, "w") as f:
        json.dump(m, f, indent=2)
    print("action_coverage ->", m["action_coverage"])


if __name__ == "__main__":
    main()
