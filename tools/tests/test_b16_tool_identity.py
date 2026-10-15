import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from tools import b16_testkit as kit

class ToolIdentityTests(unittest.TestCase):
    def test_tool_identity_binds_original_ipa_and_checks_runner_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root=Path(folder);(root/'b16_testkit.py').write_bytes(b'fixture runner')
            tool={'runner_version':'111-identity-r1','tool_source_git_sha':'b'*40,
                'installed_ipa_source_sha':'8e62dce2930f93ecaf4c21973b7456b480a4644c',
                'runner_sha256':hashlib.sha256(b'fixture runner').hexdigest(),
                'files_sha256':{'b16_testkit.py':hashlib.sha256(b'fixture runner').hexdigest()}}
            (root/'TestKitIdentity.json').write_text(json.dumps({'build_number':'111','source_git_sha':kit.INSTALLED_SOURCE_SHA}))
            (root/'RunnerIdentity.json').write_text(json.dumps(tool))
            self.assertEqual(kit.verify_tool_identity(root)['tool_source_git_sha'],'b'*40)
            (root/'b16_testkit.py').write_bytes(b'changed')
            with self.assertRaises(kit.Incomplete): kit.verify_tool_identity(root)
            (root/'b16_testkit.py').write_bytes(b'fixture runner')
            tool['installed_ipa_source_sha']='f'*40
            (root/'TestKitIdentity.json').write_text(json.dumps({'build_number':'111','source_git_sha':kit.INSTALLED_SOURCE_SHA}))
            (root/'RunnerIdentity.json').write_text(json.dumps(tool))
            with self.assertRaises(kit.Incomplete): kit.verify_tool_identity(root)
