import hashlib
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import acknowledge_q8_interruption as ack


FAILED_SOURCE = "2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158"
MODEL_SHA = "53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3"
USER_STATEMENT = "这个中断是用户发起的，原因是丧失了实际的使用性，600秒了prefill仅仅只完成了40%左右。"
MARKER_ID = "00000000-0000-4000-8000-000000000128"


def report():
    return {
        "status": "FAIL",
        "mode": "full",
        "configuration": {"context": 16384, "batch": 8, "kv": "Q8_0", "flags": 64},
        "identity": {
            "source_git_sha": FAILED_SOURCE,
            "build_number": "126",
            "official_model": {"sha256": MODEL_SHA},
        },
        "errors": [{"code": "KeyboardInterrupt"}],
    }


def correction():
    return {
        "schema": "bonsai-q8-operator-abort-correction-v1",
        "operator_initiated": True,
        "outcome": "OPERATOR_ABORTED_UNUSABLE_PREFILL",
        "elapsed_seconds_approx": 600,
        "prefill_progress_percent_approx": 40,
        "user_statement": USER_STATEMENT,
        "marker_interruption_id": MARKER_ID,
        "operator_acknowledgement_token": "ACKNOWLEDGE PRESERVED FAILED Q8",
        "historical_evidence": {
            "results_zip_sha256": "a" * 64,
            "report_json_sha256": "b" * 64,
            "failure_capabilities_sha256": "c" * 64,
            "phase_report_sha256": "d" * 64,
        },
    }


class FullOperatorAbortTests(unittest.TestCase):
    def test_full_archive_double_click_flow_prompts_for_the_separate_correction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = root / "preserved-failure"
            results.mkdir()
            (results / "report.json").write_text(json.dumps({"mode": "full"}), encoding="utf-8")
            correction_path = root / "Q8-Operator-Correction.json"
            identity = {"build_number": "128", "source_git_sha": "a" * 40,
                "official_model": {"sha256": MODEL_SHA}}
            (root / 'TestKitIdentity.json').write_text(json.dumps(identity), encoding='utf-8')
            with patch.object(ack.b, "ROOT", root), patch.object(ack.q, "verify_kit"), \
                 patch.object(ack, "verify_failure_archive", side_effect=RuntimeError("stop after path resolution")) as verify, \
                 patch.object(sys, "argv", ["acknowledge_q8_interruption.py", "--results", str(results)]), \
                 patch("builtins.input", return_value=str(correction_path)) as prompt:
                with self.assertRaisesRegex(RuntimeError, "stop after path resolution"):
                    ack.main()
            prompt.assert_called_once()
            self.assertIn("独立", prompt.call_args.args[0])
            verify.assert_called_once_with(results, identity, correction_path)
    def test_accepts_only_the_explicit_build126_full_q8_operator_abort(self):
        validated = ack.verify_operator_abort_correction(report(), correction())
        self.assertEqual(validated["outcome"], "OPERATOR_ABORTED_UNUSABLE_PREFILL")
        self.assertEqual(validated["failure_source_git_sha"], FAILED_SOURCE)

    def test_rejects_unrelated_or_incomplete_failure_and_correction(self):
        invalid_reports = [
            {**report(), "mode": "quick"},
            {**report(), "status": "PASS"},
            {**report(), "errors": [{"code": "OutOfMemory"}]},
            {**report(), "identity": {**report()["identity"], "source_git_sha": "f" * 40}},
            {**report(), "configuration": {**report()["configuration"], "kv": "Q4_0"}},
        ]
        for invalid in invalid_reports:
            with self.subTest(report=invalid):
                with self.assertRaises(Exception):
                    ack.verify_operator_abort_correction(invalid, correction())

        for key, value in (("operator_initiated", False), ("elapsed_seconds_approx", 599),
                           ("prefill_progress_percent_approx", 41), ("user_statement", ""),
                           ("marker_interruption_id", "wrong-marker"),
                           ("operator_acknowledgement_token", "")):
            with self.subTest(field=key):
                invalid = correction()
                invalid[key] = value
                with self.assertRaises(Exception):
                    ack.verify_operator_abort_correction(report(), invalid)

    def test_validates_full_archive_and_separate_correction_without_mutating_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            directory = base / "preserved-failure"
            phase_dir = directory / "before-restart"
            phase_dir.mkdir(parents=True)
            failure_process = "41ecee6c-28b0-4423-bc07-480ec09534af"
            initial_process = "34e2f3b9-19e7-4992-9fc6-4cb236b0f494"
            marker = {"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
                "flags":64,"flash_attention":True,"sequence_max":1,"kv_reuse":False,
                "interruption_id":"00000000-0000-4000-8000-000000000128"}
            full_report = report()
            full_report["initial_process"] = initial_process
            failure = {"q8_prior_interrupted":marker,"evidence":{"source_git_sha":FAILED_SOURCE,
                "build_number":"126","process_id":failure_process,
                "native_context":{"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
                    "kv_policy":"Q8_0","kv_observation_source":"allocated_native_kv_tensors",
                    "model_identity":{"sha256":MODEL_SHA}}},
                "state":{"active":False,"running":False,"ordinary_requests":0}}
            native = {"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0",
                "kv_observation_source":"allocated_native_kv_tensors",
                "model_identity":{"sha256":MODEL_SHA}}
            samples = [{"valid":True,"prompt_tokens":512,"generated_tokens":128,
                "actual":{"context":16384,"batch":8,"ubatch":8,"kv_k":"Q8_0","kv_v":"Q8_0","flags":64},
                "evidence":{"source_git_sha":FAILED_SOURCE,"build_number":"126","native_context":native}}
                for _ in range(4)]
            phase = {"status":"FAIL","restoration":"RESTORED","samples":samples}
            paths = {
                "report.json": full_report,
                "failure-capabilities.json": failure,
                "before-restart/phase-report.json": phase,
            }
            for relative, value in paths.items():
                destination = directory / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
            (directory / "samples.csv").write_text("request_id,stage\n", encoding="utf-8")
            manifest = {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(directory.rglob("*")) if path.is_file()}
            manifest_path = directory / "MANIFEST_SHA256.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
            zip_path = directory / "results.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for relative in (*manifest.keys(), "MANIFEST_SHA256.json"):
                    archive.write(directory / relative, relative)
            zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            (directory / "results.zip.sha256").write_text(zip_sha + "  results.zip\n", encoding="ascii")
            correction_record = correction()
            correction_record["historical_evidence"] = {
                "results_zip_sha256": zip_sha,
                "report_json_sha256": hashlib.sha256((directory / "report.json").read_bytes()).hexdigest(),
                "failure_capabilities_sha256": hashlib.sha256((directory / "failure-capabilities.json").read_bytes()).hexdigest(),
                "phase_report_sha256": hashlib.sha256((directory / "before-restart/phase-report.json").read_bytes()).hexdigest(),
            }
            correction_path = base / "operator-correction.json"
            correction_path.write_text(json.dumps(correction_record, sort_keys=True, indent=2), encoding="utf-8")
            identity = {"source_git_sha":"f" * 40,"build_number":"128",
                "official_model":{"sha256":MODEL_SHA}}
            before = {path.relative_to(directory).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.rglob("*") if path.is_file()}
            verified = ack.verify_failure_archive(directory, identity, correction_path)
            after = {path.relative_to(directory).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                for path in directory.rglob("*") if path.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(verified["marker"], marker)
            self.assertEqual(verified["correction"]["outcome"], "OPERATOR_ABORTED_UNUSABLE_PREFILL")


if __name__ == "__main__":
    unittest.main()
