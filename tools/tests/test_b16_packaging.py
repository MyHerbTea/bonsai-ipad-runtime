"""Candidate packaging gates; no device performance claim."""
import hashlib
import io
import zipfile
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

class B16PackagingTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.github/workflows/build-ios.yml').read_text(encoding='utf-8')

    def test_exact_candidate_branch_and_single_success_artifact(self):
        branches = self.workflow.split('  workflow_dispatch:', 1)[0]
        self.assertIn('      - codex/32k-prefill-b16\n', branches)
        self.assertIn('      - main\n', branches)
        self.assertNotIn('codex/*', branches)
        self.assertEqual(self.workflow.count('      - name: Full Xcode build\n'), 1)
        upload = self.workflow.split('      - name: Upload artifact\n', 1)[1].split('      - name:', 1)[0]
        self.assertIn('name: BonsaiLab-iPad-v1-RC1.26-Build110-B16-Prefill-TestKit', upload)
        self.assertIn('path: build/BonsaiLab-v1-RC1.26-Build110-B16-Prefill-TestKit.zip', upload)
        self.assertEqual(upload.count('path:'), 1)

    def test_native_and_vision_safety_suites_are_retained(self):
        for marker in ('rc126_build93_policy_tests.swift', 'rc126_build94_policy_tests.swift',
            'rc126_build106_policy_tests.swift', 'rc1250_multi_image_composer_contract_tests.swift',
            'rc1252_vision_lifecycle_safety_contract_tests.py', 'rc126_build89_compact_scheduler_contract_tests.py',
            'BonsaiLab/B16RuntimeEvidence.swift', 'tools/build110_runtime_evidence_tests.swift',
            'tools/build110_policy_tests.swift', 'test_b16_testkit.py', 'test_b16_runtime_source.py', 'test_b16_packaging.py'):
            self.assertIn(marker, self.workflow)
        self.assertNotIn('python3 tools/current_release_contract_tests.py', self.workflow)

    def test_portable_python_is_pinned_verified_and_imports_kit_root(self):
        for marker in ('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',
            '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3',
            'hashlib.sha256(archive).hexdigest()', 'Python archive SHA256 mismatch',
            'kit / "python"', '"python312.zip\\n.\\n..\\n"', '"python.exe"', '"_ssl.pyd"', '"libssl-3.dll"'):
            self.assertIn(marker, self.workflow)

    def test_archive_has_matching_runner_identity_and_reports(self):
        for marker in ('RUN_B16_TESTKIT.cmd', 'RUN_B16_TESTKIT_GUI.ps1', 'b16_testkit.py',
            'rc126_build106_full_stage_certification.py', 'TestKitIdentity.json', 'AUTOMATED_TEST_REPORT.txt',
            'AUTOMATED_TEST_COMMANDS.txt', 'BUILD_INFO.txt', '"$KIT_NAME/$IPA_NAME.sha256"', '"$KIT_NAME/python/python.exe"'):
            self.assertIn(marker, self.workflow)
        self.assertIn('signing/sideloading', self.workflow)

    def portable_python_script(self):
        block = self.workflow.split('          # Official portable Python download', 1)[1].split('          PY\n', 1)[0]
        script = block.split("          python3 - <<'PY'\n", 1)[1]
        return '\n'.join(line[10:] for line in script.splitlines())

    def test_bad_python_digest_fails_before_extraction(self):
        script = self.portable_python_script()
        with tempfile.TemporaryDirectory(dir=ROOT / 'tools/tests') as directory:
            with patch.dict(os.environ, {'KIT': directory}), patch('urllib.request.urlopen', return_value=io.BytesIO(b'untrusted archive')):
                with self.assertRaisesRegex(SystemExit, 'Python archive SHA256 mismatch'):
                    exec(compile(script, 'workflow-python-download', 'exec'), {})
            self.assertFalse((Path(directory) / 'python').exists())

    def test_verified_python_archive_extracts_usable_import_paths(self):
        payload = io.BytesIO()
        required = ('python.exe', 'python312.dll', 'python312.zip', '_ssl.pyd', 'libssl-3.dll', 'libcrypto-3.dll', 'LICENSE.txt')
        with zipfile.ZipFile(payload, 'w') as archive:
            for name in required:
                archive.writestr(name, 'test-fixture')
        data = payload.getvalue()
        official_hash = '4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3'
        script = self.portable_python_script().replace(official_hash, hashlib.sha256(data).hexdigest())
        with tempfile.TemporaryDirectory(dir=ROOT / 'tools/tests') as directory:
            with patch.dict(os.environ, {'KIT': directory}), patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                exec(compile(script, 'workflow-python-download', 'exec'), {})
            python_dir = Path(directory) / 'python'
            self.assertEqual((python_dir / 'python312._pth').read_text(), 'python312.zip\n.\n..\n')
            for name in required:
                self.assertTrue((python_dir / name).is_file())

    def test_identity_hashes_exact_bundled_ipa(self):
        marker = '          # Build110 TestKit identity\n'
        self.assertIn(marker, self.workflow)
        block = self.workflow.split(marker, 1)[1].split('          PY\n', 1)[0]
        script = block.split("          python3 - <<'PY'\n", 1)[1]
        script = '\n'.join(line[10:] for line in script.splitlines())
        with tempfile.TemporaryDirectory(dir=ROOT / 'tools/tests') as directory:
            kit = Path(directory)
            ipa = kit / 'candidate.ipa'
            ipa.write_bytes(b'exact unsigned candidate bytes')
            with patch.dict(os.environ, {'KIT': str(kit), 'IPA_NAME': ipa.name, 'BUILD_NUMBER': '110', 'GITHUB_SHA': 'a' * 40}):
                exec(compile(script, 'workflow-testkit-identity', 'exec'), {})
            identity = json.loads((kit / 'TestKitIdentity.json').read_text())
            self.assertEqual(identity['build_number'], '110')
            self.assertEqual(identity['source_git_sha'], 'a' * 40)
            self.assertEqual(identity['prism_sha'], 'adfffbe41b2cabcd51fff326ab045662265062bb')
            self.assertEqual(identity['unsigned_ipa_sha256'], hashlib.sha256(ipa.read_bytes()).hexdigest())

if __name__ == '__main__':
    unittest.main()
