#!/usr/bin/env python3
"""Skill-value experiment: does loading a SKILL.md make a coding agent write
more idiomatic ABP code, without regressing?

For each skill under test we run two arms in a fresh copy of the seed fixture:

  - baseline: the agent gets only a natural-language task (no ABP class names
    leaked into the prompt).
  - skilled:  the same task, prefixed with the skill's SKILL.md.

Each arm runs N times. After a successful agent process we run `dotnet build`
and count, only in C# files and lines added relative to the seed fixture, how
many of the skill's ABP idiom and generic anti-pattern markers appear. Higher
idiom + zero anti + a green build in the skilled arm is the signal we want.

This measures *code quality under a natural prompt*, NOT routing/activation — the
skill is injected, not discovered. See EXPERIMENT.md for why and for the caveats.

Requires: the `codex` CLI on PATH, `dotnet` (see ../../global.json), network for
the ABP NuGet restore. Configure `agent_cmd()` to test a different agent.
"""
import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIXTURE = HERE / "fixture"
# Single source of truth for the ABP version — reuse compat's central pin so the
# experiment and the compile-smoke suite can never drift apart.
VERSION_PROPS = REPO / "eng" / "compat" / "Directory.Packages.props"

MODEL = "gpt-5.6-sol"
EFFORT = "medium"
AGENT_TIMEOUT = 600
BUILD_TIMEOUT = 420


def agent_cmd(workspace: Path) -> list[str]:
    """The coding-agent invocation. Swap this out to test a different agent."""
    return [
        "codex", "exec", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "workspace-write", "--color", "never",
        "--cd", str(workspace),
        "-c", f'model_reasoning_effort="{EFFORT}"',
        "--model", MODEL, "-",
    ]


# skill -> {prompt, idiom markers, anti markers}. Prompts are intentionally
# natural: they describe the goal in plain terms and never name an ABP API, so a
# baseline run has to know the idiom on its own.
SKILLS = {
    "abp-infrastructure/handle-dates-and-time": {
        "prompt": "In the Acme.Fixture module, add a service that gives the current time "
                  "under a configurable timezone policy and normalizes any DateTime a caller "
                  "passes in, instead of reading the machine clock directly. Wire the needed "
                  "configuration, then run dotnet build and make it pass.",
        "idiom": ["IClock", "AbpClockOptions", "Normalize"],
        "anti": ["DateTime.Now", "DateTime.UtcNow"],
    },
    "abp-module-development/register-and-replace-services": {
        "prompt": "In the Acme.Fixture module, add a service interface with a default "
                  "implementation, then add a second implementation and make the framework "
                  "resolve MY implementation instead of the default one without editing the "
                  "original. Build and make it pass.",
        "idiom": ["ReplaceServices", "ExposeServices", "ITransientDependency"],
        "anti": [],
    },
    "abp-data-access/apply-data-filters": {
        "prompt": "In the Acme.Fixture module, show how to temporarily read soft-deleted "
                  "records within one scope and then restore normal filtering, and add a method "
                  "that permanently removes a record bypassing soft-delete. Build.",
        "idiom": ["IDataFilter", "ISoftDelete", "HardDeleteAsync"],
        "anti": [],
    },
    "abp-data-access/ef-core-integration": {
        "prompt": "In the Acme.Fixture module, add a Book aggregate and a custom repository "
                  "with a query method for it using the framework data layer, and register it. "
                  "Build and make it pass.",
        "idiom": ["AggregateRoot", "IRepository", "EfCoreRepository"],
        "anti": ["DbContext _"],
    },
    "abp-infrastructure/use-interceptors-and-dynamic-proxy": {
        "prompt": "In the Acme.Fixture module, add a cross-cutting behavior that runs before "
                  "and after every method of my services (timing/logging) without editing each "
                  "service. Build.",
        "idiom": ["IAbpInterceptor", "AbpInterceptor", "ProceedAsync", "IAbpMethodInvocation"],
        "anti": [],
    },
    "abp-module-development/model-domain-aggregates": {
        "prompt": "In the Acme.Fixture module, model an Order with order lines as one "
                  "consistency boundary that enforces invariants and raises a domain event when "
                  "the order is completed. Build.",
        "idiom": ["AggregateRoot", "AddLocalEvent", "protected "],
        "anti": [],
    },
    "abp-infrastructure/generate-guids": {
        "prompt": "In the Acme.Fixture module, when creating a new entity, generate its "
                  "identifier the framework-recommended way (sequential, DB-friendly) instead "
                  "of a raw random Guid. Build.",
        "idiom": ["IGuidGenerator", "GuidGenerator.Create"],
        "anti": ["Guid.NewGuid"],
    },
    "abp-data-access/seed-application-data": {
        "prompt": "In the Acme.Fixture module, add code that inserts default rows on first run "
                  "in a way the framework invokes automatically at startup. Build.",
        "idiom": ["IDataSeedContributor", "DataSeedContext", "SeedAsync"],
        "anti": [],
    },
}


def abp_version() -> str:
    """Read <AbpVersion> from compat's central package props (the one pin)."""
    m = re.search(r"<AbpVersion>([^<]+)</AbpVersion>", VERSION_PROPS.read_text())
    if not m:
        raise RuntimeError(f"<AbpVersion> not found in {VERSION_PROPS}")
    return m.group(1).strip()


# The fixture csproj uses central package management (no inline versions); this
# props file, written into each temp workspace, supplies the reused version.
PACKAGES_PROPS = """<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <AbpVersion>{version}</AbpVersion>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Volo.Abp.Ddd.Application" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.Autofac" Version="$(AbpVersion)" />
  </ItemGroup>
</Project>
"""


def snapshot_cs_files(workspace: Path) -> dict[str, str]:
    """Capture C# sources by workspace-relative path before or after an agent run."""
    return {
        path.relative_to(workspace).as_posix(): path.read_text(errors="ignore")
        for path in sorted(workspace.rglob("*.cs"))
        if not {"bin", "obj"}.intersection(path.relative_to(workspace).parts)
    }


def added_text_and_diff(
    before: dict[str, str], after: dict[str, str]
) -> tuple[str, str]:
    """Return new-file text plus inserted/replaced lines, and a unified C# diff."""
    added_lines: list[str] = []
    diff_lines: list[str] = []

    for relative_path in sorted(before.keys() | after.keys()):
        old_text = before.get(relative_path, "")
        new_text = after.get(relative_path, "")
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        if relative_path not in before:
            added_lines.extend(new_lines)
        elif relative_path in after:
            remaining_old_lines = Counter(old_lines)
            for line in new_lines:
                if remaining_old_lines[line]:
                    remaining_old_lines[line] -= 1
                else:
                    added_lines.append(line)

        if old_text != new_text:
            diff_lines.extend(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{relative_path}" if relative_path in before else "/dev/null",
                    tofile=f"b/{relative_path}" if relative_path in after else "/dev/null",
                )
            )

    return "".join(added_lines), "".join(diff_lines)


def marker_pattern(marker: str) -> re.Pattern[str]:
    """Match a marker as a token rather than as part of a larger identifier."""
    prefix = r"(?<!\w)" if marker and (marker[0].isalnum() or marker[0] == "_") else ""
    suffix = r"(?!\w)" if marker and (marker[-1].isalnum() or marker[-1] == "_") else ""
    return re.compile(prefix + re.escape(marker) + suffix)


def score_markers(
    added_text: str, idiom_markers: list[str], anti_markers: list[str]
) -> dict:
    idiom_hits = [marker for marker in idiom_markers if marker_pattern(marker).search(added_text)]
    anti_hits = [marker for marker in anti_markers if marker_pattern(marker).search(added_text)]
    return {
        "idiom": len(idiom_hits),
        "anti": len(anti_hits),
        "idiom_hits": idiom_hits,
        "anti_hits": anti_hits,
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def command_version(command: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def repo_commit() -> Optional[str]:
    return command_version(["git", "-C", str(REPO), "rev-parse", "HEAD"])


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def global_provenance() -> dict:
    return {
        "abp_version": abp_version(),
        "repo_commit": repo_commit(),
        "dotnet_version": command_version(["dotnet", "--version"]),
        "codex_version": command_version(["codex", "--version"]),
        "timestamp": timestamp(),
        "model": MODEL,
        "reasoning_effort": EFFORT,
    }


def _output_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _write_after_sources(artifact_dir: Path, after: dict[str, str]) -> None:
    source_dir = artifact_dir / "after_cs"
    for relative_path, content in after.items():
        destination = source_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)


def execute_workspace(
    *,
    workspace: Path,
    before: dict[str, str],
    prompt: str,
    spec: dict,
    artifact_dir: Path,
    provenance: dict,
    agent_command: list[str],
    build_command: Optional[list[str]] = None,
    agent_timeout: int = AGENT_TIMEOUT,
    build_timeout: int = BUILD_TIMEOUT,
) -> dict:
    """Run one agent and, only after normal completion, build and score its output."""
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.txt").write_text(prompt)

    agent_started = time.monotonic()
    agent_stdout = ""
    agent_stderr = ""
    agent_exit_code: Optional[int] = None
    agent_exception: Optional[str] = None
    try:
        agent_result = subprocess.run(
            agent_command,
            cwd=workspace,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=agent_timeout,
            check=False,
        )
        agent_stdout = agent_result.stdout
        agent_stderr = agent_result.stderr
        agent_exit_code = agent_result.returncode
        agent_status = "agent_ok" if agent_result.returncode == 0 else "agent_error"
    except subprocess.TimeoutExpired as exc:
        agent_status = "agent_timeout"
        agent_stdout = _output_text(exc.stdout)
        agent_stderr = _output_text(exc.stderr)
        agent_exception = str(exc)
    except Exception as exc:  # noqa: BLE001 - preserve process launch failures
        agent_status = "agent_error"
        agent_exception = f"{type(exc).__name__}: {exc}"
    agent_duration = time.monotonic() - agent_started

    after = snapshot_cs_files(workspace)
    added_text, diff = added_text_and_diff(before, after)
    has_added_code = bool(added_text.strip())
    (artifact_dir / "agent.stdout.log").write_text(agent_stdout)
    (artifact_dir / "agent.stderr.log").write_text(agent_stderr)
    (artifact_dir / "added_code.txt").write_text(added_text)
    (artifact_dir / "changes.diff").write_text(diff)
    _write_after_sources(artifact_dir, after)
    agent_metadata = {
        "status": agent_status,
        "exit_code": agent_exit_code,
        "exception": agent_exception,
        "duration_seconds": agent_duration,
        "command": agent_command,
    }
    (artifact_dir / "agent.json").write_text(json.dumps(agent_metadata, indent=2))

    build_status = "not_run"
    build_exit_code: Optional[int] = None
    build_stdout = ""
    build_stderr = ""
    build_exception: Optional[str] = None
    build_duration: Optional[float] = None
    build_ran = False
    if agent_status == "agent_ok":
        build_ran = True
        build_started = time.monotonic()
        try:
            build_result = subprocess.run(
                build_command or ["dotnet", "build", "-v", "q", "-nologo"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=build_timeout,
                check=False,
            )
            build_stdout = build_result.stdout
            build_stderr = build_result.stderr
            build_exit_code = build_result.returncode
            build_status = "build_pass" if build_result.returncode == 0 else "build_fail"
        except Exception as exc:  # noqa: BLE001 - a failed build invocation is a build failure
            build_status = "build_fail"
            build_exception = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, subprocess.TimeoutExpired):
                build_stdout = _output_text(exc.stdout)
                build_stderr = _output_text(exc.stderr)
        build_duration = time.monotonic() - build_started

    build_metadata = {
        "status": build_status,
        "ran": build_ran,
        "exit_code": build_exit_code,
        "exception": build_exception,
        "duration_seconds": build_duration,
        "command": build_command or ["dotnet", "build", "-v", "q", "-nologo"],
    }
    (artifact_dir / "build.stdout.log").write_text(build_stdout)
    (artifact_dir / "build.stderr.log").write_text(build_stderr)
    (artifact_dir / "build.log").write_text(build_stdout + build_stderr)
    (artifact_dir / "build.json").write_text(json.dumps(build_metadata, indent=2))

    run_provenance = {
        **provenance,
        "timestamp": timestamp(),
        "prompt_sha256": sha256_text(prompt),
    }
    (artifact_dir / "provenance.json").write_text(
        json.dumps(run_provenance, indent=2)
    )

    scoring_eligible = agent_status == "agent_ok" and has_added_code
    scores = (
        score_markers(added_text, spec["idiom"], spec["anti"])
        if scoring_eligible
        else {"idiom": None, "anti": None, "idiom_hits": [], "anti_hits": []}
    )
    run_record = {
        "status": build_status if agent_status == "agent_ok" else agent_status,
        "agent_status": agent_status,
        "build_status": build_status,
        "agent": agent_metadata,
        "build": build_metadata,
        "has_added_code": has_added_code,
        "scoring_eligible": scoring_eligible,
        **scores,
        "idiom_tot": len(spec["idiom"]),
        "artifact_dir": str(artifact_dir.relative_to(REPO))
        if artifact_dir.is_relative_to(REPO)
        else str(artifact_dir),
    }
    (artifact_dir / "result.json").write_text(json.dumps(run_record, indent=2))
    return run_record


def run_arm(
    skill: str,
    spec: dict,
    skilled: bool,
    run_idx: int,
    runs_dir: Path,
    provenance: dict,
) -> dict:
    ws = Path(tempfile.mkdtemp(prefix="abp-exp-"))
    try:
        for item in FIXTURE.iterdir():
            if item.name in ("bin", "obj"):
                continue
            dst = ws / item.name
            (shutil.copytree if item.is_dir() else shutil.copy2)(item, dst)
        (ws / "Directory.Packages.props").write_text(
            PACKAGES_PROPS.format(version=abp_version()))

        before = snapshot_cs_files(ws)
        plugin, name = skill.split("/")
        skill_text = (REPO / "plugins" / plugin / "skills" / name / "SKILL.md").read_text()
        prompt = spec["prompt"]
        if skilled:
            md = skill_text
            prompt = f"<available_skill>\n{md}\n</available_skill>\n\n{prompt}"
        arm = "skilled" if skilled else "baseline"
        artifact_dir = runs_dir / skill / arm / str(run_idx)
        return execute_workspace(
            workspace=ws,
            before=before,
            prompt=prompt,
            spec=spec,
            artifact_dir=artifact_dir,
            provenance={
                **provenance,
                "skill": skill,
                "arm": arm,
                "run_index": run_idx,
                "skill_sha256": sha256_text(skill_text),
            },
            agent_command=agent_cmd(ws),
        )
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def aggregate(runs: list[dict]) -> dict:
    build_runs = [run for run in runs if run["agent_status"] == "agent_ok"]
    scored_runs = [run for run in runs if run["scoring_eligible"]]
    build_pass = sum(run["build_status"] == "build_pass" for run in build_runs)
    return {
        "runs": len(runs),
        "agent_ok": len(build_runs),
        "agent_error": sum(run["agent_status"] == "agent_error" for run in runs),
        "agent_timeout": sum(run["agent_status"] == "agent_timeout" for run in runs),
        "build_eligible_runs": len(build_runs),
        "build_pass": build_pass,
        "build_fail": sum(run["build_status"] == "build_fail" for run in build_runs),
        "build_pass_rate": build_pass / len(build_runs) if build_runs else None,
        "scored_runs": len(scored_runs),
        "idiom": (
            sum(run["idiom"] for run in scored_runs) / len(scored_runs)
            if scored_runs
            else None
        ),
        "anti": sum(run["anti"] for run in scored_runs),
        "idiom_tot": runs[0]["idiom_tot"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=3, help="runs per arm (default 3)")
    ap.add_argument("--only", help="run a single skill by 'plugin/name'")
    ap.add_argument("--out", type=Path, default=HERE / "results.json")
    ap.add_argument("--runs-dir", type=Path, default=HERE / "runs")
    args = ap.parse_args()

    skills = {args.only: SKILLS[args.only]} if args.only else SKILLS
    provenance = global_provenance()
    results = []
    for skill, spec in skills.items():
        row = {"skill": skill, "baseline": [], "skilled": []}
        for run_idx in range(1, args.runs + 1):
            row["baseline"].append(
                run_arm(skill, spec, False, run_idx, args.runs_dir, provenance)
            )
            row["skilled"].append(
                run_arm(skill, spec, True, run_idx, args.runs_dir, provenance)
            )
        row["baseline_agg"] = aggregate(row["baseline"])
        row["skilled_agg"] = aggregate(row["skilled"])
        results.append(row)
        output = {"provenance": provenance, "results": results}
        args.out.write_text(json.dumps(output, indent=2))
        b, s = row["baseline_agg"], row["skilled_agg"]
        b_idiom = "n/a" if b["idiom"] is None else f"{b['idiom']:.1f}"
        s_idiom = "n/a" if s["idiom"] is None else f"{s['idiom']:.1f}"
        print(
            f"{skill:48} build b={b['build_pass']}/{b['build_eligible_runs']} "
            f"s={s['build_pass']}/{s['build_eligible_runs']} | "
            f"agent-error/timeout b={b['agent_error']}/{b['agent_timeout']} "
            f"s={s['agent_error']}/{s['agent_timeout']} | "
            f"idiom b={b_idiom} s={s_idiom}/{s['idiom_tot']} | "
            f"anti b={b['anti']} s={s['anti']}"
        )
    print(f"DONE -> {args.out}")


if __name__ == "__main__":
    main()
