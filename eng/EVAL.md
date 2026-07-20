# Skill evaluations

Evaluation manifests live at:

```text
tests/<plugin>/<skill>/eval.yaml
```

The `<plugin>/<skill>` pair must map to
`plugins/<plugin>/skills/<skill>/SKILL.md`. Every skill must have an eval
manifest — `validate_evals.py` fails if any skill is missing one.

## Manifest schema

Each eval manifest has this shape:

```yaml
scenarios:
  - name: "Unique scenario name within this manifest"
    prompt: "The user request given to the agent."
    expect_activation: true
    setup:
      copy_test_files: true
      files:
        - path: "src/Input.cs"
          content: |
            public class Input
            {
            }
        - path: "data.csv"
          source: "fixtures/sample-data.csv"
      commands:
        - "dotnet restore"
    assertions:
      - type: "output_contains"
        value: "Required literal"
      - type: "output_not_contains"
        value: "Text that must not appear"
      - type: "output_matches"
        pattern: "Required (regular expression|alternative)"
      - type: "output_not_matches"
        pattern: "Pattern that must not match"
      - type: "file_exists"
        path: "src/**/Expected.cs"
      - type: "file_not_exists"
        path: "src/Forbidden.cs"
      - type: "file_contains"
        path: "src/*.cs"
        value: "stackalloc"
      - type: "file_not_contains"
        path: "src/*.cs"
        value: "unsafe"
      - type: "exit_success"
        command: "dotnet build"
      - type: "run_command_and_assert"
        command: "dotnet test"
        exit_code: 0
        stdout_contains: "Passed"
        stdout_matches: "Passed!\\s+-\\s+Failed:\\s+0"
        stderr_matches: "^$"
    expect_tools: ["bash"]
    reject_tools: ["create_file"]
    max_turns: 15
    max_tokens: 5000
    rubric:
      - "An outcome-oriented criterion for a future judge."
    timeout: 180
```

Required scenario fields are `name`, `prompt`, `expect_activation`,
`assertions`, `rubric`, and `timeout`. `setup`, `expect_tools`, `reject_tools`,
`max_turns`, and `max_tokens` are optional. The validator requires:

- a non-empty top-level `scenarios` list;
- unique, non-empty scenario names and prompts;
- a Boolean `expect_activation` value;
- a positive integer timeout in seconds;
- at least one supported assertion and one non-empty rubric item;
- the type-specific assertion fields (see the table below);
- a compilable regular expression for every `output_matches`,
  `output_not_matches`, `stdout_matches`, and `stderr_matches` value;
- optional `expect_tools`/`reject_tools` as lists of non-empty strings and
  optional `max_turns`/`max_tokens` as positive integers;
- no unknown fields, so misspelled schema keys fail validation.

`setup.files` entries require `path` and exactly one of `source` or `content`.
`path` is the destination relative to the isolated scenario workspace;
`content` is written inline, while `source` names a file relative to the
manifest directory that is copied to the destination. Absolute paths and paths
that escape the workspace or manifest directory are rejected. The workspace is
deleted after each scenario, including failed runs.

### Setup execution

Setup now runs before the agent, in this order, inside the isolated workspace:

- `copy_test_files: true` copies every file that sits alongside `eval.yaml`
  (recursively, except `eval.yaml` itself) into the workspace, preserving each
  file's relative path. Use it when fixtures live next to the manifest.
- `files` entries are then written (inline `content` or copied `source`), so an
  explicit `files` entry can overwrite a copied fixture.
- `commands` are run last, each with `shell=True`, `cwd` set to the workspace,
  and a 120-second timeout. A non-zero exit (or a timeout) fails scenario
  setup with an explicit error and the scenario is reported as an error. The
  commands are sandboxed to the workspace directory only by `cwd`; they run
  with the invoking user's privileges, so keep manifests trusted.

`expect_activation` describes whether the target skill should activate. Every
evaluated skill should include both positive scenarios and at least one
anti-trigger whose prompt belongs to a sibling skill. Assertions and rubric
still describe the correct response for an anti-trigger; activation alone is
not a quality score.

This runner does not install a plugin into Codex or another agent. It supplies
the target `SKILL.md` content directly in the prompt as context in deterministic
assertion mode, then evaluates the resulting output and workspace. This is
useful for output and behavior evaluation, but it is not equivalent to a real
plugin activation test. `expect_activation` is currently
retained only as routing metadata and is reported as "not measured". It is
never counted as a passed activation check.

## Validate manifests and inspect coverage

Install PyYAML if the environment does not already provide it:

```bash
python3 -m pip install PyYAML
```

Run the existing marketplace validation and the independent eval validation:

```bash
python3 eng/validate.py
python3 eng/test_validate_evals.py
python3 eng/validate_evals.py
```

`validate_evals.py` exits non-zero for malformed or misplaced manifests, and
for any skill missing an eval. Its report includes the evaluated skill count,
total skill count, scenario count, and every skill still missing an eval.

## Run evaluations

List all validated scenarios without running an agent:

```bash
python3 eng/run_evals.py --list
```

Run every scenario through the deterministic mock backend:

```bash
python3 eng/run_evals.py --run
```

The mock backend echoes the assembled prompt and makes no external calls. This
exercises discovery, skill-context assembly, workspace setup, assertion
evaluation, reporting, and cleanup. It is deterministic, but it is not expected
to pass scenarios that require the agent to create files. `--dry-run` is an
explicit alias for this mock execution mode.

Select a skill, a scenario name, or a fully qualified scenario identifier:

```bash
python3 eng/run_evals.py --run --skill abp-data-access/ef-core-integration
python3 eng/run_evals.py --run \
  --scenario "Keep a custom EF Core repository in the infrastructure layer"
python3 eng/run_evals.py --run \
  --scenario "abp-data-access/ef-core-integration::Keep a custom EF Core repository in the infrastructure layer"
```

Run a real Codex agent only by selecting it explicitly:

```bash
python3 eng/run_evals.py --run --backend codex \
  --scenario "abp-data-access/ef-core-integration::Keep a custom EF Core repository in the infrastructure layer"
```

The Codex backend invokes `codex exec --ephemeral` with a workspace-write
sandbox, passes the scenario timeout to the process, captures standard output,
and records created, modified, and deleted workspace paths. A missing command,
timeout, or non-zero exit is reported as a scenario error. The runner never
selects this backend implicitly, which prevents an accidental paid run of the
full suite.

Add `--judge` to a real-backend run to score the rubric. Each rubric criterion
causes one additional call to the same backend. The judge must begin its answer
with `YES` or `NO`; malformed or failed judge responses are marked unscored.
Without `--judge`, every result states `rubric not scored`. The mock backend
cannot be used as an LLM judge.

```bash
python3 eng/run_evals.py --run --backend codex --judge \
  --scenario "abp-data-access/ef-core-integration::Keep a custom EF Core repository in the infrastructure layer"
```

## Capability A/B experiments

Experiment mode is opt-in and runs exactly one selected scenario. It is never
started by `--run`, so normal deterministic and mock evaluations do not incur
extra Codex calls. A reproducible Codex run must name its model and artifact
label:

```bash
python3 eng/run_evals.py --experiment --backend codex \
  --model gpt-5.2-codex --runs 3 --label ef-core-20260712 \
  --scenario "abp-data-access/ef-core-integration::Keep a custom EF Core repository in the infrastructure layer"
```

Use the mock backend to exercise the orchestration without a Codex call:

```bash
python3 eng/run_evals.py --experiment --backend mock \
  --runs 1 --label mock-smoke \
  --scenario "abp-data-access/ef-core-integration::Keep a custom EF Core repository in the infrastructure layer"
```

The three arms use a fresh scenario workspace for every run:

- `baseline` includes only the scenario prompt and no skill content.
- `isolated` includes only the target skill's `SKILL.md`.
- `plugin` includes every `SKILL.md` in the target skill's plugin, allowing
  sibling skills to compete in the supplied context.

Each run compares baseline with isolated and baseline with plugin. The same
backend acts as the pairwise judge. Every comparison is judged twice: baseline
on the left first, then baseline on the right. A treatment is a win or loss
only when both judgments identify the same canonical winner. Position-sensitive,
`TIE`, malformed, and unavailable judge responses aggregate as ties. The mock
backend deliberately produces structured `unavailable` judge entries and ties;
its activation proxy is also `unavailable` because echoing injected context
would create a false positive. Mock results validate the pipeline but do not
measure answer quality or activation.

The default run count is three. `--label` controls the artifact filename; when
omitted with the mock backend, the runner uses a UTC timestamp. Results are
written to `eng/eval-results/<plugin>-<skill>-<label>.json` by default. Override
the directory with `--results-dir`. The JSON contains:

- schema version, label, scenario identifier and original prompt;
- backend name, explicit Codex model, and Codex execution configuration;
- every arm's output, changed files, and execution error for every run;
- both left/right judge responses, parsed verdicts, canonical winners, and the
  final win/lose/tie result;
- aggregate win/lose/tie counts for isolated and plugin;
- per-run and aggregate activation-proxy results.

The runner prints the same aggregate counts as a Markdown summary.

Activation in this mode is only an output proxy. For the plugin arm, the runner
reuses positive `output_contains` and `output_matches` assertions to check
whether target-skill-specific symbols or guidance appear in the answer. This is
not evidence that the agent selected or activated the target skill: prompt
injection exposes no skill-selection session events. True activation measurement
requires a harness that installs the real plugin and captures its session events;
this repository does not currently have that harness. The JSON
`activation_boundary`, each run's activation-proxy disclaimer, the Markdown
summary, and this section all state that boundary explicitly.

## Deterministic assertions

Assertions run in manifest order and each produces its own pass/fail result.
The required field per type is enforced by the validator:

| Type | Required fields | Semantics |
| ------ | ----------------- | ----------- |
| `output_contains` | `value` | Output contains `value` (Unicode-aware, case-insensitive substring). |
| `output_not_contains` | `value` | Output does NOT contain `value` (same matching). |
| `output_matches` | `pattern` | Output matches the regex (case-insensitive, multiline). |
| `output_not_matches` | `pattern` | Output does NOT match the regex. |
| `file_exists` | `path` | At least one workspace file matches the `path` glob. |
| `file_not_exists` | `path` | No workspace file matches the `path` glob. |
| `file_contains` | `path`, `value` | At least one file matching `path` contains `value` (exact substring). |
| `file_not_contains` | `path`, `value` | No file matching `path` contains `value`. |
| `exit_success` | `command` | `command` runs in the workspace and exits `0`. |
| `run_command_and_assert` | `command` (+ options) | See below. |

### Glob paths

`file_exists`, `file_not_exists`, `file_contains`, and `file_not_contains`
accept globs in `path`:

- a plain relative path (no `*`/`?`/`[`) matches that exact file;
- `*` and `?` match within a single path segment;
- `**` spans any number of segments (`src/**/Program.cs`, `**/*.cs`).

A `file_exists`/`file_contains` assertion passes when at least one file matches;
the `_not_` variants pass when none match. `file_contains` and
`file_not_contains` fail when no file matches the glob at all (there is nothing
to inspect). Absolute paths and patterns that escape the workspace (`..`) are
rejected with an explicit error.

### `run_command_and_assert` and `exit_success`

`exit_success` is shorthand for "run `command` in the workspace, pass iff it
exits `0`". `run_command_and_assert` runs `command` (`shell=True`, `cwd` =
workspace, 120-second timeout) and then applies every option that is present:

| Field | Default | Check |
| ------- | --------- | ------- |
| `command` | *(required)* | Command line to run in the workspace. |
| `exit_code` | `0` | Actual exit code must equal this. |
| `stdout_contains` | — | stdout contains the value (case-insensitive). |
| `stdout_matches` | — | stdout matches the regex (case-insensitive, multiline). |
| `stderr_contains` | — | stderr contains the value (case-insensitive). |
| `stderr_matches` | — | stderr matches the regex (case-insensitive, multiline). |

A timeout, a non-matching exit code, or any failed stdout/stderr check fails the
assertion. Commands run with the invoking user's privileges and are sandboxed to
the workspace only by `cwd`; keep manifests trusted.

The scenario's deterministic result passes only when every assertion passes.
When rubric scoring is requested, every rubric item must also return `YES`.
Runner exit code `0` means every selected scenario passed; assertion failures,
execution errors, and unscored requested rubric items produce a non-zero exit.

## Behavioral constraints (schema-only, not measured)

`expect_tools`, `reject_tools`, `max_turns`, and `max_tokens` are scenario
constraints accepted and validated by the schema. They are enforced **only when the agent backend reports structured
tool-call, turn, and token telemetry**. The current mock and Codex backends do
not emit that telemetry, so these constraints are **not measured**: the runner
prints each declared constraint with a `not measured` note (exactly like
`expect_activation`) and never counts it as a passed or failed check. They are
recorded now so manifests can declare intent, and a future backend that exposes
run metrics can enforce them without a schema change. Do not treat a green run
as evidence that a `reject_tools` or `max_turns` limit was honored.

## Remaining limitations

The deterministic core and Codex adapter are intentionally small. Future work
can add:

1. real plugin installation and independent activation evidence;
2. an agent backend that emits tool-call/turn/token telemetry so the
   `expect_tools`/`reject_tools`/`max_turns`/`max_tokens` constraints can be
   enforced instead of reported as "not measured";
3. additional agent adapters and reproducible model/configuration selection;
4. persistent raw results, retries, and aggregation;
5. a regex execution timeout if manifests later accept untrusted patterns
   (Python's `re` has no built-in match timeout);
6. stronger sandboxing for `setup.commands` and `run_command_and_assert` than
   `cwd` isolation (e.g. containers or seccomp) if manifests become untrusted;
7. an isolated read-only judge view instead of relying on the judge instruction
   not to modify the scenario workspace.

## Coverage

Coverage changes as manifests are added. `python3 eng/validate_evals.py` is the
source of truth for the evaluated skill count and scenario count.
