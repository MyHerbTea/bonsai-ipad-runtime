import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/PTQ1_ONECLICK'))
import ptq1_oneclick as b
from test_oneclick import IDENTITY, sample


class RecoveryProofTests(unittest.TestCase):
    def test_progress_does_not_count_as_first_content(self):
        raw=b'event: meta\ndata: {}\n\nevent: progress\ndata: {"progress":{"stage":"PREFILL","completed":8,"total":512}}\n\nevent: delta\ndata: {"content":"answer"}\n\nevent: result\ndata: {}\n\n'
        times=iter([.1,.2,1.,2.]);events=[]
        result=b.read_sse(io.BytesIO(raw),0,clock=lambda:next(times),observer=lambda event,data:events.append(event))
        self.assertEqual(result['client_first_content_s'],1.)
        self.assertEqual(events,['meta','progress','delta','result'])

    def test_new_idle_process_never_claims_original_session_restored(self):
        class Client:
            session='old-session'
            def request(self,*args,**kwargs):return {'state':{'active':False},'evidence':dict(sample()['evidence'],process_id='new-process')}
        with tempfile.TemporaryDirectory() as directory:
            t=b.Tournament(Client(),IDENTITY,Path(directory));t.process='old-process';t.original_runtime=sample()['evidence']['native_context']
            t.restore()
            self.assertEqual(t.report['status'],'INCOMPLETE')
            self.assertNotEqual(t.report['restoration'],'RESTORED')

    def test_inactive_same_process_requires_matching_actual_configuration(self):
        class Client:
            session='old-session'
            def __init__(self,evidence):self.evidence=evidence
            def request(self,*args,**kwargs):return {'state':{'active':False},'evidence':self.evidence}
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                original=sample()['evidence']['native_context']
                evidence=json.loads(json.dumps(sample()['evidence']))
                if changed:evidence['native_context']['batch']=8
                t=b.Tournament(Client(evidence),IDENTITY,Path(directory));t.process='p';t.original_runtime=original
                t.restore()
                self.assertEqual(t.report['restoration']=='RESTORED',not changed)

if __name__=='__main__':unittest.main()
