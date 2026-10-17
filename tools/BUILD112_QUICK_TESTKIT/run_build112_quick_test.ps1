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
function Test-ShapePreconditions($Snapshot) {
  $failures = [System.Collections.Generic.List[string]]::new()
  if (-not [bool](Get-Field $Snapshot "metal_tensor_prefill_requested")) { $failures.Add("candidate_launch_arm_not_requested") }
  if (-not [bool](Get-Field $Snapshot "m5_nax_pq2_tensor_api_enabled")) { $failures.Add("tensor_api_not_enabled") }
  $apiContext = [int](Get-Field $Snapshot "api_context")
  $apiBatch = [int](Get-Field $Snapshot "api_batch")
  $apiUBatch = [int](Get-Field $Snapshot "api_ubatch")
  if ($apiContext -ne 32768) { $failures.Add("api_context_not_32768") }
  if ($apiBatch -lt 16) { $failures.Add("api_batch_below_16") }
  if ($apiUBatch -lt 16 -or ($apiUBatch % 16) -ne 0) { $failures.Add("api_ubatch_below_16_or_unaligned") }
  if (-not [bool](Get-Field $Snapshot "native_context_created")) { $failures.Add("native_context_creation_not_confirmed") }
  if ([int](Get-Field $Snapshot "native_context_context") -ne 32768) { $failures.Add("native_context_not_32768") }
  $nativeBatch = [int](Get-Field $Snapshot "native_context_batch")
  $nativeUBatch = [int](Get-Field $Snapshot "native_context_ubatch")
  if ($nativeBatch -lt 16) { $failures.Add("native_context_batch_below_16") }
  if ($nativeUBatch -lt 16 -or ($nativeUBatch % 16) -ne 0) { $failures.Add("native_context_ubatch_below_16_or_unaligned") }
  if ($nativeBatch -lt $nativeUBatch) { $failures.Add("native_context_batch_below_ubatch") }
  $modelFile = [string](Get-Field $Snapshot "model_file_name")
  $quantHint = [string](Get-Field $Snapshot "model_quantization_hint")
  if ($modelFile -notmatch "(?i)PQ2_0" -or $quantHint -ne "PQ2_0_FILENAME_HINT") { $failures.Add("PQ2_0_model_identity_not_confirmed") }
  return [pscustomobject]@{
    eligible = ($failures.Count -eq 0); failures = @($failures.ToArray())
    api_context = $apiContext; api_batch = $apiBatch; api_ubatch = $apiUBatch
    native_context_created = [bool](Get-Field $Snapshot "native_context_created")
    native_context_context = [int](Get-Field $Snapshot "native_context_context")
    native_context_batch = $nativeBatch; native_context_ubatch = $nativeUBatch
    model_file_name = $modelFile; model_description = [string](Get-Field $Snapshot "model_description")
    model_general_file_type_raw = [string](Get-Field $Snapshot "model_general_file_type_raw")
    model_quantization_hint = $quantHint
  }
}
function Test-TraceHasMarkers($Trace) {
  if ($null -eq $Trace) { return $false }
  if ([bool](Get-Field $Trace "route_selected")) { return $true }
  if ([bool](Get-Field $Trace "pipeline_observed")) { return $true }
  if ([bool](Get-Field $Trace "pipeline_ready")) { return $true }
  if ([bool](Get-Field $Trace "dispatch_enqueued")) { return $true }
  return (@(Get-Field $Trace "markers").Count -gt 0)
}
function Get-NaxFinalClassification(
  [bool]$CandidateRequested, [bool]$TensorEnabled, [bool]$ShapeEligible,
  [bool]$TraceBeforeClean, [bool]$InferenceSucceeded, [bool]$SentinelFound,
  [bool]$UsageValid, [bool]$ObservationMatched, [bool]$RouteSelected,
  [bool]$PipelineReady, [bool]$DispatchEnqueued
) {
  if (-not $CandidateRequested -or -not $TensorEnabled) { return "FAIL_TENSOR_API_NOT_ENABLED" }
  if (-not $ShapeEligible) { return "BLOCKED_SHAPE_PRECONDITION" }
  if (-not $TraceBeforeClean) { return "FAIL_STALE_TRACE_EVIDENCE" }
  if (-not $InferenceSucceeded -or -not $SentinelFound) { return "FAIL_INFERENCE" }
  if (-not $UsageValid) { return "FAIL_PREFILL_TOKEN_COUNT_OUT_OF_RANGE" }
  if (-not $ObservationMatched) { return "FAIL_REQUEST_OBSERVATION_MISMATCH" }
  if (-not $RouteSelected) { return "FAIL_ROUTE_NOT_SELECTED" }
  if (-not $PipelineReady) { return "FAIL_PIPELINE_NOT_READY" }
  if (-not $DispatchEnqueued) { return "FAIL_DISPATCH_NOT_ENQUEUED" }
  return "PASS_CANDIDATE_ROUTE_AND_INFERENCE"
}

if ($args -contains "-SelfTest") {
  $good = [pscustomobject]@{
    metal_tensor_prefill_requested = $true; m5_nax_pq2_tensor_api_enabled = $true
    api_context = 32768; api_batch = 16; api_ubatch = 16
    native_context_created = $true; native_context_context = 32768
    native_context_batch = 16; native_context_ubatch = 16
    model_file_name = "Ternary-Bonsai-2-27B-PQ2_0.gguf"
    model_description = "Qwen family model"; model_quantization_hint = "PQ2_0_FILENAME_HINT"
  }
  $shapeGood = Test-ShapePreconditions $good
  if (-not $shapeGood.eligible) { throw ("SelfTest expected B16 shape to pass: " + ($shapeGood.failures -join ",")) }
  $badUbatch = $good | Select-Object *
  $badUbatch.api_ubatch = 4
  $badUbatch.native_context_ubatch = 4
  $shapeBad = Test-ShapePreconditions $badUbatch
  if ($shapeBad.eligible -or -not ($shapeBad.failures -contains "native_context_ubatch_below_16_or_unaligned")) { throw "SelfTest must block native ubatch=4." }
  if ((Get-NaxFinalClassification $true $true $false $true $true $true $true $true $true $true $true) -ne "BLOCKED_SHAPE_PRECONDITION") { throw "SelfTest shape classification failed." }
  if ((Get-NaxFinalClassification $true $false $true $true $true $true $true $true $true $true $true) -ne "FAIL_TENSOR_API_NOT_ENABLED") { throw "SelfTest Tensor classification failed." }
  if ((Get-NaxFinalClassification $true $true $true $true $true $true $true $true $false $false $false) -ne "FAIL_ROUTE_NOT_SELECTED") { throw "SelfTest route classification failed." }
  if ((Get-NaxFinalClassification $true $true $true $true $true $true $true $true $true $false $false) -ne "FAIL_PIPELINE_NOT_READY") { throw "SelfTest Pipeline classification failed." }
  if ((Get-NaxFinalClassification $true $true $true $true $false $false $false $false $false $false $false) -ne "FAIL_INFERENCE") { throw "SelfTest inference classification failed." }
  if ((Get-NaxFinalClassification $true $true $true $true $true $true $true $true $true $true $true) -ne "PASS_CANDIDATE_ROUTE_AND_INFERENCE") { throw "SelfTest PASS classification failed." }
  Write-Host "PASS Quick TestKit 1.2 shape gate and result-classification self-tests"
  exit 0
}

$testkitSourceCommit = (Get-Content -LiteralPath (Join-Path $scriptRoot "SOURCE_COMMIT.txt") -Raw).Trim()
$expectedAppSHA = (Get-Content -LiteralPath (Join-Path $scriptRoot "EXPECTED_APP_SOURCE_SHA.txt") -Raw).Trim()
$defaultBase = "http://192.168.1.85:8080"
$enteredBase = Read-Host "Bonsai Base URL [$defaultBase]"
if ([string]::IsNullOrWhiteSpace($enteredBase)) { $enteredBase = $defaultBase }
$root = $enteredBase.Trim().TrimEnd("/")
if ($root.EndsWith("/v1")) { $root = $root.Substring(0, $root.Length - 3) }
$secure = Read-Host "API Key (needed for authenticated build/models/prefill checks)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultsRoot = Join-Path $scriptRoot "RESULTS"
$outDir = Join-Path $resultsRoot ("Build112-NAX-LongPrefill-" + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$summary = [ordered]@{
  schema_version = 2; testkit = "Bonsai Build112 M5 NAX-PQ2 Long-Prefill TestKit"; testkit_version = "1.2"
  testkit_source_commit = $testkitSourceCommit; expected_app_source_sha = $expectedAppSHA
  expected_candidate_build_id = "rc1.26-build112-m5-nax-pq2-01"; expected_model_id = "bonsai-2-27b-local"
  started_at = (Get-Date).ToString("o"); base_url = $root; api_key_saved = $false
  app_identity = [ordered]@{ source_git_sha = "unavailable" }; status = "INCOMPLETE"
  failure_class = "NOT_RUN"; failed_stage = "none"; stages = [ordered]@{}
}
function Save-Json([string]$Name, $Value) { $Value | ConvertTo-Json -Depth 35 | Set-Content -LiteralPath (Join-Path $outDir $Name) -Encoding UTF8 }
function Set-Stage([string]$Name, [string]$Status, [string]$Detail) { $summary.stages[$Name] = [ordered]@{ status = $Status; detail = $Detail; timestamp = (Get-Date).ToString("o") } }
function Get-HttpStatusCode($Record) {
  try { $response = $Record.Exception.Response; if ($null -ne $response -and $null -ne $response.StatusCode) { return [int]$response.StatusCode } } catch {}
  return 0
}
function Invoke-ApiJson([string]$Method, [string]$Path, $Body = $null, [bool]$UseKey = $true, [hashtable]$ExtraHeaders = @{}) {
  $headers = @{}
  if ($UseKey -and -not [string]::IsNullOrWhiteSpace($apiKey)) { $headers["X-API-Key"] = $apiKey }
  if ($null -ne $ExtraHeaders) { foreach ($key in $ExtraHeaders.Keys) { $headers[$key] = $ExtraHeaders[$key] } }
  try {
    if ($Method -eq "GET") { return Invoke-RestMethod -Method Get -Uri ($root + $Path) -Headers $headers -TimeoutSec 45 }
    $wire = $Body | ConvertTo-Json -Depth 35 -Compress
    return Invoke-RestMethod -Method Post -Uri ($root + $Path) -Headers $headers -ContentType "application/json" -Body $wire -TimeoutSec 600
  } catch {
    $code = Get-HttpStatusCode $_
    if ($code -eq 401 -or $code -eq 403) { $kind = "AUTH_FAILED" }
    elseif ($code -eq 400 -or $code -eq 422) { $kind = "REQUEST_CONFIGURATION_ERROR" }
    elseif ($currentStage -eq "health" -and $code -ge 500) { $kind = "HEALTH_CHECK_FAILED" }
    elseif ($currentStage -eq "models" -and $code -ge 500) { $kind = "MODEL_LIST_FAILED" }
    elseif ($currentStage -eq "long_prefill" -and $code -ge 500) { $kind = "INFERENCE_FAILED" }
    elseif ($code -ge 500) { $kind = "API_SERVER_ERROR" }
    elseif ($code -eq 0) { $kind = "API_NOT_REACHABLE" } else { $kind = "HTTP_ERROR" }
    throw ("QUICK_API_ERROR|{0}|{1}|{2}|{3}" -f $kind, $code, $Path, $_.Exception.Message)
  }
}
function Write-StartupDiagnosticsUnavailable([string]$Reason) {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) {
    Save-Json "startup-diagnostics.json" ([ordered]@{
      retrieval_status = "NOT_RETRIEVABLE_OVER_HTTP"; reason = $Reason
      api_startup_stage = "UNAVAILABLE"; api_startup_previous_incomplete = "UNAVAILABLE"
      api_startup_attempt = $null; api_startup_last_error = "UNAVAILABLE"
      note = "When the listener is down, refresh Advanced & Diagnostics in Bonsai; startup stage/error remain in the app."
    })
  }
}
Save-Json "environment.json" ([ordered]@{
  collected_at = (Get-Date).ToString("o"); operating_system = [Environment]::OSVersion.VersionString
  powershell_version = $PSVersionTable.PSVersion.ToString(); powershell_edition = $PSVersionTable.PSEdition
  is_64_bit_os = [Environment]::Is64BitOperatingSystem; is_64_bit_process = [Environment]::Is64BitProcess; base_url = $root
})
Save-Json "testkit-identity.json" ([ordered]@{
  testkit = $summary.testkit; version = $summary.testkit_version
  testkit_source_commit = $testkitSourceCommit; expected_app_source_sha = $expectedAppSHA
  expected_candidate_build_id = $summary.expected_candidate_build_id; api_key_saved = $false
})

$currentStage = "health"
try {
  $health = Invoke-ApiJson -Method GET -Path "/health" -UseKey:$false
  Save-Json "health.json" $health
  $d = Get-Field $health "diagnostics"
  $startup = [ordered]@{
    retrieval_status = "AVAILABLE"; source = "GET /health diagnostics"
    api_startup_stage = Get-Field $d "api_startup_stage"
    api_startup_previous_incomplete = Get-Field $d "api_startup_previous_incomplete"
    api_startup_attempt = Get-Field $d "api_startup_attempt"
    api_startup_last_error = Get-Field $d "api_startup_last_error"
    last_engine_stage = Get-Field $d "last_engine_stage"; context_switch_state = Get-Field $d "context_switch_state"
    collected_at = (Get-Date).ToString("o")
  }
  Save-Json "startup-diagnostics.json" $startup
  $summary.api_reachable = $true; $summary.api_startup_stage = [string]$startup.api_startup_stage
  if ([string](Get-Field $health "status") -ne "ok") { Set-Stage "health" "FAIL" "GET /health did not return status=ok."; throw "QUICK_STAGE_FAILURE|HEALTH_CHECK_FAILED|Unexpected /health status." }
  Set-Stage "health" "PASS" "GET /health returned status=ok."

  $currentStage = "build_identity"
  $build = Invoke-ApiJson -Method GET -Path "/debug/build"
  Save-Json "build.json" $build
  $appSHA = [string](Get-Field $build "source_git_sha")
  $appID = [string](Get-Field $build "candidate_build_id")
  $buildNo = [string](Get-Field $build "build_number")
  $identityOK = ($buildNo -eq "112") -and ($appID -eq "rc1.26-build112-m5-nax-pq2-01") -and ($appSHA -eq $expectedAppSHA)
  $summary.app_identity = [ordered]@{
    source_git_sha = $appSHA; candidate_build_id = $appID; build_number = $buildNo
    workflow_run_id = [string](Get-Field $build "workflow_run_id"); prism_upstream_sha = [string](Get-Field $build "prism_upstream_sha")
    matches_expected_app_source_sha = ($appSHA -eq $expectedAppSHA)
    testkit_source_commit = $testkitSourceCommit; app_sha_is_not_inferred_from_testkit_sha = $true
  }
  if (-not $identityOK) { Set-Stage "build_identity" "FAIL" "App source SHA/build ID does not match EXPECTED_APP_SOURCE_SHA.txt."; throw "QUICK_STAGE_FAILURE|FAIL_BUILD_IDENTITY_MISMATCH|App identity must match the separately pinned App SHA and Build112 candidate." }
  Set-Stage "build_identity" "PASS" "Build112 identity matches the pinned App SHA; TestKit source identity is separate."

  $currentStage = "models"
  $models = Invoke-ApiJson -Method GET -Path "/v1/models"
  Save-Json "models.json" $models
  $modelRows = @(Get-Field $models "data")
  if ($modelRows.Count -lt 1) { Set-Stage "models" "FAIL" "No model row returned."; throw "QUICK_STAGE_FAILURE|FAIL_MODEL_IDENTITY_MISMATCH|/v1/models returned no usable model." }
  $modelID = [string](Get-Field $modelRows[0] "id")
  if ($modelID -ne "bonsai-2-27b-local") { Set-Stage "models" "FAIL" ("Unexpected model ID: " + $modelID); throw "QUICK_STAGE_FAILURE|FAIL_MODEL_IDENTITY_MISMATCH|Expected bonsai-2-27b-local." }
  Set-Stage "models" "PASS" ("Target model ID: " + $modelID)

  $currentStage = "prefill_before"
  $before = Invoke-ApiJson -Method GET -Path "/debug/prefill"
  Save-Json "prefill-before.json" $before
  Set-Stage "prefill_before" "PASS" "Captured API, native-context, model, governor and NAX evidence."
  $requested = [bool](Get-Field $before "metal_tensor_prefill_requested")
  $tensorEnabled = [bool](Get-Field $before "m5_nax_pq2_tensor_api_enabled")
  if (-not $requested -or -not $tensorEnabled) { Set-Stage "candidate_tensor_api" "FAIL" "CANDIDATE arm and backend Tensor API evidence must both be true."; throw "QUICK_STAGE_FAILURE|FAIL_TENSOR_API_NOT_ENABLED|Candidate was not active before backend initialization or backend Tensor evidence is false." }
  Set-Stage "candidate_tensor_api" "PASS" "CANDIDATE arm is active and backend log evidence confirms Tensor API enabled."
  $modelFile = [string](Get-Field $before "model_file_name")
  $quantHint = [string](Get-Field $before "model_quantization_hint")
  if ($modelFile -notmatch "(?i)PQ2_0" -or $quantHint -ne "PQ2_0_FILENAME_HINT") { Set-Stage "model_quantization" "FAIL" "Loaded model basename does not confirm PQ2_0; runtime route marker remains authoritative for tensor type."; throw "QUICK_STAGE_FAILURE|FAIL_MODEL_IDENTITY_MISMATCH|Expected loaded model basename to identify PQ2_0." }
  Set-Stage "model_quantization" "PASS" "Loaded model basename identifies PQ2_0; runtime route marker must prove actual kernel selection."
  $shape = Test-ShapePreconditions $before
  Save-Json "shape-preconditions.json" $shape
  $summary.shape_preconditions = $shape
  $summary.model_identity = [ordered]@{
    model_id = $modelID
    model_file_name = [string](Get-Field $before "model_file_name")
    model_description = [string](Get-Field $before "model_description")
    model_general_file_type_raw = [string](Get-Field $before "model_general_file_type_raw")
    model_quantization_filename_hint = [string](Get-Field $before "model_quantization_hint")
    quantization_note = "general.file_type is preserved as raw GGUF metadata; PQ2_0 kernel type is confirmed only by the runtime route marker."
  }
  if (-not $shape.eligible) { $currentStage = "shape_precondition"; Set-Stage "shape_precondition" "BLOCKED" ("Runtime shape is not eligible: " + ($shape.failures -join ", ")); throw ("QUICK_STAGE_FAILURE|BLOCKED_SHAPE_PRECONDITION|" + ($shape.failures -join ", ")) }
  Set-Stage "shape_precondition" "PASS" "API and successful native context satisfy the 32K, aligned 16-row-or-larger batch and PQ2_0 hint gates."
  $beforeTrace = Get-Field $before "m5_nax_pq2_trace"
  if (Test-TraceHasMarkers $beforeTrace) { $summary.trace_before_request_clean = $false; Set-Stage "trace_isolation" "FAIL" "Trace already contains markers before this request."; throw "QUICK_STAGE_FAILURE|FAIL_STALE_TRACE_EVIDENCE|Fully restart Bonsai and rerun to isolate the first eligible dispatch." }
  $summary.trace_before_request_clean = $true
  Set-Stage "trace_isolation" "PASS" "No NAX route/pipeline/dispatch marker existed before the test request."

  $records = [System.Collections.Generic.List[string]]::new()
  for ($i = 1; $i -le 32; $i++) {
    $n = $i.ToString("D3")
    $records.Add("Record $($n): keep seed 17; ordered values are 2, 3, 5, 7, 11, 13, 17, 19. Preserve the order and retain this record.")
  }
  $nl = [Environment]::NewLine
  $prompt = "Read every numbered record before answering. Do not summarize or omit records. After processing all records, reply with exactly BONSAI_NAX_PREFILL_OK and no other text." + $nl + $nl + ($records -join $nl)
  $runID = [guid]::NewGuid().ToString("N")
  $requestID = "nax-" + [guid]::NewGuid().ToString("N")
  $requestBody = [ordered]@{
    model = $modelID; messages = @(@{ role = "user"; content = $prompt })
    max_tokens = 16; temperature = 0; stream = $false
  }
  Save-Json "long-prefill-request.json" ([ordered]@{
    run_id = $runID; request_id = $requestID; test_case = "m5-nax-pq2-long-prefill-v1"
    requested_input_token_range = "512-1024; authoritative length is response usage.prompt_tokens"
    request_body = $requestBody; api_key_saved = $false
  })

  $currentStage = "long_prefill"; $response = $null; $longError = $null
  $requestStartedAt = (Get-Date).ToString("o")
  try {
    $extraHeaders = @{
      "X-Bonsai-Run-Id" = $runID; "X-Bonsai-Request-Id" = $requestID
      "X-Bonsai-Test-Case" = "m5-nax-pq2-long-prefill-v1"
    }
    $response = Invoke-ApiJson -Method POST -Path "/v1/chat/completions" -Body $requestBody -ExtraHeaders $extraHeaders
    Save-Json "long-prefill-response.json" $response
  } catch {
    $longError = $_.Exception.Message
    Save-Json "long-prefill-error.json" ([ordered]@{ request_id = $requestID; started_at = $requestStartedAt; error = $longError; api_key_saved = $false })
  }

  $currentStage = "prefill_after"; $after = $null; $afterError = $null
  try {
    $after = Invoke-ApiJson -Method GET -Path "/debug/prefill"
    Save-Json "prefill-after.json" $after
    Set-Stage "prefill_after" "PASS" "Post-request /debug/prefill snapshot collected."
  } catch {
    $afterError = $_.Exception.Message
    Save-Json "prefill-after-error.json" ([ordered]@{ error = $afterError; request_id = $requestID })
    Set-Stage "prefill_after" "FAIL" ("Could not collect post-request evidence: " + $afterError)
  }

  $inferenceSucceeded = ($null -ne $response) -and ($null -eq $longError)
  $answer = ""; $promptTokens = 0; $completionTokens = 0; $sentinelFound = $false
  if ($inferenceSucceeded) {
    $choices = @(Get-Field $response "choices")
    if ($choices.Count -gt 0) { $answer = [string](Get-Field (Get-Field $choices[0] "message") "content") }
    $usage = Get-Field $response "usage"
    $promptTokens = [int](Get-Field $usage "prompt_tokens")
    $completionTokens = [int](Get-Field $usage "completion_tokens")
    $sentinelFound = $answer.Contains("BONSAI_NAX_PREFILL_OK")
    $usageValid = ($promptTokens -ge 512) -and ($promptTokens -le 1024) -and ($completionTokens -gt 0)
  } else { $usageValid = $false }

  $route = $false; $pipelineObserved = $false; $pipeline = $false; $dispatch = $false
  $trace = $null; $observationMatched = $false
  $sequenceBefore = 0; $sequenceAfter = 0; $observedPromptTokens = 0
  if ($null -ne $after) {
    $trace = Get-Field $after "m5_nax_pq2_trace"
    $route = [bool](Get-Field $trace "route_selected")
    $pipelineObserved = [bool](Get-Field $trace "pipeline_observed")
    $pipeline = [bool](Get-Field $trace "pipeline_ready")
    $dispatch = [bool](Get-Field $trace "dispatch_enqueued")
    $beforeObservation = Get-Field $before "last"; $afterObservation = Get-Field $after "last"
    $sequenceBefore = [int](Get-Field $beforeObservation "sequence")
    $sequenceAfter = [int](Get-Field $afterObservation "sequence")
    $observedPromptTokens = [int](Get-Field $afterObservation "prompt_tokens")
    $observationMatched = $inferenceSucceeded -and ($sequenceAfter -gt $sequenceBefore) -and ($observedPromptTokens -eq $promptTokens)
  }
  $classification = Get-NaxFinalClassification -CandidateRequested $requested -TensorEnabled $tensorEnabled -ShapeEligible ([bool]$shape.eligible) -TraceBeforeClean (-not (Test-TraceHasMarkers $beforeTrace)) -InferenceSucceeded $inferenceSucceeded -SentinelFound $sentinelFound -UsageValid $usageValid -ObservationMatched $observationMatched -RouteSelected $route -PipelineReady $pipeline -DispatchEnqueued $dispatch
  if ($null -ne $afterError -and $classification -eq "PASS_CANDIDATE_ROUTE_AND_INFERENCE") { $classification = "FAIL_DIAGNOSTICS_INCOMPLETE" }

  Save-Json "nax-verification.json" ([ordered]@{
    schema = "bonsai-build112-m5-nax-long-prefill-verification-v1"; classification = $classification
    app_source_sha = $appSHA; testkit_source_commit = $testkitSourceCommit; expected_app_source_sha = $expectedAppSHA
    request_id = $requestID; run_id = $runID; test_case = "m5-nax-pq2-long-prefill-v1"
    checks = [ordered]@{
      candidate_requested = $requested; tensor_api_enabled = $tensorEnabled; shape_preconditions = $shape.eligible
      trace_clean_before_request = (-not (Test-TraceHasMarkers $beforeTrace))
      inference_succeeded = $inferenceSucceeded; sentinel_found = $sentinelFound
      usage_prompt_tokens = $promptTokens; usage_completion_tokens = $completionTokens
      usage_in_range_512_to_1024 = $usageValid; prefill_observation_matches_response = $observationMatched
      observation_sequence_before = $sequenceBefore; observation_sequence_after = $sequenceAfter
      observation_prompt_tokens = $observedPromptTokens
      route_selected = $route; pipeline_marker_observed = $pipelineObserved
      pipeline_ready_ok_1 = $pipeline; dispatch_enqueued = $dispatch; after_snapshot_available = ($null -ne $after)
    }
    trace_evidence = $trace; note = "Dispatch-enqueued is not proof of completed GPU execution or numerical correctness."
  })
  $summary.long_prefill = [ordered]@{
    request_id = $requestID; run_id = $runID; completed = $inferenceSucceeded
    sentinel_found = $sentinelFound; prompt_tokens = $promptTokens; completion_tokens = $completionTokens
    answer = $answer; error = $longError
  }
  $summary.nax_evidence = [ordered]@{
    tensor_api_enabled = $tensorEnabled; prefill_effective = [bool](Get-Field $after "m5_nax_pq2_prefill_effective")
    prefill_state = [string](Get-Field $after "m5_nax_pq2_prefill_state")
    route_selected = $route; pipeline_observed = $pipelineObserved; pipeline_ready = $pipeline
    dispatch_enqueued = $dispatch; trace_before_clean = (-not (Test-TraceHasMarkers $beforeTrace))
  }
  $summary.failure_class = $classification
  $summary.failed_stage = if ($classification -eq "PASS_CANDIDATE_ROUTE_AND_INFERENCE") { "none" } else { "nax_verification" }
  if ($classification -eq "PASS_CANDIDATE_ROUTE_AND_INFERENCE") {
    $summary.status = "PASS"; Set-Stage "nax_verification" "PASS" "Candidate route, ok=1 Pipeline, Dispatch enqueue and attributed long-prefill inference passed."
  } elseif ($classification -eq "BLOCKED_SHAPE_PRECONDITION") {
    $summary.status = "BLOCKED"; Set-Stage "nax_verification" "BLOCKED" "Native shape preconditions are not satisfied."
  } elseif ($classification -like "INCOMPLETE_*") {
    $summary.status = "INCOMPLETE"; Set-Stage "nax_verification" "INCOMPLETE" $classification
  } else {
    $summary.status = "FAIL"; Set-Stage "nax_verification" "FAIL" $classification
  }
} catch {
  $message = $_.Exception.Message; $class = "UNCLASSIFIED_FAILURE"; $detail = $message
  if ($message.StartsWith("QUICK_API_ERROR|")) {
    $parts = $message -split "\|", 5
    if ($parts.Count -ge 5) { $class = $parts[1]; $detail = "HTTP " + $parts[2] + " " + $parts[3] + ": " + $parts[4] }
  } elseif ($message.StartsWith("QUICK_STAGE_FAILURE|")) {
    $parts = $message -split "\|", 3
    if ($parts.Count -ge 3) { $class = $parts[1]; $detail = $parts[2] }
  }
  if ($class -eq "API_NOT_REACHABLE") { $class = "INCOMPLETE_API_NOT_REACHABLE"; $summary.status = "INCOMPLETE" }
  elseif ($class -eq "BLOCKED_SHAPE_PRECONDITION") { $summary.status = "BLOCKED" } else { $summary.status = "FAIL" }
  $summary.failure_class = $class; $summary.failed_stage = $currentStage; $summary.failure_detail = $detail
  Set-Stage $currentStage $summary.status $detail
  if ($currentStage -eq "health") { Write-StartupDiagnosticsUnavailable $detail }
  if ($currentStage -eq "shape_precondition" -or $currentStage -eq "trace_isolation" -or $currentStage -eq "candidate_tensor_api") {
    try {
      $blockedAfter = Invoke-ApiJson -Method GET -Path "/debug/prefill"
      Save-Json "prefill-after.json" $blockedAfter
      Set-Stage "prefill_after" "PASS" "Post-gate snapshot collected; no long-prefill request was sent."
    } catch { Save-Json "prefill-after-error.json" ([ordered]@{ error = $_.Exception.Message; request_sent = $false }) }
  }
} finally {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) { Write-StartupDiagnosticsUnavailable "API health was not queried successfully." }
  $summary.finished_at = (Get-Date).ToString("o")
  Save-Json "summary.json" $summary
  $readme = @'
Bonsai Build112 M5 NAX-PQ2 Long-Prefill TestKit 1.2
Expected App SHA is pinned in EXPECTED_APP_SOURCE_SHA.txt; SOURCE_COMMIT.txt identifies this packaged TestKit revision.
The long-prefill request is sent only when candidate/Tensor evidence, PQ2_0 filename hint, API context and successful native context batch/ubatch satisfy the shape gate.
The ZIP includes before/after snapshots, deterministic request and response/error, usage, route markers, phase report and SHA-256 manifest.
PASS means route-selected + PIPELINE_READY ok=1 + dispatch-enqueued were observed after this request and the request completed with the fixed sentinel and 512-1024 input-token usage.
Dispatch-enqueued is not proof of completed GPU execution or numerical correctness. This is not performance A/B or device certification.
API key is never written to result files.
'@
  Set-Content -LiteralPath (Join-Path $outDir "README.txt") -Value $readme -Encoding UTF8
  $hashes = [ordered]@{}
  Get-ChildItem -LiteralPath $outDir -File | Where-Object { $_.Name -ne "manifest.json" } | Sort-Object Name | ForEach-Object {
    $hashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  Save-Json "manifest.json" ([ordered]@{
    schema_version = 2; status = $summary.status; failure_class = $summary.failure_class
    testkit_version = "1.2"; testkit_source_commit = $testkitSourceCommit
    expected_app_source_sha = $expectedAppSHA; app_source_git_sha = $summary.app_identity.source_git_sha
    api_key_saved = $false; files_sha256 = $hashes
  })
  $zipPath = Join-Path $resultsRoot ("Bonsai-Build112-M5-NAX-PQ2-LongPrefill-" + $stamp + ".zip")
  Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
  $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath ($zipPath + ".sha256") -Value ($zipHash + "  " + [IO.Path]::GetFileName($zipPath)) -Encoding ASCII
  Write-Host ""
  Write-Host ("FINAL: {0} / {1}" -f $summary.status, $summary.failure_class)
  Write-Host ("Evidence ZIP: " + $zipPath)
  Write-Host ("SHA-256: " + $zipHash)
  Write-Host ""
  Remove-Variable apiKey -ErrorAction SilentlyContinue
}
