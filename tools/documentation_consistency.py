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

def validate(root):
    authority = json.loads((root / "docs/document-authority.json").read_text(encoding="utf-8"))
    errors = []
    for rule in authority["rules"]:
        if rule["status"] not in STATUSES:
            errors.append(f"invalid authority status: {rule}")
    for document in sorted(root.rglob("*.md")):
        relative = document.relative_to(root).as_posix()
        if any(part in {".git", "__pycache__", "artifacts"} for part in document.relative_to(root).parts):
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
        print("PASS documentation classification, local file links and candidate reference scope only")
    raise SystemExit(bool(errors))
