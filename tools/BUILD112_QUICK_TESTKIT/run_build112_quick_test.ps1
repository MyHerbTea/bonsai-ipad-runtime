Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

function Get-Field($Object, [string]$Name) {
  if ($null -eq $Object) { return $null }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}
function Save-Json([string]$Name, $Value) {
  $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $outDir $Name) -Encoding UTF8
}
function Set-Stage([string]$Name, [string]$Status, [string]$Detail) {
  $summary.stages[$Name] = [ordered]@{
    status = $Status
    detail = $Detail
    timestamp = (Get-Date).ToString("o")
  }
}
function Get-HttpStatusCode($Record) {
  try {
    $response = $Record.Exception.Response
    if ($null -ne $response -and $null -ne $response.StatusCode) {
      return [int]$response.StatusCode
    }
  } catch {}
  return 0
}
function Get-ExitCodeForStatus([string]$Status) {
  switch ($Status) {
    "PASS" { return 0 }
    "FAIL" { return 1 }
    "INCOMPLETE" { return 2 }
    "BLOCKED" { return 3 }
    default { return 1 }
  }
}
function Resolve-AuthRequired($Health) {
  $value = Get-Field $Health "auth_required"
  if ($null -eq $value -or $value -isnot [bool]) {
    throw "AUTH_MODE_UNDETERMINED"
  }
  return [bool]$value
}
function New-RequestHeaders(
  [bool]$AuthRequired,
  [string]$Key,
  [bool]$AllowMissingKey = $false
) {
  $headers = @{}
  if (-not $AuthRequired) { return $headers }
  if ([string]::IsNullOrWhiteSpace($Key)) {
    if ($AllowMissingKey) { return $headers }
    throw "API_KEY_REQUIRED"
  }
  $headers["X-API-Key"] = $Key
  return $headers
}
function Invoke-ApiJson(
  [string]$Method,
  [string]$Path,
  $Body = $null,
  [string]$Key = $null,
  [bool]$AuthRequired = $false,
  [bool]$AllowMissingKey = $false,
  [int]$TimeoutSec = 45
) {
  $headers = New-RequestHeaders -AuthRequired:$AuthRequired -Key $Key -AllowMissingKey:$AllowMissingKey
  try {
    if ($Method -eq "GET") {
      $json = Invoke-RestMethod -Method Get -Uri ($root + $Path) -Headers $headers -TimeoutSec $TimeoutSec
    } else {
      $wire = $Body | ConvertTo-Json -Depth 40 -Compress
      $json = Invoke-RestMethod -Method Post -Uri ($root + $Path) -Headers $headers -ContentType "application/json" -Body $wire -TimeoutSec $TimeoutSec
    }
    return [pscustomobject]@{ http_status = 200; json = $json; error = $null }
  } catch {
    $code = Get-HttpStatusCode $_
    if ($code -eq 401 -or $code -eq 403) { $safeError = "unauthorized" }
    elseif ($code -gt 0) { $safeError = "HTTP $code" }
    else { $safeError = "connection failed; raw exception omitted to protect request metadata" }
    if (-not [string]::IsNullOrWhiteSpace($Key)) {
      $safeError = $safeError.Replace($Key, "[REDACTED]")
    }
    return [pscustomobject]@{ http_status = $code; json = $null; error = $safeError }
  }
}
function Throw-ApiFailure($Response, [string]$Stage, [string]$FailureClass) {
  if ($Response.http_status -eq 0) {
    throw "QUICK_RESULT|INCOMPLETE|INCOMPLETE_API_NOT_REACHABLE|$Stage could not reach the API endpoint."
  }
  if ($Response.http_status -eq 401 -or $Response.http_status -eq 403) {
    throw "QUICK_RESULT|FAIL|AUTH_FAILED|$Stage was rejected by API authentication."
  }
  throw "QUICK_RESULT|FAIL|$FailureClass|$Stage returned HTTP $($Response.http_status)."
}
function Write-StartupDiagnosticsUnavailable([string]$Reason) {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) {
    Save-Json "startup-diagnostics.json" ([ordered]@{
      retrieval_status = "NOT_RETRIEVABLE_OVER_HTTP"
      reason = $Reason
      api_startup_stage = "UNAVAILABLE"
      api_startup_previous_incomplete = "UNAVAILABLE"
      api_startup_last_success_stage = "UNAVAILABLE"
      api_startup_last_failure_stage = "UNAVAILABLE"
      api_startup_last_failure_error = "UNAVAILABLE"
      api_key_saved = $false
      note = "When the listener is down, reopen Bonsai diagnostics or share the app's native startup evidence separately."
    })
  }
}

if ($args -contains "-SelfTest") {
  if ((Resolve-AuthRequired ([pscustomobject]@{ auth_required = $true })) -ne $true) { throw "SelfTest expected auth_required=true." }
  if ((Resolve-AuthRequired ([pscustomobject]@{ auth_required = $false })) -ne $false) { throw "SelfTest expected auth_required=false." }
  $missingModeRejected = $false
  try { $null = Resolve-AuthRequired ([pscustomobject]@{}) } catch { $missingModeRejected = $true }
  if (-not $missingModeRejected) { throw "SelfTest must reject an unknown auth mode." }
  $disabledHeaders = New-RequestHeaders -AuthRequired:$false -Key "must-not-be-sent"
  if ($disabledHeaders.Count -ne 0) { throw "SelfTest: disabled mode must send no API key header." }
  $enabledHeaders = New-RequestHeaders -AuthRequired:$true -Key "test-key"
  if ($enabledHeaders["X-API-Key"] -ne "test-key") { throw "SelfTest: enabled mode must attach the supplied key." }
  $missingProbeHeaders = New-RequestHeaders -AuthRequired:$true -Key "" -AllowMissingKey:$true
  if ($missingProbeHeaders.Count -ne 0) { throw "SelfTest: missing-key auth probe must not add a header." }
  if ((Get-ExitCodeForStatus "PASS") -ne 0) { throw "SelfTest: PASS exit code must be 0." }
  if ((Get-ExitCodeForStatus "FAIL") -eq 0) { throw "SelfTest: FAIL exit code must be nonzero." }
  if ((Get-ExitCodeForStatus "INCOMPLETE") -eq 0) { throw "SelfTest: INCOMPLETE exit code must be nonzero." }
  if ((Get-ExitCodeForStatus "BLOCKED") -eq 0) { throw "SelfTest: BLOCKED exit code must be nonzero." }
  Write-Host "PASS Quick TestKit auth-mode detection, no-key headers and exit-code self-tests"
  exit 0
}

$testkitSourceCommit = (Get-Content -LiteralPath (Join-Path $scriptRoot "SOURCE_COMMIT.txt") -Raw).Trim()
$expectedAppSHA = (Get-Content -LiteralPath (Join-Path $scriptRoot "EXPECTED_APP_SOURCE_SHA.txt") -Raw).Trim()
$defaultBase = "http://192.168.0.102:8080"
$enteredBase = Read-Host "Bonsai Base URL [$defaultBase]"
if ([string]::IsNullOrWhiteSpace($enteredBase)) { $enteredBase = $defaultBase }
$root = $enteredBase.Trim().TrimEnd("/")
if ($root.EndsWith("/v1")) { $root = $root.Substring(0, $root.Length - 3) }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultsRoot = Join-Path $scriptRoot "RESULTS"
$outDir = Join-Path $resultsRoot ("Build112-PTQ1-Auth-Startup-" + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$apiKey = ""
$effectiveKey = $null
$authRequired = $false
$currentStage = "health"
$deferredFailure = $null
$summary = [ordered]@{
  schema_version = 3
  testkit = "Bonsai Build112 PTQ1_0 Auth-Aware Quick TestKit"
  testkit_version = "2.0"
  testkit_source_commit = $testkitSourceCommit
  expected_app_source_sha = $expectedAppSHA
  started_at = (Get-Date).ToString("o")
  base_url = $root
  api_key_saved = $false
  api_reachable = $false
  app_identity = [ordered]@{ source_git_sha = "unavailable"; candidate_build_id = "unavailable"; build_number = "unavailable" }
  auth = [ordered]@{ mode = "unknown"; auth_required = $null; detection_source = "/health.auth_required"; key_prompted = $false; api_key_header_sent = $false; missing_key_probe = "NOT_RUN"; wrong_key_probe = "NOT_RUN" }
  model_identity = [ordered]@{ model_id = "unavailable"; model_file_name = "unavailable"; model_general_file_type_raw = "unavailable"; quantization_hint = "unavailable" }
  runtime = [ordered]@{}
  status = "INCOMPLETE"
  failure_class = "NOT_RUN"
  failed_stage = "none"
  failure_detail = "Test did not complete."
  stages = [ordered]@{}
}
Save-Json "environment.json" ([ordered]@{
  collected_at = (Get-Date).ToString("o")
  operating_system = [Environment]::OSVersion.VersionString
  powershell_version = $PSVersionTable.PSVersion.ToString()
  powershell_edition = $PSVersionTable.PSEdition
  is_64_bit_os = [Environment]::Is64BitOperatingSystem
  is_64_bit_process = [Environment]::Is64BitProcess
  base_url = $root
  api_key_saved = $false
})
Save-Json "testkit-identity.json" ([ordered]@{
  testkit = $summary.testkit
  version = $summary.testkit_version
  testkit_source_commit = $testkitSourceCommit
  expected_app_source_sha = $expectedAppSHA
  api_key_saved = $false
})

try {
  $currentStage = "health"
  $healthResult = Invoke-ApiJson -Method GET -Path "/health" -AuthRequired:$false
  if ($healthResult.http_status -eq 0) {
    Save-Json "health-error.json" ([ordered]@{ http_status = 0; error = "API not reachable"; base_url = $root })
    throw "QUICK_RESULT|INCOMPLETE|INCOMPLETE_API_NOT_REACHABLE|GET /health could not reach the API endpoint."
  }
  if ($healthResult.http_status -ne 200) {
    Save-Json "health-error.json" ([ordered]@{ http_status = $healthResult.http_status; error = $healthResult.error })
    throw "QUICK_RESULT|FAIL|FAIL_AUTH_MODE_UNDETERMINED|Public GET /health did not return HTTP 200, so the effective auth mode cannot be trusted."
  }
  $health = $healthResult.json
  Save-Json "health.json" $health
  $summary.api_reachable = $true
  $healthDiagnostics = Get-Field $health "diagnostics"
  $startup = [ordered]@{
    retrieval_status = "AVAILABLE"
    source = "GET /health diagnostics"
    api_startup_stage = (Get-Field $healthDiagnostics "api_startup_stage")
    api_startup_previous_incomplete = (Get-Field $healthDiagnostics "api_startup_previous_incomplete")
    api_startup_attempt = (Get-Field $healthDiagnostics "api_startup_attempt")
    api_startup_last_error = (Get-Field $healthDiagnostics "api_startup_last_error")
    api_startup_last_success_stage = (Get-Field $healthDiagnostics "api_startup_last_success_stage")
    api_startup_last_failure_stage = (Get-Field $healthDiagnostics "api_startup_last_failure_stage")
    api_startup_last_failure_error = (Get-Field $healthDiagnostics "api_startup_last_failure_error")
    api_startup_last_failure_time = (Get-Field $healthDiagnostics "api_startup_last_failure_time")
    last_engine_stage = (Get-Field $healthDiagnostics "last_engine_stage")
    context_switch_state = (Get-Field $healthDiagnostics "context_switch_state")
    collected_at = (Get-Date).ToString("o")
  }
  Save-Json "startup-diagnostics.json" $startup
  if ([string](Get-Field $health "status") -ne "ok") {
    throw "QUICK_RESULT|FAIL|FAIL_HEALTH_CHECK|GET /health did not return status=ok."
  }
  try { $authRequired = Resolve-AuthRequired $health }
  catch { throw "QUICK_RESULT|FAIL|FAIL_AUTH_MODE_UNDETERMINED|/health is missing a boolean auth_required field." }
  $summary.auth.auth_required = $authRequired
  $summary.auth.mode = if ($authRequired) { "API_KEY_REQUIRED" } else { "NO_API_KEY_REQUIRED" }
  Save-Json "auth-mode.json" ([ordered]@{
    auth_required = $authRequired
    mode = $summary.auth.mode
    detection_source = "/health.auth_required"
    key_prompted = $false
    api_key_saved = $false
  })
  Set-Stage "health" "PASS" "Public GET /health succeeded and supplied a trusted boolean auth_required field."

  if ($authRequired) {
    $currentStage = "auth_probes"
    $probeBody = [ordered]@{ model = "bonsai-2-27b-local"; messages = @(@{ role = "user"; content = "Authentication probe; request must be rejected before inference." }); max_tokens = 1; temperature = 0; stream = $false }
    $routes = @(
      [pscustomobject]@{ method = "GET"; path = "/v1/models"; body = $null },
      [pscustomobject]@{ method = "GET"; path = "/debug/build"; body = $null },
      [pscustomobject]@{ method = "GET"; path = "/debug/prefill"; body = $null },
      [pscustomobject]@{ method = "POST"; path = "/v1/chat/completions"; body = $probeBody }
    )
    $probeResults = [System.Collections.Generic.List[object]]::new()
    foreach ($route in $routes) {
      $missing = Invoke-ApiJson -Method $route.method -Path $route.path -Body $route.body -AuthRequired:$true -AllowMissingKey:$true -TimeoutSec 20
      $wrongKey = "invalid-" + [guid]::NewGuid().ToString("N")
      $wrong = Invoke-ApiJson -Method $route.method -Path $route.path -Body $route.body -Key $wrongKey -AuthRequired:$true -TimeoutSec 20
      $probeResults.Add([ordered]@{ path = $route.path; method = $route.method; missing_key_status = $missing.http_status; wrong_key_status = $wrong.http_status; expected_status = 401; passed = ($missing.http_status -eq 401 -and $wrong.http_status -eq 401) })
      if ($missing.http_status -ne 401 -or $wrong.http_status -ne 401) {
        Save-Json "auth-route-probes.json" @($probeResults.ToArray())
        throw "QUICK_RESULT|FAIL|FAIL_AUTH_POLICY_MISMATCH|A protected route did not return HTTP 401 for missing and incorrect keys."
      }
    }
    Save-Json "auth-route-probes.json" @($probeResults.ToArray())
    $summary.auth.missing_key_probe = "ALL_PROTECTED_ROUTES_401"
    $summary.auth.wrong_key_probe = "ALL_PROTECTED_ROUTES_401"
    Set-Stage "auth_probes" "PASS" "Missing and incorrect keys returned HTTP 401 on models, build diagnostics, prefill diagnostics and inference."
    $secure = Read-Host "API Key (required because IPA /health reports auth_required=true)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
      throw "QUICK_RESULT|FAIL|FAIL_API_KEY_REQUIRED|Authentication is enabled but no API Key was supplied."
    }
    $effectiveKey = $apiKey
    $summary.auth.key_prompted = $true
    $summary.auth.api_key_header_sent = $true
  } else {
    $effectiveKey = $null
    $summary.auth.key_prompted = $false
    $summary.auth.api_key_header_sent = $false
    Save-Json "auth-route-probes.json" ([ordered]@{
      mode = "NO_API_KEY_REQUIRED"
      api_key_prompted = $false
      api_key_header_sent = $false
      note = "Protected endpoints will be called without Authorization or X-API-Key headers."
    })
    Set-Stage "auth_probes" "PASS" "IPA reports auth_required=false; no key prompt or API key header will be used."
  }

  $currentStage = "build_identity"
  $buildResult = Invoke-ApiJson -Method GET -Path "/debug/build" -Key $effectiveKey -AuthRequired:$authRequired
  if ($buildResult.http_status -ne 200) { Throw-ApiFailure $buildResult "GET /debug/build" "FAIL_BUILD_IDENTITY_UNAVAILABLE" }
  $build = $buildResult.json
  $appSHA = [string](Get-Field $build "source_git_sha")
  if ([string]::IsNullOrWhiteSpace($appSHA) -or $appSHA -eq "unknown") { $appSHA = [string](Get-Field $build "product_git_sha") }
  $buildNo = [string](Get-Field $build "build_number")
  if ([string]::IsNullOrWhiteSpace($buildNo)) { $buildNo = [string](Get-Field $build "build") }
  $candidateBuildID = [string](Get-Field $build "candidate_build_id")
  $summary.app_identity = [ordered]@{
    source_git_sha = $appSHA
    candidate_build_id = $candidateBuildID
    build_number = $buildNo
    workflow_run_id = (Get-Field $build "workflow_run_id")
    matches_expected_app_source_sha = ($appSHA -eq $expectedAppSHA)
    is_build112 = ($buildNo -eq "112")
  }
  Save-Json "app-identity.json" $summary.app_identity
  if ($appSHA -ne $expectedAppSHA -or $buildNo -ne "112") {
    throw "QUICK_RESULT|FAIL|FAIL_BUILD_IDENTITY_MISMATCH|Actual App source SHA or Build ID does not match the TestKit pin."
  }
  Set-Stage "build_identity" "PASS" "App source SHA and Build112 identity match the independent TestKit pin."

  $currentStage = "models"
  $modelsResult = Invoke-ApiJson -Method GET -Path "/v1/models" -Key $effectiveKey -AuthRequired:$authRequired
  if ($modelsResult.http_status -ne 200) { Throw-ApiFailure $modelsResult "GET /v1/models" "FAIL_MODEL_LIST" }
  $models = $modelsResult.json
  $modelRows = @(Get-Field $models "data")
  if ($modelRows.Count -lt 1) { throw "QUICK_RESULT|FAIL|FAIL_MODEL_IDENTITY_MISMATCH|/v1/models returned no usable model." }
  $modelID = [string](Get-Field $modelRows[0] "id")
  $summary.model_identity.model_id = $modelID
  Save-Json "models.json" $models
  if ($modelID -ne "bonsai-2-27b-local") {
    throw "QUICK_RESULT|FAIL|FAIL_MODEL_IDENTITY_MISMATCH|Expected model ID bonsai-2-27b-local."
  }
  Set-Stage "models" "PASS" "OpenAI-compatible model list returned the expected local model ID."

  $currentStage = "prefill_before"
  $prefillResult = Invoke-ApiJson -Method GET -Path "/debug/prefill" -Key $effectiveKey -AuthRequired:$authRequired
  if ($prefillResult.http_status -ne 200) { Throw-ApiFailure $prefillResult "GET /debug/prefill" "FAIL_PREFILL_DIAGNOSTICS" }
  $prefill = $prefillResult.json
  Save-Json "prefill-before.json" $prefill
  $modelFile = [string](Get-Field $prefill "model_file_name")
  $modelTypeRaw = [string](Get-Field $prefill "model_general_file_type_raw")
  $quantHint = [string](Get-Field $prefill "model_quantization_hint")
  $summary.model_identity = [ordered]@{
    model_id = $modelID
    model_file_name = $modelFile
    model_general_file_type_raw = $modelTypeRaw
    quantization_hint = $quantHint
    quantization_note = "Raw GGUF metadata is preserved as raw metadata; filename hints do not prove kernel dispatch."
  }
  if ($modelFile -notmatch "(?i)PTQ1_0") {
    throw "QUICK_RESULT|FAIL|FAIL_MODEL_IDENTITY_MISMATCH|The loaded model filename does not identify the required PTQ1_0 mainline model."
  }
  $tensorEnabledValue = Get-Field $prefill "m5_nax_pq2_tensor_api_enabled"
  $summary.runtime = [ordered]@{
    api_context = (Get-Field $prefill "api_context")
    api_batch = (Get-Field $prefill "api_batch")
    api_ubatch = (Get-Field $prefill "api_ubatch")
    native_context_created = (Get-Field $prefill "native_context_created")
    native_context_context = (Get-Field $prefill "native_context_context")
    native_context_batch = (Get-Field $prefill "native_context_batch")
    native_context_ubatch = (Get-Field $prefill "native_context_ubatch")
    native_context_source = (Get-Field $prefill "native_context_source")
    model_general_file_type_raw = $modelTypeRaw
    model_quantization_hint = $quantHint
    nax_tensor_api_enabled = $tensorEnabledValue
    nax_prefill_effective = (Get-Field $prefill "m5_nax_pq2_prefill_effective")
    nax_prefill_state = (Get-Field $prefill "m5_nax_pq2_prefill_state")
    nax_route_selected = (Get-Field (Get-Field $prefill "m5_nax_pq2_trace") "route_selected")
    nax_pipeline_ready = (Get-Field (Get-Field $prefill "m5_nax_pq2_trace") "pipeline_ready")
    nax_dispatch_enqueued = (Get-Field (Get-Field $prefill "m5_nax_pq2_trace") "dispatch_enqueued")
  }
  Save-Json "runtime-diagnostics.json" $summary.runtime
  if ($null -eq $tensorEnabledValue) {
    $deferredFailure = "FAIL_NAX_ISOLATION_EVIDENCE_MISSING"
  } elseif ([bool]$tensorEnabledValue) {
    $deferredFailure = "FAIL_NAX_ISOLATION"
  }
  if ([string](Get-Field $startup "api_startup_stage") -ne "READY") {
    if ($null -eq $deferredFailure) { $deferredFailure = "FAIL_STARTUP_LIFECYCLE_NOT_READY" }
  }
  Set-Stage "prefill_before" "PASS" "Captured model identity, API/native context shape, backend and persistent startup diagnostics."

  $currentStage = "smoke_inference"
  $smokePrompt = "Reply with exactly BONSAI_PTQ1_API_SMOKE_OK and no other text."
  $requestBody = [ordered]@{
    model = $modelID
    messages = @(@{ role = "user"; content = $smokePrompt })
    max_tokens = 16
    temperature = 0
    stream = $false
  }
  Save-Json "smoke-request.json" ([ordered]@{
    request_body = $requestBody
    auth_required = $authRequired
    api_key_saved = $false
    request_headers_saved = $false
  })
  $smokeResult = Invoke-ApiJson -Method POST -Path "/v1/chat/completions" -Body $requestBody -Key $effectiveKey -AuthRequired:$authRequired -TimeoutSec 600
  if ($smokeResult.http_status -eq 200) {
    Save-Json "smoke-response.json" $smokeResult.json
  } else {
    Save-Json "smoke-error.json" ([ordered]@{ http_status = $smokeResult.http_status; error = $smokeResult.error; api_key_saved = $false })
  }

  $currentStage = "prefill_after"
  $afterResult = Invoke-ApiJson -Method GET -Path "/debug/prefill" -Key $effectiveKey -AuthRequired:$authRequired
  if ($afterResult.http_status -eq 200) {
    Save-Json "prefill-after.json" $afterResult.json
    Set-Stage "prefill_after" "PASS" "Post-inference prefill/runtime snapshot collected."
  } else {
    Save-Json "prefill-after-error.json" ([ordered]@{ http_status = $afterResult.http_status; error = $afterResult.error })
    Set-Stage "prefill_after" "INCOMPLETE" "Post-inference prefill snapshot could not be collected."
    if ($null -eq $deferredFailure) { $deferredFailure = "INCOMPLETE_DIAGNOSTICS_AFTER_REQUEST" }
  }
  $healthAfterResult = Invoke-ApiJson -Method GET -Path "/health" -AuthRequired:$false
  if ($healthAfterResult.http_status -eq 200) {
    Save-Json "health-after.json" $healthAfterResult.json
  } else {
    Save-Json "health-after-error.json" ([ordered]@{ http_status = $healthAfterResult.http_status; error = $healthAfterResult.error })
    if ($null -eq $deferredFailure) { $deferredFailure = "INCOMPLETE_HEALTH_AFTER_REQUEST" }
  }

  if ($smokeResult.http_status -ne 200) { Throw-ApiFailure $smokeResult "POST /v1/chat/completions" "FAIL_INFERENCE" }
  $choices = @(Get-Field $smokeResult.json "choices")
  $answer = ""
  if ($choices.Count -gt 0) { $answer = [string](Get-Field (Get-Field $choices[0] "message") "content") }
  $usage = Get-Field $smokeResult.json "usage"
  $promptTokens = [int](Get-Field $usage "prompt_tokens")
  $completionTokens = [int](Get-Field $usage "completion_tokens")
  $sentinelFound = $answer.Contains("BONSAI_PTQ1_API_SMOKE_OK")
  $summary.smoke_inference = [ordered]@{
    http_status = $smokeResult.http_status
    completed = $true
    sentinel_found = $sentinelFound
    prompt_tokens = $promptTokens
    completion_tokens = $completionTokens
    answer = $answer
    api_key_saved = $false
  }
  Save-Json "smoke-result.json" $summary.smoke_inference
  if (-not $sentinelFound -or $promptTokens -le 0 -or $completionTokens -le 0) {
    throw "QUICK_RESULT|FAIL|FAIL_INFERENCE|Smoke request completed without the expected marker or valid usage counts."
  }
  Set-Stage "smoke_inference" "PASS" "PTQ1_0 completed a real non-streaming OpenAI-compatible inference request."

  if ($null -ne $deferredFailure) {
    if ($deferredFailure -like "INCOMPLETE_*") {
      throw "QUICK_RESULT|INCOMPLETE|$deferredFailure|Smoke inference completed but a required follow-up diagnostic was unavailable."
    }
    throw "QUICK_RESULT|FAIL|$deferredFailure|PTQ1_0 must keep the NAX Tensor experiment isolated and startup must reach READY."
  }
  $summary.status = "PASS"
  $summary.failure_class = "PASS_PTQ1_AUTH_AND_STARTUP_SMOKE"
  $summary.failed_stage = "none"
  $summary.failure_detail = "Auth behavior, Build112 identity, PTQ1_0 model identity, NAX isolation and real smoke inference passed."
  Set-Stage "final" "PASS" $summary.failure_detail
} catch {
  $message = $_.Exception.Message
  if ($message.StartsWith("QUICK_RESULT|")) {
    $parts = $message -split "\|", 4
    if ($parts.Count -eq 4) {
      $summary.status = $parts[1]
      $summary.failure_class = $parts[2]
      $summary.failure_detail = $parts[3]
    } else {
      $summary.status = "FAIL"
      $summary.failure_class = "UNCLASSIFIED_FAILURE"
      $summary.failure_detail = "TestKit returned an invalid result record."
    }
  } elseif ($message -eq "AUTH_MODE_UNDETERMINED") {
    $summary.status = "FAIL"
    $summary.failure_class = "FAIL_AUTH_MODE_UNDETERMINED"
    $summary.failure_detail = "Could not establish the actual auth mode from /health.auth_required."
  } elseif ($message -eq "API_KEY_REQUIRED") {
    $summary.status = "FAIL"
    $summary.failure_class = "FAIL_API_KEY_REQUIRED"
    $summary.failure_detail = "Authentication is enabled but no API Key was supplied."
  } else {
    $summary.status = "FAIL"
    $summary.failure_class = "UNCLASSIFIED_FAILURE"
    $summary.failure_detail = "An unexpected test stage failed; raw exception text is omitted."
  }
  $summary.failed_stage = $currentStage
  Set-Stage $currentStage $summary.status $summary.failure_detail
  if ($currentStage -eq "health") { Write-StartupDiagnosticsUnavailable $summary.failure_detail }
} finally {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) {
    Write-StartupDiagnosticsUnavailable "API startup diagnostics were not available over HTTP."
  }
  $summary.finished_at = (Get-Date).ToString("o")
  $summary.api_key_saved = $false
  Save-Json "summary.json" $summary
  $readme = @'
Bonsai Build112 PTQ1_0 Auth-Aware Quick TestKit 2.0
- Reads the real IPA auth_required boolean from unauthenticated GET /health.
- Prompts for an API Key only when auth_required=true; disabled mode sends no Authorization or X-API-Key header.
- When auth is enabled, missing/wrong keys must receive HTTP 401 on models, build diagnostics, prefill diagnostics and inference.
- Verifies independent App source SHA and Build112 identity, PTQ1_0 model filename, runtime shape, persistent startup evidence, NAX Tensor isolation, and real smoke inference.
- Result ZIP contains endpoint status, auth mode/probes, model and runtime identity, startup diagnostics, smoke request/response, per-file SHA-256 manifest and summary.
- API Key values and request headers are never written to result files.
- Exit codes: PASS=0, FAIL=1, INCOMPLETE=2, BLOCKED=3.
- PASS is a software/API smoke result, not M5 crash-free certification or a performance claim.
'@
  Set-Content -LiteralPath (Join-Path $outDir "README.txt") -Value $readme -Encoding UTF8
  $hashes = [ordered]@{}
  Get-ChildItem -LiteralPath $outDir -File | Where-Object { $_.Name -ne "manifest.json" } | Sort-Object Name | ForEach-Object {
    $hashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  Save-Json "manifest.json" ([ordered]@{
    schema_version = 3
    status = $summary.status
    failure_class = $summary.failure_class
    testkit_version = "2.0"
    testkit_source_commit = $testkitSourceCommit
    expected_app_source_sha = $expectedAppSHA
    app_source_git_sha = $summary.app_identity.source_git_sha
    api_key_saved = $false
    files_sha256 = $hashes
  })
  $zipPath = Join-Path $resultsRoot ("Bonsai-Build112-PTQ1-Auth-Startup-" + $stamp + ".zip")
  Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
  $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath ($zipPath + ".sha256") -Value ($zipHash + "  " + [IO.Path]::GetFileName($zipPath)) -Encoding ASCII
  Write-Host ""
  Write-Host ("FINAL: {0} / {1}" -f $summary.status, $summary.failure_class)
  Write-Host ("Evidence ZIP: " + $zipPath)
  Write-Host ("SHA-256: " + $zipHash)
  Remove-Variable apiKey -ErrorAction SilentlyContinue
}
$exitCode = Get-ExitCodeForStatus ([string]$summary.status)
Write-Host ("ExitCode: " + $exitCode)
exit $exitCode
