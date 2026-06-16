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
                     variant set, V5_CS2_NoIG transitively reaches LiveOpeningBook2);
                     v4 also asserts the INTERIOR iterator HardIterator_5var_NoIG
                     ([[], ['V5_CS_NoIG'], [], []]) and that each candidate-side
                     player wires its MoveIterator to it (no IG auto-fire below root)
  4. book_sizes      LiveOpeningBook2 == 50 raw entries, DefaultOpeningBook == 4
  5. reference_graph every declared reference resolves (openingBook, filter,
                     subsetFilter, buyLimits, combination, PartialPlayers,
                     include, iterator keys, PlayoutPlayer, WeightsFile file)
  6. frozen_tuple    RL_SelfPlay tuple == campaign_frozen.json (EpsilonLate /
                     EpsilonIG must EQUAL frozen -- absent config key = 0.0, so
                     frozen 0.05 + absent FAILS; older frozen files without the
                     key keep the absent-or-0 rule); v4 self-play = ONE block
                     (frozen selfplay_block) matching frozen selfplay_rounds /
                     selfplay_seed_base / selfplay_threads, NO ForcedCards,
                     run:false at rest
  7b. selfplay_replays  the self-play blocks carry the expected saveReplays dirs
                     (per-iteration replay archive contract, 2026-06-12)
  7. parent_repin    parent-side players' WeightsFile == frozen parent_bin (F-07
                     recovery + N-2); v4 set = RL_Eval (eval candidate pin) +
                     RL_SelfPlay (the data generator). RL_Eval_origin is pinned
                     to origin_bin separately (origin_pin).
  8. existences      frozen parent_pt + the train/val H5s exist on disk
  9. use_dsnn_sentinel  no use_dsnn.txt FORCE_DSNN drop-in sentinel next to
                     the engine exes (M-09): the sentinel silently swaps the
                     net + think params on every protocol-path engine call
                     (query_move / tactical suite / coverage), contaminating
                     stages 6/8; bin dir derived from --config (config lives
                     at <bin>/asset/config/config.txt, sentinel at
                     <bin>/use_dsnn.txt). The masterbot2016 baseline needs no
                     check -- the 2016 exe predates the sentinel mechanism.
  10. engine_sha     both engine exes (Prismata_Testing.exe / PrismataAI.exe)
                     sha256-match the frozen engine_*_exe_sha256 pins (Task 5/10):
                     an unrecorded rebuild can silently flip the maxPlayer value
                     SIGN or a shared-C++ feature. Fast -- always runs when frozen
                     loaded.
  11. correctness_gates  auto-runs a6_orientation_check.py (value sign-flip guard)
                     + test_three_way_feature_parity.py (JS extractor == C++
                     exporter == C++ inference) as subprocesses. These two
                     catastrophic-but-silent value failures were previously caught
                     only by MANUAL tests; preflight automates them for unattended
                     runs. SLOW (~30-60s, needs the engine + pytest) -- skip with
                     --skip-slow-gates (the fast engine_sha pin still runs).

Exit 0 = all pass; exit 1 = any failure, each printed as one
"FAIL: <check>: <detail>" line ("OK: <check>" lines unless --quiet).

NOTE on scope: Benchmarks "players" name resolution is deliberately NOT
checked -- Dave's legacy run:false blocks reference long-dead player names
(HardAI300UCT, ExpertAI1, ...); only run:true blocks construct players, and
check 2 already requires zero of those.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = "c:/libraries/PrismataAI-dave-master/bin/asset/config/config.txt"
DEFAULT_FROZEN = os.path.join(REPO_ROOT, "eval", "campaign_frozen.json")

# --- Campaign structural expectations (post SWF port / IG-subset rebuild) ----
RL_ROOT_ITERATOR     = "HardIterator_5var_IGsubset_Root"
RL_WRAPPED_ITERATOR  = "HardIterator_5var_NoIG_Root"
RL_INTERIOR_ITERATOR = "HardIterator_5var_NoIG"          # v4: interior never auto-fires IG
RL_SUBSET_FILTER     = "IG_Only"
RL_PORTFOLIO_DIMS    = [1, 5, 5, 1]
RL_ABILITY_VARIANTS  = {"V5_CS2_NoIG", "V5_CS_NoIG", "V5_CSNF_NoIG",
                        "V5_CSClickNC_NoIG", "V5_CSClickNF_NoIG"}
RL_OB_VARIANT        = "V5_CS2_NoIG"
RL_OB_BOOK           = "LiveOpeningBook2"
BOOK_SIZES           = {"LiveOpeningBook2": 50, "DefaultOpeningBook": 4}
# repo-root-relative data files the iteration driver depends on. Fallback for older
# frozen files only — a tuple_version >= 2 frozen file names its own rehearsal_file /
# tripwire_val_file and those are checked instead (check_existences).
DATA_FILES = ("training/data/human_val_1700_v2.h5",
              "training/data/human_1800_v2.h5")

# Players that must run the frozen DEPLOYMENT eval budget (preflight-gaps-06): the
# eval budget is campaign identity but lived only as config literals before 2026-06-13.
# v4 (proof-of-life): the eval surface shrinks to the candidate pin + the permanent origin.
EVAL_BUDGET_PLAYERS = ("RL_Eval", "RL_Eval_origin")

# v4: the candidate-side players whose INTERIOR (response/rollout) move iterator must be
# the NoIG portfolio -- the interior never auto-fires Infusion Grid (the root subset filter
# owns the IG-count decision; a non-NoIG interior would re-introduce auto-fire below root).
SELFPLAY_INTERIOR_PLAYERS = ("RL_SelfPlay", "RL_Eval", "RL_Eval_origin")

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

    # v4: the INTERIOR (response/rollout) iterator. The root subset filter owns the
    # IG-count decision; the interior must never auto-fire IG below root, so it is the
    # single-variant NoIG portfolio [[], ['V5_CS_NoIG'], [], []]. Each candidate-side
    # player must wire its MoveIterator to it (a legacy HardIterator_5var re-introduces
    # the auto-fire the whole v4 reframe removes).
    interior = iterators.get(RL_INTERIOR_ITERATOR)
    if not isinstance(interior, dict):
        failures.append("interior Move Iterator '%s' not found" % RL_INTERIOR_ITERATOR)
    else:
        if interior.get("type") != "PPPortfolio":
            failures.append("%s.type is '%s', expected 'PPPortfolio'"
                            % (RL_INTERIOR_ITERATOR, interior.get("type")))
        if interior.get("PartialPlayers") != [[], ["V5_CS_NoIG"], [], []]:
            failures.append("%s.PartialPlayers is %s, expected [[], ['V5_CS_NoIG'], [], []] "
                            "(the interior must be single-variant NoIG -- no IG auto-fire "
                            "below root)" % (RL_INTERIOR_ITERATOR, interior.get("PartialPlayers")))
    players = cfg.get("Players", {})
    for pname in SELFPLAY_INTERIOR_PLAYERS:
        node = players.get(pname)
        if not isinstance(node, dict):
            failures.append("Player '%s' not found (its MoveIterator must be '%s')"
                            % (pname, RL_INTERIOR_ITERATOR))
            continue
        if node.get("MoveIterator") != RL_INTERIOR_ITERATOR:
            failures.append("%s.MoveIterator is '%s', expected '%s' (v4: the interior "
                            "iterator never auto-fires IG below root)"
                            % (pname, node.get("MoveIterator"), RL_INTERIOR_ITERATOR))
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
    # UCTConstant: frozen but previously unchecked (final-review gap). Guarded on key
    # presence so older frozen files / minimal test fixtures stay valid.
    if "UCTConstant" in frozen:
        if "UCTConstant" not in sp:
            failures.append("RL_SelfPlay.UCTConstant missing from config (frozen at %s)"
                            % frozen["UCTConstant"])
        elif float(sp["UCTConstant"]) != float(frozen["UCTConstant"]):
            failures.append("RL_SelfPlay.UCTConstant is %s but campaign_frozen.json freezes it "
                            "at %s -- config drifted; reconcile deliberately"
                            % (sp["UCTConstant"], frozen["UCTConstant"]))
    blocks = {b.get("name"): b for b in cfg.get("Benchmarks", []) if isinstance(b, dict)}
    # EpsilonLate: regime v3 (2026-06-13) freezes it at 0 (retired in favour of the targeted
    # EpsilonIG); config must EQUAL frozen exactly. An ABSENT config key means 0.0 to the
    # engine, which only matches a frozen 0.0.
    # Guarded for OLDER frozen files: if frozen lacks the key, the original absent-or-0
    # convention applies (a present nonzero key would silently re-enable the late sampler).
    if "EpsilonLate" in frozen:
        got = float(sp.get("EpsilonLate", 0.0))
        want = float(frozen["EpsilonLate"])
        if got != want:
            failures.append("RL_SelfPlay.EpsilonLate is %s but campaign_frozen.json freezes it "
                            "at %s -- config drifted; reconcile deliberately (an absent config "
                            "key means 0.0 to the engine)"
                            % (sp.get("EpsilonLate", "ABSENT (= 0.0)"), frozen["EpsilonLate"]))
    elif "EpsilonLate" in sp and float(sp["EpsilonLate"]) != 0.0:
        failures.append("RL_SelfPlay.EpsilonLate is %s -- must be ABSENT (or 0): this frozen "
                        "tuple (no EpsilonLate key) has late-epsilon disabled" % sp["EpsilonLate"])
    # EpsilonIG (regime v3, 2026-06-13 — the J5 targeted IG-count exploration): same exact-match
    # convention as EpsilonLate (absent config key = 0.0 to the engine = the sampler silently off).
    if "EpsilonIG" in frozen:
        got = float(sp.get("EpsilonIG", 0.0))
        want = float(frozen["EpsilonIG"])
        if got != want:
            failures.append("RL_SelfPlay.EpsilonIG is %s but campaign_frozen.json freezes it at %s "
                            "-- config drifted; reconcile deliberately (an absent config key means "
                            "0.0 = targeted IG exploration OFF)"
                            % (sp.get("EpsilonIG", "ABSENT (= 0.0)"), frozen["EpsilonIG"]))
    elif "EpsilonIG" in sp and float(sp["EpsilonIG"]) != 0.0:
        failures.append("RL_SelfPlay.EpsilonIG is %s -- must be ABSENT (or 0): this frozen tuple "
                        "(no EpsilonIG key) has targeted IG exploration disabled" % sp["EpsilonIG"])
    # Self-play data block (v4 proof-of-life, 2026-06-14): ONE general block (no forced-Hotel
    # mix -- IG is no longer the axis under test). The block must carry the frozen rounds,
    # seed base (the driver sets Seed = base + K transiently in stage 1 and restores the base
    # in a finally, so the config must REST at the base), and thread count; it must NOT force
    # cards and must rest run:false (drivers flip it transiently). Guarded on frozen carrying
    # selfplay_block so older two-block frozen files are not misread.
    spb_name = frozen.get("selfplay_block")
    if spb_name:
        spb = blocks.get(spb_name)
        if spb is None:
            failures.append("self-play block '%s' not found in Benchmarks "
                            "(frozen selfplay_block)" % spb_name)
        else:
            if "selfplay_rounds" in frozen and int(spb.get("rounds", -1)) != int(frozen["selfplay_rounds"]):
                failures.append("%s.rounds is %s but campaign_frozen.json freezes "
                                "selfplay_rounds at %s"
                                % (spb_name, spb.get("rounds"), frozen["selfplay_rounds"]))
            sb = frozen.get("selfplay_seed_base")
            if sb is not None and int(spb.get("Seed", -1)) != int(sb):
                failures.append("%s.Seed is %s at rest but frozen selfplay_seed_base is %s "
                                "(the driver sets base+K transiently and must restore the base)"
                                % (spb_name, spb.get("Seed"), sb))
            if "selfplay_threads" in frozen and int(spb.get("Threads", 1)) != int(frozen["selfplay_threads"]):
                failures.append("%s.Threads is %s but campaign_frozen.json freezes "
                                "selfplay_threads at %s"
                                % (spb_name, spb.get("Threads", 1), frozen["selfplay_threads"]))
            if "ForcedCards" in spb:
                failures.append("%s has ForcedCards %s -- the v4 self-play block must have NO "
                                "ForcedCards (proof-of-life uses the unforced general mix)"
                                % (spb_name, spb.get("ForcedCards")))
            if spb.get("run") is True:
                failures.append("%s has \"run\": true -- self-play blocks must rest run:false "
                                "(drivers flip them transiently)" % spb_name)
    return failures


# ---------------------------------------------------------------------------
# Check 7: parent re-pin (F-07 + N-2: the v4 set (RL_Eval + RL_SelfPlay))
# ---------------------------------------------------------------------------

# Every config player that must carry the frozen parent net, with the concrete
# consequence of a mispoint (printed in the FAIL line). N-2: candidate-side
# provenance is engine-confirmed per anchor; the parent side is only as strong
# as these pins. v4 (proof-of-life) shrinks the set to the eval candidate pin
# and the self-play data generator (RL_Eval_origin is origin-pinned separately;
# RL_Eval_iter0 / RL_Narrow are no longer campaign anchors).
PARENT_PINNED_PLAYERS = (
    ("RL_Eval", "the eval candidate pin -- a killed/failed iteration left it on an "
                "unpromoted candidate (F-07); restore it before evaluating"),
    ("RL_SelfPlay", "the self-play DATA GENERATOR -- the iteration would train on "
                    "games played by the wrong net"),
)


def check_parent_repin(cfg, frozen):
    parent = frozen.get("parent_bin")
    if not parent:
        return ["campaign_frozen.json missing 'parent_bin'"]
    players = cfg.get("Players", {})
    failures = []
    for name, consequence in PARENT_PINNED_PLAYERS:
        node = players.get(name)
        if not isinstance(node, dict):
            failures.append("Player '%s' not found in config (must be pinned to frozen "
                            "parent_bin '%s'; %s)" % (name, parent, consequence))
            continue
        got = node.get("WeightsFile")
        if got != parent:
            failures.append("%s.WeightsFile is '%s' but frozen parent_bin is '%s' -- %s"
                            % (name, got, parent, consequence))
    return failures


# ---------------------------------------------------------------------------
# Check: origin pin (drl-03, 2026-06-13) — RL_Eval_origin is PERMANENTLY v221
# ---------------------------------------------------------------------------

def check_origin_pin(cfg, frozen):
    origin = frozen.get("origin_bin")
    if not origin:
        return []
    node = cfg.get("Players", {}).get("RL_Eval_origin")
    if not isinstance(node, dict):
        return ["Player 'RL_Eval_origin' not found (must be PERMANENTLY pinned to origin_bin "
                "'%s' -- it carries the campaign's cumulative-axis measurement, drl-03)" % origin]
    if node.get("WeightsFile") != origin:
        return ["RL_Eval_origin.WeightsFile is '%s' but frozen origin_bin is '%s' -- the origin "
                "anchor is NEVER repointed (promotion repoints the four parent pins ONLY); "
                "without it 'd_rl vs the fixed v221 origin' silently becomes marginal-vs-parent"
                % (node.get("WeightsFile"), origin)]
    return []


# ---------------------------------------------------------------------------
# Check: anchor blocks (preflight-gaps-06, 2026-06-13) — rounds/Seed/Threads pinned
# ---------------------------------------------------------------------------

def check_anchor_blocks(cfg, frozen):
    spec = frozen.get("anchor_blocks")
    if not isinstance(spec, dict):
        return []
    blocks = {b.get("name"): b for b in cfg.get("Benchmarks", []) if isinstance(b, dict)}
    failures = []
    for name, want in sorted(spec.items()):
        blk = blocks.get(name)
        if blk is None:
            failures.append("anchor block '%s' not found in Benchmarks (frozen anchor_blocks)" % name)
            continue
        for key in ("rounds", "Seed", "Threads"):
            if key in want and int(blk.get(key, -1)) != int(want[key]):
                failures.append("%s.%s is %s but frozen anchor_blocks pins %s"
                                % (name, key, blk.get(key), want[key]))
        if blk.get("run") is True:
            failures.append("anchor block '%s' has \"run\": true -- must rest run:false" % name)
    return failures


# ---------------------------------------------------------------------------
# Check: eval budget (preflight-gaps-06 / A1) — deployment budget on the eval players
# ---------------------------------------------------------------------------

def check_eval_budget(cfg, frozen):
    budget = frozen.get("eval_budget")
    if not isinstance(budget, dict):
        return []
    players = cfg.get("Players", {})
    failures = []
    for pname in EVAL_BUDGET_PLAYERS:
        node = players.get(pname)
        if not isinstance(node, dict):
            failures.append("Player '%s' not found (must run the frozen eval budget)" % pname)
            continue
        for cfg_key in ("TimeLimit", "MaxTraversals", "UCTConstant"):
            if cfg_key not in budget:
                continue
            if float(node.get(cfg_key, -1)) != float(budget[cfg_key]):
                failures.append("%s.%s is %s but frozen eval_budget pins %s -- the eval budget "
                                "IS campaign identity (A1); drift makes iterations incomparable"
                                % (pname, cfg_key, node.get(cfg_key), budget[cfg_key]))
    return failures


# ---------------------------------------------------------------------------
# Check: parent bin CONTENT (ops-promote-01, 2026-06-13) — sha256 pin, not just name
# ---------------------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_parent_sha(frozen, config_dir):
    want = frozen.get("parent_bin_sha256")
    parent = frozen.get("parent_bin")
    if not want or not parent:
        return []
    path = os.path.join(config_dir, parent)
    if not os.path.isfile(path):
        return ["parent bin not found for sha check: %s" % path]
    got = _sha256(path)
    if got.lower() != str(want).lower():
        return ["parent bin CONTENT mismatch: sha256(%s) = %s but frozen parent_bin_sha256 = %s "
                "-- a name-consistent-but-content-wrong parent (botched promotion, or a same-K "
                "re-export clobbered a promoted bin). Re-export from parent_pt or re-pin via "
                "eval/promote_candidate.ps1." % (parent, got, want)]
    return []


# ---------------------------------------------------------------------------
# Check: unit_index.json (impl-unitindex-05, 2026-06-13) — the lobotomized-net guard
# ---------------------------------------------------------------------------

def check_unit_index(config_path):
    config_dir = os.path.dirname(os.path.abspath(config_path))
    path = os.path.join(config_dir, "unit_index.json")
    if not os.path.isfile(path):
        return ["unit_index.json not found at %s -- without it a NeuralNet player maps 0 card "
                "types and silently evaluates on the 15 globals alone (the engine now FATALs on "
                "mappedTypes==0; this catches it before any launch)" % path]
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            idx = json.load(f)
    except ValueError as e:
        return ["unit_index.json is not valid JSON: %s" % e]
    count = idx.get("count") if isinstance(idx, dict) else None
    units = idx.get("units") if isinstance(idx, dict) else idx
    n = len(units) if isinstance(units, (list, dict)) else None
    if count != 116 and n != 116:
        return ["unit_index.json does not carry the canonical 116 units (count=%s, |units|=%s)"
                % (count, n)]
    return []


# ---------------------------------------------------------------------------
# Check 7b: saveReplays on the self-play block (2026-06-12 replay-audit fixes).
# The per-iteration replay archive (forensic record + future-schema source) is
# part of the iteration contract; a drifted/removed saveReplays key would make
# stage 1.5 throw only AFTER the full self-play run. Structural expectation,
# hardcoded like iterator_shape. v4 runs ONE self-play block, so 7b validates
# only it (the dead forced-Hotel block is no longer required to exist).
# ---------------------------------------------------------------------------

SELFPLAY_REPLAY_DIRS = (
    ("RL_SelfPlay_General", "asset/replays/rl_selfplay_general"),
)


def check_selfplay_replays(cfg):
    failures = []
    blocks = {b.get("name"): b for b in cfg.get("Benchmarks", []) if isinstance(b, dict)}
    for name, expected in SELFPLAY_REPLAY_DIRS:
        node = blocks.get(name)
        if not isinstance(node, dict):
            failures.append("Tournament block '%s' not found (expected saveReplays '%s')"
                            % (name, expected))
            continue
        got = node.get("saveReplays")
        if got != expected:
            failures.append("%s.saveReplays is %r but the iteration contract expects '%s' "
                            "(stage 1.5 archives replays per iteration)" % (name, got, expected))
    return failures


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
    # tuple_version >= 2 frozen files name their own data dependencies (the elite
    # rehearsal slice + the capped tripwire val set); older files use the constant pair.
    data_files = [frozen[k] for k in ("rehearsal_file", "tripwire_val_file") if frozen.get(k)]
    if not data_files:
        data_files = list(DATA_FILES)
    for rel in data_files:
        path = rel if os.path.isabs(rel) else os.path.join(repo_root, rel)
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
# Check 9: use_dsnn.txt drop-in sentinel (M-09 contamination guard)
# ---------------------------------------------------------------------------

def check_use_dsnn_sentinel(config_path):
    """Check 9: the FORCE_DSNN Steam drop-in sentinel must NOT exist in the
    engine bin dir. config.txt lives at <bin>/asset/config/config.txt; the
    sentinel the protocol path probes for sits NEXT TO the exe at
    <bin>/use_dsnn.txt -- derive bin from the config path (two dirnames above
    the config dir). The masterbot2016 dir needs no equivalent check: the 2016
    exe predates the sentinel mechanism."""
    config_dir = os.path.dirname(os.path.abspath(config_path))
    bin_dir = os.path.dirname(os.path.dirname(config_dir))
    sentinel = os.path.join(bin_dir, "use_dsnn.txt")
    if os.path.isfile(sentinel):
        return ["FORCE_DSNN drop-in sentinel exists: %s -- while present it silently "
                "swaps the loaded net (+ think_time/max_traversals) on EVERY "
                "protocol-path engine call (query_move.js, tactical suite, coverage; "
                "stages 6/8 run through it), so campaign measurements would be taken "
                "with the WRONG net. It is the Steam drop-in mechanism (dave 72c240a), "
                "not a campaign config -- delete/move it before running an iteration."
                % sentinel]
    return []


# ---------------------------------------------------------------------------
# Check: engine-exe sha pin (Task 5/10, 2026-06-16) — an unrecorded rebuild can
# silently flip the maxPlayer value sign or a shared-C++ feature. The frozen
# tuple pins both engine exes; preflight fails if either was rebuilt without
# re-running a6 + three-way and re-pinning the sha.
# ---------------------------------------------------------------------------

def check_engine_sha(frozen, dave_bin):
    failures = []
    for key, exe in (("engine_testing_exe_sha256", "Prismata_Testing.exe"),
                     ("engine_prismataai_exe_sha256", "PrismataAI.exe")):
        want = frozen.get(key)
        if not want:
            continue
        path = os.path.join(dave_bin, exe)
        if not os.path.isfile(path):
            failures.append("engine exe not found for sha check: %s" % path); continue
        got = _sha256(path)
        if got.lower() != str(want).lower():
            failures.append("%s sha256 mismatch: got %s but frozen %s = %s -- the engine was rebuilt; "
                            "re-run a6 + three-way and re-pin the exe sha (an unrecorded rebuild can "
                            "silently flip the value sign or a feature)" % (exe, got, key, want))
    return failures


# ---------------------------------------------------------------------------
# Check: a6 + three-way correctness gates (Task 10, 2026-06-16) — the two
# catastrophic-but-silent value failures (a maxPlayer value SIGN-FLIP and a
# shared-C++ FEATURE skew) were only caught by two MANUAL tests. Running them
# at preflight (subprocess; ~30-60s, needs the engine + pytest) closes the gap
# for unattended runs. Skippable via --skip-slow-gates (unit tests / fast probes).
# ---------------------------------------------------------------------------

def check_correctness_gates(repo_root):
    failures = []
    a6 = subprocess.run([sys.executable, os.path.join(repo_root, "eval", "a6_orientation_check.py")],
                        capture_output=True, text=True)
    if a6.returncode != 0:
        failures.append("a6 orientation check FAILED (value sign-flip guard): %s"
                        % ((a6.stdout or "")[-400:] + (a6.stderr or "")[-400:]))
    tw = subprocess.run([sys.executable, "-m", "pytest",
                         os.path.join(repo_root, "training", "tests", "test_three_way_feature_parity.py"), "-q"],
                        capture_output=True, text=True, cwd=repo_root)
    if tw.returncode != 0:
        failures.append("three-way feature parity gate FAILED: %s" % ((tw.stdout or "")[-400:]))
    return failures


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def run_checks(config_path, frozen_path, repo_root, skip_slow_gates=False):
    """Returns ordered list of (check_name, [failure detail strings])."""
    results = []
    cfg, cfg_failures = load_config(config_path)
    results.append(("json_bom", cfg_failures))
    # M-09: independent of config CONTENT -- guards the engine bin dir itself.
    results.append(("use_dsnn_sentinel", check_use_dsnn_sentinel(config_path)))
    # The engine bin dir (config lives at <bin>/asset/config/config.txt), reused by
    # the engine-sha check the same way check_use_dsnn_sentinel derives it.
    config_dir = os.path.dirname(os.path.abspath(config_path))
    dave_bin = os.path.dirname(os.path.dirname(config_dir))
    frozen, frozen_failures = load_frozen(frozen_path)
    if frozen_failures:
        results.append(("frozen_json", frozen_failures))
    if cfg is not None:
        results.append(("run_true", check_run_flags(cfg)))
        results.append(("iterator_shape", check_iterator_shape(cfg)))
        results.append(("book_sizes", check_book_sizes(cfg)))
        results.append(("reference_graph",
                        check_reference_graph(cfg, config_dir)))
        results.append(("selfplay_replays", check_selfplay_replays(cfg)))
        if frozen is not None:
            results.append(("frozen_tuple", check_frozen_tuple(cfg, frozen)))
            results.append(("parent_repin", check_parent_repin(cfg, frozen)))
            results.append(("origin_pin", check_origin_pin(cfg, frozen)))
            results.append(("anchor_blocks", check_anchor_blocks(cfg, frozen)))
            results.append(("eval_budget", check_eval_budget(cfg, frozen)))
    results.append(("unit_index", check_unit_index(config_path)))
    if frozen is not None:
        results.append(("existences", check_existences(frozen, repo_root)))
        results.append(("parent_sha",
                        check_parent_sha(frozen, config_dir)))
        # Engine-exe sha pin (fast): always run when frozen is loaded.
        results.append(("engine_sha", check_engine_sha(frozen, dave_bin)))
    # a6 + three-way correctness gates (slow; shell out to the engine + pytest):
    # only when not skipped (unit tests pass --skip-slow-gates so they don't shell out).
    if not skip_slow_gates:
        results.append(("correctness_gates", check_correctness_gates(repo_root)))
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
    p.add_argument("--skip-slow-gates", action="store_true",
                   help="skip the a6 + three-way correctness gates (they shell out to the "
                        "engine + pytest, ~30-60s); the fast engine-exe sha pin still runs")
    args = p.parse_args(argv)

    results = run_checks(args.config, args.frozen, args.repo_root,
                         skip_slow_gates=args.skip_slow_gates)
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
