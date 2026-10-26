import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/PTQ1_ONECLICK'))

class KVValidationTests(unittest.TestCase):
    def module(self):
        path=ROOT/'tools/PTQ1_ONECLICK/kv_baseline.py'
        self.assertTrue(path.exists(), 'Build126 fixed-Q8 validator is missing')
        import kv_baseline
        return kv_baseline
    def native(self):
        return dict(context=16384,batch=8,ubatch=8,kv_k='Q8_0',kv_v='Q8_0',
            kv_observation_source='allocated_native_kv_tensors',kv_policy='Q8_0',
            gpu_layers=56,threads=6,threads_batch=6,mmap=True,sequence_max=1,
            flash_attention=True,offload_kqv=True,op_offload=True,kv_unified=False,
            text_kv_reuse=False,metal_tensor_disabled=True,swa_full=False)
    def test_allocation_proof_required_not_just_requested_q8(self):
        m=self.module();n=self.native()
        self.assertEqual(m.validate_native(n), [])
        for field,value in [('kv_k','Q4_0'),('kv_v','Q4_0'),('kv_observation_source','successful_native_creation_parameters'),
                            ('context',32768),('batch',16),('gpu_layers',99),('threads',4),('mmap',False)]:
            bad=dict(n);bad[field]=value
            self.assertTrue(m.validate_native(bad),field)
    def test_quick_is_not_full_and_restart_is_mandatory(self):
        m=self.module()
        self.assertEqual(m.decide('quick',True,False,True), 'BLOCKED')
        self.assertEqual(m.decide('quick',True,True,True), 'QUICK_PASS')
        self.assertEqual(m.decide('full',True,True,True), 'FULL_PASS')
        self.assertEqual(m.decide('full',False,True,True), 'FAIL')
        self.assertEqual(m.decide('full',True,True,False), 'BLOCKED')
    def test_never_overwrite_existing_evidence(self):
        import tempfile
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result';m.new_directory(p);(p/'failure.json').write_text('keep')
            with self.assertRaises(FileExistsError):m.new_directory(p)
            self.assertEqual((p/'failure.json').read_text(),'keep')

    def test_result_bundle_preserves_failure_raw_data_and_excludes_secrets(self):
        import tempfile,json,zipfile
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sub=root/'phase';sub.mkdir()
            (sub/'raw-failure.json').write_text('{"failure":"q8 allocation"}')
            (sub/'checkpoint.json').write_text('secret-session')
            report=dict(status='FAIL',mode='quick',phases=[],session_id='SECRET',errors=[])
            m.save_bundle(root,report)
            with zipfile.ZipFile(root/'results.zip') as z:
                self.assertIn('phase/raw-failure.json',z.namelist())
                self.assertNotIn('phase/checkpoint.json',z.namelist())
                self.assertNotIn('SECRET',z.read('report.json').decode())
                manifest=json.loads(z.read('MANIFEST_SHA256.json'))
                self.assertEqual(manifest['phase/raw-failure.json'],m.b.digest(z.read('phase/raw-failure.json')))

    def test_uncertain_q8_requests_preserve_marker_and_are_not_retried(self):
        from unittest.mock import patch
        m=self.module();client=m.Q8Client('http://127.0.0.1:8080')
        with patch.object(m.b.Client,'request',side_effect=m.b.UncertainRequest('REQUEST_OUTCOME_UNKNOWN')) as call:
            with self.assertRaises(m.b.UncertainRequest):client.request('run',{'prompt':'synthetic'})
            self.assertEqual(call.call_count,1)
        self.assertTrue(client.preserve_interrupted)
        with patch.object(m.b.Client,'request',return_value={}) as call:
            client.request('restore',{})
            self.assertTrue(call.call_args.args[1]['preserve_interrupted'])

    def test_build126_source_package_has_independent_verified_kit(self):
        import contextlib,hashlib,io,json,os,plistlib,tempfile,zipfile
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('package126',ROOT/'tools/package_ptq1_oneclick.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=root/'build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app';app.mkdir(parents=True)
            (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleVersion':'126'}))
            (app/'BonsaiLab').write_bytes(b'SYNTHETIC APP')
            kit=root/'tools/PTQ1_ONECLICK';kit.mkdir(parents=True)
            for name in ('RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd','RUN_Q8_BASELINE.cmd','RUN_Q8_FULL.cmd'):
                (kit/name).write_bytes(b'@echo off\n')
            (kit/'kv_baseline.py').write_text('# synthetic')
            (root/'tools/ptq1_official_model.json').write_text('{"sha256":"model"}')
            docs=root/'docs/build126';docs.mkdir(parents=True);(docs/'audit-and-plan.md').write_text('SYNTHETIC AUDIT')
            for name in ('CI_TESTS.txt','build.log','llama-symbols.txt','app-symbols.txt','SYMBOL_IDENTITY.json','BUILD126_POLICY.txt','BUILD126_TESTS.txt'):
                (root/'build'/name).write_text('SYNTHETIC CHECK')
            (root/'build/Bonsai-Build126-Symbols.zip').write_bytes(b'SYNTHETIC SYMBOLS')
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as z:
                for name in ('python.exe','python312.dll','python312.zip','_ssl.pyd','LICENSE.txt'):z.writestr(name,b'synthetic')
            data=data.getvalue()
            with patch.object(package,'ROOT',root),patch.object(package,'PYTHON_SHA',hashlib.sha256(data).hexdigest()),patch.object(
                package.urllib.request,'urlopen',return_value=contextlib.closing(io.BytesIO(data))),patch.dict(
                os.environ,{'BUILD_NUMBER':'126','GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'1','PRISM_COMMIT':'d'*40}):
                package.build()
            for name,ipas in [('BONSAI_BUILD126_PTQ1_ONECLICK.zip',1),('BONSAI_BUILD126_Q8_TESTKIT.zip',0)]:
                with zipfile.ZipFile(root/'build/delivery'/name) as z:
                    self.assertEqual(len([x for x in z.namelist() if x.endswith('.ipa')]),ipas)
                    base='Bonsai-Build126-PTQ1/'
                    manifest=json.loads(z.read(base+'DELIVERY_SHA256.json'))
                    for file,sha in manifest.items():self.assertEqual(hashlib.sha256(z.read(base+file)).hexdigest(),sha)
                    self.assertIn(base+'RUN_Q8_BASELINE.cmd',z.namelist())
                    self.assertIn(base+'CI_EVIDENCE/BUILD126_TESTS.txt',z.namelist())
                    self.assertIn('NOT_RUN',z.read(base+'BUILD126_DELIVERY_REPORT_CN.md').decode())

    def test_evidence_validation_failure_preserves_quarantine_before_restore(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        m=self.module();client=m.Q8Client('http://127.0.0.1:8080');seen=[]
        def restore(t):
            seen.append(client.preserve_interrupted);t.report['restoration']='RESTORED'
        with tempfile.TemporaryDirectory() as d,patch.object(m.Q8Run,'prepare',return_value=True),patch.object(
            m.Q8Run,'fit_prompt',return_value=('synthetic',512)),patch.object(
            m.Q8Run,'run',side_effect=m.b.EvidenceError('Q8_SAMPLE_FAILED:native_kv_k')),patch.object(
            m.Q8Run,'restore',restore),patch.object(m,'snapshot',return_value={}):
            with self.assertRaises(m.b.EvidenceError):m.phase(client,{},Path(d)/'phase','quick')
        self.assertEqual(seen,[True])

    def test_raw_benchmark_text_survives_and_hash_can_be_recomputed(self):
        import tempfile,json,copy
        from types import SimpleNamespace
        from test_oneclick import sample,IDENTITY
        m=self.module();data=sample(64);key='raw-proof';request=m.b.digest(key)[:24]
        data['actual'].update(context=16384,batch=8,ubatch=8,kv_k='Q8_0',kv_v='Q8_0')
        data['evidence']['native_context']=dict(self.native(),context_id='ctx',model_identity=IDENTITY['official_model'])
        data.update(prompt_tokens=512,text='synthetic-output',output_sha256=m.b.digest('synthetic-output'),
            counting='off',sampling_period=0,request_id=request,
            profile=dict(request_id=request,completed=True,
                cpu_ptq1_sampling=dict(available=True,counting_on=False,sampling_enabled=False,sample_period=0)))
        client=SimpleNamespace(session=None,request=lambda *a,**k:copy.deepcopy(data))
        with tempfile.TemporaryDirectory() as d:
            t=m.Q8Run(client,IDENTITY,Path(d));t.current=dict(m.CONFIG);t.process='p';t.creation_id='ctx'
            t.run(m.CONFIG,'synthetic',512,key,'formal')
            raw=json.loads((Path(d)/(request+'-raw-result.json')).read_text())
            self.assertEqual(raw.get('text'),'synthetic-output')
            self.assertEqual(m.b.digest(raw['text']),raw['output_sha256'])

    def test_sse_engine_error_is_retained_without_auth_or_session(self):
        import tempfile,io,json
        from unittest.mock import patch
        m=self.module()
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        raw=b'event: error\ndata: {"code":"Q8_ALLOCATION_FAILED","session_id":"PRIVATE"}\n\n'
        client=m.Q8Client('http://127.0.0.1:8080','KEY')
        with tempfile.TemporaryDirectory() as d:
            client.evidence_directory=Path(d)
            with patch.object(client.opener,'open',return_value=Response(raw)):
                with self.assertRaises(m.b.APIError):
                    client.request('run',dict(request_id='req',prompt='synthetic'),stream=True)
            text=(Path(d)/'req-events.jsonl').read_text()
            self.assertIn('Q8_ALLOCATION_FAILED',text)
            self.assertNotIn('PRIVATE',text);self.assertNotIn('KEY',text)
            self.assertTrue(client.preserve_interrupted)

if __name__=='__main__':unittest.main()
