[CmdletBinding()]
param(
  [string]$BaseUrl = "",
  [string]$OutputRoot = "",
  [int]$Repetitions = 3,
  [switch]$Include8192,
  [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Field($Object, [string]$Name) {
  if ($null -eq $Object) { return $null }
  if ($Object -is [System.Collections.IDictionary]) {
    if ($Object.Contains($Name)) { return $Object[$Name] }
    return $null
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}
function Save-Json([string]$Path, $Value) {
  $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $Path -Encoding UTF8
}
function Get-HttpStatus($Exception) {
  try { return [int]$Exception.Response.StatusCode } catch { return 0 }
}
function Convert-SecureToPlainText([Security.SecureString]$Secure) {
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
  try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
function Get-Sha256([string]$Text) {
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
    return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
  } finally { $sha.Dispose() }
}
function Get-Median([double[]]$Values) {
  if ($null -eq $Values -or $Values.Count -eq 0) { return $null }
  $sorted = @($Values | Sort-Object)
  $middle = [int][Math]::Floor($sorted.Count / 2)
  if (($sorted.Count % 2) -eq 1) { return [double]$sorted[$middle] }
  return ([double]$sorted[$middle - 1] + [double]$sorted[$middle]) / 2.0
}
function Get-ApiJson(
  [string]$Method,
  [string]$Path,
  $Body = $null,
  [string]$Key = "",
  [bool]$AuthRequired = $false,
  [int]$TimeoutSec = 600
) {
  $headers = @{}
  if ($AuthRequired -and -not [string]::IsNullOrWhiteSpace($Key)) {
    $headers["X-API-Key"] = $Key
  }
  $uri = $script:BaseUrl.TrimEnd("/") + $Path
  try {
    $args = @{
      Uri = $uri
      Method = $Method
      Headers = $headers
      TimeoutSec = $TimeoutSec
      ErrorAction = "Stop"
    }
    if ($null -ne $Body) {
      $args["ContentType"] = "application/json; charset=utf-8"
      $args["Body"] = ($Body | ConvertTo-Json -Depth 30 -Compress)
    }
    $json = Invoke-RestMethod @args
    return [ordered]@{ http_status = 200; json = $json; error = "" }
  } catch {
    $status = Get-HttpStatus $_.Exception
    $message = [string]$_.Exception.Message
    return [ordered]@{ http_status = $status; json = $null; error = $message }
  }
}
function Get-Snapshot([string]$Key, [bool]$AuthRequired) {
  $health = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 20
  if ($health.http_status -ne 200) { throw "API health unavailable (HTTP $($health.http_status))." }
  $buildResult = Get-ApiJson -Method GET -Path "/debug/build" -Key $Key -AuthRequired $AuthRequired
  if ($buildResult.http_status -ne 200) { throw "GET /debug/build failed (HTTP $($buildResult.http_status))." }
  $modelsResult = Get-ApiJson -Method GET -Path "/v1/models" -Key $Key -AuthRequired $AuthRequired
  if ($modelsResult.http_status -ne 200) { throw "GET /v1/models failed (HTTP $($modelsResult.http_status))." }
  $prefillResult = Get-ApiJson -Method GET -Path "/debug/prefill" -Key $Key -AuthRequired $AuthRequired
  if ($prefillResult.http_status -ne 200) { throw "GET /debug/prefill failed (HTTP $($prefillResult.http_status))." }
  $modelRows = @((Get-Field $modelsResult.json "data"))
  if ($modelRows.Count -lt 1) { throw "The API returned no model IDs." }
  return [ordered]@{
    health = $health.json
    build = $buildResult.json
    model_id = [string](Get-Field $modelRows[0] "id")
    prefill = $prefillResult.json
    captured_at = (Get-Date).ToString("o")
  }
}
function Get-Arm($Snapshot) {
  $trace = Get-Field $Snapshot.prefill "ptq1_tensorops_trace"
  return [string](Get-Field $trace "launch_arm")
}
function Get-TraceType([string]$Line, [string]$Name) {
  if ([string]::IsNullOrWhiteSpace($Line)) { return $null }
  $match = [regex]::Match($Line, "(?:^|\s)$([regex]::Escape($Name))=(\d+)")
  if (-not $match.Success) { return $null }
  return [int]$match.Groups[1].Value
}
function Assert-ExperimentShape($Snapshot, [string]$ExpectedSHA = "") {
  $sha = [string](Get-Field $Snapshot.build "source_git_sha")
  $model = [string](Get-Field $Snapshot.prefill "model_file_name")
  $context = [int](Get-Field $Snapshot.prefill "api_context")
  $batch = [int](Get-Field $Snapshot.prefill "api_batch")
  $ubatch = [int](Get-Field $Snapshot.prefill "api_ubatch")
  $kv = Get-Field $Snapshot.prefill "text_kv_reuse"
  if ([string]::IsNullOrWhiteSpace($sha) -or $sha -eq "unavailable") { throw "App source SHA is unavailable." }
  if (-not $model.Contains("PTQ1_0")) { throw "Main model is not PTQ1_0: $model" }
  if ($context -ne 16384 -or $batch -ne 16 -or $ubatch -ne 16) {
    throw "Expected Context/Batch/UBatch = 16384/16/16; observed $context/$batch/$ubatch."
  }
  if ($null -eq $kv -or $null -eq (Get-Field $kv "enabled")) { throw "Text KV Reuse state is unavailable; refusing to benchmark." }
  if ([bool](Get-Field $kv "enabled")) { throw "Text KV Reuse is enabled. Disable it before A/B; this test will not change it." }
  if (-not [string]::IsNullOrWhiteSpace($ExpectedSHA) -and $sha -ne $ExpectedSHA) {
    throw "App source SHA changed between arms ($ExpectedSHA vs $sha)."
  }
  return $sha
}
function Invoke-Chat([string]$Model, [string]$Prompt, [int]$MaxTokens, [int]$Seed, [string]$Key, [bool]$AuthRequired) {
  $body = [ordered]@{
    model = $Model
    messages = @([ordered]@{ role = "user"; content = $Prompt })
    max_tokens = $MaxTokens
    temperature = 0
    top_p = 1.0
    seed = $Seed
    stream = $false
  }
  return Get-ApiJson -Method POST -Path "/v1/chat/completions" -Body $body -Key $Key -AuthRequired $AuthRequired -TimeoutSec 600
}
function Get-PromptTokenCount([string]$Model, [string]$Prompt, [string]$Key, [bool]$AuthRequired) {
  $result = Invoke-Chat -Model $Model -Prompt $Prompt -MaxTokens 1 -Seed 112 -Key $Key -AuthRequired $AuthRequired
  if ($result.http_status -ne 200) { throw "Prompt calibration failed (HTTP $($result.http_status)): $($result.error)" }
  $usage = Get-Field $result.json "usage"
  $count = Get-Field $usage "prompt_tokens"
  if ($null -eq $count) { throw "Prompt calibration response omitted usage.prompt_tokens." }
  return [int]$count
}
function New-ExactPrompt([int]$Target, [string]$Model, [string]$Key, [bool]$AuthRequired) {
  $prefix = "PTQ1_0 engine performance benchmark. Continue with a long uninterrupted sequence of the letter A separated by spaces. Do not explain or conclude. FILLER:"
  $low = 0
  $high = $Target * 2
  $bestCount = -1
  $bestActual = -1
  $bestDelta = [int]::MaxValue
  for ($i = 0; $i -lt 24 -and $low -le $high; $i++) {
    $mid = [int][Math]::Floor(($low + $high) / 2)
    $prompt = $prefix + (" x" * $mid)
    $actual = Get-PromptTokenCount -Model $Model -Prompt $prompt -Key $Key -AuthRequired $AuthRequired
    $delta = [Math]::Abs($actual - $Target)
    if ($delta -lt $bestDelta) { $bestCount = $mid; $bestActual = $actual; $bestDelta = $delta }
    if ($actual -eq $Target) { return $prompt }
    if ($actual -lt $Target) { $low = $mid + 1 } else { $high = $mid - 1 }
  }
  $scanLow = [Math]::Max(0, $bestCount - 12)
  $scanHigh = $bestCount + 12
  for ($count = $scanLow; $count -le $scanHigh; $count++) {
    $prompt = $prefix + (" x" * $count)
    $actual = Get-PromptTokenCount -Model $Model -Prompt $prompt -Key $Key -AuthRequired $AuthRequired
    if ($actual -eq $Target) { return $prompt }
    $delta = [Math]::Abs($actual - $Target)
    if ($delta -lt $bestDelta) { $bestCount = $count; $bestActual = $actual; $bestDelta = $delta }
  }
  throw "Could not calibrate an exact $Target-token prompt; nearest observed count was $bestActual. No performance samples were accepted."
}
function Get-TraceSummary($Prefill) {
  $trace = Get-Field $Prefill "ptq1_tensorops_trace"
  $line = [string](Get-Field $trace "input_type_line")
  return [ordered]@{
    trace = $trace
    weight_type = Get-TraceType -Line $line -Name "weight_type"
    activation_type = Get-TraceType -Line $line -Name "activation_type"
    output_type = Get-TraceType -Line $line -Name "output_type"
  }
}
function Assert-ActualPTQ1Type($Snapshot, [string]$Arm) {
  $t = Get-TraceSummary $Snapshot.prefill
  if (-not [bool](Get-Field $t.trace "input_type_observed")) { throw "$Arm did not observe actual GGML operand types in the native Metal path." }
  if ($t.weight_type -ne 143 -or $t.activation_type -ne 0 -or $t.output_type -ne 0) {
    throw "$Arm actual types differ from PTQ1_0 x F32 -> F32 (weight=$($t.weight_type), activation=$($t.activation_type), output=$($t.output_type))."
  }
  return $t
}
function Get-OutputText($Response) {
  $choices = @((Get-Field $Response "choices"))
  if ($choices.Count -lt 1) { return "" }
  $message = Get-Field $choices[0] "message"
  return [string](Get-Field $message "content")
}
function Invoke-MeasuredRequest(
  [string]$Arm,
  [int]$Target,
  [int]$Repetition,
  [string]$Prompt,
  [string]$Model,
  [string]$Key,
  [bool]$AuthRequired,
  [string]$SourceSHA,
  [string]$ModelFile
) {
  $seed = 112 + $Repetition
  $request = Invoke-Chat -Model $Model -Prompt $Prompt -MaxTokens 128 -Seed $seed -Key $Key -AuthRequired $AuthRequired
  $sample = [ordered]@{
    schema = "ptq1-metal-ab-sample-v1"
    arm = $Arm
    target_prompt_tokens = $Target
    repetition = $Repetition
    seed = $seed
    http_status = $request.http_status
    request_completed = ($request.http_status -eq 200)
    source_git_sha = $SourceSHA
    model_id = $Model
    model_file_name = $ModelFile
    actual_prompt_tokens = $null
    actual_completion_tokens = $null
    finish_reason = ""
    ttft_ms = $null
    prefill_ms = $null
    prefill_tokens_per_second = $null
    decode_ms = $null
    decode_tokens_per_second = $null
    weight_type = $null
    activation_type = $null
    output_type = $null
    route_selected = $false
    pipeline_ready = $false
    dispatch_enqueued = $false
    fallback_observed = $false
    context = $null
    batch = $null
    ubatch = $null
    metal_current_allocated_bytes = $null
    metal_working_set_headroom_bytes = $null
    thermal_state = "unknown"
    output_sha256 = ""
    prompt_sha256 = Get-Sha256 $Prompt
    gguf_general_file_type_raw = ""
    tensor_api_enabled = $false
    valid = $false
    invalid_reason = ""
  }
  if ($request.http_status -ne 200) {
    $sample.invalid_reason = "HTTP_$($request.http_status): $($request.error)"
    return $sample
  }
  $usage = Get-Field $request.json "usage"
  $promptTokens = Get-Field $usage "prompt_tokens"
  $completionTokens = Get-Field $usage "completion_tokens"
  $choices = @((Get-Field $request.json "choices"))
  if ($choices.Count -lt 1) {
    $sample.invalid_reason = "MISSING_CHOICES"
    return $sample
  }
  $sample.actual_prompt_tokens = [int]$promptTokens
  $sample.actual_completion_tokens = [int]$completionTokens
  $sample.finish_reason = [string](Get-Field $choices[0] "finish_reason")
  $output = Get-OutputText $request.json
  $sample.output_sha256 = Get-Sha256 $output

  $after = Get-ApiJson -Method GET -Path "/debug/prefill" -Key $Key -AuthRequired $AuthRequired -TimeoutSec 30
  if ($after.http_status -ne 200) {
    $sample.invalid_reason = "POST_OK_BUT_PREFILL_DIAGNOSTICS_HTTP_$($after.http_status)"
    return $sample
  }
  $prefill = $after.json
  $observation = Get-Field $prefill "last_observation"
  $traceInfo = Get-TraceSummary $prefill
  $sample.weight_type = $traceInfo.weight_type
  $sample.activation_type = $traceInfo.activation_type
  $sample.output_type = $traceInfo.output_type
  $sample.tensor_api_enabled = [bool](Get-Field $traceInfo.trace "tensor_api_enabled")
  $sample.gguf_general_file_type_raw = [string](Get-Field $prefill "model_general_file_type_raw")
  $sample.route_selected = [bool](Get-Field $traceInfo.trace "route_selected")
  $sample.pipeline_ready = [bool](Get-Field $traceInfo.trace "pipeline_ready")
  $sample.dispatch_enqueued = [bool](Get-Field $traceInfo.trace "dispatch_enqueued")
  $sample.fallback_observed = [bool](Get-Field $traceInfo.trace "fallback_observed")
  $sample.context = [int](Get-Field $prefill "api_context")
  $sample.batch = [int](Get-Field $prefill "api_batch")
  $sample.ubatch = [int](Get-Field $prefill "api_ubatch")
  $sample.metal_current_allocated_bytes = Get-Field $prefill "metal_current_allocated_bytes"
  $sample.metal_working_set_headroom_bytes = Get-Field $prefill "metal_working_set_headroom_bytes"
  $sample.thermal_state = [string](Get-Field $prefill "thermal_state")
  if ($null -eq $observation) {
    $sample.invalid_reason = "MISSING_LAST_OBSERVATION"
    return $sample
  }
  $sample.ttft_ms = [double](Get-Field $observation "ttft_ms")
  $sample.prefill_ms = [double](Get-Field $observation "prefill_ms")
  $decodeTPS = [double](Get-Field $observation "tokens_per_second")
  $sample.decode_tokens_per_second = $decodeTPS
  if ($sample.prefill_ms -gt 0) {
    $sample.prefill_tokens_per_second = [double]$sample.actual_prompt_tokens / ($sample.prefill_ms / 1000.0)
  }
  if ($decodeTPS -gt 0) {
    $sample.decode_ms = 1000.0 * [double]$sample.actual_completion_tokens / $decodeTPS
  }
  $observationPromptTokens = Get-Field $observation "prompt_tokens"
  $observationCompletionTokens = Get-Field $observation "completion_tokens"
  if ($observationPromptTokens -ne $sample.actual_prompt_tokens -or $observationCompletionTokens -ne $sample.actual_completion_tokens) { $sample.invalid_reason = "RESPONSE_USAGE_NATIVE_OBSERVATION_MISMATCH" }
  elseif ($sample.actual_prompt_tokens -ne $Target) { $sample.invalid_reason = "INPUT_TOKEN_COUNT_MISMATCH" }
  elseif ($sample.actual_completion_tokens -ne 128) { $sample.invalid_reason = "OUTPUT_TOKEN_COUNT_NOT_128" }
  elseif ($sample.prefill_ms -le 0 -or $sample.ttft_ms -le 0 -or $decodeTPS -le 0) { $sample.invalid_reason = "INVALID_TIMING_FIELDS" }
  elseif ($sample.thermal_state -in @("serious", "critical")) { $sample.invalid_reason = "THERMAL_STATE_$($sample.thermal_state.ToUpperInvariant())" }
  else { $sample.valid = $true }
  return $sample
}
function Save-JsonLine([string]$Path, $Value) {
  Add-Content -LiteralPath $Path -Value ($Value | ConvertTo-Json -Depth 30 -Compress) -Encoding UTF8
}
function Invoke-Warmup([string]$Arm, [int]$Target, [string]$Prompt, [string]$Model, [string]$Key, [bool]$AuthRequired) {
  $result = Invoke-Chat -Model $Model -Prompt $Prompt -MaxTokens 128 -Seed 111 -Key $Key -AuthRequired $AuthRequired
  $record = [ordered]@{
    arm = $Arm
    target_tokens = $Target
    http_status = $result.http_status
    request_completed = ($result.http_status -eq 200)
    prompt_tokens = $null
    completion_tokens = $null
    finish_reason = ""
  }
  if ($result.http_status -eq 200) {
    $usage = Get-Field $result.json "usage"
    $record.prompt_tokens = Get-Field $usage "prompt_tokens"
    $record.completion_tokens = Get-Field $usage "completion_tokens"
    $choices = @((Get-Field $result.json "choices"))
    if ($choices.Count -gt 0) { $record.finish_reason = [string](Get-Field $choices[0] "finish_reason") }
  } else {
    $record.error = $result.error
  }
  return $record
}
function Write-Manifest([string]$Directory) {
  $lines = @()
  Get-ChildItem -LiteralPath $Directory -Recurse -File | Where-Object { $_.Name -ne "SHA256SUMS.txt" } | Sort-Object FullName | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = $_.FullName.Substring($Directory.TrimEnd([char]92).Length + 1).Replace([string][char]92, '/')
    $lines += "$hash  $relative"
  }
  $lines | Set-Content -LiteralPath (Join-Path $Directory "SHA256SUMS.txt") -Encoding UTF8
}
function Get-Comparison([int]$Target, $Samples) {
  $baseline = @($Samples | Where-Object { $_.arm -eq "BASELINE" -and $_.target_prompt_tokens -eq $Target -and $_.valid })
  $candidate = @($Samples | Where-Object { $_.arm -eq "CANDIDATE" -and $_.target_prompt_tokens -eq $Target -and $_.valid })
  if ($baseline.Count -lt $script:Repetitions -or $candidate.Count -lt $script:Repetitions) {
    return [ordered]@{ target_tokens = $Target; valid_baseline = $baseline.Count; valid_candidate = $candidate.Count; sufficient_samples = $false }
  }
  $basePrefill = Get-Median ([double[]]@($baseline | ForEach-Object { [double]$_.prefill_tokens_per_second }))
  $candPrefill = Get-Median ([double[]]@($candidate | ForEach-Object { [double]$_.prefill_tokens_per_second }))
  $baseTTFT = Get-Median ([double[]]@($baseline | ForEach-Object { [double]$_.ttft_ms }))
  $candTTFT = Get-Median ([double[]]@($candidate | ForEach-Object { [double]$_.ttft_ms }))
  $baseDecode = Get-Median ([double[]]@($baseline | ForEach-Object { [double]$_.decode_tokens_per_second }))
  $candDecode = Get-Median ([double[]]@($candidate | ForEach-Object { [double]$_.decode_tokens_per_second }))
  $baseMem = Get-Median ([double[]]@($baseline | ForEach-Object { [double]$_.metal_current_allocated_bytes }))
  $candMem = Get-Median ([double[]]@($candidate | ForEach-Object { [double]$_.metal_current_allocated_bytes }))
  $prefillGain = 100.0 * ($candPrefill / $basePrefill - 1.0)
  $ttftGain = 100.0 * (1.0 - $candTTFT / $baseTTFT)
  $decodeChange = 100.0 * ($candDecode / $baseDecode - 1.0)
  $memoryDelta = $candMem - $baseMem
  $hashMatch = $true
  foreach ($b in $baseline) {
    $c = @($candidate | Where-Object { $_.repetition -eq $b.repetition } | Select-Object -First 1)
    if ($c.Count -ne 1 -or $c[0].output_sha256 -ne $b.output_sha256) { $hashMatch = $false }
  }
  return [ordered]@{
    target_tokens = $Target
    valid_baseline = $baseline.Count
    valid_candidate = $candidate.Count
    sufficient_samples = $true
    baseline_median_prefill_tokens_per_second = [Math]::Round($basePrefill, 4)
    candidate_median_prefill_tokens_per_second = [Math]::Round($candPrefill, 4)
    prefill_improvement_pct = [Math]::Round($prefillGain, 3)
    baseline_median_ttft_ms = [Math]::Round($baseTTFT, 3)
    candidate_median_ttft_ms = [Math]::Round($candTTFT, 3)
    ttft_improvement_pct = [Math]::Round($ttftGain, 3)
    baseline_median_decode_tokens_per_second = [Math]::Round($baseDecode, 4)
    candidate_median_decode_tokens_per_second = [Math]::Round($candDecode, 4)
    decode_throughput_change_pct = [Math]::Round($decodeChange, 3)
    baseline_median_metal_allocated_bytes = [Math]::Round($baseMem, 0)
    candidate_median_metal_allocated_bytes = [Math]::Round($candMem, 0)
    metal_allocated_delta_bytes = [Math]::Round($memoryDelta, 0)
    output_hashes_match = $hashMatch
    prefill_gate_pass = ($prefillGain -ge 15.0)
    ttft_gate_pass = ($ttftGain -ge 10.0)
    decode_gate_pass = ($decodeChange -ge -5.0)
    memory_gate_pass = ($memoryDelta -le 1073741824)
    overall_gate_pass = (($prefillGain -ge 15.0) -and ($ttftGain -ge 10.0) -and ($decodeChange -ge -5.0) -and ($memoryDelta -le 1073741824) -and $hashMatch)
  }
}

if ($SelfTest) {
  $a = Get-Field ([ordered]@{ auth_required = $true }) "auth_required"
  if (-not $a) { throw "SelfTest failed: IDictionary field access." }
  $b = Get-Field ([pscustomobject]@{ api_context = 16384 }) "api_context"
  if ([int]$b -ne 16384) { throw "SelfTest failed: PSCustomObject field access." }
  if ((Get-Sha256 "abc").Length -ne 64) { throw "SelfTest failed: SHA256." }
  if ((Get-Median ([double[]]@(1, 3, 5))) -ne 3) { throw "SelfTest failed: median." }
  Write-Output "PTQ1_METAL_AB_SELFTEST: PASS"
  exit 0
}

if ($Repetitions -lt 3) { throw "At least three repetitions are required." }
if ([string]::IsNullOrWhiteSpace($BaseUrl)) { $BaseUrl = Read-Host "Bonsai API Base URL (for example http://192.168.1.10:8080)" }
$BaseUrl = $BaseUrl.TrimEnd("/")
if ($BaseUrl -notmatch "^https?://") { throw "BaseUrl must start with http:// or https://." }
$script:BaseUrl = $BaseUrl
$script:Repetitions = $Repetitions
$targets = @(512, 2048)
if ($Include8192) { $targets += 8192 }
else {
  $includeChoice = Read-Host "Include optional 8192-token case? (y/N)"
  if ($includeChoice -match '^(?i:y|yes)
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $PSScriptRoot "RESULTS" }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionDir = Join-Path $OutputRoot "PTQ1_METAL_AB_$stamp"
$promptDir = Join-Path $sessionDir "prompts"
New-Item -ItemType Directory -Path $promptDir -Force | Out-Null
$samplesPath = Join-Path $sessionDir "samples.jsonl"
$warmupsPath = Join-Path $sessionDir "warmups.jsonl"
$summaryPath = Join-Path $sessionDir "summary.json"
$allSamples = New-Object System.Collections.Generic.List[object]
$summary = [ordered]@{
  schema = "bonsai-ptq1-metal-ab-result-v1"
  status = "IN_PROGRESS"
  created_at = (Get-Date).ToString("o")
  base_url = $BaseUrl
  repetitions_required = $Repetitions
  target_prompt_tokens = $targets
  output_tokens_required = 128
  context_batch_ubatch_required = "16384/16/16"
  auth_key_saved = $false
  source_git_sha = ""
  model_id = ""
  model_file_name = ""
  baseline = $null
  candidate = $null
  candidate_execution_verified = $false
  comparisons = @()
  error = ""
}
$exitCode = 0
$key = ""
$authRequired = $false
try {
  Write-Host "Checking current API and authentication mode..."
  $health = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 20
  if ($health.http_status -ne 200) { throw "API health check failed (HTTP $($health.http_status))." }
  $authValue = Get-Field $health.json "auth_required"
  if ($null -eq $authValue -or $authValue -isnot [bool]) { throw "Cannot determine auth_required from /health." }
  $authRequired = [bool]$authValue
  if ($authRequired) {
    $secure = Read-Host "API Key (held in memory only; never written to results)" -AsSecureString
    $key = Convert-SecureToPlainText $secure
    if ([string]::IsNullOrWhiteSpace($key)) { throw "An API key is required by /health.auth_required=true." }
  } else {
    Write-Host "API reports auth_required=false; no key will be sent or requested."
  }

  $snapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
  $sourceSHA = Assert-ExperimentShape -Snapshot $snapshot
  $arm = Get-Arm $snapshot
  if ($arm -ne "BASELINE") {
    Write-Host "The app is currently in $arm mode. Set the Metal TensorOps candidate toggle OFF, keep PTQ1_0 16K/B16 ON, fully quit and relaunch Bonsai."
    [void](Read-Host "Press Enter when API has restarted in BASELINE mode")
    $healthReady = $false
    for ($i = 0; $i -lt 120; $i++) {
      $h = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 10
      if ($h.http_status -eq 200) { $healthReady = $true; break }
      Start-Sleep -Seconds 5
    }
    if (-not $healthReady) { throw "BASELINE API did not become ready within 10 minutes." }
    $snapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
    $sourceSHA = Assert-ExperimentShape -Snapshot $snapshot
    $arm = Get-Arm $snapshot
  }
  if ($arm -ne "BASELINE") { throw "Expected BASELINE arm after relaunch, observed '$arm'." }
  $modelID = $snapshot.model_id
  $modelFile = [string](Get-Field $snapshot.prefill "model_file_name")
  $summary.source_git_sha = $sourceSHA
  $summary.model_id = $modelID
  $summary.model_file_name = $modelFile
  $summary.baseline = [ordered]@{ source_git_sha = $sourceSHA; model_id = $modelID; model_file_name = $modelFile; context = 16384; batch = 16; ubatch = 16 }

  Write-Host "Calibrating exact prompt token counts: $($targets -join ', ')"
  $prompts = @{}
  foreach ($target in $targets) {
    $prompt = New-ExactPrompt -Target $target -Model $modelID -Key $key -AuthRequired $authRequired
    $prompts[[string]$target] = $prompt
    Set-Content -LiteralPath (Join-Path $promptDir "prompt_$target.txt") -Value $prompt -Encoding UTF8
  }

  Write-Host "Running BASELINE warmups and measurements..."
  foreach ($target in $targets) {
    $warm = Invoke-Warmup -Arm "BASELINE" -Target $target -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired
    Save-JsonLine -Path $warmupsPath -Value $warm
    if (-not $warm.request_completed -or [int]$warm.prompt_tokens -ne $target -or [int]$warm.completion_tokens -ne 128) {
      throw "BASELINE warmup invalid for target $target (prompt=$($warm.prompt_tokens), output=$($warm.completion_tokens), HTTP=$($warm.http_status))."
    }
    $afterWarm = Get-Snapshot -Key $key -AuthRequired $authRequired
    $typeEvidence = Assert-ActualPTQ1Type -Snapshot $afterWarm -Arm "BASELINE"
    if ((Get-Arm $afterWarm) -ne "BASELINE") { throw "BASELINE arm changed during the run." }
    if ([bool](Get-Field $typeEvidence.trace "route_selected")) { throw "BASELINE unexpectedly selected the custom PTQ1 TensorOps route." }

    for ($rep = 1; $rep -le $Repetitions; $rep++) {
      $sample = Invoke-MeasuredRequest -Arm "BASELINE" -Target $target -Repetition $rep -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired -SourceSHA $sourceSHA -ModelFile $modelFile
      $allSamples.Add($sample)
      Save-JsonLine -Path $samplesPath -Value $sample
      Write-Host ("BASELINE {0} tokens, sample {1}/{2}: valid={3}, TTFT={4} ms, prefill={5} ms, decode={6} tok/s" -f $target,$rep,$Repetitions,$sample.valid,$sample.ttft_ms,$sample.prefill_ms,$sample.decode_tokens_per_second)
    }
  }
  $baselineEnd = Get-Snapshot -Key $key -AuthRequired $authRequired
  $baselineTrace = Get-Field $baselineEnd.prefill "ptq1_tensorops_trace"
  Save-Json -Path (Join-Path $sessionDir "trace-baseline.json") -Value $baselineTrace

  Write-Host ""
  Write-Host "BASELINE samples saved. Now switch Bonsai to CANDIDATE:"
  Write-Host "  1. Keep 'PTQ1_0 A/B fixed 16K / B16' ON."
  Write-Host "  2. Turn 'Metal TensorOps candidate (next launch)' ON."
  Write-Host "  3. Fully quit Bonsai and relaunch it; start the API and keep the screen awake."
  [void](Read-Host "Press Enter after the candidate API has restarted")
  $candidateReady = $false
  for ($i = 0; $i -lt 120; $i++) {
    $h = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 10
    if ($h.http_status -eq 200) { $candidateReady = $true; break }
    Start-Sleep -Seconds 5
  }
  if (-not $candidateReady) { throw "CANDIDATE API did not become ready within 10 minutes." }
  $candidateSnapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
  $candidateSHA = Assert-ExperimentShape -Snapshot $candidateSnapshot -ExpectedSHA $sourceSHA
  if ((Get-Arm $candidateSnapshot) -ne "CANDIDATE") { throw "Expected CANDIDATE arm after relaunch." }
  if (-not [bool](Get-Field (Get-Field $candidateSnapshot.prefill "ptq1_tensorops_trace") "tensor_api_enabled")) {
    throw "CANDIDATE arm did not enable the Metal Tensor API."
  }
  $candidateModelFile = [string](Get-Field $candidateSnapshot.prefill "model_file_name")
  if ($candidateModelFile -ne $modelFile -or $candidateSnapshot.model_id -ne $modelID) { throw "Model identity changed between arms." }
  $summary.candidate = [ordered]@{ source_git_sha = $candidateSHA; model_id = $candidateSnapshot.model_id; model_file_name = $candidateModelFile; context = 16384; batch = 16; ubatch = 16 }

  Write-Host "Running CANDIDATE warmups and measurements..."
  foreach ($target in $targets) {
    $warm = Invoke-Warmup -Arm "CANDIDATE" -Target $target -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired
    Save-JsonLine -Path $warmupsPath -Value $warm
    if (-not $warm.request_completed -or [int]$warm.prompt_tokens -ne $target -or [int]$warm.completion_tokens -ne 128) {
      throw "CANDIDATE warmup invalid for target $target (prompt=$($warm.prompt_tokens), output=$($warm.completion_tokens), HTTP=$($warm.http_status))."
    }
    $afterWarm = Get-Snapshot -Key $key -AuthRequired $authRequired
    $typeEvidence = Assert-ActualPTQ1Type -Snapshot $afterWarm -Arm "CANDIDATE"
    $trace = $typeEvidence.trace
    if (-not [bool](Get-Field $trace "route_selected") -or
        -not [bool](Get-Field $trace "pipeline_ready") -or
        -not [bool](Get-Field $trace "dispatch_enqueued") -or
        [bool](Get-Field $trace "fallback_observed")) {
      throw "CANDIDATE warmup completed but the PTQ1 custom route/pipeline/dispatch evidence is incomplete."
    }
    if ((Get-Arm $afterWarm) -ne "CANDIDATE") { throw "CANDIDATE arm changed during the run." }
    if ($target -eq $targets[0]) {
      $summary.candidate_execution_verified = $true
      Save-Json -Path (Join-Path $sessionDir "trace-candidate.json") -Value $trace
      $traceSHA = [string](Get-Field (Get-Field $trace "trace_header") "app_source_sha")
      if (-not [string]::IsNullOrWhiteSpace($traceSHA) -and $traceSHA -ne $sourceSHA) { throw "PTQ1 native trace source SHA does not match the app source SHA." }
    }

    for ($rep = 1; $rep -le $Repetitions; $rep++) {
      $sample = Invoke-MeasuredRequest -Arm "CANDIDATE" -Target $target -Repetition $rep -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired -SourceSHA $candidateSHA -ModelFile $candidateModelFile
      $allSamples.Add($sample)
      Save-JsonLine -Path $samplesPath -Value $sample
      Write-Host ("CANDIDATE {0} tokens, sample {1}/{2}: valid={3}, TTFT={4} ms, prefill={5} ms, decode={6} tok/s" -f $target,$rep,$Repetitions,$sample.valid,$sample.ttft_ms,$sample.prefill_ms,$sample.decode_tokens_per_second)
    }
  }

  $comparisons = @()
  foreach ($target in $targets) { $comparisons += Get-Comparison -Target $target -Samples $allSamples }
  $summary.comparisons = $comparisons
  $allComplete = $true
  $allGates = $true
  foreach ($comparison in $comparisons) {
    if (-not $comparison.sufficient_samples) { $allComplete = $false; $allGates = $false }
    elseif (-not $comparison.overall_gate_pass) { $allGates = $false }
  }
  if (-not $summary.candidate_execution_verified -or -not $allComplete) {
    $summary.status = "BLOCKED_NEEDS_ENGINE_EVIDENCE"
    $exitCode = 2
  } elseif ($allGates) {
    $summary.status = "M5_PERFORMANCE_GAIN_VERIFIED"
    $exitCode = 0
  } else {
    $summary.status = "CANDIDATE_NO_GAIN"
    $exitCode = 1
  }
} catch {
  $summary.status = "BLOCKED_NEEDS_ENGINE_EVIDENCE"
  $summary.error = [string]$_.Exception.Message
  $exitCode = 2
  Write-Host "A/B stopped: $($summary.error)" -ForegroundColor Yellow
} finally {
  $summary.finished_at = (Get-Date).ToString("o")
  $summary.sample_count = $allSamples.Count
  $summary.valid_sample_count = @($allSamples | Where-Object { $_.valid }).Count
  Save-Json -Path $summaryPath -Value $summary
  if ($allSamples.Count -gt 0) {
    $allSamples | Export-Csv -LiteralPath (Join-Path $sessionDir "samples.csv") -NoTypeInformation -Encoding UTF8
  }
  Write-Manifest -Directory $sessionDir
  $zipPath = Join-Path $OutputRoot "BONSAI_PTQ1_METAL_AB_RESULT_$stamp.zip"
  Compress-Archive -Path (Join-Path $sessionDir "*") -DestinationPath $zipPath -Force
  $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath "$zipPath.sha256" -Value "$zipHash  $(Split-Path -Leaf $zipPath)" -Encoding UTF8
  Write-Host ""
  Write-Host "Result: $($summary.status)"
  Write-Host "Raw samples: $samplesPath"
  Write-Host "Summary: $summaryPath"
  Write-Host "Result ZIP: $zipPath"
  Write-Host "SHA-256: $zipHash"
}
exit $exitCode
) { $targets += 8192 }
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $PSScriptRoot "RESULTS" }
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sessionDir = Join-Path $OutputRoot "PTQ1_METAL_AB_$stamp"
$promptDir = Join-Path $sessionDir "prompts"
New-Item -ItemType Directory -Path $promptDir -Force | Out-Null
$samplesPath = Join-Path $sessionDir "samples.jsonl"
$warmupsPath = Join-Path $sessionDir "warmups.jsonl"
$summaryPath = Join-Path $sessionDir "summary.json"
$allSamples = New-Object System.Collections.Generic.List[object]
$summary = [ordered]@{
  schema = "bonsai-ptq1-metal-ab-result-v1"
  status = "IN_PROGRESS"
  created_at = (Get-Date).ToString("o")
  base_url = $BaseUrl
  repetitions_required = $Repetitions
  target_prompt_tokens = $targets
  output_tokens_required = 128
  context_batch_ubatch_required = "16384/16/16"
  auth_key_saved = $false
  source_git_sha = ""
  model_id = ""
  model_file_name = ""
  baseline = $null
  candidate = $null
  candidate_execution_verified = $false
  comparisons = @()
  error = ""
}
$exitCode = 0
$key = ""
$authRequired = $false
try {
  Write-Host "Checking current API and authentication mode..."
  $health = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 20
  if ($health.http_status -ne 200) { throw "API health check failed (HTTP $($health.http_status))." }
  $authValue = Get-Field $health.json "auth_required"
  if ($null -eq $authValue -or $authValue -isnot [bool]) { throw "Cannot determine auth_required from /health." }
  $authRequired = [bool]$authValue
  if ($authRequired) {
    $secure = Read-Host "API Key (held in memory only; never written to results)" -AsSecureString
    $key = Convert-SecureToPlainText $secure
    if ([string]::IsNullOrWhiteSpace($key)) { throw "An API key is required by /health.auth_required=true." }
  } else {
    Write-Host "API reports auth_required=false; no key will be sent or requested."
  }

  $snapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
  $sourceSHA = Assert-ExperimentShape -Snapshot $snapshot
  $arm = Get-Arm $snapshot
  if ($arm -ne "BASELINE") {
    Write-Host "The app is currently in $arm mode. Set the Metal TensorOps candidate toggle OFF, keep PTQ1_0 16K/B16 ON, fully quit and relaunch Bonsai."
    [void](Read-Host "Press Enter when API has restarted in BASELINE mode")
    $healthReady = $false
    for ($i = 0; $i -lt 120; $i++) {
      $h = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 10
      if ($h.http_status -eq 200) { $healthReady = $true; break }
      Start-Sleep -Seconds 5
    }
    if (-not $healthReady) { throw "BASELINE API did not become ready within 10 minutes." }
    $snapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
    $sourceSHA = Assert-ExperimentShape -Snapshot $snapshot
    $arm = Get-Arm $snapshot
  }
  if ($arm -ne "BASELINE") { throw "Expected BASELINE arm after relaunch, observed '$arm'." }
  $modelID = $snapshot.model_id
  $modelFile = [string](Get-Field $snapshot.prefill "model_file_name")
  $summary.source_git_sha = $sourceSHA
  $summary.model_id = $modelID
  $summary.model_file_name = $modelFile
  $summary.baseline = [ordered]@{ source_git_sha = $sourceSHA; model_id = $modelID; model_file_name = $modelFile; context = 16384; batch = 16; ubatch = 16 }

  Write-Host "Calibrating exact prompt token counts: $($targets -join ', ')"
  $prompts = @{}
  foreach ($target in $targets) {
    $prompt = New-ExactPrompt -Target $target -Model $modelID -Key $key -AuthRequired $authRequired
    $prompts[[string]$target] = $prompt
    Set-Content -LiteralPath (Join-Path $promptDir "prompt_$target.txt") -Value $prompt -Encoding UTF8
  }

  Write-Host "Running BASELINE warmups and measurements..."
  foreach ($target in $targets) {
    $warm = Invoke-Warmup -Arm "BASELINE" -Target $target -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired
    Save-JsonLine -Path $warmupsPath -Value $warm
    if (-not $warm.request_completed -or [int]$warm.prompt_tokens -ne $target -or [int]$warm.completion_tokens -ne 128) {
      throw "BASELINE warmup invalid for target $target (prompt=$($warm.prompt_tokens), output=$($warm.completion_tokens), HTTP=$($warm.http_status))."
    }
    $afterWarm = Get-Snapshot -Key $key -AuthRequired $authRequired
    $typeEvidence = Assert-ActualPTQ1Type -Snapshot $afterWarm -Arm "BASELINE"
    if ((Get-Arm $afterWarm) -ne "BASELINE") { throw "BASELINE arm changed during the run." }
    if ([bool](Get-Field $typeEvidence.trace "route_selected")) { throw "BASELINE unexpectedly selected the custom PTQ1 TensorOps route." }

    for ($rep = 1; $rep -le $Repetitions; $rep++) {
      $sample = Invoke-MeasuredRequest -Arm "BASELINE" -Target $target -Repetition $rep -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired -SourceSHA $sourceSHA -ModelFile $modelFile
      $allSamples.Add($sample)
      Save-JsonLine -Path $samplesPath -Value $sample
      Write-Host ("BASELINE {0} tokens, sample {1}/{2}: valid={3}, TTFT={4} ms, prefill={5} ms, decode={6} tok/s" -f $target,$rep,$Repetitions,$sample.valid,$sample.ttft_ms,$sample.prefill_ms,$sample.decode_tokens_per_second)
    }
  }
  $baselineEnd = Get-Snapshot -Key $key -AuthRequired $authRequired
  $baselineTrace = Get-Field $baselineEnd.prefill "ptq1_tensorops_trace"
  Save-Json -Path (Join-Path $sessionDir "trace-baseline.json") -Value $baselineTrace

  Write-Host ""
  Write-Host "BASELINE samples saved. Now switch Bonsai to CANDIDATE:"
  Write-Host "  1. Keep 'PTQ1_0 A/B fixed 16K / B16' ON."
  Write-Host "  2. Turn 'Metal TensorOps candidate (next launch)' ON."
  Write-Host "  3. Fully quit Bonsai and relaunch it; start the API and keep the screen awake."
  [void](Read-Host "Press Enter after the candidate API has restarted")
  $candidateReady = $false
  for ($i = 0; $i -lt 120; $i++) {
    $h = Get-ApiJson -Method GET -Path "/health" -TimeoutSec 10
    if ($h.http_status -eq 200) { $candidateReady = $true; break }
    Start-Sleep -Seconds 5
  }
  if (-not $candidateReady) { throw "CANDIDATE API did not become ready within 10 minutes." }
  $candidateSnapshot = Get-Snapshot -Key $key -AuthRequired $authRequired
  $candidateSHA = Assert-ExperimentShape -Snapshot $candidateSnapshot -ExpectedSHA $sourceSHA
  if ((Get-Arm $candidateSnapshot) -ne "CANDIDATE") { throw "Expected CANDIDATE arm after relaunch." }
  if (-not [bool](Get-Field (Get-Field $candidateSnapshot.prefill "ptq1_tensorops_trace") "tensor_api_enabled")) {
    throw "CANDIDATE arm did not enable the Metal Tensor API."
  }
  $candidateModelFile = [string](Get-Field $candidateSnapshot.prefill "model_file_name")
  if ($candidateModelFile -ne $modelFile -or $candidateSnapshot.model_id -ne $modelID) { throw "Model identity changed between arms." }
  $summary.candidate = [ordered]@{ source_git_sha = $candidateSHA; model_id = $candidateSnapshot.model_id; model_file_name = $candidateModelFile; context = 16384; batch = 16; ubatch = 16 }

  Write-Host "Running CANDIDATE warmups and measurements..."
  foreach ($target in $targets) {
    $warm = Invoke-Warmup -Arm "CANDIDATE" -Target $target -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired
    Save-JsonLine -Path $warmupsPath -Value $warm
    if (-not $warm.request_completed -or [int]$warm.prompt_tokens -ne $target -or [int]$warm.completion_tokens -ne 128) {
      throw "CANDIDATE warmup invalid for target $target (prompt=$($warm.prompt_tokens), output=$($warm.completion_tokens), HTTP=$($warm.http_status))."
    }
    $afterWarm = Get-Snapshot -Key $key -AuthRequired $authRequired
    $typeEvidence = Assert-ActualPTQ1Type -Snapshot $afterWarm -Arm "CANDIDATE"
    $trace = $typeEvidence.trace
    if (-not [bool](Get-Field $trace "route_selected") -or
        -not [bool](Get-Field $trace "pipeline_ready") -or
        -not [bool](Get-Field $trace "dispatch_enqueued") -or
        [bool](Get-Field $trace "fallback_observed")) {
      throw "CANDIDATE warmup completed but the PTQ1 custom route/pipeline/dispatch evidence is incomplete."
    }
    if ((Get-Arm $afterWarm) -ne "CANDIDATE") { throw "CANDIDATE arm changed during the run." }
    if ($target -eq $targets[0]) {
      $summary.candidate_execution_verified = $true
      Save-Json -Path (Join-Path $sessionDir "trace-candidate.json") -Value $trace
      $traceSHA = [string](Get-Field (Get-Field $trace "trace_header") "app_source_sha")
      if (-not [string]::IsNullOrWhiteSpace($traceSHA) -and $traceSHA -ne $sourceSHA) { throw "PTQ1 native trace source SHA does not match the app source SHA." }
    }

    for ($rep = 1; $rep -le $Repetitions; $rep++) {
      $sample = Invoke-MeasuredRequest -Arm "CANDIDATE" -Target $target -Repetition $rep -Prompt $prompts[[string]$target] -Model $modelID -Key $key -AuthRequired $authRequired -SourceSHA $candidateSHA -ModelFile $candidateModelFile
      $allSamples.Add($sample)
      Save-JsonLine -Path $samplesPath -Value $sample
      Write-Host ("CANDIDATE {0} tokens, sample {1}/{2}: valid={3}, TTFT={4} ms, prefill={5} ms, decode={6} tok/s" -f $target,$rep,$Repetitions,$sample.valid,$sample.ttft_ms,$sample.prefill_ms,$sample.decode_tokens_per_second)
    }
  }

  $comparisons = @()
  foreach ($target in $targets) { $comparisons += Get-Comparison -Target $target -Samples $allSamples }
  $summary.comparisons = $comparisons
  $allComplete = $true
  $allGates = $true
  foreach ($comparison in $comparisons) {
    if (-not $comparison.sufficient_samples) { $allComplete = $false; $allGates = $false }
    elseif (-not $comparison.overall_gate_pass) { $allGates = $false }
  }
  if (-not $summary.candidate_execution_verified -or -not $allComplete) {
    $summary.status = "BLOCKED_NEEDS_ENGINE_EVIDENCE"
    $exitCode = 2
  } elseif ($allGates) {
    $summary.status = "M5_PERFORMANCE_GAIN_VERIFIED"
    $exitCode = 0
  } else {
    $summary.status = "CANDIDATE_NO_GAIN"
    $exitCode = 1
  }
} catch {
  $summary.status = "BLOCKED_NEEDS_ENGINE_EVIDENCE"
  $summary.error = [string]$_.Exception.Message
  $exitCode = 2
  Write-Host "A/B stopped: $($summary.error)" -ForegroundColor Yellow
} finally {
  $summary.finished_at = (Get-Date).ToString("o")
  $summary.sample_count = $allSamples.Count
  $summary.valid_sample_count = @($allSamples | Where-Object { $_.valid }).Count
  Save-Json -Path $summaryPath -Value $summary
  if ($allSamples.Count -gt 0) {
    $allSamples | Export-Csv -LiteralPath (Join-Path $sessionDir "samples.csv") -NoTypeInformation -Encoding UTF8
  }
  Write-Manifest -Directory $sessionDir
  $zipPath = Join-Path $OutputRoot "BONSAI_PTQ1_METAL_AB_RESULT_$stamp.zip"
  Compress-Archive -Path (Join-Path $sessionDir "*") -DestinationPath $zipPath -Force
  $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath "$zipPath.sha256" -Value "$zipHash  $(Split-Path -Leaf $zipPath)" -Encoding UTF8
  Write-Host ""
  Write-Host "Result: $($summary.status)"
  Write-Host "Raw samples: $samplesPath"
  Write-Host "Summary: $summaryPath"
  Write-Host "Result ZIP: $zipPath"
  Write-Host "SHA-256: $zipHash"
}
exit $exitCode
