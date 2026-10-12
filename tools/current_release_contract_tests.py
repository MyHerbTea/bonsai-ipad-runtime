from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.release_manifest import _setting


IDENTITY_FIELDS = (
    "product",
    "bundle_identifier",
    "marketing_version",
    "build_number",
    "source_sha",
    "workflow_run_id",
    "prism_sha",
    "patch_digest",
)
EXPECTED_PATCH_PATHS = [
    "tools/rc126_build83_patch_prism_kv_sharding.py",
    "tools/rc126_build84_patch_prism_native_trace.py",
    "tools/rc126_build85_patch_prism_scheduler_trace.py",
    "tools/rc126_build86_patch_prism_crash_forensics.py",
    "tools/rc126_build87_patch_prism_sched_context.py",
    "tools/rc126_build88_patch_prism_mmap_recovery.py",
    "tools/rc126_build89_patch_prism_compact_scheduler.py",
]
REQUIRED_NATIVE_SYMBOLS = (
    "_mtmd_init_from_file",
    "_mtmd_helper_eval_chunks",
    "_llama_memory_seq_rm",
)
REQUIRED_FALLBACK_GATES = ("ReleaseManifest.load", "unverifiedLocal")
REQUIRED_INJECTION_GATES = (
    "BonsaiPrepareVisionCache",
    "BonsaiPrefillCachedVision",
)


def _identity(value: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = value.get("identity")
    return nested if isinstance(nested, Mapping) else value


def _compare_surface(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    surface: str,
) -> list[str]:
    errors: list[str] = []
    for field in IDENTITY_FIELDS:
        if expected.get(field) != observed.get(field):
            errors.append(
                f"{surface} {field} mismatch: expected {expected.get(field)!r}, "
                f"observed {observed.get(field)!r}"
            )
    return errors


def validate_current_release(
    project: dict,
    manifest: dict,
    packaging: dict,
) -> list[str]:
    errors: list[str] = []
    identity = _identity(manifest)

    for field in ("product", "bundle_identifier", "marketing_version", "build_number"):
        if str(project.get(field, "")) != str(identity.get(field, "")):
            errors.append(
                f"project {field} mismatch: expected {identity.get(field)!r}, "
                f"observed {project.get(field)!r}"
            )
    if identity.get("source_sha") == "unverified-local-build":
        errors.append("release source_sha is unverified-local-build and cannot be certified")
    if not re.fullmatch(r"[0-9a-f]{40}", str(identity.get("source_sha", ""))):
        errors.append("release source_sha is not a full Git SHA")
    if not str(identity.get("workflow_run_id", "")).isdigit():
        errors.append("release workflow_run_id is missing or not numeric")
    if not re.fullmatch(r"[0-9a-f]{40}", str(identity.get("prism_sha", ""))):
        errors.append("release prism_sha is not a full Git SHA")

    for key, surface in (
        ("api_identity", "API"),
        ("artifact_identity", "artifact"),
        ("runner_identity", "runner"),
    ):
        observed = packaging.get(key)
        if not isinstance(observed, Mapping):
            errors.append(f"{surface} identity is missing")
            continue
        errors.extend(_compare_surface(identity, _identity(observed), surface))

    ordered = identity.get("ordered_patches")
    if not isinstance(ordered, list) or not ordered:
        errors.append("release ordered_patches is missing")
        expected_order: list[str] = []
    else:
        expected_order = [
            str(item.get("name", "")) if isinstance(item, Mapping) else str(item)
            for item in ordered
        ]
        canonical = json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode()
        computed = hashlib.sha256(canonical).hexdigest()
        if computed != identity.get("patch_digest"):
            errors.append("release patch_digest does not match ordered patch list")
    if packaging.get("patch_order") != expected_order:
        errors.append(
            f"native patch order mismatch: expected {expected_order!r}, "
            f"observed {packaging.get('patch_order')!r}"
        )

    native_diff = identity.get("native_diff_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(native_diff or "")):
        errors.append("release native_diff_sha256 is missing or invalid")

    unsigned_ipa = packaging.get("unsigned_ipa")
    if not isinstance(unsigned_ipa, Mapping):
        errors.append("unsigned IPA manifest is missing")
    else:
        if unsigned_ipa.get("artifact_kind") != "unsigned_ipa":
            errors.append("unsigned IPA artifact_kind must be unsigned_ipa")
        digest = unsigned_ipa.get("sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest or "")):
            errors.append("unsigned IPA SHA256 is missing or invalid")
        if not packaging.get("checksum_sha256") or packaging.get("checksum_sha256") != digest:
            errors.append("unsigned IPA checksum sidecar is missing or does not match")

    native_symbols = set(packaging.get("native_symbols", []))
    required_symbols = set(packaging.get("required_native_symbols", REQUIRED_NATIVE_SYMBOLS))
    for symbol in sorted(required_symbols - native_symbols):
        errors.append(f"required native symbol is missing: {symbol}")

    for name, defaults in (
        ("fallback_gates", REQUIRED_FALLBACK_GATES),
        ("injection_gates", REQUIRED_INJECTION_GATES),
    ):
        present = set(packaging.get(name, []))
        required = set(packaging.get(f"required_{name}", defaults))
        for gate in sorted(required - present):
            errors.append(f"required {name} gate is missing: {gate}")

    return errors


def validate_source_contract(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []

    def read(relative: str) -> str:
        path = root / relative
        if not path.is_file():
            errors.append(f"required source file is missing: {relative}")
            return ""
        return path.read_text(encoding="utf-8-sig")

    try:
        project = read("project.yml")
        build_number = _setting(project, "CURRENT_PROJECT_VERSION")
        if not build_number.isdigit():
            errors.append("project build number must be numeric")
        if not re.search(
            r"(?m)^  SwiftNumerics:\r?\n    url: https://github\.com/apple/swift-numerics\r?\n    exactVersion: 1\.1\.1\s*$",
            project,
        ):
            errors.append("project.yml must exactly pin apple/swift-numerics at 1.1.1")
        if not re.search(
            r"(?m)^      - package: SwiftNumerics\r?\n        product: Numerics\s*$",
            project,
        ):
            errors.append("BonsaiLab must link the SwiftNumerics Numerics product for resolution")
    except ValueError as exc:
        errors.append(str(exc))
        project = ""
        build_number = ""

    for required in (
        "BonsaiLab/release_manifest.json",
        "BonsaiLab/ReleaseManifest.swift",
    ):
        if required.endswith(".json") and required not in project:
            errors.append(f"project.yml does not register release resource: {required}")
        if not (root / required).is_file():
            errors.append(f"release identity source file is missing: {required}")

    fallback = read("BonsaiLab/BonsaiCertificationBuildIdentity.swift")
    release_swift = read("BonsaiLab/ReleaseManifest.swift")
    server = read("BonsaiLab/LocalOpenAIServer.swift")
    production = read("BonsaiLab/ProductionView.swift")
    workflow = read(".github/workflows/build-ios.yml")
    generator = read("tools/release_manifest.py")

    for needle, label in (
        ("unverified-local-build", "local identity fallback"),
        ("ReleaseManifest.load", "manifest loader"),
    ):
        if needle not in fallback + release_swift:
            errors.append(f"current identity is missing {label}")
    for needle, label in (
        ("embeddedSourceGitSHA", "source SHA binding"),
        ("embeddedWorkflowRunID", "workflow run binding"),
        ("embeddedPrismSHA", "Prism binding"),
        ("embeddedPatchDigest", "patch binding"),
        ("embeddedBuildNumber", "build number binding"),
        ("nativeDiffSHA256", "native diff binding"),
    ):
        if needle not in release_swift + fallback:
            errors.append(f"current identity is missing {label}")
    if "BonsaiCertificationBuildIdentity.manifest" not in server:
        errors.append("debug/build API does not read the shared ReleaseManifest")
    if "RC126APIStartupLifecycle.begin(build: BonsaiCertificationBuildIdentity.manifest.buildNumber)" not in production:
        errors.append("API startup lifecycle does not use the shared release build number")
    for field in (
        "sourceGitSHA",
        "workflowRunID",
        "prismSHA",
        "patchDigest",
        "isVerified",
    ):
        if field not in production:
            errors.append(f"ProductionView/report omits release identity field {field}")

    for needle in (
        "--source-sha \"$GITHUB_SHA\"",
        "--ci-run \"$GITHUB_RUN_ID\"",
        "--native-diff-sha256",
        "--output BonsaiLab/release_manifest.json",
        "--swift-output BonsaiLab/BonsaiCertificationBuildIdentity.swift",
        "build-$BUILD_NUMBER-candidate-unsigned.ipa",
        "shasum -a 256 \"build/$IPA_NAME\"",
        "--artifact-only",
        "xcodebuild -resolvePackageDependencies",
        "-disableAutomaticPackageResolution",
        "--swiftpm-resolved BonsaiLab.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
        "build/artifact_manifest.json",
        "--artifact-output build/artifact_manifest.json",
        "build/artifact_manifest.json",
        "build/*.ipa*",
        "python3 -m unittest discover -s tools/tests -p test_release_manifest.py",
    ):
        if needle not in workflow:
            errors.append(f"workflow omits current release identity/package gate: {needle}")

    for path in EXPECTED_PATCH_PATHS:
        if not (root / path).is_file():
            errors.append(f"ordered native patch script is missing: {path}")
        if f"--patch {path}" not in workflow:
            errors.append(f"workflow does not bind patch order input: {path}")
    patch_positions = [workflow.find(f"--patch {path}") for path in EXPECTED_PATCH_PATHS]
    if patch_positions != sorted(patch_positions):
        errors.append("workflow Prism patch inputs are not in the expected Build83–89 order")

    for symbol in REQUIRED_NATIVE_SYMBOLS:
        if symbol not in workflow:
            errors.append(f"workflow native symbol gate is missing: {symbol}")
    for gate in REQUIRED_INJECTION_GATES:
        if gate not in workflow:
            errors.append(f"workflow live vision injection gate is missing: {gate}")
    for gate in REQUIRED_FALLBACK_GATES:
        if gate not in fallback + release_swift:
            errors.append(f"runtime local/unverified fallback gate is missing: {gate}")
    if 'CURRENT_PROJECT_VERSION:' in workflow:
        errors.append("workflow retains a stale Build106 current-identity assertion")
    if not build_number:
        errors.append("project build number could not be resolved")

    # Ensure the tracked local resource is explicitly non-certifiable.
    try:
        local_manifest = json.loads((root / "BonsaiLab/release_manifest.json").read_text(encoding="utf-8"))
        if local_manifest.get("source_sha") != "unverified-local-build":
            errors.append("checked-in local release manifest must remain unverified")
        if str(local_manifest.get("build_number")) != build_number:
            errors.append("checked-in local release manifest build does not match project.yml")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"checked-in release manifest is invalid: {exc}")

    if "def build_release_manifest(" not in generator or "def build_artifact_manifest(" not in generator:
        errors.append("release manifest generator is missing required builders")
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the current RC1.26 release identity contract.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors = validate_source_contract(args.root)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("PASS current release identity source contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
