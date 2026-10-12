from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


SWIFT_NUMERICS_VERSION = "1.1.1"


HEX_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _setting(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'\r\n#]+)", text, re.MULTILINE)
    if not match:
        raise ValueError(f"project.yml is missing {key}")
    return match.group(1).strip()


def _patch_record(project_dir: Path, item: Any) -> dict[str, str]:
    if isinstance(item, Mapping):
        raw_path = item.get("path")
        name = str(item.get("name") or (Path(str(raw_path)).name if raw_path else ""))
    else:
        raw_path = item
        name = Path(str(raw_path)).name
    if not raw_path:
        raise ValueError("each ordered patch must include a path")
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = project_dir / path
    if not path.is_file():
        raise ValueError(f"patch file does not exist: {path}")
    if not name:
        raise ValueError(f"patch name is empty: {path}")
    return {"name": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_release_manifest(
    project: Path,
    source_sha: str,
    ci_run: str,
    prism_sha: str,
    ordered_patches: list,
) -> dict:
    project = Path(project)
    text = project.read_text(encoding="utf-8-sig")
    source_sha = str(source_sha).lower()
    prism_sha = str(prism_sha).lower()
    ci_run = str(ci_run).strip()
    if not HEX_SHA_RE.fullmatch(source_sha) or source_sha == "unverified-local-build":
        raise ValueError("source_sha must be a verified 40-character Git SHA")
    if not ci_run.isdigit():
        raise ValueError("ci_run must be the numeric GitHub Actions run ID")
    if not HEX_SHA_RE.fullmatch(prism_sha):
        raise ValueError("prism_sha must be a verified 40-character Git SHA")
    build_number = _setting(text, "CURRENT_PROJECT_VERSION")
    if not build_number.isdigit() or int(build_number) < 1:
        raise ValueError("CURRENT_PROJECT_VERSION must be a positive numeric build")
    if not ordered_patches:
        raise ValueError("at least one ordered Prism patch input is required")

    patches = [_patch_record(project.parent, item) for item in ordered_patches]
    canonical_patches = json.dumps(patches, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": 1,
        "product": _setting(text, "PRODUCT_NAME"),
        "bundle_identifier": _setting(text, "PRODUCT_BUNDLE_IDENTIFIER"),
        "marketing_version": _setting(text, "MARKETING_VERSION"),
        "build_number": build_number,
        "source_sha": source_sha,
        "workflow_run_id": ci_run,
        "prism_sha": prism_sha,
        "ordered_patches": patches,
        "patch_digest": hashlib.sha256(canonical_patches).hexdigest(),
        "native_diff_sha256": None,
        "swift_version": _setting(text, "SWIFT_VERSION"),
        "deployment_target": _setting(text, "iOS"),
        "mlx_swift_version": _setting(text, "exactVersion"),
        "default_runtime_profile": "SAFE4",
        "allowed_runtime_profiles": ["SAFE4", "BALANCED8"],
        "startup_memory_envelope_policy": {
            "formula": "max(512, maxObservedStartupFootprintDeltaMiB + max(512, 0.10 * maxObservedStartupFootprintDeltaMiB))",
            "minimum_available_memory_mib": 512,
            "upgrade_thermal_states": ["nominal", "fair"],
            "blocked_memory_grades": ["constrained", "critical"],
            "required_envelope_status": "FULL_CERTIFIED",
        },
        "assets": {
            "model_sha256": None,
            "vision_sha256": None,
            "status": "external-assets-not-available-to-CI",
        },
    }


def _swiftpm_resolution_record(path: Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    resolved = json.loads(raw)
    schema_version = resolved.get("version")
    if not isinstance(schema_version, int):
        raise ValueError("Package.resolved is missing an integer schema version")
    pins = resolved.get("pins")
    if pins is None and isinstance(resolved.get("object"), Mapping):
        pins = resolved["object"].get("pins")
    if not isinstance(pins, list) or not pins:
        raise ValueError("Package.resolved has no dependency pins")

    normalized: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for pin in pins:
        if not isinstance(pin, Mapping):
            raise ValueError("Package.resolved contains a malformed pin")
        state = pin.get("state")
        if not isinstance(state, Mapping):
            raise ValueError("Package.resolved pin has no state")
        raw_identity = pin.get("identity") or pin.get("package")
        identity = str(raw_identity or "").strip().lower()
        revision = str(state.get("revision") or "").lower()
        version = state.get("version")
        version_text = str(version).strip() if version is not None else None
        if not identity or identity in seen:
            raise ValueError("Package.resolved has an empty or duplicate package identity")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"Package.resolved pin {identity} has no exact git revision")
        if version_text == "":
            version_text = None
        seen.add(identity)
        normalized.append({
            "identity": identity,
            "version": version_text,
            "revision": revision,
        })
    normalized.sort(key=lambda pin: pin["identity"] or "")
    numerics_pin = next(
        (pin for pin in normalized if pin["identity"] == "swift-numerics"),
        None,
    )
    if numerics_pin is None:
        raise ValueError("Package.resolved does not include the audited swift-numerics dependency")
    if numerics_pin["version"] != SWIFT_NUMERICS_VERSION:
        raise ValueError(
            f"swift-numerics must resolve to audited version {SWIFT_NUMERICS_VERSION}; "
            f"observed {numerics_pin['version']!r}"
        )

    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "schema_version": schema_version,
        "pins": normalized,
    }


def build_artifact_manifest(
    release_manifest_path: Path,
    unsigned_ipa: Path,
    runner_zip: Path,
    swiftpm_resolved_path: Path | None = None,
) -> dict:
    release_manifest_path = Path(release_manifest_path)
    unsigned_ipa = Path(unsigned_ipa)
    runner_zip = Path(runner_zip)
    release = json.loads(release_manifest_path.read_text(encoding="utf-8"))
    if not release.get("source_sha") or release.get("source_sha") == "unverified-local-build":
        raise ValueError("artifact manifest requires a verified release identity")
    artifact = {
        "schema_version": 1,
        "identity": {
            key: release[key]
            for key in (
                "product",
                "bundle_identifier",
                "marketing_version",
                "build_number",
                "source_sha",
                "workflow_run_id",
                "prism_sha",
                "patch_digest",
            )
        },
        "release_manifest_sha256": hashlib.sha256(release_manifest_path.read_bytes()).hexdigest(),
        "unsigned_ipa": {
            "artifact_kind": "unsigned_ipa",
            "sha256": hashlib.sha256(unsigned_ipa.read_bytes()).hexdigest(),
            "bytes": unsigned_ipa.stat().st_size,
        },
        "runner_zip": {
            "sha256": hashlib.sha256(runner_zip.read_bytes()).hexdigest(),
            "bytes": runner_zip.stat().st_size,
        },
        "signed_ipa": None,
        "github_wrapper_sha256": None,
        "wrapper_digest_note": "GitHub computes the Actions wrapper digest after upload; it cannot be included in this uploaded manifest without a self-reference cycle.",
    }
    if swiftpm_resolved_path is not None:
        artifact["swiftpm_resolution"] = _swiftpm_resolution_record(swiftpm_resolved_path)
    return artifact


def _swift_identity_source(manifest: Mapping[str, Any]) -> str:
    return f'''// Generated by tools/release_manifest.py during CI. Do not edit by hand.
enum BonsaiCertificationBuildIdentity {{
    static let embeddedSourceGitSHA = "{manifest["source_sha"]}"
    static let embeddedWorkflowRunID = "{manifest["workflow_run_id"]}"
    static let embeddedPrismSHA = "{manifest["prism_sha"]}"
    static let embeddedPatchDigest = "{manifest["patch_digest"]}"
    static let embeddedBuildNumber = "{manifest["build_number"]}"
}}
'''


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    values = list(argv) if argv is not None else sys.argv[1:]
    if "--artifact-only" in values:
        parser = argparse.ArgumentParser()
        parser.add_argument("--artifact-only", action="store_true")
        parser.add_argument("--release-manifest", type=Path, required=True)
        parser.add_argument("--unsigned-ipa", type=Path, required=True)
        parser.add_argument("--runner-zip", type=Path, required=True)
        parser.add_argument("--swiftpm-resolved", type=Path, required=True)
        parser.add_argument("--artifact-output", type=Path, required=True)
        args = parser.parse_args(values)
        artifact = build_artifact_manifest(
            args.release_manifest,
            args.unsigned_ipa,
            args.runner_zip,
            swiftpm_resolved_path=args.swiftpm_resolved,
        )
        args.artifact_output.parent.mkdir(parents=True, exist_ok=True)
        args.artifact_output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--ci-run", required=True)
    parser.add_argument("--prism-sha", required=True)
    parser.add_argument("--patch", action="append", type=Path, required=True)
    parser.add_argument("--native-diff-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--swift-output", type=Path, required=True)
    args = parser.parse_args(values)

    manifest = build_release_manifest(
        args.project, args.source_sha, args.ci_run, args.prism_sha, args.patch
    )
    if args.native_diff_sha256:
        digest = args.native_diff_sha256.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("native diff digest must be a 64-character SHA256")
        manifest["native_diff_sha256"] = digest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.swift_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.swift_output.write_text(_swift_identity_source(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
