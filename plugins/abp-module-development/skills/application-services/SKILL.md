---
name: application-services
description: >
  Writes or reviews an ABP application service — the DTO-taking, DTO-returning boundary between the domain and the presentation/API layer.
  USE FOR: implementing IApplicationService/ApplicationService for non-CRUD use cases, using AbstractKeyCrudAppService for composite or non-standard keys, and unit-of-work basics.
  DO NOT USE FOR: exposing application services as auto/conventional API controllers, routes, verbs or [RemoteService] (use expose-http-apis); a complete standard-key CrudAppService workflow (use build-crud-application-services); detailed object-to-DTO mapping mechanics/profiles (use map-objects-and-dtos); DTO validation attributes and business exceptions (use handle-validation-and-errors); permission definitions and authorization policy (use permissions-and-authorization); the overall layered project structure (use layered-architecture).
license: MIT
---

# ABP Application Services

Application services implement use cases. They take and return **DTOs** (never entities), orchestrate domain objects and repositories, and are the boundary between the domain and the presentation/API layer.

## When to Use

- Implementing an application service (interface in `*.Application.Contracts`, class in `*.Application`).
- Using `AbstractKeyCrudAppService` when standard repository key lookup is not available.
- Understanding the ambient unit of work around app service methods.

## When Not to Use

- **Object-to-DTO mapping mechanics** (AutoMapper profiles, Mapperly, custom mappers) — use map-objects-and-dtos; here mapping appears only as `ObjectMapper.Map` usage.
- **A complete standard-key `CrudAppService` workflow** — use build-crud-application-services for contract overloads, policies, filtering, sorting, paging, mapping paths, and operation validation.
- **DTO validation attributes and business/error exceptions** — use handle-validation-and-errors; this skill only notes that validation runs automatically.
- **Permission definitions and authorization policy** — use permissions-and-authorization; `[Authorize]` here is just wiring.
- **Overall layered project structure** — use layered-architecture.

## Base class & interface

Define the interface in `*.Application.Contracts` and the implementation in `*.Application`. Implement `IApplicationService` (namespace `Volo.Abp.Application.Services`) on the interface and derive from `ApplicationService` (same namespace) in the class:

```csharp
// *.Application.Contracts
public interface IBookAppService : IApplicationService
{
    Task<BookDto> GetAsync(Guid id);
    Task<BookDto> CreateAsync(CreateBookDto input);
}

// *.Application
public class BookAppService : ApplicationService, IBookAppService
{
    private readonly IRepository<Book, Guid> _bookRepository;
    public BookAppService(IRepository<Book, Guid> bookRepository)
        => _bookRepository = bookRepository;

    public async Task<BookDto> GetAsync(Guid id)
    {
        var book = await _bookRepository.GetAsync(id);
        return ObjectMapper.Map<Book, BookDto>(book);
    }

    public async Task<BookDto> CreateAsync(CreateBookDto input)
    {
        var book = await _bookRepository.InsertAsync(
            new Book(GuidGenerator.Create(), input.Name));
        return ObjectMapper.Map<Book, BookDto>(book);
    }
}
```

The `ApplicationService` base gives you injected members via `LazyServiceProvider`: `ObjectMapper`, `GuidGenerator`, `CurrentUser`, `CurrentTenant`, `Logger`, `L` (localization), `AuthorizationService`, etc.

## DTOs & object mapping

`ObjectMapper` is an `IObjectMapper` (namespace `Volo.Abp.ObjectMapping`). Key methods:

```csharp
TDestination Map<TSource, TDestination>(TSource source);
TDestination Map<TSource, TDestination>(TSource source, TDestination destination);
```

The default implementation (`DefaultObjectMapper`) delegates to a replaceable `IAutoObjectMappingProvider`, so the actual mapping is provided by the registered AutoMapper *or* Mapperly provider — the default app template registers Mapperly (`AddMapperlyObjectMapper`). One option is AutoMapper: register mappings in an AutoMapper `Profile` and add it in your module's `ConfigureServices`:

```csharp
public class MyApplicationAutoMapperProfile : Profile
{
    public MyApplicationAutoMapperProfile()
    {
        CreateMap<Book, BookDto>(); // entity -> output DTO; build the entity via its constructor, don't auto-map the input DTO onto it
    }
}

// In the *.Application module class
Configure<AbpAutoMapperOptions>(options =>
{
    options.AddMaps<MyApplicationModule>();
});
```

## CRUD services

Use **build-crud-application-services** for the complete standard-key `ICrudAppService` / `CrudAppService` contract, implementation, authorization, mapping, filtering, sorting, paging, and validation workflow.

`AbstractKeyCrudAppService<...>` has the **same generic overloads** and is the variant to use when the entity does not derive from `IEntity<TKey>` (e.g. composite/non-standard keys). The only members you **must** implement are the abstract `GetEntityByIdAsync` and `DeleteByIdAsync` (key resolution). The mapping methods (`MapToEntityAsync`, `MapToGetOutputDtoAsync`, etc.) are `virtual` with default object-mapping implementations — override them only when you need custom mapping.

## Input validation

Input DTOs are validated automatically because `ApplicationService` implements `IValidationEnabled` (namespace `Volo.Abp.Validation`). Use standard data annotations on DTO properties:

```csharp
public class CreateBookDto
{
    [Required]
    [StringLength(128)]
    public string Name { get; set; }

    [Range(typeof(decimal), "0", "999.99")]
    public decimal Price { get; set; }
}
```

Invalid input throws `AbpValidationException` → HTTP 400 before your method body runs. Any class implementing `IValidationEnabled` gets this behavior via the validation interceptor.

## Authorization

Apply `[Authorize]` at class or method level; combine with permissions defined in `*.Application.Contracts`. You can also call `CurrentUser` / `AuthorizationService` for imperative checks:

```csharp
[Authorize(MyPermissions.Books.Default)]
public class BookAppService : ApplicationService, IBookAppService
{
    [Authorize(MyPermissions.Books.Create)]
    public async Task<BookDto> CreateAsync(CreateBookDto input) { /* ... */ }
}
```

## Exposing the service over HTTP

ABP can expose an application service as a REST API controller automatically, with no controller class — configuring `ConventionalControllers.Create`, the route/verb conventions, and `[RemoteService]` toggles is the **expose-http-apis** skill's job. Write the application service here; publish it there.

## Unit of work basics

Every app service method runs inside an **ambient unit of work** by default (`ApplicationService` implements `IUnitOfWorkEnabled`) — repository changes are saved and the DB transaction commits/rolls back around the method automatically, so you rarely call `SaveChanges` manually.

Use `[UnitOfWork]` (namespace `Volo.Abp.Uow`) to tune behavior (e.g. transactional flag, isolation) or to make a normally non-UoW method transactional:

```csharp
[UnitOfWork(isTransactional: true)]
public async Task DoWorkAsync() { /* changes commit together */ }
```

If you need the current UoW imperatively, inject `IUnitOfWorkManager` and use `Current` / `Begin`.

## Validation

- Confirm the service resolves and returns DTOs (never entities) — the `*.Application.Contracts` interface should reference only DTOs.
- After registering the app service assembly via `ConventionalControllers.Create`, confirm the auto-generated REST endpoints appear (e.g. in Swagger) with the expected verbs (`GetAsync` → GET, `CreateAsync` → POST, etc.).
- Post an invalid DTO and confirm an `AbpValidationException` → HTTP 400 before the method body runs.
- Confirm repository changes persist without a manual `SaveChanges` (the ambient UoW commits around the method).

## Common Pitfalls

- Application services take and return **DTOs, never entities** — leaking entities across the boundary defeats the layering.
- Use **build-crud-application-services** for standard-key CRUD instead of reconstructing its contract and pipeline here.
- Use `AbstractKeyCrudAppService` (not `CrudAppService`) when the entity does **not** derive from `IEntity<TKey>` (composite/non-standard keys); you must implement `GetEntityByIdAsync` and `DeleteByIdAsync`.
- Validation only fires for classes implementing `IValidationEnabled` via the interceptor — `ApplicationService` already does, so validation is automatic there.
- Every app service method runs in an ambient UoW by default, so avoid manual `SaveChanges` — but "ambient UoW" doesn't mean "DB transaction": with the default `Auto` mode, only HTTP `GET` requests are non-transactional; all other verbs (including `QUERY`) open a transaction unless a URL is listed in `NonTransactionalUrls`. Use `[UnitOfWork]` to tune behavior.
