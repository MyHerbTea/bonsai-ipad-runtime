#!/usr/bin/env python3
"""Offline regression tests for the PTQ1_0 A/B decision and ZIP integrity logic."""
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ptq1_tensorops_ab as ab  # noqa: E402


def fake_arm(arm, targets=(512, 2048), prefill_tps=None, ttft_ms=None, decode_tps=20.0, memory=1_000_000):
    candidate = arm == "CANDIDATE"
    identity = {
        "source_git_sha": "a" * 40,
        "build_number": "112",
        "prism_upstream_sha": "adfffbe41b2cabcd51fff326ab045662265062bb",
        "model_file": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "model_id": "bonsai-2-27b-local",
        "context": 16384,
        "batch": 16,
        "ubatch": 16,
        "arm": arm,
    }
    result = {
        "schema": "bonsai-ptq1-tensorops-ab-v1",
        "arm": arm,
        "identity": identity,
        "prompts_sha256": "b" * 64,
        "target_tokens": list(targets),
        "candidate_route_verified": candidate,
        "samples": [],
    }
    for target in targets:
        for repeat in range(1, ab.REPEATS + 1):
            output_hash = hashlib.sha256(f"{target}:{repeat}".encode()).hexdigest()
            result["samples"].append({
                "arm": arm,
                "target_tokens": target,
                "repeat": repeat,
                "valid": True,
                "prefill_tokens_per_second": (prefill_tps or (120.0 if candidate else 100.0)),
                "ttft_ms": (ttft_ms or (850.0 if candidate else 1000.0)),
                "decode_tokens_per_second": decode_tps,
                "metal_current_allocated_bytes": memory + (100 if candidate else 0),
                "output_sha256": output_hash,
                "route_selected_delta": 1 if candidate else 0,
                "pipeline_ready_delta": 1 if candidate else 0,
                "dispatch_enqueued_delta": 1 if candidate else 0,
                "fallback_delta": 0,
                "successful_inference_after_dispatch": candidate,
                "thermal_state": "nominal",
            })
    return result


def make_zip(path, tamper_samples=False, omit_samples_manifest=False, mismatch_result_samples=False):
    prompts = {"512": {"target_tokens": 512, "actual_tokens": 512, "prompt": " apple"}}
    identity = {
        "source_git_sha": "a" * 40,
        "model_file": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "context": 16384, "batch": 16, "ubatch": 16,
        "model_id": "bonsai-2-27b-local", "arm": "BASELINE",
    }
    prompt_hash = ab.sha(json.dumps(prompts, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    result = {
        "schema": "bonsai-ptq1-tensorops-ab-v1",
        "arm": "BASELINE",
        "identity": identity,
        "prompts_sha256": prompt_hash,
        "target_tokens": [512],
        "samples": [{"fixture_mismatch": True}] if mismatch_result_samples else [],
    }
    members = {
        "result.json": json.dumps(result, sort_keys=True).encode(),
        "prompts.json": json.dumps(prompts, sort_keys=True).encode(),
        "samples.json": b"[]",
        "identity.json": json.dumps(identity, sort_keys=True).encode(),
    }
    manifest = {name: ab.sha(data) for name, data in members.items()}
    if omit_samples_manifest:
        manifest.pop("samples.json")
    if tamper_samples:
        members["samples.json"] = b'[{ "tampered": true }]'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
        zf.writestr("SHA256_MANIFEST.json", json.dumps(manifest).encode())


def runtime_snapshot(arm):
    return {
        "build": {"source_git_sha": "a" * 40, "build_number": "112", "prism_upstream_sha": "adfffbe41b2cabcd51fff326ab045662265062bb"},
        "prefill": {
            "model_file_name": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
            "native_context_context": 16384,
            "native_context_batch": 16,
            "native_context_ubatch": 16,
            "ptq1_tensorops_trace": {
                "input_type_count": 0, "route_selected_count": 0,
                "pipeline_ready_count": 0, "dispatch_enqueued_count": 0,
                "fallback_count": 0,
            },
        },
        "phase2c": {"launch_arm": arm, "backend_latched_arm": arm, "backend_evidence_valid": True},
        "phase2d": {"launch_arm": "CANDIDATE16", "shape_evidence_valid": True, "active_batch": 16, "active_ubatch": 16},
    }


assert ab.validate_runtime(runtime_snapshot("BASELINE"), "BASELINE", "a" * 40)["backend_evidence_valid"] is True
assert ab.validate_runtime(runtime_snapshot("CANDIDATE"), "CANDIDATE", "a" * 40)["phase2d_launch_arm"] == "CANDIDATE16"
for bad_snapshot, arm, expected in (
    (runtime_snapshot("BASELINE"), "CANDIDATE", "a" * 40),
    (runtime_snapshot("CANDIDATE"), "CANDIDATE", "c" * 40),
):
    try:
        ab.validate_runtime(bad_snapshot, arm, expected)
    except RuntimeError:
        pass
    else:
        raise AssertionError("mismatched arm or source identity was accepted")
wrong_shape = runtime_snapshot("BASELINE")
wrong_shape["phase2d"]["launch_arm"] = "BASELINE8"
try:
    ab.validate_runtime(wrong_shape, "BASELINE", "a" * 40)
except RuntimeError:
    pass
else:
    raise AssertionError("non-B16 shape arm was accepted")

baseline = fake_arm("BASELINE")
candidate = fake_arm("CANDIDATE")
assert ab.compare_arms(baseline, candidate)["status"] == "M5_PERFORMANCE_GAIN_VERIFIED"

slow_candidate = fake_arm("CANDIDATE", prefill_tps=110.0, ttft_ms=950.0)
assert ab.compare_arms(baseline, slow_candidate)["status"] == "CANDIDATE_NO_GAIN"

missing_target = fake_arm("CANDIDATE")
missing_target["samples"] = [x for x in missing_target["samples"] if x["target_tokens"] == 512]
assert ab.compare_arms(baseline, missing_target)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

missing_route = fake_arm("CANDIDATE")
missing_route["candidate_route_verified"] = False
assert ab.compare_arms(baseline, missing_route)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

invalid_route_attempt = fake_arm("CANDIDATE")
invalid_route_attempt["samples"][0]["valid"] = False
invalid_route_attempt["samples"][0]["fallback_delta"] = 1
invalid_route_attempt["candidate_route_verified"] = False
assert ab.compare_arms(baseline, invalid_route_attempt)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

baseline_with_candidate_dispatch = fake_arm("BASELINE")
baseline_with_candidate_dispatch["samples"][0]["dispatch_enqueued_delta"] = 1
assert ab.compare_arms(baseline_with_candidate_dispatch, candidate)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

hash_mismatch = fake_arm("CANDIDATE")
hash_mismatch["samples"][0]["output_sha256"] = "0" * 64
assert ab.compare_arms(baseline, hash_mismatch)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

thermal_mismatch = fake_arm("CANDIDATE")
for row in thermal_mismatch["samples"]:
    row["thermal_state"] = "fair"
assert ab.compare_arms(baseline, thermal_mismatch)["status"] == "BLOCKED_NEEDS_ENGINE_EVIDENCE"

with tempfile.TemporaryDirectory() as directory:
    good = Path(directory) / "good.zip"
    make_zip(good)
    result, prompts, samples = ab.load_previous(good)
    assert result["target_tokens"] == [512] and prompts["512"]["actual_tokens"] == 512 and samples == []

    bad = Path(directory) / "bad.zip"
    make_zip(bad, tamper_samples=True)
    try:
        ab.load_previous(bad)
    except RuntimeError as exc:
        assert "SHA256 mismatch" in str(exc)
    else:
        raise AssertionError("tampered prior-arm ZIP was accepted")

    missing_manifest = Path(directory) / "missing_manifest.zip"
    make_zip(missing_manifest, omit_samples_manifest=True)
    try:
        ab.load_previous(missing_manifest)
    except RuntimeError as exc:
        assert "manifest coverage mismatch" in str(exc)
    else:
        raise AssertionError("ZIP with an unmanifested samples.json was accepted")

    inconsistent = Path(directory) / "inconsistent_samples.zip"
    make_zip(inconsistent, mismatch_result_samples=True)
    try:
        ab.load_previous(inconsistent)
    except RuntimeError as exc:
        assert "result.json samples differ from samples.json" in str(exc)
    else:
        raise AssertionError("ZIP with inconsistent result/sample payloads was accepted")

print("PTQ1_TENSOROPS_AB_LOGIC: PASS (target completeness, every-attempt route evidence, hashes, thermal gates, manifest integrity)")
