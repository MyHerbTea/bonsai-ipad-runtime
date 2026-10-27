"""Behavior tests for the Build127 Q8-pinned Metal B8 candidate patch."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "PTQ1_ONECLICK"))

import q8_metal_b8 as quick_runner
from rc126_build127_patch_prism_q8_metal_b8 import (
    patch_device_source,
    patch_kernel_source,
    patch_ops_source,
    render_gate_header,
)


class Build127Q8MetalB8Tests(unittest.TestCase):
    def test_native_gate_keeps_cpu_sdot_separate_and_accepts_only_supported_b8(self):
        compiler = shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")
        if compiler is None:
            self.skipTest("C++ compiler is required for the shared native gate fixture")
        source = render_gate_header() + r"""
#include <cassert>
int main() {
    constexpr int32_t CPU_SDOT = 64;
    constexpr int32_t CANDIDATE = 320;
    assert(bonsai_q8_metal_b8_cpu_flags(CANDIDATE) == CPU_SDOT);
    assert(bonsai_q8_metal_b8_cpu_flags(-1) == -1);
    assert(!bonsai_q8_metal_b8_eligible(CPU_SDOT, true, true, true, true, true, true, 8));
    assert(bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, true, true, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE | 1, true, true, true, true, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, false, true, true, true, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, false, true, true, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, false, true, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, true, false, true, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, true, true, false, true, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, true, true, true, false, 8));
    assert(!bonsai_q8_metal_b8_eligible(CANDIDATE, true, true, true, true, true, true, 4));
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cpp = root / "gate.cpp"
            exe = root / ("gate.exe" if sys.platform == "win32" else "gate")
            cpp.write_text(source, encoding="utf-8")
            built = subprocess.run(
                [compiler, "-std=c++17", str(cpp), "-o", str(exe)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], text=True, capture_output=True, check=False)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_kernel_patch_adds_exact_ptq1_r1_8_instantiation_once(self):
        fixture = (
            'template [[host_name("kernel_mul_mv_ext_ptq1_0_f32_r1_5")]] '
            'kernel mul_mv_ext_q4_f32_t kernel_mul_mv_ext_q4_f32_disp'
            '<5, block_ptq1_0, 128, dequantize_ptq1_0_t4>;\n'
        )
        patched = patch_kernel_source(fixture)
        self.assertIn('kernel_mul_mv_ext_ptq1_0_f32_r1_8', patched)
        self.assertEqual(patched.count('kernel_mul_mv_ext_ptq1_0_f32_r1_8'), 1)
        with self.assertRaises(ValueError):
            patch_kernel_source(patched)

    def test_ops_gate_retains_generic_path_and_exposes_route_counters(self):
        fixture = """#include "ggml-metal-ops.h"
if (flags != 32 && flags != 64 && flags != 128 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;
BonsaiNativeCPUConfigure(flags);
static std::atomic<uint64_t> bonsai_benchmark_counts[10]{};
if (index >= 0 && index < 10) bonsai_benchmark_counts[index].fetch_add(1, std::memory_order_release);
default: return index >= 0 && index < 10 ? bonsai_benchmark_counts[index].load(std::memory_order_acquire) : 0;
        };

        auto pipeline = ggml_metal_library_get_pipeline_mul_mv_ext(lib, op, nsg, nxpsg, r1ptg);
ggml_metal_encoder_dispatch_threadgroups(enc, ((ne01 + r0ptg - 1)/r0ptg), ((ne11 + r1ptg - 1)/r1ptg), ne12*ne13, 32, nsg, 1);
"""
        patched = patch_ops_source(fixture)
        self.assertIn("flags != 320", patched)
        self.assertIn("BonsaiNativeCPUConfigure(bonsai_q8_metal_b8_cpu_flags(flags))", patched)
        self.assertIn("r1ptg = 8", patched)
        self.assertIn("r1ptg = 4", patched)
        self.assertIn("BonsaiNativeBenchmarkIncrement(10)", patched)
        self.assertIn("BonsaiNativeBenchmarkIncrement(11)", patched)
        self.assertIn("BonsaiNativeBenchmarkIncrement(12)", patched)
        self.assertIn("BonsaiNativeBenchmarkIncrement(13)", patched)
        self.assertIn("bonsai_q8_metal_b8_dispatch = true", patched)
        self.assertIn("if (bonsai_q8_metal_b8_dispatch && pipeline.pipeline)", patched)
        self.assertEqual(patched.count("auto pipeline = ggml_metal_library_get_pipeline_mul_mv_ext"), 1)

    def test_quick_config_is_q8_pinned_and_candidate_evidence_is_required(self):
        self.assertEqual(quick_runner.config(64), {"context": 16384, "batch": 8, "kv": "Q8_0", "flags": 64})
        self.assertEqual(quick_runner.config(320), {"context": 16384, "batch": 8, "kv": "Q8_0", "flags": 320})
        for args in ((128, 16384, 8, "Q8_0"), (320, 8192, 8, "Q8_0"),
                     (320, 16384, 16, "Q8_0"), (320, 16384, 8, "Q4_0")):
            with self.assertRaises(Exception):
                quick_runner.config(*args)

        rows = []
        for flags, prefill in ((64, 100.0), (320, 108.0), (320, 109.0), (64, 100.0)):
            delta = [0] * 14
            if flags == 320:
                delta[10:14] = [1, 1, 1, 0]
            rows.append({
                "actual": {"context": 16384, "batch": 8, "kv_k": "Q8_0", "kv_v": "Q8_0", "flags": flags},
                "valid": True, "errors": [], "counter_delta": delta,
                "prompt_hash": "same-prompt", "output_sha256": "same-output",
                "prefill_tps": prefill, "decode_tps": 10.0,
                "memory": {"sampled_peak_footprint_bytes": 1024**3, "max_thermal_state": 0},
            })
        self.assertEqual(quick_runner.evaluate(rows)["status"], "QUICK_PASS")
        rows[1]["counter_delta"][13] = 1
        with self.assertRaises(Exception):
            quick_runner.evaluate(rows)

    def test_first_performance_screen_uses_short_fixed_prompt_and_bounded_time(self):
        self.assertEqual(quick_runner.PROMPT_TOKENS, 128)
        self.assertLessEqual(quick_runner.REQUEST_DEADLINE_S, 60)
        self.assertLessEqual(quick_runner.TOTAL_DEADLINE_S, 240)
    def test_q8_run_keeps_raw_text_without_duplicate_keyword(self):
        request_key = "build127-fixed-key"
        request_id = quick_runner.b.digest(request_key)[:24]
        output = "fixed output"
        result = {
            "text": output,
            "output_sha256": quick_runner.b.digest(output),
            "evidence": {"native_context": {"context_id": "context-1"}},
            "request_id": request_id,
            "profile": {"request_id": request_id, "completed": True,
                "cpu_ptq1_sampling": {"available": True, "counting_on": False,
                    "sampling_enabled": False, "sample_period": 0}},
            "counting": "off", "sampling_period": 0,
            "prompt_tokens": 4, "generated_tokens": 32,
            "finish_reason": "length", "valid": True, "errors": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            run = quick_runner.Q8MetalRun.__new__(quick_runner.Q8MetalRun)
            run.directory = Path(temporary)
            run.identity = {"source_git_sha": "a" * 40, "official_model": {"sha256": "b" * 64}}
            run.creation_id = "context-1"
            run.report = {"samples": [{}]}
            run.save = lambda: None

            def fake_tournament_run(self, *args, **kwargs):
                if kwargs.get("keep_text") is not True:
                    raise AssertionError("Q8 baseline runner must preserve raw output text")
                return dict(result)

            with patch.object(quick_runner.b.Tournament, "run", fake_tournament_run), \
                 patch.object(quick_runner.q, "validate_native", return_value=[]):
                sample = run.run(quick_runner.config(64), "fixed prompt", 4,
                    request_key, "quick_probe", max_tokens=32)
            self.assertEqual(sample["text"], output)
            self.assertTrue(sample["valid"])

    def test_device_preflight_rejects_wrong_build_before_cold_confirmation(self):
        identity = {"source_git_sha": "a" * 40, "build_number": "127",
            "official_model": {"sha256": "b" * 64}}
        capabilities = {"evidence": {"source_git_sha": "c" * 40,
            "build_number": "126", "native_context": {"model_identity": {"sha256": "d" * 64}}},
            "hardware": {"eligible": True}}
        with patch.object(quick_runner.q, "validate_native", return_value=[]):
            errors = quick_runner.validate_device_preflight(identity, capabilities)
        self.assertEqual(errors, ["source_git_sha", "build_number", "model_sha256"])

    def test_total_deadline_covers_setup_and_cleanup_keeps_time_to_restore(self):
        client = quick_runner.Q8MetalClient("http://127.0.0.1:8080", "")
        now = 100.0
        client.quick_deadline = now + 7
        seen = {}
        def fake_request(self, command, body=None, **kwargs):
            seen["command"] = command
            return kwargs
        with patch.object(quick_runner.time, "monotonic", return_value=now), \
             patch.object(quick_runner.q.Q8Client, "request", fake_request):
            result = client.request("tokenize", timeout=60)
            self.assertEqual(result["timeout"], 7)
        with patch.object(quick_runner.time, "monotonic", return_value=now + 8), \
             patch.object(quick_runner.q.Q8Client, "request", fake_request):
            with self.assertRaisesRegex(Exception, "QUICK_SCREEN_TOTAL_DEADLINE"):
                client.request("configure", timeout=240)
            client.quick_cleanup = True
            result = client.request("restore", timeout=240)
            self.assertEqual(result["timeout"], 240)

    def test_each_sample_requires_matching_source_build_model_and_process_identity(self):
        row = {"actual": {"context": 16384, "batch": 8, "kv_k": "Q8_0", "kv_v": "Q8_0", "flags": 320},
            "valid": True, "errors": [], "counter_delta": [0] * 10 + [1, 1, 1, 0],
            "evidence": {"source_git_sha": "a" * 40,
                "build_number": "127", "process_id": "process-1",
                "native_context": {"model_identity": {"sha256": "b" * 64}}}}
        identity = {"source_git_sha": "a" * 40, "build_number": "127",
            "official_model": {"sha256": "b" * 64}}
        self.assertEqual(quick_runner.validate_candidate_sample(row, 320, identity, "process-1"), [])
        row["evidence"]["source_git_sha"] = "c" * 40
        errors = quick_runner.validate_candidate_sample(row, 320, identity, "process-1")
        self.assertIn("sample_source_identity", errors)

    def test_post_restore_api_accepts_recreated_q8_context_and_rejects_candidate_context(self):
        identity = {"source_git_sha": "a" * 40, "official_model": {"sha256": "b" * 64}}
        class FakeClient:
            def __init__(self, context_id): self.context_id = context_id
            def request(self, command, body=None, **kwargs):
                if command == "/health": return {"model": "bonsai-test"}
                if command == "/v1/chat/completions":
                    return {"choices": [{"message": {"content": "BONSAI"}}],
                        "usage": {"completion_tokens": 1}}
                if command == "capabilities":
                    return {"evidence": {"source_git_sha": identity["source_git_sha"],
                        "native_context": {"context_id": self.context_id,
                            "model_identity": {"sha256": identity["official_model"]["sha256"]}}}}
                raise AssertionError("unexpected command: " + command)
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(quick_runner.q, "validate_native", return_value=[]):
            directory = Path(temporary)
            restored = quick_runner.ordinary_api_check(FakeClient("restored-context"), identity,
                directory, {"pre-experiment-context", "candidate-context"})
            self.assertEqual(restored, "restored-context")
            with self.assertRaisesRegex(Exception, "ORDINARY_API_CONTEXT_NOT_RECREATED"):
                quick_runner.ordinary_api_check(FakeClient("candidate-context"), identity,
                    directory, {"candidate-context"})

    def test_actual_patched_pinned_prism_has_candidate_and_generic_fallback(self):
        prism = os.environ.get("BONSAI_PRISM_TEST_DIR")
        if not prism:
            self.skipTest("CI supplies the pinned Prism checkout after applying Build127")
        root = Path(prism) / "ggml/src/ggml-metal"
        ops = (root / "ggml-metal-ops.cpp").read_text(encoding="utf-8")
        kernel = (root / "kernels/mul_mv.metal").read_text(encoding="utf-8")
        device = (root / "ggml-metal-device.m").read_text(encoding="utf-8")
        self.assertIn("BONSAI_Q8_METAL_B8_127", ops)
        self.assertIn("kernel_mul_mv_ext_ptq1_0_f32_r1_8", kernel)
        self.assertIn("r1ptg = 8", ops)
        self.assertIn("r1ptg = 4", ops)
        self.assertIn("BonsaiNativeBenchmarkIncrement(12)", ops)
        self.assertIn("BonsaiNativeBenchmarkIncrement(13)", ops)
        capability = device.index("| 256u")
        m5_guard = device.rfind("if (dev->library && dev->props.device_id >= GGML_METAL_DEVICE_M5)", 0, capability)
        self.assertGreaterEqual(m5_guard, 0)
        self.assertLess(device.rfind("}", m5_guard, capability), 0)

    def test_m5_is_only_device_publishing_the_b8_capability(self):
        fixture = "if (dev->library && dev->props.device_id >= GGML_METAL_DEVICE_M5) {\n    BonsaiNativeBenchmarkPublishCapabilities(6u | ((dev->props.has_tensor_benchmark && BonsaiNativeBenchmarkTensorSourceAvailable()) ? 1u : 0u));\n}"
        patched = patch_device_source(fixture)
        capability = patched.index("| 256u")
        m5_guard = patched.rfind("if (dev->library && dev->props.device_id >= GGML_METAL_DEVICE_M5)", 0, capability)
        self.assertGreaterEqual(m5_guard, 0)
        self.assertLess(patched.rfind("}", m5_guard, capability), 0)


if __name__ == "__main__":
    unittest.main()