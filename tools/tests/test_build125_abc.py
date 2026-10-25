import copy,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/PTQ1_ONECLICK'))
import prefill_compare as q
import ptq1_oneclick as b
from test_build124_oneclick import sample

class ABCTests(unittest.TestCase):
    def row(self):
        return [sample(slot,flag,seconds,cpu) for slot,flag,seconds,cpu in [('A1',0,110,35000),('B1',64,90,26000),('C1',128,89,25000),('C2',128,89,25000),('B2',64,90,26000),('A2',0,110,35000)]]
    def test_compare_pair_to_build124_not_original(self):
        r=q.decide_abc(self.row())
        self.assertEqual(r['PAIR_VS_BUILD124']['decision'],'STOP_CPU_MICROKERNEL_DIRECTION')
        row=self.row()
        for s in row:
            if s['actual']['flags']==128:
                s['prefill_s']=83;s['profile']['cpu_prefill_timing']['ptq1_matmul_ms']=20000
        r=q.decide_abc(row)
        self.assertEqual(r['PAIR_VS_BUILD124']['decision'],'PAIR_WORTH_RETAINING_USER_DECISION')
        self.assertNotIn('30%',r['PAIR_VS_BUILD124']['next_engine_step'])
    def test_candidate_path_proof_required_and_exclusive(self):
        s=sample('C1',128);s['profile']['cpu_ptq1_sampling'].update(pair_chunks=1,pair_rows=2)
        self.assertEqual(q.validate_pair_sample(s),[])
        for key in ['pair_chunks','pair_rows']:
            bad=copy.deepcopy(s);bad['profile']['cpu_ptq1_sampling'][key]=0
            self.assertTrue(q.validate_pair_sample(bad))
        s['actual']['flags']=64
        self.assertTrue(q.validate_pair_sample(s))
    def test_real_nine_request_pipeline_and_missing_pair_proof(self):
        from test_oneclick import sample as full_sample, IDENTITY
        from unittest.mock import patch
        for missing in (False,True):
            with tempfile.TemporaryDirectory() as d:
                client=q.QuickClient('http://127.0.0.1:8080');client.session='synthetic'
                t=q.ABCTournament(client,IDENTITY,Path(d));t.capabilities=255;t.process='p';t.current=t.config()
                t.fit_prompt=lambda n:('synthetic',512);t.thermal=lambda:0;sent=[]
                def api(command,body=None,**kwargs):
                    if command=='configure':
                        return dict(evidence=dict(native_context=dict(context=16384,batch=8,ubatch=8,kv_k='Q4_0',kv_v='Q4_0',flash_attention=True,sequence_max=1)))
                    self.assertEqual(command,'run');sent.append(body)
                    r=full_sample();flag=t.current['flags']
                    r['actual'].update(flags=flag,batch=8,ubatch=8);r['evidence']['native_context'].update(flags=flag,batch=8,ubatch=8)
                    r.update(prompt_tokens=512,request_id=body['request_id'],counting=body.get('counting'),sampling_period=0,cpu_dot_delta=[0,0,0],cpu_dot_abi_available=True)
                    r['profile']=sample('',flag)['profile'];r['profile']['request_id']=body['request_id']
                    hit=flag==128 and not missing
                    r['profile']['cpu_ptq1_sampling'].update(pair_chunks=1 if hit else 0,pair_rows=2 if hit else 0)
                    return r
                with patch.object(b.Client,'request',side_effect=api):
                    if missing:
                        with self.assertRaises(b.EvidenceError):t.compare([0,64,128],1,512)
                        self.assertEqual(len(sent),3)
                    else:
                        t.compare([0,64,128],1,512)
                        self.assertEqual(len(sent),9)
                        self.assertTrue(all(x['counting']=='off' for x in sent))
                        self.assertEqual(t.report['status'],'QUICK_COMPLETE')
    def test_missing_capability_stops_before_start(self):
        class Client:
            def request(self,command,**kwargs):
                if command!='capabilities':raise AssertionError('unexpected mutation')
                return {'capabilities':64}
        with tempfile.TemporaryDirectory() as d:
            t=q.ABCTournament(Client(),{},Path(d))
            with self.assertRaises(b.EvidenceError):t.prepare()

    def test_nine_requests_exact_order_and_fail_closed(self):
        for bad in [False,True]:
            with tempfile.TemporaryDirectory() as d:
                t=q.ABCTournament(SimpleNamespace(),{},Path(d));t.capabilities=255;t.save=lambda:None
                t.fit_prompt=lambda n:('synthetic',512);t.thermal=lambda:0
                calls=[]
                def run(config,prompt,target,key,stage,**kwargs):
                    slot=key.split(':')[-1];calls.append(slot)
                    s=sample(slot,config['flags']);s['valid']=not bad
                    t.report['samples'].append(s);return s
                t.run=run
                if bad:
                    with self.assertRaises(b.EvidenceError):t.compare([0,64,128],1,512)
                    self.assertEqual(len(calls),1)
                else:
                    t.compare([0,64,128],1,512)
                    self.assertEqual(calls,['warm_A','warm_B','warm_C','A1','B1','C1','C2','B2','A2'])
                    self.assertEqual(t.report['status'],'QUICK_COMPLETE')
                    self.assertFalse(t.report['automatic_promotion'])
if __name__=='__main__':unittest.main()
