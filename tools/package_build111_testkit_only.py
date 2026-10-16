#!/usr/bin/env python3
"""Repackage immutable Build111 CI TestKit into a tools-only Windows ZIP.

Source must be the original Build111 GitHub Actions ZIP; never builds or bundles an IPA.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

SOURCE_SHA = "2d4ef50dfb917f3cded903e5c552015780c5a28b"
PRISM_SHA = "adfffbe41b2cabcd51fff326ab045662265062bb"
PREFIX = "BonsaiLab-v1-RC1.26-Build111-B16-Prefill-TestKit/"
TOOLS = ("b16_testkit.py", "rc126_build106_full_stage_certification.py",
         "RUN_B16_TESTKIT_GUI.ps1", "RUN_B16_TESTKIT.cmd")
SUPPORT = ("TestKitIdentity.json", "BUILD_INFO.txt",
           "AUTOMATED_TEST_REPORT.txt", "AUTOMATED_TEST_COMMANDS.txt")
REQUIRED_PY = ("python.exe", "python312.dll", "python312.zip",
               "python312._pth", "_ssl.pyd", "libssl-3.dll")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verified_names(z):
    names = z.namelist()
    if z.testzip() is not None or len(names) != len(set(names)):
        raise ValueError("ZIP CRC or duplicate entry failure")
    for name in names:
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or
            "\\" in name or ":" in name or name.startswith("/")):
            raise ValueError("Unsafe ZIP entry path")
    return names


def repackage(source, checkout, head_sha):
    if not re.fullmatch(r"[a-f0-9]{40}", head_sha):
        raise ValueError("Tool commit must be a full SHA")
    with zipfile.ZipFile(source) as wrapper:
        names = verified_names(wrapper)
        if PREFIX + "TestKitIdentity.json" in names:
            # gh run download already unwraps the GitHub Actions artifact.
            inner = source.read_bytes()
        else:
            contents = [n for n in names if n.lower().endswith(".zip") and not n.endswith("/")]
            if len(contents) != 1:
                raise ValueError("Expected original Build111 CI TestKit ZIP or single-ZIP wrapper")
            inner = wrapper.read(contents[0])
    with zipfile.ZipFile(io.BytesIO(inner)) as original:
        names = verified_names(original)
        if not any(n == PREFIX + "TestKitIdentity.json" for n in names):
            raise ValueError("Wrong Build111 artifact layout")
        members = {n[len(PREFIX):]: n for n in names if n.startswith(PREFIX) and not n.endswith("/")}
        if len(members) != len([n for n in names if n.startswith(PREFIX) and not n.endswith("/")]):
            raise ValueError("Duplicate original archive member")
        for name in (*SUPPORT, "RunnerIdentity.json", *TOOLS):
            if name not in members:
                raise ValueError("Original Build111 artifact missing " + name)
        identity_bytes = original.read(members["TestKitIdentity.json"])
        identity = json.loads(identity_bytes)
        if (str(identity.get("build_number")) != "111" or
            identity.get("source_git_sha") != SOURCE_SHA or
            identity.get("prism_sha") != PRISM_SHA or
            not re.fullmatch(r"[a-f0-9]{64}", str(identity.get("unsigned_ipa_sha256", "")))):
            raise ValueError("Original Build111 IPA identity invalid")
        ipa_names = [n for n in members if n.lower().endswith(".ipa")]
        if len(ipa_names) != 1:
            raise ValueError("Expected exact original IPA in source artifact")
        ipa_digest = hashlib.sha256()
        with original.open(members[ipa_names[0]]) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                ipa_digest.update(block)
        if ipa_digest.hexdigest() != identity["unsigned_ipa_sha256"]:
            raise ValueError("Original IPA bytes do not match identity")
        runner_identity = json.loads(original.read(members["RunnerIdentity.json"]))
        if runner_identity.get("installed_ipa_source_sha") != SOURCE_SHA:
            raise ValueError("Original RunnerIdentity is not Build111")
        original_hashes = runner_identity.get("files_sha256", {})
        for name in TOOLS:
            if original_hashes.get(name) != sha(original.read(members[name])):
                raise ValueError("Original tool integrity failure: " + name)
        included = {name: original.read(member) for name, member in members.items()
                    if name.startswith("python/") or name in SUPPORT}
        for name in REQUIRED_PY:
            if "python/" + name not in included:
                raise ValueError("Incomplete Windows portable Python")
        if included["python/python312._pth"].decode("utf-8-sig").replace("\r\n", "\n") != "python312.zip\n.\n..\n":
            raise ValueError("Unexpected portable Python import paths")
    files = {name: (checkout / "tools" / name).read_bytes() for name in TOOLS}
    for name, data in files.items():
        if not data:
            raise ValueError("Empty tool file: " + name)
    match = re.search(r"^RUNNER_VERSION\s*=\s*['\"]([^'\"]+)['\"]", files["b16_testkit.py"].decode("utf-8-sig"), re.M)
    if not match or not match.group(1).startswith("111-"):
        raise ValueError("Invalid Build111 runner version")
    hashes = {name: sha(data) for name, data in files.items()}
    included.update(files)
    tool = {"runner_version": match.group(1), "tool_source_git_sha": head_sha,
            "installed_ipa_source_sha": SOURCE_SHA,
            "runner_sha256": hashes["b16_testkit.py"], "files_sha256": hashes}
    included["RunnerIdentity.json"] = (json.dumps(tool, indent=2) + "\n").encode("utf-8")
    included["README.txt"] = (
        "Bonsai Build111 Quick / Full TestKit ONLY; NO IPA.\n"
        "Keep the existing signed Build111 iPad app installed.\n"
        "Extract all files to Windows x64, double-click RUN_B16_TESTKIT.cmd, enter API key.\n"
        "Quick defaults to safe resume of scheduled restarts in the SAME RESULTS folder.\n"
        "Do not import prior result ZIPs or move RESULTS when resuming.\n"
        "You must completely swipe away the iPad app before reopening for batch switches.\n"
        "Only checkpoints created by this exact runner are resumable; older runner fingerprints fail closed.\n"
        "Quick remains EXPLORATORY, never Full PASS or default promotion.\n"
    ).encode("utf-8")
    included["PACKAGE_MANIFEST.json"] = (json.dumps({
        "kind": "Build111-TestKit-only", "ipa_included": False,
        "source_ipa_sha": SOURCE_SHA, "runner_source_sha": head_sha,
        "files_sha256": {n: sha(b) for n, b in sorted(included.items())},
    }, indent=2) + "\n").encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(included.items()):
            if name.lower().endswith(".ipa"):
                raise ValueError("Never include an IPA")
            z.writestr(name, data)
    result = output.getvalue()
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        verified_names(z)
        if set(z.namelist()) != set(included):
            raise ValueError("Repackage contents mismatch")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--checkout", default=".", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = repackage(args.original, args.checkout, args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit("Refusing to overwrite delivery")
    args.output.write_bytes(data)
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        sha(data) + "  " + args.output.name + "\n", encoding="utf-8")
    print("BUILD111_TESTKIT_ONLY_PASS:", args.output, "sha256="+sha(data))


if __name__ == "__main__":
    main()
