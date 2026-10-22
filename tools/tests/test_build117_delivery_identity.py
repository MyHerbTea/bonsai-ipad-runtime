from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[2]

class DeliveryIdentityTests(unittest.TestCase):
    def test_app_and_ci_build_numbers_match_build117_package(self):
        project=(ROOT/'project.yml').read_text(encoding='utf-8')
        workflow=(ROOT/'.github/workflows/build-ptq1-tournament.yml').read_text(encoding='utf-8')
        app=re.search(r'CURRENT_PROJECT_VERSION:\s*"(\d+)"',project).group(1)
        ci=re.search(r'BUILD_NUMBER:\s*"(\d+)"',workflow).group(1)
        self.assertEqual(app,ci,'IPA/testkit identity must not disagree')
        self.assertEqual(app,'117')

if __name__=='__main__':unittest.main()
