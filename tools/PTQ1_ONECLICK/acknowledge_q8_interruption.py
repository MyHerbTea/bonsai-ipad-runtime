"""Archive-first, explicit acknowledgement of a preserved Build126 Q8 interruption."""
import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path
import uuid
import zipfile
import ptq1_oneclick as b
import kv_baseline as q

TOKEN = "ACKNOWLEDGE PRESERVED FAILED Q8"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def matches(path, expected):
    return isinstance(expected, str) and sha(path) == expected.lower()

def verify_failure_archive(directory, identity):
    directory = Path(directory).resolve()
    report_path = directory / "report.json"
    correction_path = directory / "OPERATOR_CORRECTION.json"
    zip_path = directory / "results.zip"
    manifest_path = directory / "MANIFEST_SHA256.json"
    failure_path = directory / "failure-capabilities.json"
    after_path = directory / "POST_RESTART_OBSERVATION.json"
    phase_path = directory / "before-restart" / "phase-report.json"
    if not all(p.is_file() for p in (report_path, correction_path, zip_path, manifest_path, failure_path, after_path, phase_path)):
        raise b.EvidenceError("PRESERVED_FAILURE_ARCHIVE_INCOMPLETE")
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    correction = json.loads(correction_path.read_text(encoding="utf-8-sig"))
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    after = json.loads(after_path.read_text(encoding="utf-8-sig"))
    phase = json.loads(phase_path.read_text(encoding="utf-8-sig"))
    if report.get("status") != "FAIL" or report.get("mode") != "quick":
        raise b.EvidenceError("PRESERVED_FAILURE_NOT_QUICK_FAIL")
    if not any(item.get("code") == "REQUEST_OUTCOME_UNKNOWN" for item in report.get("errors", [])):
        raise b.EvidenceError("PRESERVED_FAILURE_OUTCOME_MISMATCH")
    if phase.get("status") != "INCOMPLETE" or len(phase.get("samples", [])) != 1 or phase.get("restoration") != "FAILED_OR_UNREACHABLE_RELAUNCH_APP_ONCE":
        raise b.EvidenceError("PRESERVED_PHASE_EVIDENCE_MISMATCH")
    report_identity = report.get("identity", {})
    if report_identity.get("build_number") != identity.get("build_number") or (report_identity.get("official_model") or {}).get("sha256") != (identity.get("official_model") or {}).get("sha256"):
        raise b.EvidenceError("PRESERVED_FAILURE_MODEL_OR_BUILD_MISMATCH")
    if report.get("identity", {}).get("source_git_sha") not in ([identity.get("source_git_sha")] + identity.get("acknowledge_failure_source_shas", [])):
        raise b.EvidenceError("PRESERVED_FAILURE_SOURCE_MISMATCH")
    if correction.get("corrected_cold_start_confirmed") is not False:
        raise b.EvidenceError("OPERATOR_CORRECTION_REQUIRED")
    original_cold = correction.get("original_report_field") or {}
    if original_cold.get("cold_launch_operator_confirmed") is not True or original_cold.get("validity") != "invalidated_by_operator_correction":
        raise b.EvidenceError("COLD_START_CORRECTION_LINK_MISSING")
    if correction.get("request_outcome") != "REQUEST_OUTCOME_UNKNOWN":
        raise b.EvidenceError("PRESERVED_FAILURE_OUTCOME_MISMATCH")
    hashes = correction.get("historical_evidence") or {}
    if not matches(zip_path, hashes.get("results_zip_sha256")) or not matches(report_path, hashes.get("report_json_sha256")):
        raise b.EvidenceError("PRESERVED_FAILURE_HASH_MISMATCH")
    if not matches(failure_path, hashes.get("failure_capabilities_sha256")) or not matches(after_path, hashes.get("post_restart_observation_sha256")):
        raise b.EvidenceError("PRESERVED_DIAGNOSTIC_HASH_MISMATCH")
    if after.get("process_id") != (failure.get("evidence") or {}).get("process_id") or after.get("process_id") == report.get("initial_process") or after.get("source_git_sha") != report_identity.get("source_git_sha") or after.get("build_number") != identity.get("build_number"):
        raise b.EvidenceError("PRESERVED_RESTART_PROCESS_MISMATCH")
    failure_evidence = failure.get("evidence") or {}; failure_native = failure_evidence.get("native_context") or {}
    after_native = after.get("native_context") or after
    sample = (phase.get("samples") or [{}])[0]
    sample_native = (sample.get("evidence") or {}).get("native_context") or {}
    sample_actual = sample.get("actual") or {}
    for actual in (failure_native, after_native, sample_native, sample_actual):
        if actual.get("context") != 16384 or actual.get("kv_k") != "Q8_0" or actual.get("kv_v") != "Q8_0":
            raise b.EvidenceError("PRESERVED_Q8_RUNTIME_EVIDENCE_MISMATCH")
    if sample.get("valid") is not True or sample_actual.get("batch") != 8 or sample_actual.get("ubatch") != 8:
        raise b.EvidenceError("PRESERVED_Q8_SAMPLE_INVALID")
    if failure_evidence.get("source_git_sha") != report_identity.get("source_git_sha") or failure_evidence.get("build_number") != identity.get("build_number"):
        raise b.EvidenceError("PRESERVED_RESTART_IDENTITY_MISMATCH")
    if any(actual.get("kv_observation_source") != "allocated_native_kv_tensors" for actual in (failure_native, after_native, sample_native)):
        raise b.EvidenceError("PRESERVED_KV_ALLOCATION_SOURCE_MISMATCH")
    sample_evidence = sample.get("evidence") or {}
    if sample_evidence.get("source_git_sha") != report_identity.get("source_git_sha") or sample_evidence.get("build_number") != identity.get("build_number"):
        raise b.EvidenceError("PRESERVED_SAMPLE_IDENTITY_MISMATCH")
    if (sample_native.get("model_identity") or {}).get("sha256") != identity.get("official_model", {}).get("sha256"):
        raise b.EvidenceError("PRESERVED_SAMPLE_MODEL_MISMATCH")
    marker = failure.get("q8_prior_interrupted")
    if not isinstance(marker, dict) or canonical(marker) != canonical(after.get("q8_prior_interrupted")):
        raise b.EvidenceError("Q8_MARKER_ARCHIVE_MISMATCH")
    if marker.get("context") != 16384 or marker.get("batch") != 8 or marker.get("ubatch") != 8 \
        or marker.get("kv_k") != "Q8_0" or marker.get("kv_v") != "Q8_0" or marker.get("flags") != 64:
        raise b.EvidenceError("Q8_MARKER_SHAPE_MISMATCH")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    for name, digest in manifest.items():
        p = (directory / name).resolve()
        if directory not in p.parents or not p.is_file() or sha(p) != digest:
            raise b.EvidenceError("FAILURE_DIRECTORY_MANIFEST_MISMATCH")
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip():
            raise b.EvidenceError("PRESERVED_FAILURE_ZIP_CORRUPT")
        if hashlib.sha256(archive.read("report.json")).hexdigest() != str(hashes.get("report_json_sha256", "")).lower():
            raise b.EvidenceError("ARCHIVED_REPORT_HASH_MISMATCH")
        if canonical(json.loads(archive.read("failure-capabilities.json"))) != canonical(failure):
            raise b.EvidenceError("ARCHIVED_FAILURE_CAPABILITIES_MISMATCH")
    zip_sha = sha(zip_path)
    expected_zip_sha = (directory / "results.zip.sha256").read_text(encoding="utf-8-sig").split()[0]
    if zip_sha != expected_zip_sha.lower():
        raise b.EvidenceError("PRESERVED_FAILURE_ZIP_SHA_MISMATCH")
    return {"directory": directory, "report": report, "correction": correction,
        "failure": failure, "after": after, "marker": marker, "zip_sha256": zip_sha,
        "report_sha256": sha(report_path), "correction_sha256": sha(correction_path),
        "failure_capabilities_sha256": sha(failure_path), "post_restart_sha256": sha(after_path)}

def verify_live(caps, identity, archived):
    ev = caps.get("evidence") or {}; native = ev.get("native_context") or {}
    hardware = caps.get("hardware") or {}; state = caps.get("state") or {}
    errors = []
    if ev.get("build_number") != identity.get("build_number"): errors.append("build")
    if ev.get("source_git_sha") != identity.get("source_git_sha"): errors.append("source")
    if ev.get("process_id") in (archived["report"].get("initial_process"), archived["after"].get("process_id")): errors.append("process_not_relaunched")
    if (native.get("model_identity") or {}).get("sha256") != identity.get("official_model", {}).get("sha256"): errors.append("model")
    if hardware.get("eligible") is not True or hardware.get("machine") != "iPad17,1" or hardware.get("physical_memory_bytes") != 12084002816: errors.append("hardware")
    expected = {"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
        "kv_policy":"Q8_0","kv_unified":True,"kv_observation_source":"allocated_native_kv_tensors",
        "gpu_layers":56,"threads":6,"threads_batch":6,"mmap":True,"flash_attention":True,
        "sequence_max":1,"offload_kqv":True,"op_offload":True,"text_kv_reuse":False,
        "metal_tensor_disabled":True,"swa_full":False}
    if any(native.get(key) != value for key,value in expected.items()): errors.append("actual_q8_runtime")
    if caps.get("actual") is not None: errors.append("benchmark_lease_active")
    if caps.get("q8_prior_interrupted") != archived["marker"]: errors.append("q8_marker_changed")
    if state.get("active") or state.get("running") or state.get("ordinary_requests"): errors.append("runtime_busy")
    if errors: raise b.EvidenceError("LIVE_Q8_ACK_PREFLIGHT_MISMATCH:" + ",".join(errors))
    return native, ev

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    identity = json.loads((b.ROOT / "TestKitIdentity.json").read_text(encoding="utf-8-sig"))
    q.verify_kit(identity)
    results_path = args.results or Path(input("包含 FAIL 结果包与 OPERATOR_CORRECTION.json 的目录：").strip())
    archived = verify_failure_archive(results_path, identity)
    output = args.output or b.ROOT / "ACKNOWLEDGEMENTS" / ("Q8-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema":"bonsai-build126-q8-ack-v1", "status":"BLOCKED", "inference_launched":False,
        "historical_results_preserved":True, "errors":[], "archive_sha256":archived["zip_sha256"]}
    client = None
    try:
        url = args.url or b.discover()
        health = b.Client(url).request("/health", timeout=10)
        key = os.environ.get("BONSAI_API_KEY", "")
        if health.get("auth_required") and not key: key = getpass.getpass("API Key（仅内存使用）：")
        client = b.Client(url, key)
        caps = client.request("capabilities", timeout=30)
        native, ev = verify_live(caps, identity, archived)
        b.dump(output / "before.json", q.safe(caps))
        report.update({"device_validation":"CONNECTED_M5_READ_ONLY_PREFLIGHT", "process_id":ev.get("process_id"),
            "context_id":native.get("context_id"), "marker":archived["marker"],
            "failure_archive_name":archived["directory"].name, "failure_report_sha256":archived["report_sha256"],
            "correction_sha256":archived["correction_sha256"]})
        print("已校验失败 ZIP、报告、更正记录、隔离标记与当前 M5/Build126/Q8 运行时。")
        print("确认后只归档并解除 Q8 重试隔离；不会发送推理请求，也不会删除/修改原失败结果包。")
        if input("输入 " + TOKEN + " 才继续：").strip() != TOKEN:
            raise b.EvidenceError("OPERATOR_ACKNOWLEDGEMENT_NOT_CONFIRMED")
        body = {"reason":"operator_reviewed_preserved_failed_result",
            "expected_source_git_sha":identity["source_git_sha"], "failure_source_git_sha":archived["report"]["identity"]["source_git_sha"], "expected_process_id":ev["process_id"],
            "expected_interruption":archived["marker"], "results_zip_sha256":archived["zip_sha256"],
            "report_sha256":archived["report_sha256"], "correction_sha256":archived["correction_sha256"]}
        b.dump(output / "acknowledgement-request.json", body)
        response = client.request("/debug/benchmark/acknowledge_q8_interruption", body, timeout=30)
        b.dump(output / "acknowledgement-response.json", q.safe(response))
        after = client.request("capabilities", timeout=30)
        b.dump(output / "after.json", q.safe(after))
        ev_after = after.get("evidence") or {}; native_after = ev_after.get("native_context") or {}
        if response.get("status") != "acknowledged_preserved_q8_interruption" or not response.get("audit_readback_verified") or not response.get("audit_snapshot_id"):
            raise b.EvidenceError("Q8_ACK_AUDIT_NOT_VERIFIED")
        if after.get("q8_prior_interrupted") is not None: raise b.EvidenceError("Q8_QUARANTINE_NOT_CLEARED")
        if after.get("prior_interrupted") != caps.get("prior_interrupted") or after.get("quick_prior_interrupted") != caps.get("quick_prior_interrupted"):
            raise b.EvidenceError("OTHER_QUARANTINE_MARKERS_CHANGED")
        if ev_after.get("source_git_sha") != identity["source_git_sha"] or ev_after.get("process_id") != ev.get("process_id"):
            raise b.EvidenceError("RUNTIME_CHANGED_DURING_ACKNOWLEDGEMENT")
        if native_after.get("kv_k") != "Q8_0" or native_after.get("kv_v") != "Q8_0" or native_after.get("context") != 16384:
            raise b.EvidenceError("RUNTIME_CHANGED_DURING_ACKNOWLEDGEMENT")
        report.update({"status":"ACKNOWLEDGED", "audit_snapshot_id":response["audit_snapshot_id"],
            "audit_readback_verified":True, "device_validation":"CONNECTED_M5_ACK_ONLY",
            "q8_quarantine_cleared":True, "historical_results_preserved":True})
    except (b.APIError,b.EvidenceError,b.UncertainRequest,ValueError,KeyError,OSError,EOFError) as error:
        code = str(error) if isinstance(error,(b.APIError,b.EvidenceError,b.UncertainRequest)) else type(error).__name__
        report["errors"].append({"code":code})
    finally:
        report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        b.dump(output / "report.json", q.safe(report))
        files=[p for p in sorted(output.rglob("*")) if p.is_file() and p.name not in ("MANIFEST_SHA256.json","acknowledgement.zip","acknowledgement.zip.sha256")]
        manifest={p.relative_to(output).as_posix():sha(p) for p in files}
        b.dump(output / "MANIFEST_SHA256.json", manifest)
        files.append(output / "MANIFEST_SHA256.json")
        with zipfile.ZipFile(output / "acknowledgement.zip","w",zipfile.ZIP_DEFLATED) as archive:
            for p in files: archive.write(p,p.relative_to(output).as_posix())
        (output / "acknowledgement.zip.sha256").write_text(sha(output / "acknowledgement.zip") + "  acknowledgement.zip\n",encoding="ascii")
        print("ACK 状态：",report["status"],"；审计包：",output / "acknowledgement.zip",flush=True)
    return 0 if report.get("status") == "ACKNOWLEDGED" else 2

if __name__ == "__main__": raise SystemExit(main())
