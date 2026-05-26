import tempfile
import unittest
from pathlib import Path

from tools.fde_brain.validate_obsidian import validate_note_content, validate_vault


VALID_NOTE = """---
type: concept
status: evergreen
aliases:
  - Demo Concept
tags:
  - ai-engineering
sources:
  - raw_path: AI Space/raw/markdown/source.md
    normalized_path: AI Space/normalized/markdown/source/sections/001-source.md
    locator: markdown
    source_hash: sha256:abc
    supported_claims:
      - Claim.
created: 2026-05-26T00:00:00+00:00
updated: 2026-05-26T00:00:00+00:00
---

# Demo Concept

## Summary

Summary.

## Core Idea

Core.

## Practical Use

Use.

## Related

- [[Other-Concept|Other Concept]]
"""


class ValidateObsidianTests(unittest.TestCase):
    def test_validates_required_frontmatter_and_sections(self) -> None:
        issues = validate_note_content("Demo-Concept.md", VALID_NOTE, existing_targets={"Other-Concept"})
        self.assertEqual([], issues)

    def test_reports_missing_aliases_and_provenance(self) -> None:
        bad = "---\ntype: concept\ntags: [x]\n---\n\n# Bad\n"
        issues = validate_note_content("Bad.md", bad, existing_targets=set())
        codes = {i.code for i in issues}
        self.assertIn("missing-aliases", codes)
        self.assertIn("missing-sources", codes)
        self.assertIn("missing-section", codes)

    def test_accepts_crlf_frontmatter(self) -> None:
        content = VALID_NOTE.replace("\n", "\r\n")
        issues = validate_note_content("Demo-Concept.md", content, existing_targets={"Other-Concept"})
        self.assertEqual([], issues)

    def test_vault_resolves_wikilinks_by_filename_and_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "Demo-Concept.md").write_text(VALID_NOTE, encoding="utf-8")
            other = VALID_NOTE.replace("Demo Concept", "Other Concept").replace("[[Other-Concept|Other Concept]]", "")
            (vault / "Other-Concept.md").write_text(other, encoding="utf-8")

            issues = validate_vault(vault)

            self.assertEqual([], issues)

    def test_vault_reports_broken_wikilinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            note = VALID_NOTE.replace("[[Other-Concept|Other Concept]]", "[[Missing Note]]")
            (vault / "Demo-Concept.md").write_text(note, encoding="utf-8")

            issues = validate_vault(vault)

            self.assertTrue(any(i.code == "broken-wikilink" for i in issues))


if __name__ == "__main__":
    unittest.main()
