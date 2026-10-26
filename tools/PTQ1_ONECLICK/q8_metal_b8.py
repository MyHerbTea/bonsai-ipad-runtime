#!/usr/bin/env python3
"""Bounded Build127 Quick screen for fixed 16K/B8/Q8_0 PTQ1 Metal B8."""
import argparse
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import statistics
import time
import uuid
import zipfile

import ptq1_oneclick as b
import kv_baseline as q

BASELINE = dict(context=16384, batch=8, kv="Q8_0", flags=64)
CANDIDATE = dict(context=16384, batch=8, kv="Q8_0", flags=320)
ORDER = (64, 320, 320, 64)
TOTAL_DEADLINE_S = 600
REQUEST_DEADLINE_S = 150
MAX_MEMORY_DELTA = 512 * 1024 * 1024

def config(flags=64, context=16384, batch=8, kv="Q8_0"):
    if (flags, context, batch, kv) not in (
        (64, 16384, 8, "Q8_0"),
        (320, 16384, 8, "Q8_0"),
    ):
        raise b.EvidenceError("ONLY_16K_B8_Q8_FLAGS_64_OR_320")
    return dict(context=context, batch=batch, kv=kv, flags=flags)

def validate_candidate_sample(row, flags, identity=None, process_id=None):
    errors = []
    actual = row.get("actual") or {}
    if actual.get("context") != 16384 or actual.get("batch") != 8:
        errors.append("actual_context_or_batch")
    if actual.get("kv_k") != "Q8_0" or actual.get("kv_v") != "Q8_0":
        errors.append("actual_kv_type")
    if actual.get("flags") != flags:
        errors.append("actual_flags")
    evidence = row.get("evidence") or {}
    model_identity = (evidence.get("native_context") or {}).get("model_identity") or {}
    if identity:
        if evidence.get("source_git_sha") != identity.get("source_git_sha"):
            errors.append("sample_source_identity")
        if str(evidence.get("build_number")) != str(identity.get("build_number")):
            errors.append("sample_build_identity")
        expected_model = (identity.get("official_model") or {}).get("sha256")
        if model_identity.get("sha256") != expected_model:
            errors.append("sample_model_identity")
    if process_id and evidence.get("process_id") != process_id:
        errors.append("sample_process_identity")
    if not row.get("valid"):
        errors.extend(row.get("errors") or ["invalid_sample"])
    if flags == 320:
        delta = row.get("counter_delta") or []
        if len(delta) < 14:
            errors.append("candidate_counter_shape")
        else:
            if delta[10] <= 0:
                errors.append("candidate_route_not_observed")
            if delta[11] <= 0:
                errors.append("candidate_pipeline_not_ready")
            if delta[12] <= 0:
                errors.append("candidate_dispatch_not_enqueued")
            if delta[13] != 0:
                errors.append("candidate_pipeline_fallback")
    return errors

def evaluate(rows):
    if len(rows) != 4 or tuple((r.get("actual") or {}).get("flags") for r in rows) != ORDER:
        raise b.EvidenceError("QUICK_ABBA_ORDER_MISMATCH")
    errors = []
    for row, flags in zip(rows, ORDER):
        errors.extend(validate_candidate_sample(row, flags))
    if errors:
        raise b.EvidenceError("QUICK_SAMPLE_EVIDENCE:" + ",".join(errors))
    hashes = [r.get("output_sha256") for r in rows]
    prompt_hashes = [r.get("prompt_hash") for r in rows]
    if not all(hashes) or len(set(hashes)) != 1:
        raise b.EvidenceError("FIXED_INPUT_OUTPUT_PARITY_FAILED")
    if not all(prompt_hashes) or len(set(prompt_hashes)) != 1:
        raise b.EvidenceError("FIXED_INPUT_IDENTITY_MISMATCH")

    def med(indices, field):
        values = [float(rows[i][field]) for i in indices]
        if any(v <= 0 for v in values):
            raise b.EvidenceError("NONPOSITIVE_MEASUREMENT:" + field)
        return statistics.median(values)

    base_prefill = med((0, 3), "prefill_tps")
    candidate_prefill = med((1, 2), "prefill_tps")
    base_decode = med((0, 3), "decode_tps")
    candidate_decode = med((1, 2), "decode_tps")
    base_footprint = statistics.median(
        int((rows[i].get("memory") or {}).get("sampled_peak_footprint_bytes", 0)) for i in (0, 3))
    candidate_footprint = statistics.median(
        int((rows[i].get("memory") or {}).get("sampled_peak_footprint_bytes", 0)) for i in (1, 2))
    if base_footprint <= 0 or candidate_footprint <= 0:
        raise b.EvidenceError("MISSING_SAMPLED_FOOTPRINT")

    def pair_drift(indices, field):
        a, c = (float(rows[i][field]) for i in indices)
        center = max(statistics.median((a, c)), 1e-9)
        return abs(a - c) / center * 100.0

    drift = max(pair_drift((0, 3), "prefill_tps"), pair_drift((1, 2), "prefill_tps"))
    gain = (candidate_prefill / base_prefill - 1.0) * 100.0
    decode_change = (candidate_decode / base_decode - 1.0) * 100.0
    memory_delta = candidate_footprint - base_footprint
    thermal = max(int((r.get("memory") or {}).get("max_thermal_state", 0)) for r in rows)
    safe_gain = gain > drift + 3.0
    no_material_decode_regression = decode_change >= -5.0
    no_memory_regression = memory_delta <= MAX_MEMORY_DELTA
    no_thermal_regression = thermal < 3
    return {
        "status": "QUICK_PASS" if all((safe_gain, no_material_decode_regression,
                                       no_memory_regression, no_thermal_regression)) else "NO_SAFE_WIN",
        "quick_only": True,
        "prefill_gain_pct": gain,
        "observed_pair_drift_pct": drift,
        "required_gain_pct": drift + 3.0,
        "decode_change_pct": decode_change,
        "sampled_peak_footprint_delta_bytes": memory_delta,
        "max_thermal_state": thermal,
        "output_sha256": hashes[0],
        "prompt_hash": prompt_hashes[0],
        "candidate_route": "observed",
        "candidate_fallbacks": 0,
        "statistical_scope": "one short four-sample ABBA screen; follow-up required before any certification",
    }

def save_bundle(directory, report):
    b.dump(directory / "report.json", q.safe(report))
    summary = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    (directory / "RESULT_CN.md").write_text(
        "# Build127 Q8 固定配置 Quick 筛选\n\n"
        f"状态：{report.get('status')}\n\n"
        "本结果仅为四请求短 ABBA Quick 筛选，不代表 Full 认证或 M5 长期稳定认证。"
        "生产默认未改；仅在实际 Q8_0、flags 320、r1_8 路由和零 fallback 被观测时才计入候选样本。\n",
        encoding="utf-8")
    (directory / "summary.json").write_text(summary, encoding="utf-8")
    files = [p for p in sorted(directory.rglob("*")) if p.is_file() and
             p.name not in ("MANIFEST_SHA256.json", "results.zip", "results.zip.sha256") and
             not p.name.endswith(".tmp")]
    checks = {p.relative_to(directory).as_posix(): b.digest(p.read_bytes()) for p in files}
    b.dump(directory / "MANIFEST_SHA256.json", checks)
    files.append(directory / "MANIFEST_SHA256.json")
    archive = directory / "results.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(directory).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise b.EvidenceError("RESULT_ZIP_CORRUPT")
        for name, digest in checks.items():
            if b.digest(z.read(name)) != digest:
                raise b.EvidenceError("RESULT_HASH_MISMATCH")
    (directory / "results.zip.sha256").write_text(
        b.digest(archive.read_bytes()) + "  results.zip\n", encoding="utf-8")

class Q8MetalClient(q.Q8Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quick_deadline = None
        self.quick_cleanup = False
    def request(self, command, body=None, **kwargs):
        if self.quick_deadline and not self.quick_cleanup:
            remaining = self.quick_deadline - time.monotonic()
            if remaining <= 0:
                raise b.EvidenceError("QUICK_SCREEN_TOTAL_DEADLINE")
            requested = kwargs.get("timeout", REQUEST_DEADLINE_S)
            kwargs["timeout"] = max(1, min(float(requested), int(remaining)))
        if command == "run" and body and body.get("stage") == "capacity":
            raise b.EvidenceError("CAPACITY_PREFILL_NOT_ALLOWED_IN_QUICK")
        return super().request(command, body, **kwargs)

class Q8MetalRun(q.Q8Run):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context_ids_by_flags = {}

    @staticmethod
    def config(flags=64, context=16384, batch=8, kv="Q8_0"):
        return config(flags, context, batch, kv)

    def switch(self, candidate):
        previous = self.current
        super().switch(candidate)
        if previous != candidate:
            caps = self.client.request("capabilities", timeout=30)
            native = (caps.get("evidence") or {}).get("native_context") or {}
            errors = q.validate_native(native)
            if errors:
                raise b.EvidenceError("SWITCHED_Q8_CONTEXT_INVALID:" + ",".join(errors))
            context_id = native.get("context_id")
            if not isinstance(context_id, str) or not context_id:
                raise b.EvidenceError("SWITCHED_Q8_CONTEXT_ID_MISSING")
            if self.creation_id and context_id == self.creation_id:
                raise b.EvidenceError("CONTEXT_NOT_RECREATED_FOR_CONFIG")
            self.creation_id = context_id
            self.context_ids_by_flags[str(candidate["flags"])] = context_id

def snapshot(client, directory, name, path="capabilities"):
    try:
        result = client.request(path, timeout=30)
    except (b.APIError, b.EvidenceError, b.UncertainRequest) as error:
        result = {"unavailable": type(error).__name__, "reason": str(error)}
    b.dump(directory / (name + ".json"), q.safe(result))
    return result

def validate_device_preflight(identity, capabilities):
    errors = []
    evidence = capabilities.get("evidence") or {}
    native = evidence.get("native_context") or {}
    if evidence.get("source_git_sha") != identity.get("source_git_sha"):
        errors.append("source_git_sha")
    if str(evidence.get("build_number")) != str(identity.get("build_number")):
        errors.append("build_number")
    if capabilities.get("hardware", {}).get("eligible") is not True:
        errors.append("eligible_m5_device")
    errors.extend(q.validate_native(native, production=True))
    expected_sha = (identity.get("official_model") or {}).get("sha256")
    if (native.get("model_identity") or {}).get("sha256") != expected_sha:
        errors.append("model_sha256")
    if capabilities.get("q8_prior_interrupted"):
        errors.append("q8_interrupted_quarantine")
    return errors

def ordinary_api_check(client, identity, directory, forbidden_context_ids=()):
    health = client.request("/health", timeout=10)
    body = {"model": health["model"], "messages": [
        {"role": "system", "content": b.SYSTEM},
        {"role": "user", "content": "Return exactly the word BONSAI."}],
        "temperature": 0, "seed": 1234, "max_tokens": 32, "stream": False}
    forbidden_context_ids = {value for value in forbidden_context_ids if isinstance(value, str) and value}
    restored_context_id = None
    for index in range(2):
        b.dump(directory / f"ordinary-{index}-request.json", body)
        result = client.request("/v1/chat/completions", body, timeout=REQUEST_DEADLINE_S)
        b.dump(directory / f"ordinary-{index}-result.json", q.safe(result))
        if not result.get("choices") or not result.get("usage", {}).get("completion_tokens", 0):
            raise b.EvidenceError("ORDINARY_API_EMPTY_OUTPUT")
        caps = client.request("capabilities", timeout=30)
        b.dump(directory / f"ordinary-{index}-capabilities.json", q.safe(caps))
        evidence = caps.get("evidence") or {}
        native = evidence.get("native_context") or {}
        errors = q.validate_native(native, production=True)
        context_id = native.get("context_id")
        if errors or not isinstance(context_id, str) or not context_id:
            raise b.EvidenceError("ORDINARY_API_Q8_CONTEXT_INVALID:" + ",".join(errors))
        if context_id in forbidden_context_ids:
            raise b.EvidenceError("ORDINARY_API_CONTEXT_NOT_RECREATED")
        if restored_context_id is not None and context_id != restored_context_id:
            raise b.EvidenceError("ORDINARY_API_CONTEXT_CHANGED_BETWEEN_REQUESTS")
        restored_context_id = context_id
        if evidence.get("source_git_sha") != identity["source_git_sha"]:
            raise b.EvidenceError("ORDINARY_API_SOURCE_CHANGED")
        if (native.get("model_identity") or {}).get("sha256") != identity["official_model"]["sha256"]:
            raise b.EvidenceError("ORDINARY_API_MODEL_CHANGED")
    return restored_context_id

def run_screen(client, identity, directory):
    directory.mkdir(parents=True, exist_ok=False)
    runner = Q8MetalRun(client, identity, directory)
    client.evidence_directory = directory
    report = {
        "schema": "bonsai-build127-q8-metal-b8-quick-v1",
        "status": "BLOCKED",
        "mode": "quick",
        "device_validation": "CONNECTED_M5_QUICK_ONLY",
        "configuration": {"baseline": BASELINE, "candidate": CANDIDATE, "order": ORDER},
        "fixed_runtime": {"model_sha256": identity["official_model"]["sha256"],
            "context": 16384, "batch": 8, "ubatch": 8, "kv_k": "Q8_0", "kv_v": "Q8_0",
            "gpu_layers": 56, "threads": 6, "threads_batch": 6, "mmap": True,
            "flash_attention": True, "sequence_max": 1, "kv_reuse": False,
            "cpu_flags_both_arms": 64, "metal_candidate_bit": 256},
        "production_default": "UNCHANGED",
        "samples": [],
        "errors": [],
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "entry_capabilities",
    }
    client.quick_deadline = time.monotonic() + TOTAL_DEADLINE_S
    try:
        caps = client.request("capabilities", timeout=30)
        q.b.dump(directory / "entry-capabilities.json", q.safe(caps))
        report["initial_process_id"] = (caps.get("evidence") or {}).get("process_id")
        report["identity"] = identity
        report["phase"] = "prepare_q8_baseline_context"
        runner.prepare()
        report["initial_q8_context_id"] = runner.creation_id
        report["phase"] = "calibrate_fixed_prompt"
        prompt, target = runner.fit_prompt(128)
        rows = []
        for index, flags in enumerate(ORDER):
            if time.monotonic() >= client.quick_deadline:
                raise b.EvidenceError("QUICK_SCREEN_TOTAL_DEADLINE")
            report["phase"] = f"abba_{index + 1}_flags_{flags}"
            row = runner.run(config(flags), prompt, target,
                f"build127-q8-metal-b8:{index}:{uuid.uuid4()}",
                "quick_probe", max_tokens=32)
            # Exclude generated text from the immutable summary; raw response remains preserved by Q8Run.
            row.pop("text", None)
            errors = validate_candidate_sample(row, flags, identity, runner.process)
            if errors:
                raise b.EvidenceError("QUICK_SAMPLE_EVIDENCE:" + ",".join(errors))
            if row.get("memory"):
                row["sampled_peak_footprint_bytes"] = row["memory"].get("sampled_peak_footprint_bytes")
            rows.append(row)
            report["samples"].append(b.scrub(row))
        report["context_ids_by_flags"] = dict(runner.context_ids_by_flags)
        report["phase"] = "compare_abba_samples"
        report["measurement"] = evaluate(rows)
        report["status"] = report["measurement"]["status"]
    except BaseException as error:
        client.preserve_interrupted = True
        report["failure_stage"] = report.get("phase", "unknown")
        report["status"] = "FAIL"
        report["errors"].append({"code": str(error) if isinstance(error, (b.APIError, b.EvidenceError, b.UncertainRequest)) else type(error).__name__})
        snapshot(client, directory, "failure-capabilities")
    finally:
        report["phase"] = "restore_production_context"
        client.quick_cleanup = True
        runner.restore()
        report["restoration"] = runner.report.get("restoration", "NOT_CONFIRMED")
        if report["restoration"] == "RESTORED" and runner.original_runtime:
            try:
                report["phase"] = "post_restore_ordinary_api"
                forbidden_ids = {runner.original_runtime.get("context_id"), *runner.context_ids_by_flags.values()}
                report["restored_context_id"] = ordinary_api_check(client, identity, directory, forbidden_ids)
                report["ordinary_api"] = "PASS_TWO_REQUESTS"
            except (b.APIError, b.EvidenceError, b.UncertainRequest) as error:
                report["ordinary_api"] = "FAIL"
                report.setdefault("failure_stage", "post_restore_ordinary_api")
                report["errors"].append({"code": str(error)})
                report["status"] = "FAIL"
        else:
            report["ordinary_api"] = "NOT_RUN_RESTORE_UNCONFIRMED"
        snapshot(client, directory, "after-restore-capabilities")
        snapshot(client, directory, "profiling", "/debug/profiling")
        snapshot(client, directory, "crashes", "/debug/crashes")
        report["phase"] = "final_evidence_snapshot"
        report["runner_report"] = q.safe(runner.report)
        report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_bundle(directory, report)
    if report["status"] == "QUICK_PASS" and report["restoration"] != "RESTORED":
        report["status"] = "BLOCKED"
        report["errors"].append({"code": "RESTORE_NOT_CONFIRMED"})
        save_bundle(directory, report)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"mode": "quick", "configuration": {"baseline": BASELINE,
            "candidate": CANDIDATE, "order": ORDER}, "total_deadline_s": TOTAL_DEADLINE_S,
            "request_deadline_s": REQUEST_DEADLINE_S, "production_default": "UNCHANGED",
            "full_certification": "NOT_RUN"}, sort_keys=True))
        return 0
    root = b.ROOT
    output = args.output or root / "RESULTS" / (
        "Build127-Q8-Metal-B8-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    client = None
    report = {"status": "BLOCKED", "mode": "quick", "device_validation": "NOT_RUN",
              "production_default": "UNCHANGED", "errors": []}
    try:
        identity = json.loads((root / "TestKitIdentity.json").read_text(encoding="utf-8-sig"))
        q.verify_kit(identity)
        url = args.url or b.discover()
        health = b.Client(url).request("/health", timeout=10)
        key = os.environ.get("BONSAI_API_KEY", "")
        if health.get("auth_required") and not key:
            key = getpass.getpass("API key (kept in memory): ")
        client = Q8MetalClient(url, key)
        before = snapshot(client, output, "before")
        preflight_errors = validate_device_preflight(identity, before)
        if preflight_errors:
            raise b.EvidenceError("DEVICE_CANDIDATE_PREFLIGHT:" + ",".join(preflight_errors))
        print("请确认：Build127 App 已冷启动，模型 SHA 与 TestKit 一致，API 正在运行，配置为16K + 固定Q8_0。")
        if input("确认请键入 COLD；否则保留 BLOCKED：").strip() != "COLD":
            raise b.EvidenceError("COLD_LAUNCH_NOT_CONFIRMED")
        report = run_screen(client, identity, output / "screen")
        report["initial_process_id"] = (before.get("evidence") or {}).get("process_id")
        report["initial_process"] = report["initial_process_id"]
        report["cold_launch_operator_confirmed"] = True
        save_bundle(output, report)
    except BaseException as error:
        report["failure_stage"] = "preflight"
        report["errors"].append({"code": str(error) if isinstance(error, (b.APIError, b.EvidenceError, b.UncertainRequest)) else type(error).__name__})
        q.b.dump(output / "blocked.json", q.safe(report))
        save_bundle(output, report)
    print(json.dumps({"status": report.get("status"), "device_validation": report.get("device_validation"),
        "output": str(output), "production_default": "UNCHANGED"}, ensure_ascii=False))
    return 0 if report.get("status") in ("QUICK_PASS", "NO_SAFE_WIN") and report.get("restoration") == "RESTORED" else 1

if __name__ == "__main__":
    raise SystemExit(main())