# =============================================================================
# RL Self-Play — one-iteration driver (regime v4 "proof-of-life", 2026-06-14)
#
# Stages (display numbers kept stable):
#   0   structural preflight (eval/preflight_config.py — hard gate)
#   1   self-play export: ONE general block, one engine launch, Seed = base+K (J4)
#   1.5 archive sidecars + replays -> training/data/rl_iter_<K>/
#   2   concat shards -> vectorize -> H5 (provenance-stamped, C5)
#   3   RL fine-tune: warm-start, NO SWA, rehearsal 0.10 on the ELITE corpus (J1)
#   4   export candidate .bin
#   4.5 val-acc tripwire (candidate vs parent on the capped held-out val)
#   4.6 prediction-movement probe (B5 — the null-update detector; informational)
#   5   export-parity GATE (PyTorch <-> C++)
#   (6  tactical suite REMOVED in v4 — IG-specific; dropped with the IG axis)
#   7   per-iteration eval: origin + masterbot anchors (general pool). The origin
#       anchor is the COLLAPSE/abort signal (collapse iff its win-rate vs the
#       PERMANENT origin reference < abort_winrate_vs_origin). No REJECT/REVIEW.
#   8   action coverage (general slice; telemetry, non-fatal) + dashboard
#
# PROMOTION POLICY (v4, frozen): promote-unless-collapse.
#   Phase 0 (fixed generator): do NOT promote.
#   Phase 1: promote every candidate UNLESS the run aborted — collapse (win-rate
#   vs origin below abort_winrate_vs_origin) OR the 4.5 val-acc tripwire fired.
# Promotion = eval/promote_candidate.ps1 (a SEPARATE script; the driver never
# promotes). Per-iteration human record -> eval/campaign_log.md.
#
# -ResumeFrom <stage>: restart at a later stage after a downstream failure
# (stages 2+ reuse this K's already-archived artifacts; stage-1 re-runs are the
# expensive thing this exists to avoid). Each stage validates its prerequisites.
# =============================================================================
param(
    [int]$K = 1,        # RL iteration index
    [int]$N = 0,        # informational only; a nonzero -N differing from frozen_N throws
    [int]$Window = 0,   # replay-buffer window W; 0 => the FROZEN replay_window (a nonzero mismatch throws)
    [string]$ParentPt = '',  # parent checkpoint override (lineage bypass — printed loudly)
    [int]$ResumeFrom = 0     # 0 = full run; 2..8 = skip earlier stages (this K's artifacts must exist)
)
$ErrorActionPreference = 'Stop'

# --- Paths -------------------------------------------------------------------
$dave    = 'c:/libraries/PrismataAI-dave-master'
$bin     = "$dave/bin"
$config  = "$bin/asset/config/config.txt"
$repo    = 'c:/libraries/PrismataAI'
$train   = "$repo/training"
$eval    = "$repo/eval"
$tools   = "$repo/tools"

$selfplayDirGen = "$bin/asset/training/rl_general_v2"  # general slice (RL_SelfPlay_General) — v4's only block
$workDir     = "$train/data/rl_iter_$K"
$catJsonl    = "$workDir/selfplay_iter_$K.jsonl"
$h5          = "$workDir/selfplay_iter_$K.h5"
$modelDir    = "$train/models/rl_iter_$K"
$bestPt      = "$modelDir/final_model.pt"              # J1: NO SWA — final-epoch weights are the candidate
$candBin     = "neural_weights_rl_iter$K.bin"
$candBinPath = "$bin/asset/config/$candBin"
$frozenPath  = "$eval/campaign_frozen.json"
$frozenEarly = Get-Content -Raw $frozenPath | ConvertFrom-Json
$parentBin   = $frozenEarly.parent_bin
if (-not $parentBin) { throw "campaign_frozen.json has no parent_bin" }
$parityLiveGen    = "${selfplayDirGen}_parity"
$parityStatesLegacy = "$bin/asset/training/parity_states"  # pre-2026-06-12 shared dir — wiped only
$schema      = "$train/schema_v2.json"
$propTable   = "$train/property_table.json"
# J1/C6: rehearsal = the ELITE corpus; tripwire val = the capped held-out set.
# Both are FROZEN HP-tier knobs — read from campaign_frozen.json, never hardcoded.
$humanH5     = "$repo/$($frozenEarly.rehearsal_file)"
$humanValH5  = "$repo/$($frozenEarly.tripwire_val_file)"
$manifest    = "$eval/manifests/eval_iter_$K.json"
$ledger      = "$eval/campaign_log.jsonl"
$lockFile    = "$eval/.iteration.lock"

# --- Input validation (C4) ----------------------------------------------------
if ($K -lt 1) { throw "-K must be >= 1 (got $K)" }
if ($K -gt 1 -and -not (Test-Path "$train/data/rl_iter_$($K-1)")) {
    Write-Host "*** WARNING: rl_iter_$($K-1) does not exist — running K=$K with a gap in the window. Deliberate? ***"
}
$frozenW = [int]$frozenEarly.replay_window
if ($Window -eq 0) { $Window = $frozenW }
elseif ($Window -ne $frozenW) {
    throw "-Window $Window conflicts with frozen replay_window $frozenW — W is campaign identity (scale tier); change campaign_frozen.json deliberately instead."
}
if ($ResumeFrom -lt 0 -or $ResumeFrom -gt 8) { throw "-ResumeFrom must be 0..8" }

# --- Resolve the parent checkpoint (E1 + N-3: promotion-gated lineage) ---------
if (-not $ParentPt) {
    $ParentPt = $frozenEarly.parent_pt
    if (-not $ParentPt) { throw "campaign_frozen.json has no parent_pt" }
    if (-not [System.IO.Path]::IsPathRooted($ParentPt)) { $ParentPt = "$repo/$ParentPt" }
} else {
    Write-Host "*** -ParentPt OVERRIDE: warm-starting from $ParentPt (NOT the frozen parent_pt — lineage bypass; make sure this is deliberate) ***"
}
if (-not (Test-Path $ParentPt)) {
    throw "parent checkpoint not found: $ParentPt — the RL fine-tune must warm-start from its parent net (E1). Promote (eval/promote_candidate.ps1) or pass -ParentPt explicitly."
}
# ops-promote-01: the candidate bin name must never equal the frozen parent bin —
# stage 4's unconditional export would clobber the promoted parent's weights.
if ($candBin -eq $parentBin) {
    throw "candidate bin '$candBin' == frozen parent_bin — stage 4 would OVERWRITE the promoted parent. Wrong -K (re-running the iteration that was just promoted)?"
}

New-Item -ItemType Directory -Force -Path $workDir | Out-Null

# --- Append-only machine ledger (C4) ------------------------------------------
function Write-Ledger {
    param([hashtable]$Entry)
    $Entry['ts'] = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
    $Entry['K'] = $K
    ($Entry | ConvertTo-Json -Compress) | Add-Content -LiteralPath $ledger
}

# --- Surgical in-place config.txt edit (atomic: temp + os.replace, C9) --------
#   Edit-Config run        <Tournament-block> <true|false>
#   Edit-Config traversals <PlayerName>       <int>
#   Edit-Config weights    <PlayerName>       <file.bin>
#   Edit-Config seed       <Tournament-block> <int>          (J4 seed-from-K)
function Edit-Config {
    param([string]$Op, [string]$Name, [string]$Value)
    $py = @'
import json, os, re, sys, tempfile
path, op, name, value = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(path, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()
found = False
if op in ("run", "seed"):
    target = re.compile(r'"name"\s*:\s*"' + re.escape(name) + r'"')
    if op == "run":
        field = re.compile(r'("run"\s*:\s*)(true|false)')
        nv = "true" if value.lower() in ("true", "1", "yes") else "false"
        repl = lambda m: m.group(1) + nv
    else:
        field = re.compile(r'("Seed"\s*:\s*)\d+')
        repl = lambda m: m.group(1) + str(int(value))
    for i, ln in enumerate(lines):
        if target.search(ln) and '"Tournament"' in ln:
            new_ln, n = field.subn(repl, ln, count=1)
            if n == 0: sys.exit("no %s field on block '%s'" % (op, name))
            lines[i] = new_ln; found = True
else:
    key = re.compile(r'^\s*"' + re.escape(name) + r'"\s*:\s*\{')
    if op == "traversals":
        field, repl = re.compile(r'("MaxTraversals"\s*:\s*)\d+'), (lambda m: m.group(1) + str(int(value)))
    elif op == "weights":
        field, repl = re.compile(r'("WeightsFile"\s*:\s*")[^"]*(")'), (lambda m: m.group(1) + value + m.group(2))
    else:
        sys.exit("unknown op: " + op)
    for i, ln in enumerate(lines):
        if key.search(ln):
            new_ln, n = field.subn(repl, ln, count=1)
            if n == 0: sys.exit("no %s field on player '%s'" % (op, name))
            lines[i] = new_ln; found = True; break
if not found:
    sys.exit("target '%s' (%s) not found in %s" % (name, op, path))
text = "".join(lines)
json.loads(text)  # strict-JSON sanity BEFORE touching the live file
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".cfgtmp")
with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
    f.write(text)
os.replace(tmp, path)  # atomic on NTFS — a crash mid-edit cannot half-write the live config
print("cfg %s %s -> %s" % (op, name, value))
'@
    python -c $py $config $Op $Name $Value
    if ($LASTEXITCODE -ne 0) { throw "Edit-Config $Op $Name failed" }
}

# --- Held-out val-acc of a .pt checkpoint (stage 4.5 tripwire) -----------------
function Get-ValAcc {
    param([string]$Pt)
    $env:PYTHONIOENCODING = 'utf-8'
    $out = python "$eval/eval_deepsets_h5.py" --model $Pt --val-file $humanValH5 | Out-String
    if ($LASTEXITCODE -ne 0) { Write-Host $out; throw "eval_deepsets_h5.py exited $LASTEXITCODE for $Pt" }
    if ($out -notmatch 'val_acc\s*=\s*(\d+(?:\.\d+)?)\s*%') {
        Write-Host $out; throw "could not parse 'val_acc = NN.N%' from eval_deepsets_h5.py output for $Pt"
    }
    [double]::Parse($Matches[1], [System.Globalization.CultureInfo]::InvariantCulture)
}

# --- Driver lockfile (C3: no concurrent drivers/tools on the live config) -----
if (Test-Path $lockFile) {
    $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    $content = Get-Content -Raw $lockFile -ErrorAction SilentlyContinue
    throw ("another iteration appears to be running (lock $lockFile, age {0:N0} min, contents: {1}). " -f $age.TotalMinutes, $content) +
          "If that run is dead, delete the lock and re-run. NEVER run two drivers (or calibrate_n/matchup tools) against the live config at once."
}
"K=$K pid=$PID started=$(Get-Date -Format o)" | Set-Content -LiteralPath $lockFile

$stageReached = 0
$transcript = "$workDir/iteration_${K}_$(Get-Date -Format yyyyMMdd_HHmmss).log"
Start-Transcript -Path $transcript | Out-Null
Write-Ledger @{ event = 'start'; resume_from = $ResumeFrom; parent_bin = $parentBin; parent_pt = $ParentPt }

try {

# -----------------------------------------------------------------------------
# 0) Structural preflight — single source of truth: eval/preflight_config.py.
# -----------------------------------------------------------------------------
Write-Host "`n[0/8] structural preflight (eval/preflight_config.py)"
python "$eval/preflight_config.py" --config $config --frozen $frozenPath
if ($LASTEXITCODE -ne 0) {
    throw "structural preflight FAILED (eval/preflight_config.py exit $LASTEXITCODE) — fix every FAIL line above before running an iteration."
}
$frozen = Get-Content -Raw $frozenPath | ConvertFrom-Json
if ($N -gt 0 -and $N -ne [int]$frozen.frozen_N) {
    throw "-N $N conflicts with frozen_N $($frozen.frozen_N) in campaign_frozen.json — the tuple is frozen; reconcile deliberately instead of overriding."
}
$N = [int]$frozen.frozen_N

Write-Host "=== RL iteration $K  (N=$N, W=$Window, resume_from=$ResumeFrom) ==="

# -----------------------------------------------------------------------------
# 1) Self-play: ONE general block (v4 — the forced-Hotel block was dropped with
#    the IG axis), one engine launch, Seed derived base+K (J4: fresh card sets
#    every iteration, reproducible per iteration; base restored in the finally so
#    the config rests at the preflight-asserted value). Engine output teed to
#    selfplay.log (C9).
# -----------------------------------------------------------------------------
if ($ResumeFrom -le 1) {
$stageReached = 1
$selfplayBlock = $frozen.selfplay_block
$seedBase    = [int]$frozen.selfplay_seed_base
$seedGeneral = $seedBase + $K
Write-Host "`n[1/8] self-play ($selfplayBlock Seed=$seedGeneral -> $selfplayDirGen)"
if (Test-Path $selfplayDirGen) { Remove-Item "$selfplayDirGen/selfplay_*.jsonl" -ErrorAction SilentlyContinue }
foreach ($pd in @($parityLiveGen, $parityStatesLegacy)) {
    if (Test-Path $pd) { Remove-Item "$pd/sp_*.json","$pd/sp_*.json.gz" -ErrorAction SilentlyContinue }
}
$replayLiveGen = "$bin/asset/replays/rl_selfplay_general"
if ((Test-Path $replayLiveGen) -and (Get-ChildItem -Path $replayLiveGen -Filter 'game_*.json.gz' -ErrorAction SilentlyContinue)) {
    $orphanDir = "$train/data/_orphans/replays_$(Get-Date -Format yyyyMMdd_HHmmss)_$(Split-Path $replayLiveGen -Leaf)"
    New-Item -ItemType Directory -Force -Path $orphanDir | Out-Null
    Move-Item "$replayLiveGen/game_*.json.gz" $orphanDir
    Write-Host "moved leftover replays from $replayLiveGen -> $orphanDir (crashed prior run?)"
}
$selfplayLog = "$workDir/selfplay_$(Get-Date -Format yyyyMMdd_HHmmss).log"
try {
    Edit-Config -Op seed -Name $selfplayBlock -Value $seedGeneral
    Edit-Config -Op run -Name $selfplayBlock -Value true
    Push-Location $bin
    try {
        & "$bin/Prismata_Testing.exe" 2>&1 | Tee-Object -FilePath $selfplayLog
        if ($LASTEXITCODE -ne 0) { throw "Prismata_Testing.exe (self-play) exited $LASTEXITCODE (log: $selfplayLog)" }
    }
    finally {
        Pop-Location
    }
}
finally {
    Edit-Config -Op run -Name $selfplayBlock -Value false
    Edit-Config -Op seed -Name $selfplayBlock -Value $seedBase
}
$warnings = @(Select-String -Path $selfplayLog -Pattern 'WARNING:' -ErrorAction SilentlyContinue)
if ($warnings) {
    Write-Host "*** $($warnings.Count) engine WARNING line(s) during self-play (see $selfplayLog): ***"
    $warnings | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.Line)" }
}

# -----------------------------------------------------------------------------
# 1.5) Archive this iteration's state artifacts.
# -----------------------------------------------------------------------------
Write-Host "`n[1.5/8] archive sidecars + replays -> $workDir"
$parityArchive = "$workDir/parity_states"
$staleArchives = @()
if ((Test-Path $parityArchive) -and (Get-ChildItem -Path "$parityArchive/*" -Include 'sp_*.json','sp_*.json.gz' -ErrorAction SilentlyContinue)) { $staleArchives += $parityArchive }
$replayArchiveGen = "$workDir/replays/general"
if ((Test-Path $replayArchiveGen) -and (Get-ChildItem -Path $replayArchiveGen -Filter 'game_*.json.gz' -ErrorAction SilentlyContinue)) { $staleArchives += $replayArchiveGen }
if ($staleArchives) {
    $aside = "$train/data/_orphans/rl_iter_${K}_superseded_$(Get-Date -Format yyyyMMdd_HHmmss)"
    New-Item -ItemType Directory -Force -Path $aside | Out-Null
    foreach ($d in $staleArchives) {
        $leaf = ($d -replace [regex]::Escape($workDir), '') -replace '^[/\\]', '' -replace '[/\\]', '_'
        Move-Item $d "$aside/$leaf"
    }
    Write-Host "prior attempt's archive for iteration $K moved aside -> $aside"
}
New-Item -ItemType Directory -Force -Path $parityArchive | Out-Null
$sidecarFiles = @(Get-ChildItem -Path "$parityLiveGen/*" -Include 'sp_*.json.gz','sp_*.json' -ErrorAction SilentlyContinue)
foreach ($f in $sidecarFiles) { Move-Item $f.FullName "$parityArchive/general_$($f.Name)" }
$sidecarCount = $sidecarFiles.Count
if ($sidecarCount -eq 0) { throw "no parity sidecars (sp_*.json.gz) in $parityLiveGen after self-play — exporter regression, or exportTrainingV2 drifted in config.txt?" }
New-Item -ItemType Directory -Force -Path $replayArchiveGen | Out-Null
if ((Test-Path $replayLiveGen) -and (Get-ChildItem -Path $replayLiveGen -Filter 'game_*.json.gz' -ErrorAction SilentlyContinue)) {
    Move-Item "$replayLiveGen/game_*.json.gz" $replayArchiveGen
} else {
    throw "no replays in $replayLiveGen (general slice) — saveReplays missing from the config block, or serializer failure (check $selfplayLog for [ReplaySerializer] lines)"
}
Write-Host ("archived: {0} sidecars; replays general={1}" -f `
    $sidecarCount, `
    @(Get-ChildItem -Path $replayArchiveGen -Filter 'game_*.json.gz' -ErrorAction SilentlyContinue).Count)
} else {
    $parityArchive = "$workDir/parity_states"
    Write-Host "`n[1/8 + 1.5/8] SKIPPED (resume_from=$ResumeFrom) — reusing this K's archived artifacts"
    if (-not (Test-Path $parityArchive)) { throw "-ResumeFrom $ResumeFrom but $parityArchive does not exist — this K was never generated; run without -ResumeFrom" }
}

# -----------------------------------------------------------------------------
# 2) Concat V2 shards (the general export dir) -> one JSONL -> vectorize -> H5.
#    The H5 carries provenance stamps (C5): parent sha, tuple hash, slice counts.
# -----------------------------------------------------------------------------
if ($ResumeFrom -le 2) {
$stageReached = 2
Write-Host "`n[2/8] concat shards + vectorize -> $h5"
if ($ResumeFrom -le 1) {
    $shards = @(Get-ChildItem -Path $selfplayDirGen -Filter 'selfplay_*.jsonl' | Sort-Object Name)
    if (-not $shards) { throw "no selfplay_*.jsonl shards in $selfplayDirGen (general slice missing)" }
    if (Test-Path $catJsonl) { Remove-Item $catJsonl }
    foreach ($s in $shards) { Get-Content -LiteralPath $s.FullName | Add-Content -LiteralPath $catJsonl }
} elseif (-not (Test-Path $catJsonl)) {
    throw "-ResumeFrom 2 but $catJsonl does not exist and the live shards may belong to a NEWER run — re-run without -ResumeFrom"
}
python "$train/vectorize_v2.py" --input $catJsonl --output $h5 --schema $schema `
    --stamp-parent "$bin/asset/config/$parentBin" --stamp-frozen $frozenPath
if ($LASTEXITCODE -ne 0) { throw "vectorize_v2.py exited $LASTEXITCODE" }
} else {
    if (-not (Test-Path $h5)) { throw "-ResumeFrom $ResumeFrom but $h5 does not exist" }
    Write-Host "`n[2/8] SKIPPED (resume_from=$ResumeFrom)"
}

# -----------------------------------------------------------------------------
# 3) RL fine-tune (J1 re-freeze): warm-start from the frozen parent, NO SWA
#    (final-epoch weights are the candidate), rehearsal 0.10 from the ELITE
#    corpus, lr 1e-5, 6 epochs, seeded (training-06), num_workers 0.
#    Window membership is stamp-checked by train.py (C5).
# -----------------------------------------------------------------------------
if ($ResumeFrom -le 3) {
$stageReached = 3
Write-Host "`n[3/8] RL fine-tune (rl-mode, W=$Window, no-SWA) -> $modelDir"
$spFiles = @()
for ($i = [math]::Max(1, $K - $Window + 1); $i -le $K; $i++) {
    $cand = "$train/data/rl_iter_$i/selfplay_iter_$i.h5"
    if (Test-Path $cand) { $spFiles += $cand }
}
$ts = [int]$frozen.train_schedule.epochs
python "$train/train.py" --model deepsets --property-table $propTable `
    --train-file $spFiles[-1] --val-file $humanValH5 `
    --rl-mode --init-weights $ParentPt --selfplay-files @spFiles --human-file $humanH5 `
    --replay-window $Window --rl-iteration $K `
    --epochs $ts --lr $frozen.train_schedule.lr --no-swa `
    --seed (2026000 + $K) --num-workers 0 --device xpu `
    --output-dir $modelDir
if ($LASTEXITCODE -ne 0) { throw "train.py exited $LASTEXITCODE" }
if (-not (Test-Path $bestPt)) { throw "expected final-epoch model not found: $bestPt" }
} else {
    if (-not (Test-Path $bestPt)) { throw "-ResumeFrom $ResumeFrom but $bestPt does not exist" }
    Write-Host "`n[3/8] SKIPPED (resume_from=$ResumeFrom)"
}

# -----------------------------------------------------------------------------
# 4) Export the trained net to the C++ binary.
# -----------------------------------------------------------------------------
if ($ResumeFrom -le 4) {
$stageReached = 4
Write-Host "`n[4/8] export weights -> $candBinPath"
python "$train/export_weights_v2.py" $bestPt $candBinPath --property-table $propTable
if ($LASTEXITCODE -ne 0) { throw "export_weights_v2.py exited $LASTEXITCODE" }

# --- 4.5) Val-acc tripwire (E1-class canary) ---
Write-Host "`n[4.5/8] val-acc tripwire (held-out $humanValH5)"
$candAcc = Get-ValAcc $bestPt
if ($frozen.PSObject.Properties.Name -contains 'parent_val_acc_pct' -and $frozen.parent_val_acc_pct) {
    $parentAcc = [double]$frozen.parent_val_acc_pct   # cached at promotion time (C6) — saves a full val pass
    Write-Host "parent val_acc = $parentAcc% (cached in campaign_frozen.json)"
} else {
    $parentAcc = Get-ValAcc $ParentPt
    Write-Host "HINT: add `"parent_val_acc_pct`": $parentAcc to campaign_frozen.json (promote_candidate.ps1 does this) to skip recomputing it every iteration."
}
Write-Host "val_acc: candidate = $candAcc%  parent = $parentAcc%"
if ($candAcc -lt ($parentAcc - 3.0)) {
    throw "val-acc tripwire: candidate $candAcc% is more than 3.0pp below parent $parentAcc% — candidate trained badly (E1-class failure); aborting iteration."
}

# --- 4.6) Prediction-movement probe (B5 — informational, never gates) ---
Write-Host "`n[4.6/8] prediction-movement probe (candidate vs parent)"
python "$eval/prediction_movement.py" --candidate-pt $bestPt --parent-pt $ParentPt `
    --fixed-h5 $humanH5 --selfplay-h5 $h5 --out "$workDir/prediction_movement.json"
if ($LASTEXITCODE -ne 0) { throw "prediction_movement.py exited $LASTEXITCODE" }
Write-Host "RECORD the mean|dP| values in eval/campaign_log.md — a near-zero fixed-probe value means stage 3 produced a NULL update (rl-design-01)."
} else {
    if (-not (Test-Path $candBinPath)) { throw "-ResumeFrom $ResumeFrom but $candBinPath does not exist" }
    Write-Host "`n[4/8 + 4.5 + 4.6] SKIPPED (resume_from=$ResumeFrom)"
}

# -----------------------------------------------------------------------------
# 5) Export-parity GATE (PyTorch <-> C++ forward value).
# -----------------------------------------------------------------------------
if ($ResumeFrom -le 5) {
$stageReached = 5
Write-Host "`n[5/8] export-parity GATE"
python "$tools/parity/dump_value_batch.py" `
    --states-dir $parityArchive --weights $candBinPath --dave-bin $bin `
    --pt $bestPt --bin $candBinPath
if ($LASTEXITCODE -ne 0) { throw "export-parity GATE FAILED — aborting iteration" }
} else { Write-Host "`n[5/8] SKIPPED (resume_from=$ResumeFrom)" }

# -----------------------------------------------------------------------------
# (6 — REMOVED in v4) The O7 tactical suite was IG-specific and dropped with the
#    IG axis. No stage 6 runs.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 7) Per-iteration eval (v4 PoL): origin + masterbot anchors on the general pool.
#    The origin anchor pits the candidate vs the PERMANENT origin reference and
#    is the COLLAPSE/abort signal (collapse iff its win-rate < abort_winrate).
#    The masterbot anchor is the absolute-strength trend. No REJECT/REVIEW.
# -----------------------------------------------------------------------------
$collapsed = $false
if ($ResumeFrom -le 7) {
$stageReached = 7
Write-Host "`n[7/8] repoint RL_Eval -> $candBin + origin+masterbot anchor eval"
try {
    Edit-Config -Op weights -Name RL_Eval -Value $candBin
    python "$eval/run_eval.py" --iteration $K `
        --weights $candBin --origin-weights $($frozen.origin_bin) `
        --dave-bin $bin `
        --anchors origin masterbot --pools general --abort-winrate $($frozen.abort_winrate_vs_origin) `
        --out "$eval/manifests"
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py exited $LASTEXITCODE" }
}
finally {
    Edit-Config -Op weights -Name RL_Eval -Value $parentBin
    Write-Host "RL_Eval.WeightsFile restored -> $parentBin (F-07 guard)"
}
if (Test-Path $manifest) {
    $collapsed = [bool]((Get-Content -Raw $manifest | ConvertFrom-Json).collapse)
}
if ($collapsed) {
    Write-Host "`n*** COLLAPSE: win-rate vs origin below abort threshold ($($frozen.abort_winrate_vs_origin)) — candidate is NOT promotable this iteration ***"
}
} else { Write-Host "`n[7/8] SKIPPED (resume_from=$ResumeFrom)" }

# -----------------------------------------------------------------------------
# 8) Action coverage (general slice — TELEMETRY, non-fatal) + dashboard.
#    action_coverage is IG-specific; with the IG axis dropped it is watch-stat
#    only, so a failure here must NOT abort the iteration.
# -----------------------------------------------------------------------------
$stageReached = 8
Write-Host "`n[8/8] action coverage (telemetry) + dashboard"
try {
    python "$eval/action_coverage.py" `
        --selfplay-jsonl-dir $selfplayDirGen `
        --dave-exe "$bin/PrismataAI.exe" `
        --weights $candBin --battery "$eval/ig_battery" --manifest $manifest
    if ($LASTEXITCODE -ne 0) { Write-Host "*** action_coverage.py exited $LASTEXITCODE — telemetry only, continuing ***" }
} catch {
    Write-Host "*** action_coverage.py threw ($($_.Exception.Message)) — telemetry only, continuing ***"
}
python "$eval/render_dashboard.py"
if ($LASTEXITCODE -ne 0) { throw "render_dashboard.py exited $LASTEXITCODE" }

if ((-not $collapsed) -and (Test-Path $manifest)) {
    $collapsed = [bool]((Get-Content -Raw $manifest | ConvertFrom-Json).collapse)
}
Write-Ledger @{ event = 'complete'; stage_reached = $stageReached; collapse = $collapsed; candidate_bin = $candBin }

Write-Host "`n=== iteration $K complete ==="
Write-Host "Manifest : $manifest   (collapse: $collapsed)"
Write-Host "PROMOTION POLICY (v4, frozen): promote-unless-collapse."
Write-Host "  Phase 0 (fixed generator): do NOT promote."
Write-Host "  Phase 1   : promote unless collapse / val-acc tripwire fired"
Write-Host "             -> eval/promote_candidate.ps1 -K $K"
if ($collapsed) {
    Write-Host "  COLLAPSE  : win-rate vs origin below abort threshold — do NOT promote; record in eval/campaign_log.md"
}
Write-Host "Record this iteration in eval/campaign_log.md (template at the top of that file)."

}
catch {
    Write-Ledger @{ event = 'abort'; stage_reached = $stageReached; error = "$($_.Exception.Message)" }
    throw
}
finally {
    Remove-Item $lockFile -ErrorAction SilentlyContinue
    Stop-Transcript | Out-Null
}
