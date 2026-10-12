import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.current_release_contract_tests import (
    validate_current_release,
    validate_source_contract,
)


class CurrentReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        patches = [
            {"name": f"build{number}", "sha256": f"{number:064x}"}
            for number in range(83, 90)
        ]
        canonical = json.dumps(patches, sort_keys=True, separators=(",", ":")).encode()
        self.manifest = {
            "product": "BonsaiLab",
            "bundle_identifier": "local.bonsai.lab.v1",
            "marketing_version": "1.0.0",
            "build_number": "109",
            "source_sha": "a" * 40,
            "workflow_run_id": "123456789",
            "prism_sha": "b" * 40,
            "ordered_patches": patches,
            "patch_digest": hashlib.sha256(canonical).hexdigest(),
            "native_diff_sha256": "9" * 64,
        }
        self.project = {
            "product": "BonsaiLab",
            "bundle_identifier": "local.bonsai.lab.v1",
            "marketing_version": "1.0.0",
            "build_number": "109",
        }
        self.packaging = {
            "api_identity": copy.deepcopy(self.manifest),
            "artifact_identity": copy.deepcopy(self.manifest),
            "runner_identity": copy.deepcopy(self.manifest),
            "unsigned_ipa": {"artifact_kind": "unsigned_ipa", "sha256": "c" * 64},
            "checksum_sha256": "c" * 64,
            "native_symbols": ["_mtmd_init_from_file", "_mtmd_helper_eval_chunks", "_llama_memory_seq_rm"],
            "required_native_symbols": ["_mtmd_init_from_file", "_mtmd_helper_eval_chunks", "_llama_memory_seq_rm"],
            "fallback_gates": ["ReleaseManifest.load", "unverifiedLocal"],
            "required_fallback_gates": ["ReleaseManifest.load", "unverifiedLocal"],
            "injection_gates": ["BonsaiPrepareVisionCache", "BonsaiPrefillCachedVision"],
            "required_injection_gates": ["BonsaiPrepareVisionCache", "BonsaiPrefillCachedVision"],
            "patch_order": [patch["name"] for patch in patches],
        }

    def test_accepts_consistent_app_api_artifact_and_runner_identity(self):
        self.assertEqual(validate_current_release(self.project, self.manifest, self.packaging), [])

    def test_rejects_build_and_sha_conflicts_on_each_surface(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["api_identity"]["source_sha"] = "d" * 40
        packaging["artifact_identity"]["build_number"] = "108"
        packaging["runner_identity"]["prism_sha"] = "e" * 40
        errors = validate_current_release(self.project, self.manifest, packaging)
        for field in ("source_sha", "build_number", "prism_sha"):
            self.assertTrue(any(field in error for error in errors), field)

    def test_rejects_same_build_number_from_different_source(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["source_sha"] = "f" * 40
        errors = validate_current_release(self.project, manifest, self.packaging)
        self.assertTrue(any("source_sha" in error for error in errors))

    def test_rejects_missing_native_symbol(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["native_symbols"].remove("_mtmd_helper_eval_chunks")
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("_mtmd_helper_eval_chunks" in error for error in errors))

    def test_rejects_missing_fallback_or_live_vision_injection_gate(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["fallback_gates"].remove("unverifiedLocal")
        packaging["injection_gates"].remove("BonsaiPrefillCachedVision")
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("unverifiedLocal" in error for error in errors))
        self.assertTrue(any("BonsaiPrefillCachedVision" in error for error in errors))

    def test_rejects_missing_or_wrong_ipa_checksum(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["checksum_sha256"] = None
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("checksum" in error for error in errors))
        packaging["checksum_sha256"] = "d" * 64
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("checksum" in error for error in errors))

    def test_rejects_signed_unsigned_confusion(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["unsigned_ipa"]["artifact_kind"] = "signed_ipa"
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("artifact_kind" in error for error in errors))

    def test_rejects_wrong_native_patch_order(self):
        packaging = copy.deepcopy(self.packaging)
        packaging["patch_order"].reverse()
        errors = validate_current_release(self.project, self.manifest, packaging)
        self.assertTrue(any("patch order" in error for error in errors))

    def test_current_repository_wires_one_identity_and_preserves_runtime_gates(self):
        self.assertEqual(validate_source_contract(self.root), [])

    def test_swift_numerics_is_exactly_pinned_and_resolved_as_a_direct_product(self):
        project = (self.root / "project.yml").read_text(encoding="utf-8")
        self.assertRegex(
            project,
            r"(?ms)^  SwiftNumerics:\n    url: https://github\.com/apple/swift-numerics\n    exactVersion: 1\.1\.1$",
        )
        self.assertRegex(
            project,
            r"(?ms)^      - package: SwiftNumerics\n        product: Numerics$",
        )


if __name__ == "__main__":
    unittest.main()
