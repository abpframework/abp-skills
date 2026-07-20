#!/usr/bin/env python3
"""Skill-value experiment for a weaker model reached through a plain chat API.

The agent-based `run_experiment.py` measures a strong tool-driven agent (codex).
Against GPT/Opus-class models that already know the ABP idiom, the baseline is at
ceiling and the skill can't move the number (see `EXPERIMENT.md`). A weaker model is
where a skill should earn its place — but a weak model behind a raw chat endpoint is
not an agent: it can't read the fixture, write files, or iterate on a build.

So this harness measures **single-shot generation**: give the model the task (baseline)
or the task prefixed with the skill's `SKILL.md` (skilled), take the C# it returns,
drop it into a fresh copy of the fixture, `dotnet build`, and count idiom vs anti-pattern
markers in the generated code. Both arms are the same model, so it is a clean
within-model comparison of "does loading the skill change the code the model writes".

Markers here are deliberately **ABP-distinctive** (e.g. `IBlobContainer`, not the
generic `SaveAsync` that any storage interface would also have), because a single-shot
answer often invents its own generic interface whose method names collide with loose
markers.

Serial only — the endpoint rate-limits hard (error 1305). The API key is read from the
`GLM_API_KEY` environment variable and is never committed or passed on curl's argv; during
each request it is written to a private (0600) temp config file that is removed when curl
exits or times out, before any response processing or retry sleep.

Usage:
  GLM_API_KEY=... python3 eng/experiment/run_experiment_chat.py            # all, 3 runs
  GLM_API_KEY=... python3 eng/experiment/run_experiment_chat.py --runs 2 --only abp-files/store-blobs
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIXTURE = HERE / "fixture"
VERSION_PROPS = REPO / "eng" / "compat" / "Directory.Packages.props"
PLUGINS = REPO / "plugins"

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4.7-flash"
BACKEND = "glm"          # "glm" (bigmodel chat API) or "claude" (local `claude -p`)
TEMPERATURE = 0.8
MAX_TOKENS = 8192

# The hard skills: ones where a weak model's default reach is clearly non-ABP, so the
# baseline has somewhere to fall and the skill has room to lift. Markers are
# ABP-distinctive on the idiom side and the generic default on the anti side.
HARD_SKILLS = {
    "abp-files/store-blobs": {
        "task": "add a service that saves the raw bytes of an uploaded file under a key for a "
                "given entity, and reads them back later, written so the storage backend "
                "(local disk, database, cloud) can be swapped later without changing this code.",
        "idiom": ["IBlobContainer", "GetAllBytesAsync"],
        "anti": ["File.WriteAllBytes", "File.ReadAllBytes", "File.WriteAllBytesAsync",
                 "File.ReadAllBytesAsync", "Path.Combine", "Directory.CreateDirectory"],
    },
    "abp-runtime/distributed-caching-and-locking": {
        "task": "add a method that guarantees a section of work runs on only one instance at a "
                "time even when several copies of the app run at once, and releases it when done.",
        "idiom": ["IAbpDistributedLock", "TryAcquireAsync"],
        "anti": ["SemaphoreSlim", "Monitor.Enter", "Mutex", "lock ("],
    },
    "abp-runtime/background-jobs-and-events": {
        "task": "add something that runs a maintenance task repeatedly on a fixed interval in the "
                "background, managed by the framework's own scheduling rather than a hand-rolled "
                "timer or hosted background loop.",
        "idiom": ["AsyncPeriodicBackgroundWorkerBase", "PeriodicBackgroundWorkerContext"],
        "anti": ["IHostedService", "BackgroundService", "System.Threading.Timer", "Task.Run",
                 "while (true)"],
    },
    "abp-infrastructure/manage-settings-and-features": {
        "task": "add a configuration value with a default that an administrator can change at "
                "runtime (for example, per tenant) without redeploying, and read its current "
                "value in a service.",
        "idiom": ["SettingDefinitionProvider", "ISettingProvider", "GetOrNullAsync"],
        "anti": ["IConfiguration", "IOptions", "appsettings", "GetConnectionString"],
    },
}

CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>Acme.Fixture</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Volo.Abp.Ddd.Application" />
    <PackageReference Include="Volo.Abp.Autofac" />
    <PackageReference Include="Volo.Abp.BlobStoring" />
    <PackageReference Include="Volo.Abp.DistributedLocking" />
    <PackageReference Include="Volo.Abp.BackgroundWorkers" />
    <PackageReference Include="Volo.Abp.BackgroundJobs.Abstractions" />
    <PackageReference Include="Volo.Abp.Settings" />
  </ItemGroup>
</Project>
"""
# Note: IHostedService / BackgroundService (a baseline's generic reach) resolve through
# Volo.Abp.Autofac's transitive Microsoft.Extensions.Hosting.Abstractions, so no explicit
# reference is needed (pinning an older one triggers an NU1605 downgrade error).

PACKAGES_PROPS = """<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <AbpVersion>{abp}</AbpVersion>
  </PropertyGroup>
  <ItemGroup>
    <PackageVersion Include="Volo.Abp.Ddd.Application" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.Autofac" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.BlobStoring" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.DistributedLocking" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.BackgroundWorkers" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.BackgroundJobs.Abstractions" Version="$(AbpVersion)" />
    <PackageVersion Include="Volo.Abp.Settings" Version="$(AbpVersion)" />
  </ItemGroup>
</Project>
"""

INSTRUCTION_CS = ("You are writing C# for an ABP Framework module named Acme.Fixture. "
                  "Task: {task} "
                  "Output only the complete C# file(s), each in its own ```csharp code block.")
INSTRUCTION_TS = ("You are writing TypeScript for an ABP Angular application. "
                  "Task: {task} "
                  "Output only the complete .ts file(s), each in its own ```typescript code block.")


def instruction_for(spec):
    return (INSTRUCTION_TS if spec.get("lang") == "ts" else INSTRUCTION_CS).format(task=spec["task"])


def abp_version():
    m = re.search(r"<AbpVersion>([^<]+)</AbpVersion>", VERSION_PROPS.read_text())
    if not m:
        raise RuntimeError(f"<AbpVersion> not found in {VERSION_PROPS}")
    return m.group(1).strip()


def marker_pattern(marker):
    prefix = r"(?<!\w)" if marker and (marker[0].isalnum() or marker[0] == "_") else ""
    suffix = r"(?!\w)" if marker and (marker[-1].isalnum() or marker[-1] == "_") else ""
    return re.compile(prefix + re.escape(marker) + suffix)


def score_markers(text, idiom, anti):
    idiom_hits = [m for m in idiom if marker_pattern(m).search(text)]
    anti_hits = [m for m in anti if marker_pattern(m).search(text)]
    return {"idiom": len(idiom_hits), "anti": len(anti_hits),
            "idiom_hits": idiom_hits, "anti_hits": anti_hits}


def call_glm(prompt, api_key, max_attempts=12):
    """Call the chat endpoint serially with backoff on rate-limit (error 1305)."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "enabled"},
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    delay = 15
    last = None
    for attempt in range(max_attempts):
        # Write the Authorization header to a private curl config file (mkstemp => 0600) read
        # via -K, so the key is not passed on curl's argv. Remove it when curl exits or times
        # out — before response processing or any retry sleep — so it does not remain during
        # retry backoff.
        cfg_path = None
        proc = None
        try:
            fd, cfg_path = tempfile.mkstemp(suffix=".curlcfg")
            with os.fdopen(fd, "w", encoding="utf-8") as cfg:
                cfg.write(f'header = "Authorization: Bearer {api_key}"\n')
            proc = subprocess.run(
                ["curl", "-s", "-X", "POST", API_URL,
                 "-K", cfg_path,
                 "-H", "Content-Type: application/json",
                 "-d", "@-"],
                input=json.dumps(body), capture_output=True, text=True, timeout=240,
            )
        except subprocess.TimeoutExpired:
            last = "curl timeout (240s)"
        finally:
            if cfg_path is not None:
                try:
                    os.unlink(cfg_path)
                except FileNotFoundError:
                    pass

        if proc is None:  # timed out; key file already removed
            time.sleep(delay)
            delay = min(delay + 10, 60)
            continue

        try:
            data = json.loads(proc.stdout)
        except ValueError:
            last = f"non-JSON: {proc.stdout[:200]}"
            time.sleep(delay)
            continue
        if "error" in data:
            last = f"{data['error'].get('code')} {data['error'].get('message')}"
            time.sleep(delay)
            delay = min(delay + 10, 60)
            continue
        content = data["choices"][0]["message"].get("content", "") or ""
        return content, data.get("usage", {})
    raise RuntimeError(f"glm call failed after {max_attempts} attempts: {last}")


def call_claude(prompt, model, max_attempts=3):
    """Single-shot generation via the local `claude -p` CLI (for Opus/Sonnet).

    Run in a throwaway cwd so the model answers from the prompt alone instead of
    exploring this repo — matching the glm single-shot setup.
    """
    last = None
    for _ in range(max_attempts):
        scratch = tempfile.mkdtemp(prefix="claude_gen_")
        try:
            # Prompt goes on stdin, not argv: a skilled prompt starts with the SKILL.md
            # `---` frontmatter, which `claude -p` would otherwise read as a CLI option.
            proc = subprocess.run(
                ["claude", "-p", "--model", model],
                input=prompt, capture_output=True, text=True, timeout=900, cwd=scratch,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout, {"backend": "claude", "model": model}
        last = (proc.stderr or proc.stdout)[:200]
        time.sleep(5)
    raise RuntimeError(f"claude call failed: {last}")


def call_codex(prompt, model, effort, max_attempts=3):
    """Single-shot generation via `codex exec` (for the GPT column). Prompt on stdin,
    read-only sandbox; the code lands in the final agent_message of the --json stream."""
    last = None
    for _ in range(max_attempts):
        proc = subprocess.run(
            ["codex", "exec", "--json", "--skip-git-repo-check", "-s", "read-only",
             "-c", f"model_reasoning_effort={effort}", "--model", model, "-"],
            input=prompt, capture_output=True, text=True, timeout=600,
        )
        texts = []
        for line in proc.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            item = event.get("item", {})
            if item.get("type") == "agent_message" and item.get("text"):
                texts.append(item["text"])
        if texts:
            return "\n".join(texts), {"backend": "codex", "model": model}
        last = (proc.stderr or proc.stdout)[:200]
        time.sleep(5)
    raise RuntimeError(f"codex call failed: {last}")


def call_model(prompt, api_key, effort):
    if BACKEND == "claude":
        return call_claude(prompt, MODEL)
    if BACKEND == "codex":
        return call_codex(prompt, MODEL, effort)
    return call_glm(prompt, api_key)


CODE_BLOCK = re.compile(r"```(?:csharp|cs|c#|ts|typescript|js)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text):
    blocks = [b.strip() for b in CODE_BLOCK.findall(text) if b.strip()]
    return blocks


def build_workspace(code_blocks, abp):
    """Fresh fixture copy + generated files; returns (workspace, added_text)."""
    ws = Path(tempfile.mkdtemp(prefix="glm_exp_"))
    for item in FIXTURE.iterdir():
        if item.name in {"bin", "obj", "README.md"}:
            continue
        if item.suffix == ".csproj":
            continue  # replaced below
        shutil.copy2(item, ws / item.name)
    (ws / "Acme.Fixture.csproj").write_text(CSPROJ)
    (ws / "Directory.Packages.props").write_text(PACKAGES_PROPS.format(abp=abp))
    gen = ws / "Generated"
    gen.mkdir()
    for i, block in enumerate(code_blocks):
        (gen / f"Generated{i}.cs").write_text(block)
    return ws, "\n".join(code_blocks)


def run_one(skill, spec, arm, run_idx, abp, api_key, artifact_root, no_build, effort):
    prompt = instruction_for(spec)
    if arm == "skilled":
        skill_md = (PLUGINS / skill.replace("/", "/skills/") / "SKILL.md").read_text()
        prompt = skill_md + "\n\n---\n\n" + prompt

    art = artifact_root / skill / arm / str(run_idx)
    art.mkdir(parents=True, exist_ok=True)
    (art / "prompt.txt").write_text(prompt)

    result = {"skill": skill, "arm": arm, "run": run_idx}
    try:
        content, usage = call_model(prompt, api_key, effort)
    except Exception as exc:  # noqa: BLE001 - one bad call must never kill the whole run
        result.update(status="api_fail", error=f"{type(exc).__name__}: {exc}")
        (art / "error.txt").write_text(str(exc))
        return result
    (art / "response.txt").write_text(content)
    (art / "usage.json").write_text(json.dumps(usage, indent=2))

    blocks = extract_code(content)
    if not blocks:
        result.update(status="no_code", build="not_run", idiom=0, anti=0)
        return result
    added = "\n".join(blocks)
    (art / "added_code.txt").write_text(added)
    scores = score_markers(added, spec["idiom"], spec["anti"])

    # Marker scoring is the discriminating metric; the build is a secondary check we skip
    # for the full-matrix sweep (--no-build) and always for TS (no dotnet build applies).
    build_status = "skipped"
    if not no_build and spec.get("lang") != "ts":
        ws, _ = build_workspace(blocks, abp)
        build = subprocess.run(
            ["dotnet", "build", "-v", "q", "-nologo"], cwd=ws,
            capture_output=True, text=True, timeout=600,
        )
        (art / "build.log").write_text(build.stdout + build.stderr)
        shutil.rmtree(ws, ignore_errors=True)
        build_status = "pass" if build.returncode == 0 else "fail"

    result.update(
        status="ok",
        build=build_status,
        idiom=scores["idiom"], idiom_tot=len(spec["idiom"]), idiom_hits=scores["idiom_hits"],
        anti=scores["anti"], anti_hits=scores["anti_hits"],
    )
    return result


def aggregate(rows):
    ok = [r for r in rows if r.get("status") == "ok"]
    n = len(ok)
    return {
        "runs": len(rows),
        "scored": n,
        "build_pass": sum(1 for r in ok if r["build"] == "pass"),
        "idiom_mean": round(sum(r["idiom"] for r in ok) / n, 2) if n else None,
        "anti_mean": round(sum(r["anti"] for r in ok) / n, 2) if n else None,
    }


def assemble(skills, rows, abp):
    """Group finished rows into per-skill baseline/skilled records with aggregates."""
    results = []
    for skill in skills:
        record = {"skill": skill}
        for arm in ("baseline", "skilled"):
            arm_rows = [r for r in rows if r["skill"] == skill and r["arm"] == arm]
            arm_rows.sort(key=lambda r: r["run"])
            record[arm] = arm_rows
            record[arm + "_agg"] = aggregate(arm_rows)
        results.append(record)
    return {
        "provenance": {"model": MODEL, "abp_version": abp,
                       "timestamp": datetime.now(timezone.utc).isoformat(),
                       "temperature": TEMPERATURE, "mode": "single-shot chat"},
        "results": results,
    }


def main():
    global MODEL, BACKEND
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", help="single skill key, e.g. abp-files/store-blobs")
    parser.add_argument("--backend", choices=["glm", "claude", "codex"], default=BACKEND,
                        help="glm = bigmodel chat API; claude = local `claude -p` (Opus); codex = `codex exec` (GPT)")
    parser.add_argument("--model", default=MODEL,
                        help="model id: glm-4.7-flash / glm-4.7 / opus / gpt-5.6-sol")
    parser.add_argument("--jobs", type=int, default=1,
                        help="concurrent calls. Keep 1 for rate-limited models (glm-4.7-flash); "
                             "glm-4.7 / claude / codex have no such limit, so a higher value is fine.")
    parser.add_argument("--effort", default="medium", help="reasoning effort for codex backend")
    parser.add_argument("--specs", help="JSON file {skill: {task,lang,idiom,anti}} — replaces the built-in set")
    parser.add_argument("--no-build", action="store_true", help="skip dotnet build; score markers only")
    parser.add_argument("--resume", action="store_true",
                        help="keep already-ok rows in --out and only re-run the missing/failed (skill,arm,run)")
    parser.add_argument("--out", default=str(HERE / "results_glm.json"))
    parser.add_argument("--runs-dir", default=str(HERE / "runs_glm"))
    args = parser.parse_args()
    MODEL = args.model
    BACKEND = args.backend

    api_key = os.environ.get("GLM_API_KEY")
    if BACKEND == "glm" and not api_key:
        raise SystemExit("set GLM_API_KEY")
    abp = abp_version()
    all_specs = json.loads(Path(args.specs).read_text()) if args.specs else HARD_SKILLS
    skills = {args.only: all_specs[args.only]} if args.only else all_specs
    artifact_root = Path(args.runs_dir)

    tasks = [(skill, spec, arm, run_idx)
             for skill, spec in skills.items()
             for arm in ("baseline", "skilled")
             for run_idx in range(1, args.runs + 1)]

    rows = []
    if args.resume and Path(args.out).exists():
        prev = json.loads(Path(args.out).read_text())
        done = set()
        for rec in prev.get("results", []):
            for arm in ("baseline", "skilled"):
                for r in rec.get(arm, []):
                    if r.get("status") == "ok":
                        rows.append(r)
                        done.add((r["skill"], r["arm"], r["run"]))
        before = len(tasks)
        tasks = [t for t in tasks if (t[0], t[2], t[3]) not in done]
        print(f"resume: {len(rows)} ok rows kept, {before - len(tasks)} skipped, {len(tasks)} to run",
              flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(run_one, s, spec, arm, ri, abp, api_key, artifact_root,
                               args.no_build, args.effort): (s, arm, ri)
                   for (s, spec, arm, ri) in tasks}
        for fut in as_completed(futures):
            row = fut.result()
            rows.append(row)
            print(f"{row['skill']} {row['arm']} run{row['run']}: {row.get('status')} "
                  f"build={row.get('build')} idiom={row.get('idiom')}/{row.get('idiom_tot','?')} "
                  f"anti={row.get('anti')}", flush=True)
            # incremental save so a stall/crash never loses finished work
            Path(args.out).write_text(json.dumps(assemble(skills, rows, abp), indent=2, ensure_ascii=False))

    print("\n=== summary (baseline -> skilled) ===")
    for r in assemble(skills, rows, abp)["results"]:
        b, s = r["baseline_agg"], r["skilled_agg"]
        print(f"{r['skill']}")
        print(f"   build {b['build_pass']}/{b['scored']} -> {s['build_pass']}/{s['scored']} | "
              f"idiom {b['idiom_mean']} -> {s['idiom_mean']} | anti {b['anti_mean']} -> {s['anti_mean']}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
