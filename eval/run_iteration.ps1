# =============================================================================
# RL Self-Play — one-iteration driver (Task 14)
#
# DEFERRED — do not run until the "Run prerequisites" in eval/rl_campaign.md are
# satisfied (FROZEN tuple in eval/campaign_frozen.json must match dave config.txt's
# RL_SelfPlay — asserted below, never rewritten; eval/calib_states/ +
# eval/ig_battery/ populated). iter-0 anchor = v221 on RL_Eval_iter0 (per the
# 2026-06-07 decision — NOT a random wide-untrained net); the 2016 MasterBot
# baseline lives at its permanent home c:/libraries/prismata_baselines/masterbot2016/.
#
# The gate (promote / reject / inconclusive) is a HUMAN decision on the eval
# manifest + dashboard — this driver only PRODUCES the manifest + dashboard and
# prints the §12 decision inputs. It does NOT auto-promote.
#
# This orchestrates already-built tools (it does NOT rebuild them):
#   preflight  : eval/preflight_config.py            (stage 0 — config integrity + frozen tuple + parent re-pin)
#   self-play  : Prismata_Testing.exe over a run:true block in dave's config.txt
#   vectorize  : training/vectorize_v2.py
#   train      : training/train.py --rl-mode (Task 6)
#   export     : training/export_weights_v2.py
#   tripwire   : eval/eval_deepsets_h5.py            (held-out val-acc, candidate vs parent; abort < parent-3pp)
#   parity GATE: tools/parity/dump_value_batch.py   (abort on worst |Δ| >= 1e-3)
#   tactical   : eval/tactical_suite.py             (O7 leading indicator)
#   eval (3 anchors) : eval/run_eval.py
#   coverage   : eval/action_coverage.py
#   dashboard  : eval/render_dashboard.py
# =============================================================================
param(
    [int]$K = 1,        # RL iteration index
    [int]$N = 0,        # informational only; the tuple is FROZEN in eval/campaign_frozen.json — a nonzero -N that differs from frozen_N throws
    [int]$Window = 5,   # replay-buffer window W
    [string]$ParentPt = ''  # parent checkpoint (.pt) to warm-start from; empty => the FROZEN parent_pt from eval/campaign_frozen.json (promotion-gated lineage, N-3)
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
# Current promoted net (gating parent / manifest label / stage-7 finally-restore target)
# AND its .pt checkpoint (the warm-start parent). Both read from campaign_frozen.json so a
# promotion (which edits the frozen file) propagates here automatically — a stale literal
# would make the F-07 restore re-pin the OLD parent. ($frozen proper is loaded at stage 0;
# this early read only needs parent_bin/parent_pt for path wiring.)
$frozenEarly = Get-Content -Raw "$eval/campaign_frozen.json" | ConvertFrom-Json
$parentBin   = $frozenEarly.parent_bin
if (-not $parentBin) { throw "campaign_frozen.json has no parent_bin" }
$origExe     = 'c:/libraries/prismata_baselines/masterbot2016/PrismataAI.exe'  # genuine 2016 MasterBot at its permanent home (steam anchor baseline)
$parityStates = "$bin/asset/training/parity_states"     # native GameState sidecar (sp_*.json) from self-play
$schema      = "$train/schema_v2.json"
$propTable   = "$train/property_table.json"
$humanH5     = "$train/data/human_1800_v2.h5"           # rehearsal data (--human-file) ONLY — never the val set
$humanValH5  = "$train/data/human_val_1700_v2.h5"        # HELD-OUT human val set (M-03: validate on this, not the rehearsal file)
$manifest    = "$eval/manifests/eval_iter_$K.json"

# --- Resolve the parent checkpoint (E1 + N-3: promotion-gated lineage) ---
# Default = the FROZEN parent_pt from campaign_frozen.json — the same provenance source as
# $parentBin. Promotion = updating campaign_frozen.json's parent_pt/parent_bin (documented in
# eval/rl_runbook.md "Between iterations"), so running K>1 WITHOUT a promotion warm-starts
# from the SAME frozen parent again — correct: an unpromoted candidate must never enter the
# lineage (N-3). The old K-based auto-resolve (iter K-1's SWA) could silently absorb a
# REJECTED candidate. -ParentPt stays as an explicit override (printed loudly).
# Fail fast — train.py --rl-mode hard-fails without --init-weights.
if (-not $ParentPt) {
    $ParentPt = $frozenEarly.parent_pt
    if (-not $ParentPt) { throw "campaign_frozen.json has no parent_pt" }
    if (-not [System.IO.Path]::IsPathRooted($ParentPt)) { $ParentPt = "$repo/$ParentPt" }
} else {
    Write-Host "*** -ParentPt OVERRIDE: warm-starting from $ParentPt (NOT the frozen parent_pt — lineage bypass; make sure this is deliberate) ***"
}
if (-not (Test-Path $ParentPt)) {
    throw "parent checkpoint not found: $ParentPt — the RL fine-tune must warm-start from its parent net (E1). Promote (update campaign_frozen.json) or pass -ParentPt explicitly."
}

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

# --- Held-out val-acc of a .pt checkpoint (stage 4.5 tripwire) ---------------
# Runs eval/eval_deepsets_h5.py and parses its "  val_acc  = NN.N%" stdout line.
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

# -----------------------------------------------------------------------------
# 0) Structural preflight — single source of truth: eval/preflight_config.py.
#    Subsumes the former inline frozen-tuple assert and adds: config JSON/BOM
#    integrity, zero run:true Benchmarks blocks, RL iterator shape (the
#    crippled-iterator guard), opening-book sizes, the full declared reference
#    graph (incl. WeightsFile existence), EpsilonLate key-absent convention,
#    all-four parent re-pins (F-07/N-2), and parent_pt / data-H5 existences.
#    The tuple stays FROZEN by owner decision: nothing here rewrites config.txt;
#    reconcile drift deliberately (edit campaign_frozen.json AND config.txt
#    together) — the script must never silently mutate the campaign identity.
# -----------------------------------------------------------------------------
Write-Host "`n[0/8] structural preflight (eval/preflight_config.py)"
$frozenPath = "$eval/campaign_frozen.json"
python "$eval/preflight_config.py" --config $config --frozen $frozenPath
if ($LASTEXITCODE -ne 0) {
    throw "structural preflight FAILED (eval/preflight_config.py exit $LASTEXITCODE) — fix every FAIL line above before running an iteration."
}

# -N is informational; the tuple itself was verified by the preflight above.
$frozen = Get-Content -Raw $frozenPath | ConvertFrom-Json
if ($N -gt 0 -and $N -ne [int]$frozen.frozen_N) {
    throw "-N $N conflicts with frozen_N $($frozen.frozen_N) in campaign_frozen.json — the tuple is frozen; reconcile deliberately instead of overriding."
}
$N = [int]$frozen.frozen_N

Write-Host "=== RL iteration $K  (N=$N, W=$Window) ==="

# -----------------------------------------------------------------------------
# 1) Self-play: run the RL_Step2 block (RL_SelfPlay vs RL_SelfPlay, ForcedCards
#    Hotel/IG-optional, fixed N, exportTrainingV2 on) -> selfplay_*.jsonl shards.
#    The block is RL_Step2_Smoke; for a real run flip its rounds up + run:true.
#    RL_SelfPlay's MaxTraversals is NOT rewritten here — the frozen-tuple assert
#    above already verified config.txt matches campaign_frozen.json.
# -----------------------------------------------------------------------------
Write-Host "`n[1/8] self-play -> $selfplayDir"
# Clear stale shards + parity sidecar from any prior iteration: the C++ export game
# counter resets to 0 each run, so a shorter run would otherwise leave higher-numbered
# selfplay_*.jsonl that Stage 2's glob would wrongly concatenate into this iter's data.
if (Test-Path $selfplayDir)  { Remove-Item "$selfplayDir/selfplay_*.jsonl" -ErrorAction SilentlyContinue }
if (Test-Path $parityStates) { Remove-Item "$parityStates/sp_*.json"        -ErrorAction SilentlyContinue }
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
#    WARM-STARTS from the parent checkpoint via --init-weights (E1 fix — train.py
#    --rl-mode hard-fails without it; the parent = the FROZEN parent_pt, v221 until
#    a promotion updates campaign_frozen.json — N-3) and validates on the HELD-OUT
#    human val set (M-03 fix — never the rehearsal file).
#    --rl-mode wires the replay buffer (window W), human rehearsal, colour
#    balance, and SWA (Task 6). Pass prior iterations' H5 too if present so the
#    sliding window has its W shards.
#    --swa-lr 5e-6 (N-1 fix): the train.py default (lr*0.1 = 1e-6 at lr=1e-5)
#    equals the min-lr floor, freezing the SWA phase (epochs 3-6, HALF the run).
#    5e-6 = half the fine-tune LR — keeps SWA-phase learning alive without
#    overshooting the cosine tail. (train.py also auto-rescales the 1000-step
#    warmup default down to ~10% of this run's ~78 total steps.)
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
# MUST be passed even in --rl-mode: --val-file = the HELD-OUT human val H5 (M-03 —
# validating on the rehearsal file leaked training data into the val signal),
# --train-file = the newest window H5 (this iteration's vectorized self-play, $spFiles[-1]).
python "$train/train.py" --model deepsets --property-table $propTable `
    --train-file $spFiles[-1] --val-file $humanValH5 `
    --rl-mode --init-weights $ParentPt --selfplay-files @spFiles --human-file $humanH5 `
    --replay-window $Window --rl-iteration $K `
    --epochs 6 --lr 1e-5 --swa-start-epoch 3 --swa-lr 5e-6 --device xpu `
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
# 4.5) Val-acc tripwire: candidate vs parent on the HELD-OUT human val set.
#      Catches an E1-class failure (candidate trained badly / from the wrong init)
#      cheaply, BEFORE the expensive eval stages. Abort if the candidate fell
#      more than 3.0pp below its parent.
# -----------------------------------------------------------------------------
Write-Host "`n[4.5/8] val-acc tripwire (held-out $humanValH5)"
$candAcc   = Get-ValAcc $bestPt
$parentAcc = Get-ValAcc $ParentPt
Write-Host "val_acc: candidate = $candAcc%  parent = $parentAcc%"
if ($candAcc -lt ($parentAcc - 3.0)) {
    throw "val-acc tripwire: candidate $candAcc% is more than 3.0pp below parent $parentAcc% — candidate trained badly (E1-class failure); aborting iteration."
}

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
#    F-07: try/finally so RL_Eval is ALWAYS restored to the promoted parent net
#    on any exit path after the repoint (a killed/failed run must not leave
#    config.txt pointing at an unpromoted candidate). Stage 8 does NOT need the
#    repoint — action_coverage.py passes --weights explicitly to query_move.js,
#    which overrides the player's WeightsFile — so restore happens right here.
# -----------------------------------------------------------------------------
Write-Host "`n[7/8] repoint RL_Eval -> $candBin + 3-anchor eval"
try {
    Edit-Config -Op weights -Name RL_Eval -Value $candBin
    python "$eval/run_eval.py" --iteration $K `
        --weights $candBin --parent-weights $parentBin `
        --dave-bin $bin --orig-exe $origExe `
        --pools forced general --out "$eval/manifests"
    if ($LASTEXITCODE -ne 0) { throw "run_eval.py exited $LASTEXITCODE" }
}
finally {
    Edit-Config -Op weights -Name RL_Eval -Value $parentBin
    Write-Host "RL_Eval.WeightsFile restored -> $parentBin (F-07 guard)"
}

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
Write-Host "          verdict REJECT = proven worse on the general pool (Wilson95 ci_upper < 0.5);"
Write-Host "          verdict REVIEW = human decision. See eval/run_eval.py VERDICT_RULE for exact semantics."
