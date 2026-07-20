#!/usr/bin/env python3
"""Tests for the standalone eval manifest validator."""

import tempfile
import unittest
from pathlib import Path

import validate_evals


VALID_EVAL = """\
scenarios:
  - name: "Explain CRUD policies"
    prompt: "Explain how CRUD authorization is configured."
    expect_activation: true
    assertions:
      - type: "output_contains"
        value: "GetPolicyName"
      - type: "output_matches"
        pattern: "(Create|Update)PolicyName"
    rubric:
      - "Explains that every CRUD operation needs an explicit policy name."
    timeout: 120
  - name: "Anti-trigger for a sibling skill"
    prompt: "Configure a background job queue."
    expect_activation: false
    assertions:
      - type: "output_contains"
        value: "GetPolicyName"
    rubric:
      - "Does not incorrectly explain CRUD policy names for a background job request."
    timeout: 120
"""


class ValidateEvalsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)

    def add_skill(self, plugin: str, skill: str) -> None:
        skill_dir = self.root / "plugins" / plugin / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")

    def add_eval(self, plugin: str, skill: str, content: str = VALID_EVAL) -> None:
        eval_dir = self.root / "tests" / plugin / skill
        eval_dir.mkdir(parents=True)
        (eval_dir / "eval.yaml").write_text(content, encoding="utf-8")

    def test_every_skill_with_eval_passes(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_skill("plugin-a", "skill-b")
        self.add_eval("plugin-a", "skill-a")
        # Distinct scenario names so the global-uniqueness rule is satisfied.
        self.add_eval(
            "plugin-a",
            "skill-b",
            VALID_EVAL.replace("Explain CRUD policies", "Explain CRUD policies (b)")
            .replace("Anti-trigger for a sibling skill", "Anti-trigger for a sibling skill (b)"),
        )

        errors, coverage = validate_evals.validate_repository(self.root)

        self.assertEqual([], errors)
        self.assertEqual(2, coverage.total_skills)
        self.assertEqual(2, coverage.evaluated_skills)
        self.assertEqual(4, coverage.scenario_count)
        self.assertEqual([], coverage.missing_skills)

    def test_missing_eval_is_an_error(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_skill("plugin-a", "skill-b")
        self.add_eval("plugin-a", "skill-a")

        errors, coverage = validate_evals.validate_repository(self.root)

        self.assertTrue(any("skill-b: skill has no eval file" in error for error in errors))
        self.assertEqual(["plugin-a/skill-b"], coverage.missing_skills)

    def test_rejects_non_boolean_expect_activation(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval("plugin-a", "skill-a", VALID_EVAL.replace("expect_activation: true", 'expect_activation: "true"'))

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("expect_activation must be a boolean" in error for error in errors))

    def test_rejects_unknown_assertion_type(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval("plugin-a", "skill-a", VALID_EVAL.replace("output_contains", "output_startswith"))

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("unsupported assertion type 'output_startswith'" in error for error in errors))

    def test_rejects_assertion_missing_type_specific_field(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval("plugin-a", "skill-a", VALID_EVAL.replace('        value: "GetPolicyName"\n', ""))

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("output_contains requires a non-empty 'value'" in error for error in errors))

    def test_rejects_invalid_output_regular_expression(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval(
            "plugin-a",
            "skill-a",
            VALID_EVAL.replace('pattern: "(Create|Update)PolicyName"', 'pattern: "["'),
        )

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("invalid regular expression" in error for error in errors))

    def test_rejects_eval_for_unknown_skill(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval("plugin-a", "unknown-skill")

        errors, coverage = validate_evals.validate_repository(self.root)

        self.assertTrue(any("does not map to a skill" in error for error in errors))
        self.assertEqual(0, coverage.evaluated_skills)

    def test_rejects_duplicate_scenario_names(self):
        self.add_skill("plugin-a", "skill-a")
        duplicate = VALID_EVAL + VALID_EVAL.split("scenarios:\n", maxsplit=1)[1]
        self.add_eval("plugin-a", "skill-a", duplicate)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("duplicate scenario name" in error for error in errors))

    def test_rejects_globally_duplicate_scenario_names_across_files(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_skill("plugin-a", "skill-b")
        self.add_eval("plugin-a", "skill-a")
        self.add_eval("plugin-a", "skill-b")

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("names must be globally unique" in error for error in errors)
        )

    def test_requires_a_positive_scenario(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval(
            "plugin-a", "skill-a", VALID_EVAL.replace("expect_activation: true", "expect_activation: false")
        )

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("has no positive scenario" in error for error in errors))

    def test_requires_an_anti_trigger_scenario(self):
        self.add_skill("plugin-a", "skill-a")
        self.add_eval(
            "plugin-a", "skill-a", VALID_EVAL.replace("expect_activation: false", "expect_activation: true")
        )

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("has no anti-trigger scenario" in error for error in errors))

    def test_rejects_setup_path_escape(self):
        self.add_skill("plugin-a", "skill-a")
        escaping_setup = (
            "    setup:\n"
            "      files:\n"
            "        - path: \"../outside.txt\"\n"
            "          content: \"hi\"\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + escaping_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("must be relative and stay within the workspace" in error for error in errors)
        )

    def test_accepts_executable_setup_commands(self):
        self.add_skill("plugin-a", "skill-a")
        command_setup = (
            "    setup:\n"
            "      commands:\n"
            "        - \"dotnet build\"\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + command_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertEqual([], errors)

    def test_rejects_non_string_setup_commands(self):
        self.add_skill("plugin-a", "skill-a")
        command_setup = (
            "    setup:\n"
            "      commands:\n"
            "        - 42\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + command_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("setup.commands must be a list of non-empty strings" in error for error in errors)
        )

    def test_rejects_empty_setup_source(self):
        self.add_skill("plugin-a", "skill-a")
        source_setup = (
            "    setup:\n"
            "      files:\n"
            "        - path: \"dest.txt\"\n"
            "          source: \"\"\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + source_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("'source' must be a non-empty string" in error for error in errors)
        )

    def test_accepts_setup_copy_test_files(self):
        self.add_skill("plugin-a", "skill-a")
        copy_setup = (
            "    setup:\n"
            "      copy_test_files: true\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + copy_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertEqual([], errors)

    def test_rejects_non_boolean_copy_test_files(self):
        self.add_skill("plugin-a", "skill-a")
        copy_setup = (
            "    setup:\n"
            "      copy_test_files: \"yes\"\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + copy_setup,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("setup.copy_test_files must be a boolean" in error for error in errors)
        )

    def test_accepts_new_assertion_types(self):
        self.add_skill("plugin-a", "skill-a")
        assertions = (
            "    assertions:\n"
            "      - type: \"output_not_contains\"\n"
            "        value: \"forbidden\"\n"
            "      - type: \"output_not_matches\"\n"
            "        pattern: \"never-\\\\d+\"\n"
            "      - type: \"file_contains\"\n"
            "        path: \"*.cs\"\n"
            "        value: \"stackalloc\"\n"
            "      - type: \"file_not_contains\"\n"
            "        path: \"*.cs\"\n"
            "        value: \"unsafe\"\n"
            "      - type: \"exit_success\"\n"
            "        command: \"true\"\n"
            "      - type: \"run_command_and_assert\"\n"
            "        command: \"dotnet test\"\n"
            "        exit_code: 0\n"
            "        stdout_contains: \"Passed\"\n"
        )
        content = VALID_EVAL.replace(
            "    assertions:\n"
            "      - type: \"output_contains\"\n"
            "        value: \"GetPolicyName\"\n"
            "      - type: \"output_matches\"\n"
            "        pattern: \"(Create|Update)PolicyName\"\n",
            assertions,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertEqual([], errors)

    def test_rejects_file_contains_missing_value(self):
        self.add_skill("plugin-a", "skill-a")
        content = VALID_EVAL.replace(
            "      - type: \"output_contains\"\n"
            "        value: \"GetPolicyName\"\n",
            "      - type: \"file_contains\"\n"
            "        path: \"*.cs\"\n",
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("file_contains requires a non-empty 'value'" in error for error in errors)
        )

    def test_rejects_run_command_without_command(self):
        self.add_skill("plugin-a", "skill-a")
        content = VALID_EVAL.replace(
            "      - type: \"output_contains\"\n"
            "        value: \"GetPolicyName\"\n",
            "      - type: \"run_command_and_assert\"\n"
            "        exit_code: 0\n",
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("run_command_and_assert requires a non-empty 'command'" in error for error in errors)
        )

    def test_rejects_run_command_non_integer_exit_code(self):
        self.add_skill("plugin-a", "skill-a")
        content = VALID_EVAL.replace(
            "      - type: \"output_contains\"\n"
            "        value: \"GetPolicyName\"\n",
            "      - type: \"run_command_and_assert\"\n"
            "        command: \"true\"\n"
            "        exit_code: \"zero\"\n",
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("exit_code must be an integer" in error for error in errors)
        )

    def test_rejects_unknown_run_command_field(self):
        self.add_skill("plugin-a", "skill-a")
        content = VALID_EVAL.replace(
            "      - type: \"output_contains\"\n"
            "        value: \"GetPolicyName\"\n",
            "      - type: \"run_command_and_assert\"\n"
            "        command: \"true\"\n"
            "        bogus: \"x\"\n",
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("does not accept field(s): bogus" in error for error in errors)
        )

    def test_accepts_behavioral_constraints(self):
        self.add_skill("plugin-a", "skill-a")
        constraints = (
            "    expect_tools: [\"bash\"]\n"
            "    reject_tools: [\"create_file\"]\n"
            "    max_turns: 15\n"
            "    max_tokens: 5000\n"
        )
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n" + constraints,
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertEqual([], errors)

    def test_rejects_non_positive_max_turns(self):
        self.add_skill("plugin-a", "skill-a")
        content = VALID_EVAL.replace(
            "    expect_activation: true\n",
            "    expect_activation: true\n    max_turns: 0\n",
            1,
        )
        self.add_eval("plugin-a", "skill-a", content)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(
            any("max_turns must be a positive integer" in error for error in errors)
        )

    def test_rejects_duplicate_yaml_key(self):
        self.add_skill("plugin-a", "skill-a")
        dup_key = VALID_EVAL.replace(
            '    prompt: "Explain how CRUD authorization is configured."\n',
            '    prompt: "Explain how CRUD authorization is configured."\n'
            '    prompt: "A second prompt with the same key."\n',
            1,
        )
        self.add_eval("plugin-a", "skill-a", dup_key)

        errors, _ = validate_evals.validate_repository(self.root)

        self.assertTrue(any("duplicate key" in error for error in errors))


class EvalRunnerScaffoldTests(unittest.TestCase):
    def test_collects_scenarios_without_executing_an_agent(self):
        import run_evals

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "tests" / "plugin-a" / "skill-a"
            eval_dir.mkdir(parents=True)
            (eval_dir / "eval.yaml").write_text(VALID_EVAL, encoding="utf-8")

            scenarios = run_evals.collect_scenarios(root)

        self.assertEqual(2, len(scenarios))
        self.assertEqual("plugin-a/skill-a", scenarios[0].skill)
        self.assertEqual("Explain CRUD policies", scenarios[0].name)
        self.assertTrue(scenarios[0].expect_activation)


if __name__ == "__main__":
    unittest.main()
