"""Net-side IG-click argmax per ig_battery state, merged with the human side (eval/_ig_human.json)
from ig_human_clicks.js -> the human-vs-net IG comparison table.

For each ig_battery/*.json (a query_move request), run query_move with the IG-subset iterator +
v221 and count the net's argmax IG self-sac clicks (tactical_suite.count_ig_clicks). Then line it
up against what the human actually did from the same decision point.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tactical_suite import query, count_ig_clicks  # noqa: E402

ROOT_ITER = "HardIterator_5var_IGsubset_Root"
MOVE_ITER = "HardIterator_5var"
WEIGHTS = "neural_weights_mixed_v221.bin"
DAVE_EXE = r"c:/libraries/PrismataAI-dave-master/bin/PrismataAI.exe"
TIME_LIMIT = 3000


def main():
    battery = os.path.join(HERE, "ig_battery")
    human = {r["dump"].replace(".txt", ""): r
             for r in json.load(open(os.path.join(HERE, "_ig_human.json")))}

    rows = []
    files = sorted(glob.glob(os.path.join(battery, "*.json")))
    for i, fp in enumerate(files):
        name = os.path.splitext(os.path.basename(fp))[0]
        if name == "ktink_t9":
            continue  # smoke fixture, no human-replay row
        case = {"request": json.load(open(fp, encoding="utf-8-sig"))}
        try:
            resp = query(case, "RL_Eval", WEIGHTS, DAVE_EXE, TIME_LIMIT, 90000, ROOT_ITER, MOVE_ITER)
            net_ig = count_ig_clicks(resp)
        except Exception as e:
            print(f"  {name}: query FAILED {e}", file=sys.stderr)
            net_ig = None
        h = human.get(name, {})
        rows.append({"dump": name, "realTurn": h.get("realTurn"), "side": h.get("side"),
                     "human_ig": h.get("humanIG"), "net_ig": net_ig})
        print(f"  [{i+1}/{len(files)}] {name}: human={h.get('humanIG')} net={net_ig}", file=sys.stderr)

    rows.sort(key=lambda r: r["dump"])
    print(f"\n{'dump':22s} {'realT':>5s} {'side':>4s} {'human_IG':>8s} {'net_IG':>6s}  match")
    print("-" * 60)
    agree = same = hi = lo = 0
    for r in rows:
        if r["net_ig"] is None:
            mark = "ERR"
        elif r["human_ig"] == r["net_ig"]:
            mark = "=="; agree += 1
        elif r["net_ig"] > r["human_ig"]:
            mark = f"net+{r['net_ig']-r['human_ig']}"; hi += 1
        else:
            mark = f"net-{r['human_ig']-r['net_ig']}"; lo += 1
        print(f"{r['dump']:22s} {str(r['realTurn']):>5s} {str(r['side']):>4s} "
              f"{str(r['human_ig']):>8s} {str(r['net_ig']):>6s}  {mark}")
    n = len([r for r in rows if r["net_ig"] is not None])
    print(f"\n{n} positions: agree(==)={agree}  net_over(>human)={hi}  net_under(<human)={lo}")
    if n:
        print(f"exact-agreement rate = {agree}/{n} = {100*agree/n:.0f}%")
    json.dump(rows, open(os.path.join(HERE, "_ig_human_vs_net.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
