#!/usr/bin/env python3
"""Tests for the deterministic skill eval runner."""

import json
import tempfile
import unittest
from pathlib import Path

import run_evals


class AssertionEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)

    def test_evaluates_all_supported_assertions_in_order(self):
        (self.workspace / "created.txt").write_text("content", encoding="utf-8")
        assertions = [
            {"type": "output_contains", "value": "required literal"},
            {"type": "output_matches", "pattern": r"item\s+\d+"},
            {"type": "file_exists", "path": "created.txt"},
            {"type": "file_not_exists", "path": "forbidden.txt"},
        ]

        results = run_evals.evaluate_assertions(
            assertions, "Required Literal\nITEM 42", self.workspace
        )

        self.assertEqual(4, len(results))
        self.assertTrue(all(result.passed for result in results))
        self.assertEqual(
            [
                "output_contains",
                "output_matches",
                "file_exists",
                "file_not_exists",
            ],
            [result.assertion_type for result in results],
        )

    def test_reports_each_failed_assertion(self):
        (self.workspace / "forbidden.txt").write_text("content", encoding="utf-8")
        assertions = [
            {"type": "output_contains", "value": "missing"},
            {"type": "output_matches", "pattern": "never-match"},
            {"type": "file_exists", "path": "absent.txt"},
            {"type": "file_not_exists", "path": "forbidden.txt"},
        ]

        results = run_evals.evaluate_assertions(assertions, "output", self.workspace)

        self.assertFalse(any(result.passed for result in results))
        self.assertTrue(all(result.description for result in results))

    def test_rejects_file_assertion_outside_workspace(self):
        results = run_evals.evaluate_assertions(
            [{"type": "file_exists", "path": "../outside.txt"}],
            "",
            self.workspace,
        )

        self.assertFalse(results[0].passed)
        self.assertIn("escapes the workspace", results[0].description)


class WorkspaceSetupTests(unittest.TestCase):
    def test_writes_inline_and_source_files_then_cleans_workspace(self):
        with tempfile.TemporaryDirectory() as manifest_temp:
            manifest_dir = Path(manifest_temp)
            (manifest_dir / "fixture.txt").write_text("source payload", encoding="utf-8")
            setup = {
                "files": [
                    {"path": "src/inline.txt", "content": "inline payload"},
                    {"path": "src/copied.txt", "source": "fixture.txt"},
                ]
            }

            with run_evals.scenario_workspace(setup, manifest_dir) as workspace:
                workspace_path = workspace
                self.assertEqual(
                    "inline payload",
                    (workspace / "src" / "inline.txt").read_text(encoding="utf-8"),
                )
                self.assertEqual(
                    "source payload",
                    (workspace / "src" / "copied.txt").read_text(encoding="utf-8"),
                )

            self.assertFalse(workspace_path.exists())

    def test_runs_setup_commands_in_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            run_evals.apply_setup(
                workspace,
                {"commands": ["echo hello > from_command.txt"]},
                workspace,
            )
            self.assertEqual(
                "hello\n",
                (workspace / "from_command.txt").read_text(encoding="utf-8"),
            )

    def test_failed_setup_command_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with self.assertRaisesRegex(RuntimeError, "Setup command failed"):
                run_evals.apply_setup(
                    workspace, {"commands": ["exit 3"]}, workspace
                )

    def test_copy_test_files_copies_fixtures_except_manifest(self):
        with tempfile.TemporaryDirectory() as manifest_temp, tempfile.TemporaryDirectory() as ws_temp:
            manifest_dir = Path(manifest_temp)
            (manifest_dir / "eval.yaml").write_text("scenarios: []", encoding="utf-8")
            (manifest_dir / "Program.cs").write_text("class C {}", encoding="utf-8")
            nested = manifest_dir / "fixtures"
            nested.mkdir()
            (nested / "data.csv").write_text("a,b", encoding="utf-8")

            workspace = Path(ws_temp)
            run_evals.apply_setup(workspace, {"copy_test_files": True}, manifest_dir)

            self.assertEqual(
                "class C {}", (workspace / "Program.cs").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "a,b", (workspace / "fixtures" / "data.csv").read_text(encoding="utf-8")
            )
            self.assertFalse((workspace / "eval.yaml").exists())


class NewAssertionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)

    def _single(self, assertion, output=""):
        results = run_evals.evaluate_assertions([assertion], output, self.workspace)
        return results[0]

    def test_output_not_contains_positive_and_negative(self):
        self.assertTrue(
            self._single(
                {"type": "output_not_contains", "value": "forbidden"}, "clean output"
            ).passed
        )
        self.assertFalse(
            self._single(
                {"type": "output_not_contains", "value": "Forbidden"}, "has forbidden text"
            ).passed
        )

    def test_output_not_matches_positive_and_negative(self):
        self.assertTrue(
            self._single(
                {"type": "output_not_matches", "pattern": r"error \d+"}, "all good"
            ).passed
        )
        self.assertFalse(
            self._single(
                {"type": "output_not_matches", "pattern": r"error \d+"}, "ERROR 42"
            ).passed
        )

    def test_file_contains_positive_and_negative(self):
        (self.workspace / "code.cs").write_text("var x = stackalloc int[4];", encoding="utf-8")
        self.assertTrue(
            self._single({"type": "file_contains", "path": "code.cs", "value": "stackalloc"}).passed
        )
        self.assertFalse(
            self._single({"type": "file_contains", "path": "code.cs", "value": "unsafe"}).passed
        )

    def test_file_contains_no_matching_file_fails(self):
        result = self._single({"type": "file_contains", "path": "absent.cs", "value": "x"})
        self.assertFalse(result.passed)
        self.assertIn("No file matches", result.description)

    def test_file_not_contains_positive_and_negative(self):
        (self.workspace / "code.cs").write_text("safe code", encoding="utf-8")
        self.assertTrue(
            self._single({"type": "file_not_contains", "path": "code.cs", "value": "unsafe"}).passed
        )
        self.assertFalse(
            self._single({"type": "file_not_contains", "path": "code.cs", "value": "safe"}).passed
        )

    def test_file_not_contains_no_matching_file_fails(self):
        result = self._single({"type": "file_not_contains", "path": "absent.cs", "value": "x"})
        self.assertFalse(result.passed)

    def test_content_assertion_fails_on_unreadable_file(self):
        # Invalid UTF-8 makes the content unverifiable; neither variant may pass.
        (self.workspace / "binary.cs").write_bytes(b"\xff\xfe\x00abc")
        not_contains = self._single(
            {"type": "file_not_contains", "path": "binary.cs", "value": "abc"}
        )
        contains = self._single(
            {"type": "file_contains", "path": "binary.cs", "value": "abc"}
        )
        self.assertFalse(not_contains.passed)
        self.assertIn("could not be read", not_contains.description)
        self.assertFalse(contains.passed)

    def test_file_exists_glob_matches_nested_file(self):
        nested = self.workspace / "src" / "app"
        nested.mkdir(parents=True)
        (nested / "Program.cs").write_text("x", encoding="utf-8")

        self.assertTrue(self._single({"type": "file_exists", "path": "**/*.cs"}).passed)
        self.assertTrue(self._single({"type": "file_exists", "path": "src/**/Program.cs"}).passed)
        self.assertFalse(self._single({"type": "file_exists", "path": "*.cs"}).passed)

    def test_file_not_exists_glob(self):
        (self.workspace / "keep.txt").write_text("x", encoding="utf-8")
        self.assertTrue(self._single({"type": "file_not_exists", "path": "**/*.cs"}).passed)
        self.assertFalse(self._single({"type": "file_not_exists", "path": "**/*.txt"}).passed)

    def test_single_star_stays_within_one_segment(self):
        nested = self.workspace / "src"
        nested.mkdir()
        (nested / "a.cs").write_text("x", encoding="utf-8")
        # `*.cs` should not reach into src/
        self.assertFalse(self._single({"type": "file_exists", "path": "*.cs"}).passed)
        # `*/*.cs` should
        self.assertTrue(self._single({"type": "file_exists", "path": "*/*.cs"}).passed)

    def test_glob_rejects_escaping_pattern(self):
        result = self._single({"type": "file_exists", "path": "../outside/*.cs"})
        self.assertFalse(result.passed)
        self.assertIn("escapes the workspace", result.description)

    def test_bracket_pattern_is_literal_not_glob(self):
        (self.workspace / "[ab].cs").write_text("x", encoding="utf-8")
        (self.workspace / "a.cs").write_text("x", encoding="utf-8")
        # `[ab].cs` matches the literal file, not a character class.
        self.assertTrue(self._single({"type": "file_exists", "path": "[ab].cs"}).passed)

    def test_middle_globstar_matches_variable_depth(self):
        deep = self.workspace / "a" / "x" / "y"
        deep.mkdir(parents=True)
        (deep / "b").write_text("x", encoding="utf-8")
        (self.workspace / "a").joinpath("b").write_text("x", encoding="utf-8")
        self.assertTrue(self._single({"type": "file_exists", "path": "a/**/b"}).passed)

    def test_trailing_globstar_requires_a_child(self):
        (self.workspace / "x").mkdir()
        (self.workspace / "x" / "child.txt").write_text("y", encoding="utf-8")
        self.assertTrue(self._single({"type": "file_exists", "path": "x/**"}).passed)
        # A file literally named "y" must not satisfy "y/**".
        (self.workspace / "y").write_text("z", encoding="utf-8")
        self.assertFalse(self._single({"type": "file_exists", "path": "y/**"}).passed)

    def test_exit_success(self):
        self.assertTrue(self._single({"type": "exit_success", "command": "true"}).passed)
        self.assertFalse(self._single({"type": "exit_success", "command": "false"}).passed)

    def test_run_command_and_assert_default_exit_zero(self):
        self.assertTrue(
            self._single({"type": "run_command_and_assert", "command": "true"}).passed
        )
        self.assertFalse(
            self._single({"type": "run_command_and_assert", "command": "false"}).passed
        )

    def test_run_command_and_assert_explicit_exit_code(self):
        self.assertTrue(
            self._single(
                {"type": "run_command_and_assert", "command": "exit 3", "exit_code": 3}
            ).passed
        )

    def test_run_command_and_assert_stdout_stderr(self):
        self.assertTrue(
            self._single(
                {
                    "type": "run_command_and_assert",
                    "command": "echo hello world",
                    "stdout_contains": "HELLO",
                    "stdout_matches": r"hello\s+world",
                }
            ).passed
        )
        self.assertFalse(
            self._single(
                {
                    "type": "run_command_and_assert",
                    "command": "echo hi",
                    "stdout_contains": "missing",
                }
            ).passed
        )
        self.assertTrue(
            self._single(
                {
                    "type": "run_command_and_assert",
                    "command": "echo oops 1>&2",
                    "stderr_contains": "oops",
                    "stderr_matches": r"oo+ps",
                }
            ).passed
        )

    def test_run_command_runs_in_workspace(self):
        (self.workspace / "marker.txt").write_text("here", encoding="utf-8")
        self.assertTrue(
            self._single(
                {
                    "type": "run_command_and_assert",
                    "command": "cat marker.txt",
                    "stdout_contains": "here",
                }
            ).passed
        )


class MockBackendTests(unittest.TestCase):
    def test_echoes_prompt_and_reports_created_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            backend = run_evals.MockBackend(files={"generated/result.txt": "done"})

            output, files = backend.run("echo this", workspace, timeout=1)

            self.assertEqual("echo this", output)
            self.assertEqual(("generated/result.txt",), files)
            self.assertEqual(
                "done",
                (workspace / "generated" / "result.txt").read_text(encoding="utf-8"),
            )

    def test_returns_configured_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backend = run_evals.MockBackend(output="fixed response")

            output, files = backend.run("ignored", Path(temp_dir), timeout=1)

            self.assertEqual("fixed response", output)
            self.assertEqual((), files)

    def test_reports_modified_and_deleted_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            modified = workspace / "modified.txt"
            deleted = workspace / "deleted.txt"
            modified.write_text("before", encoding="utf-8")
            deleted.write_text("before", encoding="utf-8")
            before = run_evals.snapshot_workspace(workspace)

            modified.write_text("after", encoding="utf-8")
            deleted.unlink()

            self.assertEqual(
                ("deleted.txt", "modified.txt"),
                run_evals.changed_paths(before, workspace),
            )


class RubricTests(unittest.TestCase):
    def test_scores_each_rubric_item_as_yes_or_no(self):
        class JudgeBackend:
            def __init__(self):
                self.responses = iter(("YES - complete", "NO - incomplete"))

            def run(self, prompt, workspace, timeout):
                del prompt, workspace, timeout
                return next(self.responses), ()

        scenario = run_evals.ScenarioSummary(
            skill="plugin-a/skill-a",
            name="sample",
            expect_activation=True,
            manifest=Path("tests/plugin-a/skill-a/eval.yaml"),
            prompt="Do work",
            rubric=("First", "Second"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_evals.score_rubric(
                JudgeBackend(), scenario, "done", (), Path(temp_dir)
            )

        self.assertEqual((True, False), tuple(result.passed for result in results))


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)
        for skill, content in (
            ("target", "Target guidance with UNIQUE_SYMBOL"),
            ("sibling", "Sibling guidance"),
        ):
            path = self.root / "plugins" / "sample" / "skills" / skill
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text(content, encoding="utf-8")
        manifest = self.root / "tests" / "sample" / "target" / "eval.yaml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("scenarios: []\n", encoding="utf-8")
        self.scenario = run_evals.ScenarioSummary(
            skill="sample/target",
            name="experiment scenario",
            expect_activation=True,
            manifest=Path("tests/sample/target/eval.yaml"),
            prompt="Solve the task",
            assertions=(
                {"type": "output_contains", "value": "UNIQUE_SYMBOL"},
            ),
        )

    class RecordingBackend:
        def __init__(self):
            self.arm_prompts = []
            self.judge_positions = []

        def run(self, prompt, workspace, timeout):
            del workspace, timeout
            if prompt.startswith("Compare two candidate answers"):
                left = prompt.split("LEFT answer:\n", 1)[1].split("\n\nRIGHT answer:", 1)[0]
                right = prompt.split("RIGHT answer:\n", 1)[1]
                self.judge_positions.append((left, right))
                if left == "BASELINE":
                    return "RIGHT treatment is better", ()
                if right == "BASELINE":
                    return "LEFT treatment is better", ()
                return "TIE", ()

            self.arm_prompts.append(prompt)
            if "sample/sibling" in prompt:
                return "PLUGIN UNIQUE_SYMBOL", ()
            if "sample/target" in prompt:
                return "ISOLATED UNIQUE_SYMBOL", ()
            return "BASELINE", ()

    def test_runs_all_three_arms(self):
        backend = self.RecordingBackend()
        result = run_evals.run_experiment(
            self.root, self.scenario, backend, "mock", 1, "test"
        )

        self.assertEqual(3, len(backend.arm_prompts))
        self.assertEqual(
            {"baseline", "isolated", "plugin"},
            set(result["runs"][0]["arms"]),
        )
        self.assertNotIn("available_skill", backend.arm_prompts[0])
        self.assertEqual(1, backend.arm_prompts[1].count("<available_skill"))
        self.assertEqual(2, backend.arm_prompts[2].count("<available_skill"))

    def test_pairwise_judge_swaps_positions(self):
        backend = self.RecordingBackend()
        comparison = run_evals.judge_pairwise(
            backend,
            self.scenario,
            "isolated",
            "BASELINE",
            "ISOLATED UNIQUE_SYMBOL",
        )

        self.assertEqual(
            [
                ("BASELINE", "ISOLATED UNIQUE_SYMBOL"),
                ("ISOLATED UNIQUE_SYMBOL", "BASELINE"),
            ],
            backend.judge_positions,
        )
        self.assertEqual("win", comparison["result"])

    def test_writes_structured_json_artifact(self):
        result = run_evals.run_experiment(
            self.root, self.scenario, self.RecordingBackend(), "mock", 1, "fixture"
        )
        artifact = run_evals.write_experiment_artifact(
            self.root, result, Path("eng/eval-results")
        )

        saved = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(1, saved["schema_version"])
        self.assertEqual("capability_ab", saved["experiment"])
        self.assertEqual("sample/target", saved["scenario"]["skill"])
        self.assertEqual(["baseline", "isolated", "plugin"], saved["config"]["arms"])
        self.assertIn("activation_boundary", saved)

    def test_aggregates_win_lose_tie_counts(self):
        result = run_evals.run_experiment(
            self.root, self.scenario, self.RecordingBackend(), "mock", 3, "aggregate"
        )

        self.assertEqual(
            {"win": 3, "lose": 0, "tie": 0},
            result["aggregate"]["pairwise"]["isolated"],
        )
        self.assertEqual(
            {"win": 3, "lose": 0, "tie": 0},
            result["aggregate"]["pairwise"]["plugin"],
        )
        self.assertEqual(
            {"matched": 3, "not_matched": 0, "unavailable": 0},
            result["aggregate"]["activation_proxy"],
        )

    def test_mock_backend_records_unavailable_judges_as_ties(self):
        result = run_evals.run_experiment(
            self.root, self.scenario, run_evals.MockBackend(), "mock", 1, "mock"
        )

        self.assertEqual(1, result["aggregate"]["pairwise"]["isolated"]["tie"])
        judgments = result["runs"][0]["comparisons"]["isolated"]["judgments"]
        self.assertTrue(all(item["verdict"] == "unavailable" for item in judgments))


if __name__ == "__main__":
    unittest.main()
