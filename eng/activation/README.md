# Four-tool activation matrix

The eval suite injects a `SKILL.md` into the prompt and checks the response shape —
it does **not** test whether a tool's router *discovers and selects* the right skill
from its `description`. That routing is the product's core runtime behavior, and it
can only be observed by installing the plugins into the real tools and probing them.
This directory makes that a repeatable, recorded procedure instead of an ad-hoc one.

## What's automated vs manual

- **Probe set** (`generate_probes.py`): turns the eval scenarios into `probes.yaml` —
  one positive (`activate`) and one anti-trigger (`not-activate`) per skill, using the
  exact eval prompts. Regenerate whenever evals change.
- **Claude Code + Codex are automated** (`run_claude_probes.py`, `run_codex_probes.py`):
  both are CLI, and both leak which skill the router picked into an event stream, so the
  observation is scripted, not a human reading an indicator:
  - Claude Code — the first `Skill` tool_use in `claude -p --output-format stream-json`.
  - Codex — the first `command_execution` that reads `.../skills/<skill>/SKILL.md`
    (Codex loads a skill by cat-ing its `SKILL.md`).
  Recorded results live in `results.md`; raw per-probe output in `claude-probes.json` /
  `codex-probes.json`.
- **Cursor + VS Code stay manual** (GUI, no event stream): install, run the probes, and
  read the tool's skill-use indicator by hand. Record in `results.md` (template below).

## Install (per tool)

The marketplace repo is `abpframework/abp-skills`. `scripts/install-all-plugins*.sh`
install everything; for the matrix, install **by profile** (see the README
"Recommended profiles").

- **Claude Code**: `/plugin marketplace add <owner>/<repo>` then
  `/plugin install <plugin>@abp-agent-skills` for each plugin in the profile, `/reload-plugins`.
- **Codex CLI**: `codex plugin marketplace add <owner>/<repo>`; `codex plugin add <plugin>@abp-agent-skills`.
- **Cursor**: marketplace panel, or import a local checkout to `~/.cursor/plugins/local/`.
- **VS Code / Copilot**: `settings.json` → `chat.plugins.marketplaces: ["<owner>/<repo>"]`.

## Profiles to cover

Run the matrix for at least: **one single plugin**, the three README profiles
(Backend core / Full-stack / Microservices), and **Everything** (all 15). Isolated
installs surface the cross-plugin dead-hand-off risk; Everything surfaces
truncation/ordering at the ~56k-char full menu.

## Procedure (per tool × per profile)

For **Claude Code / Codex**, steps 2–4 are the driver scripts:

```bash
python3 eng/activation/run_claude_probes.py   # -> claude-probes.json
python3 eng/activation/run_codex_probes.py    # -> codex-probes.json
```

Then paste the printed summary into `results.md`. For **Cursor / VS Code**, do it by
hand:

1. Clean install of the profile from the (official) marketplace ref. Record tool
   version + the ref.
2. Confirm discovery: the tool lists the expected skill count for the profile.
3. Run each relevant probe from `probes.yaml`:
   - `activate` probe → the tool should select `expected_skill`. Pass if it does.
   - `not-activate` probe → it must **not** select `expected_skill` (it should route
     to the sibling the eval's rubric names, or handle generically). Pass if it doesn't.
4. Record per probe: activated skill (or none), pass/fail. Note any misfire.
5. Also record: uninstall + upgrade behaves (re-point at a newer tag, reinstall).

## Results template (copy to `results.md`, one block per tool)

```md
### <Tool> <version> — profile: <name> — ref: <owner>/<repo>@<tag> — date: <YYYY-MM-DD>

- Discovery: expected N skills, tool showed M.
- Positive probes: P/Q selected the expected skill.
- Anti-trigger probes: A/B correctly did NOT select the skill.
- Misfires (probe → activated instead):
  - "<prompt excerpt>" → activated <wrong-skill> (expected <right-skill>)
- Upgrade/uninstall: <ok / issue>
- Notes: <truncation, ordering, cross-plugin hand-off to an uninstalled plugin, etc.>
```

## Release bar

For an official `1.0.0`: every tool × the profiles above has a recorded block, with
positive-trigger and anti-trigger pass rates, cross-plugin hand-off behavior, and no
unexplained misfires — saved as a release artifact.

Status (see `results.md`): **Claude Code and Codex are recorded** at the Everything
profile (positive activation 73–78/79; anti-triggers route to the correct sibling
77–78/79, after fixing the three shared misfires — see `results.md`). **Not yet met**:
Cursor + VS Code (GUI, manual), and the smaller profiles (single plugin / Backend core /
Full-stack / Microservices). Until the full grid exists, the top-level README `Status`
must not claim a complete activation matrix.
