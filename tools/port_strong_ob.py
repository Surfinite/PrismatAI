#!/usr/bin/env python3
"""Option 2: add a STRONG-opening-book variant of dave's NATIVE HardIterator_Root
chain, so DSNN_Mixed35 / HardestAI / HardestAIUCT can be benchmarked with the
exact 50-entry MasterBot opening book on all sides — using ONLY engine_v1-native
partial-player types (mirrors the existing working ACEasy / ACAvoidBreach_ChillSolver
chain, just pointing at the strong book). The 50-entry book is sourced directly
from the SWF DefaultOpeningBook2 (the literal MasterBot book)."""
import json, re, shutil

DAVE = 'bin/asset/config/config.txt'
SWF = 'C:/libraries/PrismataAI/tmp_swf_extract/148_AI.AIThreadHandler_aiParamTextLoad.bin'

def load(p):
    t = open(p, encoding='utf-8-sig').read()
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    t = re.sub(r'(^|[^:])//.*$', r'\1', t, flags=re.M)
    return json.loads(t)

swf = load(SWF)
strong_ob = swf['Opening Books']['DefaultOpeningBook2']   # 50 entries, byte-verified == LiveOpeningBook2
assert len(strong_ob) == 50, len(strong_ob)

new_obs = {'LiveOpeningBook2': strong_ob}
new_pps = {
    'BuyOpeningBook2': {"type": "ActionBuy_OpeningBook", "openingBook": "LiveOpeningBook2"},
    'ACEasy_OB2': {"type": "ActionAbility_Combination", "combination": ["ACDefault", "BuyOpeningBook2"]},
    'ACAvoidBreach_ChillSolver_OB2': {"type": "ActionAbility_Combination", "combination": ["ACEasy_OB2", "AvoidBreach_SolveChill"]},
}
new_mis = {
    'HardIterator_OB2_Root': {"type": "PPPortfolio", "PartialPlayers": [
        ["DefenseSolver"], ["ACAvoidBreach_ChillSolver_OB2"],
        ["BuyEconTech", "BuyTechEcon", "BCGAttack_Root", "BCGWill_Root", "BCGDef_Root"],
        ["BreachGreedyKnapsack"]]},
}
new_players = {
    'DSNN_Mixed35_OB': {"type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
        "RootMoveIterator": "HardIterator_OB2_Root", "MoveIterator": "HardIterator", "Eval": "NeuralNet",
        "WeightsFile": "neural_weights_mixed_35prop.bin"},
    'HardestAI_OB': {"type": "Player_StackAlphaBeta", "TimeLimit": 7000, "MaxChildren": 40,
        "RootMoveIterator": "HardIterator_OB2_Root", "MoveIterator": "HardIterator", "Eval": "Playout", "PlayoutPlayer": "Playout"},
    'HardestAIUCT_OB': {"type": "Player_UCT", "TimeLimit": 7000, "MaxChildren": 40, "MaxTraversals": 100000,
        "RootMoveIterator": "HardIterator_OB2_Root", "MoveIterator": "HardIterator", "Eval": "Playout", "PlayoutPlayer": "Playout"},
}
tblocks = [
    {"run": True, "type": "Tournament", "name": "PV_OB2_Mixed35_vs_HardestAI", "rounds": 64,
     "UpdateIntervalSec": 10, "Threads": 8, "RandomCards": 8, "saveReplays": "asset/replays/ob2_mixed35_vs_hardestai",
     "players": [{"name": "DSNN_Mixed35_OB", "group": 1}, {"name": "HardestAI_OB", "group": 2}]},
    {"run": True, "type": "Tournament", "name": "PV_OB2_Mixed35_vs_HardestAIUCT", "rounds": 64,
     "UpdateIntervalSec": 10, "Threads": 8, "RandomCards": 8, "saveReplays": "asset/replays/ob2_mixed35_vs_hardestaiuct",
     "players": [{"name": "DSNN_Mixed35_OB", "group": 1}, {"name": "HardestAIUCT_OB", "group": 2}]},
]

shutil.copyfile(DAVE, DAVE + '.preob2.bak')
text = open(DAVE, encoding='utf-8-sig').read()

def insert_obj(text, section, entries):
    if not entries: return text
    m = re.search(r'("%s"\s*:\s*)\{' % re.escape(section), text)
    if not m: raise SystemExit('section not found: ' + section)
    payload = '\n' + ''.join('        %s: %s,\n' % (json.dumps(k), json.dumps(v)) for k, v in entries.items())
    return text[:m.end()] + payload + text[m.end():]

text = insert_obj(text, 'Opening Books', new_obs)
text = insert_obj(text, 'Partial Players', new_pps)
text = insert_obj(text, 'Move Iterators', new_mis)
text = insert_obj(text, 'Players', new_players)
m = re.search(r'("Benchmarks"\s*:\s*)\[', text)
text = text[:m.end()] + '\n' + ''.join('    ' + json.dumps(b) + ',\n' for b in tblocks) + text[m.end():]

chk = re.sub(r'/\*.*?\*/', '', text, flags=re.S); chk = re.sub(r'(^|[^:])//.*$', r'\1', chk, flags=re.M)
parsed = json.loads(chk)  # validate
open(DAVE, 'w', encoding='utf-8').write(text)
print('Added STRONG-OB (50-entry) native chain. LiveOpeningBook2 entries:', len(parsed['Opening Books']['LiveOpeningBook2']))
for n in new_players: print('  player', n, '-> root', parsed['Players'][n]['RootMoveIterator'])
print('  tournament blocks:', [b['name'] for b in tblocks], '| active run:true now:', [b['name'] for b in parsed['Benchmarks'] if b.get('run')])
print('  backup:', DAVE + '.preob2.bak')
