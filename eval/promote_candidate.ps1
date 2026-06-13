# =============================================================================
# promote_candidate.ps1 — THE promotion mechanism (C1/ops-promote-01, 2026-06-13).
#
# Replaces the manual 6-edit/2-repo procedure whose worst failure modes
# (consistent-but-wrong repoint; parent_pt/parent_bin generation mismatch; a
# same-K re-run clobbering the promoted parent's .bin) all passed the old
# name-only preflight. This script makes the parent pin CONTENT-addressed:
#
#   1. verify the candidate: manifest exists, verdict != REJECT (override -Force);
#   2. sha-verify the lineage: a FRESH re-export of the candidate .pt must be
#      byte-identical to the on-disk candidate .bin (catches a stale/clobbered bin);
#   3. update eval/campaign_frozen.json: parent_bin, parent_pt, parent_bin_sha256,
#      parent_val_acc_pct (caches the 4.5 tripwire's parent side);
#   4. repoint the FOUR parent-pinned players (RL_Eval, RL_Eval_iter0, RL_SelfPlay,
#      RL_Narrow) — NEVER RL_Eval_origin (permanently v221, drl-03);
#   5. re-run the full preflight (must pass);
#   6. copy the promoted .bin into the MAIN repo's tracked bin/asset/config/;
#   7. run the promotion-time NARROW anchor (J3: 256 games, iterator-only contrast
#      with the NEW parent net on both sides) unless -SkipNarrow;
#   8. append the ledger entry and PRINT the two per-repo commit commands
#      (commits stay human-reviewed).
#
# PROMOTION POLICY (J2, frozen): promote-unless-harm — run this for every
# candidate whose iteration ended verdict!=REJECT with the tripwire quiet and no
# REPRODUCED tactical regression. Record the decision in eval/campaign_log.md.
# =============================================================================
param(
    [Parameter(Mandatory = $true)][int]$K,
    [switch]$Force,        # promote despite verdict==REJECT (you had better have a reason)
    [switch]$SkipNarrow    # skip the promotion-time narrow anchor run
)
$ErrorActionPreference = 'Stop'

$dave   = 'c:/libraries/PrismataAI-dave-master'
$bin    = "$dave/bin"
$config = "$bin/asset/config/config.txt"
$repo   = 'c:/libraries/PrismataAI'
$eval   = "$repo/eval"
$train  = "$repo/training"
$frozenPath = "$eval/campaign_frozen.json"
$ledger     = "$eval/campaign_log.jsonl"

$candBin     = "neural_weights_rl_iter$K.bin"
$candBinPath = "$bin/asset/config/$candBin"
$candPtRel   = "training/models/rl_iter_$K/final_model.pt"
$candPt      = "$repo/$candPtRel"
$manifest    = "$eval/manifests/eval_iter_$K.json"

foreach ($f in @($candBinPath, $candPt, $manifest)) {
    if (-not (Test-Path $f)) { throw "promotion prerequisite missing: $f" }
}

# --- 1) verdict check --------------------------------------------------------
$m = Get-Content -Raw $manifest | ConvertFrom-Json
if ($m.verdict -eq 'REJECT' -and -not $Force) {
    throw "iteration $K verdict is REJECT (proven worse than the parent on the general pool) — refusing to promote. Use -Force only with a written justification in eval/campaign_log.md."
}
if ($m.verdict -ne 'REVIEW' -and -not $Force) {
    throw "iteration $K verdict is '$($m.verdict)' (expected REVIEW) — the eval did not complete; re-run stage 7 (run_iteration.ps1 -K $K -ResumeFrom 7) first."
}
Write-Host "iteration $K verdict: $($m.verdict)  (general: $($m.verdict_inputs.general_wr_ci))"

# --- 2) sha-verified lineage: fresh re-export of the .pt must equal the .bin --
Write-Host "sha-verifying candidate lineage (re-export $candPtRel)..."
$tmpBin = [System.IO.Path]::GetTempFileName()
$env:PYTHONIOENCODING = 'utf-8'
python "$train/export_weights_v2.py" $candPt $tmpBin --property-table "$train/property_table.json"
if ($LASTEXITCODE -ne 0) { Remove-Item $tmpBin -ErrorAction SilentlyContinue; throw "re-export failed" }
$shaFresh = (Get-FileHash -Algorithm SHA256 $tmpBin).Hash.ToLower()
$shaDisk  = (Get-FileHash -Algorithm SHA256 $candBinPath).Hash.ToLower()
Remove-Item $tmpBin -ErrorAction SilentlyContinue
if ($shaFresh -ne $shaDisk) {
    throw "LINEAGE MISMATCH: fresh export of $candPtRel = $shaFresh but on-disk $candBin = $shaDisk — the bin was clobbered (same-K re-run?) or belongs to a different training run. Re-run stage 4 (run_iteration.ps1 -K $K -ResumeFrom 4) and retry."
}
Write-Host "lineage OK: $candBin sha256 $shaDisk"

# --- 3) candidate val-acc (cached as the next parent's tripwire side) ---------
$frozen = Get-Content -Raw $frozenPath | ConvertFrom-Json
$valFile = "$repo/$($frozen.tripwire_val_file)"
$out = python "$eval/eval_deepsets_h5.py" --model $candPt --val-file $valFile | Out-String
if ($LASTEXITCODE -ne 0 -or $out -notmatch 'val_acc\s*=\s*(\d+(?:\.\d+)?)\s*%') { Write-Host $out; throw "could not measure candidate val-acc" }
$candAcc = [double]::Parse($Matches[1], [System.Globalization.CultureInfo]::InvariantCulture)
Write-Host "candidate val-acc on $($frozen.tripwire_val_file): $candAcc%"

# --- 4) update campaign_frozen.json (the ONLY legal parent-pin mechanism, J7) --
$frozen.parent_bin = $candBin
$frozen.parent_pt = $candPtRel
$frozen.parent_bin_sha256 = $shaDisk
if ($frozen.PSObject.Properties.Name -contains 'parent_val_acc_pct') {
    $frozen.parent_val_acc_pct = $candAcc
} else {
    $frozen | Add-Member -NotePropertyName parent_val_acc_pct -NotePropertyValue $candAcc
}
$tmp = "$frozenPath.tmp"
$frozen | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $tmp -Encoding utf8
Move-Item -Force $tmp $frozenPath
Write-Host "campaign_frozen.json: parent -> $candBin (sha-pinned)"

# --- 5) repoint the FOUR parent-pinned players (never RL_Eval_origin) ---------
$py = @'
import json, os, re, sys, tempfile
path, value = sys.argv[1], sys.argv[2]
players = ("RL_Eval", "RL_Eval_iter0", "RL_SelfPlay", "RL_Narrow")
with open(path, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()
field = re.compile(r'("WeightsFile"\s*:\s*")[^"]*(")')
done = set()
for name in players:
    key = re.compile(r'^\s*"' + re.escape(name) + r'"\s*:\s*\{')
    for i, ln in enumerate(lines):
        if key.search(ln):
            new_ln, n = field.subn(lambda m: m.group(1) + value + m.group(2), ln, count=1)
            if n == 0: sys.exit("no WeightsFile on player '%s'" % name)
            lines[i] = new_ln; done.add(name); break
missing = set(players) - done
if missing: sys.exit("players not found: %s" % sorted(missing))
text = "".join(lines)
json.loads(text)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".cfgtmp")
with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
    f.write(text)
os.replace(tmp, path)
print("repointed %s -> %s" % (", ".join(players), value))
'@
python -c $py $config $candBin
if ($LASTEXITCODE -ne 0) { throw "config repoint failed — campaign_frozen.json is already updated; fix config.txt manually and re-run the preflight" }

# --- 6) full preflight must pass on the new identity ---------------------------
python "$eval/preflight_config.py" --config $config --frozen $frozenPath
if ($LASTEXITCODE -ne 0) { throw "preflight FAILED after promotion edits — reconcile before doing anything else" }

# --- 7) tracked copy in the MAIN repo ------------------------------------------
Copy-Item $candBinPath "$repo/bin/asset/config/$candBin" -Force
Write-Host "tracked copy -> $repo/bin/asset/config/$candBin"

# --- 8) promotion-time NARROW anchor (J3: iterator-only contrast, 256 games) ---
if (-not $SkipNarrow) {
    Write-Host "running the promotion-time narrow anchor (RL_Eval[IGsubset] vs RL_Narrow[narrow], same new-parent net)..."
    python "$eval/run_eval.py" --iteration $K --weights $candBin `
        --dave-bin $bin --anchors narrow --pools forced general `
        --out "$eval/manifests"
    if ($LASTEXITCODE -ne 0) { throw "narrow anchor run failed (manifest eval_iter_$K.json may be partially overwritten — it now reflects the narrow run)" }
    Write-Host "NOTE: the narrow run REWROTE eval_iter_$K.json with anchors_requested=[narrow]; the original iter0 manifest content is preserved only in git history — commit before promoting next time if you need both."
}

# --- 9) ledger + the two human-reviewed commits ---------------------------------
$entry = @{ ts = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'); K = $K; event = 'promote';
            new_parent_bin = $candBin; new_parent_sha256 = $shaDisk; val_acc_pct = $candAcc } | ConvertTo-Json -Compress
$entry | Add-Content -LiteralPath $ledger

Write-Host "`n=== PROMOTED: iteration $K candidate is the new parent ==="
Write-Host "Now: 1) add the human entry to eval/campaign_log.md (decision + reasoning);"
Write-Host "     2) commit BOTH repos so the campaign identity stays one tuple:"
Write-Host "        cd $repo ; git add eval/campaign_frozen.json eval/campaign_log.md eval/campaign_log.jsonl bin/asset/config/$candBin ; git commit -m 'rl: promote iter-$K candidate to parent (sha $($shaDisk.Substring(0,12)))'"
Write-Host "        cd $dave ; git add bin/asset/config/config.txt ; git commit -m 'rl: repoint parent pins to iter-$K candidate'"
Write-Host "     3) every 3-5 iterations: eval/run_checkpoint.ps1 (the powered origin eval)."
