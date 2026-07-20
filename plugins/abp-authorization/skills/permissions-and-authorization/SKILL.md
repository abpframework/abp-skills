---
name: permissions-and-authorization
description: >
  Define and check global named permissions in an ABP app (PermissionDefinitionProvider), protect app services/controllers with [Authorize], check grants via IAuthorizationService / IPermissionChecker, and read the current user through ICurrentUser.
  USE FOR: defining permissions and groups, granting to roles/users/clients, [Authorize] on services or controllers, programmatic IsGrantedAsync/CheckAsync checks, reading the current user / current principal (ICurrentUser, ICurrentPrincipalAccessor) — id, tenant, roles, claims, and temporarily changing the ambient principal.
  DO NOT USE FOR: access that depends on a specific entity instance ("this document") — use the authorize-resources skill; configuring the login/token server (OpenIddict) — use the configure-openiddict-authentication skill; refreshing claims mid-session — use the configure-dynamic-claims skill.
license: MIT
---

# Authorization in ABP

ABP builds on ASP.NET Core authorization and adds a **permission system**: named permissions are defined in code, granted to roles/users/clients, and checked with the standard `[Authorize]` attribute or programmatic APIs. Ground everything below in the real APIs shown here.

## When to Use

- Defining named permissions and permission groups in a `PermissionDefinitionProvider`.
- Protecting an application service, method, or MVC controller/action with `[Authorize("...")]`.
- Checking granted permissions programmatically via `IAuthorizationService` or `IPermissionChecker`.
- Reading the authenticated user (id, tenant, roles, claims) through `ICurrentUser`.
- Understanding how grants are stored/evaluated (role/user/client value providers, Permission Management module).

## When Not to Use

- **Access that depends on a specific entity instance** ("can edit *this* document") — use the **authorize-resources** skill instead.
- **Configuring the auth server / login / token issuance** (OpenIddict) — use the **configure-openiddict-authentication** skill.
- **Refreshing claims mid-session without re-login** — use the **configure-dynamic-claims** skill.

## Defining permissions

Create a class deriving from `PermissionDefinitionProvider` (namespace `Volo.Abp.Authorization.Permissions`) and override `Define`. It's auto-registered (`ITransientDependency`). Keep permission names in a `static` constants class so you reference them without magic strings.

```csharp
public static class BookStorePermissions
{
    public const string GroupName = "BookStore";

    public static class Books
    {
        public const string Default = GroupName + ".Books";   // "BookStore.Books"
        public const string Create  = Default + ".Create";
        public const string Edit    = Default + ".Edit";
        public const string Delete  = Default + ".Delete";
    }
}

public class BookStorePermissionDefinitionProvider : PermissionDefinitionProvider
{
    public override void Define(IPermissionDefinitionContext context)
    {
        var group = context.AddGroup(
            BookStorePermissions.GroupName,
            L("Permission:BookStore"));

        var books = group.AddPermission(
            BookStorePermissions.Books.Default,
            L("Permission:Books"));

        // Child permissions (nested under the parent for UI/organization).
        books.AddChild(BookStorePermissions.Books.Create, L("Permission:Create"));
        books.AddChild(BookStorePermissions.Books.Edit,   L("Permission:Edit"));
        books.AddChild(BookStorePermissions.Books.Delete, L("Permission:Delete"));
    }

    private static LocalizableString L(string name)
        => LocalizableString.Create<BookStoreResource>(name);
}
```

- `context.AddGroup(name, displayName)` returns a `PermissionGroupDefinition`. Group names must be unique.
- `group.AddPermission(name, displayName, multiTenancySide, isEnabled)` returns a `PermissionDefinition`.
- On a `PermissionDefinition`, `AddChild(...)` adds a nested permission. Nesting is a UI/organizational relationship, not a runtime rule — a child grant is checked on its own regardless of the parent (see the note under Common Pitfalls).
- `MultiTenancySides` (a `[Flags]` enum: `Tenant = 1`, `Host = 2`, `Both`) restricts where a permission applies. Default is `Both`. Use `MultiTenancySides.Host` for host-only features.
- `permission.WithProviders(...)` restricts which value providers can grant it (e.g. `ClientPermissionValueProvider.ProviderName` for machine-to-machine/client-only permissions). Empty = all providers allowed.

### Localizing display names

Display names are `ILocalizableString`. Use `LocalizableString.Create<TResource>("Permission:Xxx")` and add the keys to your module's localization JSON (e.g. `Localization/BookStore/en.json`):

```json
{
  "Permission:BookStore": "Book Store",
  "Permission:Books": "Book Management",
  "Permission:Create": "Create"
}
```

If a key is missing, the raw key text is shown, so keep the JSON in sync across locales.

## Checking authorization

### Declarative — `[Authorize]`

Put the permission name in `[Authorize("...")]` on an application service, method, or MVC controller/action. ABP maps each permission to an ASP.NET Core authorization policy of the same name automatically.

```csharp
[Authorize(BookStorePermissions.Books.Default)]      // whole service
public class BookAppService : ApplicationService, IBookAppService
{
    [Authorize(BookStorePermissions.Books.Create)]   // specific method
    public async Task<BookDto> CreateAsync(CreateBookDto input)
    {
        // ... create the book and return the DTO ...
        return new BookDto();
    }
}
```

### Programmatic — `IAuthorizationService`

Inject `IAuthorizationService`. ABP adds extension methods (in namespace `Microsoft.AspNetCore.Authorization`, from `AbpAuthorizationServiceExtensions`) that check the current user:

```csharp
// returns bool
if (await AuthorizationService.IsGrantedAsync(BookStorePermissions.Books.Delete))
{
    // ...
}

// throws AbpAuthorizationException when not granted
await AuthorizationService.CheckAsync(BookStorePermissions.Books.Delete);

// any of several
await AuthorizationService.IsGrantedAnyAsync(perm1, perm2);
```

`ApplicationService` and `AbpController` already expose an `AuthorizationService` property, so you usually don't inject it manually.

### `IPermissionChecker` for a specific permission

For a direct permission check (also usable outside a web request), inject `IPermissionChecker` (impl `PermissionChecker`):

```csharp
bool granted = await PermissionChecker.IsGrantedAsync(BookStorePermissions.Books.Edit);
// batch check:
MultiplePermissionGrantResult result = await PermissionChecker.IsGrantedAsync(new[] { permA, permB });
```

`IsGrantedAsync` returns `false` for an unknown, disabled, or wrong-multi-tenancy-side permission — checks never throw for those cases.

## The current user — `ICurrentUser`

Inject `ICurrentUser` (namespace `Volo.Abp.Users`) to read the authenticated user. Available on `ApplicationService`/`AbpController` as `CurrentUser`.

```csharp
if (CurrentUser.IsAuthenticated)
{
    Guid?  userId   = CurrentUser.Id;
    string? name    = CurrentUser.UserName;
    Guid?  tenantId = CurrentUser.TenantId;     // null on host side
    string[] roles  = CurrentUser.Roles;

    if (CurrentUser.IsInRole("admin"))
    {
        // ... admin-only logic ...
    }
}
```

Other members: `Email`, `EmailVerified`, `PhoneNumber`, `Name`, `SurName`, and `FindClaim(type)` / `FindClaims(type)` / `GetAllClaims()` for raw claims. `Id`, `UserName`, `TenantId`, etc. are `null` when not authenticated — always guard with `IsAuthenticated`.

## Current principal (advanced)

`ICurrentUser` reads its values from claims on the *current principal*. That principal is served by `ICurrentPrincipalAccessor` (namespace `Volo.Abp.Security.Claims`), the low-level service ABP itself uses whenever it needs the ambient `ClaimsPrincipal`. For a web request it returns `HttpContext.User`; outside a request (background jobs, console) it falls back to `Thread.CurrentPrincipal`. You rarely inject it directly — prefer `ICurrentUser` — but you need it to read uncommon claims off the raw principal or to switch the ambient user for a scope.

### Reading arbitrary claims

`ICurrentUser`'s claim methods (`FindClaim`, `FindClaims`, `GetAllClaims`) plus the extension helpers (in `CurrentUserExtensions`, namespace `Volo.Abp.Users`) cover most claim reads without touching the accessor:

```csharp
// Extension: value of a claim, or null. Generic overload parses to a struct.
string? sessionId = CurrentUser.FindClaimValue(AbpClaimTypes.SessionId);
int level = CurrentUser.FindClaimValue<int>("subscription_level");   // 0 if absent

// GetId() returns Id as a non-null Guid — throws if not authenticated,
// so use it only where you've already checked IsAuthenticated.
Guid userId = CurrentUser.GetId();
```

Use `AbpClaimTypes` constants (see below) for claim names rather than magic strings.

### Temporarily changing the ambient principal

`ICurrentPrincipalAccessor.Change(ClaimsPrincipal)` returns an `IDisposable`. It sets the given principal as current inside an `AsyncLocal`, and disposing the scope restores whatever was current before — so **always** use it in a `using` block. This is how you run a block of code *as another user* — a constructed principal for background work, a system/service identity, or an impersonated user — without any real login.

```csharp
public class ReportRunner : ITransientDependency
{
    private readonly ICurrentPrincipalAccessor _currentPrincipalAccessor;
    private readonly ICurrentUser _currentUser;

    public ReportRunner(
        ICurrentPrincipalAccessor currentPrincipalAccessor,
        ICurrentUser currentUser)
    {
        _currentPrincipalAccessor = currentPrincipalAccessor;
        _currentUser = currentUser;
    }

    public async Task RunAsAsync(Guid userId, string userName)
    {
        // Pass an authentication type so ClaimsIdentity.IsAuthenticated is true — without
        // it, ABP's ICurrentUser sees a UserId but ASP.NET Core authorization/middleware
        // still treat the principal as anonymous, which splits behavior. This only swaps
        // the ambient principal for the scope; it is not a real login or token validation.
        var principal = new ClaimsPrincipal(
            new ClaimsIdentity(
                new[]
                {
                    new Claim(AbpClaimTypes.UserId, userId.ToString()),
                    new Claim(AbpClaimTypes.UserName, userName)
                },
                authenticationType: "Impersonation"));

        using (_currentPrincipalAccessor.Change(principal))
        {
            // Inside here ICurrentUser, permission checks, and audit logging read this
            // principal. This does NOT change the tenant: multi-tenancy data filters use
            // ICurrentTenant, so wrap ICurrentTenant.Change(tenantId) as well if you also
            // need to run as a different tenant.
            var name = _currentUser.UserName;   // == userName
            await DoWorkAsync();
        }
        // Out here the original principal is restored.
    }
}
```

`CurrentPrincipalAccessorExtensions` adds overloads so you can pass a single `Claim`, an `IEnumerable<Claim>`, or a `ClaimsIdentity` instead of building the `ClaimsPrincipal` yourself. **Caveat:** the `Claim` / `IEnumerable<Claim>` overloads build a `ClaimsIdentity` **without** an authentication type, so `IsAuthenticated` is `false` — use the full `ClaimsPrincipal` form above (with an `authenticationType`) whenever authorization/middleware must see the user as authenticated.

```csharp
using (_currentPrincipalAccessor.Change(new Claim(AbpClaimTypes.UserId, userId.ToString())))
{
    // ...
}
```

The switch is scoped and `AsyncLocal`-based, so it flows across `await`s within the `using` but does not leak outside it. It changes only the ambient principal for this async flow — it does not sign anyone in or issue a token.

### `AbpClaimTypes` — claim name constants

`AbpClaimTypes` (static, `Volo.Abp.Security.Claims`) holds the claim-type strings ABP standardizes on: `UserId`, `UserName`, `Name`, `SurName`, `Email`, `EmailVerified`, `PhoneNumber`, `PhoneNumberVerified`, `Role`, `TenantId`, `EditionId`, `ClientId`, `SessionId`, `Picture`, `RememberMe`, and the impersonation set (`ImpersonatorUserId`, `ImpersonatorTenantId`, `ImpersonatorUserName`, `ImpersonatorTenantName`). Defaults for `UserId`/`UserName`/`Role`/`Email` map to `System.Security.Claims.ClaimTypes`, and `Name`/`SurName` to `ClaimTypes.GivenName`/`Surname`; the rest use short standard names (e.g. `TenantId` = `"tenantid"`).

They're mutable `get; set;` properties: set them once at startup if your identity provider emits different claim type names, and every ABP consumer (including `ICurrentUser`) follows. That's the reason to reference `AbpClaimTypes.UserId` instead of hard-coding `ClaimTypes.NameIdentifier` or `"sub"` — a hard-coded string breaks the moment the mapping is customized, and it won't track the property change.

## Permission management (granting)

Defined permissions are just *definitions*. Actual grants are stored and evaluated by value providers: `RolePermissionValueProvider`, `UserPermissionValueProvider`, `ClientPermissionValueProvider`. The **Permission Management** module (`Volo.Abp.PermissionManagement`) persists grants and powers the "Permissions" modal in the UI, where an admin grants permissions per role, user, or client. A user is granted a permission if any of their roles/direct grants/client grants allows it (and none prohibits it).

## How Identity and OpenIddict fit in (brief)

- **Identity module** (`Volo.Abp.Identity`) manages users, roles, and role/user assignments. Roles carry permission grants, so "grant a permission" in practice means granting it to a role and assigning the role to users. Its own permissions (`AbpIdentity.Users`, `AbpIdentity.Roles`, ...) are defined in `IdentityPermissionDefinitionProvider` — a good real-world reference.
- **OpenIddict** is the auth server: it authenticates users (login) and issues tokens (cookies for MVC/Blazor Server, access tokens for APIs/SPAs/mobile). It establishes *who* the user is; ABP's permission system decides *what* they may do. A remote API evaluates permissions from the current user's roles/identity against the Permission Management store (and its cache) — permission grants are **not** carried as token claims; ABP's dynamic-claims feature keeps the role/profile claims fresh (see configure-dynamic-claims), and permission changes take effect through the store, not by re-issuing the token.

## Validation

- The `PermissionDefinitionProvider` is auto-discovered (`ITransientDependency`), but a compile only checks types — whether the provider is actually loaded into the definition providers is a runtime concern. Confirm at runtime by resolving `IPermissionDefinitionManager` and querying your permission, or by opening the "Permissions" modal for a role/user and seeing your defined group and permissions appear with their localized display names.
- Call a `[Authorize("...")]`-protected endpoint as an unauthorized user and confirm it is rejected; grant the permission and confirm it succeeds.
- For programmatic checks, confirm `IsGrantedAsync` returns `false` (not an exception) for unknown/disabled permissions.

## Common Pitfalls

- A missing localization key shows the raw key text instead of the display name — keep the JSON in sync across all locales.
- Parent/child is a UI and organizational convention, not a runtime rule — `PermissionChecker` does not consult `PermissionDefinition.Parent`, and `PermissionManager.SetAsync` will set a child grant directly. The "Permissions" modal ties a child's checkbox to its parent for usability, but a child grant checks as granted on its own regardless of the parent's state.
- `MultiTenancySides` defaults to `Both`; a permission restricted to `Host` will read as not-granted on the tenant side (and vice versa), and `IsGrantedAsync` returns `false` rather than throwing.
- Group names must be unique across the app; a collision breaks definition.
- Defining a permission does not grant it — grants live in the Permission Management module via the value providers.
- A remote API evaluates permissions from the current user's roles/identity against the Permission Management store — permission grants aren't token claims; dynamic claims keep the role/profile claims fresh (see configure-dynamic-claims).
