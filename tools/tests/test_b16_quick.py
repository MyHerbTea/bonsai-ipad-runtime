import unittest, tempfile, json
from pathlib import Path
from unittest.mock import patch
from tools import b16_testkit as kit

class QuickTests(unittest.TestCase):
    def test_cli_defaults_full_and_quick_registration(self):
        with patch('builtins.print') as output:
            self.assertEqual(kit.run(['--dry-run']),0)
        full=json.loads(output.call_args.args[0])
        self.assertIn('strict_sse',full['regressions'])
        with patch('builtins.print') as output:
            self.assertEqual(kit.run(['--dry-run','--mode','quick']),0)
        quick=json.loads(output.call_args.args[0])
        self.assertEqual(quick['direction'],'prefill-batch')
        self.assertFalse(quick['device_certified'])
        self.assertNotIn('strict_sse',quick['regressions'])
        self.assertEqual(quick['samples_per_workload_per_arm'],2)

    def rows(self, ratio=1):
        return [dict(arm=a,workload=w,rep=r,prompt_tokens=600,completion_tokens=12,
                     workload_sha256=w,prefill_ms=100*(ratio if a=='B' else 1),
                     ttft_ms=110*(ratio if a=='B' else 1),tokens_per_second=10)
                for a in ('A1','B','A2') for w in ('medium','long') for r in range(2)]

    def decode(self, ratio=1):
        return [dict(case=a+'.quick_decode.'+str(r),state='PASS',semantic_validated=True,
                     request_sha256='a'*64,finish_reason='stop',observation=dict(prompt_tokens=40,
                     completion_tokens=100,tokens_per_second=10*(ratio if a=='B' else 1)))
                for a in ('A1','B','A2') for r in range(2)]

    def test_exploratory_only_and_decode_guard(self):
        status,metrics=kit.quick_comparison(self.rows(.8),self.decode())
        self.assertEqual(status,'QUICK_COMPLETE')
        self.assertFalse(metrics['default_promoted'])
        self.assertAlmostEqual(metrics['workloads']['long']['prefill_ratio'],.8)
        self.assertEqual(kit.quick_comparison(self.rows(),self.decode(.7))[1]['decode_check'],'OBVIOUS_REGRESSION')
        self.assertEqual(kit.quick_comparison(self.rows()[:-1],self.decode())[0],'INCOMPLETE')
        rows=self.rows();rows[0]['prompt_tokens']=601
        self.assertEqual(kit.quick_comparison(rows,self.decode())[0],'INCOMPLETE')

    def test_sampling_loss_is_limited_quick_only(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            journal=kit.Journal(folder,{'build_number':'111','source_git_sha':'a'*40})
            run=kit.QuickDeviceRun(journal,journal.state['identity'],'http://test','key')
            run.check_sampling({'issue':'MEASUREMENT_UNAVAILABLE','samples':[]})
            with self.assertRaises(kit.Failure):
                run.check_sampling({'issue':'MEMORY_ANOMALY','samples':[]})
            full=kit.DeviceRun(journal,journal.state['identity'],'http://test','key')
            with self.assertRaises(kit.Incomplete):
                full.check_sampling({'issue':'MEASUREMENT_UNAVAILABLE','samples':[]})

    def test_quick_export_never_full_pass(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            journal=kit.Journal(Path(folder)/'run',{'build_number':'111','source_git_sha':'a'*40})
            journal.state['mode']='quick'
            kit.export(journal,'QUICK_COMPLETE','Exploratory only',{})
            report=(journal.folder/'FINAL_REPORT.md').read_text(encoding='utf-8')
            self.assertIn('EXPLORATORY',report)
            self.assertNotIn('EXPERIMENT_PASS',report)
            manifest=json.loads((journal.folder/'manifest.json').read_text(encoding='utf-8'))
            self.assertFalse(manifest['default_promoted'])
            self.assertEqual(manifest['mode'],'quick')

if __name__=='__main__': unittest.main()
