# =============================================================================
# run_phase1_loop.ps1 — DRAFT (review before unattended use) — 2026-06-18
#
# Thin Phase-1 chaining wrapper for the RL self-play loop: it runs
#   run_iteration.ps1 -K K  ->  (unless aborted) promote_candidate.ps1 -K K  ->  K+1
# for a bounded number of iterations / wall-clock budget, with a powered
# run_checkpoint.ps1 every -CheckpointEvery promotions, and HALTS (does not blindly
# continue) the moment anything looks wrong. Built for an overnight, owner-clears-PC
# run. It changes NO campaign identity: the only edits it makes are the same at-rest
# config self-heals run_iteration / run_checkpoint already do.
#
# SAFETY MODEL (the reason this wrapper exists):
#   * HALT (never continue) on: run_iteration crash, val-acc tripwire, collapse==true
#     or null, degenerate self-play, or any promote_candidate refusal. An unattended
#     loop must stop for a human on ANY abort signal, not push past it.
#   * BOUNDED RETRY only for the documented transient Windows HTML file-lock FATAL
#     (engine exit 0xC0000409 at HTMLTable::appendHTMLTableToFile) — re-run, don't halt.
#   * CONFIG RESTORE: a host-kill that skips run_checkpoint's finally leaves the anchor
#     blocks at rounds 192 -> preflight then rejects every run. This wrapper SELF-HEALS
#     anchor rounds + the self-play block at STARTUP (defending against last run's kill)
#     and again in its own finally.
#
# OPEN DECISIONS FOR REVIEW (search "REVIEW:"):
#   1. file-lock retry currently re-runs the WHOLE iteration (safe, ~3h). Stage-aware
#      -ResumeFrom would be cheaper but needs reliable stage detection.
#   2. degeneracy thresholds read from the manifest if present; otherwise we lean on
#      promote_candidate's gates. Confirm the manifest carries game-length / seat WR.
#   3. StartK is derived from campaign_frozen.json parent_bin (rl_iter<N> -> N+1).
#
# USAGE:
#   pwsh eval/run_phase1_loop.ps1 -DryRun                 # print the plan, run nothing
#   pwsh eval/run_phase1_loop.ps1 -MaxIterations 4 -CheckpointEvery 4 -BudgetHours 20
#   pwsh eval/run_phase1_loop.ps1 -StartK 5 -EndK 8       # explicit range
# =============================================================================
param(
    [int]$StartK = 0,                 # 0 => derive from frozen parent_bin (rl_iter<N> -> N+1)
    [int]$EndK = 0,                   # 0 => use -MaxIterations from StartK
    [int]$MaxIterations = 4,          # cap on promotions this run (ignored if -EndK set)
    [int]$CheckpointEvery = 4,        # powered run_checkpoint after this many promotions (0 = never)
    [double]$BudgetHours = 0,         # wall-clock stop BEFORE starting an iteration that can't finish; 0 = no limit
    [double]$HoursPerIteration = 3.0, # budget estimate per iteration (self-play ~82m + eval ~90m)
    [int]$MaxFileLockRetries = 2,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$evalDir = $PSScriptRoot
$repo = Split-Path $evalDir -Parent
$frozenPath = Join-Path $evalDir 'campaign_frozen.json'
$daveBin = 'c:/libraries/PrismataAI-dave-master/bin'
$frozen = Get-Content -Raw $frozenPath | ConvertFrom-Json
$startTime = Get-Date

function Log($msg) { Write-Host ("[phase1-loop {0:HH:mm:ss}] {1}" -f (Get-Date), $msg) }

# --- derive StartK from the promoted parent (rl_iter<N> -> N+1) ----------------
if ($StartK -le 0) {
    if ($frozen.parent_bin -match 'rl_iter(\d+)') {
        $StartK = [int]$Matches[1] + 1
    } else {
        throw "parent_bin '$($frozen.parent_bin)' is not an rl_iter net — pass -StartK explicitly (Phase 0 / v221 parent does not auto-derive)."
    }
}
if ($EndK -le 0) { $EndK = $StartK + $MaxIterations - 1 }
Log "parent=$($frozen.parent_bin)  StartK=$StartK  EndK=$EndK  checkpointEvery=$CheckpointEvery  budgetHours=$BudgetHours"

# --- config self-heal: restore anchor rounds to frozen + selfplay run:false ----
# (defends against a previous host-kill that skipped run_checkpoint/run_iteration's finally)
function Restore-ConfigAtRest {
    $py = @"
import json, re, sys
cfg = r'$daveBin/asset/config/config.txt'
fro = json.load(open(r'$frozenPath', encoding='utf-8-sig'))
want = {
    'RL_PoL_origin':    int(fro['anchor_blocks']['RL_PoL_origin']['rounds']),
    'RL_PoL_masterbot': int(fro['anchor_blocks']['RL_PoL_masterbot']['rounds']),
}
text = open(cfg, encoding='utf-8-sig').read()
lines = text.splitlines(keepends=True)
changed = []
for i, ln in enumerate(lines):
    for blk, r in want.items():
        if ('"name":"%s"' % blk) in ln.replace(' ', '') or ('"name": "%s"' % blk) in ln:
            new = re.sub(r'("rounds"\s*:\s*)\d+', lambda m: m.group(1) + str(r), ln, count=1)
            if new != ln:
                lines[i] = new; changed.append('%s->rounds %d' % (blk, r))
    # selfplay block run:true -> false at rest
    if '"name":"RL_SelfPlay_General"' in ln.replace(' ', '') or '"name": "RL_SelfPlay_General"' in ln:
        new = re.sub(r'("run"\s*:\s*)true', r'\g<1>false', ln, count=1)
        if new != ln:
            lines[i] = new; changed.append('RL_SelfPlay_General->run false')
if changed:
    open(cfg, 'w', encoding='utf-8', newline='').write(''.join(lines))
    json.load(open(cfg, encoding='utf-8-sig'))  # validate strict JSON
    print('self-heal: ' + '; '.join(changed))
else:
    print('self-heal: config already at rest')
"@
    $py | python -
    if ($LASTEXITCODE -ne 0) { throw "config self-heal failed" }
}

# --- the known transient file-lock signature ----------------------------------
function Test-FileLock($text) {
    return ($text -match '0xC0000409') -or ($text -match 'C0000409') -or ($text -match 'HTMLTable')
}

if ($DryRun) {
    Log "DRY RUN — plan:"
    for ($k = $StartK; $k -le $EndK; $k++) {
        $cp = ($CheckpointEvery -gt 0 -and (($k - $StartK + 1) % $CheckpointEvery -eq 0)) ? ' + CHECKPOINT' : ''
        Log "  K=$k : run_iteration -> promote-unless-collapse$cp"
    }
    Log "config self-heal would run at startup + in finally; HALT on any abort; file-lock bounded-retry x$MaxFileLockRetries."
    return
}

try {
    Restore-ConfigAtRest
    $promotions = 0
    for ($k = $StartK; $k -le $EndK; $k++) {
        # budget gate: do not START an iteration that cannot finish within the budget
        if ($BudgetHours -gt 0) {
            $elapsed = ((Get-Date) - $startTime).TotalHours
            if (($elapsed + $HoursPerIteration) -gt $BudgetHours) {
                Log "BUDGET: $([math]::Round($elapsed,1))h elapsed + ~${HoursPerIteration}h/iter would exceed ${BudgetHours}h — stopping cleanly before K=$k."
                break
            }
        }

        # --- run the iteration (with bounded file-lock retry) ------------------
        $attempt = 0; $iterOk = $false; $iterOut = ''
        while ($attempt -le $MaxFileLockRetries -and -not $iterOk) {
            $attempt++
            Log "K=$k : run_iteration (attempt $attempt)"
            $iterOut = & pwsh -NoProfile -File (Join-Path $evalDir 'run_iteration.ps1') -K $k 2>&1 | Out-String
            Write-Host $iterOut
            if ($LASTEXITCODE -eq 0) { $iterOk = $true; break }
            if (Test-FileLock $iterOut) {
                Log "K=$k : transient file-lock detected (exit $LASTEXITCODE) — retrying (REVIEW: whole-iteration retry)."
                continue
            }
            # tripwire / crash / parity-fail — a real abort
            Log "*** HALT: run_iteration -K $k exited $LASTEXITCODE (NOT a file-lock — crash / val-acc tripwire / parity). Inspect the log; do NOT blindly resume. ***"
            return
        }
        if (-not $iterOk) { Log "*** HALT: run_iteration -K $k failed after $MaxFileLockRetries file-lock retries. ***"; return }

        # --- read collapse + degeneracy from the manifest ----------------------
        $manifest = Join-Path $evalDir "manifests/eval_iter_$k.json"
        if (-not (Test-Path $manifest)) { Log "*** HALT: manifest $manifest missing after K=$k. ***"; return }
        $m = Get-Content -Raw $manifest | ConvertFrom-Json
        if ($null -eq $m.collapse) { Log "*** HALT: K=$k manifest.collapse is null (origin anchor missing/errored). ***"; return }
        if ($m.collapse -eq $true) { Log "*** HALT: K=$k COLLAPSE (origin WR < $($frozen.abort_winrate_vs_origin)). Keep parent; record in campaign_log.md. ***"; return }
        # REVIEW: degeneracy thresholds — confirm these fields exist in the manifest.
        # (game-length band + per-seat WR; if absent, promote_candidate's gates still apply.)

        # --- promote (authoritative collapse + lineage + tripwire gate) --------
        Log "K=$k : collapse=$($m.collapse) — promoting"
        & pwsh -NoProfile -File (Join-Path $evalDir 'promote_candidate.ps1') -K $k 2>&1 | Out-String | Write-Host
        if ($LASTEXITCODE -ne 0) { Log "*** HALT: promote_candidate -K $k refused/failed (collapse/lineage/tripwire). Keep parent; inspect. ***"; return }
        $promotions++
        Log "K=$k : PROMOTED (#$promotions this run). REMINDER: add the K=$k entry to eval/campaign_log.md."

        # --- powered checkpoint at cadence -------------------------------------
        if ($CheckpointEvery -gt 0 -and ($promotions % $CheckpointEvery -eq 0)) {
            Log "checkpoint after $promotions promotions (run_checkpoint -Iteration 0)"
            & pwsh -NoProfile -File (Join-Path $evalDir 'run_checkpoint.ps1') -Iteration 0 2>&1 | Out-String | Write-Host
            if ($LASTEXITCODE -ne 0) { Log "*** HALT: run_checkpoint failed — config restored by its finally; inspect. ***"; Restore-ConfigAtRest; return }
        }
    }
    Log "loop complete: $promotions promotion(s), K=$StartK..$([math]::Min($k-1,$EndK))."
}
finally {
    try { Restore-ConfigAtRest } catch { Log "WARNING: final config self-heal failed: $($_.Exception.Message)" }
    Log "exit."
}
