#!/usr/bin/env python3
"""Run skill eval scenarios with deterministic assertions and pluggable agents."""

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterator, List, Mapping, Optional, Protocol, Sequence, Tuple

import yaml

import validate_evals


ROOT = Path(__file__).resolve().parent.parent

# Commands run in the isolated workspace (setup.commands and
# run_command_and_assert) are given this many seconds before they are killed.
SETUP_COMMAND_TIMEOUT = 120
COMMAND_ASSERTION_TIMEOUT = 120


@dataclass(frozen=True)
class ScenarioSummary:
    skill: str
    name: str
    expect_activation: bool
    manifest: Path
    prompt: str = ""
    setup: Optional[Mapping[str, Any]] = None
    assertions: Tuple[Mapping[str, Any], ...] = ()
    rubric: Tuple[str, ...] = ()
    timeout: int = 120
    expect_tools: Tuple[str, ...] = ()
    reject_tools: Tuple[str, ...] = ()
    max_turns: Optional[int] = None
    max_tokens: Optional[int] = None

    @property
    def identifier(self) -> str:
        return f"{self.skill}::{self.name}"

    @property
    def behavioral_constraints(self) -> Tuple[str, ...]:
        constraints: List[str] = []
        if self.expect_tools:
            constraints.append(f"expect_tools={list(self.expect_tools)}")
        if self.reject_tools:
            constraints.append(f"reject_tools={list(self.reject_tools)}")
        if self.max_turns is not None:
            constraints.append(f"max_turns={self.max_turns}")
        if self.max_tokens is not None:
            constraints.append(f"max_tokens={self.max_tokens}")
        return tuple(constraints)


@dataclass(frozen=True)
class AssertionResult:
    assertion_type: str
    passed: bool
    description: str


@dataclass(frozen=True)
class RubricResult:
    criterion: str
    passed: Optional[bool]
    response: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario: ScenarioSummary
    output: str
    changed_files: Tuple[str, ...]
    assertions: Tuple[AssertionResult, ...]
    rubric: Optional[Tuple[RubricResult, ...]]

    @property
    def passed(self) -> bool:
        deterministic_passed = all(result.passed for result in self.assertions)
        rubric_passed = self.rubric is None or all(
            result.passed is True for result in self.rubric
        )
        return deterministic_passed and rubric_passed


class AgentBackend(Protocol):
    """Minimal interface implemented by agent execution backends."""

    def run(
        self, prompt: str, workspace: Path, timeout: int = 120
    ) -> Tuple[str, Tuple[str, ...]]:
        """Return the agent output and workspace paths changed during the run."""


class MockBackend:
    """Deterministic backend that echoes its prompt and can create fixture files."""

    def __init__(
        self,
        output: Optional[str] = None,
        files: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.output = output
        self.files = dict(files or {})

    def run(
        self, prompt: str, workspace: Path, timeout: int = 120
    ) -> Tuple[str, Tuple[str, ...]]:
        del timeout
        before = snapshot_workspace(workspace)
        for relative_path, content in self.files.items():
            destination = resolve_workspace_path(workspace, relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        output = self.output if self.output is not None else prompt
        return output, changed_paths(before, workspace)


class CodexBackend:
    """Run Codex non-interactively inside an isolated workspace."""

    def __init__(self, executable: str = "codex", model: Optional[str] = None) -> None:
        self.executable = executable
        self.model = model

    def run(
        self, prompt: str, workspace: Path, timeout: int = 120
    ) -> Tuple[str, Tuple[str, ...]]:
        before = snapshot_workspace(workspace)
        command = [
            self.executable,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--color",
            "never",
            "--cd",
            str(workspace),
        ]
        if self.model:
            command.extend(("--model", self.model))
        command.append("-")
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Codex executable not found: {self.executable}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Codex timed out after {timeout} seconds") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            detail = stderr if stderr else "no stderr"
            raise RuntimeError(f"Codex exited with code {completed.returncode}: {detail}")
        return completed.stdout, changed_paths(before, workspace)


def collect_scenarios(root: Path) -> List[ScenarioSummary]:
    scenarios: List[ScenarioSummary] = []
    for eval_path in sorted(root.glob("tests/*/*/eval.yaml")):
        relative = eval_path.relative_to(root)
        skill = f"{relative.parts[1]}/{relative.parts[2]}"
        data = yaml.safe_load(eval_path.read_text(encoding="utf-8"))
        for scenario in data["scenarios"]:
            scenarios.append(
                ScenarioSummary(
                    skill=skill,
                    name=scenario["name"],
                    expect_activation=scenario["expect_activation"],
                    manifest=relative,
                    prompt=scenario["prompt"],
                    setup=scenario.get("setup"),
                    assertions=tuple(scenario["assertions"]),
                    rubric=tuple(scenario["rubric"]),
                    timeout=scenario["timeout"],
                    expect_tools=tuple(scenario.get("expect_tools", []) or []),
                    reject_tools=tuple(scenario.get("reject_tools", []) or []),
                    max_turns=scenario.get("max_turns"),
                    max_tokens=scenario.get("max_tokens"),
                )
            )
    return scenarios


def resolve_workspace_path(workspace: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"Workspace path must be relative: {relative_path}")
    workspace = workspace.resolve()
    resolved = (workspace / path).resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError(f"Workspace path escapes the workspace: {relative_path}")
    return resolved


def _is_glob(pattern: str) -> bool:
    # `[...]` character classes are not supported; only `*`, `**`, and `?` are
    # treated as globs so `_is_glob` stays consistent with `_glob_to_regex`
    # (which escapes `[`). A path containing only `[` is matched literally.
    return any(char in pattern for char in "*?")


def glob_workspace(workspace: Path, pattern: str) -> List[Path]:
    """Return workspace files matching a relative glob (``*``/``**``) or an
    exact relative path. Raises ValueError for absolute or escaping patterns so
    the caller can report the same guard the runner applies elsewhere."""
    path = Path(pattern)
    if path.is_absolute():
        raise ValueError(f"Workspace path must be relative: {pattern}")
    workspace = workspace.resolve()
    if ".." in path.parts:
        raise ValueError(f"Workspace path escapes the workspace: {pattern}")
    if not _is_glob(pattern):
        resolved = (workspace / path).resolve()
        if resolved != workspace and workspace not in resolved.parents:
            raise ValueError(f"Workspace path escapes the workspace: {pattern}")
        return [resolved] if resolved.is_file() else []

    regex = re.compile(_glob_to_regex(PurePosixPath(pattern).as_posix()))
    matches: List[Path] = []
    for candidate in workspace.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(workspace).as_posix()
        if regex.match(relative):
            matches.append(candidate)
    return sorted(matches)


def _segment_to_regex(segment: str) -> str:
    """Translate a single path segment (no ``/``). Within a segment ``*`` and
    ``?`` never cross a separator; a bare ``**`` here is treated as ``*``."""
    parts: List[str] = []
    for char in segment:
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def _glob_to_regex(pattern_str: str) -> str:
    """Compile a glob to a full-match regex. A ``**`` segment crosses path
    separators only when it is a complete segment (``a/**/b``, ``**/x``,
    ``x/**``, or the whole pattern); everywhere else ``*`` and ``?`` stay within
    a single segment. Adjacent ``**`` segments collapse into one."""
    # Collapse runs of `**` so `**/**/x` behaves like `**/x`.
    segments: List[str] = []
    for segment in pattern_str.split("/"):
        if segment == "**" and segments and segments[-1] == "**":
            continue
        segments.append(segment)

    out = "(?s)"
    for index, segment in enumerate(segments):
        first = index == 0
        last = index == len(segments) - 1
        if segment == "**":
            if first and last:
                out += ".*"  # whole pattern is `**`
            elif first:
                out += ".*" if last else "(?:[^/]+/)*"  # leading `**/`
            elif last:
                out += "/.+"  # trailing `/**` — at least one child
            else:
                out += "(?:/[^/]+)*/"  # middle `/**/`
        else:
            if not first and segments[index - 1] != "**":
                out += "/"  # normal segment boundary; `**` supplies its own
            out += _segment_to_regex(segment)
    out += r"\Z"
    return out


def _resolve_source_path(manifest_dir: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"Setup source must be relative: {relative_path}")
    manifest_dir = manifest_dir.resolve()
    resolved = (manifest_dir / path).resolve()
    if resolved != manifest_dir and manifest_dir not in resolved.parents:
        raise ValueError(f"Setup source escapes the manifest directory: {relative_path}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Setup source does not exist: {relative_path}")
    return resolved


def _copy_test_files(workspace: Path, manifest_dir: Path) -> None:
    """Copy every fixture file alongside the manifest (except eval.yaml) into
    the isolated workspace, preserving its relative path."""
    manifest_dir = manifest_dir.resolve()
    for source in sorted(manifest_dir.rglob("*")):
        if not source.is_file() or source.name == "eval.yaml":
            continue
        relative = source.relative_to(manifest_dir).as_posix()
        destination = resolve_workspace_path(workspace, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _run_setup_commands(workspace: Path, commands: Sequence[str]) -> None:
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(workspace),
                text=True,
                capture_output=True,
                timeout=SETUP_COMMAND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Setup command timed out after {SETUP_COMMAND_TIMEOUT}s: {command}"
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
            raise RuntimeError(
                f"Setup command failed (exit {completed.returncode}): {command}: {detail}"
            )


def apply_setup(
    workspace: Path, setup: Optional[Mapping[str, Any]], manifest_dir: Path
) -> None:
    if not setup:
        return

    if setup.get("copy_test_files"):
        _copy_test_files(workspace, manifest_dir)

    for setup_file in setup.get("files", []):
        destination = resolve_workspace_path(workspace, setup_file["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if "content" in setup_file:
            destination.write_text(setup_file["content"], encoding="utf-8")
        else:
            source = _resolve_source_path(manifest_dir, setup_file["source"])
            shutil.copyfile(source, destination)

    commands = setup.get("commands")
    if commands:
        _run_setup_commands(workspace, commands)


@contextmanager
def scenario_workspace(
    setup: Optional[Mapping[str, Any]], manifest_dir: Path
) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="abp-skill-eval-") as temp_dir:
        workspace = Path(temp_dir)
        apply_setup(workspace, setup, manifest_dir)
        yield workspace


def snapshot_workspace(workspace: Path) -> Dict[str, str]:
    snapshot: Dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            relative = path.relative_to(workspace).as_posix()
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def changed_paths(before: Mapping[str, str], workspace: Path) -> Tuple[str, ...]:
    after = snapshot_workspace(workspace)
    return tuple(
        sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )
    )


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _run_assertion_command(
    command: str, workspace: Path
) -> Tuple[Optional[int], str, str, Optional[str]]:
    """Run a command in the workspace. Returns (exit_code, stdout, stderr,
    error). When error is set the command could not be run to completion."""
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace),
            text=True,
            capture_output=True,
            timeout=COMMAND_ASSERTION_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", "", f"Command timed out after {COMMAND_ASSERTION_TIMEOUT}s"
    return completed.returncode, completed.stdout, completed.stderr, None


def _evaluate_run_command(
    assertion: Mapping[str, Any], workspace: Path
) -> Tuple[bool, str]:
    command = assertion["command"]
    exit_code, stdout, stderr, error = _run_assertion_command(command, workspace)
    if error is not None:
        return False, f"{command}: {error}"

    expected_exit = assertion.get("exit_code", 0)
    if exit_code != expected_exit:
        return False, (
            f"Command {command!r} exited with {exit_code}, expected {expected_exit}"
        )

    checks = (
        ("stdout_contains", stdout, "stdout", False),
        ("stderr_contains", stderr, "stderr", False),
        ("stdout_matches", stdout, "stdout", True),
        ("stderr_matches", stderr, "stderr", True),
    )
    for field, stream, label, is_regex in checks:
        expected = assertion.get(field)
        if expected is None:
            continue
        if is_regex:
            matched = re.search(expected, stream, flags=re.IGNORECASE | re.MULTILINE)
            if matched is None:
                return False, f"Command {label} does not match {expected!r}"
        elif expected.casefold() not in stream.casefold():
            return False, f"Command {label} does not contain {expected!r}"
    return True, f"Command {command!r} satisfied its assertions"


def _evaluate_single(
    assertion: Mapping[str, Any], output_text: str, workspace: Path
) -> Tuple[bool, str]:
    assertion_type = assertion["type"]

    if assertion_type in {"output_contains", "output_not_contains"}:
        value = assertion["value"]
        contains = value.casefold() in output_text.casefold()
        if assertion_type == "output_contains":
            return contains, (
                f"Output contains {value!r}" if contains
                else f"Output does not contain {value!r}"
            )
        return not contains, (
            f"Output does not contain {value!r}" if not contains
            else f"Output contains {value!r} but must not"
        )

    if assertion_type in {"output_matches", "output_not_matches"}:
        pattern = assertion["pattern"]
        matched = (
            re.search(pattern, output_text, flags=re.IGNORECASE | re.MULTILINE)
            is not None
        )
        if assertion_type == "output_matches":
            return matched, (
                f"Output matches {pattern!r}" if matched
                else f"Output does not match {pattern!r}"
            )
        return not matched, (
            f"Output does not match {pattern!r}" if not matched
            else f"Output matches {pattern!r} but must not"
        )

    if assertion_type in {"file_exists", "file_not_exists"}:
        pattern = assertion["path"]
        try:
            matches = glob_workspace(workspace, pattern)
        except ValueError as exc:
            return False, str(exc)
        exists = bool(matches)
        if assertion_type == "file_exists":
            return exists, (
                f"File matches {pattern!r}" if exists
                else f"No file matches {pattern!r}"
            )
        return not exists, (
            f"No file matches {pattern!r}" if not exists
            else f"File matches {pattern!r} but must not: "
            + ", ".join(sorted(p.name for p in matches))
        )

    if assertion_type in {"file_contains", "file_not_contains"}:
        pattern = assertion["path"]
        value = assertion["value"]
        try:
            matches = glob_workspace(workspace, pattern)
        except ValueError as exc:
            return False, str(exc)
        if not matches:
            return False, f"No file matches {pattern!r}"
        contents = {path: _read_text(path) for path in matches}
        unreadable = [path for path, text in contents.items() if text is None]
        if unreadable:
            # Content cannot be verified, so neither variant may pass on trust.
            return False, (
                f"File matching {pattern!r} could not be read: "
                + ", ".join(sorted(p.name for p in unreadable))
            )
        any_contains = any(value in text for text in contents.values())
        if assertion_type == "file_contains":
            return any_contains, (
                f"A file matching {pattern!r} contains {value!r}" if any_contains
                else f"No file matching {pattern!r} contains {value!r}"
            )
        return not any_contains, (
            f"No file matching {pattern!r} contains {value!r}" if not any_contains
            else f"A file matching {pattern!r} contains {value!r} but must not"
        )

    if assertion_type == "exit_success":
        command = assertion["command"]
        exit_code, _, stderr, error = _run_assertion_command(command, workspace)
        if error is not None:
            return False, f"{command}: {error}"
        return exit_code == 0, (
            f"Command {command!r} exited 0" if exit_code == 0
            else f"Command {command!r} exited with {exit_code}: {stderr.strip()}"
        )

    if assertion_type == "run_command_and_assert":
        return _evaluate_run_command(assertion, workspace)

    return False, f"Unsupported assertion type: {assertion_type}"


def evaluate_assertions(
    assertions: Sequence[Mapping[str, Any]], output_text: str, workspace: Path
) -> Tuple[AssertionResult, ...]:
    results: List[AssertionResult] = []
    for assertion in assertions:
        passed, description = _evaluate_single(assertion, output_text, workspace)
        results.append(AssertionResult(assertion["type"], passed, description))
    return tuple(results)


def build_agent_prompt(root: Path, scenario: ScenarioSummary) -> str:
    skill_path = root / "plugins" / scenario.skill.split("/", maxsplit=1)[0] / "skills"
    skill_path = skill_path / scenario.skill.split("/", maxsplit=1)[1] / "SKILL.md"
    skill_content = skill_path.read_text(encoding="utf-8")
    return (
        "Use the following target skill as task context. It is provided directly; "
        "this is not a plugin activation test.\n\n"
        "<target_skill>\n"
        f"{skill_content}\n"
        "</target_skill>\n\n"
        "<user_request>\n"
        f"{scenario.prompt}\n"
        "</user_request>"
    )


def score_rubric(
    backend: AgentBackend,
    scenario: ScenarioSummary,
    agent_output: str,
    changed_files: Sequence[str],
    workspace: Path,
) -> Tuple[RubricResult, ...]:
    results: List[RubricResult] = []
    for criterion in scenario.rubric:
        prompt = (
            "Evaluate exactly one rubric criterion for an agent run. Inspect files in the "
            "workspace only if needed. Do not modify any file. Start the response with exactly "
            "YES or NO, then give one short reason.\n\n"
            f"Task:\n{scenario.prompt}\n\n"
            f"Agent output:\n{agent_output}\n\n"
            f"Changed files:\n{', '.join(changed_files) if changed_files else '(none)'}\n\n"
            f"Criterion:\n{criterion}"
        )
        try:
            response, _ = backend.run(prompt, workspace, scenario.timeout)
        except RuntimeError as exc:
            results.append(RubricResult(criterion, None, str(exc)))
            continue
        match = re.match(r"\s*(YES|NO)\b", response, flags=re.IGNORECASE)
        if match is None:
            results.append(RubricResult(criterion, None, response.strip()))
        else:
            results.append(
                RubricResult(
                    criterion, match.group(1).upper() == "YES", response.strip()
                )
            )
    return tuple(results)


def run_scenario(
    root: Path,
    scenario: ScenarioSummary,
    backend: AgentBackend,
    judge: bool = False,
) -> ScenarioResult:
    manifest_path = root / scenario.manifest
    with scenario_workspace(scenario.setup, manifest_path.parent) as workspace:
        prompt = build_agent_prompt(root, scenario)
        output, changed_files = backend.run(prompt, workspace, scenario.timeout)
        assertions = evaluate_assertions(scenario.assertions, output, workspace)
        rubric = (
            score_rubric(backend, scenario, output, changed_files, workspace)
            if judge
            else None
        )
        return ScenarioResult(scenario, output, changed_files, assertions, rubric)


def _skill_file(root: Path, skill: str) -> Path:
    plugin, skill_name = skill.split("/", maxsplit=1)
    return root / "plugins" / plugin / "skills" / skill_name / "SKILL.md"


def build_experiment_prompt(
    root: Path, scenario: ScenarioSummary, arm: str
) -> str:
    if arm == "baseline":
        context = ""
    elif arm == "isolated":
        content = _skill_file(root, scenario.skill).read_text(encoding="utf-8")
        context = f"<available_skill name=\"{scenario.skill}\">\n{content}\n</available_skill>\n\n"
    elif arm == "plugin":
        plugin = scenario.skill.split("/", maxsplit=1)[0]
        skill_root = root / "plugins" / plugin / "skills"
        blocks = []
        for path in sorted(skill_root.glob("*/SKILL.md")):
            name = f"{plugin}/{path.parent.name}"
            content = path.read_text(encoding="utf-8")
            blocks.append(f"<available_skill name=\"{name}\">\n{content}\n</available_skill>")
        context = "\n\n".join(blocks) + "\n\n"
    else:
        raise ValueError(f"Unknown experiment arm: {arm}")
    return f"{context}<user_request>\n{scenario.prompt}\n</user_request>"


def _copy_seed_workspace(workspace: Path, seed: Path) -> None:
    """Copy a seed project (e.g. a real ABP module) into the isolated workspace
    so the agent works against a realistic project instead of an empty dir.
    Build/VCS output is skipped so the seed stays small."""
    ignore = shutil.ignore_patterns("bin", "obj", ".git", "node_modules")
    for item in seed.iterdir():
        if item.name in {"bin", "obj", ".git", "node_modules"}:
            continue
        dest = workspace / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def _run_experiment_arm(
    root: Path,
    scenario: ScenarioSummary,
    backend: AgentBackend,
    arm: str,
    seed_workspace: Optional[Path] = None,
) -> Dict[str, Any]:
    manifest_path = root / scenario.manifest
    with scenario_workspace(scenario.setup, manifest_path.parent) as workspace:
        if seed_workspace is not None:
            _copy_seed_workspace(workspace, seed_workspace)
        prompt = build_experiment_prompt(root, scenario, arm)
        try:
            output, changed_files = backend.run(prompt, workspace, scenario.timeout)
            return {
                "output": output,
                "changed_files": list(changed_files),
                "error": None,
            }
        except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            return {"output": "", "changed_files": [], "error": str(exc)}


def _parse_pairwise_verdict(response: str) -> Optional[str]:
    match = re.match(r"\s*(LEFT|RIGHT|TIE)\b", response, flags=re.IGNORECASE)
    return match.group(1).lower() if match else None


def _judge_pairwise_once(
    backend: AgentBackend,
    scenario: ScenarioSummary,
    left_name: str,
    left_output: str,
    right_name: str,
    right_output: str,
) -> Dict[str, Any]:
    prompt = (
        "Compare two candidate answers to the same user request. Judge only answer quality: "
        "correctness, relevance, completeness, and actionable guidance. Do not prefer an answer "
        "because of its position. Start with exactly LEFT, RIGHT, or TIE, then give one short "
        "reason.\n\n"
        f"User request:\n{scenario.prompt}\n\n"
        f"LEFT answer:\n{left_output}\n\n"
        f"RIGHT answer:\n{right_output}"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="abp-skill-eval-judge-") as temp_dir:
            response, _ = backend.run(prompt, Path(temp_dir), scenario.timeout)
        verdict = _parse_pairwise_verdict(response)
        error = None if verdict else "Judge response did not start with LEFT, RIGHT, or TIE"
    except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
        response = ""
        verdict = None
        error = str(exc)

    canonical = None
    if verdict == "tie":
        canonical = "tie"
    elif verdict == "left":
        canonical = left_name
    elif verdict == "right":
        canonical = right_name
    return {
        "left": left_name,
        "right": right_name,
        "verdict": verdict or "unavailable",
        "canonical_winner": canonical or "unavailable",
        "response": response,
        "error": error,
    }


def judge_pairwise(
    backend: AgentBackend,
    scenario: ScenarioSummary,
    treatment: str,
    baseline_output: str,
    treatment_output: str,
) -> Dict[str, Any]:
    judgments = [
        _judge_pairwise_once(
            backend,
            scenario,
            "baseline",
            baseline_output,
            treatment,
            treatment_output,
        ),
        _judge_pairwise_once(
            backend,
            scenario,
            treatment,
            treatment_output,
            "baseline",
            baseline_output,
        ),
    ]
    winners = [judgment["canonical_winner"] for judgment in judgments]
    if winners == [treatment, treatment]:
        result = "win"
    elif winners == ["baseline", "baseline"]:
        result = "lose"
    else:
        result = "tie"
    return {"treatment": treatment, "judgments": judgments, "result": result}


def activation_proxy(
    assertions: Sequence[Mapping[str, Any]], output: str
) -> Dict[str, Any]:
    signals: List[Dict[str, Any]] = []
    for assertion in assertions:
        assertion_type = assertion["type"]
        if assertion_type == "output_contains":
            expected = assertion["value"]
            matched = expected.casefold() in output.casefold()
            signals.append({"type": assertion_type, "value": expected, "matched": matched})
        elif assertion_type == "output_matches":
            pattern = assertion["pattern"]
            matched = re.search(
                pattern, output, flags=re.IGNORECASE | re.MULTILINE
            ) is not None
            signals.append({"type": assertion_type, "pattern": pattern, "matched": matched})
    return {
        "available": bool(signals),
        "matched": all(signal["matched"] for signal in signals) if signals else None,
        "signals": signals,
        "disclaimer": (
            "Proxy signal from output assertions; this is not evidence that the agent "
            "activated the target skill. True activation requires a plugin-installation harness."
        ),
    }


def _backend_metadata(backend_name: str, model: Optional[str]) -> Dict[str, Any]:
    if backend_name == "codex":
        return {
            "name": "codex",
            "model": model or "codex default",
            "config": {
                "ephemeral": True,
                "sandbox": "workspace-write",
                "skip_git_repo_check": True,
            },
        }
    return {"name": "mock", "model": None, "config": {"deterministic_echo": True}}


def run_experiment(
    root: Path,
    scenario: ScenarioSummary,
    backend: AgentBackend,
    backend_name: str,
    runs: int,
    label: str,
    model: Optional[str] = None,
    seed_workspace: Optional[Path] = None,
) -> Dict[str, Any]:
    run_results: List[Dict[str, Any]] = []
    aggregate = {
        treatment: {"win": 0, "lose": 0, "tie": 0}
        for treatment in ("isolated", "plugin")
    }
    proxy_aggregate = {"matched": 0, "not_matched": 0, "unavailable": 0}

    for run_number in range(1, runs + 1):
        arms = {
            arm: _run_experiment_arm(root, scenario, backend, arm, seed_workspace)
            for arm in ("baseline", "isolated", "plugin")
        }
        comparisons = {}
        for treatment in ("isolated", "plugin"):
            comparison = judge_pairwise(
                backend,
                scenario,
                treatment,
                arms["baseline"]["output"],
                arms[treatment]["output"],
            )
            comparisons[treatment] = comparison
            aggregate[treatment][comparison["result"]] += 1

        proxy = activation_proxy(scenario.assertions, arms["plugin"]["output"])
        if isinstance(backend, MockBackend):
            proxy = {
                **proxy,
                "available": False,
                "matched": None,
                "disclaimer": (
                    proxy["disclaimer"]
                    + " The echo-only mock backend cannot produce a meaningful proxy signal."
                ),
            }
        if not proxy["available"]:
            proxy_aggregate["unavailable"] += 1
        elif proxy["matched"]:
            proxy_aggregate["matched"] += 1
        else:
            proxy_aggregate["not_matched"] += 1
        run_results.append(
            {
                "run": run_number,
                "arms": arms,
                "comparisons": comparisons,
                "activation_proxy": proxy,
            }
        )

    return {
        "schema_version": 1,
        "experiment": "capability_ab",
        "label": label,
        "scenario": {
            "identifier": scenario.identifier,
            "skill": scenario.skill,
            "name": scenario.name,
            "prompt": scenario.prompt,
        },
        "backend": _backend_metadata(backend_name, model),
        "config": {"runs": runs, "arms": ["baseline", "isolated", "plugin"]},
        "runs": run_results,
        "aggregate": {
            "pairwise": aggregate,
            "activation_proxy": proxy_aggregate,
        },
        "activation_boundary": (
            "Plugin-arm output assertions are only a proxy signal, not true activation "
            "evidence. True activation requires a plugin-installation harness."
        ),
    }


def write_experiment_artifact(
    root: Path, result: Mapping[str, Any], results_dir: Path
) -> Path:
    skill = str(result["scenario"]["skill"]).replace("/", "-")
    label = str(result["label"])
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
        raise ValueError("Experiment label must contain only letters, numbers, '.', '_', or '-'")
    path = results_dir if results_dir.is_absolute() else root / results_dir
    path.mkdir(parents=True, exist_ok=True)
    artifact = path / f"{skill}-{label}.json"
    artifact.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact


def print_experiment_summary(result: Mapping[str, Any], artifact: Path) -> None:
    scenario = result["scenario"]
    aggregate = result["aggregate"]
    print(f"# Capability A/B experiment: {scenario['identifier']}")
    print()
    print(f"- Backend: {result['backend']['name']}")
    print(f"- Model: {result['backend']['model'] or 'not applicable'}")
    print(f"- Runs: {result['config']['runs']}")
    print(f"- Artifact: {artifact}")
    print()
    print("| Treatment vs baseline | Win | Lose | Tie |")
    print("|---|---:|---:|---:|")
    for treatment in ("isolated", "plugin"):
        counts = aggregate["pairwise"][treatment]
        print(
            f"| {treatment} | {counts['win']} | {counts['lose']} | {counts['tie']} |"
        )
    proxy = aggregate["activation_proxy"]
    print()
    print(
        "Activation proxy (plugin output assertions): "
        f"{proxy['matched']} matched, {proxy['not_matched']} not matched, "
        f"{proxy['unavailable']} unavailable."
    )
    print(
        "This is a proxy signal, not true activation evidence; true activation requires "
        "a plugin-installation harness."
    )


def select_scenarios(
    scenarios: Sequence[ScenarioSummary], skills: Sequence[str], names: Sequence[str]
) -> List[ScenarioSummary]:
    selected = list(scenarios)
    if skills:
        selected = [scenario for scenario in selected if scenario.skill in skills]
    if names:
        requested = set(names)
        selected = [
            scenario
            for scenario in selected
            if scenario.name in requested or scenario.identifier in requested
        ]
    return selected


def print_scenario_result(result: ScenarioResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"{status} {result.scenario.identifier}")
    for assertion in result.assertions:
        marker = "PASS" if assertion.passed else "FAIL"
        print(f"  [{marker}] {assertion.description}")
    changes = ", ".join(result.changed_files) if result.changed_files else "none"
    print(f"  changed files: {changes}")
    if result.rubric is None:
        print("  rubric not scored")
    else:
        for rubric in result.rubric:
            marker = (
                "PASS"
                if rubric.passed is True
                else "FAIL"
                if rubric.passed is False
                else "UNSCORED"
            )
            print(f"  [{marker}] rubric: {rubric.criterion}")
            if rubric.passed is None and rubric.response:
                print(f"    judge response: {rubric.response}")
    activation = "expected" if result.scenario.expect_activation else "not expected"
    print(f"  activation metadata: {activation}; not measured")
    for constraint in result.scenario.behavioral_constraints:
        print(f"  behavioral constraint {constraint}: not measured")


def _validate_manifests() -> bool:
    errors, _ = validate_evals.validate_repository(ROOT)
    if errors:
        print("run_evals.py: eval manifests are invalid; run eng/validate_evals.py", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List or run skill eval scenarios with deterministic assertions."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="List scenario names.")
    action.add_argument("--run", action="store_true", help="Run selected scenarios.")
    action.add_argument(
        "--experiment",
        action="store_true",
        help="Run an explicit three-arm capability A/B experiment for one scenario.",
    )
    action.add_argument(
        "--dry-run",
        action="store_true",
        help="Run selected scenarios with the deterministic mock backend.",
    )
    parser.add_argument(
        "--backend",
        choices=("mock", "codex"),
        default="mock",
        help="Agent backend. Codex is never selected implicitly (default: mock).",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        help="Run only this plugin/skill. May be repeated.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Run a scenario name or plugin/skill::scenario identifier. May be repeated.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Score each rubric item with the selected real backend (extra agent calls).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Experiment runs per arm (default: 3).",
    )
    parser.add_argument(
        "--label",
        help="Reproducible artifact label (default: current UTC timestamp).",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("eng/eval-results"),
        help="Experiment artifact directory (default: eng/eval-results).",
    )
    parser.add_argument(
        "--model",
        help="Codex model passed to `codex exec --model` and recorded in results.",
    )
    parser.add_argument(
        "--seed-workspace",
        type=Path,
        help="Experiment only: copy this directory (e.g. a real ABP module) into "
        "each arm's isolated workspace so the agent works against a real project.",
    )
    args = parser.parse_args()

    if not (args.list or args.run or args.dry_run or args.experiment):
        parser.print_help()
        return 0
    if args.dry_run and args.backend != "mock":
        parser.error("--dry-run only supports --backend mock")
    if args.judge and args.backend == "mock":
        parser.error("--judge requires a real backend such as --backend codex")
    if args.experiment and args.judge:
        parser.error("--experiment includes pairwise judging; do not add --judge")
    if args.experiment and args.backend == "codex" and not args.model:
        parser.error("--experiment --backend codex requires --model for reproducibility")
    if args.runs < 1:
        parser.error("--runs must be a positive integer")
    if not _validate_manifests():
        return 1

    scenarios = collect_scenarios(ROOT)
    selected = select_scenarios(scenarios, args.skill, args.scenario)
    if (args.skill or args.scenario) and not selected:
        print("run_evals.py: no scenarios matched the selection", file=sys.stderr)
        return 2

    if args.list:
        for scenario in selected:
            activation = "activate" if scenario.expect_activation else "do not activate"
            print(f"{scenario.skill}: {scenario.name} [{activation} metadata]")
        print(f"Listed {len(selected)} scenarios. Activation is not measured by this runner.")
        return 0

    backend: AgentBackend = (
        CodexBackend(model=args.model) if args.backend == "codex" else MockBackend()
    )
    if args.experiment:
        if len(selected) != 1:
            print(
                "run_evals.py: --experiment requires exactly one selected scenario",
                file=sys.stderr,
            )
            return 2
        label = args.label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        try:
            experiment = run_experiment(
                ROOT,
                selected[0],
                backend,
                args.backend,
                args.runs,
                label,
                args.model,
                args.seed_workspace,
            )
            artifact = write_experiment_artifact(ROOT, experiment, args.results_dir)
        except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            print(f"ERROR {selected[0].identifier}: {exc}", file=sys.stderr)
            return 1
        print_experiment_summary(experiment, artifact)
        arm_errors = sum(
            arm["error"] is not None
            for run in experiment["runs"]
            for arm in run["arms"].values()
        )
        return 1 if arm_errors else 0

    results: List[ScenarioResult] = []
    for scenario in selected:
        try:
            result = run_scenario(ROOT, scenario, backend, judge=args.judge)
        except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            print(f"ERROR {scenario.identifier}: {exc}", file=sys.stderr)
            continue
        results.append(result)
        print_scenario_result(result)

    passed = sum(result.passed for result in results)
    failed = len(results) - passed
    errors = len(selected) - len(results)
    print(
        f"Summary: {passed} passed, {failed} failed, {errors} errors, "
        f"{len(selected)} total; backend={args.backend}"
    )
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())
