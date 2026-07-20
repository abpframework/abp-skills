#!/usr/bin/env python3
"""Validate eval.yaml files and report skill evaluation coverage."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Set, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without the dependency
    print("validate_evals.py: PyYAML is required (python3 -m pip install PyYAML)", file=sys.stderr)
    sys.exit(2)


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """SafeLoader that raises instead of silently keeping the last value when a
    mapping declares the same key twice."""


def _no_duplicate_keys(loader, node, deep=False):
    mapping: Dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


ROOT = Path(__file__).resolve().parent.parent

# Assertion type -> the required field(s) that must be non-empty strings.
ASSERTION_REQUIRED = {
    "output_contains": ("value",),
    "output_not_contains": ("value",),
    "output_matches": ("pattern",),
    "output_not_matches": ("pattern",),
    "file_exists": ("path",),
    "file_not_exists": ("path",),
    "file_contains": ("path", "value"),
    "file_not_contains": ("path", "value"),
    "exit_success": ("command",),
    "run_command_and_assert": ("command",),
}
# Fields each assertion type is allowed to carry (beyond "type").
ASSERTION_ALLOWED = {
    "output_contains": {"value"},
    "output_not_contains": {"value"},
    "output_matches": {"pattern"},
    "output_not_matches": {"pattern"},
    "file_exists": {"path"},
    "file_not_exists": {"path"},
    "file_contains": {"path", "value"},
    "file_not_contains": {"path", "value"},
    "exit_success": {"command"},
    "run_command_and_assert": {
        "command",
        "exit_code",
        "stdout_contains",
        "stdout_matches",
        "stderr_contains",
        "stderr_matches",
    },
}
# Assertion types whose required field must compile as a regular expression.
ASSERTION_REGEX_FIELDS = {
    "output_matches": "pattern",
    "output_not_matches": "pattern",
}
# Bare language keywords are too weak for an output_contains assertion: any file
# with a `using` directive or a `new` expression satisfies them, so they don't
# distinguish a correct answer. Require a distinctive symbol or an output_matches
# regex instead. (Distinctive identifiers like IBlobContainer are fine.)
GENERIC_KEYWORD_DENYLIST = {
    "using", "new", "var", "public", "private", "protected", "internal",
    "async", "await", "class", "return", "void", "int", "string", "bool",
    "if", "else", "for", "foreach", "while", "try", "catch", "this", "base",
    "null", "true", "false", "static", "namespace", "get", "set", "task",
}
ROOT_FIELDS = {"scenarios"}
SCENARIO_FIELDS = {
    "name",
    "prompt",
    "expect_activation",
    "setup",
    "assertions",
    "rubric",
    "timeout",
    "expect_tools",
    "reject_tools",
    "max_turns",
    "max_tokens",
}
REQUIRED_SCENARIO_FIELDS = SCENARIO_FIELDS - {
    "setup",
    "expect_tools",
    "reject_tools",
    "max_turns",
    "max_tokens",
}
SETUP_FIELDS = {"copy_test_files", "files", "commands"}
SETUP_FILE_FIELDS = {"path", "source", "content"}
ASSERTION_FIELDS_ALL = {
    "type",
    "value",
    "pattern",
    "path",
    "command",
    "exit_code",
    "stdout_contains",
    "stdout_matches",
    "stderr_contains",
    "stderr_matches",
}


@dataclass(frozen=True)
class Coverage:
    total_skills: int
    evaluated_skills: int
    scenario_count: int
    missing_skills: List[str]

    @property
    def percentage(self) -> float:
        if self.total_skills == 0:
            return 0.0
        return self.evaluated_skills / self.total_skills * 100


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _escapes_workspace(relative_path: str) -> bool:
    """Return True when a setup path is absolute or normalizes to somewhere
    outside its base directory (workspace for `path`, manifest dir for
    `source`). Mirrors the runner's resolve-time guards so the validator
    rejects these at validation time."""
    path = PurePosixPath(relative_path)
    if path.is_absolute() or PureWindowsPath(relative_path).is_absolute():
        return True
    depth = 0
    for part in path.parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part not in ("", "."):
            depth += 1
    return False


def _unknown_fields(value: Dict[str, Any], allowed: Set[str], location: str, errors: List[str]) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{location}: unknown field(s): {', '.join(unknown)}")


def _validate_setup(setup: Any, location: str, errors: List[str]) -> None:
    if not isinstance(setup, dict):
        errors.append(f"{location}: setup must be a mapping")
        return

    _unknown_fields(setup, SETUP_FIELDS, location, errors)
    if "copy_test_files" in setup and not isinstance(setup["copy_test_files"], bool):
        errors.append(f"{location}: setup.copy_test_files must be a boolean")

    commands = setup.get("commands")
    if commands is not None and (
        not isinstance(commands, list) or not all(_is_non_empty_string(command) for command in commands)
    ):
        errors.append(f"{location}: setup.commands must be a list of non-empty strings")

    files = setup.get("files")
    if files is None:
        return
    if not isinstance(files, list):
        errors.append(f"{location}: setup.files must be a list")
        return
    for index, setup_file in enumerate(files):
        file_location = f"{location}: setup.files[{index}]"
        if not isinstance(setup_file, dict):
            errors.append(f"{file_location} must be a mapping")
            continue
        _unknown_fields(setup_file, SETUP_FILE_FIELDS, file_location, errors)
        path_value = setup_file.get("path")
        if not _is_non_empty_string(path_value):
            errors.append(f"{file_location}: 'path' must be a non-empty string")
        elif _escapes_workspace(path_value):
            errors.append(
                f"{file_location}: 'path' must be relative and stay within the "
                f"workspace (got {path_value!r})"
            )
        source_value = setup_file.get("source")
        if "source" in setup_file and not _is_non_empty_string(source_value):
            # `content` may be an empty string (empty file); a `source` names a
            # real fixture, so it must be non-empty.
            errors.append(f"{file_location}: 'source' must be a non-empty string")
        elif _is_non_empty_string(source_value) and _escapes_workspace(source_value):
            errors.append(
                f"{file_location}: 'source' must be relative and stay within the "
                f"manifest directory (got {source_value!r})"
            )
        payloads = [field for field in ("source", "content") if field in setup_file]
        if len(payloads) != 1 or not isinstance(setup_file.get(payloads[0]) if payloads else None, str):
            errors.append(f"{file_location}: provide exactly one string 'source' or 'content'")


def _validate_assertions(assertions: Any, location: str, errors: List[str]) -> None:
    if not isinstance(assertions, list) or not assertions:
        errors.append(f"{location}: assertions must be a non-empty list")
        return

    for index, assertion in enumerate(assertions):
        assertion_location = f"{location}: assertions[{index}]"
        if not isinstance(assertion, dict):
            errors.append(f"{assertion_location} must be a mapping")
            continue
        _unknown_fields(assertion, ASSERTION_FIELDS_ALL, assertion_location, errors)
        assertion_type = assertion.get("type")
        if assertion_type not in ASSERTION_REQUIRED:
            errors.append(f"{assertion_location}: unsupported assertion type '{assertion_type}'")
            continue

        for required_field in ASSERTION_REQUIRED[assertion_type]:
            if not _is_non_empty_string(assertion.get(required_field)):
                errors.append(
                    f"{assertion_location}: {assertion_type} requires a non-empty '{required_field}'"
                )

        if assertion_type in ("output_contains", "output_not_contains"):
            value = assertion.get("value")
            if _is_non_empty_string(value) and value.strip().lower() in GENERIC_KEYWORD_DENYLIST:
                errors.append(
                    f"{assertion_location}: {assertion_type} value '{value.strip()}' is a bare "
                    f"language keyword — too weak to distinguish a correct answer; use a "
                    f"distinctive symbol or an output_matches regex"
                )

        regex_field = ASSERTION_REGEX_FIELDS.get(assertion_type)
        if regex_field and _is_non_empty_string(assertion.get(regex_field)):
            try:
                re.compile(assertion[regex_field])
            except re.error as exc:
                errors.append(f"{assertion_location}: invalid regular expression ({exc})")

        if assertion_type == "run_command_and_assert":
            _validate_run_command(assertion, assertion_location, errors)

        allowed = {"type"} | ASSERTION_ALLOWED[assertion_type]
        extras = sorted(set(assertion) - allowed)
        if extras:
            errors.append(
                f"{assertion_location}: {assertion_type} does not accept field(s): {', '.join(extras)}"
            )


def _validate_run_command(assertion: Dict[str, Any], location: str, errors: List[str]) -> None:
    exit_code = assertion.get("exit_code")
    if "exit_code" in assertion and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
        errors.append(f"{location}: run_command_and_assert exit_code must be an integer")

    for field in ("stdout_contains", "stderr_contains", "stdout_matches", "stderr_matches"):
        if field in assertion and not _is_non_empty_string(assertion.get(field)):
            errors.append(
                f"{location}: run_command_and_assert {field} must be a non-empty string"
            )
    for field in ("stdout_matches", "stderr_matches"):
        if _is_non_empty_string(assertion.get(field)):
            try:
                re.compile(assertion[field])
            except re.error as exc:
                errors.append(f"{location}: invalid regular expression in {field} ({exc})")


@dataclass
class EvalFileResult:
    scenario_count: int = 0
    activations: List[bool] = None  # type: ignore[assignment]
    scenario_names: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.activations is None:
            self.activations = []
        if self.scenario_names is None:
            self.scenario_names = []


def _validate_eval_file(path: Path, errors: List[str]) -> EvalFileResult:
    result = EvalFileResult()
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDuplicateKeysLoader)
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
        return result

    if not isinstance(data, dict):
        errors.append(f"{path}: root must be a mapping")
        return result
    _unknown_fields(data, ROOT_FIELDS, str(path), errors)
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        errors.append(f"{path}: scenarios must be a non-empty list")
        return result

    result.scenario_count = len(scenarios)
    names: Set[str] = set()
    for index, scenario in enumerate(scenarios):
        location = f"{path}: scenarios[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{location} must be a mapping")
            continue
        _unknown_fields(scenario, SCENARIO_FIELDS, location, errors)
        missing = sorted(REQUIRED_SCENARIO_FIELDS - set(scenario))
        if missing:
            errors.append(f"{location}: missing required field(s): {', '.join(missing)}")

        name = scenario.get("name")
        if not _is_non_empty_string(name):
            errors.append(f"{location}: name must be a non-empty string")
        elif name in names:
            errors.append(f"{location}: duplicate scenario name '{name}'")
        else:
            names.add(name)
            result.scenario_names.append(name)

        if not _is_non_empty_string(scenario.get("prompt")):
            errors.append(f"{location}: prompt must be a non-empty string")
        activation = scenario.get("expect_activation")
        if not isinstance(activation, bool):
            errors.append(f"{location}: expect_activation must be a boolean")
        else:
            result.activations.append(activation)

        timeout = scenario.get("timeout")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            errors.append(f"{location}: timeout must be a positive integer")

        rubric = scenario.get("rubric")
        if not isinstance(rubric, list) or not rubric or not all(
            _is_non_empty_string(item) for item in rubric
        ):
            errors.append(f"{location}: rubric must be a non-empty list of non-empty strings")

        for tool_field in ("expect_tools", "reject_tools"):
            if tool_field in scenario:
                value = scenario[tool_field]
                if not isinstance(value, list) or not all(
                    _is_non_empty_string(item) for item in value
                ):
                    errors.append(
                        f"{location}: {tool_field} must be a list of non-empty strings"
                    )

        for limit_field in ("max_turns", "max_tokens"):
            if limit_field in scenario:
                value = scenario[limit_field]
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    errors.append(f"{location}: {limit_field} must be a positive integer")

        if "setup" in scenario:
            _validate_setup(scenario["setup"], location, errors)
        _validate_assertions(scenario.get("assertions"), location, errors)

    return result


def validate_repository(root: Path) -> Tuple[List[str], Coverage]:
    root = root.resolve()
    errors: List[str] = []
    skills = {
        f"{path.parents[2].name}/{path.parent.name}"
        for path in root.glob("plugins/*/skills/*/SKILL.md")
    }
    evaluated: Set[str] = set()
    scenario_count = 0
    global_names: Dict[str, str] = {}

    for eval_path in sorted(root.glob("tests/**/eval.yaml")):
        relative = eval_path.relative_to(root)
        if len(relative.parts) != 4:
            errors.append(
                f"{relative}: eval path must be tests/<plugin>/<skill>/eval.yaml"
            )
            scenario_count += _validate_eval_file(eval_path, errors).scenario_count
            continue

        skill_key = f"{relative.parts[1]}/{relative.parts[2]}"
        if skill_key not in skills:
            errors.append(
                f"{relative}: does not map to a skill at "
                f"plugins/{relative.parts[1]}/skills/{relative.parts[2]}"
            )
        else:
            evaluated.add(skill_key)

        file_result = _validate_eval_file(eval_path, errors)
        scenario_count += file_result.scenario_count

        if file_result.activations:
            if not any(file_result.activations):
                errors.append(
                    f"{relative}: has no positive scenario "
                    f"(at least one 'expect_activation: true' required)"
                )
            if all(file_result.activations):
                errors.append(
                    f"{relative}: has no anti-trigger scenario "
                    f"(at least one 'expect_activation: false' required)"
                )

        for scenario_name in file_result.scenario_names:
            if scenario_name in global_names:
                errors.append(
                    f"{relative}: scenario name '{scenario_name}' also used in "
                    f"{global_names[scenario_name]} (names must be globally unique)"
                )
            else:
                global_names[scenario_name] = str(relative)

    missing = sorted(skills - evaluated)
    for skill_key in missing:
        errors.append(
            f"{skill_key}: skill has no eval file "
            f"(expected tests/{skill_key}/eval.yaml)"
        )
    return errors, Coverage(len(skills), len(evaluated), scenario_count, missing)


def _print_coverage(coverage: Coverage) -> None:
    print(
        "Eval coverage: "
        f"{coverage.evaluated_skills}/{coverage.total_skills} skills "
        f"({coverage.percentage:.1f}%), {coverage.scenario_count} scenarios"
    )
    if coverage.missing_skills:
        print("Skills without eval:")
        for skill in coverage.missing_skills:
            print(f"  - {skill}")
    else:
        print("Skills without eval: none")


def main() -> int:
    errors, coverage = validate_repository(ROOT)
    if errors:
        print(f"validate_evals.py: {len(errors)} problem(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    else:
        print("validate_evals.py: OK")
    _print_coverage(coverage)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
