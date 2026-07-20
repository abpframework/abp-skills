---
name: separate-domain-and-application-logic
description: >
  Decide whether business logic belongs in the domain layer (entities, domain services) or the application layer (application services), per ABP's DDD guidance.
  USE FOR: judging a rule as core domain vs use-case (application) logic; keeping domain services free of authorization, current user/session and notifications; making the application service the unit-of-work boundary that authorizes, calls infrastructure, saves and returns DTOs (never entities); the "important is not core domain" test; multiple application layers per client sharing one domain layer.
  DO NOT USE FOR: writing an application service (application-services); exposing it as auto/conventional controllers or routes (expose-http-apis); modeling the entities, aggregates, value objects or domain services (model-domain-aggregates); defining or checking permissions (permissions-and-authorization); entity-to-DTO mapping (map-objects-and-dtos); which project a type lives in and reference flow (layered-architecture).
license: MIT
---

# Domain Logic vs Application Logic

ABP splits business logic into two layers, and the hardest DDD question in practice is
*which layer a given rule belongs to*. Getting it wrong leaks use-case concerns into the
domain (making it un-reusable) or scatters core rules across application services (making
them un-enforceable). This skill is the decision guide; the mechanics of writing each
building block live in `model-domain-aggregates` and `application-services`.

- **Domain logic** = the *core domain rules* of the system, independent of any single use
  case. It lives in **entities/aggregate roots** (rules about their own state) and in
  **domain services** (rules that span aggregates or need a repository).
- **Application logic** = the *use case*. It lives in **application services**, which
  orchestrate domain objects to fulfill one user interaction.

## When to Use

- You're unsure whether a check/step goes in an entity, a domain service, or an application service.
- A domain service is reaching for the current user, an authorization check, an email, or `SaveChangesAsync`.
- An application service has grown business rules that should be reusable across use cases.
- You have several front-ends (public web, back-office, mobile) over one domain and want to keep their differences out of the domain.

## When Not to Use

- **Writing the application service itself** (DTOs, orchestration) — use application-services. **Exposing it as auto/conventional controllers or routes** — use expose-http-apis.
- **Modeling the entity, aggregate, value object, or domain service** — use model-domain-aggregates.
- **Defining or checking permissions** — use permissions-and-authorization.
- **Mapping an entity to a DTO** — use map-objects-and-dtos.

## What belongs in the Domain Layer

Put a rule in the **domain** when it must hold for *every* use case — it's part of what
makes the data valid. Prefer the **entity** first; use a **domain service** (a `Manager`)
only when the rule spans aggregates or needs a repository/other service.

A domain service must **not**:

- **Do authorization.** Authorization is a use-case concern; it belongs in the application layer.
- **Depend on the current user / session** (`ICurrentUser`). A domain service should be
  usable even when there is no logged-in user (background workers, data import). Pass any
  needed user id in as a parameter.
- **Send notifications** (`IEmailSender`, SMS, etc.). Whether and what to notify is
  use-case specific.
- **Save to the database.** Persisting is the application service's job (see below). The
  application service may make further changes to the entity before saving, so if the
  domain service saved too you'd get a double database operation (an insert, then an update)
  that needs a transaction spanning both — and if a later rule cancels the creation, both
  have to roll back.

```csharp
public class OrganizationManager : DomainService
{
    private readonly IRepository<Organization, Guid> _organizationRepository;

    public OrganizationManager(IRepository<Organization, Guid> organizationRepository)
    {
        _organizationRepository = organizationRepository;
    }

    public async Task<Organization> CreateAsync(string name)
    {
        // Core domain rule: an organization name is always unique. It holds for every
        // use case, so it belongs here — not in one application service.
        if (await _organizationRepository.AnyAsync(o => o.Name == name))
        {
            throw new BusinessException("IssueTracking:DuplicateOrganizationName");
        }

        return new Organization(GuidGenerator.Create(), name);
        // No authorization, no CurrentUser, no email, no InsertAsync here.
    }
}
```

## What belongs in the Application Layer

The **application service** implements one use case. It's the natural home for everything
tied to *how* this interaction runs:

- **Unit of work.** ABP wraps each application service method in a unit of work by default,
  so you don't need `[UnitOfWork]`. Write requests get a database transaction (all changes
  commit together or roll back on error); read (HTTP GET) methods still get a unit of work
  but no transaction.
- **Authorization.** Guard the use case with `[Authorize("...")]` (or an
  `IAuthorizationService`/`IPermissionChecker` check).
- **Infrastructure calls** for this use case (payment, email, external APIs).
- **Persisting** the changes (call the repository's `InsertAsync`/`UpdateAsync`, or rely
  on the unit of work for tracked entities).
- **Returning DTOs**, never entities — map with `IObjectMapper`.

```csharp
public class OrganizationAppService : ApplicationService, IOrganizationAppService
{
    private readonly OrganizationManager _organizationManager;
    private readonly IRepository<Organization, Guid> _organizationRepository;
    private readonly IPaymentService _paymentService;
    private readonly IEmailSender _emailSender;

    public OrganizationAppService(
        OrganizationManager organizationManager,
        IRepository<Organization, Guid> organizationRepository,
        IPaymentService paymentService,
        IEmailSender emailSender)
    {
        _organizationManager = organizationManager;
        _organizationRepository = organizationRepository;
        _paymentService = paymentService;
        _emailSender = emailSender;
    }

    [Authorize("OrganizationCreationPermission")]     // authorization: application layer
    public async Task<OrganizationDto> CreateAsync(CreateOrganizationDto input)
    {
        await _paymentService.ChargeAsync(CurrentUser.GetId(), GetOrganizationPrice()); // infra + CurrentUser
        var organization = await _organizationManager.CreateAsync(input.Name);          // core rule reused
        await _organizationRepository.InsertAsync(organization);                        // persist
        await _emailSender.SendAsync("admin@acme.com", "New organization", input.Name); // notify
        return ObjectMapper.Map<Organization, OrganizationDto>(organization);           // return a DTO
    }
}
```

## The "important is not the same as core domain" test

The trap is thinking *important* logic must be domain logic. In the example, **charging
payment** feels critical — but it's still application logic, because there are valid use
cases that create an organization **without** payment (an admin creating one from the
back office; a background data-import job). A rule is core domain logic only if it must
hold for **every** use case. If you can name a use case where it shouldn't run, it's
application logic.

## Multiple application layers, one domain

When several clients (public web MVC, back-office Angular, mobile) share one domain, don't
pile their differing use cases, DTOs, validation and authorization into a single
application layer full of `if` branches. Instead:

- Keep **one domain layer** with the shared core logic.
- Create a **separate application layer** per client type (e.g. `Acme.Admin.Application`,
  `Acme.Public.Application`, `Acme.Mobile.Application`), each with its own application
  services, DTOs and authorization for that client's use cases.

## Common Pitfalls

- **Authorization inside a domain service** — move `[Authorize]`/permission checks to the application service.
- **A domain service reading `ICurrentUser`** — pass the needed user id as a method parameter so the service works with no active user.
- **Sending emails/notifications from a domain service** — that's a use-case decision; do it in the application service.
- **Saving inside a domain service** (`InsertAsync`/`UpdateAsync`) — let the application service persist; saving in the domain service causes a double database operation once the application service updates the entity again.
- **Returning entities from an application service** — return a DTO (`ObjectMapper.Map`) instead.
- **Treating "important" as "core domain"** — if any use case legitimately skips the rule, it's application logic.
