# Skill-value experiment

A reproducible check of whether a skill actually helps a coding agent — does
loading a `SKILL.md` make the agent write more idiomatic ABP code, and does it
ever make things worse? This is the evidence behind "these skills earn their
place." Re-run it when ABP or the underlying model changes to confirm the skills
still pull their weight.

This is separate from the eval suite (`tests/**/eval.yaml`, run by
`eng/run_evals.py`), which checks routing/trigger wording. This experiment
measures the *code an agent produces* with and without the skill.

## What it measures

For each skill, two arms run in a fresh copy of a small real ABP module
(`eng/experiment/fixture/`, `Acme.Fixture`):

- **baseline** — the agent gets only a natural-language task. Prompts never name
  an ABP API, so the baseline has to know the idiom on its own.
- **skilled** — the same task, prefixed with the skill's `SKILL.md`.

Each arm runs 3 times. Before the agent starts, the harness snapshots every
fixture `.cs` file. After a successful agent process, it runs `dotnet build` and
counts markers only in newly created files and lines added to existing files.
Fixture code never contributes to the score. Agent errors and timeouts are
reported separately and excluded from the build-rate denominator. Idiom and
anti-pattern scores include only successful agent runs that added C# code.

## How to run

```bash
cd eng/experiment
python3 run_experiment.py                    # all skills, 3 runs each
python3 run_experiment.py --runs 5           # more runs
python3 run_experiment.py --only abp-data-access/apply-data-filters
```

Requires the `codex` CLI on `PATH`, `dotnet` (version in `global.json`), and
network for the ABP NuGet restore. The agent command, model, and reasoning effort
are constants at the top of `run_experiment.py` — change `agent_cmd()` to point
the same harness at a different agent. Summary and per-run status data land in
`results.json`. Auditable artifacts for each run land under
`runs/<plugin>/<skill>/<arm>/<run>/`, including the prompt, agent output, exit
status, C# diff and post-run sources, build logs, marker hits, and provenance.

The ABP version is not pinned in the fixture — the harness reuses the
`<AbpVersion>` from `eng/compat/Directory.Packages.props` (the one place the repo
pins it) and injects it into each temp workspace, so bumping that one file moves
both the compile-smoke suite and this experiment together.

## Results

Re-run on the current (hardened) harness. Model `gpt-5.6-sol`, medium reasoning
effort, 3 runs per arm, ABP `10.5.0`, repo commit `a2f6cb3`, dotnet `10.0.301`,
`codex-cli 0.144.5`, 2026-07-17. `b` = baseline, `s` = skilled. Idiom is the mean
count of the skill's ABP markers found (out of the total in parentheses); anti is the
total generic-shortcut hits across all runs.

| skill | compile b/s | idiom b/s | anti b/s | verdict |
| --- | --- | --- | --- | --- |
| handle-dates-and-time | 3/3 | 3.0 / 3.0 (of 3) | 0/0 | tie |
| register-and-replace-services | 3/3 → 2/3 | 2.3 / 1.7 (of 3) | 0/0 | build fail = harness, see below |
| apply-data-filters | 3/3 | 3.0 / 3.0 (of 3) | 0/0 | tie |
| ef-core-integration | 3/3 | 1.7 → 2.0 (of 3) | 0/0 | slight help |
| use-interceptors-and-dynamic-proxy | 3/3 | 3.0 / 3.0 (of 4) | 0/0 | tie |
| model-domain-aggregates | 3/3 | 3.0 / 3.0 (of 3) | 0/0 | tie |
| generate-guids | 3/3 | 1.0 / 1.0 (of 2) | 0/0 | tie |
| seed-application-data | 3/3 | 3.0 / 3.0 (of 3) | 0/0 | tie |

**1 slight-help / 6 tie / 0 content regressions / 0 anti-patterns.** The one skilled
build failure (`register-and-replace-services`, run 1) was `dotnet build` **MSB1011**
("more than one project or solution file"): that run's agent also scaffolded a test
project, so the folder-level build turned ambiguous and exited in 0.09 s without
compiling. The C# it wrote was fine and baseline passed 3/3 — so it is a harness/agent
artifact, not broken code (fix: point the build step at `Acme.Fixture.csproj`).

## Conclusions

**This re-run does not demonstrate a skill-value lift on this sample — and it does not
show a regression either.** The honest read:

- **Ceiling effect.** Baseline (gpt-5.6-sol at medium effort, no skill) already
  compiles 8/8 and hits most idiom markers on its own — 6 of 8 skills score baseline
  idiom at or near the maximum. That leaves almost no headroom for the skill to move
  the number, so a null result here is expected and is **not** evidence the skills are
  useless; it is evidence the sample and model are saturated.
- **No real regression.** The single skilled build failure was MSB1011 (harness/agent
  scaffolding, above), not broken code. Anti-patterns stayed at 0 in both arms for
  every skill — loading a skill never pushed the agent toward a generic shortcut.
- **The one positive move** (`ef-core-integration` idiom 1.7 → 2.0) is within n=3 noise;
  it is not a claim.

So for these deliberately foundational skills against a frontier model, effectiveness is
**undemonstrated by measurement, not disproven** — a ceiling effect, not a useless skill.
The way to actually measure lift is inputs where the baseline fails: more obscure ABP
surface and/or a weaker model.

**That follow-up run now exists** — see `model-comparison.md`. On four non-obvious skills
(blob storage, distributed locking, background workers, settings) two open models
(`glm-4.7` and `glm-4.7-flash`) *do* write materially more idiomatic ABP code with the
skill: idiom markers rise ~+1 on average and generic shortcuts (`File.WriteAllBytes`,
`SemaphoreSlim`, hand-rolled timers, `IConfiguration`) drop to zero. So skill value is
real where the model's untutored answer is not already the ABP idiom; it just does not
show up for a frontier model on foundational surface, which is at ceiling. The gates
prove the referenced samples compile and the listed runtime behaviors pass — loading a
skill improves output only where there is headroom.

## Caveats — what this does NOT prove

- **Injection, not activation.** The skill is prepended to the prompt; the
  experiment does not test whether the agent's router would *discover* the skill
  from its `description`. Trigger wording is covered separately by the eval suite.
- **Proxy metric.** Marker matching is lexical, not a C# syntax-tree analysis.
  It uses token boundaries and only added lines, which prevents fixture and
  larger-identifier substring hits, but a marker in a newly added comment or
  string can still count. `dotnet build` passing is a floor, not proof the code
  does the right thing.
- **One model, one effort, small n.** Results shift with a weaker/stronger model,
  lower/higher reasoning effort, and a bigger fixture. A lean earlier variant
  (low effort, terse answers) *overstated* the skills' value; this stricter setup
  is more modest and more trustworthy. Treat the numbers as directional.
- **One scenario per skill.** Each skill is probed with a single task; a broader
  prompt set would give a fuller picture.
