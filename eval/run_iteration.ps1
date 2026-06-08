# =============================================================================
# RL Self-Play — one-iteration driver (Task 14)
#
# DEFERRED — do not run until the "Run prerequisites" in eval/rl_campaign.md are
# satisfied (recommended_N + ε from calibrate_n.py; eval/calib_states/ +
# eval/ig_battery/ populated). iter-0 anchor = v221 on RL_Eval_iter0 (per the
# 2026-06-07 decision — NOT a random wide-untrained net); PrismataAI.exe.ORIG is
# installed in dave bin/.
#
# The gate (promote / reject / inconclusive) is a HUMAN decision on the eval
# manifest + dashboard — this driver only PRODUCES the manifest + dashboard and
# prints the §12 decision inputs. It does NOT auto-promote.
#
# This orchestrates already-built tools (it does NOT rebuild them):
#   self-play  : Prismata_Testing.exe over a run:true block in dave's config.txt
#   vectorize  : training/vectorize_v2.py
#   train      : training/train.py --rl-mode (Task 6)
#   export     : training/export_weights_v2.py
#   parity GATE: tools/parity/dump_value_batch.py   (abort on worst |Δ| >= 1e-3)
#   tactical   : eval/tactical_suite.py             (O7 leading indicator)
#   eval (3 anchors) : eval/run_eval.py
#   coverage   : eval/action_coverage.py
#   dashboard  : eval/render_dashboard.py
# =============================================================================
param(
    [int]$K = 1,        # RL iteration index
    [int]$N = 0,        # self-play MaxTraversals; 0 => auto-read recommended_N from eval/n_calibration.json (pass -N for a smoke)
    [int]$Window = 5    # replay-buffer window W
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

# Self-play export dir for the RL_Step2 block (exportTrainingV2 target in config.txt).
$selfplayDir = "$bin/asset/training/rl_step2_v2"
# Where this iteration's H5 + concatenated JSONL land.
$workDir     = "$train/data/rl_iter_$K"
$catJsonl    = "$workDir/selfplay_iter_$K.jsonl"
$h5          = "$workDir/selfplay_iter_$K.h5"
$modelDir    = "$train/models/rl_iter_$K"
# SWA model (since --swa-start-epoch 3 < --epochs 6, train.py writes swa_model.pt).
$bestPt      = "$modelDir/swa_model.pt"
$candBin     = "neural_weights_rl_iter$K.bin"          # filename only — resolved under bin/asset/config
$candBinPath = "$bin/asset/config/$candBin"
$parentBin   = "neural_weights_mixed_v221.bin"          # current promoted net (gating parent / manifest label)
$origExe     = "$bin/PrismataAI.exe.ORIG"               # STEAMAI baseline (run_eval contamination assert)
$parityStates = "$bin/asset/training/parity_states"     # native GameState sidecar (sp_*.json) from self-play
$schema      = "$train/schema_v2.json"
$propTable   = "$train/property_table.json"
$humanH5     = "$train/data/human_1800_v2.h5"
$manifest    = "$eval/manifests/eval_iter_$K.json"

New-Item -ItemType Directory -Force -Path $workDir | Out-Null

# --- Surgical in-place config.txt edit -------------------------------------
# Mirrors calibrate_n.set_block_run: a LINE-LEVEL regex rewrite of the single matching line
# (NOT a json.load->json.dump reserialize, which would reformat every block and produce a huge
# spurious diff). Re-parses the whole file as strict JSON afterwards so a bad edit fails loudly.
#   Edit-Config run        <Tournament-block> <true|false>
#   Edit-Config traversals <PlayerName>       <int>
#   Edit-Config weights    <PlayerName>       <file.bin>
function Edit-Config {
    param([string]$Op, [string]$Name, [string]$Value)
    $py = @'
import json, re, sys
path, op, name, value = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(path, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()
found = False
if op == "run":
    target = re.compile(r'"name"\s*:\s*"' + re.escape(name) + r'"')
    run_re = re.compile(r'("run"\s*:\s*)(true|false)')
    nv = "true" if value.lower() in ("true", "1", "yes") else "false"
    for i, ln in enumerate(lines):
        if target.search(ln) and '"Tournament"' in ln:
            lines[i] = run_re.sub(lambda m: m.group(1) + nv, ln, count=1); found = True
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
with open(path, "w", encoding="utf-8", newline="") as f:
    f.writelines(lines)
with open(path, "r", encoding="utf-8-sig") as f:
    json.load(f)  # strict-JSON sanity
print("cfg %s %s -> %s" % (op, name, value))
'@
    python -c $py $config $Op $Name $Value
    if ($LASTEXITCODE -ne 0) { throw "Edit-Config $Op $Name failed" }
}

# --- Resolve self-play N (refuse the un-calibrated placeholder) --------------
if ($N -le 0) {
    $ncal = "$eval/n_calibration.json"
    if (-not (Test-Path $ncal)) {
        throw "N not calibrated: run eval/calibrate_n.py (writes eval/n_calibration.json), then re-run; or pass -N <int> explicitly for a smoke."
    }
    $recN = (Get-Content -Raw $ncal | ConvertFrom-Json).recommended_N
    if (-not $recN) { throw "n_calibration.json has no recommended_N (no N passed the non-degeneracy check) — pass -N explicitly or re-sweep." }
    $N = [int]$recN
    Write-Host "N resolved from $ncal : recommended_N = $N"
}

Write-Host "=== RL iteration $K  (N=$N, W=$Window) ==="

# -----------------------------------------------------------------------------
# 1) Self-play: run the RL_Step2 block (RL_SelfPlay vs RL_SelfPlay, ForcedCards
#    Hotel/IG-optional, fixed N, exportTrainingV2 on) -> selfplay_*.jsonl shards.
#    The block is RL_Step2_Smoke; for a real run flip its rounds up + run:true.
#    Set RL_SelfPlay's MaxTraversals to $N first (the calibrated N).
# -----------------------------------------------------------------------------
Write-Host "`n[1/8] self-play -> $selfplayDir"
# Clear stale shards + parity sidecar from any prior iteration: the C++ export game
# counter resets to 0 each run, so a shorter run would otherwise leave higher-numbered
# selfplay_*.jsonl that Stage 2's glob would wrongly concatenate into this iter's data.
if (Test-Path $selfplayDir)  { Remove-Item "$selfplayDir/selfplay_*.jsonl" -ErrorAction SilentlyContinue }
if (Test-Path $parityStates) { Remove-Item "$parityStates/sp_*.json"        -ErrorAction SilentlyContinue }
Edit-Config -Op traversals -Name RL_SelfPlay -Value $N
Edit-Config -Op run -Name RL_Step2_Smoke -Value true
Push-Location $bin   # the exe resolves asset/config/* (cardLibrary.jso, config.txt) CWD-relative
try {
    & "$bin/Prismata_Testing.exe"
    if ($LASTEXITCODE -ne 0) { throw "Prismata_Testing.exe (self-play) exited $LASTEXITCODE" }
}
finally {
    Pop-Location
    Edit-Config -Op run -Name RL_Step2_Smoke -Value false
}

# -----------------------------------------------------------------------------
# 2) Concat V2 shards -> one JSONL -> vectorize -> H5.
# -----------------------------------------------------------------------------
Write-Host "`n[2/8] concat shards + vectorize -> $h5"
$shards = Get-ChildItem -Path $selfplayDir -Filter 'selfplay_*.jsonl' | Sort-Object Name
if (-not $shards) { throw "no selfplay_*.jsonl shards in $selfplayDir" }
if (Test-Path $catJsonl) { Remove-Item $catJsonl }
foreach ($s in $shards) { Get-Content -LiteralPath $s.FullName | Add-Content -LiteralPath $catJsonl }
python "$train/vectorize_v2.py" --input $catJsonl --output $h5 --schema $schema
if ($LASTEXITCODE -ne 0) { throw "vectorize_v2.py exited $LASTEXITCODE" }

# -----------------------------------------------------------------------------
# 3) Low-LR few-epoch SWA fine-tune over the sliding window + human rehearsal.
#    --rl-mode wires the replay buffer (window W), human rehearsal, colour
#    balance, and SWA (Task 6). Pass prior iterations' H5 too if present so the
#    sliding window has its W shards.
# -----------------------------------------------------------------------------
Write-Host "`n[3/8] RL fine-tune (rl-mode, W=$Window) -> $modelDir"
$spFiles = @()
for ($i = [math]::Max(1, $K - $Window + 1); $i -le $K; $i++) {
    $cand = "$train/data/rl_iter_$i/selfplay_iter_$i.h5"
    if (Test-Path $cand) { $spFiles += $cand }
}
# train.py declares --train-file/--val-file as required=True with NO --rl-mode bypass
# (the deepsets loader builds val_ds from --val-file before the rl-mode block, and
# run_metadata dereferences args.train_file/args.val_file unconditionally), so they
# MUST be passed even in --rl-mode: --val-file = the human rehearsal H5 (the val set),
# --train-file = the newest window H5 (this iteration's vectorized self-play, $spFiles[-1]).
python "$train/train.py" --model deepsets --property-table $propTable `
    --train-file $spFiles[-1] --val-file $humanH5 `
    --rl-mode --selfplay-files @spFiles --human-file $humanH5 `
    --replay-window $Window --rl-iteration $K `
    --epochs 6 --lr 1e-5 --swa-start-epoch 3 --device xpu `
    --output-dir $modelDir
if ($LASTEXITCODE -ne 0) { throw "train.py exited $LASTEXITCODE" }
if (-not (Test-Path $bestPt)) { throw "expected SWA model not found: $bestPt" }

# -----------------------------------------------------------------------------
# 4) Export the trained net to the C++ binary.
# -----------------------------------------------------------------------------
Write-Host "`n[4/8] export weights -> $candBinPath"
python "$train/export_weights_v2.py" $bestPt $candBinPath --property-table $propTable
if ($LASTEXITCODE -ne 0) { throw "export_weights_v2.py exited $LASTEXITCODE" }

# -----------------------------------------------------------------------------
# 5) Export-parity GATE (PyTorch <-> C++ forward value). Aborts on worst |Δ| >= 1e-3.
# -----------------------------------------------------------------------------
Write-Host "`n[5/8] export-parity GATE"
# Pass --pt/--bin so the parity check is candidate.pt vs candidate.bin (this iteration's own
# PyTorch<->C++ round-trip). Without them, dump_value_batch.py defaults --pt/--bin to None and
# compare_parity_deepsets.py falls back to its HARDCODED interim (ep30) reference — which would
# compare C++(candidate) vs PyTorch(ep30) and fail for the wrong reason on any real iteration.
python "$tools/parity/dump_value_batch.py" `
    --states-dir $parityStates --weights $candBinPath --dave-bin $bin `
    --pt $bestPt --bin $candBinPath
if ($LASTEXITCODE -ne 0) { throw "export-parity GATE FAILED (worst |Δ| >= 1e-3) — aborting iteration" }

# -----------------------------------------------------------------------------
# 6) O7 tactical leading indicator (IG-click-COUNT regression). Exits nonzero
#    only on a regression vs eval/tactical_baseline.json.
# -----------------------------------------------------------------------------
Write-Host "`n[6/8] O7 tactical suite (IG-click-count regression)"
python "$eval/tactical_suite.py" --weights $candBin --dave-exe "$bin/PrismataAI.exe"
if ($LASTEXITCODE -ne 0) { throw "tactical_suite regression — aborting iteration" }

# -----------------------------------------------------------------------------
# 7) Repoint RL_Eval.WeightsFile -> the new candidate .bin (json-safe in-place
#    config rewrite), then run the 3-anchor eval (iter0 / narrow / steam).
# -----------------------------------------------------------------------------
Write-Host "`n[7/8] repoint RL_Eval -> $candBin + 3-anchor eval"
Edit-Config -Op weights -Name RL_Eval -Value $candBin
python "$eval/run_eval.py" --iteration $K `
    --weights $candBin --parent-weights $parentBin `
    --dave-bin $bin --orig-exe $origExe `
    --pools forced general --out "$eval/manifests"
if ($LASTEXITCODE -ne 0) { throw "run_eval.py exited $LASTEXITCODE" }

# -----------------------------------------------------------------------------
# 8) Action coverage (IG-click-count distribution -> manifest) + render dashboard.
# -----------------------------------------------------------------------------
Write-Host "`n[8/8] action coverage + dashboard"
python "$eval/action_coverage.py" `
    --selfplay-jsonl-dir $selfplayDir --dave-exe "$bin/PrismataAI.exe" `
    --weights $candBin --battery "$eval/ig_battery" --manifest $manifest
if ($LASTEXITCODE -ne 0) { throw "action_coverage.py exited $LASTEXITCODE" }
python "$eval/render_dashboard.py"

Write-Host "`n=== iteration $K complete ==="
Write-Host "Manifest : $manifest"
Write-Host "DECISION  : HUMAN call on the manifest + dashboard (eval/rl_campaign.md §3 decision rule)."
Write-Host "          GO iff  CI_lower(d_rl) > 0  AND  d_rl >= E(+5pp)  AND  d_reg(general) >= -Y(0.03)."
