# Changelog

Notable changes to the ABP Agent Skills plugins. All plugins release in
**lockstep** — every plugin shares one suite version (`X.Y.Z`).

## 1.0.0

Initial release — 15 plugins / 80 skills covering ABP Framework development:

- **abp-cli** — abp / ABP Studio CLI: solution architecture, creating solutions,
  updating packages, installing client libraries, generating proxies.
- **abp-module-development** — modules, DDD aggregates, application services, DTOs,
  validation & errors, object mapping, module customization, localization,
  domain-vs-application logic.
- **abp-data-access** — EF Core / MongoDB / Dapper, units of work, data filters,
  concurrency, connection strings, migrations, seeding.
- **abp-authorization**, **abp-authentication** — permissions, current user,
  resource-based authorization, OpenIddict, tokens, dynamic claims.
- **abp-multitenancy**, **abp-api**, **abp-ui** — tenant isolation; auto controllers,
  client proxies, versioning, CORS; Blazor / Angular / MVC pages, lists & forms,
  theming, bundling.
- **abp-infrastructure**, **abp-runtime**, **abp-files**, **abp-realtime**,
  **abp-microservices** — configuration, logging, caching, locking, background
  work, email/SMS, hosting; BLOB storage; SignalR; integration events, outbox/inbox.
- **abp-testing**, **abp-upgrade** — integration/UI test infrastructure; the abp CLI
  update flow and migration guidance.

Content was source-reviewed against the ABP `rel-10.6` baseline; C# skills are
compile-smoked against ABP `10.5.0`, with runtime tests for behavior the
compile-smoke can't reach.
