#!/usr/bin/env python3
"""Tests for the version-annotation checker's detection rules."""

import unittest

import check_version_annotations as cva


class AnnotationRegexTest(unittest.TestCase):
    def _is_annotation(self, text):
        return bool(cva._ANNOTATION_RE.search(text)) and not cva.is_doc_link(text)

    def test_matches_current_major(self):
        for text in ("ABP 10.6+", "available from **ABP 10.6+**",
                     "this option is ABP 10.6+", "ABP 10.6-only"):
            self.assertTrue(self._is_annotation(text), text)

    def test_matches_future_major_and_minor(self):
        # The whole point of the fix: not hardcoded to major 10.
        for text in ("ABP 11.0+", "requires ABP 11.0", "since ABP 12.1",
                     "available in ABP 11.2", "ABP 11.0-only"):
            self.assertTrue(self._is_annotation(text), text)

    def test_ignores_non_abp_versions(self):
        for text in (".NET 8.0+", "C# 12+", "requires .NET 9.0",
                     "pinned to 10.5.0", "@abp/ng.core 10.5.0"):
            self.assertFalse(self._is_annotation(text), text)

    def test_ignores_doc_links(self):
        self.assertFalse(self._is_annotation(
            "https://github.com/abpframework/abp/blob/rel-10.5/docs/x.md"))

    def test_bare_version_without_abp_is_not_flagged(self):
        # Requiring "ABP" avoids false positives; "10.6+" alone is not an ABP claim.
        self.assertFalse(self._is_annotation("bumped to 10.6+ recently"))


class SymbolMemberMatchTest(unittest.TestCase):
    def test_member_is_last_dotted_segment(self):
        self.assertEqual("ConvertUnspecifiedToUtc",
                         "ITimezoneProvider.ConvertUnspecifiedToUtc".split(".")[-1])
        self.assertEqual("AbpAntiforgery", "AbpAntiforgery".split(".")[-1])


class AbpNextRegionTest(unittest.TestCase):
    def test_member_inside_guard_is_found(self):
        src = "void A(){}\n#if ABP_NEXT\nvoid B(){ Foo(); }\n#endif\nvoid C(){}"
        region = cva.abp_next_regions(src)
        self.assertIn("Foo", region)
        self.assertNotIn("void A", region)
        self.assertNotIn("void C", region)

    def test_member_outside_guard_is_not_found(self):
        # Foo is outside the guard; an empty ABP_NEXT guard exists elsewhere.
        src = "void A(){ Foo(); }\n#if ABP_NEXT\n#endif"
        region = cva.abp_next_regions(src)
        self.assertNotIn("Foo", region)

    def test_no_guard_yields_empty(self):
        self.assertEqual(cva.abp_next_regions("void A(){ Foo(); }").strip(), "")

    def test_nested_if_inside_guard(self):
        src = "#if ABP_NEXT\n#if DEBUG\nBar();\n#endif\nBaz();\n#endif"
        region = cva.abp_next_regions(src)
        self.assertIn("Bar", region)
        self.assertIn("Baz", region)


if __name__ == "__main__":
    unittest.main()
