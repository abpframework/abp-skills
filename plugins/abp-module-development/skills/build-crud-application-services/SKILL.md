---
name: build-crud-application-services
description: >
  Builds or reviews a complete ABP CRUD application-service contract and implementation with the CrudAppService APIs.
  USE FOR: choosing ICrudAppService/CrudAppService generic overloads, separating get/list/create/update DTOs, wiring IRepository, object mappings and five policy properties, adding list filters without breaking count/sort/page order, and validating all five CRUD operations.
  DO NOT USE FOR: a non-CRUD use case or general ApplicationService orchestration (use application-services); composite or non-standard keys with AbstractKeyCrudAppService (use application-services); mapping-provider configuration details (use map-objects-and-dtos); permission definitions (use permissions-and-authorization); optimistic concurrency (use handle-optimistic-concurrency); HTTP endpoint conventions (use expose-http-apis); integration-test infrastructure (use test-abp-applications).
license: MIT
---

# Build ABP CRUD Application Services

Use the framework CRUD base only when the use case really has the standard get, list, create, update, and delete shape.

## When to Use

- Implement a standard keyed entity CRUD contract in `*.Application.Contracts` and its service in `*.Application`.
- Select the shortest generic overload that still preserves distinct public DTO contracts.
- Add filtering while retaining the framework's count, sorting, paging, mapping, authorization, and tenant behavior.
- Review an existing `CrudAppService` for missing policies, mappings, pagination, or operation coverage.

## When Not to Use

- **A use case with commands or workflows beyond CRUD** — use **application-services** and explicit methods.
- **An entity that cannot use `IEntity<TKey>` key lookup** — use **application-services** for `AbstractKeyCrudAppService` and implement key resolution.
- **Mapping-provider setup or profile troubleshooting** — use **map-objects-and-dtos**.
- **Permission definition and grant configuration** — use **permissions-and-authorization**; this skill only connects policy names to CRUD operations.
- **Concurrency-token design** — use **handle-optimistic-concurrency**.
- **Conventional HTTP controllers or routes** — use **expose-http-apis**.
- **Test host, database, current user, or current tenant setup** — use **test-abp-applications**.

## How it works

### Contract shape

The widest contract is:

```csharp
ICrudAppService<
    TGetOutputDto,
    TGetListOutputDto,
    TKey,
    TGetListInput,
    TCreateInput,
    TUpdateInput>
```

It combines these five methods:

```csharp
Task<TGetOutputDto> GetAsync(TKey id);
Task<PagedResultDto<TGetListOutputDto>> GetListAsync(TGetListInput input);
Task<TGetOutputDto> CreateAsync(TCreateInput input);
Task<TGetOutputDto> UpdateAsync(TKey id, TUpdateInput input);
Task DeleteAsync(TKey id);
```

The shorter overloads progressively reuse one DTO type for get, list, create, and update, and the shortest overload uses `PagedAndSortedResultRequestDto`. Prefer the widest overload when the public fields differ between detail, list, create, and update contracts.

ABP's test application contains this shortest-overload implementation. The excerpt omits unrelated test endpoints:

```csharp
public interface IPeopleAppService : ICrudAppService<PersonDto, Guid>
{
    // Other test endpoints omitted.
}

public class PeopleAppService : CrudAppService<Person, PersonDto, Guid>, IPeopleAppService
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public PeopleAppService(
        IRepository<Person, Guid> repository,
        IHttpContextAccessor httpContextAccessor)
        : base(repository)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    // Other test endpoints omitted.
}
```

The extra HTTP-context dependency belongs to that test application, not to `CrudAppService`; the base constructor accepts `IRepository<TEntity, TKey>`.

### Implementation shape

For separate DTO contracts, derive from the widest base:

```csharp
CrudAppService<
    TEntity,
    TGetOutputDto,
    TGetListOutputDto,
    TKey,
    TGetListInput,
    TCreateInput,
    TUpdateInput>
```

`TEntity` must be a class implementing `IEntity<TKey>`. The base receives `IRepository<TEntity, TKey>` and supplies standard key lookup and deletion.

Register mappings for every default mapping path used by the selected generic arguments:

- `TEntity` to `TGetOutputDto`.
- `TEntity` to `TGetListOutputDto`.
- `TCreateInput` to `TEntity`.
- `TUpdateInput` to the existing `TEntity` instance.

Use **map-objects-and-dtos** to configure the selected object-mapping provider. Override the async mapping methods when entity creation or mutation must go through constructors, aggregate methods, or a domain service. Both are `protected virtual` with default (object-mapper-backed) bodies, so override the one(s) you need:

- `Task<TEntity> MapToEntityAsync(TCreateInput createInput)` — build the new entity (e.g. via its constructor or a factory). A custom create override therefore owns key assignment.
- `Task MapToEntityAsync(TUpdateInput updateInput, TEntity entity)` — apply the changes onto the loaded entity (e.g. through aggregate methods). A custom update override owns any input-ID normalization.

The async overrides take precedence over the default synchronous mapping methods.

### Operation pipeline

- `GetAsync` checks `GetPolicyName`, loads by key, then maps to `TGetOutputDto`.
- `GetListAsync` checks `GetListPolicyName`, creates the filtered query, counts it, applies sorting, applies paging, executes it, then maps the page to `TGetListOutputDto`.
- `CreateAsync` checks `CreatePolicyName`, maps a new entity, sets framework-managed values described below, inserts with `autoSave: true`, then maps the result.
- `UpdateAsync` checks `UpdatePolicyName`, loads the entity, maps onto that existing instance, updates with `autoSave: true`, then maps the result.
- `DeleteAsync` checks `DeletePolicyName`, then deletes by key.

Set all five protected policy-name properties in the derived service. `CheckPolicyAsync` returns without checking authorization when a property is null or empty; leaving a policy property unset does not deny access.

### Framework-managed create and update values

- On the default create-mapping path, an empty (`Guid.Empty`) key on an `IEntity<Guid>` is assigned through `GuidGenerator` — but only when the `Id` property is settable and not marked `[DisableIdGeneration]`. A non-empty client-supplied ID is left as-is (only `Guid.Empty` is replaced).
- After create mapping, an `IMultiTenant` entity gets `CurrentTenant.Id` when the current tenant has a value and the entity exposes a settable `TenantId` property.
- Before the default update mapping, if `TUpdateInput` implements `IEntityDto<TKey>`, its `Id` is replaced with the loaded entity's ID.

Do not depend on a client-supplied ID or tenant ID when these framework paths apply.

### Filtering, sorting, and paging

Override `CreateFilteredQueryAsync` to apply filters only:

```csharp
protected override async Task<IQueryable<TEntity>> CreateFilteredQueryAsync(
    TGetListInput input)
{
    var query = await base.CreateFilteredQueryAsync(input);

    // Apply filters only. Sorting and paging run after the total count query.
    return query;
}
```

Do not sort or page in this method. The base counts the filtered query before calling `ApplySorting` and `ApplyPaging`.

Sorting is applied only when the input implements `ISortedResultRequest`. A non-empty `Sorting` value is passed to dynamic LINQ `OrderBy`. When a limited result is requested without explicit sorting, `CrudAppService` orders descending by `CreationTime` for `IHasCreationTime` entities and otherwise by `Id`.

Paging is applied when the input implements `IPagedResultRequest`; otherwise a plain `ILimitedResultRequest` receives `Take(MaxResultCount)`. `PagedAndSortedResultRequestDto` supplies both paging and sorting. `LimitedResultRequestDto.MaxResultCount` defaults to 10 and validates against a maximum of 1,000.

## Workflow

1. Define the detail output, list output, list input, create input, and update input in `*.Application.Contracts`.
2. Select the matching `ICrudAppService` overload; use the widest overload unless two contract roles intentionally share the same shape.
3. Derive the implementation from the matching `CrudAppService` overload and pass `IRepository<TEntity, TKey>` to the base constructor.
4. Register all default mapping pairs, or override the async mapping methods for domain-controlled construction and mutation.
5. Assign `GetPolicyName`, `GetListPolicyName`, `CreatePolicyName`, `UpdatePolicyName`, and `DeletePolicyName` to defined permission names.
6. Override `CreateFilteredQueryAsync` for filters; leave sorting and paging to their dedicated base methods.
7. Validate get, filtered/paged list, create, update, delete, permission denial, mapping, and tenant behavior in integration tests.

## Validation

- Build the contracts and application projects so every selected generic argument and mapping override compiles.
- Resolve the interface from DI and execute all five methods against the integration-test database.
- Verify list `TotalCount` represents the filtered query before paging, while `Items` contains only the requested page.
- Verify each operation is denied when its assigned policy is not granted; an unset policy property is a configuration failure, not a denial test.
- For a tenant entity, create under a non-null `CurrentTenant.Id` and verify the persisted tenant ID comes from the current tenant.
- When using the default create mapping for a `Guid` entity with an empty ID (and a settable `Id` without `[DisableIdGeneration]`), verify the returned DTO has a non-empty ID; with a non-empty input ID, verify it is kept unchanged.
- If update input implements `IEntityDto<TKey>`, test with a mismatched input ID and verify the method ID remains authoritative.
- Use **test-abp-applications** for the test host and **handle-optimistic-concurrency** for stale-update and stale-delete cases.

## Common Pitfalls

- **Leaving policy properties null.** The base treats null or empty as "no policy check," not "deny by default."
- **Using one DTO for every operation by habit.** Short overloads deliberately reuse types; choose the widest overload when writable fields differ from returned fields.
- **Missing one mapping direction.** Get/list map from the entity, create maps to a new entity, and update maps onto the loaded entity.
- **Paging inside `CreateFilteredQueryAsync`.** It makes `TotalCount` describe the page instead of the full filtered set and is then paged again by the base.
- **Using a custom list input without paging interfaces.** Sorting and paging are interface-driven; unrelated properties with similar names do not activate them.
- **Trusting client IDs or tenant IDs during create/update.** The base can generate an empty `Guid`, replace an update DTO ID, and assign the current tenant ID.
- **Overriding async mapping and expecting default key handling to continue.** The async override has priority; custom creation must assign the key, and custom update mapping must preserve the loaded entity's key.
- **Using `CrudAppService` for a non-standard key.** It requires `IEntity<TKey>` and standard repository key lookup; use the `AbstractKeyCrudAppService` path in **application-services** instead.
- **Treating CRUD as a substitute for domain behavior.** Override mapping or explicit methods when construction and mutation must enforce aggregate invariants.
