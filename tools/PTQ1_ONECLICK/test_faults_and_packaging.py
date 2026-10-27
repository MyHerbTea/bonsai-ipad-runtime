"""Explicitly synthetic HTTP/packaging fault tests, never device results."""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import ptq1_oneclick as b
from test_oneclick import IDENTITY, CONFIG, sample

class Handler(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*args):pass
    def do_POST(self):
        self.calls.append(self.path)
        self.rfile.read(int(self.headers['Content-Length']))
        if self.path.endswith('/run'):
            # Drop after metadata: inference result is unknown, not a failed request safe to replay.
            data=b'event: meta\ndata: {}\n\n';kind='text/event-stream'
        else:data=json.dumps({'state':{'running':False,'active':True,'cancelled':True}}).encode();kind='application/json'
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        self.calls.append(self.path)
        data=json.dumps({'state':{'running':False,'active':True,'cancelled':True}}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

class IntegrationTests(unittest.TestCase):
    def test_build128_swift_ack_ci_compiles_its_recovery_dependency(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/build-ptq1-tournament.yml").read_text()
        commands = [line for line in workflow.splitlines() if "tools/build128_q8_operator_abort_tests.swift" in line]
        self.assertEqual(len(commands), 1)
        self.assertIn("BonsaiLab/BenchmarkCancellationEvidence.swift", commands[0])
    def test_build128_quick_uses_bounded_first_principles_screen(self):
        import q8_metal_b8
        self.assertEqual(q8_metal_b8.PROMPT_TOKENS, 128)
        self.assertEqual(q8_metal_b8.REQUEST_DEADLINE_S, 60)
        self.assertEqual(q8_metal_b8.TOTAL_DEADLINE_S, 240)

    def test_uncertain_inference_is_cancelled_checkpointed_never_replayed(self):
        Handler.calls=[]
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                client=b.Client('http://127.0.0.1:'+str(server.server_port),'test-key-never-persist')
                client.session='synthetic-session'
                tournament=b.Tournament(client,IDENTITY,Path(d));tournament.current=dict(CONFIG);tournament.process='p'
                with self.assertRaises(b.UncertainRequest):tournament.run(CONFIG,'synthetic prompt',2048,'fault','formal')
                self.assertEqual(Handler.calls.count('/debug/benchmark/run'),1)
                self.assertIn('/debug/benchmark/cancel',Handler.calls)
                checkpoint=json.loads((Path(d)/'checkpoint.json').read_text())
                self.assertIsNotNone(checkpoint['in_flight'])
                self.assertIn(tournament.config_id(CONFIG),checkpoint['blacklist'])
                self.assertNotIn('test-key-never-persist',(Path(d)/'checkpoint.json').read_text())
        finally:server.shutdown();server.server_close();thread.join(2)
    def test_recovery_quarantines_attempted_shape_not_old_marker(self):
        class FakeClient:
            session=None
            def __init__(self):self.calls=[]
            def request(self,command,body=None,**kwargs):
                self.calls.append(command)
                if command=='/health':return {'model':'official'}
                if command=='/v1/models':return {'data':[]}
                if command=='status':return {'state':{'active':False}}
                if command=='capabilities':return {'capabilities':7,'state':{'active':False},'hardware':{'eligible':True},'safe_baseline_backend':True,
                    'evidence':sample()['evidence'],'prior_interrupted':sample()['actual']}
                if command=='start':return {'session_id':'synthetic','capabilities':7}
                raise AssertionError(command)
        for fault_flags in (1,0):
            with self.subTest(fault_flags=fault_flags),tempfile.TemporaryDirectory() as d:
                directory=Path(d);config=dict(CONFIG,flags=fault_flags)
                b.dump(directory/'checkpoint.json',{'source':IDENTITY['source_git_sha'],'model':IDENTITY['official_model']['sha256'],
                    'process_id':'prior-process','in_flight':{'config':config,'key':'uncertain'},'blacklist':[]})
                client=FakeClient();tournament=b.Tournament(client,IDENTITY,directory)
                if fault_flags==0:
                    with self.assertRaises(b.EvidenceError):tournament.prepare()
                    self.assertNotIn('start',client.calls)
                else:
                    self.assertTrue(tournament.prepare())
                    self.assertIn(tournament.config_id(config),tournament.blacklist)
                    self.assertNotIn(tournament.config_id(CONFIG),tournament.blacklist)

    def test_build128_delivery_contains_fixed_q8_metal_b8_and_ack_testkit(self):
        script=Path(__file__).resolve().parents[1]/'package_ptq1_oneclick.py'
        spec=importlib.util.spec_from_file_location('package_build128_under_test',script)
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=root/'build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app';app.mkdir(parents=True)
            (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleVersion':'128'}));(app/'BonsaiLab').write_bytes(b'synthetic executable')
            tools=root/'tools';kit=tools/'PTQ1_ONECLICK';kit.mkdir(parents=True)
            for name in ('RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd','RUN_Q8_METAL_B8_QUICK.cmd','RUN_Q8_BASELINE.cmd','RUN_Q8_FULL.cmd','RUN_Q8_ACKNOWLEDGE.cmd'):
                (kit/name).write_bytes(b'@echo off\necho synthetic\npause\n')
            for name in ('ptq1_oneclick.py','kv_baseline.py','q8_metal_b8.py','README_BUILD128_CN.md','acknowledge_q8_interruption.py'):
                (kit/name).write_text('synthetic test')
            (tools/'ptq1_official_model.json').write_text(json.dumps(IDENTITY['official_model']))
            for name in ('CI_TESTS.txt','BUILD128_POLICY.txt','BUILD128_TESTS.txt','build.log','llama-symbols.txt','app-symbols.txt','SYMBOL_IDENTITY.json'):
                (root/'build'/name).write_text('SYNTHETIC TEST FIXTURE')
            (root/'build/Bonsai-Build128-Symbols.zip').write_bytes(b'SYNTHETIC SYMBOL ARTIFACT')
            for name in ('docs/superpowers/specs/2026-10-27-build128-q8-performance-enablement.md',
                         'docs/superpowers/plans/2026-10-27-build128-q8-performance.md',
                         'tools/PTQ1_ONECLICK/README_BUILD128_CN.md'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic source audit')
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                for name in ('python.exe','python312.dll','python312.zip','_ssl.pyd','LICENSE.txt'):archive.writestr(name,b'synthetic')
            data=stream.getvalue()
            env={'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'128','PRISM_COMMIT':'d'*40,
                 'GITHUB_REF_NAME':'codex/build128-q8-performance','BUILD_NUMBER':'128'}
            with patch.object(package,'ROOT',root),patch.object(package,'PYTHON_SHA',hashlib.sha256(data).hexdigest()),patch.object(package.urllib.request,'urlopen',return_value=contextlib.closing(io.BytesIO(data))),patch.dict(os.environ,env):
                package.build()
            full=root/'build/delivery/BONSAI_BUILD128_PTQ1_ONECLICK.zip'
            standalone=root/'build/delivery/BONSAI_BUILD128_Q8_TESTKIT.zip'
            with zipfile.ZipFile(full) as archive:
                self.assertIsNone(archive.testzip())
                names=archive.namelist()
                prefix='Bonsai-Build128-PTQ1/'
                self.assertIn(prefix+'RUN_Q8_METAL_B8_QUICK.cmd',names)
                self.assertIn(prefix+'RUN_Q8_ACKNOWLEDGE.cmd',names)
                self.assertNotIn(prefix+'RUN_Q8_BASELINE.cmd',names)
                self.assertNotIn(prefix+'RUN_Q8_FULL.cmd',names)
                self.assertEqual(len([n for n in names if n.endswith('.ipa')]),1)
                identity=json.loads(archive.read(prefix+'TestKitIdentity.json'))
                self.assertEqual(identity['acknowledge_failure_source_shas'],['2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158'])
                build_info=archive.read(prefix+'BUILD_INFO.txt').decode()
                delivery_report=archive.read(prefix+'BUILD128_DELIVERY_REPORT_CN.md').decode()
                self.assertIn('128-token',build_info)
                self.assertIn('240 seconds',build_info)
                self.assertIn('128输入/32输出',delivery_report)
                self.assertIn('240秒',delivery_report)
                self.assertNotIn('512-token input',build_info)
                self.assertNotIn('总时限10分钟',delivery_report)
            with zipfile.ZipFile(standalone) as archive:
                self.assertIsNone(archive.testzip())
                names=archive.namelist()
                self.assertTrue(any(n.endswith('q8_metal_b8.py') for n in names))
                self.assertTrue(any(n.endswith('README_BUILD128_CN.md') for n in names))
                self.assertTrue(any(n.endswith('RUN_Q8_METAL_B8_QUICK.cmd') for n in names))
                self.assertTrue(any(n.endswith('RUN_Q8_ACKNOWLEDGE.cmd') for n in names))
                self.assertFalse(any(n.endswith('.ipa') for n in names))

    def test_delivery_contains_one_ipa_portable_runtime_and_identity(self):
        script=Path(__file__).resolve().parents[1]/'package_ptq1_oneclick.py'
        spec=importlib.util.spec_from_file_location('package_under_test',script)
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=root/'build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app';app.mkdir(parents=True)
            (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleVersion':'118'}));(app/'BonsaiLab').write_bytes(b'synthetic executable')
            tools=root/'tools';kit=tools/'PTQ1_ONECLICK';kit.mkdir(parents=True)
            (kit/'RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd').write_bytes(b'@echo off\necho synthetic test\npause\n')
            (kit/'ptq1_oneclick.py').write_text('# synthetic test')
            (tools/'ptq1_official_model.json').write_text(json.dumps(IDENTITY['official_model']))
            for name in ('CI_TESTS.txt','build.log','llama-symbols.txt','app-symbols.txt','SYMBOL_IDENTITY.json'):(root/'build'/name).write_text('SYNTHETIC TEST FIXTURE')
            (root/'build/Bonsai-Build118-Symbols.zip').write_bytes(b'SYNTHETIC SYMBOL ARTIFACT')
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                for name in ('python.exe','python312.dll','python312.zip','_ssl.pyd','LICENSE.txt'):archive.writestr(name,b'synthetic')
            data=stream.getvalue()
            with patch.object(package,'ROOT',root),patch.object(package,'PYTHON_SHA',hashlib.sha256(data).hexdigest()),patch.object(package.urllib.request,'urlopen',return_value=contextlib.closing(io.BytesIO(data))),patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'1','PRISM_COMMIT':'d'*40,'BUILD_NUMBER':'118'}):
                package.build()
            output=root/'build/delivery/BONSAI_BUILD118_PTQ1_ONECLICK.zip'
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                launcher=archive.read('Bonsai-Build118-PTQ1/RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd')
                self.assertNotIn(b'\n',launcher.replace(b'\r\n',b''),'Windows CMD must be packaged with CRLF')
                self.assertFalse(launcher.startswith(b'\xef\xbb\xbf'))
                self.assertEqual(len([n for n in archive.namelist() if n.endswith('.ipa')]),1)
                identity=json.loads(archive.read('Bonsai-Build118-PTQ1/TestKitIdentity.json'))
                self.assertEqual(identity['device_validation'],'NOT_RUN')
                self.assertEqual(identity['source_git_sha'],'a'*40)
                self.assertIn('Bonsai-Build118-PTQ1/CI_EVIDENCE/SYMBOL_IDENTITY.json',archive.namelist())
                self.assertEqual(identity['symbols_artifact']['sha256'],hashlib.sha256(b'SYNTHETIC SYMBOL ARTIFACT').hexdigest())
if __name__=='__main__':unittest.main()
