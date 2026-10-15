from pathlib import Path
import unittest
import re

ROOT = Path(__file__).resolve().parents[2]
class B16RuntimeSourceTests(unittest.TestCase):
    def test_hash_workers_are_independent_and_report_actual_failures(self):
        source=(ROOT/'BonsaiLab/B16RuntimeEvidence.swift').read_text()
        self.assertIn('bonsai.b16.model-identity',source)
        self.assertIn('bonsai.b16.vision-identity',source)
        self.assertIn('autoreleasepool',source)
        self.assertIn('"asset_hashing"',source)
        for code in ('METADATA_FAILED','OPEN_FAILED','READ_FAILED','FILE_CHANGED','LENGTH_MISMATCH'):
            self.assertIn(code,source)
        self.assertNotIn('guard let digest = fileIdentity(modelURL) else { return }',source)

    def test_evidence_is_recorded_after_both_native_creation_successes(self):
        engine = (ROOT / "BonsaiLab/BonsaiEngine.swift").read_text(encoding="utf-8")
        load = engine[engine.index("guard let loadedContext = llama_init_from_model(loadedModel, contextParams)"):]
        self.assertLess(load.index('mark("MODEL_08_CONTEXT_CREATE_DONE")'), load.index("B16RuntimeEvidence.created("))
        recreate = engine[engine.index("private func makeContext("):]
        self.assertLess(recreate.index("guard let created = llama_init_from_model"), recreate.index("B16RuntimeEvidence.created("))
        self.assertIn("B16RuntimeEvidence.invalidate()", engine[engine.index("func unloadAll("):])

    def test_every_context_free_invalidates_proof_and_completion_is_bound(self):
        engine = (ROOT / "BonsaiLab/BonsaiEngine.swift").read_text(encoding="utf-8")
        for match in re.finditer(r"llama_free\(context\)", engine):
            self.assertTrue(engine[:match.start()].rstrip().endswith("B16RuntimeEvidence.invalidate()"))
        view = (ROOT / "BonsaiLab/ProductionView.swift").read_text(encoding="utf-8")
        self.assertIn("B16RuntimeEvidence.qualifiesTextCompletion(", view)
        self.assertIn("contextID: b16QualificationContext, batch: qualificationBatch", view)

    def test_qualification_identity_does_not_bypass_recovery(self):
        policy = (ROOT / "BonsaiLab/Build94BatchExperiment.swift").read_text(encoding="utf-8")
        self.assertIn("static func bindCertificationIdentity(", policy)
        self.assertIn('if arm == .candidate16 && !defaults.bool(forKey: baselineOKKey)', policy)
        self.assertIn('defaults.bool(forKey: pendingKey)', policy)
        self.assertIn('defaults.bool(forKey: fallbackKey)', policy)
        view = (ROOT / "BonsaiLab/ProductionView.swift").read_text(encoding="utf-8")
        self.assertIn("Build94BatchExperiment.bindCertificationIdentity(", view)

    def test_read_only_evidence_and_real_source_are_exposed(self):
        server = (ROOT / "BonsaiLab/LocalOpenAIServer.swift").read_text(encoding="utf-8")
        self.assertIn('request.path == "/debug/b16/evidence"', server)
        self.assertIn('"source_git_sha": BonsaiCertificationBuildIdentity.sourceGitSHA', server)
        self.assertIn('"candidate_build_id": "rc1.26-build111-b16-prefill"', server)

if __name__ == "__main__":
    unittest.main()
