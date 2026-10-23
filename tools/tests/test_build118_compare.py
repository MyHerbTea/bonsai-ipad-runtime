import copy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/PTQ1_ONECLICK'))
import ptq1_oneclick as runner
import prefill_compare as quick
from test_oneclick import sample, IDENTITY


class QuickComparisonTests(unittest.TestCase):
    def test_quick_start_is_explicit_and_b8(self):
        client=quick.QuickClient('http://127.0.0.1:8080')
        with patch.object(runner.Client,'request',return_value={}) as request:
            client.request('start',{},timeout=12)
            request.assert_called_once_with('start',{'mode':'quick_prefill'},timeout=12)
        self.assertEqual(quick.QuickTournament.config()['batch'],8)
        self.assertEqual(runner.Tournament.config()['batch'],16)

    def test_cpu_candidate_requires_real_hits_and_exclusive_branch(self):
        s=sample(0);s['actual']['flags']=8
        config=runner.Tournament.config(8)
        s['cpu_dot_abi_available']=True;s['cpu_dot_delta']=[0,100,0]
        self.assertNotIn('cpu_candidate_not_observed',runner.validate_sample(s,config,IDENTITY))
        for counters in ([100,0,0],[0,0,0],[0,100,2],[-1,100,0],[]):
            s['cpu_dot_delta']=counters
            self.assertIn('cpu_candidate_not_observed',runner.validate_sample(s,config,IDENTITY))

    def test_quick_old_pending_blocks_before_any_start(self):
        class Client:
            def request(self,command,**kwargs):
                if command!='capabilities':raise AssertionError('unexpected mutation')
                return {'quick_prior_interrupted':{'batch':8}}
        with tempfile.TemporaryDirectory() as d:
            t=quick.QuickTournament(Client(),IDENTITY,Path(d))
            with self.assertRaisesRegex(runner.EvidenceError,'PREVIOUS_INTERRUPTED'):t.prepare()

    def test_unknown_request_retains_quarantine_even_when_restore_succeeds(self):
        client=quick.QuickClient('http://127.0.0.1:8080')
        with patch.object(runner.Client,'request',side_effect=runner.UncertainRequest('UNKNOWN')):
            with self.assertRaises(runner.UncertainRequest):client.request('run',{'prompt':'synthetic'})
        with patch.object(runner.Client,'request',return_value={}) as request:
            client.request('restore',{})
            request.assert_called_once_with('restore',{'preserve_interrupted':True})

    def test_all_candidates_measured_in_one_report_without_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            t=quick.QuickTournament(None,IDENTITY,Path(d));t.capabilities=31;t.save=lambda:None
            def abba(config,stage,index,target):
                row=[]
                for slot in ('A1','B1','B2','A2'):
                    flag=config['flags'] if slot.startswith('B') else 0
                    s=sample(0);s['actual']['flags']=flag
                    s.update(config=t.config(flag),abba_slot=slot,abba_round='one',thermal_before=0,valid=True)
                    row.append(s)
                return row
            t.abba=abba;t.compare([4,8,16],1,512)
            self.assertEqual(t.report['status'],'QUICK_COMPLETE')
            self.assertEqual(len(t.report['comparisons']),3)
            self.assertFalse(t.report['automatic_promotion'])
            self.assertTrue(all(x['status']=='QUICK_MEASURED' for x in t.report['comparisons'].values()))
            quick.write_comparison(Path(d),t.report)
            self.assertIn('PTQ1_CPU_NEON',(Path(d)/'COMPARISON.md').read_text(encoding='utf-8'))

    def test_unknown_outcome_stops_before_next_candidate_without_replay(self):
        with tempfile.TemporaryDirectory() as d:
            t=quick.QuickTournament(None,IDENTITY,Path(d));t.capabilities=31
            calls=[]
            def uncertain(*args):calls.append(args);raise runner.UncertainRequest('REQUEST_OUTCOME_UNKNOWN')
            t.abba=uncertain
            with self.assertRaises(runner.UncertainRequest):t.compare([4,8,16],1,512)
            self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
