# Compile-smoke tests

These projects pin a specific ABP release and exercise the ABP APIs each skill
relies on. They are **compile-only** checks — the snippets never run.

If the pinned ABP version removed, renamed, or changed the signature of an API a
skill teaches, this project **fails to compile** and the error names the exact
file (skill) and symbol. That is how we learn a skill went stale for a new ABP
release.

## Layout

- `Directory.Build.props` — applies `net10.0`, nullable analysis, disabled
  implicit usings, and the `CS0618` error policy to every child project.
- `Directory.Packages.props` — pins `<AbpVersion>` and the `Volo.Abp.*` package
  versions. This version is the "compile-tested ABP" value in the root README's
  compatibility table.
- `AbpSkillsCompat.slnx` — builds all 71 skill projects in one command.
- `Projects/<Skill>/<Skill>.csproj` — one project per C# skill. Each project
  compiles one matching snippet and directly references only the packages that
  own the ABP APIs exercised by that snippet.
- `generate-projects.py` — regenerates the 71 projects and solution from the
  checked source-to-package map.
- `Skills/<Skill>.cs` — one file per compile-checkable skill. Each references the
  types and calls the methods that skill documents. Projects link these files so
  the test points remain centralized and unchanged.

The 71 C# snippets each have an isolated project. This prevents one skill's
package references from satisfying another skill's undeclared dependencies.
Plugins without a C# surface (`abp-cli` and `abp-upgrade`) have no project.

The JavaScript/TypeScript UI surface is covered separately by `eng/compat-ts/`.
Angular is active in the default TypeScript build. React checks and the
generated-app React Native scaffold are documented there.

`<WarningsAsErrors>` promotes `CS0618` to an error, so an API a skill still
teaches after ABP marks it `[Obsolete]` also fails the build (not just a silent
warning).

## What this does NOT catch

Compile-checking proves an API *exists with a compatible signature* in the
pinned version. It is a first alarm, not full coverage. It cannot see:

- **Behavioral / runtime changes** — DI auto-registration, `[DependsOn]` module
  wiring, interceptor activation, provider fallback order, default transaction
  behavior, tenant filtering, cache serialization. The snippets compile but
  never run.
- **Value changes that keep the type** — an optional parameter's default flipping
  (`hideErrors: true`→`false`), an enum's numeric value, a string constant
  (`AbpClaimTypes.TenantId`), or a route convention.
- **Attribute semantics** — `[Authorize]`, `[RequiresFeature]`, `[UnitOfWork]`
  still compile even if their runtime rules change.
- **Overloads not referenced** — only the specific overload a snippet calls is
  checked; a sibling overload's signature change is invisible.
- **Runtime module wiring** — a package reference proves package ownership, but
  does not prove the application's `[DependsOn]` graph initializes the module.
- **Razor/HTML, JSON localization, CLI** — outside a C# compile.

These gaps are the job of the `tests/**/eval.yaml` scenarios and manual review,
not this project.

## Run

```bash
dotnet build eng/compat/AbpSkillsCompat.slnx
cd compat-ts
npm ci
npm run build
```

Green = the core ABP APIs each smoke references exist in the pinned version (the
smokes are representative, not an exhaustive copy of every symbol the prose names). A
build error pinpoints the stale skill and symbol.

## Security advisories on test-graph packages

`dotnet restore` may report `NU1901`–`NU1904` audit warnings for transitive
packages in the compile-smoke / runtime-test graph (e.g. `AutoMapper`,
`Scriban`, `SQLitePCLRaw`, `MailKit`/`MimeKit`, `AWSSDK.Core`). These packages
exist **only to type-check and boot the tests** — nothing here is published to
users; the plugins ship as Markdown. So an advisory here is not a plugin-runtime
vulnerability.

Policy: bump `<AbpVersion>` (which pulls newer transitives) to clear what it can,
and treat any residual advisory as a test-only note, not a release blocker. The
build does not set `<NuGetAudit>false>`, so new advisories stay visible in CI
logs rather than being silenced.

## Testing a new ABP release

1. Bump `<AbpVersion>` in `Directory.Packages.props` to the new release.
2. `dotnet build eng/compat/AbpSkillsCompat.slnx`.
3. Fix each reported skill (or note it requires a newer ABP) until green.
4. Update the compatibility table in the root `README.md` and cut a release.
