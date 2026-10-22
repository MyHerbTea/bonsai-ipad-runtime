import unittest
from test_abba_measurement import runner, rounds
from measurement import target_pass, ALIASES


class ThresholdTests(unittest.TestCase):
    def test_decode_threshold_does_not_inherit_balanced_prefill_gate(self):
        for gain,expected in [(2.99,False),(3.,True),(4.3,True)]:
            result=runner.compare_abba(rounds(gain=gain,prefill=-10),2)
            self.assertEqual(result['status']=='PERFORMANCE_PASS',expected)
        self.assertNotEqual(runner.compare_abba(rounds(prefill=-10.01),2)['status'],'PERFORMANCE_PASS')

    def test_prefill_and_balanced_guardrails(self):
        gain={'prefill_s':5.,'decode_tps':-10.,'ttft_s':0.,'client_first_content_s':0.}
        self.assertTrue(target_pass(gain,1))
        self.assertFalse(target_pass(dict(gain,decode_tps=-10.01),1))
        gain.update(prefill_s=15,decode_tps=-5,ttft_s=10,client_first_content_s=10)
        self.assertTrue(target_pass(gain,4))
        self.assertFalse(target_pass(dict(gain,ttft_s=9.99),4))

    def test_levels_and_screen_confirmation_are_distinct(self):
        for gain,level in [(1.99,'NO_BENEFIT'),(2.,'MINOR'),(4.99,'MINOR'),(5.,'MODERATE'),(14.99,'MODERATE'),(15.,'SIGNIFICANT')]:
            self.assertEqual(runner.compare_abba(rounds(gain=gain),2)['benefit_level'],level)
        result=runner.compare_abba(rounds(gain=0,count=1),2,screen=True)
        self.assertEqual(result['evidence_status'],'SHORT_SCREEN_NO_BENEFIT')
        self.assertEqual(runner.compare_abba(rounds(gain=0),2)['evidence_status'],'CONFIRMED_NO_BENEFIT')

    def test_candidate_aliases_keep_stable_masks(self):
        self.assertEqual(ALIASES['PTQ1_MV_R5'],ALIASES['PTQ1_FUSED_KERNEL'])
        self.assertEqual(ALIASES['PTQ1_BATCH_REUSE'],ALIASES['PTQ1_LOW_OVERHEAD'])
        self.assertEqual(ALIASES.get('unknown'),None)

if __name__=='__main__':unittest.main()
