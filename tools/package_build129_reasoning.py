#!/usr/bin/env python3
"""Package the unsigned Build129 IPA and an independent functional test kit."""
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
PYTHON_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
TESTKIT_SOURCE = ROOT / "tools/BUILD129_REASONING_TESTKIT"


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def digest_archive_member(archive, member):
    digest = hashlib.sha256()
    with archive.open(member, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build():
    app = ROOT / "build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app"
    if not app.is_dir():
        raise FileNotFoundError("Release app missing")
    info = plistlib.loads((app / "Info.plist").read_bytes())
    build_number = os.environ.get("BUILD_NUMBER", "")
    if build_number != "129" or str(info.get("CFBundleVersion")) != build_number:
        raise ValueError("Build129 bundle identity mismatch")
    source_sha = os.environ["GITHUB_SHA"]
    if len(source_sha) != 40:
        raise ValueError("GITHUB_SHA must be a full commit SHA")
    run_id = os.environ["GITHUB_RUN_ID"]
    delivery_root = ROOT / "build/delivery"
    kit = delivery_root / "Bonsai-Build129-Reasoning-Mode"
    kit.mkdir(parents=True, exist_ok=False)
    (kit / "python").mkdir()

    for name in (
        "README_BUILD129_CN.md",
        "RUN_BUILD129_REASONING_API_SMOKE.cmd",
        "build129_reasoning_api_smoke.py",
    ):
        source = TESTKIT_SOURCE / name
        destination = kit / name
        if name.lower().endswith(".cmd"):
            text = source.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            destination.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        else:
            shutil.copy2(source, destination)

    ipa = kit / "BonsaiLab-Build129-Reasoning-unsigned.ipa"
    with zipfile.ZipFile(ipa, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app.rglob("*")):
            if path.is_file():
                archive.write(path, "Payload/BonsaiLab.app/" + path.relative_to(app).as_posix())
    (kit / (ipa.name + ".sha256")).write_text(
        f"{digest_file(ipa)}  {ipa.name}\n", encoding="utf-8"
    )

    with urllib.request.urlopen(PYTHON_URL, timeout=120) as response:
        python_archive = response.read()
    if digest_bytes(python_archive) != PYTHON_SHA256:
        raise ValueError("Official Python embedded archive SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(python_archive)) as archive:
        archive.extractall(kit / "python")
    (kit / "python/python312._pth").write_text("python312.zip\n.\n..\n", encoding="utf-8")
    for name in ("python.exe", "python312.dll", "python312.zip", "_ssl.pyd", "LICENSE.txt"):
        if not (kit / "python" / name).is_file():
            raise FileNotFoundError(f"Embedded Python component missing: {name}")

    identity = {
        "schema": "bonsai-build129-reasoning-testkit-identity-v1",
        "build_number": build_number,
        "source_git_sha": source_sha,
        "workflow_run_id": run_id,
        "prism_upstream_sha": os.environ["PRISM_COMMIT"],
        "unsigned_ipa_sha256": digest_file(ipa),
        "testkit_source_sha": source_sha,
        "functional_smoke": "NOT_RUN",
        "performance_and_stability_certification": "NOT_RUN",
    }
    (kit / "TestKitIdentity.json").write_text(
        json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    evidence = kit / "CI_EVIDENCE"
    evidence.mkdir()
    for name in ("CI_TESTS.txt", "BUILD129_POLICY.txt", "BUILD129_TESTS.txt", "build.log", "SYMBOL_IDENTITY.json"):
        shutil.copy2(ROOT / "build" / name, evidence / name)
    for relative, name in (
        ("docs/superpowers/specs/2026-10-27-api-reasoning-effort-design.md", "DESIGN.md"),
        ("docs/superpowers/plans/2026-10-27-api-reasoning-effort.md", "IMPLEMENTATION_PLAN.md"),
    ):
        shutil.copy2(ROOT / relative, evidence / name)

    (kit / "BUILD_INFO.txt").write_text(
        f"Build129 API reasoning-mode candidate\nSource: {source_sha}\n"
        f"Workflow run: {run_id}\nIPA SHA-256: {digest_file(ipa)}\n"
        "IPA is unsigned. Functional smoke and M5 device validation: NOT_RUN.\n"
        "No Q8/B8 performance change or Stable certification is claimed.\n",
        encoding="utf-8",
    )

    manifest = {
        path.relative_to(kit).as_posix(): digest_file(path)
        for path in sorted(kit.rglob("*"))
        if path.is_file()
    }
    (kit / "DELIVERY_SHA256.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    candidate = delivery_root / "BONSAI_BUILD129_REASONING_MODE_CANDIDATE.zip"
    with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(kit.rglob("*")):
            if path.is_file():
                archive.write(path, kit.name + "/" + path.relative_to(kit).as_posix())
    with zipfile.ZipFile(candidate) as archive:
        if archive.testzip() is not None:
            raise ValueError("Candidate archive integrity check failed")
        for name, digest in manifest.items():
            member = kit.name + "/" + name
            if digest_archive_member(archive, member) != digest:
                raise ValueError(f"Candidate member hash mismatch: {name}")
        if len([name for name in archive.namelist() if name.endswith(".ipa")]) != 1:
            raise ValueError("Candidate must contain exactly one IPA")
    (Path(str(candidate) + ".sha256")).write_text(
        f"{digest_file(candidate)}  {candidate.name}\n", encoding="utf-8"
    )

    testkit = delivery_root / "BONSAI_BUILD129_REASONING_TESTKIT.zip"
    with zipfile.ZipFile(testkit, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in manifest:
            if name.endswith((".ipa", ".ipa.sha256")):
                continue
            archive.write(kit / name, kit.name + "/" + name)
        testkit_manifest = {
            name: digest for name, digest in manifest.items()
            if not name.endswith((".ipa", ".ipa.sha256"))
        }
        archive.writestr(
            kit.name + "/DELIVERY_SHA256.json",
            json.dumps(testkit_manifest, indent=2) + "\n",
        )
    with zipfile.ZipFile(testkit) as archive:
        if archive.testzip() is not None:
            raise ValueError("TestKit archive integrity check failed")
        for name, digest in testkit_manifest.items():
            member = kit.name + "/" + name
            if digest_archive_member(archive, member) != digest:
                raise ValueError(f"TestKit member hash mismatch: {name}")
        if any(name.endswith(".ipa") for name in archive.namelist()):
            raise ValueError("Independent TestKit must not contain the IPA")
        if not any(name.endswith("RUN_BUILD129_REASONING_API_SMOKE.cmd") for name in archive.namelist()):
            raise ValueError("Independent TestKit runner missing")
    (Path(str(testkit) + ".sha256")).write_text(
        f"{digest_file(testkit)}  {testkit.name}\n", encoding="utf-8"
    )
    print("Build129 candidate and independent TestKit: PASS; device validation: NOT_RUN")


if __name__ == "__main__":
    build()
