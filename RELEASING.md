# Releasing

Cutting a release is gated by the automated checks **and** a manual activation
smoke that CI cannot run (it needs the four agent tools installed).

## 1. Automated gate (CI + local)

These run in `.github/workflows/validate.yml` on every push/PR and again in
`release.yml` before a tag produces a release. Run them locally first:

```bash
pip install -r requirements.txt
python3 eng/validate.py
python3 eng/validate_evals.py
python3 eng/verify_compat_coverage.py
python3 eng/check_version_annotations.py
python3 eng/verify_baselines.py
python3 -m unittest discover -s eng -p 'test_*.py'
dotnet build eng/compat/AbpSkillsCompat.slnx                            # stable baseline (10.5.0)
dotnet build eng/compat/AbpSkillsCompat.slnx -p:AbpVersion=10.6.0-rc.1 -p:AbpNext=true  # next ABP prerelease
dotnet test eng/runtime/AbpRuntimeTests.csproj                          # executable runtime behavior tests
cd eng/compat-ts && npm ci && npm ls @abp/ng.core @angular/core && npm run build && cd ../..
cd eng/compat-ts-extensible && npm ci && npm run build && cd ../..    # Angular-20 extension-API smoke
npx --yes markdownlint-cli2@0.23.0
actionlint                                                          # workflow lint (needs shellcheck on PATH)
shellcheck scripts/install-all-plugins.sh scripts/install-all-plugins-codex.sh   # installer lint
```

All must pass. `validate.yml` and `release.yml` run this **same** set (including
both the stable and next-ABP compile-smokes and the version-annotation check), so
the two gates stay equivalent. The release workflow also asserts the git tag
(`vX.Y.Z`) matches the `version` in every `plugins/*/plugin.json`.

## 2. Manual activation smoke (not automated)

The eval suite checks response **shape**, not live activation. Before tagging,
verify the marketplace actually installs and a skill activates in each target
tool. This is a spot check, not full coverage — pick 2–3 representative skills.

- **Claude Code**: `/plugin marketplace add <repo>`, install a plugin, `/reload-plugins`; prompt something the skill's `USE FOR` covers and confirm it activates; prompt an anti-trigger and confirm it does **not**.
- **Codex CLI**: `codex plugin marketplace add <repo>`, install a plugin; repeat the activate / anti-trigger check.
- **Cursor**: install from the marketplace panel (or local import); repeat.
- **VS Code / Copilot**: enable the marketplace in settings; repeat.

Record which tools/skills were checked in the release notes.

## 3. Tag

All plugins release in **lockstep** — one suite version. Bump **every**
`plugins/*/plugin.json` (and its `.codex-plugin/plugin.json`) to the same new
`X.Y.Z`, commit, then:

```bash
git tag vX.Y.Z   # must equal EVERY plugin's version
git push origin vX.Y.Z
```

The release workflow's "Verify tag matches plugin versions" step fails unless the
tag equals every plugin's version, so a partial bump won't publish. (Independent
per-plugin versions would need a different workflow; lockstep is the 1.0 model —
all skills track one ABP baseline.) The release workflow re-runs the full gate
before publishing.
