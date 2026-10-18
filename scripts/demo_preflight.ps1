<#
 Machine check before using the app (ISD OCR-LLM-QNA). Run from the project root in PowerShell.
   .\scripts\demo_preflight.ps1            # CHECK: tools, venv, model, 7 DBs, ports (changes nothing; before starting the server)
   .\scripts\demo_preflight.ps1 -Exam      # EXAM DAY: ollama serve + uvicorn already running (README 1.2); checks
                                           # git HEAD = GitHub main, qwen3:4b, /api/health, 7 plans, then warms the model
                                           # with one model-path question and re-asks it to time a warm answer
 File is saved as UTF-8 with BOM so Windows PowerShell 5.1 reads the Thai questions correctly.
#>
param([switch]$Exam)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
function Ok($m)   { Write-Host "[ OK ] $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "[FAIL] $m" -ForegroundColor Red; $script:fail++ }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
$script:fail = 0

if (-not ((Test-Path README.md) -and (Test-Path lab10_fastapi))) { Bad "Run this from the project root (README.md + lab10_fastapi expected)"; exit 1 }

if ($Exam) {
  $rows = New-Object System.Collections.Generic.List[object]
  function Rec($status, $name, $detail) {
    $rows.Add([pscustomobject]@{ Status = $status; Check = $name; Detail = $detail })
    $color = @{ PASS = 'Green'; FAIL = 'Red'; WARN = 'Yellow' }[$status]
    Write-Host ("[{0}] {1}: {2}" -f $status, $name, $detail) -ForegroundColor $color
  }
  $api = 'http://127.0.0.1:8000'

  # 1) code on this machine = main on GitHub (compare with ls-remote, never a hard-coded hash)
  $head = (git rev-parse HEAD 2>$null)
  if (-not $head) {
    Rec 'FAIL' 'git HEAD' 'not a git checkout (ZIP download?): cannot prove the code matches GitHub'
  } else {
    $branch = (git rev-parse --abbrev-ref HEAD 2>$null)
    $remote = ((git ls-remote origin refs/heads/main 2>$null) -split '\s+')[0]
    if (-not $remote) {
      $local = (git rev-parse origin/main 2>$null)
      Rec 'WARN' 'git HEAD = GitHub main' ("ls-remote failed (no internet?); HEAD {0} vs last fetched origin/main {1}" -f $head.Substring(0, 7), "$local".Substring(0, [Math]::Min(7, "$local".Length)))
    } elseif ($remote -eq $head) {
      Rec 'PASS' 'git HEAD = GitHub main' ("{0} on branch {1}" -f $head.Substring(0, 7), $branch)
    } else {
      Rec 'FAIL' 'git HEAD = GitHub main' ("HEAD {0} but GitHub main {1}: run git pull (branch {2})" -f $head.Substring(0, 7), $remote.Substring(0, 7), $branch)
    }
    $dirty = @(git status --porcelain --untracked-files=no 2>$null)
    if ($dirty.Count -eq 0) { Rec 'PASS' 'tracked files unchanged' 'no local edits to tracked files' }
    else { Rec 'WARN' 'tracked files unchanged' ("{0} tracked file(s) edited locally: {1}" -f $dirty.Count, (($dirty | ForEach-Object { $_.Trim() }) -join ', ')) }
  }

  # 2) Ollama answers and has the model
  try {
    $tags = Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 5
    $names = @($tags.models | ForEach-Object { $_.name })
    if ($names -contains 'qwen3:4b') { Rec 'PASS' 'ollama qwen3:4b' ("ollama up, models: {0}" -f ($names -join ', ')) }
    else { Rec 'FAIL' 'ollama qwen3:4b' ("ollama up but qwen3:4b missing (ollama pull qwen3:4b); has: {0}" -f ($names -join ', ')) }
  } catch {
    Rec 'FAIL' 'ollama qwen3:4b' 'ollama not reachable on :11434. Start it from a folder OUTSIDE the repo, e.g. cd $HOME; ollama serve'
  }

  # 3) app health
  $serverUp = $false
  try {
    $h = Invoke-RestMethod "$api/api/health" -TimeoutSec 5
    $serverUp = $true
    if ($h.status -eq 'ok') { Rec 'PASS' '/api/health' ("status=ok, model={0}" -f $h.model) }
    else { Rec 'FAIL' '/api/health' ("status={0}, database_ready={1}, ollama_ready={2}" -f $h.status, $h.database_ready, $h.ollama_ready) }
  } catch {
    Rec 'FAIL' '/api/health' 'server not reachable on :8000: start uvicorn (README 1.2)'
  }

  if ($serverUp) {
    try {
      # PS 5.1 emits a JSON array as ONE object; ForEach-Object unrolls it so .Count is the number of plans
      $progs = @(Invoke-RestMethod "$api/api/programs" -TimeoutSec 5 | ForEach-Object { $_ })
      $ready = @($progs | Where-Object { $_.available })
      if ($ready.Count -ge 7) { Rec 'PASS' '7 plans available' (($ready | ForEach-Object { $_.id }) -join ', ') }
      else { Rec 'FAIL' '7 plans available' ("only {0} of {1} available" -f $ready.Count, $progs.Count) }
    } catch { Rec 'FAIL' '7 plans available' "/api/programs failed: $($_.Exception.Message)" }

    # 4) warm-up: a question no shortcut answers, so it loads qwen3 into memory; then the same question again, warm
    $qAi = 'วิชาไหนบ้างที่มีคำว่า PROGRAMMING ในชื่อ'     # 2026-10-18: 200 three times, 2.5-3.3 s warm
    $body = [System.Text.Encoding]::UTF8.GetBytes((@{ question = $qAi; program = 'dsba_coop' } | ConvertTo-Json -Compress))
    foreach ($round in 'warm-up ask (cold)', 'second ask (warm, < 5 s)') {
      $sw = [Diagnostics.Stopwatch]::StartNew()
      try {
        $r = Invoke-RestMethod "$api/api/ask" -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 180
        $s = $sw.Elapsed.TotalSeconds
        $detail = "{0:N1}s, answer_type={1}, answer length={2}" -f $s, $r.answer_type, "$($r.answer)".Length
        if (-not "$($r.answer)".Trim()) { Rec 'FAIL' $round "empty answer ($detail)" }
        elseif ($r.answer_type -notin 'ai', 'hybrid') { Rec 'WARN' $round "answered by a shortcut, model NOT warmed ($detail): pick another model-path question" }
        elseif ($round -like 'second*' -and $s -ge 5) { Rec 'FAIL' $round "slower than 5 s ($detail)" }
        else { Rec 'PASS' $round $detail }
      } catch {
        $code = $null
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        # 422 (code before 48c0903; now a 200 "ลองถามใหม่" answer) = the model answered but its SQL failed twice: qwen3 is loaded
        if ($code -eq 422) { Rec 'WARN' $round ("HTTP 422 after {0:N1}s: model loaded, its SQL failed twice; run -Exam again" -f $sw.Elapsed.TotalSeconds); continue }
        Rec 'FAIL' $round ("HTTP {0} after {1:N1}s: {2}" -f $code, $sw.Elapsed.TotalSeconds, $_.Exception.Message)
      }
    }
  }

  Write-Host "`n== SUMMARY =="
  $rows | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
  $nFail = @($rows | Where-Object { $_.Status -eq 'FAIL' }).Count
  $nWarn = @($rows | Where-Object { $_.Status -eq 'WARN' }).Count
  if ($nFail -gt 0) { Write-Host "$nFail FAIL, $nWarn WARN: fix before the exam starts." -ForegroundColor Red; exit 1 }
  Write-Host "All checks passed ($nWarn WARN). Model is warm: open http://127.0.0.1:8000/" -ForegroundColor Green
  exit 0
}

Write-Host "== CHECK =="
foreach ($t in @(@('python','--version'), @('git','--version'), @('ollama','--version'))) {
  $cmd = Get-Command $t[0] -ErrorAction SilentlyContinue
  if ($cmd) { Ok ("{0}: {1}" -f $t[0], ((& $t[0] $t[1] 2>&1) -join ' ')) } else { Bad "$($t[0]) not found in PATH" }
}
if (Test-Path .venv\Scripts\Activate.ps1) { Ok ".venv present" } else { Bad ".venv missing (README 1.1)" }
$pol = Get-ExecutionPolicy -Scope CurrentUser
if ($pol -in 'Restricted','Undefined') { Warn "ExecutionPolicy(CurrentUser)=$pol : Activate.ps1 may be blocked. Fix: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" } else { Ok "ExecutionPolicy(CurrentUser)=$pol" }

# model file check without needing ollama to be running
$man = Join-Path $env:USERPROFILE '.ollama\models\manifests\registry.ollama.ai\library\qwen3\4b'
if (Test-Path $man) { Ok "qwen3:4b is pulled" } else { Bad "qwen3:4b not pulled (ollama pull qwen3:4b)" }

$dbs = Get-ChildItem -Recurse -Filter curriculum.db Lab7B_Lab8B_ocr_system\runs -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '_archive' }
if ($dbs.Count -ge 7) { Ok "$($dbs.Count) curriculum.db found (7 plans)" } else { Bad "expected 7 curriculum.db, found $($dbs.Count)" }

foreach ($port in 8000, 11434) {
  $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($c) { Warn "port $port is in use by PID $($c[0].OwningProcess) (fine if it is your uvicorn/ollama; otherwise stop it first)" } else { Ok "port $port free" }
}

if ($script:fail -gt 0) { Write-Host "`n$($script:fail) problem(s). Fix before starting the app." -ForegroundColor Red; exit 1 }
Write-Host "`nAll good. Next: start ollama serve + uvicorn (README 1.2), then run .\scripts\demo_preflight.ps1 -Exam" -ForegroundColor Green
