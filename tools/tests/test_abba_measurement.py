"""Synthetic observations; no device performance claim."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'PTQ1_ONECLICK'))
import ptq1_oneclick as runner
from test_oneclick import sample, IDENTITY


def rounds(gain=4.3, prefill=-2., count=5):
    records=[]
    for r in range(count):
        row=[]
        for slot in ('A1','B1','B2','A2'):
            s=sample(2 if slot.startswith('B') else 0)
            s.update(abba_round=str(r), abba_slot=slot, repeat=r,
                     config=runner.Tournament.config(s['actual']['flags']), thermal_before=0)
            if slot.startswith('B'):
                s['decode_tps']*=1+gain/100
                s['prefill_s']*=1-prefill/100
            row.append(s)
        records.append(row)
    return records


class ABBATests(unittest.TestCase):
    def test_decode_target_and_minor_are_separate_from_promotion(self):
        self.assertTrue(hasattr(runner, 'compare_abba'), 'ABBA comparison missing')
        result=runner.compare_abba(rounds(), 2)
        self.assertEqual(result['status'], 'PERFORMANCE_PASS')
        self.assertEqual(result['benefit_level'], 'MINOR')
        self.assertAlmostEqual(result['decode_change_pct'],4.3)
        self.assertEqual(result['valid_rounds'],5)
        self.assertGreater(result['statistics']['decode_tps']['ci95'][0],0)

    def test_unknown_values_and_mismatches_cannot_pass(self):
        self.assertTrue(hasattr(runner, 'compare_abba'), 'ABBA comparison missing')
        for key,value in [('decode_tps',float('nan')),('prefill_s',0),('prompt_hash','different')]:
            rows=rounds();rows[0][1][key]=value
            self.assertEqual(runner.compare_abba(rows,2)['status'],'INCOMPLETE')
        self.assertEqual(runner.compare_abba(rounds(count=1),2)['status'],'INCOMPLETE')

    def test_abba_collection_warms_every_slot_twice_and_never_reuses_partial_round(self):
        with __import__('tempfile').TemporaryDirectory() as directory:
            t=runner.Tournament(None,IDENTITY,Path(directory));calls=[]
            t.fit_prompt=lambda target:('synthetic',target)
            t.switch=lambda config:None
            t.save=lambda:None
            t.thermal=lambda:0
            def run(config,prompt,target,key,stage,max_tokens=128,**kw):
                calls.append((config['flags'],stage,max_tokens,key))
                s=sample(config['flags']);s['config']=config;s['valid']=True
                return s
            t.run=run
            self.assertTrue(hasattr(t,'abba'), 'ABBA collector missing')
            row=t.abba(t.config(2),'screen',0,512)
            self.assertEqual([s['abba_slot'] for s in row],['A1','B1','B2','A2'])
            self.assertEqual([f for f,stage,_,_ in calls if stage=='screen'],[0,2,2,0])
            self.assertEqual([n for _,stage,n,_ in calls if stage=='warmup'],[256]*8)
            self.assertEqual(len({k for *_,k in calls}),12)


if __name__=='__main__':unittest.main()
