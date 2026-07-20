---
name: abp-cli-commands
description: >
  Command-line workflow for the ABP Framework abp CLI — creating/scaffolding solutions, updating packages, installing client libs, generating proxies, adding packages/modules, bundling Blazor WASM, logging into abp.io, and switching to local ABP source.
  USE FOR: running `abp new`, `abp update`, `abp install-libs`, `abp generate-proxy`, `abp add-package`, `abp add-module`, `abp bundle`, `abp login`/`logout`, `abp switch-to-local`; choosing between the classic and ABP Studio CLIs; resolving the "Libs folder is missing" error.
  DO NOT USE FOR: upgrading an existing solution across a minor/major version and aligning package versions (use version-upgrade); using the CLI-created solution structure itself (use layered-architecture); consuming the generated Angular proxy services in components (use angular-ui).
license: MIT
---

# ABP CLI Commands

Command-line workflow for ABP Framework (abp.io) development. Install once:

```bash
dotnet tool install -g Volo.Abp.Studio.Cli   # newer, recommended (the default `abp`)
abp install-old-cli                           # optional: install the classic CLI for `--old` commands
```

`Volo.Abp.Studio.Cli` is the default `abp`, and the commands in this skill are the Studio CLI's unless marked `--old`. To run a classic `Volo.Abp.Cli` command, first install it once with `abp install-old-cli`, then append `--old` at the **end** of the command (e.g. `abp new Acme.BookStore -t console --old`).

## When to Use

- Creating or scaffolding a new ABP solution or reusable module.
- Installing `wwwroot/libs` client-side libraries or fixing a "Libs folder is missing" error.
- Generating strongly-typed client proxies (Angular/C#/JS) from a running HTTP API.
- Adding a single NuGet/NPM package or a whole ABP module to a solution.
- Bundling Blazor WASM global styles/scripts.
- Logging into abp.io, or switching a project to reference local ABP source.

## When Not to Use

- **Upgrading an existing solution across versions** and aligning `Volo.*` package numbers — use the **version-upgrade** skill (it wraps `abp update` with the migration-guide workflow).
- Understanding the generated solution layout — use **layered-architecture**.
- **Consuming the generated Angular proxy services** in components/pages — use the **angular-ui** skill (this skill generates them; angular-ui uses them).

## Two CLIs

- **ABP Studio CLI** (`Volo.Abp.Studio.Cli`) — the newer CLI that ships with ABP Studio; it is the recommended default and what `abp` resolves to. The commands and `abp new` parameters in this skill are the Studio CLI's unless marked `--old`.
- **Classic `abp` CLI** (`Volo.Abp.Cli`) — the long-standing tool. Install it once with `abp install-old-cli`, then reach it by appending `--old` at the end of a command. It still owns a few templates/commands the Studio CLI doesn't (e.g. `console` / `wpf`) and uses the older parameter names (`--ui`, `--skip-installing-libs`).

The two CLIs **do not share the exact same command set** — don't assume every command exists in both. They overlap on the core ones (`new`, `update`, `install-libs`, `generate-proxy`, `add-package`, `login`). Per the docs, the Studio CLI's documented command set includes the template/module commands (`new-module`, `install-module`, `add-package-ref`, `add-module-source`) **and** `switch-to-local` and `bundle` — so those are not classic-only. The classic CLI still has `add-module`. The exact per-CLI differences shift between versions (for example the older `agent` command may be replaced by `mcp` in a given version's table), so run `abp help` or `abp <command> --help` against your installed CLI — verify rather than assume. Append `--old` to run a classic-CLI command from the Studio CLI.

## Workflow

### `abp new` — create a solution

`abp new` runs the **ABP Studio CLI** template system by default. Add `--modern` for the React-first modern templates. To use the **classic** CLI instead, install it once with `abp install-old-cli` and append `--old` at the **end** of the command. Parameter names differ between the two — don't mix them.

```bash
abp new Acme.BookStore                          # default template (app), MVC UI
abp new Acme.BookStore -u angular               # Angular UI
abp new Acme.BookStore -u blazor -d mongodb     # Blazor UI + MongoDB
abp new Acme.BookStore -t microservice          # microservice template
abp new Acme.BookStore -u react --modern        # React UI (requires --modern)
abp new-module Acme.MyModule                    # reusable module (separate command, not `new -t module`)
```

**Studio CLI options** (the default; always confirm with `abp new --help` for your installed version):

- `-t|--template <name>` — `empty`, `app` (default), `app-nolayers`, or `microservice`. `console` / `wpf` are **classic-only** (see below), not Studio templates.
- `-u|--ui-framework <framework>` — `mvc` (default), `angular`, `blazor`, `blazor-webapp`, `blazor-server`, `no-ui`, `maui-blazor`, and `react` (the latter only with `--modern`). The long form is `--ui-framework` (the classic CLI's is `--ui`).
- `-d|--database-provider <provider>` — `ef` or `mongodb`.
- `-dbms|--database-management-system <system>` — `sqlserver`, `mysql`, `postgresql`, `oracle`, `sqlite`, etc.
- `-m|--mobile <framework>` — `none`, `react-native`, or `maui`.
- `--theme <name>` — defaults to `leptonx-lite`; `leptonx` is also available. Also `-o|--output-folder <path>`, `-cs|--connection-string <cs>`.
- `--dont-run-install-libs` / `--dont-run-bundling` — skip the automatic `abp install-libs` / `abp bundle` (these are the Studio names; the classic CLI uses `--skip-installing-libs` / `--skip-bundling`).
- `--modern` — use the modern (React-first) template source shipped with ABP Studio.
- `--local-framework-ref` / `-lfr` — reference a local ABP repo instead of NuGet packages.

**Classic CLI (`--old`)** — some templates (`console`, `wpf`) and the older parameter names live only in the classic CLI. Install it once, then put `--old` at the **end**:

```bash
abp install-old-cli                             # one-time: install the classic CLI
abp new Acme.MyConsoleApp -t console --old      # console template (classic-only)
abp new Acme.MyWpfApp -t wpf --old              # WPF template (classic-only)
```

The classic CLI uses `--ui`, `--skip-installing-libs`, `--skip-bundling`, `--separate-auth-server` and similar. Don't pass those to a Studio-CLI (non-`--old`) command — they won't be recognized.

### `abp update` — update ABP packages

Updates ABP NuGet and NPM packages in the solution to the latest matching versions.

```bash
abp update            # update all ABP packages
abp update --nuget    # only NuGet packages
abp update --npm      # only NPM packages
abp update -v <version>  # update to a specific version
```

Other options: `-sp|--solution-path`, `-sn|--solution-name`, `--check-all`, `-lv|--leptonx-version`.

### `abp install-libs` — install client-side libraries

Installs the NPM/`wwwroot/libs` client-side packages a web project needs (bootstrap, jQuery, etc.), driven by `abp.resourcemapping.js`.

```bash
cd Acme.BookStore.Web         # run in the web project folder
abp install-libs
# or point at a folder:
abp install-libs -wd ../Acme.BookStore.Web
```

### `abp generate-proxy` — generate client proxies

Generates strongly-typed client proxies from an HTTP API's `/api/abp/api-definition`. The HTTP API host must be running.

```bash
abp generate-proxy -t ng                                     # Angular services/models
abp generate-proxy -t csharp -url https://localhost:44302/   # C# HTTP client proxies
abp generate-proxy -t js -m identity -o Pages/Identity/client-proxies.js -url https://localhost:44302/
abp generate-proxy -t csharp --folder MyProxies/Inner --without-contracts -url https://localhost:44302/
```

- `-t <type>` — proxy type: `ng` (Angular), `csharp`, or `js` (JavaScript).
- `-m <module>` — target module (e.g. `identity`, `app`).
- `-url <url>` — API host URL; `-o <path>` output file; `--folder <path>` output folder.
- `--without-contracts` — for `-t csharp`, skip generating contract interfaces/DTOs.

Angular projects generated through NX (e.g. ng-packs workspaces) use the NX generator instead: `npx nx g @abp/nx.generators:generate-proxy`.

### `abp add-package` / `abp add-module`

`add-package` adds a single NuGet/NPM package (and wires up the `[DependsOn]` module):

```bash
abp add-package Volo.Abp.FluentValidation
abp add-package Volo.Abp.FluentValidation -p Acme.BookStore.Application
abp add-package @abp/ng.theme.basic          # NPM package
```

`add-module` adds a whole ABP module (multiple packages across layers) to the solution — run it in the folder containing the `.sln`/`.slnx`:

```bash
abp add-module Volo.Blogging
abp add-module Volo.Blogging -s Acme.BookStore
abp add-module ProductManagement --new -sp ../Acme.BookStore.Web/Acme.BookStore.Web.csproj  # create a fresh in-solution module
```

Useful flags: `--with-source-code`, `--new`, `-s|--solution`, `-sp|--startup-project`, `--skip-db-migrations`.

### `abp bundle` — bundle Blazor WASM resources

Regenerates the global styles/scripts bundle for a Blazor WebAssembly project (run in the Blazor project folder).

```bash
abp bundle
abp bundle -f              # force rebuild
abp bundle -wd ../MyProject.Blazor
```

### `abp login` / `abp logout`

Authenticates the abp CLI with your abp.io account, required to create/update solutions and modules that need an authenticated account.

```bash
abp login <username>                   # prompts for the password interactively (preferred)
abp login <username> -p <password>     # avoid: the password lands in shell history
abp login <username> --device          # device-code flow (needed with 2FA enabled)
abp logout
```

Prefer the interactive prompt (omit `-p`) or `--device`. Passing `-p <password>` records the password in shell history and process listings — don't use it in shared or CI environments.

With multiple organizations, pass `--organization <name>`.

### `abp switch-to-local` — reference local ABP source

Replaces `Volo.*` NuGet `PackageReference`s in a solution with `ProjectReference`s to a local ABP repo, so the app runs against your local source changes.

```bash
abp switch-to-local --paths <path-to-abp-source>
abp switch-to-local --paths "<path-to-abp-source>|<path-to-volo-source>"   # multiple repos
abp switch-to-local --paths <path-to-abp-source> --solution <path-to-solution>
```

`-p|--paths` is required (pipe-separated for multiple repos); `-s|--solution` defaults to the current directory.

## Validation

- Confirm the installed CLI and its version with `abp --version`; list its actual command set with `abp help` or `abp <command> --help` (the two CLIs differ — verify, don't assume).
- After `abp new` / `abp install-libs`, the web project should start without the "Libs folder is missing!" error page.
- After `abp generate-proxy`, the generated proxy files should appear at the `-o`/`--folder` target; diff them before committing.
- After `abp switch-to-local`, the solution's `Volo.*` references should be `ProjectReference`s pointing at your local repo (not NuGet `PackageReference`s).

## Common Pitfalls

- **"The Libs folder is missing!":** run `abp install-libs` in the web project. Do **not** work around it with `CheckLibs=false` — that only disables the check, leaving the libs actually missing. This happens after cloning a repo, or when a project was created with `--skip-installing-libs`.
- **Assuming a command exists in both CLIs, or is classic-only:** the classic and Studio CLIs differ, and the split shifts by version. The Studio CLI's command set includes `switch-to-local` and `bundle` (they are **not** classic-only) plus `new-module`/`install-module`; don't rely on a hard-coded per-CLI list — check with `abp help` and use `--old` to reach the classic CLI.
- **Running `generate-proxy` against a stopped API:** the HTTP API host must be running so the CLI can read `/api/abp/api-definition`.
- **Using `abp generate-proxy -t ng` in an NX workspace:** ng-packs-style workspaces use the NX generator (`npx nx g @abp/nx.generators:generate-proxy`) instead.
- **`new`/`update` without logging in:** creating/updating solutions and modules that need an authenticated account requires `abp login` first; use `--device` when 2FA is enabled.
