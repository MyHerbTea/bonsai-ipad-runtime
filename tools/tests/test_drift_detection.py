import copy
import unittest
from test_abba_measurement import runner, rounds


class DriftTests(unittest.TestCase):
    def test_strict_drift_boundaries(self):
        self.assertTrue(hasattr(runner,'analyze_abba_round'), 'drift analysis missing')
        for drift,status in [(5.,'STABLE'),(5.01,'DRIFT_DETECTED'),(10.,'DRIFT_DETECTED'),(10.01,'UNSTABLE')]:
            row=rounds(count=1)[0];row[3]['prefill_s']*=1+drift/100
            self.assertEqual(runner.analyze_abba_round(row)['status'],status)

    def test_one_bad_or_thermal_round_prevents_confirmation(self):
        self.assertTrue(hasattr(runner,'compare_abba'), 'ABBA comparison missing')
        rows=rounds();rows[0][3]['decode_tps']*=1.11
        self.assertEqual(runner.compare_abba(rows,2)['status'],'INCOMPLETE')
        rows=rounds();rows[0][1]['thermal_before']=2
        self.assertEqual(runner.compare_abba(rows,2)['status'],'INCOMPLETE')


if __name__=='__main__':unittest.main()
