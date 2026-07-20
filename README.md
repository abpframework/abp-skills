# ABP Agent Skills

A curated set of [ABP](https://abp.io) agent skills, distributed as versioned plugins
for AI coding tools. One set of skill content, published to Claude Code, Codex CLI,
Cursor, and VS Code through per-tool marketplace manifests.

## Plugins

| Plugin | What it covers |
| --- | --- |
| `abp-cli` | ABP CLI and ABP Studio CLI: choosing a solution architecture, creating solutions, updating packages, installing client libs, generating proxies. |
| `abp-module-development` | Modules, DDD aggregates, application services, DTOs, validation & errors, object mapping, module customization, localization. |
| `abp-data-access` | EF Core / MongoDB / Dapper, units of work, data filters, concurrency, connection strings, migrations, seeding. |
| `abp-authorization` | Permission definitions, authorization checks, current user, resource-based authorization. |
| `abp-authentication` | OpenIddict server/validation configuration, tokens, dynamic claims. |
| `abp-multitenancy` | Tenant-aware entities, current tenant, tenant resolution, per-tenant databases, data isolation. |
| `abp-api` | Conventional/auto controllers, integration services, dynamic & static C# client proxies, API versioning, Swagger/OpenAPI, CORS. |
| `abp-ui` | Blazor, Angular, MVC/Razor: pages, lists & forms, module UI extensions, menus, theming, localization, bundling, browser JS API consumption. |
| `abp-infrastructure` | Configuration, logging, JSON serialization, GUIDs, date/time, encryption, images, cancellation, correlation IDs, Autofac & interceptors, settings/features, audit logging, AI. |
| `abp-runtime` | Distributed/hybrid/entity caching, distributed locking, background jobs/events/workers, email/SMS/text-templating, production & cluster hosting, web security, app URLs. |
| `abp-files` | BLOB storing containers and providers, virtual file system. |
| `abp-realtime` | SignalR hubs, automatic hub routes, authorization, clients. |
| `abp-microservices` | Integration services vs distributed events, outbox/inbox, Dapr integration. |
| `abp-testing` | Integration and UI test infrastructure, test data seeding, authorization and multi-tenant test scenarios. |
| `abp-upgrade` | Upgrading ABP across versions: the abp CLI update flow, migration guides, breaking changes. |

## Scope

These skills cover **ABP Framework development** — modules and DDD/module
architecture, data access, APIs, authorization/authentication, multi-tenancy, UI,
and testing — building and extending modules through the framework's extension points.

## Compatibility

Content is API-reviewed against the ABP `rel-10.6` source; the compile-smoke tests pin
the latest stable NuGet, **ABP 10.5.0**. Each plugin's compile-tested ABP version:

| Plugin | Version | Compile-tested ABP |
| --- | --- | --- |
| `abp-cli` | 1.0.0 | 10.5.0 |
| `abp-module-development` | 1.0.0 | 10.5.0 |
| `abp-data-access` | 1.0.0 | 10.5.0 |
| `abp-authorization` | 1.0.0 | 10.5.0 |
| `abp-authentication` | 1.0.0 | 10.5.0 |
| `abp-multitenancy` | 1.0.0 | 10.5.0 |
| `abp-api` | 1.0.0 | 10.5.0 |
| `abp-ui` | 1.0.0 | 10.5.0 |
| `abp-infrastructure` | 1.0.0 | 10.5.0 |
| `abp-runtime` | 1.0.0 | 10.5.0 |
| `abp-files` | 1.0.0 | 10.5.0 |
| `abp-realtime` | 1.0.0 | 10.5.0 |
| `abp-microservices` | 1.0.0 | 10.5.0 |
| `abp-testing` | 1.0.0 | 10.5.0 |
| `abp-upgrade` | 1.0.0 | 10.5.0 |

## Install

Install only the plugins for the areas you work in — each plugin is one domain
(see the table above). You don't need all of them; pick what fits your task and
add more later.

### Recommended profiles

Skills route to sibling skills across plugins (a `DO NOT USE FOR` may point at a
skill in another plugin). Those cross-plugin hand-offs only resolve when both
plugins are installed, so install by **profile** rather than one isolated plugin:

- **Backend core** — `abp-cli`, `abp-module-development`, `abp-data-access`,
  `abp-authorization`, `abp-api`, `abp-infrastructure`, `abp-runtime`, `abp-testing`.
- **Full-stack app** — Backend core **+** `abp-ui`, `abp-authentication`,
  `abp-multitenancy` (add `abp-files` / `abp-realtime` as needed).
- **Microservices** — Full-stack app **+** `abp-microservices` (and `abp-realtime`,
  `abp-runtime` for distributed concerns).
- **Everything** — all 15, if you'd rather not think about it. (On Codex, a full install can truncate the skill menu; a smaller profile is safer there.)

### Install everything at once

To pull in all 15 without repeating the install command, the repo ships
convenience scripts that add the marketplace and install every plugin in one go:

```bash
scripts/install-all-plugins.sh          # Claude Code
scripts/install-all-plugins-codex.sh    # Codex CLI
scripts/install-all-plugins.ps1         # Windows (PowerShell)
```

They default to the `abpframework/abp-skills` marketplace; override the source
with `ABP_SKILLS_REPO=owner/repo`. Restart the tool (or run `/reload-plugins` in
Claude Code) afterward to load the skills.

### Claude Code

```bash
/plugin marketplace add abpframework/abp-skills
/plugin install abp-cli@abp-agent-skills               # one plugin at a time
/plugin install abp-module-development@abp-agent-skills # add the domains you need
/reload-plugins
```

### Codex CLI (v0.121.0+)

```bash
codex plugin marketplace add abpframework/abp-skills
# then, inside Codex, open the plugin browser and install:
#   /plugins
# or install directly from the CLI:
codex plugin add abp-cli@abp-agent-skills
codex plugin marketplace upgrade abp-agent-skills   # refresh the snapshot later
```

### Cursor

Add this repository as a marketplace, then install the plugins you want:

1. Open **Browse Marketplace** and click **Add Marketplace → Import from GitHub**
   (*Add a marketplace from a repository*).
2. Paste the repo URL: `https://github.com/abpframework/abp-skills`
3. Back in **Customize**, install plugins from the **Abp Agent Skills** section
   (skills appear in chat as `/skill-name`, or set them to *Agent Decides*).

The marketplace is added to your Cursor account and reads
`.cursor-plugin/marketplace.json` from the repo — no separate publishing needed.

### VS Code / Copilot (Preview)

```jsonc
// settings.json
{
  "chat.plugins.enabled": true,
  "chat.plugins.marketplaces": ["abpframework/abp-skills"]
}
```

## Layout

```text
.claude-plugin/marketplace.json      # Claude Code marketplace manifest
.agents/plugins/marketplace.json     # Codex CLI marketplace manifest
.cursor-plugin/marketplace.json      # Cursor marketplace manifest
.github/plugin/marketplace.json      # VS Code / Copilot marketplace manifest
plugins/
  <plugin>/
    plugin.json                      # plugin manifest (Claude Code / Cursor)
    .codex-plugin/plugin.json        # plugin manifest (Codex)
    skills/<skill>/SKILL.md          # the skill (shared by all tools)
eng/validate.py                      # layout/manifest validator (run in CI)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) to add a plugin or a skill.

## Versioning

Each plugin carries a `version` in its `plugin.json`, and releases are tagged
(`v1.0.0`, ...). The tools install from the marketplace repo, so a team pins a
version by pointing the marketplace at a specific tag or commit instead of the
default branch, and rolls back by re-pointing at the previous tag and
reinstalling. Selecting a ref is done in each tool's marketplace configuration
(Claude Code, Codex, Cursor, VS Code) — there is no per-plugin version flag on
the `install` command itself.

## Evaluations

Each skill ships eval scenarios under `tests/<plugin>/<skill>/eval.yaml` (positive +
anti-trigger routing cases) that check response shape and sibling routing. See
[eng/EVAL.md](eng/EVAL.md) for harness details.

## Do the skills help?

A **preliminary internal evaluation** (`eng/experiment/`) checks whether loading a
`SKILL.md` moves a model's generated code toward ABP idiom. It is a single-shot A/B
generation, 3 runs/arm, scored by lexical markers — not a generalizable benchmark. In
that run, open models (`glm-4.7`, `glm-4.7-flash`) shifted on ~86–88% of the measured
skills, while frontier models (`gpt-5.6-sol`, `opus-4.8`) mostly already wrote the idiom
(the skill acts as a guardrail). Method, models, dates, and caveats:
[eng/experiment/effectiveness-matrix.md](eng/experiment/effectiveness-matrix.md).
