# Contributing

## Add a skill to an existing plugin

1. Create `plugins/<plugin>/skills/<skill-name>/SKILL.md`.
2. Start the file with front matter:

   ```md
   ---
   name: <skill-name>
   description: <when an agent should use this skill — concrete trigger conditions>
   license: MIT
   ---

   # Title

   Concise, accurate guidance...
   ```

   Allowed front matter fields are exactly `name`, `description`, and `license`.
   Keep skill **prose** version-agnostic — do not pin a specific ABP version
   (a release-branch name or an `x.y.z` number) as if the guidance only holds for
   that version. Two deliberate exceptions: (a) a **doc/source reference URL** may
   carry a version ref so it resolves to a stable page — link to
   `https://github.com/abpframework/abp/blob/<rel-x.y>/…` rather than a bare repo
   path (bump the ref when the baseline moves); (b) an API that only exists from a
   specific version **may** be annotated (e.g. "available in ABP 10.6+") so readers
   on an older release don't copy it blindly.

3. Keep skills focused. Prefer one clear task per skill. Ground every API,
   command, and class name in real ABP behavior — do not invent signatures.
   Verify against the latest stable ABP release branch (an internal QA step;
   don't write the version into the skill).

## Skill quality standards

- **Fill a real capability gap.** A skill should teach something a strong base
  model gets wrong or doesn't know — ABP-specific APIs, conventions, and pitfalls
  — not restate general C#/.NET knowledge the model already has. If the baseline
  answer is already correct, the skill adds noise.
- **The `description` is the only thing seen at routing time.** Make it carry the
  outcome, the concrete trigger conditions (`USE FOR:`), and the non-applicable
  boundary (`DO NOT USE FOR:` routing to sibling skills). A vague description means
  the skill won't activate when it should, or activates when it shouldn't.
- **Keep `SKILL.md` scannable — aim for ≤ 500 lines.** When it grows past that,
  use progressive disclosure: keep the high-signal workflow in `SKILL.md` and move
  long reference material to a `references/` file the skill links to.
- **Lead with the essentials**: outcome, when to use, how to validate. A
  Purpose / Workflow / Validation / Common Pitfalls shape works well.
- **Every external dependency needs an unprivileged verification path** — a way
  to confirm the guidance without running untrusted code. No `http://` links,
  no `curl | bash`, no external `<script>` without SRI (the validator enforces
  this). New external domains must be added to `eng/allowed-domains.txt`.
- **Every skill ships an eval** (`tests/<plugin>/<skill>/eval.yaml`) with at
  least one positive and one anti-trigger scenario; update it whenever the
  skill's behavior changes. A C#-surface skill also gets a `eng/compat/Skills/*.cs`
  compile-smoke (or a `eng/compat/coverage-exemptions.yaml` entry).

## Add a new plugin

1. Create `plugins/<plugin>/`.
2. Add `plugins/<plugin>/plugin.json`:

   ```json
   {
     "name": "<plugin>",
     "version": "0.1.0",
     "description": "<one line>",
     "skills": ["./skills/"]
   }
   ```

3. Add `plugins/<plugin>/.codex-plugin/plugin.json` (Codex reads this one). The
   shared fields (`name`, `version`, `description`, `skills`) must match
   `plugin.json`; Codex may add tool-specific fields (`author`, `interface`), and
   `eng/validate.py` only checks the shared fields agree.
4. Register the plugin in all four marketplace manifests, keeping the shared
   entry fields consistent across them:
   - `.claude-plugin/marketplace.json` (Claude Code)
   - `.agents/plugins/marketplace.json` (Codex)
   - `.cursor-plugin/marketplace.json` (Cursor)
   - `.github/plugin/marketplace.json` (VS Code / Copilot)
5. Add a row to the plugin table in `README.md`.
6. Run `python3 eng/validate.py` and make sure it passes.

## Add skill evaluations

Add scenarios at `tests/<plugin>/<skill>/eval.yaml`, then run
`python3 eng/validate_evals.py`. **Every skill must have an eval** — a skill
without one fails validation. Each eval needs at least one positive and one
anti-trigger scenario. See [eng/EVAL.md](eng/EVAL.md) for the schema,
anti-trigger guidance, coverage report, and runner status.

## Release

All plugins release in **lockstep** — one suite version. Bump **every**
`plugins/*/plugin.json` (and its `.codex-plugin/plugin.json`) to the same new `X.Y.Z`,
commit, then tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The release workflow publishes a GitHub Release for the tag. See
[RELEASING.md](RELEASING.md) for the full checklist.
