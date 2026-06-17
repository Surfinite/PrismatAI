<#
.SYNOPSIS
  Assemble + VERIFY a self-describing DSNN Steam drop-in bundle for a given net.
  Repeatable: run once per checkpoint to package the current lineage head (or any net).

.DESCRIPTION
  Produces  <OutRoot>/<Label>/  containing:
      PrismataAI.exe                       (the campaign-pinned dave-master engine)
      use_dsnn.txt                         (sentinel + 'weights=' key naming THIS bundle's net)
      asset/config/config.txt              (defines the IG-subset root + NoIG interior iterators)
      asset/config/<Weights>               (the net)
      asset/config/unit_index.json         (REQUIRED — card-type mapping)
      README.txt                           (generated provenance + deploy + verify notes)
      bundle_manifest.json                 (file shas + provenance, for record)

  The bundle is a TRUE drop-in: use_dsnn.txt's 'weights=' key names the net (engine
  dave@50977510+), so no PRISMATA_DSNN_WEIGHTS env var and no renamed .bin are needed.

  The build VERIFIES itself by driving the bundle's exe on a one-shot FORCE_DSNN request and
  asserting: the right net loads, rootIterator=HardIterator_5var_IGsubset_Root,
  treeIterator=HardIterator_5var_NoIG (the trained/measured action space), mappedTypes>0, and a
  move is produced. -SkipVerify to skip.

.EXAMPLE
  eval/build_steam_bundle.ps1 -Label v221_rl_iter4
  eval/build_steam_bundle.ps1 -Label v221_rl_iter5 -Weights neural_weights_rl_iter5.bin -Force
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [string]$Weights = '',                                  # default: frozen parent_bin (lineage head)
    [string]$OutRoot = 'C:/libraries/DSNN_steam_bundles',
    [int]$ThinkTime  = 0,                                   # 0 = omit (engine default 10000 for the 7s bot)
    [switch]$SkipVerify,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$dave   = 'C:/libraries/PrismataAI-dave-master'
$bin    = "$dave/bin"
$cfgSrc = "$bin/asset/config"
$repo   = 'C:/libraries/PrismataAI'
$frozen = Get-Content -Raw "$repo/eval/campaign_frozen.json" | ConvertFrom-Json

if (-not $Weights) { $Weights = $frozen.parent_bin }
$Weights = Split-Path -Leaf $Weights                       # bare filename
$netSrc  = Join-Path $cfgSrc $Weights
if (-not (Test-Path $netSrc)) { throw "weights '$Weights' not found in $cfgSrc — export/promote it first." }

# The bundle MUST ship the campaign-pinned engine (it carries the FORCE_DSNN weights-key + NoIG
# interior). Refuse to package a stale/unpinned exe.
$exeSrc = "$bin/PrismataAI.exe"
if (-not (Test-Path $exeSrc)) { throw "engine not found: $exeSrc" }
$exeSha = (Get-FileHash $exeSrc -Algorithm SHA256).Hash.ToLower()
if ($exeSha -ne $frozen.engine_prismataai_exe_sha256.ToLower()) {
    throw "PrismataAI.exe sha $exeSha != frozen pin $($frozen.engine_prismataai_exe_sha256). Rebuild + re-pin first (the bundle must ship the pinned engine)."
}
$unitIdx = "$cfgSrc/unit_index.json"
if (-not (Test-Path $unitIdx)) { throw "unit_index.json not found at $unitIdx (required — without it the net is lobotomized)." }

$out = Join-Path $OutRoot $Label
if (Test-Path $out) {
    if ($Force) { Remove-Item -Recurse -Force $out } else { throw "bundle dir already exists: $out  (use -Force to overwrite, or pick a new -Label)." }
}
New-Item -ItemType Directory -Force -Path "$out/asset/config" | Out-Null

Write-Host "[build] $Label  <-  net=$Weights  engine=$exeSrc"
Copy-Item $exeSrc                 "$out/PrismataAI.exe"
Copy-Item "$cfgSrc/config.txt"    "$out/asset/config/config.txt"
Copy-Item $netSrc                 "$out/asset/config/$Weights"
Copy-Item $unitIdx                "$out/asset/config/unit_index.json"

$netSha    = (Get-FileHash $netSrc -Algorithm SHA256).Hash.ToLower()
$buildDate = (Get-Date -Format 'yyyy-MM-dd')

# --- use_dsnn.txt : self-describing (the 'weights=' key names this bundle's net) ----------------
$thinkLine = if ($ThinkTime -gt 0) { "think_time = $ThinkTime" } else { "# think_time = 10000   # unset -> the 7s Master Bot becomes 10s (the visible 'DSNN active' tell)" }
$usednn = @"
# DSNN drop-in config (PrismataAI.exe FORCE_DSNN override). The PRESENCE of this file next to
# PrismataAI.exe activates the DSNN; the 'weights' key names the net THIS bundle ships, so it is a
# self-describing drop-in -- no PRISMATA_DSNN_WEIGHTS env var, no renamed .bin. Re-read every turn.
weights = $Weights
$thinkLine
# max_traversals = 100000
"@
Set-Content -Path "$out/use_dsnn.txt" -Value $usednn -Encoding ascii

# --- README.txt (generated) ---------------------------------------------------------------------
$readme = @"
DSNN drop-in for the Steam Prismata client  --  bundle: $Label
================================================================
Built $buildDate from PrismataAI-dave-master (branch dave-master-jsonclean) by
eval/build_steam_bundle.ps1.

WHAT THIS IS
  A self-contained DSNN swap-in for Steam's PrismataAI.exe. With use_dsnn.txt present next to the
  exe, the engine ignores the requested Master-Bot player and runs UCT + DeepSets-NeuralNet with
  THIS bundle's net, searching the IG-click-COUNT "subset" action space. Single-threaded.

  Net    : $Weights
           sha256 $netSha
  Engine : PrismataAI.exe   sha256 $exeSha
           (campaign-pinned dave-master build; FORCE_DSNN in source/ai/AITools.cpp)

ACTION SPACE  (this is the RL_Eval pairing -- the space the net was TRAINED + EVALUATED on)
  * ROOT  -- IG-click-COUNT SUBSET: Infusion Grid is NOT force-fired; the net chooses HOW MANY
    times to click it (0..N) as a first-class root move. Root iterator
    HardIterator_5var_IGsubset_Root over the SWF-faithful 5-variant no-IG portfolio.
  * INTERIOR -- NoIG (no interior IG auto-fire): below the root, IG NEVER auto-fires; the tree
    iterator is HardIterator_5var_NoIG. So the net's ROOT IG-count choice is the ONLY IG decision
    in the entire search -- exactly the action space the RL campaign measured this net on.
    (Bundles <= v221 shipped HardIterator_5var here, which let IG auto-fire at interior nodes -- an
    UNMEASURED, over-click-prone space. The deploy path was fixed in engine dave@50977510.)
  * Search: MaxChildren 40, cValue 0.3 (STRONG; strength is monotonic in 1/c -- the engine default
    2.0 is the WEAKEST). Override cValue via env var PRISMATA_DSNN_CVALUE.

  Provenance: the underlying 5-variant chain is structurally identical to the SWF-verified live
  MasterBot chain (partials, ability variants, filters incl. Odin, 50-entry DefaultOpeningBook2 +
  4-entry DefaultOpeningBook) -- the ONLY deltas are the IG-exclusion filters + the AbilitySubset
  wrapper that re-adds IG as the 0..N count choice.

HOW THE NET IS SELECTED  (self-describing bundle)
  use_dsnn.txt carries  weights = $Weights  -- the engine loads THAT net (resolved against the
  exe's asset/config/). Precedence: use_dsnn.txt 'weights=' > PRISMATA_DSNN_WEIGHTS env > built-in
  default. If you ever set PRISMATA_DSNN_WEIGHTS globally, the use_dsnn.txt key still wins -- but
  unset the env var to avoid confusion across bundles.

CONFIGURING THINK TIME / TRAVERSALS
  use_dsnn.txt is re-read every turn (the exe is one-shot per turn), so edits take effect next AI
  turn. Keys (key = value, '#' comments):
    weights        = <file.bin>   the net this bundle plays (set above).
    think_time     = <ms>         applied to EVERY difficulty. 0 = no time cap (needs traversals>=1).
                                  Unset -> requested TimeLimit, with the 7s Master Bot bumped to
                                  10000 ms (the visible "DSNN active" tell).
    max_traversals = <n>          UCT cap. 0 = uncapped (needs think_time>=1). Unset -> 100000.
  Deleting use_dsnn.txt mid-game is a clean kill-switch back to the normal Master Bot.

WHERE THE FILES GO  (Steam install: ...\Steam\steamapps\common\Prismata\AI\)
  ALL of these are required (an exe-only swap, or a missing net / unit_index, makes the engine fall
  back to the NORMAL requested bot with only a stderr diagnostic you will never see from Steam):
    PrismataAI.exe                 ->  ...\Prismata\AI\PrismataAI.exe       (REPLACES the current one)
    use_dsnn.txt                   ->  ...\Prismata\AI\use_dsnn.txt
    asset\config\config.txt        ->  ...\Prismata\AI\asset\config\config.txt
    asset\config\$Weights  ->  ...\Prismata\AI\asset\config\
    asset\config\unit_index.json   ->  ...\Prismata\AI\asset\config\
  BACK UP FIRST: copy your existing PrismataAI.exe aside. Your install already keeps the genuine
  2016 Master Bot as PrismataAI.exe.ORIG -- leave that intact.

VERIFY IT'S ACTIVE  (deployment acceptance check)
  In-game: with default settings the "7s" bot thinks ~10s. If it thinks only ~7s, the DSNN did NOT
  activate (likely a missing net / unit_index at the target). On stderr you would see:
    FORCE_DSNN: 'HardestAI' -> UCT+NeuralNet, weights=$Weights, timeLimit=10000ms,
                maxTraversals=100000, cValue=0.30,
                rootIterator=HardIterator_5var_IGsubset_Root, treeIterator=HardIterator_5var_NoIG
    NeuralNet: loaded 116 unit names ... ; mapped 19 / 21 engine card types
  This bundle was BUILD-TIME verified (build_steam_bundle.ps1): FORCE_DSNN fired with the net +
  treeIterator=HardIterator_5var_NoIG + mappedTypes>0 + a move produced.

REVERT
  * Normal (requested) Master-Bot-equivalent : delete use_dsnn.txt.
  * Genuine 2016 Master Bot                  : copy PrismataAI.exe.ORIG over PrismataAI.exe.

PROVENANCE / LINEAGE
  $Weights is the RL campaign lineage head at build time -- see eval/campaign_log.md for the
  promotion + checkpoint that produced it. Re-run eval/build_steam_bundle.ps1 per checkpoint to
  package the latest promoted net.
"@
Set-Content -Path "$out/README.txt" -Value $readme -Encoding ascii

# --- bundle_manifest.json (record) --------------------------------------------------------------
$manifest = [ordered]@{
    label            = $Label
    build_date       = $buildDate
    weights          = $Weights
    weights_sha256   = $netSha
    engine_sha256    = $exeSha
    root_iterator    = 'HardIterator_5var_IGsubset_Root'
    interior_iterator= 'HardIterator_5var_NoIG'
    cvalue           = 0.3
    think_time_ms    = $(if ($ThinkTime -gt 0) { $ThinkTime } else { 'default (10000 for the 7s bot)' })
    source_repo      = 'PrismataAI-dave-master @ dave-master-jsonclean'
    verified         = (-not $SkipVerify)
}
$manifest | ConvertTo-Json | Set-Content -Path "$out/bundle_manifest.json" -Encoding ascii

# --- VERIFY: drive FORCE_DSNN on a one-shot probe request ---------------------------------------
if (-not $SkipVerify) {
    Write-Host "[verify] driving FORCE_DSNN on a probe request (one move) ..."
    $probeSrc = "$repo/eval/ig_battery/@Eobd-nYKU2_1.json"
    if (-not (Test-Path $probeSrc)) { throw "verify probe state not found: $probeSrc (use -SkipVerify to bypass)." }
    $probe = Get-Content -Raw $probeSrc | ConvertFrom-Json
    $probe | Add-Member -NotePropertyName aiPlayerName -NotePropertyValue 'HardestAI' -Force
    $reqLine = ($probe | ConvertTo-Json -Depth 60 -Compress)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName               = (Join-Path $out 'PrismataAI.exe')
    $psi.WorkingDirectory       = $out
    $psi.RedirectStandardInput  = $true
    $psi.RedirectStandardError  = $true
    $psi.RedirectStandardOutput = $true
    $psi.UseShellExecute        = $false
    $p = [System.Diagnostics.Process]::Start($psi)
    $errTask = $p.StandardError.ReadToEndAsync()
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $p.StandardInput.WriteLine($reqLine)
    $p.StandardInput.Close()
    if (-not $p.WaitForExit(90000)) { try { $p.Kill() } catch {}; throw "[verify] engine did not exit within 90s." }
    $err    = $errTask.Result
    $stdout = $outTask.Result

    $forceLine = ($err -split "`n" | Where-Object { $_ -match 'FORCE_DSNN:.*UCT\+NeuralNet' } | Select-Object -First 1)
    $fail = @()
    if (-not $forceLine) {
        $fail += 'FORCE_DSNN player line absent — the DSNN did not activate'
    } else {
        if ($forceLine -notmatch [regex]::Escape("weights=$Weights"))            { $fail += "wrong net (expected weights=$Weights)" }
        if ($forceLine -notmatch 'treeIterator=HardIterator_5var_NoIG')          { $fail += 'interior iterator is NOT HardIterator_5var_NoIG' }
        if ($forceLine -notmatch 'rootIterator=HardIterator_5var_IGsubset_Root') { $fail += 'root iterator is NOT the IG-subset root' }
    }
    if ($err -match 'mapped\s+(\d+)\s*/\s*(\d+)') { if ([int]$Matches[1] -le 0) { $fail += 'mappedTypes==0 — net lobotomized (unit_index missing/bad)' } }
    else { $fail += "no 'mapped N/M' line — NeuralNet card mapping not confirmed" }
    if ($err -match 'FATAL|could NOT build DSNN|falling back to requested')      { $fail += 'engine FATAL / FORCE_DSNN fell back to the requested bot' }
    if ($stdout -notmatch 'aiclicks')                                            { $fail += 'no aiclicks in the response — no move produced' }

    if ($fail.Count) {
        Write-Host "[verify] FAILED:" -ForegroundColor Red
        $fail | ForEach-Object { Write-Host "    - $_" }
        Write-Host "--- FORCE_DSNN line ---`n$forceLine`n--- last stderr ---"
        Write-Host (($err -split "`n" | Select-Object -Last 8) -join "`n")
        throw 'bundle verification FAILED'
    }
    Write-Host "[verify] OK"
    Write-Host "         $($forceLine.Trim())"
    if ($err -match '(mapped\s+\d+\s*/\s*\d+[^\r\n]*)') { Write-Host "         $($Matches[1].Trim())" }
}

Write-Host ""
Write-Host "Bundle ready: $out"
Write-Host "  net     : $Weights ($netSha)"
Write-Host "  engine  : $exeSha"
Write-Host "  root    : HardIterator_5var_IGsubset_Root   interior: HardIterator_5var_NoIG"
