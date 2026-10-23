#!/usr/bin/env python3
"""Build a single, hash-verified IPA + portable Windows benchmark delivery."""
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
PYTHON_SHA = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"

def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()

def windows_cmd_bytes(data):
    # Git checkouts on macOS/Linux must not leak LF-only CMDs into Windows ZIPs.
    text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r\n").encode("utf-8")

def build():
    app = ROOT / "build/DerivedData/Build/Products/Release-iphoneos/BonsaiLab.app"
    assert app.is_dir(), "Release app missing"
    info = plistlib.loads((app / "Info.plist").read_bytes())
    number = os.environ.get('BUILD_NUMBER','118')
    assert str(info["CFBundleVersion"]) == number
    source = os.environ["GITHUB_SHA"]
    kit = ROOT / f"build/delivery/Bonsai-Build{number}-PTQ1"
    kit.mkdir(parents=True, exist_ok=True)
    assert not any(kit.iterdir()), "Refuse stale delivery directory"
    for file in (ROOT / "tools/PTQ1_ONECLICK").iterdir():
        if file.is_file() and file.suffix in (".py", ".cmd", ".txt", ".md", ".json"):
            if file.suffix.lower() == ".cmd":
                (kit / file.name).write_bytes(windows_cmd_bytes(file.read_bytes()))
            else:
                shutil.copy2(file, kit / file.name)
    ipa = kit / f"BonsaiLab-Build{number}-PTQ1-unsigned.ipa"
    with zipfile.ZipFile(ipa, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(app.rglob("*")):
            if file.is_file():
                archive.write(file, "Payload/BonsaiLab.app/" + file.relative_to(app).as_posix())
    (kit / (ipa.name + ".sha256")).write_text(sha(ipa) + "  " + ipa.name + "\n", encoding="utf-8")
    with urllib.request.urlopen(PYTHON_URL, timeout=120) as response:
        data = response.read()
    assert hashlib.sha256(data).hexdigest() == PYTHON_SHA, "Official Python archive checksum mismatch"
    python_dir = kit / "python"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(python_dir)
    (python_dir / "python312._pth").write_text("python312.zip\n.\n..\n", encoding="utf-8")
    for filename in ("python.exe", "python312.dll", "python312.zip", "_ssl.pyd", "LICENSE.txt"):
        assert (python_dir / filename).is_file(), filename
    identity = {"schema": "bonsai-ptq1-oneclick-identity-v1", "source_git_sha": source,
        "testkit_source_sha": source, "build_number": number, "unsigned_ipa_sha256": sha(ipa),
        "prism_upstream_sha": os.environ["PRISM_COMMIT"], "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "official_model": json.loads((ROOT / "tools/ptq1_official_model.json").read_text(encoding="utf-8")),
        "python_archive_url": PYTHON_URL, "python_archive_sha256": PYTHON_SHA,
        "symbols_artifact": {"file": f"Bonsai-Build{number}-Symbols.zip",
            "sha256": sha(ROOT / f"build/Bonsai-Build{number}-Symbols.zip"),
            "uuid_identity": "CI_EVIDENCE/SYMBOL_IDENTITY.json"},
        "device_validation": "NOT_RUN"}
    (kit / "TestKitIdentity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    checks = kit / "CI_EVIDENCE"
    checks.mkdir()
    for filename in ("CI_TESTS.txt", "build.log", "llama-symbols.txt", "app-symbols.txt", "SYMBOL_IDENTITY.json"):
        shutil.copy2(ROOT / "build" / filename, checks / filename)
    (kit / "BUILD_INFO.txt").write_text(
        f"Build{number} PTQ1 candidates; concentrated prefill comparison included\n"
        f"Source: {source}\nWorkflow: {os.environ['GITHUB_RUN_ID']}\n"
        "Unsigned IPA: sign once with your existing iPad installation method.\n"
        "Target: M5 iPad Pro 12GB; official PTQ1 GGUF only.\n"
        "Device runtime compilation, numerical quality and performance: NOT_RUN.\n"
        "All candidates share one IPA. Production defaults are restored after benchmark.\n"
        "No candidate is a winner until actual device gates pass.\n", encoding="utf-8")
    manifest = {file.relative_to(kit).as_posix(): sha(file) for file in sorted(kit.rglob("*")) if file.is_file()}
    (kit / "DELIVERY_SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    output = kit.parent / f"BONSAI_BUILD{number}_PTQ1_ONECLICK.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(kit.rglob("*")):
            if file.is_file(): archive.write(file, kit.name + "/" + file.relative_to(kit).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(kit.name + "/" + name)).hexdigest() == digest, name
        assert any(name.endswith("RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd") for name in archive.namelist())
        assert len([name for name in archive.namelist() if name.endswith(".ipa")]) == 1
    Path(str(output) + ".sha256").write_text(sha(output) + "  " + output.name + "\n", encoding="utf-8")
    print("Combined delivery integrity: PASS; device validation: NOT_RUN")

if __name__ == "__main__":
    build()
