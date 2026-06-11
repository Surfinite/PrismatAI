#!/usr/bin/env python
"""Structural preflight for the dave-master engine config + frozen campaign tuple.

Stage 0 of eval/run_iteration.ps1 (and runnable standalone before ANY engine
launch). Rationale (Jun-9/10 RL-loop audits): a misconfigured config once ran
the engine handicapped for 5 days and was caught only by a human. The engine
now hard-fails on unknown/empty names at construction (dave 26075fa/d0ec633),
but a config-side preflight (a) catches everything BEFORE a multi-day run
starts, (b) catches drift the engine cannot know about (frozen-tuple drift,
RL_Eval parent re-pin / F-07), and (c) covers players the engine never
constructs in a given run.

Checks
  1. json_bom        config parses as strict JSON, no BOM (first byte '{')
  2. run_true        zero "run": true Benchmarks blocks (no surprise tournaments)
  3. iterator_shape  RL root iterator structure (AbilitySubset/IG_Only wrapping
                     the 5-variant NoIG PPPortfolio, dims [1,5,5,1], exact
                     variant set, V5_CS2_NoIG transitively reaches LiveOpeningBook2)
  4. book_sizes      LiveOpeningBook2 == 50 raw entries, DefaultOpeningBook == 4
  5. reference_graph every declared reference resolves (openingBook, filter,
                     subsetFilter, buyLimits, combination, PartialPlayers,
                     include, iterator keys, PlayoutPlayer, WeightsFile file)
  6. frozen_tuple    RL_SelfPlay tuple == campaign_frozen.json; EpsilonLate
                     absent (or 0) -- config convention is key-absent
  7. parent_repin    RL_Eval.WeightsFile == frozen parent_bin (F-07 recovery)
  8. existences      frozen parent_pt + the train/val H5s exist on disk

Exit 0 = all pass; exit 1 = any failure, each printed as one
"FAIL: <check>: <detail>" line ("OK: <check>" lines unless --quiet).

NOTE on scope: Benchmarks "players" name resolution is deliberately NOT
checked -- Dave's legacy run:false blocks reference long-dead player names
(HardAI300UCT, ExpertAI1, ...); only run:true blocks construct players, and
check 2 already requires zero of those.
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = "c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt"
DEFAULT_FROZEN = os.path.join(REPO_ROOT, "eval", "campaign_frozen.json")

# --- Campaign structural expectations (post SWF port / IG-subset rebuild) ----
RL_ROOT_ITERATOR    = "HardIterator_5var_IGsubset_Root"
RL_WRAPPED_ITERATOR = "HardIterator_5var_NoIG_Root"
RL_SUBSET_FILTER    = "IG_Only"
RL_PORTFOLIO_DIMS   = [1, 5, 5, 1]
RL_ABILITY_VARIANTS = {"V5_CS2_NoIG", "V5_CS_NoIG", "V5_CSNF_NoIG",
                       "V5_CSClickNC_NoIG", "V5_CSClickNF_NoIG"}
RL_OB_VARIANT       = "V5_CS2_NoIG"
RL_OB_BOOK          = "LiveOpeningBook2"
BOOK_SIZES          = {"LiveOpeningBook2": 50, "DefaultOpeningBook": 4}
# repo-root-relative data files the iteration driver depends on
DATA_FILES = ("training/data/human_val_1700_v2.h5",
              "training/data/human_1800_v2.h5")

# config keys (by section) that reference a Move Iterator by name
PLAYER_ITERATOR_KEYS = ("RootMoveIterator", "MoveIterator", "ResponseMoveIterator",
                        "iterator", "Portfolio")


# ---------------------------------------------------------------------------
# Loaders (check 1 lives in load_config)
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Check 1: strict JSON + no BOM. Returns (cfg_or_None, failures)."""
    failures = []
    try:
        with open(config_path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return None, ["cannot read config: %s" % e]
    if raw[:1] != b"{":
        failures.append("first byte is %r, expected '{' (BOM/junk before JSON -- "
                        "the C++ parser silently skips pre-load on BOM)" % raw[:3])
    try:
        # decode with utf-8-sig so a BOM'd file still parses and the remaining
        # checks can run (more failures surfaced in one pass)
        cfg = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        failures.append("config is not strict JSON: %s" % e)
        return None, failures
    if not isinstance(cfg, dict):
        failures.append("config top level is %s, expected object" % type(cfg).__name__)
        return None, failures
    return cfg, failures


def load_frozen(frozen_path):
    """Returns (frozen_or_None, failures)."""
    try:
        with open(frozen_path, "r", encoding="utf-8-sig") as f:
            return json.load(f), []
    except OSError as e:
        return None, ["cannot read frozen tuple: %s" % e]
    except ValueError as e:
        return None, ["campaign_frozen.json is not valid JSON: %s" % e]


# ---------------------------------------------------------------------------
# Check 2: zero run:true Benchmarks blocks
# ---------------------------------------------------------------------------

def check_run_flags(cfg):
    failures = []
    for i, block in enumerate(cfg.get("Benchmarks", [])):
        if isinstance(block, dict) and block.get("run") is True:
            failures.append("Benchmarks[%d] '%s' has \"run\": true -- a stray engine "
                            "launch would run it; flip to false (drivers toggle it "
                            "transiently themselves)" % (i, block.get("name", "?")))
    return failures


# ---------------------------------------------------------------------------
# Check 3: RL root iterator shape
# ---------------------------------------------------------------------------

def _reachable_books(partials, start):
    """Walk `combination` arrays transitively from `start`; collect openingBook refs."""
    books, seen, stack = set(), set(), [start]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        node = partials.get(name)
        if not isinstance(node, dict):
            continue
        ob = node.get("openingBook")
        if isinstance(ob, str):
            books.add(ob)
        for child in node.get("combination", []):
            if isinstance(child, str):
                stack.append(child)
    return books


def check_iterator_shape(cfg):
    failures = []
    iterators = cfg.get("Move Iterators", {})
    partials = cfg.get("Partial Players", {})

    root = iterators.get(RL_ROOT_ITERATOR)
    if not isinstance(root, dict):
        failures.append("Move Iterator '%s' not found" % RL_ROOT_ITERATOR)
    else:
        if root.get("type") != "AbilitySubset":
            failures.append("%s.type is '%s', expected 'AbilitySubset'"
                            % (RL_ROOT_ITERATOR, root.get("type")))
        if root.get("subsetFilter") != RL_SUBSET_FILTER:
            failures.append("%s.subsetFilter is '%s', expected '%s'"
                            % (RL_ROOT_ITERATOR, root.get("subsetFilter"), RL_SUBSET_FILTER))
        if root.get("include") != RL_WRAPPED_ITERATOR:
            failures.append("%s.include is '%s', expected '%s'"
                            % (RL_ROOT_ITERATOR, root.get("include"), RL_WRAPPED_ITERATOR))

    inner = iterators.get(RL_WRAPPED_ITERATOR)
    if not isinstance(inner, dict):
        failures.append("Move Iterator '%s' not found" % RL_WRAPPED_ITERATOR)
    else:
        if inner.get("type") != "PPPortfolio":
            failures.append("%s.type is '%s', expected 'PPPortfolio'"
                            % (RL_WRAPPED_ITERATOR, inner.get("type")))
        pps = inner.get("PartialPlayers")
        if not isinstance(pps, list):
            failures.append("%s.PartialPlayers missing/not a list" % RL_WRAPPED_ITERATOR)
        else:
            dims = [len(x) if isinstance(x, list) else -1 for x in pps]
            if dims != RL_PORTFOLIO_DIMS:
                failures.append("%s.PartialPlayers dims are %s, expected %s "
                                "(crippled-iterator guard)"
                                % (RL_WRAPPED_ITERATOR, dims, RL_PORTFOLIO_DIMS))
            if len(pps) > 1 and isinstance(pps[1], list):
                got = set(pps[1])
                if got != RL_ABILITY_VARIANTS:
                    failures.append("%s ActionAbility variants are %s, expected exactly %s"
                                    % (RL_WRAPPED_ITERATOR, sorted(got),
                                       sorted(RL_ABILITY_VARIANTS)))

    reached = _reachable_books(partials, RL_OB_VARIANT)
    if RL_OB_BOOK not in reached:
        failures.append("'%s' does not transitively reach openingBook '%s' "
                        "(combination chain reaches only %s)"
                        % (RL_OB_VARIANT, RL_OB_BOOK, sorted(reached) or "no books"))
    return failures


# ---------------------------------------------------------------------------
# Check 4: opening-book sizes
# ---------------------------------------------------------------------------

def check_book_sizes(cfg):
    failures = []
    books = cfg.get("Opening Books", {})
    for name, want in sorted(BOOK_SIZES.items()):
        entries = books.get(name)
        if not isinstance(entries, list):
            failures.append("Opening Book '%s' missing/not a list" % name)
        elif len(entries) != want:
            failures.append("Opening Book '%s' has %d raw entries, expected %d "
                            "(post SWF port)" % (name, len(entries), want))
    return failures


# ---------------------------------------------------------------------------
# Check 5: declared reference graph resolves
# ---------------------------------------------------------------------------

def _flat_names(value):
    """Flatten a (possibly nested) list structure into the strings it contains."""
    out = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for v in value:
            out.extend(_flat_names(v))
    return out


def check_reference_graph(cfg, config_dir):
    failures = []
    books = cfg.get("Opening Books", {})
    filters = cfg.get("Filters", {})
    buy_limits = cfg.get("Buy Limits", {})
    partials = cfg.get("Partial Players", {})
    iterators = cfg.get("Move Iterators", {})
    players = cfg.get("Players", {})

    def need(section, key, owner, what):
        if key not in section:
            failures.append("%s: %s '%s' not found" % (owner, what, key))

    for name, node in partials.items():
        if not isinstance(node, dict):
            continue
        owner = "Partial Player '%s'" % name
        if "openingBook" in node:
            need(books, node["openingBook"], owner, "openingBook")
        if "filter" in node:
            need(filters, node["filter"], owner, "filter")
        if "buyLimits" in node:
            need(buy_limits, node["buyLimits"], owner, "buyLimits")
        for ref in _flat_names(node.get("combination", [])):
            need(partials, ref, owner, "combination Partial Player")

    for name, node in iterators.items():
        if not isinstance(node, dict):
            continue
        owner = "Move Iterator '%s'" % name
        if "include" in node:
            need(iterators, node["include"], owner, "include Move Iterator")
        if "subsetFilter" in node:
            need(filters, node["subsetFilter"], owner, "subsetFilter")
        if "buyLimits" in node:
            need(buy_limits, node["buyLimits"], owner, "buyLimits")
        for ref in _flat_names(node.get("PartialPlayers", [])):
            need(partials, ref, owner, "Partial Player")

    for name, node in players.items():
        if not isinstance(node, dict):
            continue
        owner = "Player '%s'" % name
        for key in PLAYER_ITERATOR_KEYS:
            if key in node:
                need(iterators, node[key], owner, "%s Move Iterator" % key)
        for ref in _flat_names(node.get("PartialPlayers", [])):
            need(partials, ref, owner, "Partial Player")
        if "PlayoutPlayer" in node:
            need(players, node["PlayoutPlayer"], owner, "PlayoutPlayer")
        wf = node.get("WeightsFile")
        if wf and not os.path.isfile(os.path.join(config_dir, wf)):
            failures.append("%s: WeightsFile '%s' not found in %s"
                            % (owner, wf, config_dir))
    return failures


# ---------------------------------------------------------------------------
# Check 6: frozen tuple (incl. the EpsilonLate key-absent convention)
# ---------------------------------------------------------------------------

def check_frozen_tuple(cfg, frozen):
    failures = []
    sp = cfg.get("Players", {}).get("RL_SelfPlay")
    if not isinstance(sp, dict):
        return ["Player 'RL_SelfPlay' not found in config"]
    pairs = (("MaxTraversals", "frozen_N"),
             ("TemperatureK", "TemperatureK"),
             ("TemperatureTau", "TemperatureTau"),
             ("EpsilonUniform", "EpsilonUniform"))
    for cfg_key, frozen_key in pairs:
        if frozen_key not in frozen:
            failures.append("campaign_frozen.json missing '%s'" % frozen_key)
            continue
        if cfg_key not in sp:
            failures.append("RL_SelfPlay.%s missing from config (frozen at %s)"
                            % (cfg_key, frozen[frozen_key]))
            continue
        got, want = float(sp[cfg_key]), float(frozen[frozen_key])
        if got != want:
            failures.append("RL_SelfPlay.%s is %s but campaign_frozen.json freezes it at %s "
                            "-- config drifted; reconcile deliberately (edit BOTH together)"
                            % (cfg_key, sp[cfg_key], frozen[frozen_key]))
    # EpsilonLate: frozen json says 0.0 and the config convention is KEY-ABSENT;
    # a present nonzero key would silently re-enable the late-epsilon sampler.
    if "EpsilonLate" in sp and float(sp["EpsilonLate"]) != 0.0:
        failures.append("RL_SelfPlay.EpsilonLate is %s -- must be ABSENT (or 0): the frozen "
                        "tuple has late-epsilon disabled" % sp["EpsilonLate"])
    if float(frozen.get("EpsilonLate", 0.0)) != 0.0:
        failures.append("campaign_frozen.json EpsilonLate is %s -- nonzero late-epsilon is "
                        "outside the frozen-campaign contract (config convention is "
                        "key-absent); update preflight_config.py deliberately if re-enabling"
                        % frozen["EpsilonLate"])
    return failures


# ---------------------------------------------------------------------------
# Check 7: parent re-pin (F-07)
# ---------------------------------------------------------------------------

def check_parent_repin(cfg, frozen):
    ev = cfg.get("Players", {}).get("RL_Eval")
    if not isinstance(ev, dict):
        return ["Player 'RL_Eval' not found in config"]
    parent = frozen.get("parent_bin")
    if not parent:
        return ["campaign_frozen.json missing 'parent_bin'"]
    got = ev.get("WeightsFile")
    if got != parent:
        return ["RL_Eval.WeightsFile is '%s' but frozen parent_bin is '%s' -- a killed/"
                "failed iteration left RL_Eval pointing at an unpromoted candidate "
                "(F-07); restore it before evaluating" % (got, parent)]
    return []


# ---------------------------------------------------------------------------
# Check 8: file existences (frozen parent_pt + data H5s)
# ---------------------------------------------------------------------------

def check_existences(frozen, repo_root):
    failures = []
    pt = frozen.get("parent_pt")
    if not pt:
        failures.append("campaign_frozen.json missing 'parent_pt'")
    else:
        pt_path = pt if os.path.isabs(pt) else os.path.join(repo_root, pt)
        if not os.path.isfile(pt_path):
            failures.append("frozen parent_pt not found: %s" % pt_path)
    for rel in DATA_FILES:
        path = os.path.join(repo_root, rel)
        if not os.path.isfile(path):
            failures.append("required data file not found: %s" % path)
    # Steam-anchor baseline (F-08 rewire): for a campaign run the 2016 MasterBot must exist at
    # its permanent home. (run_eval soft-skips when absent for ad-hoc use; stage 0 fails hard
    # by design — a campaign run should never silently lose its strength yardstick.)
    mb = frozen.get("masterbot2016_exe")
    if mb and not os.path.isfile(mb):
        failures.append("frozen masterbot2016_exe not found: %s" % mb)
    return failures


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def run_checks(config_path, frozen_path, repo_root):
    """Returns ordered list of (check_name, [failure detail strings])."""
    results = []
    cfg, cfg_failures = load_config(config_path)
    results.append(("json_bom", cfg_failures))
    frozen, frozen_failures = load_frozen(frozen_path)
    if frozen_failures:
        results.append(("frozen_json", frozen_failures))
    if cfg is not None:
        results.append(("run_true", check_run_flags(cfg)))
        results.append(("iterator_shape", check_iterator_shape(cfg)))
        results.append(("book_sizes", check_book_sizes(cfg)))
        results.append(("reference_graph",
                        check_reference_graph(cfg, os.path.dirname(os.path.abspath(config_path)))))
        if frozen is not None:
            results.append(("frozen_tuple", check_frozen_tuple(cfg, frozen)))
            results.append(("parent_repin", check_parent_repin(cfg, frozen)))
    if frozen is not None:
        results.append(("existences", check_existences(frozen, repo_root)))
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Structural preflight: engine config integrity "
                                            "+ frozen campaign tuple + parent re-pin.")
    p.add_argument("--config", default=DEFAULT_CONFIG,
                   help="dave-master engine config.txt (default: %(default)s)")
    p.add_argument("--frozen", default=DEFAULT_FROZEN,
                   help="campaign_frozen.json (default: %(default)s)")
    p.add_argument("--repo-root", default=REPO_ROOT,
                   help="repo root for repo-relative existence checks (default: %(default)s)")
    p.add_argument("--quiet", action="store_true", help="suppress OK lines")
    args = p.parse_args(argv)

    results = run_checks(args.config, args.frozen, args.repo_root)
    n_failures = 0
    for check, failures in results:
        if failures:
            n_failures += len(failures)
            for detail in failures:
                print("FAIL: %s: %s" % (check, detail))
        elif not args.quiet:
            print("OK: %s" % check)
    if n_failures:
        print("preflight FAILED: %d failure(s)" % n_failures)
        return 1
    if not args.quiet:
        print("preflight PASSED (%d checks)" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
