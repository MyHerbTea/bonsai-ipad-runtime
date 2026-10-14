import json
import re
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from tools.documentation_consistency import classify, check_links, check_candidate_references, validate

class DocumentationConsistencyTests(unittest.TestCase):
    def test_unknown_document_is_unclassified(self):
        self.assertIsNone(classify("unknown.md", {"rules": []}))
        self.assertEqual(classify("docs/a.md", {"rules": [{"pattern": "docs/*.md", "status": "DRAFT"}]}), "DRAFT")

    def test_links_are_relative_to_document_and_code_examples_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "README.md").write_text("# Readme\n", encoding="utf-8")
            p = root / "docs/a.md"
            p.write_text("[ok](../README.md)\n[bad](missing.md)\n```md\n[example](absent.md)\n```\n[web](https://example.org)\n", encoding="utf-8")
            errors = check_links(root, p)
            self.assertEqual(len(errors), 1)
            self.assertIn("missing.md", errors[0])

    def test_missing_candidate_file_cannot_be_called_pass_or_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{"path": "absent.py", "scope": "Build109 historical candidate", "availability": "NOT_AVAILABLE", "verification": "NOT_VERIFIED"}]
            self.assertEqual(check_candidate_references(root, rows), [])
            rows[0]["verification"] = "PASS"
            self.assertTrue(check_candidate_references(root, rows))
            rows[0]["verification"] = "NOT_VERIFIED"
            rows[0]["availability"] = "PRESENT"
            self.assertTrue(check_candidate_references(root, rows))

    def test_present_candidate_file_does_not_make_missing_scope_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("", encoding="utf-8")
            rows = [{"path": "a.py", "scope": "", "availability": "PRESENT", "verification": "NOT_VERIFIED"}]
            self.assertTrue(check_candidate_references(root, rows))

    def test_invalid_status_and_missing_navigation_fail_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/optimization").mkdir(parents=True)
            (root / "AGENTS.md").write_text("D:\\codexSpace\\bonsai-ipad-runtime\n[INDEX](docs/INDEX.md)\n", encoding="utf-8")
            (root / "README.md").write_text("# README without navigation\n", encoding="utf-8")
            (root / "docs/INDEX.md").write_text("[State](optimization/CURRENT_STATE.md)\n", encoding="utf-8")
            (root / "docs/optimization/CURRENT_STATE.md").write_text("# State\n", encoding="utf-8")
            (root / "docs/document-authority.json").write_text(json.dumps({"rules": [
                {"pattern": "README.md", "status": "INVALID"},
                {"pattern": "*", "status": "ACTIVE"}
            ]}), encoding="utf-8")
            (root / "docs/optimization/candidate-references.json").write_text('{"references": []}', encoding="utf-8")
            errors = validate(root)
            self.assertTrue(any("invalid authority status" in error for error in errors))
            self.assertTrue(any("required navigation missing: README.md" in error for error in errors))

    def validate_override(self, name, value):
        root = Path(__file__).resolve().parents[2]
        original = Path.read_text
        def read(path, *args, **kwargs):
            return value if path.resolve() == (root / name).resolve() else original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            return validate(root)

    def test_main_identity_conflicts_fail(self):
        root = Path(__file__).resolve().parents[2]
        state = "docs/optimization/CURRENT_STATE.md"
        refs = "docs/optimization/candidate-references.json"
        sha = json.loads((root / refs).read_text(encoding="utf-8"))["source_baseline_sha"]
        state_text = (root / state).read_text(encoding="utf-8")
        ci = "docs/optimization/" + re.search(r"\]\((evidence/main-ci-[^)]+\.json)\)", state_text).group(1)
        for name in (state, ci, refs):
            with self.subTest(document=name):
                text = (root / name).read_text(encoding="utf-8").replace(sha, "a" * 40)
                self.assertTrue(any("main SHA" in e for e in self.validate_override(name, text)))
        for short in (sha[:7], ""):
            with self.subTest(short=short):
                text = (root / state).read_text(encoding="utf-8").replace(sha, short)
                self.assertTrue(any("main SHA" in e for e in self.validate_override(state, text)))

    def test_development_head_can_differ_from_main(self):
        root = Path(__file__).resolve().parents[2]
        name = "docs/optimization/CURRENT_STATE.md"
        text = (root / name).read_text(encoding="utf-8").replace("## Local candidate", "## Local candidate\n\nDevelopment HEAD: " + "b" * 40)
        self.assertEqual(self.validate_override(name, text), [])

    def test_active_workspace_conflicts_fail_but_history_is_allowed(self):
        root = Path(__file__).resolve().parents[2]
        name = "docs/PROJECT_WORKSPACE_POLICY.md"
        text = (root / name).read_text(encoding="utf-8")
        for prefix in ("workspace at ", "directory is exactly "):
            with self.subTest(rule=prefix):
                changed = text.replace(prefix + r"D:\codexSpace\bonsai-ipad-runtime", prefix + r"D:\codexSpace\iPad27B", 1)
                self.assertTrue(any("active workspace" in e for e in self.validate_override(name, changed)))
        historical = text + "\n## Old incident (HISTORICAL)\nD:/codexSpace/iPad27B/old\n## Old plan (SUPERSEDED)\nUse D:\\codexSpace\\iPad27B.\n"
        self.assertEqual(self.validate_override(name, historical), [])

    def test_completed_handoff_cannot_be_active(self):
        root = Path(__file__).resolve().parents[2]
        name = "docs/document-authority.json"
        authority = json.loads((root / name).read_text(encoding="utf-8"))
        for rule in authority["rules"]:
            if rule["pattern"] == "AI_HANDOFF.md":
                rule["status"] = "ACTIVE"
        self.assertTrue(any("completed handoff" in e for e in self.validate_override(name, json.dumps(authority))))
        name = "AI_HANDOFF.md"
        text = (root / name).read_text(encoding="utf-8")
        changed = "\n".join("状态：ACTIVE；旧任务仍生效。" if line.startswith("状态：") else line for line in text.splitlines())
        self.assertTrue(any("completed handoff" in e for e in self.validate_override(name, changed)))

    def test_repository_navigation_and_authority_are_consistent(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(validate(root), [])

if __name__ == "__main__":
    unittest.main()
