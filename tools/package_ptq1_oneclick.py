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
        if number == "128" and file.name.startswith("README_BUILD") and file.name != "README_BUILD128_CN.md":
            continue
        if number in ("127", "128") and file.suffix.lower() == ".cmd":
            allowed = {"RUN_Q8_METAL_B8_QUICK.cmd"}
            if number == "128": allowed.add("RUN_Q8_ACKNOWLEDGE.cmd")
            if file.name not in allowed: continue
        if number == "127" and file.name == "acknowledge_q8_interruption.py":
            continue
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
        "acknowledge_failure_source_shas": (["2d5b75430ac152da7b03c0e4f0edb18b1a9ac5f2"] if number == "126" else
            (["2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158"] if number == "128" else [])),
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
    if number == "126":
        for filename in ("BUILD126_POLICY.txt", "BUILD126_TESTS.txt"):
            shutil.copy2(ROOT / "build" / filename, checks / filename)
    elif number in ("127", "128"):
        for filename in (f"BUILD{number}_POLICY.txt", f"BUILD{number}_TESTS.txt"):
            shutil.copy2(ROOT / "build" / filename, checks / filename)
    (kit / "BUILD_INFO.txt").write_text(
        f"Build{number} PTQ1 candidates; concentrated prefill comparison included\n"
        f"Source: {source}\nWorkflow: {os.environ['GITHUB_RUN_ID']}\n"
        "Unsigned IPA: sign once with your existing iPad installation method.\n"
        "Target: M5 iPad Pro 12GB; official PTQ1 GGUF only.\n"
        "Device runtime compilation, numerical quality and performance: NOT_RUN.\n"
        "All candidates share one IPA. Production defaults are restored after benchmark.\n"
        "No candidate is a winner until actual device gates pass.\n", encoding="utf-8")
    (kit / f"BUILD{number}_DELIVERY_REPORT_CN.md").write_text(
        f"# Build{number} 交付与证据状态\n\n"
        f"源码：{source}\n\n分支：{os.environ.get('GITHUB_REF_NAME', 'UNKNOWN')}\n\n"
        f"Apple Release CI：[运行记录](https://github.com/MyHerbTea/bonsai-ipad-runtime/actions/runs/{os.environ['GITHUB_RUN_ID']})\n\n"
        f"IPA SHA256：{sha(ipa)}\n\n"
        "构建及检查记录：同源码专项自动化、Swift策略/语法、实际ARM64原始/单行/双行数值parity及ASAN/UBSAN测试、双行共享Q8及无spill汇编门禁、Release构建、便携环境与哈希打包。每项实际执行/skip状态以CI_EVIDENCE/CI_TESTS.txt为准，skip不作为通过证据。\n\n"
        "真机性能：NOT_RUN，待用户安装本IPA并双击RUN_PREFILL_COMPARE.cmd。CI成功、数值正确和汇编含SDOT均不证明性能收益。\n\n"
        "保持生产默认，不晋级SDOT，不创建Stable Release。Build125九请求A/B/C集中实验会自动输出COMPARISON.md、完整JSON/CSV和统一results.zip。\n\n"
        "Build124单行SDOT保留为基线，不另做独立确认。A原始0/B单行64/C双行128，主要比较C/B。待用户提供一次测试结果后，决定保留双行或停止CPU微内核方向转具体GPU算子；不自动执行真机、不新增独立分析阶段、不改生产默认。\n",
        encoding="utf-8")
    if number == "126":
        (kit / f"BUILD{number}_DELIVERY_REPORT_CN.md").write_text(
            f"# Build126 固定 Q8_0 候选\n\n源码：{source}\n\n"
            f"CI：https://github.com/MyHerbTea/bonsai-ipad-runtime/actions/runs/{os.environ['GITHUB_RUN_ID']}\n\n"
            f"IPA SHA256：{sha(ipa)}\n\n"
            "入口RUN_Q8_BASELINE.cmd；Full独立入口RUN_Q8_FULL.cmd；中断标记仅可经RUN_Q8_ACKNOWLEDGE.cmd显式归档确认。先读README_BUILD126_CN.md。\n"
            "实际已执行/skip以CI_EVIDENCE/CI_TESTS.txt为准，skip不计通过。\n"
            "M5真机NOT_RUN；生产默认不变；32K未开放；未晋级Certified Stable。\n", encoding="utf-8")
        (kit / "BUILD_INFO.txt").write_text(
            f"Build126 fixed Q8 candidate; source {source}; CI {os.environ['GITHUB_RUN_ID']}\n"
            "16K/Q8_0/B8/8/GPU56/threads6/mmap, flag64 existing single-row path.\n"
            "Model PTQ1_0 is independent of KV Q8_0. Device NOT_RUN. No default promotion.\n", encoding="utf-8")
        shutil.copy2(ROOT / "docs/build126/audit-and-plan.md", kit / "SOURCE_AUDIT_AND_PLAN.md")
    if number == "127":
        (kit / "BUILD_INFO.txt").write_text(
            f"Build127 fixed 16K/B8/Q8_0; opt-in PTQ1 Metal B8 screen; source {source}; CI {os.environ['GITHUB_RUN_ID']}\n"
            "A flags64 vs B flags320, with CPU flags held at64. Four-request short ABBA Quick only.\n"
            "Device validation: NOT_RUN. Production defaults unchanged. No Full or Certified Stable claim.\n",
            encoding="utf-8")
        (kit / "BUILD127_DELIVERY_REPORT_CN.md").write_text(
            f"# Build127 固定 Q8 + PTQ1 Metal B8 Quick 候选\n\n源码：{source}\n\n"
            f"CI：https://github.com/MyHerbTea/bonsai-ipad-runtime/actions/runs/{os.environ['GITHUB_RUN_ID']}\n\n"
            f"IPA SHA256：{sha(ipa)}\n\n"
            "交付包含一个 unsigned IPA 和独立 Q8 Metal B8 TestKit。先读 README_BUILD127_CN.md。\n"
            "自动化测试与实际 skip 以 CI_EVIDENCE/CI_TESTS.txt 为准。\n"
            "M5 真机：NOT_RUN；生产默认不变；只提供 16K/B8/Q8_0 的四请求 Quick，不是 Full 或稳定认证。\n",
            encoding="utf-8")
        for relative, destination in (
            ("docs/superpowers/specs/2026-10-27-build127-q8-metal-b8-design.md", "SOURCE_AUDIT_AND_DESIGN.md"),
            ("docs/superpowers/plans/2026-10-27-build127-q8-metal-b8.md", "IMPLEMENTATION_PLAN.md"),
        ):
            shutil.copy2(ROOT / relative, kit / destination)
    if number == "128":
        (kit / "BUILD_INFO.txt").write_text(
            f"Build128 fixed 16K/B8/Q8_0; opt-in PTQ1 Metal B8; source {source}; CI {os.environ['GITHUB_RUN_ID']}\n"
            "Four-request ABBA Quick uses a fixed 128-token input and 32-token output cap; 60 seconds per request, 240 seconds total.\n"
            "Device validation: NOT_RUN. Production defaults unchanged. No Full or Certified Stable claim.\n",
            encoding="utf-8")
        (kit / "BUILD128_DELIVERY_REPORT_CN.md").write_text(
            f"# Build128 固定 Q8 + PTQ1 Metal B8 性能候选\n\n源码：{source}\n\n"
            f"CI：https://github.com/MyHerbTea/bonsai-ipad-runtime/actions/runs/{os.environ['GITHUB_RUN_ID']}\n\n"
            f"IPA SHA256：{sha(ipa)}\n\n"
            "交付包含 unsigned IPA 与独立 Q8 Metal B8 TestKit。Quick 为四请求 ABBA、128输入/32输出、单请求限时60秒、全程上限240秒。\n"
            "Q8隔离恢复需完整匹配已保存的Build126 Full人工中止证据；M5性能NOT_RUN，生产默认未改。\n",
            encoding="utf-8")
        for relative, destination in (
            ("docs/superpowers/specs/2026-10-27-build128-q8-performance-enablement.md", "SOURCE_AUDIT_AND_DESIGN.md"),
            ("docs/superpowers/plans/2026-10-27-build128-q8-performance.md", "IMPLEMENTATION_PLAN.md"),
            ("tools/PTQ1_ONECLICK/README_BUILD128_CN.md", "README_BUILD128_CN.md"),
        ):
            shutil.copy2(ROOT / relative, kit / destination)
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
        if number in ("127", "128"):
            assert any(name.endswith("RUN_Q8_METAL_B8_QUICK.cmd") for name in archive.namelist())
            assert not any(name.endswith("RUN_Q8_BASELINE.cmd") or name.endswith("RUN_Q8_FULL.cmd")
                           for name in archive.namelist())
            if number == "127":
                assert not any(name.endswith("RUN_Q8_ACKNOWLEDGE.cmd") for name in archive.namelist())
            else:
                assert any(name.endswith("RUN_Q8_ACKNOWLEDGE.cmd") for name in archive.namelist())
        else:
            assert any(name.endswith("RUN_BONSAI_PTQ1_ONECLICK_BENCHMARK.cmd") for name in archive.namelist())
        if number == "126":
            assert any(name.endswith("RUN_Q8_ACKNOWLEDGE.cmd") for name in archive.namelist())
        assert len([name for name in archive.namelist() if name.endswith(".ipa")]) == 1
    Path(str(output) + ".sha256").write_text(sha(output) + "  " + output.name + "\n", encoding="utf-8")
    if number in ("126", "127", "128"):
        standalone_name = (f"BONSAI_BUILD{number}_Q8_TESTKIT.zip" if number in ("126", "128")
            else "BONSAI_BUILD127_Q8_METAL_B8_TESTKIT.zip")
        standalone = kit.parent / standalone_name
        separate = {name: digest for name, digest in manifest.items()
                    if not name.endswith((".ipa", ".ipa.sha256"))}
        with zipfile.ZipFile(standalone, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in separate:
                archive.write(kit / name, kit.name + "/" + name)
            archive.writestr(kit.name + "/DELIVERY_SHA256.json", json.dumps(separate, indent=2) + "\n")
        with zipfile.ZipFile(standalone) as archive:
            assert archive.testzip() is None
            if number in ("127", "128"):
                assert any(name.endswith("RUN_Q8_METAL_B8_QUICK.cmd") for name in archive.namelist())
                assert not any(name.endswith(".ipa") for name in archive.namelist())
                if number == "128":
                    assert any(name.endswith("RUN_Q8_ACKNOWLEDGE.cmd") for name in archive.namelist())
            else:
                assert any(name.endswith("RUN_Q8_ACKNOWLEDGE.cmd") for name in archive.namelist())
            for name, digest in separate.items():
                assert hashlib.sha256(archive.read(kit.name + "/" + name)).hexdigest() == digest
        Path(str(standalone) + ".sha256").write_text(sha(standalone) + "  " + standalone.name + "\n")
    print("Combined delivery integrity: PASS; device validation: NOT_RUN")

if __name__ == "__main__":
    build()
