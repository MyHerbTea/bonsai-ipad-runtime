#!/usr/bin/env python3
"""Contract checks for the M5-NAX-PQ2-01 candidate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/rc126_build113_patch_prism_m5_nax_pq2.py"
WORKFLOW = ROOT / ".github/workflows/build112-b16-default.yml"
DOC = ROOT / "docs/optimization/backburner-integration/RC1.26_BUILD113_M5_NAX_PQ2_01.md"
VERIFY = ROOT / "tools/rc126_build113_verify_m5_nax_pq2_binary.sh"
ENGINE = ROOT / "BonsaiLab/BonsaiEngine.swift"
PRODUCTION = ROOT / "BonsaiLab/ProductionView.swift"
POLICY = ROOT / "BonsaiLab/Build113MetalTensorPolicy.swift"
GOVERNOR = ROOT / "BonsaiLab/M5RuntimeGovernor.swift"
POLICY_TESTS = ROOT / "tools/rc126_build113_metal_tensor_policy_tests.swift"
APP = ROOT / "BonsaiLab/BonsaiLabApp.swift"
SERVER = ROOT / "BonsaiLab/LocalOpenAIServer.swift"

def require(path: Path, *needles: str) -> None:
    source = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in source, f"{needle!r} missing from {path}"

require(
    PATCH,
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "BONSAI_M5_NAX_PQ2_01",
    "GGML_TYPE_PQ2_0",
    "GGML_METAL_PQ2_NAX_DISABLE",
    "get_left_input_cooperative_tensor",
    "kernel_mul_mm_nax_pq2_0_f32",
    "BONSAI_M5_NAX_PQ2_BM 16",
    "BONSAI_M5_NAX_PQ2_BN 128",
    "BONSAI_M5_NAX_PQ2_NSG 4",
    "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED",
    "BUILD113_M5_NAX_PQ2_PIPELINE_READY",
    "BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED",
    "ne11 >= 16 && ne11 % 16 == 0",
    "max_total_threads_per_threadgroup(128)",
    "std::atomic_flag",
    "bonsai-build84-trace.h",
    "bonsai_m5_nax_pq2_trace",
    "BONSAI_M5_NAX_PQ2_TRACE_PATH",
    'std::getenv("BONSAI_M5_NAX_PQ2_TRACE_PATH") != nullptr',
)

require(
    WORKFLOW,
    "lab/m5-nax-pq2-01",
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "rc126_build113_patch_prism_m5_nax_pq2.py",
    "build-xcframework.sh ios-device",
    "M5-NAX-PQ2-01",
    "Metal Tensor API: default-disabled; explicit Phase2C CANDIDATE launch arm enables it",
    "combined Tensor + NAX-PQ2 bundle versus stock B16",
    "rc126_build113_metal_tensor_policy_tests.swift",
    "build113_metal_tensor_policy_tests",
    "rc126_build113_verify_m5_nax_pq2_binary.sh",
    "M5_NAX_PQ2_BINARY_VERIFICATION.txt",
)

require(
    DOC,
    "Build112",
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "PQ2_0",
    "cooperative tensor",
    "combined Tensor-enabled + NAX-PQ2 bundle",
    "does not isolate NAX-only performance",
    "NOT DEVICE CERTIFIED",
)

require(
    ENGINE,
    "effectiveBuild113MetalTensorDisabled",
    "Build113MetalTensorPolicy.effectiveDisabled",
    "Phase2CMetalTensorLaunchLatch.arm.rawValue",
    "Build113MetalTensorPolicy.requiresRestart",
    "unsetenv(\"GGML_METAL_TENSOR_DISABLE\")",
    "enableBuild113NaxRouteTrace",
    "contextLength: config.context",
    "contextLength: validated.context",
    "recordBuild113NativeContextAttempt",
    "recordBuild113NativeContextCreated",
    "BonsaiBuild113ModelFileName",
    "PQ2_0_FILENAME_HINT",
    "BONSAI_M5_NAX_PQ2_TRACE_PATH",
    "unsetenv(\"BONSAI_M5_NAX_PQ2_TRACE_PATH\")",
)

require(
    GOVERNOR,
    "beginCandidateShapeTrialIfPending",
    "noteCandidateShapeTrialStartupFailure",
    "noteCandidateShapeTrialInferenceFailure",
    "noteCandidateShapeTrialTextSuccess",
    "candidateShapeTrialSnapshot",
    "BonsaiBuild113NaxCandidateTrialPending",
    "LONG_PREFILL_SUCCESS",
)

require(
    APP,
    "init()",
    "Phase2CMetalTensorLaunchLatch.arm",
)

require(
    ROOT / "tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1",
    "HEALTH_CHECK_FAILED",
    "MODEL_LIST_FAILED",
    "INFERENCE_FAILED",
    "AUTH_FAILED",
    "REQUEST_CONFIGURATION_ERROR",
)

require(
    POLICY,
    'launchArmRawValue == "CANDIDATE"',
    "return requestedDisabled",
    "requiresRestart",
    "latchedDisabled != effectiveDisabled",
)

require(
    POLICY_TESTS,
    "Default API cold start",
    "explicit CANDIDATE",
    "PASS Build113 Metal Tensor policy",
)

require(
    PRODUCTION,
    "Phase2CMetalTensorLaunchLatch.apply(",
    "allowNAXCandidate: allowNAXCandidateForModel",
    "beginCandidateShapeTrialIfPending",
    "noteCandidateShapeTrialTextSuccess",
    "noteCandidateShapeTrialStartupFailure",
    "实验：M5 NAX-PQ2 Tensor 候选（下次启动）",
    "Phase2CMetalTensorLaunchLatch.scheduleNext",
)

require(
    SERVER,
    '"build_id": "rc1.26-build112-m5-nax-pq2-01"',
    '"candidate_build_id": "rc1.26-build112-m5-nax-pq2-01"',
    "debugM5NaxPQ2TraceEvidence",
    "api_startup_stage",
    "api_startup_previous_incomplete",
    "api_startup_last_error",
    "m5_nax_pq2_trace",
    "m5-nax-pq2-trace-evidence-v1",
    "m5_nax_pq2_prefill_effective",
    "m5_nax_pq2_prefill_state",
    "m5_nax_pq2_tensor_api_enabled",
    "native_context_created",
    "native_context_ubatch",
    "model_file_name",
    "model_quantization_hint",
    "m5_nax_candidate_shape_trial",
    "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED",
    "BUILD113_M5_NAX_PQ2_PIPELINE_READY",
    "BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED",
    "TRACE_FILE_UNAVAILABLE",
    "tensor_api_enabled",
    "tensor_disable_env_present",
    "backend_tensor_log_observed",
    "backend_has_tensor",
    "TENSOR_API_NOT_ENABLED",
    "DISPATCH_ENQUEUED_NOT_COMPLETION_PROOF",
    "trace_header",
)

require(
    VERIFY,
    "strings",
    "nm -gU",
    "kernel_mul_mm_nax_pq2_0_f32",
    "_ggml_metal_library_get_pipeline_mul_mm_nax_pq2",
    "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED",
    "BONSAI_M5_NAX_PQ2_TRACE_PATH",
    "runtime_metal_compile=NOT_VERIFIED",
    "performance=NOT_MEASURED",
)

print("BUILD113_M5_NAX_PQ2_CONTRACT: PASS")
