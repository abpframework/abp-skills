---
name: version-upgrade
description: >
  Upgrades an existing ABP solution through reviewable version hops using the classic Volo.Abp.Cli update implementation and the migration guides that apply to every crossed release.
  USE FOR: planning major or minor ABP upgrades, applying breaking changes, handling non-CPM and centrally managed package versions, running install-libs/proxy/DbMigrator follow-up work, validating each hop, and proving rollback before production rollout.
  DO NOT USE FOR: discovering the general ABP CLI command surface (use abp-cli-commands); creating a new solution (use abp-cli-commands); designing application integration tests (use test-abp-applications); or changing production unit-of-work behavior (use manage-units-of-work).
license: MIT
---

# Upgrade ABP Versions

The exact `update` behavior below is the classic `Volo.Abp.Cli` implementation. The current CLI documentation describes `Volo.Abp.Studio.Cli` as the default and says to append `--old` to invoke the classic CLI.

## When to Use

- Upgrade an existing ABP solution across one or more minor or major releases.
- Move NuGet and NPM packages to an exact stable, RC, or preview target (NuGet inline `Version` becomes exact; NPM keeps its existing `^`/`~` range unless you strip it yourself).
- Turn migration-guide entries into scoped code, package, database, UI, and test work.
- Recover from a partial upgrade without confusing a source rollback with a database rollback.

## When Not to Use

- **General CLI usage, solution creation, module installation, or proxy option discovery** — use **abp-cli-commands**.
- **A new application** — create it with **abp-cli-commands** instead of treating creation as an upgrade.
- **Application test architecture** — use **test-abp-applications** after this workflow identifies the regression coverage needed.
- **Production transaction configuration** — use **manage-units-of-work**; running the DbMigrator is an upgrade deployment step, not unit-of-work design.

## Workflow

### 1. Inventory before choosing a target

Record all version sources, not just one `PackageReference`:

```bash
dotnet tool list --global
find . -name '*.csproj' -o -name 'Directory.Packages.props' -o -name 'package.json'
git status --short
```

Inspect:

- inline `Version` attributes on `Volo.*` `PackageReference` items;
- `Volo.*` `PackageVersion` items in `Directory.Packages.props` when Central Package Management (CPM) is enabled;
- `@abp/*`, `@volo/*`, and `@volosoft/*` entries in `dependencies`, `devDependencies`, and `peerDependencies`;
- the installed CLI and SDK versions;
- every database and tenant connection that the solution's DbMigrator will touch.

Require a clean or explicitly reviewed working tree. Ask before creating a commit or tag. Before any database change, take a restorable backup or snapshot and record how to restore it.

### 2. Build an ordered hop plan

Read every migration guide after the current version through the target version. Do not read only the guide for the final major. The docs include both major guides (for example, a major-version boundary such as `N.x` to `(N+1).0`) and adjacent minor guides (each `x.y` to `x.y+1` step).

For example, a `<old>` to `<new>` plan that crosses a major boundary and then steps every minor looks like:

```text
x.3 -> (x+1).0 -> (x+1).1 -> ... -> (x+1).y   # cross the major, then every minor up to the target
```

For each hop:

1. Read that release's migration guide and its `package-version-changes.md` entries.
2. Mark each item as applicable or not applicable, with the affected project and validation.
3. Choose one exact package version for the hop, including the prerelease suffix when applicable.
4. When stepping hop by hop, complete the package update, manual changes, migrations, and validation for a hop before starting the next (a recommended discipline — see step 7 — not an ABP requirement).

Major guides can require a new .NET target framework or third-party major upgrade. Minor guides can still require schema migrations, proxy regeneration, HTTP changes, or dependency alignment; do not collapse them into one unreviewed jump.

### 3. Run the classic `update` command deliberately

Run from the solution root. Append `--old` when the installed `abp` command defaults to Studio CLI:

```bash
abp update -v <target-version> --old
```

Verified classic options:

| Option | Behavior |
| --- | --- |
| `-v`, `--version <version>` | Use an exact ABP target instead of resolving the latest version. |
| `-lv`, `--leptonx-version <version>` | With `--version`, override the LeptonX target. |
| `--nuget` | Run only the NuGet updater. |
| `--npm` | Run only the NPM updater. |
| `-sp`, `--solution-path <path>` | Use a directory other than the current directory. |
| `-sn`, `--solution-name <name>` | Skip solution auto-discovery and use the given value as the solution-path anchor; it is not combined with `-sp` into a `.sln` path. |
| `--check-all` | Resolve each package separately only when no exact `--version` is supplied. |

Do not use `-p` / `--include-previews` for this command. It appears in the classic usage text, but `UpdateCommand.ExecuteAsync` never reads it. Pin the complete prerelease version instead:

```bash
abp update -v <full-prerelease-version> --old
```

The command performs both NuGet and NPM updates unless one exclusive selector is supplied. If both `--nuget` and `--npm` are present, both paths run.

### 4. Review what `update` can and cannot change

For NuGet, the classic updater scans `*.csproj` files and selects `PackageReference` items whose `Include` starts with `Volo.`.

- A reference without an inline `Version` is logged as CPM-managed and skipped (the updater does not check `ManagePackageVersionsCentrally` or locate `Directory.Packages.props` — it just skips versionless references). Confirm the project actually uses CPM, find where that package's version is really declared, and update it yourself.
- With `--version`, `Volo.Abp.Studio.*` references are skipped with a warning and require separate manual alignment.
- With an exact ABP target, NuGet LeptonX packages use its compatible mapped version or the explicit `--leptonx-version` value. The NPM updater uses `--leptonx-version` only together with `--version`.
- An exact target is applied only when it exists for that package and is greater than the current semantic version. `abp update -v <older-version>` is not a downgrade or rollback command.
- An unparseable or unavailable version is skipped with a warning. Treat every warning as an unresolved package, not a successful upgrade.

For NPM, the updater scans `package.json` files for the three ABP scopes in dependencies, dev dependencies, and peer dependencies. When it changes a file, it runs `npx yarn --ignore-scripts`. It then runs `install-libs` automatically for non-Angular projects, but not for a directory containing `angular.json`.

`update` does not apply migration-guide code edits, create application EF Core migrations for changed entities, regenerate proxies, run the DbMigrator, or validate application behavior.

### 5. Apply the migration guide before deployment work

Implement only applicable guide items. Typical categories are:

- target framework and third-party dependency changes;
- renamed or changed APIs and interfaces;
- direct dependency versions listed in `package-version-changes.md`;
- EF Core schema changes that require a new application migration;
- generated proxy changes;
- UI framework and build-pipeline changes.

Create and review an EF Core migration when the guide or the application's model change requires one. Do not assume the DbMigrator invents that migration. Build immediately after the manual code changes so compiler failures stay attached to one hop.

### 6. Complete client and database follow-up work

#### Client libraries

If `update` changed a non-Angular `package.json`, the classic NPM updater already runs Yarn and `install-libs`. Run `abp install-libs` explicitly when dependencies were changed outside that path, its automatic execution failed, or `wwwroot/libs` must be rebuilt:

```bash
abp install-libs --working-directory <web-project-directory> --old
```

`install-libs` searches the given directory recursively (`SearchOption.AllDirectories`), so you can run it from the solution root. To rebuild `wwwroot/libs` it needs a Web/Razor/Blazor `*.csproj` in range and an `abp.resourcemapping.js` (also found recursively under the project); it reads that mapping and copies resources from `node_modules` to `wwwroot/libs`. For Angular, restore packages and run the Angular build/test workflow instead.

#### Generated proxies

Regenerate only the client types and modules the migration guide or API changes affect. Start the host first because proxy generation reads the live API definition:

```bash
abp generate-proxy -t ng -u <host-url> --old
abp generate-proxy -t js -u <host-url> --old
abp generate-proxy -t csharp -u <host-url> --old
```

Review generated diffs. A migration guide can explicitly require proxy regeneration for upload/content-type changes and recommend regenerating Angular proxies after an Angular major upgrade.

#### Database migration and seeding

After creating/reviewing required migrations and backing up the database, build and run the solution's DbMigrator:

```bash
dotnet build
dotnet run --project <path-to-DbMigrator.csproj>
```

The application template's DbMigrator calls the schema migrators and then `IDataSeeder` for the host and tenants. The EF Core schema migrator calls `Database.MigrateAsync`. Running it applies existing migrations and seed contributors; it is not a substitute for creating the migration your application needs.

### 7. Gate every hop

Reading each crossed version's migration guide is required (the guides are written per adjacent version). Physically installing and validating every intermediate version, and running a rollback drill per hop, is **not** mandated by ABP or the CLI — `abp update` can jump straight to the target. It is a recommended, conservative discipline for large or high-risk upgrades. When you follow it, don't start the next hop until all applicable checks pass:

- Review the full diff, including lock files, generated proxies, migrations, and client assets.
- Confirm every skipped/warned package was intentionally handled.
- Restore dependencies, build the complete solution, and run unit/integration tests.
- Run UI builds and tests for each included UI technology.
- Run the DbMigrator against a disposable or staging copy of the database, then run it a second time to catch non-idempotent migration or seed behavior.
- Start every deployable application and smoke-test authentication, authorization, tenant boundaries, critical writes, background processing, and changed guide-specific flows.
- Check runtime logs for package-load, DI, database, serialization, route, and proxy failures.

When a crossed guide flags them, include upload proxy flows, custom background job stores/options, Angular applications on a new Angular major, mixed SPA/MVC antiforgery flows, client-credential token forwarding, and code that treated a missing thread principal as `null` when those scenarios exist.

### 8. Prove rollback separately

Do not use `abp update -v <old-version>` as rollback; both NuGet and NPM exact-version paths reject a target that is not greater than the current version.

When you choose to run a rollback drill (part of the recommended discipline, not required), do it in a disposable environment:

1. Restore source, generated files, package manifests, and lock files from the recorded pre-hop revision without rewriting unrelated work.
2. Restore every changed database from the pre-hop backup. Do not assume reversing an EF migration also reverses seed data or destructive schema changes.
3. Restore the previous deployment artifacts and configuration.
4. Start the previous version and repeat the critical smoke tests.
5. Record the restore duration and any manual step before approving the production rollout.

Never perform a destructive reset, database restore, commit, tag, or deployment without explicit user authorization.

## Validation

- [ ] Current NuGet, CPM, NPM, CLI, SDK, UI, and database versions are inventoried.
- [ ] Every crossed major and minor migration guide is in the ordered hop plan.
- [ ] Each guide item has applicability, an owner/project, and a validation check.
- [ ] The exact target exists and all updater warnings/skips are resolved.
- [ ] CPM, Studio, LeptonX, and direct third-party package versions are reviewed separately.
- [ ] Required manual code changes and EF Core migrations are created and reviewed.
- [ ] Client dependencies/assets and affected proxies are regenerated through the correct path.
- [ ] Build, tests, UI checks, DbMigrator rerun, startup, and scenario smoke tests pass.
- [ ] The previous source and databases can be restored and the old version starts successfully.
- [ ] (Recommended) the next hop begins only after the current hop — and, if you run one, its rollback drill — passes.

## Common Pitfalls

- **Treating `abp update` as a migration engine.** It updates package declarations and NPM artifacts; migration-guide code, schema, proxy, and behavior changes remain manual work.
- **Reading only the final major guide.** Adjacent minor guides have required actions; include every crossed release.
- **Trying to downgrade with `--version`.** Exact-version NuGet and NPM updates only move to a greater semantic version.
- **Missing CPM packages.** Inline versionless `Volo.*` references are skipped (the updater doesn't check whether CPM is enabled). Confirm the project actually uses CPM, find where the version is really declared (usually `Directory.Packages.props`), update it, and verify restore/build output.
- **Ignoring warnings.** Missing target versions, unparseable versions, Studio packages, and unmapped LeptonX versions can all be skipped.
- **Combining `--check-all` with `--version`.** The per-package `check-all` path is selected only when no exact target is provided.
- **Using `-p` for a preview.** The execution path does not consume it; pin the full preview/RC version.
- **Expecting `install-libs` to rebuild `wwwroot/libs` with no eligible project in range.** It searches recursively from the given directory, but only a Web/Razor/Blazor `*.csproj` with an `abp.resourcemapping.js` triggers the copy.
- **Regenerating proxies while the host is stopped.** The generator requires the live API definition.
- **Running DbMigrator before creating or reviewing the required migration and backup.** It applies available migrations and seed data to host/tenant databases.
- **Rolling back code but not data.** Source restoration does not undo schema or seed changes; prove database restore independently.
