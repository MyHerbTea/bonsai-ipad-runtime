import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load_module("build129_reasoning_package", ROOT / "tools/package_build129_reasoning.py")
smoke = load_module(
    "build129_reasoning_smoke",
    ROOT / "tools/BUILD129_REASONING_TESTKIT/build129_reasoning_api_smoke.py",
)


class Build129ReasoningPackageTests(unittest.TestCase):
    def test_api_base_url_is_normalized_without_embedded_secrets(self):
        self.assertEqual(smoke.Client("http://192.168.1.92:8080/v1/").base_url, "http://192.168.1.92:8080")
        with self.assertRaises(ValueError):
            smoke.Client("http://user:secret@192.168.1.92:8080/?api_key=secret")

    def test_smoke_checks_mode_metadata_and_sends_omitted_and_explicit_values(self):
        class FakeClient:
            def __init__(self):
                self.payloads = []
                self.trace_events = []

            def request(self, path, payload=None, timeout=30, additional_headers=None):
                if path == "/health":
                    return 200, {
                        "status": "ok", "default_reasoning_effort": "medium",
                        "capabilities": {"reasoning": True},
                    }
                if path == "/v1/models":
                    return 200, {"data": [{
                        "id": "bonsai-test", "default_reasoning_effort": "medium",
                        "capabilities": {"reasoning": True},
                        "supported_parameters": ["reasoning_effort"],
                    }]}
                if path == "/v1/chat/completions":
                    self.payloads.append(payload)
                    self.trace_events.append({
                        "request_id": additional_headers["X-Bonsai-Request-ID"],
                        "stage": "inference_finished",
                        "reasoning_effort": payload.get("reasoning_effort", "medium"),
                    })
                    return 200, {"choices": [{"message": {"content": "OK"}}]}
                if path == "/debug/request-trace":
                    return 200, {"events": list(self.trace_events)}
                raise AssertionError(path)

        client = FakeClient()
        report = {"raw": {}, "requests": []}
        self.assertEqual(smoke.check_metadata(client, "medium", report, "on"), "bonsai-test")
        smoke.run_completion(client, "bonsai-test", "default", None, "medium", report)
        smoke.run_completion(client, "bonsai-test", "override", "none", "none", report)
        self.assertNotIn("reasoning_effort", client.payloads[0])
        self.assertEqual(client.payloads[1]["reasoning_effort"], "none")
        self.assertEqual(
            [item["observed_effective_reasoning_effort"] for item in report["requests"]],
            ["medium", "none"],
        )
        self.assertEqual(len(report["requests"]), 2)

    def test_package_contains_one_ipa_and_separate_identity_checked_testkit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app"
            app.mkdir(parents=True)
            (app / "BonsaiLab").write_bytes(b"synthetic app executable")
            (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleVersion": "129"}))
            (root / "build/delivery").mkdir(parents=True)
            (root / "build/Bonsai-Build129-Symbols.zip").write_bytes(b"symbols")
            for name in ("CI_TESTS.txt", "BUILD129_POLICY.txt", "BUILD129_TESTS.txt", "build.log", "SYMBOL_IDENTITY.json"):
                path = root / "build" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic CI evidence\n", encoding="utf-8")
            for relative in (
                "docs/superpowers/specs/2026-10-27-api-reasoning-effort-design.md",
                "docs/superpowers/plans/2026-10-27-api-reasoning-effort.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic documentation\n", encoding="utf-8")
            testkit_source = root / "tools/BUILD129_REASONING_TESTKIT"
            testkit_source.parent.mkdir(parents=True)
            import shutil
            shutil.copytree(package.TESTKIT_SOURCE, testkit_source)

            python_buffer = io.BytesIO()
            with zipfile.ZipFile(python_buffer, "w") as archive:
                for name in ("python.exe", "python312.dll", "python312.zip", "_ssl.pyd", "LICENSE.txt"):
                    archive.writestr(name, b"synthetic embedded runtime")
            python_data = python_buffer.getvalue()
            environment = {
                "BUILD_NUMBER": "129", "GITHUB_SHA": "a" * 40,
                "GITHUB_RUN_ID": "12345", "PRISM_COMMIT": "b" * 40,
            }
            with patch.object(package, "ROOT", root), \
                 patch.object(package, "TESTKIT_SOURCE", testkit_source), \
                 patch.object(package.urllib.request, "urlopen", return_value=contextlib.closing(io.BytesIO(python_data))), \
                 patch.object(package, "PYTHON_SHA256", hashlib.sha256(python_data).hexdigest()), \
                 patch.dict(os.environ, environment):
                package.build()

            delivery = root / "build/delivery"
            candidate = delivery / "BONSAI_BUILD129_REASONING_MODE_CANDIDATE.zip"
            testkit = delivery / "BONSAI_BUILD129_REASONING_TESTKIT.zip"
            with zipfile.ZipFile(candidate) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertEqual(len([name for name in names if name.endswith(".ipa")]), 1)
                identity_path = next(name for name in names if name.endswith("TestKitIdentity.json"))
                identity = json.loads(archive.read(identity_path))
                self.assertEqual(identity["build_number"], "129")
                self.assertEqual(identity["source_git_sha"], "a" * 40)
                self.assertEqual(identity["functional_smoke"], "NOT_RUN")
                self.assertTrue(any(name.endswith("RUN_BUILD129_REASONING_API_SMOKE.cmd") for name in names))
            with zipfile.ZipFile(testkit) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertFalse(any(name.endswith(".ipa") for name in names))
                self.assertTrue(any(name.endswith("build129_reasoning_api_smoke.py") for name in names))
                self.assertTrue(any(name.endswith("DELIVERY_SHA256.json") for name in names))


if __name__ == "__main__":
    unittest.main()
