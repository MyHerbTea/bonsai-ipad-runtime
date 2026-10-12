import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.release_manifest import build_artifact_manifest, build_release_manifest
from tools.certification.identity import verify_identity


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project.yml"
        self.project.write_text("\n".join([
            "name: BonsaiLab",
            "options:",
            "  deploymentTarget:",
            '    iOS: "17.0"',
            "packages:",
            "  MLXSwift:",
            "    exactVersion: 0.31.3",
            "targets:",
            "  BonsaiLab:",
            "    settings:",
            "      base:",
            "        PRODUCT_BUNDLE_IDENTIFIER: local.bonsai.lab.v1",
            "        PRODUCT_NAME: BonsaiLab",
            '        MARKETING_VERSION: "1.0.0"',
            '        CURRENT_PROJECT_VERSION: "109"',
            '        SWIFT_VERSION: "5.0"',
            "",
        ]), encoding="utf-8")
        self.patch_a = self.root / "patch-a.py"
        self.patch_b = self.root / "patch-b.py"
        self.patch_a.write_text("patch A\n", encoding="utf-8")
        self.patch_b.write_text("patch B\n", encoding="utf-8")
        self.patch_order = [self.patch_a, self.patch_b]
        self.source = "a" * 40
        self.prism = "b" * 40

    def tearDown(self):
        self.temp.cleanup()

    def build(self, source=None, patches=None):
        return build_release_manifest(
            self.project,
            source or self.source,
            "1234567890",
            self.prism,
            list(patches if patches is not None else self.patch_order),
        )

    def test_manifest_reads_the_unique_build_from_project(self):
        manifest = self.build()
        self.assertEqual(manifest["build_number"], "109")
        self.assertEqual(manifest["source_sha"], self.source)
        self.assertEqual(manifest["workflow_run_id"], "1234567890")
        self.assertEqual(manifest["prism_sha"], self.prism)
        self.assertEqual(len(manifest["patch_digest"]), 64)
        self.assertEqual(len(manifest["ordered_patches"]), 2)
        self.assertIn("maxObservedStartupFootprintDeltaMiB", manifest["startup_memory_envelope_policy"]["formula"])
        self.assertEqual(manifest["startup_memory_envelope_policy"]["required_envelope_status"], "FULL_CERTIFIED")

    def test_patch_order_changes_the_digest(self):
        forward = self.build()
        reverse = self.build(patches=reversed(self.patch_order))
        self.assertNotEqual(forward["patch_digest"], reverse["patch_digest"])

    def test_unknown_local_build_cannot_be_certified(self):
        with self.assertRaises(ValueError):
            self.build(source="unverified-local-build")

    def test_correct_observed_identity_has_no_differences(self):
        manifest = self.build()
        self.assertEqual(verify_identity(manifest, dict(manifest)), [])

    def test_wrong_source_build_prism_or_patch_order_is_rejected(self):
        expected = self.build()
        observed = dict(expected)
        observed.update(
            source_sha="c" * 40,
            build_number="108",
            prism_sha="d" * 40,
            patch_digest="e" * 64,
        )
        differences = verify_identity(expected, observed)
        for key in ("source_sha", "build_number", "prism_sha", "patch_digest"):
            self.assertTrue(any(key in difference for difference in differences), key)

    def test_same_build_number_with_different_source_sha_is_rejected(self):
        expected = self.build(source="a" * 40)
        observed = self.build(source="c" * 40)
        self.assertEqual(expected["build_number"], observed["build_number"])
        self.assertTrue(any("source_sha" in d for d in verify_identity(expected, observed)))

    def test_artifact_manifest_separates_unsigned_ipa_from_signed_ipa(self):
        release_path = self.root / "release_manifest.json"
        release_path.write_text(__import__("json").dumps(self.build()), encoding="utf-8")
        ipa = self.root / "candidate.ipa"
        runner = self.root / "runner.zip"
        ipa.write_bytes(b"unsigned ipa bytes")
        runner.write_bytes(b"runner bytes")
        artifact = build_artifact_manifest(release_path, ipa, runner)
        self.assertEqual(artifact["unsigned_ipa"]["artifact_kind"], "unsigned_ipa")
        self.assertIsNone(artifact["signed_ipa"])
        self.assertEqual(artifact["unsigned_ipa"]["bytes"], len(b"unsigned ipa bytes"))
        self.assertEqual(len(artifact["runner_zip"]["sha256"]), 64)

    def test_artifact_manifest_binds_generated_swiftpm_resolution(self):
        release_path = self.root / "release_manifest.json"
        release_path.write_text(json.dumps(self.build()), encoding="utf-8")
        ipa = self.root / "candidate.ipa"
        runner = self.root / "runner.zip"
        resolved = self.root / "Package.resolved"
        ipa.write_bytes(b"unsigned ipa bytes")
        runner.write_bytes(b"runner bytes")
        resolved_bytes = json.dumps({
            "version": 3,
            "pins": [
                {
                    "identity": "swift-numerics",
                    "kind": "remoteSourceControl",
                    "location": "https://github.com/apple/swift-numerics",
                    "state": {"revision": "a" * 40, "version": "1.1.1"},
                },
                {
                    "identity": "mlx-swift",
                    "kind": "remoteSourceControl",
                    "location": "https://github.com/ml-explore/mlx-swift",
                    "state": {"revision": "b" * 40, "version": "0.31.3"},
                },
            ],
        }, sort_keys=True).encode()
        resolved.write_bytes(resolved_bytes)

        artifact = build_artifact_manifest(
            release_path, ipa, runner, swiftpm_resolved_path=resolved
        )
        record = artifact["swiftpm_resolution"]
        self.assertEqual(record["sha256"], hashlib.sha256(resolved_bytes).hexdigest())
        self.assertEqual(record["schema_version"], 3)
        self.assertEqual(
            [(pin["identity"], pin["version"], pin["revision"]) for pin in record["pins"]],
            [
                ("mlx-swift", "0.31.3", "b" * 40),
                ("swift-numerics", "1.1.1", "a" * 40),
            ],
        )

    def test_swiftpm_resolution_rejects_missing_numerics_or_revision(self):
        release_path = self.root / "release_manifest.json"
        release_path.write_text(json.dumps(self.build()), encoding="utf-8")
        ipa = self.root / "candidate.ipa"
        runner = self.root / "runner.zip"
        ipa.write_bytes(b"unsigned ipa bytes")
        runner.write_bytes(b"runner bytes")
        resolved = self.root / "Package.resolved"
        for pins in (
            [{"identity": "mlx-swift", "state": {"revision": "a" * 40, "version": "0.31.3"}}],
            [{"identity": "swift-numerics", "state": {"version": "1.1.1"}}],
            [{"identity": "swift-numerics", "state": {"revision": "a" * 40}}],
            [{"identity": "swift-numerics", "state": {"revision": "a" * 40, "version": "1.1.2"}}],
        ):
            resolved.write_text(json.dumps({"version": 3, "pins": pins}), encoding="utf-8")
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                build_artifact_manifest(
                    release_path, ipa, runner, swiftpm_resolved_path=resolved
                )

    def test_unsigned_and_signed_digest_kinds_cannot_be_confused(self):
        expected = {"artifact_kind": "unsigned_ipa", "artifact_sha256": "a" * 64}
        observed = {"artifact_kind": "signed_ipa", "artifact_sha256": "b" * 64}
        differences = verify_identity(expected, observed)
        self.assertTrue(any("artifact_kind" in d for d in differences))
        self.assertTrue(any("artifact_sha256" in d for d in differences))


if __name__ == "__main__":
    unittest.main()
