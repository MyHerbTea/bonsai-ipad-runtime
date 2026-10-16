import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_b16_testkit import LoopbackFixture, evidence
from tools import b16_testkit as kit

class ReadinessTests(LoopbackFixture, unittest.TestCase):
    def pending(self, phase):
        obj=copy.deepcopy(self.state['evidence']);obj['startup_ready']=False
        obj['identity_hashing_active']=True
        if phase=='native': obj['native_context']=None
        elif phase=='model': obj['native_context'].pop('model_identity')
        else: obj.pop('vision_identity')
        obj['private_path']='PRIVATE_MODEL_PATH';return obj

    def test_native_hash_failure_is_terminal_and_diagnostics_are_allowlisted(self):
        obj=self.pending('model')
        obj['asset_hashing']={'model':{'phase':'failed','error_code':'OPEN_FAILED','bytes_hashed':0,'total_bytes':123,'elapsed_s':1.0,'private_path':'SECRET_PATH'},
            'vision':{'phase':'reading','bytes_hashed':12,'total_bytes':20}}
        self.state['evidence']=obj
        with self.assertRaisesRegex(kit.Incomplete,'MODEL_HASH_FAILED'):
            self.device.wait_ready(timeout=1)
        self.assertEqual(self.state['calls'],0);self.assertEqual(self.state['arms'],[])
        report=json.dumps(self.journal.state)
        self.assertIn('OPEN_FAILED',report);self.assertNotIn('SECRET_PATH',report)

    def test_vision_failure_and_hash_progress_to_ready_are_read_only(self):
        failed=self.pending('vision')
        failed['asset_hashing']={'vision':{'phase':'failed','error_code':'ACCESS_DENIED'}}
        self.state['evidence']=failed
        with self.assertRaisesRegex(kit.Incomplete,'VISION_HASH_FAILED'): self.device.wait_ready(timeout=1)
        self.state['evidence']=evidence()
        self.state['evidence']['vision_identity']={'sha256':'c'*64,'size_bytes':50}
        progressing=self.pending('model')
        progressing['asset_hashing']={'model':{'phase':'reading','bytes_hashed':1024,'total_bytes':2048}}
        self.state['readiness_frames']=[progressing]
        with patch.object(kit.time,'sleep'): result=self.device.wait_ready(timeout=2)
        self.assertTrue(result['startup_ready'])
        self.assertEqual(self.state['calls'],0);self.assertEqual(self.state['arms'],[])

    def test_native_progress_is_preserved_without_claiming_failure(self):
        obj=self.pending('model')
        obj['asset_hashing']={'model':{'phase':'reading','bytes_hashed':4,'total_bytes':100,'elapsed_s':2.0},
            'vision':{'phase':'ready','bytes_hashed':20,'total_bytes':20}}
        state,flags=kit.startup_status(obj)
        self.assertEqual(state,'MODEL_HASH_PENDING')
        self.assertEqual(flags['asset_hashing']['model']['bytes_hashed'],4)

    def test_initial_a1_waits_through_real_http_sequence_before_first_arm(self):
        self.state['readiness_frames']=[self.pending(x) for x in ('native','model','vision')]
        with patch('builtins.input',self.restart_ipad),patch.object(kit.time,'sleep'):
            self.device.restart('A1','BASELINE8')
        states=[x['state'] for x in self.journal.state.get('readiness',[])]
        for state in ('NATIVE_CONTEXT_MISSING','MODEL_HASH_PENDING','VISION_HASH_PENDING','READY'):
            self.assertIn(state,states)
        self.assertEqual(self.state['calls'],0);self.assertEqual(len(self.state['arms']),1)
        self.assertNotIn('PRIVATE_MODEL_PATH',json.dumps(self.journal.state))

    def test_restart_handoff_displays_phase_expected_batch_and_previous_process(self):
        import contextlib, io
        previous_id=self.state['evidence']['process_id']
        output=io.StringIO()
        with patch('builtins.input',self.restart_ipad),patch.object(kit.time,'sleep'),contextlib.redirect_stdout(output):
            self.device.restart('A1','BASELINE8')
        message=output.getvalue()
        self.assertIn('[RESTART HANDOFF] A1: B8 -> required B8',message)
        self.assertIn('old process='+previous_id,message)
        self.assertIn('swipe away Bonsai completely',message)
        self.assertIn('do not start a new experiment',message)
        self.assertEqual(len(self.state['arms']),1)

    def test_read_only_timeout_retains_safe_diagnostics_and_no_post(self):
        self.state['evidence']=self.pending('model')
        with self.assertRaisesRegex(kit.Incomplete,'READY_TIMEOUT'):
            self.device.wait_ready(timeout=1)
        self.assertEqual(self.state['calls'],0);self.assertEqual(self.state['arms'],[])
        diag=json.dumps(self.journal.state)
        self.assertIn('MODEL_HASH_PENDING',diag);self.assertNotIn('PRIVATE_MODEL_PATH',diag)
        self.assertNotIn('PRIVATE_KEY',diag)

    def test_unavailable_vision_identity_is_not_claimed_as_known_file_failure(self):
        self.state['evidence'].pop('vision_identity')
        with self.assertRaisesRegex(kit.Incomplete,'ASSET_MISSING'):
            self.device.wait_ready(timeout=1)
        self.assertEqual(self.state['arms'],[])

    def test_auth_and_version_are_terminal_without_posts(self):
        for status in (401,403):
            self.state['auth_status']=status
            with self.assertRaisesRegex(kit.Incomplete,'AUTH_FAILED'): self.device.wait_ready(timeout=1)
        self.state['auth_status']=200
        self.state['build']={'build_number':'111','source_git_sha':'f'*40}
        with self.assertRaisesRegex(kit.Incomplete,'VERSION_MISMATCH'): self.device.wait_ready(timeout=1)
        self.assertEqual(self.state['arms'],[]);self.assertEqual(self.state['calls'],0)

    def test_restart_waits_for_hashes_without_repeating_arm_post(self):
        def restart(*args):
            self.restart_ipad()
            self.state['readiness_frames']=[self.pending('model'),self.pending('vision')]
        self.device.restart_timeout=2
        with patch('builtins.input',restart),patch.object(kit.time,'sleep'):
            self.device.restart('A1','BASELINE8')
        self.assertEqual(len(self.state['arms']),1);self.assertEqual(self.state['calls'],0)

    def test_slow_or_trickling_read_cannot_extend_wall_clock_deadline(self):
        import threading,time
        release=threading.Event()
        def slow(*args,**kwargs):
            release.wait(2)
            return {'build_number':'111','source_git_sha':'a'*40}
        start=time.monotonic()
        try:
            with patch.object(self.device,'get',slow):
                with self.assertRaisesRegex(kit.Incomplete,'READY_TIMEOUT'):
                    self.device.wait_ready(timeout=.05)
            self.assertLess(time.monotonic()-start,.5)
            self.assertEqual(self.state['arms'],[]);self.assertEqual(self.state['calls'],0)
        finally: release.set()

class MigrationTests(unittest.TestCase):
    def test_only_empty_read_only_first_failure_can_start_new_runner(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            old=kit.Journal(Path(directory)/'B16-old',identity)
            old.state.update(stage='A1_restart',workload_fingerprint='old-runner')
            kit.export(old,'INCOMPLETE','Native startup evidence is missing or not ready')
            original=old.path.read_bytes()
            archived=kit.archive_readonly_failure(old.folder,Path(directory)/'archives',identity)
            self.assertEqual(old.path.read_bytes(),original)
            self.assertEqual((archived/'checkpoint.json').read_bytes(),original)
            original_zip=old.folder.with_suffix('.zip')
            original_zip_bytes=original_zip.read_bytes()
            imported=kit.archive_previous(original_zip,Path(directory)/'zip-archives',identity)
            self.assertEqual((imported/'original-result.zip').read_bytes(),original_zip_bytes)
            self.assertEqual(original_zip.read_bytes(),original_zip_bytes)
            for mutation in ({'inflight':'A1.arm_next_launch'},{'restart':{'phase':'scheduled'}},
                {'events':[{'case':'A1.arm_next_launch','state':'PASS'}]}, {'measurements':[{}]},
                {'reason':'Unknown failure'},{'arm_evidence':{'A1':{}}}):
                changed=copy.deepcopy(old.state);changed.update(mutation)
                old.path.write_text(json.dumps(changed))
                with self.assertRaises(kit.Incomplete):
                    kit.archive_readonly_failure(old.folder,Path(directory)/'archives',identity)

if __name__=='__main__': unittest.main()

class ImportRejectionTests(unittest.TestCase):
    def test_rejected_import_cannot_mask_uncertainty_on_next_default_run(self):
        import contextlib,io,os
        identity={'build_number':'111','source_git_sha':kit.INSTALLED_SOURCE_SHA}
        original_read=Path.read_text
        def read(path,*args,**kwargs):
            if path.name=='TestKitIdentity.json': return json.dumps(identity)
            return original_read(path,*args,**kwargs)
        for local_uncertain in (True,False):
            with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
                root=Path(directory);output=root/'RESULTS';previous=root/'previous'
                old=kit.Journal(previous/'B16-old',identity);old.state['stage']='A1_restart'
                if not local_uncertain: old.begin('A1.arm_next_launch')
                kit.export(old,'INCOMPLETE','Native startup evidence is missing or not ready')
                if local_uncertain:
                    local=kit.Journal(output/'B16-uncertain',identity);local.begin('A1.nonstream')
                with patch.object(kit,'verify_tool_identity',return_value={'tool_source_git_sha':'b'*40,'installed_ipa_source_sha':kit.INSTALLED_SOURCE_SHA}),patch.object(Path,'read_text',read),patch.object(kit,'discover',return_value='http://localhost'),patch.dict(os.environ,{'BONSAI_API_KEY':'PRIVATE_SECRET'}),patch.object(kit.DeviceRun,'execute',return_value=('INCOMPLETE',{})) as execute,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(kit.run(['--output',str(output),'--previous-results',str(previous)]),3)
                    self.assertEqual(kit.run(['--output',str(output),'--resume-latest']),3)
                    execute.assert_not_called()

    def test_safe_legacy_import_preserves_bytes_and_starts_new_experiment(self):
        import contextlib,io,os
        identity={'build_number':'111','source_git_sha':kit.INSTALLED_SOURCE_SHA}
        original_read=Path.read_text;called=[]
        def read(path,*args,**kwargs):
            if path.name=='TestKitIdentity.json': return json.dumps(identity)
            return original_read(path,*args,**kwargs)
        def execute(device):
            called.append(device.journal)
            device.journal.stage('A1_restart')
            device.journal.state['readiness']=[{'state':'MODEL_HASH_PENDING'}]
            raise kit.ReadinessError('READY_TIMEOUT','MODEL_HASH_PENDING')
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root=Path(directory);old=kit.Journal(root/'old'/'B16-first',identity)
            old.state.update(stage='A1_restart',workload_fingerprint='original-runner')
            kit.export(old,'INCOMPLETE','Native startup evidence is missing or not ready')
            original=old.path.read_bytes();original_zip=old.folder.with_suffix('.zip').read_bytes()
            with patch.object(kit,'verify_tool_identity',return_value={'tool_source_git_sha':'b'*40,'installed_ipa_source_sha':kit.INSTALLED_SOURCE_SHA}),patch.object(Path,'read_text',read),patch.object(kit,'discover',return_value='http://localhost'),patch.dict(os.environ,{'BONSAI_API_KEY':'PRIVATE_SECRET'}),patch.object(kit.DeviceRun,'execute',execute),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(kit.run(['--output',str(root/'RESULTS'),'--previous-results',str(old.folder.with_suffix('.zip'))]),3)
            self.assertEqual(len(called),1);self.assertEqual(old.path.read_bytes(),original)
            self.assertEqual(old.folder.with_suffix('.zip').read_bytes(),original_zip)
            new=called[0];self.assertEqual(new.state['identity'],identity)
            self.assertTrue(new.state['prior_archive']['new_experiment'])
            self.assertEqual(new.state['measurements'],[])
            self.assertNotIn('PRIVATE_SECRET',out.getvalue());self.assertNotIn('PRIVATE_SECRET',json.dumps(new.state))
