from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[2]

class SymbolTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'tools/build117_symbols.py'
        self.assertTrue(path.exists(),'symbol preservation implementation missing')
        spec=importlib.util.spec_from_file_location('symbols',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)

    def test_uuid_architecture_pair_must_match_exactly(self):
        a='UUID: 00000000-0000-0000-0000-000000000001 (arm64) /synthetic/binary'
        b=a.replace('/synthetic/binary','/synthetic/App.dSYM')
        self.assertEqual(self.module.verify_uuids(a,b),{'arm64':'00000000-0000-0000-0000-000000000001'})
        for wrong in [b.replace('000001','000002'),b.replace('arm64','x86_64'),'']:
            with self.assertRaises(ValueError):self.module.verify_uuids(a,wrong)

if __name__=='__main__':unittest.main()
