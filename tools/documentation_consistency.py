"""Offline documentation navigation and evidence-scope checks (stdlib only)."""
import fnmatch
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATUSES = {"ACTIVE", "REFERENCE", "HISTORICAL", "DRAFT", "SUPERSEDED"}

def classify(path, authority):
    for rule in authority["rules"]:
        if fnmatch.fnmatchcase(path, rule["pattern"]):
            return rule["status"]
    return None

def ignored_document_path(path):
    parts = Path(path).parts
    return (
        any(part in {".git", "__pycache__", "artifacts"} for part in parts)
        or bool(parts and parts[0] in {".pytest_cache", "deliveries"})
    )

def check_links(root, document, unavailable=()):
    source = document.read_text(encoding="utf-8-sig")
    source = re.sub(r"(?ms)^ *(```|~~~).*?^ *\1[^\n]*$", "", source)
    errors = []
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", source):
        target = target.strip().split(' "', 1)[0].strip("<>")
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        path = (document.parent / unquote(parts.path)).resolve()
        if path != root.resolve() and root.resolve() not in path.parents:
            errors.append(f"{document.relative_to(root)}: link escapes repository: {target}")
        elif not path.exists() and target not in unavailable:
            errors.append(f"{document.relative_to(root)}: missing link: {target}")
    return errors

def check_candidate_references(root, rows):
    errors = []
    for row in rows:
        path = root / row["path"]
        if not row.get("scope"):
            errors.append(f"candidate reference lacks scope: {row['path']}")
        actual = "PRESENT" if path.exists() else "NOT_AVAILABLE"
        if row.get("availability") != actual:
            errors.append(f"candidate availability mismatch: {row['path']}")
        if row.get("verification") != "NOT_VERIFIED":
            errors.append(f"path inventory cannot claim verification: {row['path']}")
    return errors

def check_main_identity(root, references):
    """Compare documented snapshot identities; never compare a development HEAD."""
    state = (root / "docs/optimization/CURRENT_STATE.md").read_text(encoding="utf-8")
    main = re.search(r"(?ms)^## Remote main\n(.*?)(?=^## |\Z)", state)
    hashes = re.findall(r"审计时远端 main 完整 SHA：\s*" + chr(96) + r"([0-9a-fA-F]{40})" + chr(96), main.group(1) if main else "")
    if len(hashes) != 1:
        return ["main SHA: CURRENT_STATE requires one full remote-main snapshot SHA"]
    sha = hashes[0].lower()
    ci = re.search(r"(?ms)^## CI\n(.*?)(?=^## |\Z)", state)
    links = re.findall(r"\]\((evidence/main-ci-[^)]+\.json)\)", ci.group(1) if ci else "")
    if len(links) != 1:
        return ["main SHA: CURRENT_STATE requires one current CI metadata link"]
    folder = (root / "docs/optimization").resolve()
    path = (folder / links[0]).resolve()
    if folder not in path.parents:
        return ["main SHA: CI metadata link escapes its document directory"]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        run = snapshot.get("run", {})
        ci_sha = run.get("head_sha") if isinstance(run, dict) else None
    except (OSError, ValueError, AttributeError) as exc:
        return [f"main SHA: CI metadata unavailable or invalid: {exc}"]
    errors = []
    for label, value in (("CI run.head_sha", ci_sha), ("candidate source_baseline_sha", references.get("source_baseline_sha"))):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", value) or value.lower() != sha:
            errors.append(f"main SHA mismatch: CURRENT_STATE vs {label}")
    return errors

def check_active_workspace(root):
    """Only explicitly historical/superseded policy sections may retain old paths."""
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    section = re.search(r"(?ms)^## 1\. Authoritative Workspace\n(.*?)(?=^## |\Z)", agents)
    paths = re.findall(r"[A-Za-z]:[\\/][^\s]+", section.group(1) if section else "")
    if len(paths) != 1:
        return ["active workspace: AGENTS requires one authoritative directory"]
    normalize = lambda value: value.rstrip(".,;").replace("\\", "/").lower()
    expected = normalize(paths[0])
    policy = (root / "docs/PROJECT_WORKSPACE_POLICY.md").read_text(encoding="utf-8")
    active, historical = [], False
    for line in policy.splitlines():
        if line.startswith("## "):
            historical = bool(re.search(r"\((?:HISTORICAL|SUPERSEDED)\b[^)]*\)", line))
        if not historical:
            active.append(line)
    text = "\n".join(active)
    errors = []
    for prefix in ("workspace at ", "directory is exactly "):
        declarations = re.findall(re.escape(prefix) + r"([A-Za-z]:[\\/][^\s]+)", text)
        if len(declarations) != 1 or normalize(declarations[0]) != expected:
            errors.append(f"active workspace: policy {prefix.strip()} differs from AGENTS")
    for path in re.findall(r"[A-Za-z]:[\\/]codexSpace[\\/][^\s]+", text, re.I):
        normalized = normalize(path)
        if normalized != expected and not normalized.startswith(expected + "/"):
            errors.append(f"active workspace: conflicting policy directory: {path}")
    return errors

def check_completed_handoff(root, authority):
    try:
        text = (root / "AI_HANDOFF.md").read_text(encoding="utf-8")
    except OSError:
        return ["completed handoff document is missing"]
    if classify("AI_HANDOFF.md", authority) != "HISTORICAL" or not re.search(r"(?m)^状态：HISTORICAL[；。]", text):
        return ["completed handoff must remain HISTORICAL in authority and document status"]
    return []

def validate(root):
    authority = json.loads((root / "docs/document-authority.json").read_text(encoding="utf-8"))
    errors = []
    for rule in authority["rules"]:
        if rule["status"] not in STATUSES:
            errors.append(f"invalid authority status: {rule}")
    for document in sorted(root.rglob("*.md")):
        relative_path = document.relative_to(root)
        relative = relative_path.as_posix()
        # Root-level ignored build/cache output is not repository documentation.
        if ignored_document_path(relative_path):
            continue
        status = classify(relative, authority)
        if status not in STATUSES:
            errors.append(f"unclassified document: {relative}")
        unavailable = []
        for exception in authority.get("unavailable_historical_links", []):
            if exception["document"] == relative:
                if status != "HISTORICAL" or not exception.get("scope") or exception.get("verification") != "NOT_VERIFIED":
                    errors.append(f"invalid historical unavailable-link scope: {relative}")
                else:
                    unavailable.extend(exception["targets"])
        errors.extend(check_links(root, document, unavailable))
    references = json.loads((root / "docs/optimization/candidate-references.json").read_text(encoding="utf-8"))
    errors.extend(check_candidate_references(root, references["references"]))
    errors.extend(check_main_identity(root, references))
    errors.extend(check_active_workspace(root))
    errors.extend(check_completed_handoff(root, authority))
    navigation = [
        ("AGENTS.md", "docs/INDEX.md"),
        ("docs/INDEX.md", "optimization/CURRENT_STATE.md"),
        ("README.md", "docs/INDEX.md"),
    ]
    for file, link in navigation:
        if f"]({link})" not in (root / file).read_text(encoding="utf-8"):
            errors.append(f"required navigation missing: {file} -> {link}")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    if "D:\\codexSpace\\bonsai-ipad-runtime" not in agents or agents.count("```") % 2:
        errors.append("AGENTS workspace or fenced block is inconsistent")
    return errors

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    errors = validate(root)
    for error in errors:
        print("FAIL " + error)
    if not errors:
        print("PASS documentation classification, links, evidence identities, active workspace and completed handoff scope only")
    raise SystemExit(bool(errors))
