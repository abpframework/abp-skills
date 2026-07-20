---
name: test-abp-applications
description: >
  Write or fix integration tests for an ABP application against the generated *TestBase — resolving services, controlling the unit of work, seeding data, faking the current user/tenant, exercising the real `[Authorize]` pipeline, and proving transaction rollback across EF Core and MongoDB.
  USE FOR: the `AbpIntegratedTest`/`*TestBase` chain, per-provider test classes, `GetRequiredService`, `WithUnitOfWorkAsync`/`IUnitOfWorkManager.Begin`, `*TestDataSeedContributor`, `ICurrentPrincipalAccessor.Change`, undoing `AddAlwaysAllowAuthorization` (DENY) / `AddAlwaysDisableUnitOfWorkTransaction` (EF rollback), `ICurrentTenant.Change`, SQLite/MongoSandbox differences.
  DO NOT USE FOR: production unit-of-work config (use manage-units-of-work); production data seeding (use seed-application-data); production multi-tenant setup (use configure-multi-tenancy); production permission definitions (use permissions-and-authorization); Angular component tests (use test-angular-ui); MVC/Razor page tests (use test-mvc-razor-ui).
license: MIT
---

# Testing ABP Applications

ABP integration tests run the real application (DI, unit of work, repositories, EF Core/Mongo mapping) — you don't mock the infrastructure. This is the recommended default for testing application services, domain services, and repositories.

## When to Use

- Writing integration tests for application services, domain services, or repositories.
- Resolving real services in a test and asserting against real DB behavior.
- Controlling the unit of work when touching a repository/`DbContext` directly.
- Seeding data for tests, or faking the current user/tenant to drive code paths.
- Verifying that `[Authorize(PermissionName)]` actually denies an application-service call.
- Proving commit/rollback behavior without getting a false positive from an unsaved entity.
- Sharing application tests across EF Core and MongoDB while keeping provider-specific query tests separate.

## When Not to Use

- **Configuring the unit of work in production code** — use **manage-units-of-work**; here `WithUnitOfWorkAsync`/`Begin` is only about the test body.
- **Production data seeding** — use **seed-application-data**; this skill covers the test-side `*TestDataSeedContributor`.
- **Setting up multi-tenancy in the app** — use **configure-multi-tenancy**; here `ICurrentTenant.Change` is only for scoping a test.
- **Defining permissions/authorization** — use **permissions-and-authorization**; tests use `AddAlwaysAllowAuthorization` by default.

## Unit test or integration test?

Pick the cheaper one that still exercises the behavior — don't spin up the ABP application when a plain unit test suffices:

- **Plain unit test (no ABP application).** Entity/aggregate/value-object invariants and domain rules with no framework dependency: instantiate the type and assert. ABP's own unit-test docs use ordinary xUnit + NSubstitute (for the few collaborators you fake) + Shouldly — there's nothing ABP-specific to start up.
- **Integration test (this skill).** Anything that depends on the ABP runtime: repositories/`DbContext`, the unit of work, the authorization interceptor, data filters, tenant or provider-specific behavior. Mocking that infrastructure is more fragile than running it, so drive it through the `*TestBase` chain.
- **UI-layer tests have their own skills.** Angular component tests (Vitest + `CoreTestingModule` + TestBed) → **test-angular-ui**; MVC/Razor page tests over HTTP (`AbpWebApplicationFactoryIntegratedTest`) → **test-mvc-razor-ui**. Blazor bUnit has **no sibling skill yet** — it's not covered here. This skill is server-side integration testing only.

## How it works

### The test module chain

The base class is `AbpIntegratedTest<TStartupModule>` (package `Volo.Abp.TestBase`). Its constructor builds a service collection, adds the ABP application for `TStartupModule`, initializes it, and exposes a scoped `ServiceProvider`. `Dispose()` shuts the application down. You rarely derive from it directly — the startup template generates a `*TestBase` (e.g. `MyProjectDomainTestBase<TStartupModule>`) that already wires in the test module chain, so your test classes derive from that.

Test classes are usually written as `abstract` against `TStartupModule`, then made concrete per database provider so the test explorer picks them up:

```csharp
// In .Application.Tests (abstract — not shown in test explorer)
public abstract class IssueAppService_Tests<TStartupModule> : MyProjectApplicationTestBase<TStartupModule>
    where TStartupModule : IAbpModule
{
    private readonly IIssueAppService _issueAppService;

    protected IssueAppService_Tests()
    {
        _issueAppService = GetRequiredService<IIssueAppService>();
    }

    [Fact]
    public async Task Should_Get_All_Issues()
    {
        var issues = await _issueAppService.GetListAsync();
        issues.Count.ShouldBeGreaterThan(0);
    }
}

// In .EntityFrameworkCore.Tests (concrete — runs)
[Collection(MyProjectTestConsts.CollectionDefinitionName)]
public class EfCoreIssueAppService_Tests : IssueAppService_Tests<MyProjectEntityFrameworkCoreTestModule>
{
}
```

The generated concrete provider tests carry `[Collection(MyProjectTestConsts.CollectionDefinitionName)]` (both EF Core and MongoDB use the same collection name). For MongoDB the collection is what binds the test to the `ICollectionFixture<...MongoDbFixture>`, so omitting it breaks the fixture's lifecycle/cleanup — keep the attribute.

The template ships xUnit (test framework), NSubstitute (mocking), and Shouldly (assertions).

### Resolving services

`AbpIntegratedTest` inherits `GetRequiredService<T>()` and `GetService<T>()` (plus keyed variants) from `AbpTestBaseWithServiceProvider`. Resolve anything the module graph registers — application services, domain managers, repositories:

```csharp
var issueManager = GetRequiredService<IssueManager>();
var repository = GetRequiredService<IRepository<Issue, Guid>>();
var uowManager = GetRequiredService<IUnitOfWorkManager>();
```

### Unit of work in tests

Every DB operation runs inside a unit of work. When you call an application service method, the UoW scope is that method — nothing extra needed. Repository **method calls** (e.g. `InsertAsync`, `FindAsync`) also run in their own automatic UoW — repositories are `IUnitOfWorkEnabled`, so a plain repository call in the test body works without opening one. You only need an explicit UoW when you use a `DbContext` directly, or when you materialize an `IQueryable` from `GetQueryableAsync()` in the test body (outside a repository method) — e.g. `GetQueryableAsync()` then `FirstOrDefaultAsync`. Open one explicitly for those.

The generated test base exposes a `WithUnitOfWorkAsync` helper (this is a template-provided member, not part of `Volo.Abp.TestBase`):

```csharp
await WithUnitOfWorkAsync(async () =>
{
    var queryable = await _issueRepository.GetQueryableAsync();
    var issue = await queryable.FirstOrDefaultAsync(i => i.Title == "My issue");
    issue.ShouldNotBeNull();
});
```

Equivalent using `IUnitOfWorkManager` directly (`Begin()` is an extension in `Volo.Abp.Uow`; its `isTransactional` default is `false`):

```csharp
using (var uow = _unitOfWorkManager.Begin())
{
    var queryable = await _issueRepository.GetQueryableAsync();
    // ...
    await uow.CompleteAsync();
}
```

### Seeding test data

Use ABP's data-seeding system. The template generates a `*TestDataSeedContributor` in the `.TestBase` project implementing `IDataSeedContributor, ITransientDependency` — it runs automatically before tests via the test module chain:

```csharp
public class MyProjectTestDataSeedContributor : IDataSeedContributor, ITransientDependency
{
    private readonly IIssueRepository _issueRepository;

    public MyProjectTestDataSeedContributor(IIssueRepository issueRepository)
        => _issueRepository = issueRepository;

    public async Task SeedAsync(DataSeedContext context)
    {
        await _issueRepository.InsertAsync(new Issue { Title = "Test issue one" });
        await _issueRepository.InsertAsync(new Issue { Title = "Test issue two" });
    }
}
```

Keep known IDs in a static `TestData` class so tests can assert against seeded rows. To seed for a specific tenant, `IDataSeeder.SeedAsync(tenantId)` (extension in `Volo.Abp.Data`) sets `DataSeedContext.TenantId`.

### Faking the current user

`ICurrentPrincipalAccessor` (namespace `Volo.Abp.Security.Claims`) has `Change(ClaimsPrincipal)` returning an `IDisposable` — the principal is restored when disposed. Extension overloads accept a single `Claim`, an `IEnumerable<Claim>`, or a `ClaimsIdentity`. Build the claims with `AbpClaimTypes` (`UserId`, `UserName`, `Role`, `TenantId`, ...) so `ICurrentUser` reflects them:

```csharp
var accessor = GetRequiredService<ICurrentPrincipalAccessor>();
var identity = new ClaimsIdentity(
    new[]
    {
        new Claim(AbpClaimTypes.UserId, userId.ToString()),
        new Claim(AbpClaimTypes.UserName, "test-user"),
        new Claim(AbpClaimTypes.Role, "admin"),
    },
    authenticationType: "Test"
);
var principal = new ClaimsPrincipal(identity);

using (accessor.Change(principal))
{
    // Code here sees ICurrentUser.Id == userId (roles/claims reflected in ICurrentUser).
    await _issueAppService.CreateAsync(input);
}
```

Use this to give the running code an identity — `ICurrentUser.Id`, roles and other claims come from the changed principal.

### Test the real `[Authorize]` permission-denial path

Authorization does not fail in a generated test project by default. `*TestBaseModule` calls `AddAlwaysAllowAuthorization()`, which replaces all four decision points:

- `IAuthorizationService` and `IAbpAuthorizationService` with `AlwaysAllowAuthorizationService`.
- `IMethodInvocationAuthorizationService` with `AlwaysAllowMethodInvocationAuthorizationService`.
- `IPermissionChecker` with `AlwaysAllowPermissionChecker`.

Replacing only `IPermissionChecker` is **not enough** for `[Authorize]`: `AuthorizationInterceptor` delegates to `IMethodInvocationAuthorizationService`, and the always-allow implementation returns without evaluating the policy. Restore the real authorization services in `AfterAddApplication`, then replace the permission checker with a deterministic DENY. `AfterAddApplication` runs after all module registrations and before the service provider is built.

```csharp
protected override void AfterAddApplication(IServiceCollection services)
{
    base.AfterAddApplication(services);

    services.Replace(
        ServiceDescriptor.Transient<IAuthorizationService, AbpAuthorizationService>()
    );
    services.Replace(
        ServiceDescriptor.Transient<IAbpAuthorizationService, AbpAuthorizationService>()
    );
    services.Replace(
        ServiceDescriptor.Transient<IMethodInvocationAuthorizationService, MethodInvocationAuthorizationService>()
    );

    var permissionChecker = Substitute.For<IPermissionChecker>();
    permissionChecker
        .IsGrantedAsync(
            Arg.Any<ClaimsPrincipal?>(),
            MyProjectPermissions.Issues.Delete
        )
        .Returns(false);

    services.Replace(ServiceDescriptor.Singleton(permissionChecker));
}
```

This keeps the real interceptor → policy provider → authorization handler path. `PermissionRequirementHandler` calls the two-argument `IPermissionChecker.IsGrantedAsync(ClaimsPrincipal?, string)` overload, which is why that exact overload is configured.

Now assert both the exception and the invariant protected by authorization:

```csharp
[Fact]
public async Task Should_Deny_Delete_Without_Permission()
{
    await Assert.ThrowsAsync<AbpAuthorizationException>(
        () => _issueAppService.DeleteAsync(_issueId)
    );

    var issue = await WithUnitOfWorkAsync(
        () => _issueRepository.FindAsync(_issueId)
    );
    issue.ShouldNotBeNull();
}
```

Use a dedicated test base for DENY tests so restoring authorization does not silently change unrelated tests that intentionally rely on always-allow. The permission named in `[Authorize]` must exist in a `PermissionDefinitionProvider`; `AbpAuthorizationPolicyProvider` only creates a permission policy for a known definition.

### Multi-tenant behavior

`ICurrentTenant.Change(Guid? id, string? name = null)` (namespace `Volo.Abp.MultiTenancy`) returns an `IDisposable` scoping the current tenant. Data filters, connection resolution, and seeding all honor it:

```csharp
var currentTenant = GetRequiredService<ICurrentTenant>();
using (currentTenant.Change(tenantId))
{
    // Queries are filtered to this tenant; new entities get TenantId = tenantId.
    var issues = await _issueRepository.GetListAsync();
}
```

Combine with `ICurrentPrincipalAccessor.Change` (add an `AbpClaimTypes.TenantId` claim) when you need both the tenant and an authenticated user.

### Database setup from the templates

The startup template pre-configures a fresh throwaway database per test case:

- **EF Core** → a keep-alive `AbpUnitTestSqliteConnection` with `Data Source=:memory:`; the test module creates the tables and reuses that open connection for the test application.
- **MongoDB** → `MongoSandbox` starts one embedded runner with `UseSingleNodeReplicaSet = true`; each test application receives a random database name. The replica-set mode is what lets MongoDB transactions run in these tests.

The wiring lives in each provider's own test module — `*EntityFrameworkCoreTestModule` sets up the SQLite connection and creates the tables, and `*MongoDbTestModule` assigns the random MongoDB database name. (The shared `*TestBaseModule` handles cross-provider setup — always-allow authorization, data seeding, and disabling background-job execution — but not DB wiring.) You normally don't configure the connection yourself — derive from the generated base classes and it just works.

Keep provider-neutral application/domain tests in the abstract `.Application.Tests` / `.Domain.Tests` projects. Put direct LINQ repository tests in the provider project: the generated EF sample uses `Microsoft.EntityFrameworkCore` async operators, while the Mongo sample uses `MongoDB.Driver.Linq` async operators.

### Prove transaction rollback

`WithUnitOfWorkAsync(Func<Task>)` creates `new AbpUnitOfWorkOptions()`, begins a UoW, invokes the delegate, and calls `CompleteAsync()` only when the delegate returns. Passing `new AbpUnitOfWorkOptions { IsTransactional = true }` requests a transaction.

There is one critical provider difference in the generated templates:

- The EF Core test module calls `AddAlwaysDisableUnitOfWorkTransaction()`. It replaces `IUnitOfWorkManager` with `AlwaysDisableTransactionsUnitOfWorkManager`, whose `Begin` forcibly sets `options.IsTransactional = false`. Requesting a transaction does not override it.
- The MongoDB test module does not disable transactions, and its MongoSandbox runner is a single-node replica set. `UnitOfWorkMongoDbContextProvider` starts a session transaction when `IsTransactional` is `true`.

For an EF Core rollback-specific test base, restore the normal manager after module registration:

```csharp
protected override void AfterAddApplication(IServiceCollection services)
{
    base.AfterAddApplication(services);

    services.Replace(ServiceDescriptor.Singleton<IUnitOfWorkManager>(
        serviceProvider => serviceProvider.GetRequiredService<UnitOfWorkManager>()
    ));
}
```

Then force a database write before throwing. Without `SaveChangesAsync`, an EF test can pass merely because the pending insert was never flushed, which does not prove rollback.

```csharp
[Fact]
public async Task Should_Roll_Back_A_Flushed_Insert()
{
    var issueId = Guid.NewGuid();

    await Assert.ThrowsAsync<InvalidOperationException>(async () =>
    {
        await WithUnitOfWorkAsync(
            new AbpUnitOfWorkOptions { IsTransactional = true },
            async () =>
            {
                var uow = GetRequiredService<IUnitOfWorkManager>().Current!;
                uow.Options.IsTransactional.ShouldBeTrue();

                await _issueRepository.InsertAsync(new Issue(issueId, "Rollback test"));
                await uow.SaveChangesAsync();

                throw new InvalidOperationException("Rollback test");
            }
        );
    });

    var issue = await WithUnitOfWorkAsync(
        () => _issueRepository.FindAsync(issueId)
    );
    issue.ShouldBeNull();
}
```

The same rollback assertion can run against the generated MongoDB provider without the EF-only manager replacement. ABP's EF and Mongo transaction APIs both implement `ISupportsRollback`, and ABP's own provider transaction tests verify explicit rollback as well as disposal without `CompleteAsync()`.

## Validation

- Derive the test from the generated `*TestBase` and run it with `dotnet test`; the throwaway SQLite/MongoDB DB and the seed contributor come up automatically.
- Confirm services resolve via `GetRequiredService<T>()` for anything the module graph registers.
- To confirm a fake identity took effect, assert `GetRequiredService<ICurrentUser>().Id` equals the injected `userId` inside the `accessor.Change(...)` scope.
- For a DENY test, verify the resolved `IMethodInvocationAuthorizationService` is `MethodInvocationAuthorizationService`, assert `AbpAuthorizationException`, and assert the protected state did not change.
- For rollback, assert `Current.Options.IsTransactional` inside the UoW, flush before the failure, then query in a new UoW and assert the row is absent.
- Run the shared application/domain test suite once through each concrete provider project; run provider-specific query tests only in their provider project.

## Common Pitfalls

- **Materializing a query or using `DbContext` in the test body with no UoW.** Repository *method* calls open their own UoW, but a `GetQueryableAsync()` result materialized in the test body (or direct `DbContext` access) has no active UoW and throws — wrap those in `WithUnitOfWorkAsync` or `IUnitOfWorkManager.Begin()`.
- **Replacing only `IPermissionChecker` for an `[Authorize]` test.** The always-allow method-invocation service short-circuits before the checker; restore the three real authorization services too.
- **Assuming `IsTransactional = true` beats the EF template default.** `AlwaysDisableTransactionsUnitOfWorkManager` rewrites it to `false`; restore `UnitOfWorkManager` in a rollback-specific EF test base.
- **Calling rollback without first flushing an EF write.** A missing row can mean “never saved,” not “rolled back”; call `SaveChangesAsync()` inside the transaction before the forced failure.
- **Only deriving the abstract test class.** Write the test `abstract` against `TStartupModule`, then a concrete per-provider subclass — the test explorer only runs the concrete one.
- **Putting provider-specific async LINQ in a shared test.** EF Core and MongoDB use different async LINQ extension namespaces; keep direct-query tests in the provider projects.
- **Configuring the test DB connection by hand.** Each provider's own test module (`*EntityFrameworkCoreTestModule` / `*MongoDbTestModule`) wires the throwaway SQLite/MongoSandbox DB — derive from the generated base and it just works.
