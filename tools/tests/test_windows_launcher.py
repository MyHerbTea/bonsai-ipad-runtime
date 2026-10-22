"""Execute the real CMD parser; Python-only tests cannot catch batch truncation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
LAUNCHER=ROOT/'tools/PTQ1_ONECLICK/RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd'

@unittest.skipUnless(os.name=='nt','Actual CMD execution requires Windows')
class WindowsLauncherTests(unittest.TestCase):
    def execute_case(self,script,with_runtime=True):
        scratch=ROOT/'deliveries';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='cmd 中文 空格 (test) ! ',dir=scratch) as folder:
            root=Path(folder).resolve()
            self.assertEqual(root.parent,scratch.resolve())
            launcher=root/LAUNCHER.name;launcher.write_bytes(LAUNCHER.read_bytes())
            if script is not None:(root/'ptq1_oneclick.py').write_text(script,encoding='utf-8')
            runtime=root/'python'
            if with_runtime:
                result=subprocess.run(f'"{os.environ["COMSPEC"]}" /d /c mklink /J "{runtime}" "{Path(sys.executable).parent}"',capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
            try:
                command=f'"{os.environ["COMSPEC"]}" /d /v:off /c call "{launcher}" --help'
                result=subprocess.run(command,input=b'\r\n',capture_output=True,timeout=20)
                out=result.stdout.decode('utf-8','replace');err=result.stderr.decode('utf-8','replace')
                self.assertIn('Press any key to close this window.',out)
                self.assertNotIn('not recognized',err)
                return result.returncode,out,err
            finally:
                # Remove only the junction, not the interpreter directory it targets.
                if with_runtime:
                    self.assertEqual(runtime.parent,root)
                    os.rmdir(runtime)
    def test_success_returns_from_python_and_reaches_pause(self):
        code,out,err=self.execute_case('import sys\nprint("CMD_TEST_RUNNER_OK", sys.argv[1:])\n')
        self.assertEqual(code,0,err);self.assertIn('CMD_TEST_RUNNER_OK',out);self.assertIn('--help',out)
    def test_python_failure_preserves_exit_code_and_pause(self):
        code,out,err=self.execute_case('raise SystemExit(7)\n')
        self.assertEqual(code,7,err);self.assertIn('Exit code: 7',out)
    def test_missing_runtime_reaches_diagnostic_and_pause(self):
        code,out,err=self.execute_case('print("unused")\n',with_runtime=False)
        self.assertEqual(code,2,err);self.assertIn('Missing bundled Python',out)
    def test_missing_script_reaches_diagnostic_and_pause(self):
        code,out,err=self.execute_case(None)
        self.assertEqual(code,2,err);self.assertIn('Missing ptq1_oneclick.py',out)

if __name__=='__main__':unittest.main()
