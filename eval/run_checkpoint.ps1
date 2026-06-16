# =============================================================================
# run_checkpoint.ps1 — the CAMPAIGN'S answer-producing measurement (v4, 2026-06-16).
#
# Run every 3-5 iterations (and before any AWS go/no-go). Per-iteration evals
# are collapse screens only; THIS is where "did RL improve the net?" gets
# actually measured:
#
#   1. powered ORIGIN eval (general pool @ -Rounds, default 192, rounds/block =
#      384 games each = 192 × 2 colour-swapped seats): current lineage head vs
#      RL_Eval_origin (PERMANENTLY v221 — never repointed; drl-03). The relative-
#      drift anchor: the powered CI (~±2.5pp) is the campaign's go/no-go evidence,
#      not per-iteration cells.
#   2. MASTERBOT absolute trend (general @ $ckptRounds rounds = 384 games):
#      lineage head vs MasterBot_SWF (AB Playout, NO NeuralNet). Tracks whether
#      RL is improving absolute strength.
#   3. B8 cumulative-forgetting guard: the lineage's human-val accuracy must
#      stay within 5pp of the ORIGIN constant (the per-iteration 4.5 tripwire
#      compares vs the moving parent, so drift could ratchet ~3pp per promotion
#      without ever tripping — this closes that leak against the fixed v221 value).
#
# Evaluates the CURRENT PARENT (the promoted lineage head) by default; pass
# -CandidateBin/-CandidatePt to checkpoint an unpromoted candidate instead.
#
# NOTE: Set-BlockRounds bumps RL_PoL_origin and RL_PoL_masterbot to $ckptRounds
# for the duration of the eval and restores them in a finally block. A host-kill
# that skips finally would leave config.txt at $ckptRounds (preflight check
# check_anchor_blocks would then reject it). Manual recovery: restore "rounds"
# in those two blocks to the frozen value ($frozen.anchor_blocks.RL_PoL_origin.rounds).
# =============================================================================
param(
    [int]$Iteration = 0,                 # labelling only (manifest name suffix); 0 = timestamp
    [string]$CandidateBin = '',          # default: the frozen parent_bin (the lineage head)
    [string]$CandidatePt = '',           # default: the frozen parent_pt
    [ValidateRange(1, 100000)][int]$Rounds = 192   # rounds per anchor block for the powered checkpoint eval
                                         # (192 rounds * 2 seats = 384 games per anchor at default Threads:8)
)
$ErrorActionPreference = 'Stop'

$dave   = 'c:/libraries/PrismataAI-dave-master'
$bin    = "$dave/bin"
$config = "$bin/asset/config/config.txt"
$repo   = 'c:/libraries/PrismataAI'
$eval   = "$repo/eval"
$frozenPath = "$eval/campaign_frozen.json"
$ledger     = "$eval/campaign_log.jsonl"
$frozen = Get-Content -Raw $frozenPath | ConvertFrom-Json

$ckptRounds = $Rounds

if (-not $CandidateBin) { $CandidateBin = $frozen.parent_bin }
if (-not $CandidatePt)  { $CandidatePt = "$repo/$($frozen.parent_pt)" }
$originBin = $frozen.origin_bin
$label = if ($Iteration -gt 0) { "$Iteration" } else { "ckpt_$(Get-Date -Format yyyyMMdd_HHmm)" }

Write-Host "=== CHECKPOINT: $CandidateBin (lineage head) vs origin $originBin ==="

# --- 0) preflight ---------------------------------------------------------------
$env:PYTHONIOENCODING = 'utf-8'
python "$eval/preflight_config.py" --config $config --frozen $frozenPath
if ($LASTEXITCODE -ne 0) { throw "preflight FAILED — fix before checkpointing" }

# --- B8) cumulative-forgetting guard vs the ORIGIN constant ----------------------
Write-Host "`n[B8] lineage val-acc vs the origin constant"
$valFile = "$repo/$($frozen.tripwire_val_file)"
$out = python "$eval/eval_deepsets_h5.py" --model $CandidatePt --val-file $valFile | Out-String
if ($LASTEXITCODE -ne 0 -or $out -notmatch 'val_acc\s*=\s*(\d+(?:\.\d+)?)\s*%') { Write-Host $out; throw "could not measure lineage val-acc" }
$acc = [double]::Parse($Matches[1], [System.Globalization.CultureInfo]::InvariantCulture)
$originAcc = [double]$frozen.origin_val_acc_pct
Write-Host "lineage val_acc = $acc%   origin (v221, fixed) = $originAcc%"
if ($acc -lt ($originAcc - 5.0)) {
    Write-Host "*** B8 FORGETTING GUARD: lineage is >5pp below the ORIGIN on human val ($acc% vs $originAcc%). ***"
    Write-Host "*** Pre-registered response: RAISE the rehearsal fraction (training/rl_data.py schedule + frozen train_schedule) — see rl_data.rehearsal_fraction_for_iter docstring. Recording, not aborting. ***"
}

# --- helpers: Set-PlayerWeights + Set-BlockRounds --------------------------------
# Both do surgical in-place regex rewrites (NOT json.load->json.dump) to minimise
# spurious config diffs; both validate strict JSON before committing the edit.
function Set-PlayerWeights {
    param([string]$Player, [string]$Value)
    $py = @'
import json, os, re, sys, tempfile
path, name, value = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()
key = re.compile(r'^\s*"' + re.escape(name) + r'"\s*:\s*\{')
field = re.compile(r'("WeightsFile"\s*:\s*")[^"]*(")')
found = False
for i, ln in enumerate(lines):
    if key.search(ln):
        new_ln, n = field.subn(lambda m: m.group(1) + value + m.group(2), ln, count=1)
        if n == 0: sys.exit("no WeightsFile on player '%s'" % name)
        lines[i] = new_ln; found = True; break
if not found: sys.exit("player '%s' not found" % name)
text = "".join(lines)
json.loads(text)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".cfgtmp")
with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
    f.write(text)
os.replace(tmp, path)
print("cfg weights %s -> %s" % (name, value))
'@
    python -c $py $config $Player $Value
    if ($LASTEXITCODE -ne 0) { throw "Set-PlayerWeights $Player failed" }
}

function Set-BlockRounds {
    param([string]$Block, [int]$Value)
    $py = @'
import json, os, re, sys, tempfile
path, name, value = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()
target = re.compile(r'"name"\s*:\s*"' + re.escape(name) + r'"')
field  = re.compile(r'("rounds"\s*:\s*)\d+')
found = False
for i, ln in enumerate(lines):
    if target.search(ln) and '"Tournament"' in ln:
        new_ln, n = field.subn(lambda m: m.group(1) + str(int(value)), ln, count=1)
        if n == 0: sys.exit("no rounds field on block '%s'" % name)
        lines[i] = new_ln; found = True
if not found:
    sys.exit("Tournament block '%s' not found in %s" % (name, path))
text = "".join(lines)
json.loads(text)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".cfgtmp")
with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
    f.write(text)
os.replace(tmp, path)
print("cfg rounds %s -> %s" % (name, value))
'@
    python -c $py $config $Block "$Value"
    if ($LASTEXITCODE -ne 0) { throw "Set-BlockRounds $Block failed" }
}

# Frozen rest-value for each anchor block (read once before we modify anything).
$restRoundsOrigin    = [int]$frozen.anchor_blocks.RL_PoL_origin.rounds
$restRoundsMasterbot = [int]$frozen.anchor_blocks.RL_PoL_masterbot.rounds

Write-Host "`n[checkpoint] powered origin + masterbot eval ($ckptRounds rounds each = $($ckptRounds * 2) games per anchor)"
try {
    Set-PlayerWeights -Player RL_Eval -Value $CandidateBin
    # NOTE: --parent-weights deliberately OMITTED — at a lineage checkpoint the candidate IS
    # the parent (same bin), and run_eval refuses candidate==parent; the origin opponent's
    # provenance is checked via --origin-weights instead.

    # Bump both anchor blocks to the powered round count for this checkpoint.
    Set-BlockRounds -Block RL_PoL_origin    -Value $ckptRounds
    Set-BlockRounds -Block RL_PoL_masterbot -Value $ckptRounds

    python "$eval/run_eval.py" --iteration $label --weights $CandidateBin `
        --origin-weights $originBin `
        --dave-bin $bin `
        --anchors origin masterbot --pools general `
        --out "$eval/manifests"
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py (checkpoint) exited $LASTEXITCODE" }
}
finally {
    # Always restore rounds AND weights — a crash mid-eval must not leave the config
    # at $ckptRounds (preflight's check_anchor_blocks would reject it on the next run).
    Set-BlockRounds -Block RL_PoL_origin    -Value $restRoundsOrigin
    Set-BlockRounds -Block RL_PoL_masterbot -Value $restRoundsMasterbot
    Set-PlayerWeights -Player RL_Eval -Value $frozen.parent_bin
    Write-Host "RL_PoL_origin rounds restored -> $restRoundsOrigin"
    Write-Host "RL_PoL_masterbot rounds restored -> $restRoundsMasterbot"
    Write-Host "RL_Eval.WeightsFile restored -> $($frozen.parent_bin)"
}

$manifest = "$eval/manifests/eval_iter_$label.json"
@{ ts = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); event = 'checkpoint'; label = "$label";
   lineage_bin = $CandidateBin; lineage_val_acc = $acc; origin_val_acc = $originAcc } |
    ConvertTo-Json -Compress | Add-Content -LiteralPath $ledger

Write-Host "`n=== checkpoint complete ==="
Write-Host "Manifest : $manifest"
Write-Host "READ: anchors.origin.pools.general (the powered lineage-vs-origin number, ~±2.5pp at 384g) and"
Write-Host "      anchors.masterbot.pools.general (absolute-strength trend vs MasterBot_SWF). Record"
Write-Host "      both + the B8 line in eval/campaign_log.md. THIS number — not per-iteration collapse"
Write-Host "      cells — is the campaign's go/no-go evidence (kill criteria = flat across checkpoints, §3)."
