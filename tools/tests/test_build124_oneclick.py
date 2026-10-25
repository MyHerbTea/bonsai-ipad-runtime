import copy, sys, tempfile, unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/PTQ1_ONECLICK'))
import prefill_compare as q
import ptq1_oneclick as b


def sample(slot, flag, seconds=100, cpu=80000):
    return dict(abba_slot=slot, valid=True, errors=[], actual=dict(flags=flag),
        prefill_s=seconds, ttft_s=seconds+1, client_first_content_s=seconds+1,
        decode_tps=10, prompt_tokens=512, generated_tokens=128, effective_max_tokens=128,
        finish_reason='length', output_sha256='same', logits_probe=dict(sample=[1.0],top1=0),
        request_id='req', profile=dict(request_id='req',completed=True,
            cpu_ptq1_sampling=dict(available=True,counting_on=False,sampling_enabled=False,sample_period=0),
            cpu_prefill_timing=dict(available=True,ptq1_matmul_ms=cpu,node_counts=[1,0,0,0]),
            gpu_execution_ms=None,gpu_time_source='unavailable'), counting='off',sampling_period=0)

class SDOTOneclickTests(unittest.TestCase):
    def test_request_binding_modes_and_exact_tokens_fail_closed(self):
        s=sample('B1',64)
        self.assertEqual(q.validate_sdot_sample(s,'req'),[])
        cases=[('request_id','old'),('prompt_tokens',511),('counting','on'),('effective_max_tokens',127)]
        for k,v in cases:
            t=copy.deepcopy(s);t[k]=v
            self.assertTrue(q.validate_sdot_sample(t,'req'),k)
        for k,v in [('request_id','stale'),('completed',False),('cpu_ptq1_sampling',{}),('cpu_prefill_timing',{})]:
            t=copy.deepcopy(s);t['profile'][k]=v
            self.assertTrue(q.validate_sdot_sample(t,'req'),k)
        t=copy.deepcopy(s);t['profile']['cpu_ptq1_sampling']['counting_on']=True
        self.assertTrue(q.validate_sdot_sample(t,'req'))
    def row(self, candidate=94):
        return [sample('A1',0),sample('B1',64,candidate,70000),sample('B2',64,candidate,70000),sample('A2',0)]
    def test_relative_decisions_noise_cpu_and_missing_evidence(self):
        self.assertEqual(q.decide_sdot(self.row())['decision'],'KEEP_CANDIDATE_SHORT_CONFIRMATION')
        self.assertEqual(q.decide_sdot(self.row(98))['decision'],'STOP_SDOT_EXPANSION')
        self.assertEqual(q.decide_sdot(self.row(96))['decision'],'UNCERTAIN')
        row=self.row();row[-1]['prefill_s']=114
        self.assertEqual(q.decide_sdot(row)['decision'],'STOP_SDOT_EXPANSION')
        row=self.row();row[1]['profile']['cpu_prefill_timing']={}
        self.assertEqual(q.decide_sdot(row)['decision'],'UNCERTAIN')
        row=self.row();row[2]['valid']=False
        self.assertEqual(q.decide_sdot(row)['status'],'INCOMPLETE')
        self.assertEqual(q.decide_sdot(self.row()[:3])['status'],'INCOMPLETE')
    def test_sequence_exactly_six_and_stops_on_bad_evidence(self):
        for fail in (False,True):
            with tempfile.TemporaryDirectory() as d:
                t=q.SDOTTournament(SimpleNamespace(),{},Path(d));t.capabilities=64;t.save=lambda:None
                t.fit_prompt=lambda target:('synthetic',512);t.thermal=lambda:0
                calls=[]
                def run(config,prompt,target,key,stage,**kw):
                    calls.append((config['flags'],stage,kw.get('max_tokens',128)))
                    s=sample(key.split(':')[-1],config['flags'])
                    s['valid']=not fail
                    t.report['samples'].append(s)
                    return s
                t.run=run
                if fail:
                    with self.assertRaises(b.EvidenceError):t.compare([64],1,512)
                    self.assertEqual(len(calls),1)
                else:
                    t.compare([64],1,512)
                    self.assertEqual([x[0] for x in calls],[0,64,0,64,64,0])
                    self.assertTrue(all(x[2]==128 for x in calls))
                    self.assertEqual(t.report['status'],'QUICK_COMPLETE')
    def test_streaming_request_preserves_counting_off(self):
        client=q.QuickClient('http://127.0.0.1:8080')
        with patch.object(b.Client,'request',return_value={}) as request:
            client.request('run',dict(counting='off'),stream=True)
            self.assertEqual(request.call_args.args[1]['counting'],'off')
    def test_real_run_pipeline_and_unified_zip(self):
        import json, zipfile
        from test_oneclick import sample as full_sample, IDENTITY
        for stale in (False,True):
            with tempfile.TemporaryDirectory() as d:
                client=q.QuickClient('http://127.0.0.1:8080','secret-key')
                client.session='local-session'
                t=q.SDOTTournament(client,IDENTITY,Path(d));t.capabilities=64;t.process='p'
                t.current=t.config();t.thermal=lambda:0;t.fit_prompt=lambda n:('synthetic prompt',512)
                sent=[]
                def api(command,body=None,**kw):
                    if command=='configure':
                        return dict(evidence=dict(native_context=dict(context=16384,batch=8,ubatch=8,kv_k='Q4_0',kv_v='Q4_0',flash_attention=True,sequence_max=1)))
                    self.assertEqual(command,'run');sent.append(body)
                    flag=t.current['flags'];r=full_sample()
                    r['actual'].update(batch=8,ubatch=8,flags=flag)
                    r['evidence']['native_context'].update(batch=8,ubatch=8,flags=flag)
                    r.update(prompt_tokens=512,request_id=body['request_id'],counting=body.get('counting'),sampling_period=0,
                        cpu_dot_abi_available=True,cpu_dot_delta=[0,0,0])
                    r['profile']=sample('',flag)['profile'];r['profile']['request_id']='stale' if stale else body['request_id']
                    return r
                with patch.object(b.Client,'request',side_effect=api):
                    if stale:
                        with self.assertRaises(b.EvidenceError):t.compare([64],1,512)
                        self.assertEqual(len(sent),1)
                    else:
                        t.compare([64],1,512)
                        self.assertEqual(len(sent),6)
                        self.assertTrue(all(x['counting']=='off' for x in sent))
                        self.assertEqual(len({x['request_id'] for x in sent}),6)
                        t.report['restoration']='RESTORED'
                        q.write_comparison(Path(d),t.report);b.write_reports(Path(d),t.report)
                        with zipfile.ZipFile(Path(d)/'results.zip') as z:
                            self.assertIn('COMPARISON.md',z.namelist())
                            self.assertEqual(sum(x.endswith('-request.json') for x in z.namelist()),6)
                            self.assertNotIn('checkpoint.json',z.namelist())
                            self.assertNotIn(b'secret-key',b''.join(z.read(x) for x in z.namelist()))

    def test_native_control_prefix_is_shared_before_sdot_dispatch(self):
        import subprocess
        sys.path.insert(0,str(ROOT/'tools'))
        import rc126_build118_patch_cpu_prefill as p118
        import rc126_build122_patch_sampling as p122
        import rc126_build124_patch_sdot as p124
        native=Path('D:/codexSpace/iPad27B/native-prism')
        if not native.exists():self.skipTest('local pinned source unavailable; CI covers native')
        source=(native/'ggml/src/ggml-cpu/quants.c').read_text(encoding='utf-8')
        if 'BONSAI_SDOT_124' in source:self.skipTest('already patched native')
        result=p124.instrument_quants(source)
        body=result[result.index('void ggml_vec_dot_ptq1_0_q8_0_generic('):]
        self.assertLess(body.index('bonsai_sample_next(n)'),body.index('if (bonsai_flags == 64)'))
        self.assertIn('(bonsai_flags == 0 || bonsai_flags == 64)',body)

if __name__=='__main__':unittest.main()
