---
name: choose-solution-architecture
description: "Decide which ABP solution architecture and template to create before running abp new. USE FOR: choosing between single-layer (app-nolayers), layered (app), modular monolith, and microservice; modern vs classic templates; tiered vs non-tiered; how UI / database / auth-server / license affect template availability; reserving Contracts + integration services + distributed events so a modular monolith can later split into microservices; then routing to abp-cli-commands for the actual command. DO NOT USE FOR: the abp new command syntax, template names, and parameters (abp-cli-commands); DDD project layers and dependency direction within a solution (layered-architecture); designing module/service communication once boundaries exist (design-module-and-service-communication); upgrading an existing solution (version-upgrade)."
license: MIT
---

# Choose an ABP Solution Architecture

The first decision — *what shape of solution to create* — is the one that's cheapest to get right up front and expensive to change later. This skill helps pick the architecture, template, and key options **before** `abp new`; once you've decided, the **abp-cli-commands** skill has the exact command and parameters.

## When to Use

- Starting a new ABP solution and deciding single-layer vs layered vs modular monolith vs microservice.
- Choosing the modern vs classic template, tiered vs non-tiered, UI, and database provider up front.
- Setting up a modular monolith so it can later split into microservices with minimal rework.

## When Not to Use

- **The `abp new` command, template names, and parameter syntax** — use the **abp-cli-commands** skill (this skill decides *what* to create; that one runs it).
- **DDD project layers and dependency direction** inside a solution — use the **layered-architecture** skill.
- **Designing communication** between modules/services once the boundaries exist — use the **design-module-and-service-communication** skill.
- **Upgrading or restructuring an existing solution** — use the **version-upgrade** skill.

## Decision 1 — solution shape

| Shape | Template | Fits when | Cost |
| --- | --- | --- | --- |
| **Single-layer** | `app-nolayers` | Small apps, prototypes, internal tools; one project, minimal ceremony. | Refactoring to layers later is manual. |
| **Layered** | `app` | Most business apps; DDD layering (Domain / Application / HttpApi / UI). The default. | More projects than a single-layer app. |
| **Modular monolith** | `app` **+ modules** | You want strong internal boundaries and a likely future split, but one deployable. Built on the layered template by adding modules (each with its own layers + Contracts). | Discipline to keep modules decoupled. |
| **Microservice** | `microservice` | Independent deploy/scale per service, separate teams/databases, gateway. | Highest operational complexity — don't start here without the need. |

Prefer the **simplest shape that meets the requirement**. A **modular monolith is the usual sweet spot** when microservices are a *maybe*: you get boundaries now and a lower-friction split later (see below), without day-one distributed-systems cost.

## Decision 2 — modern vs classic template

- **Modern** (`--modern`) — React-first templates shipped with ABP Studio; choose it when the UI is **React**, or you want the newer template system.
- **Classic** (default) — MVC/Angular/Blazor via the established templates. `console` / `wpf` exist only in the **classic CLI** (`--old`).

The UI framework and `--modern` interact: `react` is available **only** with `--modern`. Confirm the current matrix with `abp new --help` (see **abp-cli-commands**).

## Decision 3 — tiered vs non-tiered

- **Non-tiered** (default) — the UI/host and the API run in one process. Simpler; fine for most apps.
- **Tiered** — the API host and the web/auth server run as separate deployables (separate processes/servers). Choose it for independent scaling of the API vs the UI, or a separate auth server. It adds hosting and CORS/redirect configuration.

## Decision 4 — options that constrain the template

- **UI framework** — MVC, Angular, Blazor (Server/WebApp/WASM), React (modern only), MAUI/React Native for mobile.
- **Database provider** — EF Core (default; pick the DBMS) or MongoDB. Some features assume relational.
- **Separate auth server / public website / multi-tenancy** — template options that affect the solution shape; enable them when your app needs them.

## Design a modular monolith so it can split later

If microservices are a *future maybe*, build a modular monolith now but keep the seams a microservice split will need — that keeps stable contracts and reduces the business-logic rewrite, but the split still needs real work: remote authentication, network failures/timeouts, data consistency across services, observability, and data/deployment migration:

- Give each module its own **Application.Contracts** (integration-service interfaces + DTOs) that other modules reference — never share entities or a module's internal projects.
- Use **integration services** for cross-module queries and the **distributed event bus** for cross-module notifications (both run in-process in a monolith and swap to a broker/remote transport when split) — see **design-module-and-service-communication**.
- Keep **per-module database ownership**: a module owns its tables/schema; other modules reach its data only through its Contracts, not by joining its tables.

## Then create it

Once the shape, template, and options are chosen, run the actual command with the **abp-cli-commands** skill — it has the Studio-vs-classic parameters, template names, and license/login flow. Don't copy CLI parameter lists here; decide here, create there.

## Common Pitfalls

- **Starting with microservices "to be safe"** — you pay distributed-systems cost from day one. A modular monolith gives boundaries with a cheap later split.
- **Assuming a shape is easy to change later** — single-layer → layered and monolith → microservice are real refactors; choose deliberately.
- **Picking a UI/option the template doesn't support** — e.g. `react` without `--modern`. Verify with `abp new --help`.
- **Sharing entities or internal projects between modules** in a monolith — it destroys the boundary and blocks a future split; share only Contracts.
