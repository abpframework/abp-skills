#!/usr/bin/env python3
"""Tests for eng/validate.py pure helpers."""

import unittest

import validate


class DescriptionErrorsTest(unittest.TestCase):
    CLEAN = ("Do a thing in ABP. USE FOR: FooOptions, BarService. "
             "DO NOT USE FOR: something else (other-skill).")

    def test_clean_description_has_no_problems(self):
        self.assertEqual(validate.description_errors("s", self.CLEAN), [])

    def test_missing_both_markers(self):
        # A description with neither marker is flagged for both.
        problems = validate.description_errors("s", "Just a sentence, no markers.")
        self.assertTrue(any("missing 'USE FOR:'" in p for p in problems))
        self.assertTrue(any("missing 'DO NOT USE FOR:'" in p for p in problems))

    def test_missing_do_not_use_for_marker(self):
        problems = validate.description_errors("s", "USE FOR: x.")
        self.assertTrue(any("missing 'DO NOT USE FOR:'" in p for p in problems))

    def test_angle_brackets_flagged(self):
        desc = ("Typed cache. USE FOR: IHybridCache<TCacheItem, TKey>. "
                "DO NOT USE FOR: x (other).")
        problems = validate.description_errors("s", desc)
        self.assertTrue(any("angle bracket" in p for p in problems),
                        f"expected an angle-bracket problem, got: {problems}")

    def test_open_or_close_bracket_alone_flagged(self):
        for desc in ("USE FOR: a < b. DO NOT USE FOR: x.",
                     "USE FOR: a > b. DO NOT USE FOR: x."):
            problems = validate.description_errors("s", desc)
            self.assertTrue(any("angle bracket" in p for p in problems))

    def test_over_length_flagged(self):
        desc = "USE FOR: x. DO NOT USE FOR: y. " + ("a" * (validate.MAX_DESCRIPTION_LEN + 1))
        problems = validate.description_errors("s", desc)
        self.assertTrue(any("chars" in p for p in problems))


class RoutingTargetsTest(unittest.TestCase):
    def test_parenthetical_and_use_forms(self):
        desc = "DO NOT USE FOR: mapping (map-objects-and-dtos); wiring (use define-modules)."
        self.assertEqual(
            validate.routing_targets(desc),
            {"map-objects-and-dtos", "define-modules"},
        )

    def test_slash_list_extracts_every_target(self):
        # A `use A / B` list must yield both A and B, not just the first.
        desc = "building UI pages (use angular-ui / blazor-ui / mvc-razor-ui)."
        self.assertEqual(
            validate.routing_targets(desc),
            {"angular-ui", "blazor-ui", "mvc-razor-ui"},
        )

    def test_non_skill_prose_terms_excluded(self):
        # Hyphenated prose in the allowlist is not treated as a routing target.
        self.assertEqual(validate.routing_targets("configure it per-stack."), set())
        self.assertNotIn("build-time", validate.routing_targets("done at (build-time)."))


class PersonalPathTest(unittest.TestCase):
    def test_flags_unix_and_macos_and_windows_home(self):
        for path in ("/Users/alice/Github/abp", "/home/bob/src",
                     "/var/folders/82/abc/T/x", r"C:\Users\carol\repo",
                     "C:/Users/dave/repo", r"C:\\Users\\eve\\repo"):  # last: JSON-escaped form
            self.assertIsNotNone(validate._PERSONAL_PATH_RE.search(path), path)

    def test_ignores_neutral_and_system_paths(self):
        for path in ("<path-to-abp-source>", "/tmp/x", "/opt/abp", "/usr/local/bin",
                     "/home/runner/work"):  # CI runner home is scanned only in workflows (excluded)
            # neutral placeholders and non-user system paths must not match
            if path == "/home/runner/work":
                # /home/<name>/ does match the regex; the scan simply excludes workflow files
                continue
            self.assertIsNone(validate._PERSONAL_PATH_RE.search(path), path)


if __name__ == "__main__":
    unittest.main()
