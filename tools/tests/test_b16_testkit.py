import copy
import json
import tempfile
import unittest
import uuid
from pathlib import Path
try:
    from tools import b16_testkit as kit
except ImportError:
    kit = None

def evidence(batch=8):
    return {'process_id': str(uuid.uuid4()), 'source_git_sha': 'a'*40,
        'build_number': '111', 'startup_ready': True, 'identity_hashing_active': False,
        'physical_memory_bytes':16*1024**3, 'operating_system':'iPadOS 26', 'native_context': {
        'context_id': str(uuid.uuid4()), 'context': 32768, 'batch': batch,
        'ubatch': batch, 'sequence_max': 1, 'kv_k': 'Q4_0', 'kv_v': 'Q4_0',
        'text_kv_reuse': False, 'model_identity': {'sha256': 'b'*64, 'size_bytes': 100},
        'gpu_layers': 99, 'flash_attention': True, 'threads': 6,
        'offload_kqv': True, 'op_offload': True, 'mmap': True, 'kv_unified':True,
        'observation_source':'successful_native_creation_parameters','threads_batch':6,
        'swa_full':True,'metal_tensor_disabled':True}}


def decode_records():
    cases=('max_tokens_gt256','max_completion_tokens_gt256','max_output_tokens_gt256','implicit_output_gt256')
    return [{'case':arm+'.'+case,'state':'PASS','semantic_validated':True,
             'request_sha256':'d'*64,'finish_reason':'stop','observation':{
             'prompt_tokens':500,'completion_tokens':400,'tokens_per_second':20}}
            for arm in ('A1','B','A2') for case in cases]

class TestKitTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(kit, 'B16 TestKit must exist')
        self.identity = {'source_git_sha': 'a'*40, 'build_number': '111'}

    def test_identity_and_actual_creation_parameters_required(self):
        good = evidence(); kit.validate_evidence(good, self.identity, 8)
        for field in ('source_git_sha', 'process_id', 'startup_ready'):
            bad = copy.deepcopy(good); bad.pop(field)
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad, self.identity, 8)
        for field in ('context_id', 'model_identity', 'kv_k', 'threads'):
            bad = copy.deepcopy(good); bad['native_context'].pop(field)
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad, self.identity, 8)
        bad = copy.deepcopy(good); bad['source_git_sha'] = 'c'*40
        with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad, self.identity, 8)

    def test_restart_demands_new_process_context_and_same_assets(self):
        old = evidence(); new = evidence(16)
        kit.validate_evidence(new, self.identity, 16, old)
        bad = copy.deepcopy(new); bad['process_id'] = old['process_id']
        with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad, self.identity, 16, old)
        for field, value in (('context_id', old['native_context']['context_id']),
            ('model_identity', {'sha256': 'c'*64, 'size_bytes': 100}), ('threads', 4)):
            bad = copy.deepcopy(new); bad['native_context'][field] = value
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad, self.identity, 16, old)

    def test_safe4_stops_and_arm_request_never_forges_acknowledgement(self):
        good = {'active_arm': 'BASELINE8', 'engine_context_batch': 8,
            'engine_context_ubatch': 8, 'sticky_fallback': False}
        kit.validate_launch(good, 'BASELINE8')
        good['active_arm'] = 'SAFE4'
        with self.assertRaises(kit.Incomplete): kit.validate_launch(good, 'BASELINE8')
        self.assertEqual(kit.arm_payload('CANDIDATE16'),
            {'arm': 'CANDIDATE16', 'acknowledge_recovery': False})
        with self.assertRaises(kit.Incomplete): kit.arm_payload('CANDIDATE32')

    def test_sse_requires_multiple_real_content_deltas_done_usage(self):
        rows = [json.dumps({'choices': [{'delta': {'content': x}, 'finish_reason': None}]})
            for x in ('OK', ' SENTINEL')]
        rows += [json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]}),
            json.dumps({'choices': [], 'usage': {'prompt_tokens': 201, 'completion_tokens': 3}}), '[DONE]']
        wire = ''.join('data: '+row+'\n\n' for row in rows)
        self.assertEqual(kit.parse_sse(wire, 'text/event-stream')[0], 'OK SENTINEL')
        for index in (0, 3, 4):
            broken = wire.replace('data: '+rows[index]+'\n\n', '')
            with self.assertRaises(kit.Incomplete): kit.parse_sse(broken, 'text/event-stream')

    def test_inflight_checkpoint_refuses_automatic_replay_and_stores_no_secrets(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal = kit.Journal(Path(folder), self.identity); journal.begin('A1.medium.1')
            with self.assertRaises(kit.Incomplete): kit.Journal(Path(folder), self.identity)
            raw = (Path(folder)/'checkpoint.json').read_text()
            for word in ('api_key', 'base_url', 'prompt', 'response'): self.assertNotIn(word, raw)

    def test_telemetry_allowlist_discards_private_diagnostics(self):
        clean = kit.safe_telemetry({'phys_footprint_bytes': 100, 'thermal_state': 'nominal',
            'api_key': 'secret', 'path': 'private', 'error': 'private'})
        self.assertEqual(clean, {'phys_footprint_bytes': 100, 'thermal_state': 'nominal'})

    def test_observation_must_be_fresh_counts_exact_and_zero_reuse(self):
        obj = {'last_observation': {'sequence': 2, 'prompt_tokens': 250,
            'completion_tokens': 20, 'prefill_ms': 100, 'ttft_ms': 120, 'tokens_per_second': 10},
            'text_kv_reuse': {'reused_tokens': 0}, 'build104_text_kv_checkpoint': {
            'effective_sequence_max': 1, 'build105_quarantined': True}}
        usage = {'prompt_tokens': 250, 'completion_tokens': 20}
        kit.validate_observation(obj, 1, usage)
        for change in ({'sequence': 1}, {'prompt_tokens': 251}, {'prefill_ms': None}):
            bad = copy.deepcopy(obj); bad['last_observation'].update(change)
            with self.assertRaises(kit.Incomplete): kit.validate_observation(bad, 1, usage)
        obj['text_kv_reuse']['reused_tokens'] = 1
        with self.assertRaises(kit.Failure): kit.validate_observation(obj, 1, usage)

    def test_performance_requires_all_repetitions_drift_and_decode_gates(self):
        records = [{'arm': arm, 'workload': work, 'rep': rep, 'prefill_ms': ms,
            'tokens_per_second': 20, 'prompt_tokens': 500, 'completion_tokens': 32}
            for arm, ms in (('A1',1000),('B',800),('A2',1020))
            for work in ('medium','long') for rep in range(3)]
        self.assertEqual(kit.performance_verdict(records,decode_records())[0], 'PASS')
        self.assertEqual(kit.performance_verdict(records[:-1],decode_records())[0], 'INCOMPLETE')
        bad = copy.deepcopy(records)
        for row in bad:
            if row['arm'] == 'A2': row['prefill_ms'] = 1200
        self.assertEqual(kit.performance_verdict(bad,decode_records())[0], 'INCOMPLETE')
        for row in records:
            if row['arm'] == 'B': row['tokens_per_second'] = 18
        self.assertEqual(kit.performance_verdict(records,decode_records())[0], 'PASS')

    def test_three_distinct_public_png_fixtures(self):
        imgs = kit.public_images()
        self.assertEqual(len(imgs),3); self.assertEqual(len(set(imgs)),3)
        self.assertTrue(all(x.startswith(bytes.fromhex('89504e470d0a1a0a')) for x in imgs))


class OrchestrationTests(unittest.TestCase):
    def test_missing_vision_or_active_hashing_cannot_start_full_run(self):
        self.assertIsNotNone(kit)
        identity = {'source_git_sha':'a'*40,'build_number':'111'}
        good = evidence()
        with self.assertRaises(kit.Incomplete): kit.validate_assets(good)
        good['vision_identity'] = {'sha256':'c'*64,'size_bytes':50}
        good['identity_hashing_active'] = False
        kit.validate_assets(good)
        good['identity_hashing_active'] = True
        with self.assertRaises(kit.Incomplete): kit.validate_assets(good)

    def test_dry_run_lists_stages_and_never_device_pass(self):
        self.assertIsNotNone(kit)
        result = kit.dry_run()
        self.assertEqual(result['status'],'INCOMPLETE')
        self.assertFalse(result['device_certified'])
        self.assertIn('B_regression',result['stages'])

    def test_export_incomplete_preserves_inflight_and_has_hash_manifest(self):
        self.assertIsNotNone(kit)
        import zipfile
        identity = {'source_git_sha':'a'*40,'build_number':'111'}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal = kit.Journal(Path(folder)/'session',identity)
            journal.begin('A1.uncertain')
            path = kit.export(journal,'INCOMPLETE','Transport interrupted')
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                checkpoint = json.loads(archive.read('checkpoint.json'))
                self.assertEqual(manifest['status'],'INCOMPLETE')
                self.assertEqual(checkpoint['inflight'],'A1.uncertain')
                self.assertIn('checkpoint.json',manifest['files_sha256'])
                self.assertFalse(manifest['default_promoted'])

class GateExtensionsTests(unittest.TestCase):
    def test_environment_must_match_after_restart(self):
        identity={'source_git_sha':'a'*40,'build_number':'111'}
        old=evidence(); new=evidence(16)
        old.update(physical_memory_bytes=16*1024**3,operating_system='iPadOS 26')
        new.update(physical_memory_bytes=16*1024**3,operating_system='iPadOS 27')
        with self.assertRaises(kit.Incomplete): kit.validate_evidence(new,identity,16,old)

    def test_missing_native_observation_provenance_and_invalid_threads_stop(self):
        identity={'source_git_sha':'a'*40,'build_number':'111'}
        for field,value in (('observation_source','advertised_defaults'),('threads',0)):
            bad=evidence(); bad['native_context'][field]=value
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad,identity,8)

    def test_native_sequence_must_advance_exactly_once(self):
        obj={'last_observation':{'sequence':4,'prompt_tokens':250,'completion_tokens':20,
             'prefill_ms':100,'ttft_ms':120,'tokens_per_second':10},
             'text_kv_reuse':{'reused_tokens':0},'build104_text_kv_checkpoint':{
             'effective_sequence_max':1,'build105_quarantined':True}}
        with self.assertRaises(kit.Incomplete): kit.validate_observation(obj,1,{'prompt_tokens':250,'completion_tokens':20})

class LoopbackFixture:
    def setUp(self):
        import http.server
        import threading
        self.state={'evidence':evidence(),'batch':8,'next':'BASELINE8','sequence':0,
                    'baseline':False,'pending':False,'confirmed':False,'calls':0,'arms':[],'uncertain':False}
        self.state['evidence']['vision_identity']={'sha256':'c'*64,'size_bytes':50}
        state=self.state
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def send(self,obj,mime='application/json',status=200):
                raw=obj.encode() if isinstance(obj,str) else json.dumps(obj).encode()
                self.send_response(status); self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/debug/build': self.send(state.get('build',{'build_number':'111','source_git_sha':'a'*40}),status=state.get('auth_status',200))
                elif self.path=='/debug/b16/evidence':
                    frames=state.get('readiness_frames',[])
                    self.send(frames.pop(0) if frames else state['evidence'])
                elif self.path=='/debug/telemetry': self.send({'phys_footprint_bytes':2*1024**3,
                    'available_bytes':4*1024**3,'thermal_state':'nominal','private_path':'PRIVATE_DIAGNOSTIC'})
                elif self.path=='/v1/models': self.send({'data':[{'id':'fixture-model'}]})
                elif self.path=='/health': self.send({'status':'ok'})
                elif self.path=='/debug/build94/launch': self.send({'active_arm':'CANDIDATE16' if state['batch']==16 else 'BASELINE8',
                    'engine_context_batch':state['batch'],'engine_context_ubatch':state['batch'],
                    'baseline8_completed':state['baseline'],'pending':state['pending'],
                    'confirmed_candidate16':state['confirmed'],'sticky_fallback':False})
                elif self.path=='/debug/prefill': self.send({'last_observation':state.get('observation'),
                    'text_kv_reuse':{'reused_tokens':0,'enabled':False,'hit':False},
                    'build104_text_kv_checkpoint':{'effective_sequence_max':1,'build105_quarantined':True}})
                else: self.send({})
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/debug/build94/next-launch':
                    state['arms'].append(body);state['next']=body['arm']; self.send({'ok':True}); return
                state['calls']+=1
                if state['uncertain']:
                    import socket
                    self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
                message=body['messages'][-1]['content']
                if isinstance(message,list):
                    count=len(message)-1;text='IMAGES_%d red blue'%count
                elif 'Print each integer' in message: text='\n'.join('%04d'%i for i in range(1,401))
                elif 'Final instruction' in message: text='B16_SENTINEL amber cedar violet maple'
                elif 'five short sentences' in message: text='Trees grow. SSE_SENTINEL'
                elif 'POST_VISION' in message: text='POST_VISION_SENTINEL'
                elif 'LILAC' in message or 'exact marker' in message: text='LILAC-0427'
                else: text='TEXT_SENTINEL'
                count=400 if text.startswith('0001') else 8
                prompt_count=600 if isinstance(message,str) and 'Record 0095' in message else 500
                usage={'prompt_tokens':prompt_count,'completion_tokens':count,'private_path':'PRIVATE_USAGE'}
                state['sequence']+=1
                state['observation']={'sequence':state['sequence'],'prompt_tokens':prompt_count,'completion_tokens':count,
                    'prefill_ms':800 if state['batch']==16 else 1000,'ttft_ms':1100,'tokens_per_second':20}
                if state['batch']==8: state['baseline']=True
                else: state['pending']=False;state['confirmed']=True
                if body['stream']:
                    packets=[{'choices':[{'delta':{'content':'Trees grow. '},'finish_reason':None}]},
                        {'choices':[{'delta':{'content':'SSE_SENTINEL'},'finish_reason':None}]},
                        {'choices':[{'delta':{},'finish_reason':'stop'}]}, {'choices':[],'usage':usage}]
                    wire=''.join('data: '+json.dumps(x)+'\n\n' for x in packets)+'data: [DONE]\n\n'
                    self.send(wire,'text/event-stream')
                else: self.send({'choices':[{'message':{'content':text},'finish_reason':'stop'}],'usage':usage})
        class TestHTTPServer(http.server.ThreadingHTTPServer):
            request_queue_size=128
            daemon_threads=False
            block_on_close=True
        self.server=TestHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2]))
        self.identity={'build_number':'111','source_git_sha':'a'*40}
        self.journal=kit.Journal(Path(self.temp.name)/'session',self.identity)
        self.device=kit.DeviceRun(self.journal,self.identity,'http://127.0.0.1:'+str(self.server.server_port),'PRIVATE_KEY',timeout=5,restart_timeout=2)
        # Embedded CPython can hit Windows loopback endpoint conflicts in zero-latency
        # synthetic bursts. Model ordinary LAN latency in the test transport only;
        # execute every real HTTP operation exactly once, never retry a POST.
        from unittest.mock import patch
        original_request=kit.request
        def paced_request(*args,**kwargs):
            threading.Event().wait(.05)
            return original_request(*args,**kwargs)
        self.request_patch=patch.object(kit,'request',paced_request)
        self.request_patch.start()
        import contextlib,io
        self.capture=contextlib.redirect_stdout(io.StringIO());self.capture.__enter__()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.request_patch.stop();self.temp.cleanup();self.capture.__exit__(None,None,None)
    def restart_ipad(self,*args):
        state=self.state; batch=16 if state['next']=='CANDIDATE16' else 8
        state['batch']=batch;state['evidence']=evidence(batch)
        state['evidence']['vision_identity']={'sha256':'c'*64,'size_bytes':50}
        state['sequence']=0;state['observation']=None;state['pending']=batch==16
class LoopbackTests(LoopbackFixture,unittest.TestCase):
    def test_complete_aba_run_and_zip_are_privacy_safe(self):
        from unittest.mock import patch
        import zipfile
        with patch('builtins.input',self.restart_ipad): verdict,metrics=self.device.execute()
        self.assertEqual(verdict,'PASS');self.assertEqual(len(self.journal.state['measurements']),18)
        self.assertEqual([x['arm'] for x in self.state['arms']],['BASELINE8','CANDIDATE16','BASELINE8'])
        self.assertTrue(all(x['acknowledge_recovery'] is False for x in self.state['arms']))
        path=kit.export(self.journal,verdict,'Fixture experiment only',metrics)
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                raw=archive.read(name).decode('utf-8')
                for secret in ('PRIVATE_KEY','PRIVATE_DIAGNOSTIC','PRIVATE_USAGE','http://127.0.0.1'):
                    self.assertNotIn(secret,raw)
    def test_same_process_restart_never_runs_inference(self):
        self.device.restart_timeout=.1
        from unittest.mock import patch
        with patch('builtins.input',lambda *args:None):
            with self.assertRaises(kit.Incomplete): self.device.restart('A1','BASELINE8')
        self.assertEqual(self.state['calls'],0);self.assertEqual(len(self.state['arms']),1)
    def test_uncertain_transport_stops_after_single_request(self):
        self.device.evidence=copy.deepcopy(self.state['evidence']);self.device.model='fixture-model';self.device.arm='A1'
        self.state['uncertain']=True
        with self.assertRaises(kit.Incomplete):
            self.device.chat('A1.uncertain',self.device.text('Reply exactly TEXT_SENTINEL.'),sentinel='TEXT_SENTINEL')
        self.assertEqual(self.state['calls'],1)
        self.assertEqual(self.journal.state['inflight'],'A1.uncertain')

class SamplerTests(unittest.TestCase):
    def test_sampler_records_bounded_public_fields_and_reports_observed_peak(self):
        import threading
        self.assertIsNotNone(getattr(kit,'TelemetrySampler',None),'In-flight memory sampler must exist')
        ready=threading.Event()
        def fetch():
            ready.set()
            return {'phys_footprint_bytes':123,'available_bytes':1024**3,
                    'thermal_state':'nominal','private_path':'PRIVATE_SAMPLE'}
        sampler=kit.TelemetrySampler(fetch,interval=.01);sampler.start()
        self.assertTrue(ready.wait(2)); summary=sampler.stop()
        self.assertEqual(summary['sampled_peak_footprint_bytes'],123)
        self.assertNotIn('PRIVATE_SAMPLE',json.dumps(summary))
        self.assertEqual(summary['sampling_interval_s'],.01)

    def test_sampler_reports_measurement_failure_without_raw_exception(self):
        import threading
        self.assertIsNotNone(getattr(kit,'TelemetrySampler',None),'In-flight memory sampler must exist')
        ready=threading.Event()
        def fetch():
            ready.set();raise kit.Failure('PRIVATE_ERROR')
        sampler=kit.TelemetrySampler(fetch,interval=.01);sampler.start()
        self.assertTrue(ready.wait(2)); summary=sampler.stop()
        self.assertEqual(summary['issue'],'MEMORY_ANOMALY')
        self.assertNotIn('PRIVATE_ERROR',json.dumps(summary))

class ResumeTests(unittest.TestCase):
    def test_completed_checkpoint_resumes_without_losing_measurements(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal=kit.Journal(Path(folder),identity)
            journal.finish('A1.nonstream',request_sha256='b'*64)
            journal.state['measurements']=[{'arm':'A1','workload':'medium','rep':0}];journal.save()
            restored=kit.Journal(Path(folder),identity,resume=True)
            self.assertEqual(restored.state['measurements'],journal.state['measurements'])
            self.assertIsNotNone(restored.completed('A1.nonstream'))

    def test_resume_rejects_inflight_changed_workload_and_unknown_cases(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal=kit.Journal(Path(folder),identity)
            for mutation in ({'inflight':'A1.medium.1'},{'workload_fingerprint':'wrong'},
                {'events':[{'case':'B.forged','state':'PASS'}]}):
                saved=copy.deepcopy(journal.state);saved.update(mutation)
                journal.path.write_text(json.dumps(saved))
                with self.assertRaises(kit.Incomplete): kit.Journal(Path(folder),identity,resume=True)

    def test_export_excludes_arbitrary_files_in_report_folder(self):
        import zipfile
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal=kit.Journal(Path(folder)/'session',identity)
            (journal.folder/'private-photo.txt').write_text('PRIVATE_FILE')
            path=kit.export(journal,'INCOMPLETE','Stopped safely')
            with zipfile.ZipFile(path) as archive:
                self.assertNotIn('private-photo.txt',archive.namelist())
                self.assertNotIn('private-photo.txt',json.loads(archive.read('manifest.json'))['files_sha256'])

class ResumeLoopbackTests(LoopbackFixture,unittest.TestCase):
    def test_completed_cases_resume_without_repeating_requests_or_measurements(self):
        from unittest.mock import patch
        with patch('builtins.input',self.restart_ipad):
            self.device.restart('A1','BASELINE8');self.device.performance('A1')
        original_calls=self.state['calls']
        kit.export(self.journal,'INCOMPLETE','Stopped between completed cases')
        restored=kit.Journal(self.journal.folder,self.identity,resume=True)
        resumed=kit.DeviceRun(restored,self.identity,self.device.base,'PRIVATE_KEY',timeout=5,restart_timeout=2)
        with patch('builtins.input',self.restart_ipad): verdict,metrics=resumed.execute()
        self.assertEqual(verdict,'PASS');self.assertEqual(len(restored.state['measurements']),18)
        self.assertEqual(self.state['calls'],63)
        self.assertEqual(original_calls,7)
        self.assertEqual(len(self.state['arms']),3)

    def test_missing_completed_regression_can_never_produce_pass(self):
        from unittest.mock import patch
        with patch('builtins.input',self.restart_ipad): verdict,metrics=self.device.execute()
        self.assertEqual(verdict,'PASS')
        missing=self.journal.completed('A1.strict_sse')
        self.journal.state['events']=[x for x in self.journal.state['events'] if x['case']!='A1.strict_sse']
        calls=self.state['calls']
        resumed=kit.DeviceRun(self.journal,self.identity,self.device.base,'PRIVATE_KEY',timeout=5,restart_timeout=2)
        verdict,metrics=resumed.execute()
        self.assertEqual(verdict,'INCOMPLETE')
        self.assertEqual(self.state['calls'],calls)
        self.journal.state['events'].append(missing)
        self.journal.completed('B.max_output_tokens_gt256')['observation']['tokens_per_second']=None
        verdict,metrics=resumed.execute()
        self.assertEqual(verdict,'INCOMPLETE');self.assertEqual(self.state['calls'],calls)

    def test_scheduled_restart_resume_waits_for_new_process_without_resending_post(self):
        from unittest.mock import patch
        with patch('builtins.input',self.restart_ipad):
            self.device.restart('A1','BASELINE8');self.device.performance('A1');self.device.regression('A1')
        with patch('builtins.input',side_effect=EOFError):
            with self.assertRaises(EOFError): self.device.restart('B','CANDIDATE16')
        self.assertEqual(len(self.state['arms']),2)
        kit.export(self.journal,'INCOMPLETE','Operator stopped at restart boundary')
        restored=kit.Journal(self.journal.folder,self.identity,resume=True)
        resumed=kit.DeviceRun(restored,self.identity,self.device.base,'PRIVATE_KEY',timeout=5,restart_timeout=2)
        with patch('builtins.input',self.restart_ipad): verdict,metrics=resumed.execute()
        self.assertEqual(verdict,'PASS');self.assertEqual(len(self.state['arms']),3)
        self.assertEqual(self.state['calls'],63)
        self.assertEqual(len(restored.state['measurements']),18)

class FinalGateTests(unittest.TestCase):
    def test_batch_threads_swa_and_tensor_backend_proofs_are_required(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        for field in ('threads_batch','swa_full','metal_tensor_disabled'):
            bad=evidence();bad['native_context'].pop(field)
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad,identity,8)

    def test_native_flag_values_cannot_export_untrusted_diagnostic_strings(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        for field in ('flash_attention','offload_kqv','op_offload','mmap','kv_unified'):
            bad=evidence();bad['native_context'][field]='PRIVATE_PATH'
            with self.assertRaises(kit.Incomplete): kit.validate_evidence(bad,identity,8)

    def test_latest_checkpoint_never_skips_an_uncertain_run(self):
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            older=kit.Journal(Path(folder)/'B16-old',identity)
            newer=kit.Journal(Path(folder)/'B16-new',identity);newer.begin('A1.nonstream')
            selected=kit.latest_checkpoint(folder)
            self.assertEqual(selected,newer.folder)
            with self.assertRaises(kit.Incomplete): kit.Journal(selected,identity,resume=True)


class WindowsCheckpointTests(unittest.TestCase):
    def test_transient_atomic_replace_sharing_error_retries_locally_with_unique_staging(self):
        from unittest.mock import patch
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal=kit.Journal(Path(folder),identity)
            original=Path.replace;attempts=[]
            def sharing_once(path,target):
                attempts.append(path.name)
                if len(attempts)==1: raise PermissionError(13,'Simulated Windows sharing violation')
                return original(path,target)
            with patch.object(Path,'replace',sharing_once): journal.stage('A1_restart')
            self.assertEqual(len(attempts),2)
            self.assertNotEqual(attempts[0],'checkpoint.tmp')
            self.assertEqual(json.loads(journal.path.read_text())['stage'],'A1_restart')

    def test_exhausted_checkpoint_replace_fails_closed_and_keeps_last_durable_state(self):
        from unittest.mock import patch
        identity={'build_number':'111','source_git_sha':'a'*40}
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parents[2])) as folder:
            journal=kit.Journal(Path(folder),identity)
            with patch.object(Path,'replace',side_effect=PermissionError(13,'PRIVATE_WINDOWS_PATH')) as replace:
                with self.assertRaises(kit.Incomplete) as raised: journal.begin('A1.nonstream')
            self.assertNotIn('PRIVATE_WINDOWS_PATH',str(raised.exception))
            self.assertGreater(replace.call_count,1);self.assertLessEqual(replace.call_count,8)
            self.assertIsNone(json.loads(journal.path.read_text())['inflight'])


class SustainedDecodeTests(unittest.TestCase):
    def test_actual_long_output_cases_pass_and_short_decode_is_descriptive(self):
        self.assertIsNotNone(getattr(kit,'sustained_decode_verdict',None))
        status,metrics=kit.sustained_decode_verdict(decode_records())
        self.assertEqual(status,'PASS');self.assertEqual(metrics['cases_per_arm'],4)
        self.assertEqual(metrics['median_tokens_per_second']['B'],20)

    def test_missing_long_decode_and_short_only_never_pass(self):
        self.assertIsNotNone(getattr(kit,'sustained_decode_verdict',None))
        for rows in ([],decode_records()[:-1]):
            self.assertEqual(kit.sustained_decode_verdict(rows)[0],'INCOMPLETE')
        rows=decode_records();rows[0]['observation']['completion_tokens']=256
        self.assertEqual(kit.sustained_decode_verdict(rows)[0],'INCOMPLETE')

    def test_decode_regression_and_baseline_drift_gate_actual_sustained_tokens(self):
        self.assertIsNotNone(getattr(kit,'sustained_decode_verdict',None))
        rows=decode_records()
        for row in rows:
            if row['case'].startswith('B.'):row['observation']['tokens_per_second']=18
        self.assertEqual(kit.sustained_decode_verdict(rows)[0],'FAIL')
        rows=decode_records()
        for row in rows:
            if row['case'].startswith('A2.'):row['observation']['tokens_per_second']=23
        self.assertEqual(kit.sustained_decode_verdict(rows)[0],'INCOMPLETE')

    def test_case_usage_finish_quality_and_payload_identity_are_bound(self):
        self.assertIsNotNone(getattr(kit,'sustained_decode_verdict',None))
        for change in ({'semantic_validated':False},{'finish_reason':'error'},
                       {'request_sha256':'e'*64}):
            rows=decode_records();rows[4].update(change)
            self.assertEqual(kit.sustained_decode_verdict(rows)[0],'INCOMPLETE')
        rows=decode_records();rows[4]['observation']['completion_tokens']=399
        self.assertEqual(kit.sustained_decode_verdict(rows)[0],'INCOMPLETE')

class StreamTimingTests(unittest.TestCase):
    def test_first_event_includes_connection_and_header_delay(self):
        from unittest.mock import patch
        moment=[10.0]
        rows=[{'choices':[{'delta':{'content':'ONE '},'finish_reason':None}]},
              {'choices':[{'delta':{'content':'TWO'},'finish_reason':None}]},
              {'choices':[{'delta':{},'finish_reason':'stop'}]},
              {'choices':[],'usage':{'prompt_tokens':250,'completion_tokens':10}}]
        wire=['data: '+json.dumps(row)+'\n\n' for row in rows]+['data: [DONE]\n\n']
        class Response:
            status=200;headers={'Content-Type':'text/event-stream'}
            def __init__(self):self.lines=iter(x.encode() for x in wire)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def readline(self):return next(self.lines,b'')
        class Opener:
            def open(self,*args,**kwargs):moment[0]+=5;return Response()
        device=kit.DeviceRun(None,{'build_number':'111','source_git_sha':'a'*40},'http://fixture','key')
        with patch.object(kit.urllib.request,'build_opener',return_value=Opener()),patch.object(kit.time,'monotonic',side_effect=lambda:moment[0]):
            result,first=device.stream({'stream':True},'fixture')
        self.assertEqual(first,5.0)

if __name__ == '__main__': unittest.main()
