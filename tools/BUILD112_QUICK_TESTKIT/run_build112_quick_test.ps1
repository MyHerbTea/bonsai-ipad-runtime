Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

$defaultBase = "http://192.168.1.85:8080"
$enteredBase = Read-Host "Bonsai Base URL [$defaultBase]"
if ([string]::IsNullOrWhiteSpace($enteredBase)) { $enteredBase = $defaultBase }

$root = $enteredBase.Trim().TrimEnd("/")
if ($root.EndsWith("/v1")) { $root = $root.Substring(0, $root.Length - 3) }

$secure = Read-Host "API Key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($apiKey)) { throw "API Key is required." }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $scriptRoot ("RESULTS\Build112-Quick-" + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$headers = @{ "X-API-Key" = $apiKey; "Content-Type" = "application/json" }

function Save-Json($Value, [string]$Name) {
    $Value | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 (Join-Path $outDir $Name)
}
function Get-Bonsai([string]$Path) {
    Invoke-RestMethod -Method Get -Uri ($root + $Path) -Headers $headers -TimeoutSec 30
}
function Invoke-Chat([string]$Prompt) {
    $body = @{
        model = "bonsai-2-27b-local"
        messages = @(@{ role = "user"; content = $Prompt })
        max_tokens = 8
        temperature = 0
        top_p = 1
        seed = 424242
        stream = $false
    } | ConvertTo-Json -Depth 20
    Invoke-RestMethod -Method Post -Uri ($root + "/v1/chat/completions") -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 600
}
function New-Prompt([int]$TargetTokens) {
    $unit = "alpha beta gamma delta epsilon zeta eta theta iota kappa "
    $repeat = [math]::Ceiling($TargetTokens / 10.0)
    return "Read the deterministic sequence and reply only OK. " + ($unit * $repeat)
}
function Measure-Case([string]$Label, [int]$TargetTokens) {
    $prompt = New-Prompt $TargetTokens
    Write-Host ("[TEST] {0} target={1}..." -f $Label, $TargetTokens)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-Chat $prompt
    $sw.Stop()
    $prefill = Get-Bonsai "/debug/prefill"
    $last = $prefill.last
    $usage = $response.usage
    $answer = [string]$response.choices[0].message.content

    if ($null -eq $last) { throw "No /debug/prefill observation after $Label." }
    if ($null -eq $usage) { throw "No response usage after $Label." }

    $row = [ordered]@{
        label = $Label
        target_prompt_tokens = $TargetTokens
        prompt_tokens_response = [int]$usage.prompt_tokens
        prompt_tokens_native = [int]$last.prompt_tokens
        completion_tokens = [int]$last.completion_tokens
        prefill_ms = [double]$last.prefill_ms
        decode_to_first_token_ms = [double]$last.decode_to_first_token_ms
        ttft_ms = [double]$last.ttft_ms
        tokens_per_second = [double]$last.tokens_per_second
        wall_ms = [double]$sw.Elapsed.TotalMilliseconds
        answer = $answer
        semantic_ok = ($answer.Trim() -eq "OK")
        sequence = [int]$last.sequence
    }
    if ($row.prompt_tokens_response -ne $row.prompt_tokens_native) {
        throw "Prompt token mismatch for $Label."
    }
    return [pscustomobject]$row
}

$summary = [ordered]@{
    testkit = "Build112-Quick"
    testkit_version = "1.0"
    purpose = "M5 32K B16 default prefill measurement"
    mode = "quick"
    comparison = "B16-only observation; no automatic B8 replay or state manipulation"
    started_at = (Get-Date).ToString("o")
    base_url = $enteredBase
}

try {
    Write-Host ""
    Write-Host "=== Bonsai Build112 Quick Test ==="
    Write-Host "No checkpoint, no resume, no arm switching, no SAFE4 manipulation."
    Write-Host ""

    $health = Get-Bonsai "/health"
    Save-Json $health "health.json"
    $build = Get-Bonsai "/debug/build"
    Save-Json $build "build.json"
    $governor = Get-Bonsai "/debug/build106/governor"
    Save-Json $governor "governor.json"
    $telemetryBefore = Get-Bonsai "/debug/telemetry"
    Save-Json $telemetryBefore "telemetry-before.json"
    $models = Get-Bonsai "/v1/models"
    Save-Json $models "models.json"

    $identityOk = ([string]$build.build_number -eq "112") -and ([string]$build.candidate_build_id -eq "rc1.26-build112-b16-default")
    $b16Ok = ([string]$governor.profile -eq "PERFORMANCE16") -and ([int]$governor.active_batch -eq 16) -and ([int]$governor.active_ubatch -eq 16) -and ([int]$governor.context -eq 32768) -and ([string]$governor.fallback_profile -eq "NONE") -and ($governor.sticky_fallback -eq $false)

    $summary.build_identity_ok = $identityOk
    $summary.b16_runtime_ok = $b16Ok
    $summary.build_number = [string]$build.build_number
    $summary.candidate_build_id = [string]$build.candidate_build_id
    $summary.profile = [string]$governor.profile
    $summary.active_batch = [int]$governor.active_batch
    $summary.active_ubatch = [int]$governor.active_ubatch
    $summary.context = [int]$governor.context

    if (-not $identityOk) {
        $summary.status = "BLOCKED_NOT_BUILD112"
        $summary.reason = "The connected app is not Build112."
        Save-Json $summary "summary.json"
        throw "Connected app is not Build112."
    }

    if (-not $b16Ok) {
        $summary.status = "BLOCKED_NOT_B16"
        $summary.reason = "Build112 is not currently running the expected 32768-context PERFORMANCE16 16/16 profile."
        Save-Json $summary "summary.json"
        throw "Build112 is not currently running the expected B16 profile. No inference was sent."
    }

    $null = Measure-Case "warmup-512" 512
    $rows = @()
    foreach ($spec in @(
        @{ name = "medium-512"; target = 512 },
        @{ name = "long-2048"; target = 2048 },
        @{ name = "xlong-8192"; target = 8192 }
    )) {
        1..2 | ForEach-Object {
            $rows += Measure-Case ("{0}-r{1}" -f $spec.name, $_) $spec.target
        }
    }

    $rows | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 (Join-Path $outDir "measurements.json")
    $telemetryAfter = Get-Bonsai "/debug/telemetry"
    $prefillAfter = Get-Bonsai "/debug/prefill"
    Save-Json $telemetryAfter "telemetry-after.json"
    Save-Json $prefillAfter "prefill-after.json"

    $summary.measurements = @($rows | ForEach-Object {
        [ordered]@{
            label = $_.label
            prompt_tokens = $_.prompt_tokens_native
            prefill_ms = $_.prefill_ms
            prefill_ms_per_token = if ($_.prompt_tokens_native -gt 0) { $_.prefill_ms / $_.prompt_tokens_native } else { 0 }
            ttft_ms = $_.ttft_ms
            tokens_per_second = $_.tokens_per_second
            semantic_ok = $_.semantic_ok
        }
    })

    $summary.medians = @{}
    foreach ($name in @("medium-512","long-2048","xlong-8192")) {
        $group = @($rows | Where-Object { $_.label.StartsWith($name) })
        $summary.medians[$name] = [ordered]@{
            prompt_tokens = [int](($group.prompt_tokens_native | Sort-Object)[[math]::Floor(($group.Count - 1) / 2)])
            prefill_ms = [double](($group.prefill_ms | Measure-Object -Average).Average)
            prefill_ms_per_token = [double](($group | ForEach-Object { $_.prefill_ms / $_.prompt_tokens_native } | Measure-Object -Average).Average)
            ttft_ms = [double](($group.ttft_ms | Measure-Object -Average).Average)
            tokens_per_second = [double](($group.tokens_per_second | Measure-Object -Average).Average)
        }
    }

    $summary.status = "MEASUREMENT_COMPLETE"
    $summary.verdict = "B16 measured successfully. This run intentionally does not claim B8 speedup because it does not switch the installed runtime to B8."
}
catch {
    if (-not $summary.Contains("status")) {
        $summary.status = "ERROR"
        $summary.reason = $_.Exception.Message
    }
    $summary.error = $_.Exception.Message
}
finally {
    $summary.finished_at = (Get-Date).ToString("o")
    Save-Json $summary "summary.json"

    $readme = @"
Bonsai Build112 Quick Test

Purpose
- Verify Build112 identity.
- Verify 32768 context + PERFORMANCE16 + batch/ubatch 16/16.
- Run one warmup and six measured deterministic text requests at approximately 512, 2048 and 8192 prompt-token targets.
- Capture prefill, TTFT, decode rate, and memory/thermal telemetry before and after.

Safety
- No checkpoint/resume.
- No B8/B16 arm switching.
- No SAFE4 manipulation.
- No runtime configuration changes.
- No automatic inference retry.
- One API key is kept only in process memory.

Interpretation
- MEASUREMENT_COMPLETE means the B16 path was observed and measured.
- It is NOT a certification and it does NOT claim a B8 speedup.
- Compare the reported prefill_ms / prompt_tokens against an existing B8 baseline when available.

Files
- summary.json
- measurements.json
- governor.json
- build.json
- telemetry-before.json
- telemetry-after.json
- prefill-after.json
- models.json
- health.json
"@
    $readme | Set-Content -Encoding UTF8 (Join-Path $outDir "README.txt")

    $zip = Join-Path $scriptRoot ("RESULTS\Build112-Quick-" + $stamp + ".zip")
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zip -Force

    Write-Host ""
    Write-Host ("FINAL: {0}" -f $summary.status)
    if ($summary.Contains("verdict")) { Write-Host $summary.verdict }
    Write-Host ("Evidence ZIP: {0}" -f $zip)
    Write-Host ""
}
finally {
    Remove-Variable apiKey -ErrorAction SilentlyContinue
}
