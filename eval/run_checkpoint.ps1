# =============================================================================
# run_checkpoint.ps1 — the CAMPAIGN'S answer-producing measurement (J2/J3, 2026-06-13).
#
# Run every 3-5 iterations (and before any AWS go/no-go). Per-iteration evals are
# harm screens; THIS is where "did RL improve the net?" actually gets measured:
#
#   1. powered ORIGIN eval: current parent lineage vs RL_Eval_origin (PERMANENTLY
#      v221 — never repointed; drl-03) — general 768 games across two seed panels
#      (~±3.5pp CI, ~80% power at +5pp) + forced 192 games (cumulative d_rl on the
#      IG axis);
#   2. STEAMAI yardstick (100-200 games, trajectory only);
#   3. B8 cumulative-forgetting guard: the candidate lineage's human-val accuracy
#      must stay within 5pp of the ORIGIN constant (the per-iteration 4.5 tripwire
#      compares vs the moving parent, so drift could ratchet ~3pp per promotion
#      without ever tripping — this closes that leak against the fixed v221 value).
#
# Evaluates the CURRENT PARENT (the promoted lineage head) by default; pass
# -CandidateBin/-CandidatePt to checkpoint an unpromoted candidate instead.
# =============================================================================
param(
    [int]$Iteration = 0,                 # labelling only (manifest name suffix); 0 = timestamp
    [string]$CandidateBin = '',          # default: the frozen parent_bin (the lineage head)
    [string]$CandidatePt = '',           # default: the frozen parent_pt
    [int]$SteamGames = 100,
    [switch]$SkipSteam
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

# --- origin + steam eval ---------------------------------------------------------
# RL_Eval carries the candidate (same pattern as run_iteration stage 7), restored in finally.
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

Write-Host "`n[checkpoint] origin eval (forced 192 + general 768 games) $(if (-not $SkipSteam) { '+ steam' })"
$steamArg = @()
if (-not $SkipSteam) { $steamArg = @('--run-steam', '--steam-games', "$SteamGames") }
try {
    Set-PlayerWeights -Player RL_Eval -Value $CandidateBin
    # NOTE: --parent-weights deliberately OMITTED — at a lineage checkpoint the candidate IS
    # the parent (same bin), and run_eval refuses candidate==parent; the origin opponent's
    # provenance is checked via --origin-weights instead.
    python "$eval/run_eval.py" --iteration $label --weights $CandidateBin `
        --origin-weights $originBin `
        --dave-bin $bin --orig-exe $frozen.masterbot2016_exe `
        --anchors origin --pools forced general @steamArg `
        --out "$eval/manifests"
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py (checkpoint) exited $LASTEXITCODE" }
}
finally {
    Set-PlayerWeights -Player RL_Eval -Value $frozen.parent_bin
    Write-Host "RL_Eval.WeightsFile restored -> $($frozen.parent_bin)"
}

$manifest = "$eval/manifests/eval_iter_$label.json"
@{ ts = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); event = 'checkpoint'; label = "$label";
   lineage_bin = $CandidateBin; lineage_val_acc = $acc; origin_val_acc = $originAcc } |
    ConvertTo-Json -Compress | Add-Content -LiteralPath $ledger

Write-Host "`n=== checkpoint complete ==="
Write-Host "Manifest : $manifest"
Write-Host "READ: anchors.origin.pools.general (the powered lineage-vs-v221 number, ~±3.5pp) and"
Write-Host "      anchors.origin.pools.forced (cumulative IG-axis d_rl). Record both + the B8 line"
Write-Host "      in eval/campaign_log.md. THIS number — not per-iteration REVIEW cells — is the"
Write-Host "      campaign's go/no-go evidence (kill criteria = flat across checkpoints, §3)."
