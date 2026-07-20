---
name: authorize-resources
description: >
  Grant access to a specific entity instance ("edit this document") rather than a global permission — using ABP resource permissions or a standard ASP.NET Core AuthorizationHandler with a resource.
  USE FOR: per-owner or per-instance access (this project, this document), AddResourcePermission, IAuthorizationService.IsGrantedAsync(resource, name), IResourcePermissionChecker/IResourcePermissionManager, a custom resource-based AuthorizationHandler.
  DO NOT USE FOR: global named permissions ("can edit documents" for everyone) — use the permissions-and-authorization skill; configuring the auth server (OpenIddict) — use the configure-openiddict-authentication skill; refreshing claims mid-session — use the configure-dynamic-claims skill.
license: MIT
---

# Resource-Based Authorization in ABP

Standard ABP permissions are global ("can edit documents"). **Resource-based authorization** grants access to a *specific* instance ("can edit **this** document"). Use it for per-owner blog posts, team-scoped projects, document sharing with per-user access levels, or any ownership/sharing rule.

## When to Use

- Access must depend on a specific entity instance, not a blanket permission.
- Per-owner or team-scoped resources (blog posts, projects, documents with per-user access levels).
- Admin-managed per-instance grants (Option 1 — ABP resource permissions).
- Rule-based access such as "owner or admin" evaluated in code (Option 2 — custom `AuthorizationHandler`).

## When Not to Use

- **Global named permissions** that apply the same to everyone ("can edit documents") — use the **permissions-and-authorization** skill instead.
- **Configuring the auth server / login / token issuance** (OpenIddict) — use the **configure-openiddict-authentication** skill.
- **Refreshing claims mid-session without re-login** — use the **configure-dynamic-claims** skill.

## How it works — two styles

ABP supports two distinct styles:

1. **ABP resource permissions** — permissions defined per resource type, granted per resource key, managed through the Permission Management module. Best for admin-managed, per-instance grants.
2. **Standard ASP.NET Core resource authorization** — pass a resource object plus a requirement/policy to `IAuthorizationService.AuthorizeAsync`, backed by a custom `AuthorizationHandler`. Best for rule-based logic (e.g. "owner or admin").

## Option 1 — ABP resource permissions

### Define the permissions

Define them in your `PermissionDefinitionProvider` using `context.AddResourcePermission(...)`:

```csharp
public class BookStorePermissionDefinitionProvider : PermissionDefinitionProvider
{
    public override void Define(IPermissionDefinitionContext context)
    {
        var myGroup = context.AddGroup("BookStore");

        // A standard permission that controls who may manage resource grants (required)
        myGroup.AddPermission(BookStorePermissions.Books.ManagePermissions, L("Permission:Books:ManagePermissions"));

        context.AddResourcePermission(
            name: BookStorePermissions.Books.Resources.Edit,           // unique permission name
            resourceName: BookStorePermissions.Books.Resources.Name,   // resource type id, e.g. "Acme.BookStore.Books.Book"
            managementPermissionName: BookStorePermissions.Books.ManagePermissions,
            displayName: L("Permission:Books:Edit")
        );
    }
}
```

`AddResourcePermission` parameters:

- `name`: unique permission name.
- `resourceName`: identifier for the resource *type* (typically the entity's full name, e.g. `Acme.BookStore.Books.Book`).
- `managementPermissionName`: a standard permission that gates who can grant/revoke these resource permissions.
- `displayName` (optional): localized display name for the UI.
- `multiTenancySide` (optional): `MultiTenancySides.Host`, `.Tenant`, or `.Both` (default).

### Check against a specific instance

Use `IAuthorizationService.IsGrantedAsync(resource, permissionName)` — available as `AuthorizationService` inside any `ApplicationService`. It internally uses `IResourcePermissionChecker` and reads the resource key via `IKeyedObject.GetObjectKey()`. All ABP entities implement `IKeyedObject`, so you can pass an entity directly:

```csharp
public virtual async Task UpdateAsync(Guid id, UpdateBookDto input)
{
    var book = await _bookRepository.GetAsync(id);

    var isGranted = await AuthorizationService.IsGrantedAsync(
        book, BookStorePermissions.Books.Resources.Edit);
    if (!isGranted)
    {
        throw new AbpAuthorizationException("You don't have permission to edit this book.");
    }

    book.Title = input.Title;
    await _bookRepository.UpdateAsync(book);
}
```

### Check several permissions at once

Inject `IResourcePermissionChecker` for batch checks. Here you pass the resource key explicitly:

```csharp
var result = await _resourcePermissionChecker.IsGrantedAsync(
    new[]
    {
        BookStorePermissions.Books.Resources.View,
        BookStorePermissions.Books.Resources.Edit,
        BookStorePermissions.Books.Resources.Delete
    },
    BookStorePermissions.Books.Resources.Name, // resourceName
    book.GetObjectKey()!);                      // resourceKey

var canEdit = result.Result[BookStorePermissions.Books.Resources.Edit]
    == PermissionGrantResult.Granted;
```

`IResourcePermissionChecker` signatures (from `IResourcePermissionChecker`):

- `Task<bool> IsGrantedAsync(string name, string resourceName, string resourceKey)`
- `Task<bool> IsGrantedAsync(ClaimsPrincipal? claimsPrincipal, string name, string resourceName, string resourceKey)`
- `Task<MultiplePermissionGrantResult> IsGrantedAsync(string[] names, string resourceName, string resourceKey)`
- `Task<MultiplePermissionGrantResult> IsGrantedAsync(ClaimsPrincipal? claimsPrincipal, string[] names, string resourceName, string resourceKey)`

For the single-instance case prefer `AuthorizationService.IsGrantedAsync(book, permissionName)` shown above (it reads the key from the entity for you). The `KeyedObjectResourcePermissionCheckerExtensions.IsGrantedAsync<TResource>(string permissionName, TResource resource)` overload also works — just be aware it does not take an explicit resource name: it derives `resourceName` from `typeof(TResource).FullName`, so it only matches a resource permission defined under that same name.

### Grant / revoke at runtime

Use `IResourcePermissionManager` to programmatically grant, revoke, and query resource permissions (e.g. auto-grant the creator when a resource is created, or implement sharing). The Permission Management module also ships built-in modal dialogs (MVC/Razor, Blazor, Angular) for admins. See the [Permission Management Module](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/modules/permission-management.md) docs.

## Option 2 — custom AuthorizationHandler with a resource

For rule-based checks, ABP extends `IAuthorizationService` so you can pass a resource plus a requirement or policy. From `AbpAuthorizationServiceExtensions`:

- `AuthorizeAsync(object resource, IAuthorizationRequirement requirement)` → `AuthorizationResult`
- `AuthorizeAsync(object resource, AuthorizationPolicy policy)`
- `AuthorizeAsync(object resource, string policyName)`
- `IsGrantedAsync(object resource, IAuthorizationRequirement requirement)` / `(object resource, string policyName)` → `bool`

These use the current principal automatically, so you don't have to pass `User`.

Write a standard ASP.NET Core `AuthorizationHandler<TRequirement, TResource>`:

```csharp
public class SameAuthorRequirement : IAuthorizationRequirement { }

public class BookAuthorHandler
    : AuthorizationHandler<SameAuthorRequirement, Book>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        SameAuthorRequirement requirement,
        Book resource)
    {
        var userId = context.User.FindFirst(AbpClaimTypes.UserId)?.Value;
        if (userId != null && resource.CreatorId?.ToString() == userId)
        {
            context.Succeed(requirement);
        }
        return Task.CompletedTask;
    }
}
```

Check it:

```csharp
var result = await AuthorizationService.AuthorizeAsync(book, new SameAuthorRequirement());
if (!result.Succeeded)
{
    throw new AbpAuthorizationException("You are not the author of this book.");
}
```

Register the handler explicitly against the `IAuthorizationHandler` service so the authorization system can resolve it — as written (no `ITransientDependency` / `[Dependency]`), this handler is not picked up by ABP's conventional DI at all, so register it yourself:

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    context.Services.AddTransient<IAuthorizationHandler, BookAuthorHandler>();
}
```

If you check by policy name, define the policy with `AddAuthorization` and attach the requirement.

## Choosing between them

- Grants that admins configure per instance, stored and manageable through the UI → **Option 1** (ABP resource permissions).
- Access derived from a rule (ownership, group membership, sharing table) evaluated in code → **Option 2** (custom handler).

## Validation

- The `PermissionDefinitionProvider` is auto-discovered, but a compile only checks types — whether it is loaded into the definition providers is a runtime concern. Confirm Option 1 wiring at runtime by resolving `IPermissionDefinitionManager` and querying the permission (or opening the "Permissions" modal).
- Option 1: grant a resource permission for one specific resource key (via the Permission Management UI or `IResourcePermissionManager`) and confirm `IsGrantedAsync(resource, name)` returns `true` only for that instance and `false` for others.
- Option 2: as the resource's creator confirm the handler calls `context.Succeed`; as a different user confirm the check fails — and confirm the handler is actually resolved (it is only picked up after you register it explicitly against `IAuthorizationHandler`).

## Common Pitfalls

- The custom `AuthorizationHandler` is **not** picked up by ABP conventional DI as written (no `ITransientDependency` / `[Dependency]`) — you must register it explicitly with `AddTransient<IAuthorizationHandler, ...>`, or it never runs.
- `KeyedObjectResourcePermissionCheckerExtensions.IsGrantedAsync<TResource>(name, resource)` derives `resourceName` from `typeof(TResource).FullName`, so it only matches a resource permission defined under that exact name — a mismatch silently fails to match.
- Option 1 requires a `managementPermissionName` (a standard permission) to gate who can grant/revoke resource permissions.
- For the single-instance check, prefer `AuthorizationService.IsGrantedAsync(book, permissionName)` (reads the key from the entity) over passing keys manually.

## References

- `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/fundamentals/authorization/resource-based-authorization.md`
- `IResourcePermissionChecker`: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Authorization.Abstractions/Volo/Abp/Authorization/Permissions/Resources/IResourcePermissionChecker.cs`
- `AbpAuthorizationServiceExtensions`: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Authorization/Microsoft/AspNetCore/Authorization/AbpAuthorizationServiceExtensions.cs`
