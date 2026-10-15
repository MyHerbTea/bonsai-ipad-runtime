import io
import json
import hashlib
import unittest
import zipfile
from unittest.mock import patch
try:
    from tools import package_b16_testkit_r2 as pack
except ImportError:
    pack=None

class RepackageTests(unittest.TestCase):
    def fixture(self,wrong_source=False,unsafe=False):
        identity={'build_number':'110','source_git_sha':('f'*40 if wrong_source else '8e62dce2930f93ecaf4c21973b7456b480a4644c'),
            'unsigned_ipa_sha256':'9fb9b421fffe5a307449c3c015582130b087bba1f5f09ba60fbe1214b9866a07',
            'prism_sha':'adfffbe41b2cabcd51fff326ab045662265062bb'}
        inner=io.BytesIO()
        with zipfile.ZipFile(inner,'w') as z:
            prefix='BonsaiLab-v1-RC1.26-Build110-B16-Prefill-TestKit/'
            z.writestr(prefix+'TestKitIdentity.json',json.dumps(identity))
            z.writestr(prefix+'AUTOMATED_TEST_REPORT.txt','Original IPA CI only')
            z.writestr(prefix+'original.ipa',b'not to be repackaged')
            for name in ('python.exe','python312.dll','python312.zip','python312._pth','_ssl.pyd','libssl-3.dll'):
                z.writestr(prefix+'python/'+name,b'fixture')
            if unsafe: z.writestr('../private',b'bad')
        outer=io.BytesIO()
        with zipfile.ZipFile(outer,'w') as z: z.writestr('kit.zip',inner.getvalue())
        return outer.getvalue()

    def test_digest_rejected_before_unpacking(self):
        self.assertIsNotNone(pack,'Repackage tool required')
        with self.assertRaises(ValueError): pack.build_kit(b'wrong artifact','b'*40,{},'')

    def test_original_ipa_identity_is_immutable_and_complete_tools_bundled(self):
        self.assertIsNotNone(pack,'Repackage tool required')
        raw=self.fixture();files={n:b'fixture' for n in pack.TOOL_FILES}
        with patch.object(pack,'ORIGINAL_ARTIFACT_SHA256',hashlib.sha256(raw).hexdigest()):
            result=pack.build_kit(raw,'b'*40,files,'Real local test summary')
        with zipfile.ZipFile(io.BytesIO(result)) as z:
            identity=json.loads(z.read('TestKitIdentity.json'));tool=json.loads(z.read('RunnerIdentity.json'))
            self.assertEqual(identity['source_git_sha'],'8e62dce2930f93ecaf4c21973b7456b480a4644c')
            self.assertEqual(tool['tool_source_git_sha'],'b'*40)
            self.assertFalse(any(n.endswith('.ipa') for n in z.namelist()))
            self.assertIn('python/python.exe',z.namelist());self.assertIn('RUN_B16_TESTKIT_GUI.ps1',z.namelist())
            self.assertIn(b'No IPA reinstall',z.read('README.txt'))
            self.assertEqual(z.read('TESTKIT_VERIFICATION.txt'),b'Real local test summary')

    def test_wrong_identity_and_unsafe_archive_are_rejected(self):
        self.assertIsNotNone(pack,'Repackage tool required')
        for kw in ({'wrong_source':True},{'unsafe':True}):
            raw=self.fixture(**kw)
            with patch.object(pack,'ORIGINAL_ARTIFACT_SHA256',hashlib.sha256(raw).hexdigest()):
                with self.assertRaises(ValueError): pack.build_kit(raw,'b'*40,{n:b'x' for n in pack.TOOL_FILES},'')

    def test_incomplete_tool_set_is_rejected(self):
        self.assertIsNotNone(pack)
        raw=self.fixture()
        with patch.object(pack,'ORIGINAL_ARTIFACT_SHA256',hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(ValueError,'Complete runner'): pack.build_kit(raw,'b'*40,{},'')
