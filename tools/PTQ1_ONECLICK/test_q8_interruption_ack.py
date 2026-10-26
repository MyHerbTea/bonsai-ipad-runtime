import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import acknowledge_q8_interruption as ack

SOURCE = "2d5b75430ac152da7b03c0e4f0edb18b1a9ac5f2"
MODEL = "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")

class Q8InterruptionAckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "failed"
        self.root.mkdir()
        marker = {"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
            "flags":64,"flash_attention":True,"sequence_max":1,"kv_reuse":False,
            "interruption_id":"83a07a86-b4b3-4514-b5da-10a74393cf0e"}
        self.marker = marker
        report = {"status":"FAIL","mode":"quick","cold_launch_operator_confirmed":True,"identity":{"build_number":"126","official_model":{"sha256":MODEL}},
            "initial_process":"1be59517-0313-458c-ae1a-f9076483696d",
            "identity":{"source_git_sha":SOURCE,"build_number":"126","build_number":"126","official_model":{"sha256":MODEL}},
            "errors":[{"code":"REQUEST_OUTCOME_UNKNOWN"}]}
        failure = {"q8_prior_interrupted":marker,"evidence":{"source_git_sha":SOURCE,"build_number":"126",
            "process_id":"ccd151ae-a58e-4ecd-addf-e453d504b497","native_context":{"context":16384,"kv_k":"Q8_0","kv_v":"Q8_0","kv_observation_source":"allocated_native_kv_tensors","model_identity":{"sha256":MODEL}}},
            "state":{"active":False,"running":False,"ordinary_requests":0}}
        after = {"source_git_sha":SOURCE,"build_number":"126","process_id":"ccd151ae-a58e-4ecd-addf-e453d504b497","q8_prior_interrupted":marker,"context":16384,"kv_k":"Q8_0","kv_v":"Q8_0","kv_observation_source":"allocated_native_kv_tensors"}
        write(self.root / "report.json", report)
        write(self.root / "failure-capabilities.json", failure)
        write(self.root / "POST_RESTART_OBSERVATION.json", after)
        write(self.root / "before-restart" / "phase-report.json", {"status":"INCOMPLETE","samples":[{"valid":True,"batch":8,"ubatch":8,"actual":{"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0"},"evidence":{"source_git_sha":SOURCE,"build_number":"126","native_context":{"context":16384,"kv_k":"Q8_0","kv_v":"Q8_0","kv_observation_source":"allocated_native_kv_tensors","model_identity":{"sha256":MODEL}}}}],"restoration":"FAILED_OR_UNREACHABLE_RELAUNCH_APP_ONCE"})
        manifest = {"before-restart/phase-report.json":digest(self.root / "before-restart" / "phase-report.json"),"report.json":digest(self.root / "report.json"),
            "failure-capabilities.json":digest(self.root / "failure-capabilities.json")}
        write(self.root / "MANIFEST_SHA256.json", manifest)
        with zipfile.ZipFile(self.root / "results.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("report.json", "failure-capabilities.json", "MANIFEST_SHA256.json", "before-restart/phase-report.json"):
                z.write(self.root / name, name)
        (self.root / "results.zip.sha256").write_text(digest(self.root / "results.zip") + "  results.zip\n", encoding="ascii")
        correction = {"corrected_cold_start_confirmed":False,"original_report_field":{"cold_launch_operator_confirmed":True,"validity":"invalidated_by_operator_correction"},"request_outcome":"REQUEST_OUTCOME_UNKNOWN",
            "historical_evidence":{"results_zip_sha256":digest(self.root / "results.zip"),
                "report_json_sha256":digest(self.root / "report.json"),
                "failure_capabilities_sha256":digest(self.root / "failure-capabilities.json"),
                "post_restart_observation_sha256":digest(self.root / "POST_RESTART_OBSERVATION.json")}}
        write(self.root / "OPERATOR_CORRECTION.json", correction)
        self.identity = {"source_git_sha":"f"*40,"acknowledge_failure_source_shas":[SOURCE],"build_number":"126","official_model":{"sha256":MODEL}}

    def tearDown(self):
        self.temp.cleanup()

    def test_verifies_preserved_failure_archive_and_marker(self):
        verified = ack.verify_failure_archive(self.root, self.identity)
        self.assertEqual(verified["marker"], self.marker)
        self.assertEqual(verified["report"]["status"], "FAIL")

    def test_rejects_modified_raw_failure_report(self):
        path = self.root / "report.json"
        report = json.loads(path.read_text())
        report["status"] = "PASS"
        write(path, report)
        with self.assertRaises(Exception):
            ack.verify_failure_archive(self.root, self.identity)

    def test_rejects_source_mismatch(self):
        with self.assertRaises(Exception):
            ack.verify_failure_archive(self.root, {**self.identity,"source_git_sha":"e"*40,"acknowledge_failure_source_shas":[]})

    def test_live_preflight_requires_current_q8_marker_and_m5_identity(self):
        native = {"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
            "kv_policy":"Q8_0","kv_unified":True,"kv_observation_source":"allocated_native_kv_tensors",
            "gpu_layers":56,"threads":6,"threads_batch":6,"mmap":True,"flash_attention":True,
            "sequence_max":1,"offload_kqv":True,"op_offload":True,"text_kv_reuse":False,
            "metal_tensor_disabled":True,"swa_full":False,"model_identity":{"sha256":MODEL}}
        archived = {"marker":self.marker,"after":{"process_id":"ccd151ae-a58e-4ecd-addf-e453d504b497","native_context":{"context":16384,"kv_k":"Q8_0","kv_v":"Q8_0","kv_observation_source":"allocated_native_kv_tensors","model_identity":{"sha256":MODEL}}},
            "report":{"initial_process":"1be59517-0313-458c-ae1a-f9076483696d"}}
        caps = {"evidence":{"build_number":"126","source_git_sha":self.identity["source_git_sha"],
            "process_id":"ee95d2a0-80b3-479b-89b8-2e09a712de31","native_context":native},
            "hardware":{"eligible":True,"machine":"iPad17,1","physical_memory_bytes":12084002816},"actual":None,
            "q8_prior_interrupted":self.marker,"state":{"active":False,"running":False,"ordinary_requests":0}}
        self.assertEqual(ack.verify_live(caps,self.identity,archived)[0],native)
        bad = {**caps,"q8_prior_interrupted":None}
        with self.assertRaises(Exception): ack.verify_live(bad,self.identity,archived)

    def test_acknowledgement_is_explicit_and_has_no_inference_route(self):
        source = Path(ack.__file__).read_text(encoding="utf-8")
        self.assertLess(source.index('if input("输入 " + TOKEN'),
                        source.index('client.request("/debug/benchmark/acknowledge_q8_interruption"'))
        self.assertIn('ACKNOWLEDGE PRESERVED FAILED Q8',source)
        self.assertNotIn('/v1/chat/completions',source)

if __name__ == "__main__":
    unittest.main()
