Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot
$expectedCommit = (Get-Content -LiteralPath (Join-Path $scriptRoot "SOURCE_COMMIT.txt") -Raw).Trim()
$defaultBase = "http://192.168.1.85:8080"
$enteredBase = Read-Host "Bonsai Base URL [$defaultBase]"
if ([string]::IsNullOrWhiteSpace($enteredBase)) { $enteredBase = $defaultBase }
$root = $enteredBase.Trim().TrimEnd("/")
if ($root.EndsWith("/v1")) { $root = $root.Substring(0, $root.Length - 3) }
$secure = Read-Host "API Key (needed for authenticated build/models/Smoke checks)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resultsRoot = Join-Path $scriptRoot "RESULTS"
$outDir = Join-Path $resultsRoot ("Build112-NAX-Quick-" + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$summary = [ordered]@{
  schema_version=1; testkit="Bonsai Build112 NAX Quick TestKit"; testkit_version="1.1"
  testkit_source_commit=$expectedCommit; expected_candidate_build_id="rc1.26-build112-m5-nax-pq2-01"
  started_at=(Get-Date).ToString("o"); base_url=$root; api_key_saved=$false
  app_identity=[ordered]@{source_git_sha="unavailable"}; status="INCOMPLETE"; failure_class="NOT_RUN"
  failed_stage="none"; stages=[ordered]@{}
}
function Save-Json([string]$Name,$Value) {
  $Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $outDir $Name) -Encoding UTF8
}
function Set-Stage([string]$Name,[string]$Status,[string]$Detail) {
  $summary.stages[$Name]=[ordered]@{status=$Status;detail=$Detail;timestamp=(Get-Date).ToString("o")}
}
function Get-HttpStatusCode($Record) {
  try { $response=$Record.Exception.Response; if ($null -ne $response -and $null -ne $response.StatusCode) { return [int]$response.StatusCode } } catch {}
  return 0
}
function Invoke-ApiJson([string]$Method,[string]$Path,$Body=$null,[bool]$UseKey=$true) {
  $headers=@{}
  if ($UseKey -and -not [string]::IsNullOrWhiteSpace($apiKey)) { $headers["X-API-Key"]=$apiKey }
  try {
    if ($Method -eq "GET") { return Invoke-RestMethod -Method Get -Uri ($root+$Path) -Headers $headers -TimeoutSec 30 }
    $wire=$Body | ConvertTo-Json -Depth 20 -Compress
    return Invoke-RestMethod -Method Post -Uri ($root+$Path) -Headers $headers -ContentType "application/json" -Body $wire -TimeoutSec 600
  } catch {
    $code=Get-HttpStatusCode $_
    if ($code -eq 401 -or $code -eq 403) { $kind="AUTH_FAILED" }
    elseif ($code -eq 400 -or $code -eq 422) { $kind="REQUEST_CONFIGURATION_ERROR" }
    elseif ($code -ge 500 -and $currentStage -eq "health") { $kind="HEALTH_CHECK_FAILED" }
    elseif ($code -ge 500 -and $currentStage -eq "models") { $kind="MODEL_LIST_FAILED" }
    elseif ($code -ge 500 -and $currentStage -eq "smoke") { $kind="INFERENCE_FAILED" }
    elseif ($code -ge 500) { $kind="API_SERVER_ERROR" }
    elseif ($code -eq 0) { $kind="API_NOT_REACHABLE" } else { $kind="HTTP_ERROR" }
    throw ("QUICK_API_ERROR|{0}|{1}|{2}|{3}" -f $kind,$code,$Path,$_.Exception.Message)
  }
}
function Write-StartupDiagnosticsUnavailable([string]$Reason) {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) {
    Save-Json "startup-diagnostics.json" ([ordered]@{
      retrieval_status="NOT_RETRIEVABLE_OVER_HTTP";reason=$Reason;api_startup_stage="UNAVAILABLE"
      api_startup_previous_incomplete="UNAVAILABLE";api_startup_attempt=$null;api_startup_last_error="UNAVAILABLE"
      note="When listener is down, open Bonsai > Advanced & Diagnostics > Refresh and copy full diagnostics. The app persists startup stage/error locally."
    })
  }
}
Save-Json "environment.json" ([ordered]@{
  collected_at=(Get-Date).ToString("o");operating_system=[Environment]::OSVersion.VersionString
  powershell_version=$PSVersionTable.PSVersion.ToString();powershell_edition=$PSVersionTable.PSEdition
  is_64_bit_os=[Environment]::Is64BitOperatingSystem;is_64_bit_process=[Environment]::Is64BitProcess;base_url=$root
})
Save-Json "testkit-identity.json" ([ordered]@{
  testkit=$summary.testkit;version=$summary.testkit_version;source_commit=$expectedCommit
  expected_candidate_build_id=$summary.expected_candidate_build_id;api_key_saved=$false
})

$currentStage="health"
try {
  $health=Invoke-ApiJson -Method GET -Path "/health" -UseKey:$false
  Save-Json "health.json" $health
  $d=$health.diagnostics
  $startup=[ordered]@{
    retrieval_status="AVAILABLE";source="GET /health diagnostics";api_startup_stage=$d.api_startup_stage
    api_startup_previous_incomplete=$d.api_startup_previous_incomplete;api_startup_attempt=$d.api_startup_attempt
    api_startup_last_error=$d.api_startup_last_error;last_engine_stage=$d.last_engine_stage
    context_switch_state=$d.context_switch_state;collected_at=(Get-Date).ToString("o")
  }
  Save-Json "startup-diagnostics.json" $startup
  $summary.api_reachable=$true;$summary.api_startup_stage=[string]$startup.api_startup_stage
  if ([string]$health.status -ne "ok") { Set-Stage "health" "FAIL" "Unexpected /health status."; throw "QUICK_STAGE_FAILURE|HEALTH_CHECK_FAILED|Unexpected /health status." }
  Set-Stage "health" "PASS" "GET /health returned status=ok."

  $currentStage="build_identity"
  $build=Invoke-ApiJson -Method GET -Path "/debug/build";Save-Json "build.json" $build
  $appSHA=[string]$build.source_git_sha;$appID=[string]$build.candidate_build_id;$buildNo=[string]$build.build_number
  $identityOK=($buildNo -eq "112") -and ($appID -eq "rc1.26-build112-m5-nax-pq2-01") -and ($appSHA -eq $expectedCommit)
  $summary.app_identity=[ordered]@{
    source_git_sha=$appSHA;candidate_build_id=$appID;build_number=$buildNo
    workflow_run_id=[string]$build.workflow_run_id;prism_upstream_sha=[string]$build.prism_upstream_sha
    matches_testkit_source_commit=($appSHA -eq $expectedCommit)
  }
  if (-not $identityOK) { Set-Stage "build_identity" "FAIL" "App build identity differs from this exact TestKit source/candidate."; throw "QUICK_STAGE_FAILURE|BUILD_IDENTITY_MISMATCH|App identity must match Build112 M5-NAX-PQ2 and this TestKit commit." }
  Set-Stage "build_identity" "PASS" "Build112 candidate and exact source commit match."

  $currentStage="models"
  $models=Invoke-ApiJson -Method GET -Path "/v1/models";Save-Json "models.json" $models
  $modelRows=@($models.data)
  if ($modelRows.Count -lt 1 -or [string]::IsNullOrWhiteSpace([string]$modelRows[0].id)) { Set-Stage "models" "FAIL" "No model ID returned."; throw "QUICK_STAGE_FAILURE|MODEL_UNAVAILABLE|/v1/models returned no usable model ID." }
  $modelID=[string]$modelRows[0].id;Set-Stage "models" "PASS" ("Model ID: "+$modelID)

  $currentStage="prefill_before"
  $before=Invoke-ApiJson -Method GET -Path "/debug/prefill";Save-Json "prefill-before.json" $before
  Set-Stage "prefill_before" "PASS" "Pre-request Phase2C/NAX diagnostics collected."

  $currentStage="smoke"
  $body=[ordered]@{model=$modelID;messages=@(@{role="user";content="Reply exactly with BONSAI_QUICK_SMOKE_OK."});max_tokens=16;temperature=0;stream=$false}
  Save-Json "smoke-request.json" $body
  $response=Invoke-ApiJson -Method POST -Path "/v1/chat/completions" -Body $body
  Save-Json "smoke-response.json" $response
  $answer=[string]$response.choices[0].message.content
  $summary.smoke_answer_contains_sentinel=$answer.Contains("BONSAI_QUICK_SMOKE_OK");$summary.smoke_usage=$response.usage
  if (-not $summary.smoke_answer_contains_sentinel) { Set-Stage "smoke" "FAIL" "Fixed sentinel absent."; throw "QUICK_STAGE_FAILURE|SMOKE_SEMANTIC_FAILURE|Response did not contain BONSAI_QUICK_SMOKE_OK." }
  Set-Stage "smoke" "PASS" "Fixed non-streaming request returned the expected sentinel."

  $currentStage="prefill_after"
  $after=Invoke-ApiJson -Method GET -Path "/debug/prefill";Save-Json "prefill-after.json" $after
  $names=@($after.PSObject.Properties.Name)
  $hasLegacy=$names -contains "metal_tensor_prefill_effective";$hasTrace=$names -contains "m5_nax_pq2_trace"
  $hasState=$names -contains "m5_nax_pq2_prefill_state";$hasTensor=$names -contains "m5_nax_pq2_tensor_api_enabled"
  $requested=[bool]$after.metal_tensor_prefill_requested;$tensorEnabled=[bool]$after.m5_nax_pq2_tensor_api_enabled
  $trace=$after.m5_nax_pq2_trace;$route=[bool]$trace.route_selected;$pipeline=[bool]$trace.pipeline_ready;$dispatch=[bool]$trace.dispatch_enqueued
  $diagStatus="PASS";$diagDetail="Phase2C legacy and NAX evidence fields exist and the launch arm matches Tensor state."
  if (-not ($hasLegacy -and $hasTrace -and $hasState -and $hasTensor)) { $diagStatus="FAIL";$diagDetail="Phase2C/NAX diagnostic fields missing." }
  elseif ($requested -ne $tensorEnabled) { $diagStatus="FAIL";$diagDetail="Requested launch arm and observed Tensor API state disagree." }
  if (-not $requested) { $naxStatus="NOT_REQUESTED_BASELINE" }
  elseif ($route -and $pipeline -and $dispatch) { $naxStatus="DISPATCH_ENQUEUED_NOT_COMPLETION_PROOF" }
  else { $naxStatus="NOT_EXERCISED_BY_MINIMAL_SMOKE" }
  Save-Json "phase2c-nax-diagnostics.json" ([ordered]@{
    schema_status=$diagStatus;schema_detail=$diagDetail;phase2c_metal_tensor_prefill_requested=$requested
    legacy_phase2c_metal_tensor_prefill_effective=$after.metal_tensor_prefill_effective
    phase2c_policy=$after.metal_tensor_prefill_policy;nax_prefill_effective=$after.m5_nax_pq2_prefill_effective
    nax_prefill_state=$after.m5_nax_pq2_prefill_state;nax_tensor_api_enabled=$tensorEnabled
    nax_route_selected=$route;nax_pipeline_ready=$pipeline;nax_dispatch_enqueued=$dispatch;nax_status=$naxStatus
    trace=$trace;note="The short Smoke request is not intended to trigger large-prefill NAX. Missing route evidence here is not a dispatch pass or fail."
  })
  if ($diagStatus -ne "PASS") { Set-Stage "phase2c_nax_diagnostics" "FAIL" $diagDetail;throw "QUICK_STAGE_FAILURE|NAX_DIAGNOSTIC_INCONSISTENCY|$diagDetail" }
  Set-Stage "phase2c_nax_diagnostics" "PASS" $diagDetail
  $summary.nax_status=$naxStatus;$summary.nax_candidate_requested=$requested;$summary.nax_route_selected=$route
  $summary.nax_pipeline_ready=$pipeline;$summary.nax_dispatch_enqueued=$dispatch
  if ([string]$startup.api_startup_stage -ne "READY") { Set-Stage "startup_lifecycle" "FAIL" "API responding but startup stage is not READY.";throw ("QUICK_STAGE_FAILURE|STARTUP_LIFECYCLE_INCONSISTENCY|API responding with stage "+[string]$startup.api_startup_stage) }
  Set-Stage "startup_lifecycle" "PASS" "Persisted startup lifecycle is READY."
  $summary.status="PASS";$summary.failure_class="NONE";$summary.failed_stage="none"
} catch {
  $message=$_.Exception.Message;$class="UNCLASSIFIED_FAILURE";$detail=$message
  if ($message.StartsWith("QUICK_API_ERROR|")) {
    $parts=$message -split "\|",5
    if ($parts.Count -ge 5) { $class=$parts[1];$detail="HTTP "+$parts[2]+" "+$parts[3]+": "+$parts[4] }
  } elseif ($message.StartsWith("QUICK_STAGE_FAILURE|")) {
    $parts=$message -split "\|",3
    if ($parts.Count -ge 3) { $class=$parts[1];$detail=$parts[2] }
  }
  if ($class -eq "API_NOT_REACHABLE") { $summary.status="INCOMPLETE" } else { $summary.status="FAIL" }
  $summary.failure_class=$class;$summary.failed_stage=$currentStage;$summary.failure_detail=$detail
  Set-Stage $currentStage $summary.status $detail
  if ($currentStage -eq "health") { Write-StartupDiagnosticsUnavailable $detail }
} finally {
  if (-not (Test-Path -LiteralPath (Join-Path $outDir "startup-diagnostics.json"))) { Write-StartupDiagnosticsUnavailable "API health was not queried successfully." }
  $summary.finished_at=(Get-Date).ToString("o");Save-Json "summary.json" $summary
  $readme=@"
Bonsai Build112 NAX Quick TestKit result
Overall status: $($summary.status)
Failure class: $($summary.failure_class)
Failed stage: $($summary.failed_stage)

Files: summary.json, environment.json, health.json (if reachable), startup-diagnostics.json, build.json, models.json, smoke-request.json, smoke-response.json, prefill-before.json, prefill-after.json, phase2c-nax-diagnostics.json and manifest.json.
The manifest contains SHA-256 hashes of other result files. The API key is never saved. If the listener is down, internal startup state is marked unavailable over HTTP and remains accessible in the app's Advanced & Diagnostics snapshot.
The short Smoke request does not certify NAX execution/performance; dispatch-enqueued is not proof of completed GPU execution.
"@
  Set-Content -LiteralPath (Join-Path $outDir "README.txt") -Value $readme -Encoding UTF8
  $hashes=[ordered]@{}
  Get-ChildItem -LiteralPath $outDir -File | Where-Object { $_.Name -ne "manifest.json" } | Sort-Object Name | ForEach-Object { $hashes[$_.Name]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  Save-Json "manifest.json" ([ordered]@{schema_version=1;status=$summary.status;failure_class=$summary.failure_class;testkit_source_commit=$expectedCommit;app_source_git_sha=$summary.app_identity.source_git_sha;api_key_saved=$false;files_sha256=$hashes})
  $zipPath=Join-Path $resultsRoot ("Bonsai-Build112-NAX-Quick-"+$stamp+".zip")
  Compress-Archive -Path (Join-Path $outDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
  $zipHash=(Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  Set-Content -LiteralPath ($zipPath+".sha256") -Value ($zipHash+"  "+[IO.Path]::GetFileName($zipPath)) -Encoding ASCII
  Write-Host "";Write-Host ("FINAL: {0} / {1}" -f $summary.status,$summary.failure_class);Write-Host ("Evidence ZIP: "+$zipPath);Write-Host ("SHA-256: "+$zipHash);Write-Host ""
  Remove-Variable apiKey -ErrorAction SilentlyContinue
}
