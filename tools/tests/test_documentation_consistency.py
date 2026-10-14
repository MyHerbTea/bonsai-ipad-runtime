import json
import tempfile
import unittest
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

    def test_repository_navigation_and_authority_are_consistent(self):
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(validate(root), [])

if __name__ == "__main__":
    unittest.main()
