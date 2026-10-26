from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class Build126Q8RecoveryContractTests(unittest.TestCase):
    def test_api_acknowledgement_is_a_separate_locked_command(self):
        manager = (ROOT / "BonsaiLab/BenchmarkSessionManager.swift").read_text(encoding="utf-8")
        server = (ROOT / "BonsaiLab/LocalOpenAIServer.swift").read_text(encoding="utf-8")
        self.assertIn('if command == "acknowledge_q8_interruption"', manager)
        self.assertIn('engine.acknowledgeQ8Interruption(body)', manager)
        self.assertIn('control.beginSession()', manager[manager.index('if command == "acknowledge_q8_interruption"'):])
        self.assertIn('"acknowledge_q8_interruption"', server)

    def test_engine_requires_idle_loaded_production_context_and_audit_receipt(self):
        engine = (ROOT / "BonsaiLab/BonsaiEngine.swift").read_text(encoding="utf-8")
        method = engine[engine.index("func acknowledgeQ8Interruption"):engine.index("func benchmarkStart")]
        self.assertIn("benchmarkOriginal == nil", method)
        self.assertIn("native_context", method)
        self.assertIn("BenchmarkInterruptionRecovery.acknowledgeQ8", method)
        self.assertIn('"audit_readback_verified":true', method)
        self.assertIn('"inference_launched":false', method)


    def test_q8_quarantine_is_removed_only_after_durable_readback(self):
        recovery = (ROOT / "BonsaiLab/BenchmarkInterruptionRecovery.swift").read_text(encoding="utf-8")
        method = recovery[recovery.index("static func acknowledgeQ8"):recovery.index("private static func isSHA256")]
        self.assertLess(method.index("saveAudit("), method.index("readAudit(audit)"))
        self.assertLess(method.index("readAudit(audit)"), method.index("defaults.removeObject(forKey: key)"))
        for guard in ("results_zip_sha256", "report_sha256", "correction_sha256", "allocated_native_kv_tensors", "Q8_0"):
            self.assertIn(guard, method)

    def test_package_allows_known_predecessor_and_requires_ack_launcher(self):
        packager = (ROOT / "tools/package_ptq1_oneclick.py").read_text(encoding="utf-8")
        self.assertIn("acknowledge_failure_source_shas", packager)
        self.assertIn("RUN_Q8_ACKNOWLEDGE.cmd", packager)

    def test_host_tool_requires_archive_hashes_and_explicit_operator_phrase(self):
        tool = (ROOT / "tools/PTQ1_ONECLICK/acknowledge_q8_interruption.py").read_text(encoding="utf-8")
        self.assertIn("verify_failure_archive", tool)
        self.assertIn("OPERATOR_CORRECTION.json", tool)
        self.assertIn("ACKNOWLEDGE PRESERVED FAILED Q8", tool)
        self.assertIn("/debug/benchmark/acknowledge_q8_interruption", tool)
        self.assertNotIn("/v1/chat/completions", tool)
        self.assertLess(tool.index('if input("输入 " + TOKEN'),
                        tool.index('client.request("/debug/benchmark/acknowledge_q8_interruption"'))

if __name__ == "__main__":
    unittest.main()
