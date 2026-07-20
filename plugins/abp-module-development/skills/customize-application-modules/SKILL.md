---
name: customize-application-modules
description: >
  Extends or customizes a pre-built ABP module (Identity, Account, etc.) referenced as NuGet packages without editing its source.
  USE FOR: adding extra entity/DTO properties via the module extension system, mapping extra properties to real EF Core columns, replacing/overriding module services, repositories, domain services, and controllers, overriding module UI.
  DO NOT USE FOR: defining your own new application module from scratch (use define-application-modules); modeling your own aggregates/entities (use model-domain-aggregates); general object-to-DTO mapping mechanics (use map-objects-and-dtos).
license: MIT
---

# Customizing Application Modules Without Editing Their Source

When you use ABP's pre-built modules as NuGet package references, you can't change their source — but you can extend and override them through well-defined extension points. This keeps the module upgradeable (`abp update`) while letting you tailor behavior.

## When to Use

- Adding an extra property to a pre-built module's entity, DB, HTTP API, and UI from one place.
- Storing an extra property in a dedicated EF Core column instead of JSON.
- Exposing an extra property on a module's DTOs.
- Replacing or overriding a module's app services, domain services, repositories, or controllers.
- Overriding a module's UI pages/components.

## When Not to Use

- **Defining a brand-new application module of your own** — use define-application-modules; this skill is only about customizing modules you consume as packages.
- **Modeling your own domain aggregates/entities** — use model-domain-aggregates.
- **General object-to-object / entity-to-DTO mapping** — use map-objects-and-dtos; here mapping appears only for extra properties.

## Module Entity Extensions (add properties)

This is the main, high-level extension system. It adds a property to the entity, database, HTTP API, and UI from a single place. The module must be built with the extension system in mind — all official modules are.

Configure inside `YourProjectNameModuleExtensionConfigurator.ConfigureExtraProperties()` in the `Domain.Shared` project. It runs once at startup via `OneTimeRunner`.

```csharp
public static void ConfigureExtraProperties()
{
    OneTimeRunner.Run(() =>
    {
        ObjectExtensionManager.Instance.Modules()
            .ConfigureIdentity(identity =>
            {
                identity.ConfigureUser(user =>
                {
                    user.AddOrUpdateProperty<string>(
                        "SocialSecurityNumber",
                        property =>
                        {
                            property.Attributes.Add(new RequiredAttribute());
                            property.Attributes.Add(new StringLengthAttribute(64) { MinimumLength = 4 });
                        });
                });
            });
    });
}
```

- `ObjectExtensionManager.Instance.Modules()` is the entry point; `ConfigureIdentity` / `ConfigureUser` pick the module and entity (use IntelliSense to discover extensible ones).
- `AddOrUpdateProperty<T>` adds the property; calling it again for the same name reconfigures the same property.
- Validation via data annotation attributes works full-stack (UI, HTTP API, and `SetProperty` on the entity). `RequiredAttribute` is auto-added for non-nullable primitives/enums — make the property nullable (e.g. `int?`) to allow null, or call `property.Attributes.Clear()`.
- Control display, ordering, and visibility with `property.DisplayName`, `property.UI.Order`, `property.UI.OnTable/OnCreateForm/OnEditForm.IsVisible`, and API availability with `property.Api.OnCreate/OnUpdate/OnGet.IsAvailable`.

**Localize by convention:** add the property name (or `DisplayName:SocialSecurityNumber`) as a key in your `en.json` `texts` section.

**Dedicated DB column (EF Core):** by default values are stored as JSON in the `ExtraProperties` field. To use a real column, add mapping in `YourProjectNameEfCoreEntityExtensionMappings`, then run `Add-Migration` / `Update-Database`:

```csharp
ObjectExtensionManager.Instance
    .MapEfCoreProperty<IdentityUser, string>(
        "SocialSecurityNumber",
        (entityBuilder, propertyBuilder) => propertyBuilder.HasMaxLength(64));
```

### Extra properties on DTOs

Defining an extra property on an entity does **not** automatically expose it on DTOs (by design, for security). Define it explicitly on each DTO you want it in:

```csharp
ObjectExtensionManager.Instance
    .AddOrUpdateProperty<IdentityUserDto, string>("SocialSecurityNumber");
```

Add it to `IdentityUserCreateDto` / `IdentityUserUpdateDto` too if you want it settable. Passing an array of types adds it to several at once. It surfaces in the API's `extraProperties` object. To skip the entity-vs-DTO definition check, pass the `options` overload of `AddOrUpdateProperty` and set `CheckPairDefinitionOnMapping` there (it lives on `ObjectExtensionPropertyInfo`, not on the `ExtensionPropertyConfiguration` callback param):

```csharp
ObjectExtensionManager.Instance
    .AddOrUpdateProperty<IdentityUser, string>(
        "SocialSecurityNumber",
        options => options.CheckPairDefinitionOnMapping = false);
```

## Overriding Services

Any DI-registered class (app services, domain services, repositories, controllers, framework services) can be replaced. ABP makes module methods `virtual` by design so you can override them.

**Re-implement an interface** — matched by naming convention (both end with `IdentityUserAppService`); otherwise use `[ExposeServices]`. Explicitly replace to guarantee a single registration:

```csharp
[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(IIdentityUserAppService))]
public class MyIdentityUserAppService : IIdentityUserAppService, ITransientDependency
{
    //...
}
```

**Inherit and override one method** (most common). Expose the interface, the base class, and self so all injection paths resolve your class:

```csharp
[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(IIdentityUserAppService), typeof(IdentityUserAppService), typeof(MyIdentityUserAppService))]
public class MyIdentityUserAppService : IdentityUserAppService
{
    public MyIdentityUserAppService(/* base ctor deps */) : base(/* ... */) { }

    public override async Task<IdentityUserDto> CreateAsync(IdentityUserCreateDto input)
    {
        // custom logic before/after
        return await base.CreateAsync(input);
    }
}
```

**Replace by code** in your module's `ConfigureServices`:

```csharp
context.Services.Replace(
    ServiceDescriptor.Transient<IIdentityUserAppService, MyIdentityUserAppService>());
```

**Domain services** have no interface, so `[ExposeServices(typeof(IdentityUserManager))]` is **required** when inheriting `IdentityUserManager` (DI doesn't expose base classes by convention like it does interfaces).

**Repositories** override by naming convention (`MyEfCoreIdentityUserRepository` ends with `EfCoreIdentityUserRepository`). To make `IRepository<IdentityUser, Guid>` use it too:

```csharp
context.Services.AddDefaultRepository(
    typeof(Volo.Abp.Identity.IdentityUser),
    typeof(MyEfCoreIdentityUserRepository),
    replaceExisting: true);
```

## Overriding Controllers

`[ExposeServices(typeof(AccountController))]` is essential — it registers your controller in place of the module's. `[Dependency(ReplaceServices = true)]` clears the old registration.

```csharp
[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(AccountController))]
public class MyAccountController : AccountController
{
    public MyAccountController(IAccountAppService accountAppService) : base(accountAppService) { }

    public override async Task SendPasswordResetCodeAsync(SendPasswordResetCodeDto input)
    {
        Logger.LogInformation("Your custom logic...");
        await base.SendPasswordResetCodeAsync(input);
    }
}
```

Because it defines `ExposeServicesAttribute`, `MyAccountController` is removed from the `ApplicationModel`. Use `IncludeSelf = true` to remove the base `AccountController` instead (useful when **extending**). To keep both, add your type to `AbpAspNetCoreMvcOptions.IgnoredControllersOnModelExclusion`.

## UI extension & override points

The entity-extension system adds properties to the UI automatically but doesn't override existing pages/components. To change the module UI itself without editing its source, use the per-stack mechanisms below.

### MVC / Razor Pages

**Override a page** three ways:

- *Page Model only (C#)*: derive from the module's page model and register the replacement with `[Dependency(ReplaceServices = true)]` + `[ExposeServices(typeof(TheModel))]`; override `OnGetAsync` / `OnPostAsync` around `base`.
- *Razor page only (.cshtml)*: drop a `.cshtml` at the **same path** as the module's page — the Virtual File System serves yours (add `_ViewImports.cshtml` for ABP tag helpers).
- *Completely*: derive a new page model (without replacing), override the `.cshtml`, and point its `@model` at yours.

View components (e.g. the theme `Brand`) and static resources (js/css/images) override the same way — same path wins via the Virtual File System. Add/replace bundle files through `AbpBundlingOptions` (`StandardBundles.Styles.Global` / `StandardBundles.Scripts.Global`, or a page bundle keyed by `typeof(SomeModule.IndexModel).FullName`).

**Row/table/toolbar extensions:**

- *Entity actions*: `abp.ui.extensions.entityActions.get('identity.user').addContributor(actionList => …)` — `actionList` is a doubly-linked list (`addTail`/`addHead`/`dropHead`); ship the js via a page bundle.
- *Data table columns*: `abp.ui.extensions.tableColumns.get('identity.user').addContributor((columnList[, order]) => …)`; each column has `title`/`data`/`render`. (For an extra property, prefer module entity extensions.)
- *Page toolbar*: `AbpPageToolbarOptions.Configure<SomeModule.IndexModel>(toolbar => toolbar.AddButton(...))` / `AddComponent<TViewComponent>()`, gate with `requiredPolicyName`, or implement `IPageToolbarContributor` / `PageToolbarContributor` and add it to `toolbar.Contributors`.

Layout-level hooks (`IMenuContributor` + `StandardMenus.Main`/`.User`, `IToolbarContributor` + `AbpToolbarOptions` + `StandardToolbars.Main`, `AbpLayoutHookOptions` + `LayoutHooks.Head.Last`) belong to the application shell — see the extend-application-shell skill.

### Blazor

Override/replace a module or theme component by inheriting it and registering the replacement via DI:

```razor
@inherits Branding
@attribute [ExposeServices(typeof(Branding))]
@attribute [Dependency(ReplaceServices = true)]
```

`@inherits` the component being replaced (from the active theme namespace, e.g. the Basic theme's `...BasicTheme.Themes.Basic` for Blazorise, or the MudBlazor theme namespace); `ExposeServices` + `Dependency(ReplaceServices = true)` swap it in, and inheriting keeps the original's non-private members. The same attributes work from a `.razor.cs` code-behind. Pages are components, so the same applies to module pages.

### Angular

Two distinct systems — don't confuse them:

1. **Full component replacement** — `ReplaceableComponentsService.add({ component, key })` with keys from enums like `eIdentityComponents` / `eThemeBasicComponents`. Covered in the **angular-ui** skill; use it to swap an entire component or layout.
2. **Extension points** — add fields/columns/actions *without* replacing the component. Build contributor constants keyed by the module's component enum and register them by passing them to the module's `createRoutes({ … })` in `app.routes.ts` (or `SomeModule.forLazy({ … })` for legacy NgModule). All extension classes live in `@abp/ng.components/extensible`; contributor lists are doubly-linked (`addTail`/`addHead`/`addByIndex`/`dropByValue`).

   | Extension | Class / options | Route option |
   | --- | --- | --- |
   | Entity actions | `EntityAction` / `EntityActionOptions`, `EntityActionList` | `entityActionContributors` |
   | Table columns | `EntityProp` / `EntityPropOptions` (`ePropType`, `valueResolver`), `EntityPropList` | `entityPropContributors` |
   | Page toolbar | `ToolbarAction` / `ToolbarComponent` (+ `…Options`), `ToolbarActionList` | `toolbarActionContributors` |
   | Form fields | `FormProp` / `FormPropOptions` (`validators`, `asyncValidators`, `template`), `FormPropList` | `createFormPropContributors` / `editFormPropContributors` |

   Action/prop callbacks receive `ActionData` / `PropData` (`record`, `index`, `getInjected`). Custom toolbar/form components read context via the `EXTENSIONS_ACTION_DATA` / `EXTENSIONS_FORM_PROP` injection tokens.

These are all framework extension points — none are license-gated in the ABP docs.

## Validation

- After adding an extra property, confirm it appears in the module's create/edit form and table (per your `property.UI.*` settings) and in the API's `extraProperties` object.
- For a dedicated EF Core column, run `Add-Migration` / `Update-Database` and confirm the real column exists (values no longer only in the JSON `ExtraProperties`).
- After overriding a service/controller, confirm your override runs (e.g. hit the endpoint and observe your custom log/behavior) and that DI resolves your type on every injection path you exposed.

## Common Pitfalls

- Prefer package references (upgradeable) over including module source; use these extension points first. Only include source (`abp add-module --with-source-code`) when the extension points aren't enough.
- An extra entity property is **not** exposed on DTOs automatically (by design, for security) — define it on each DTO explicitly, and on the Create/Update DTOs to make it settable.
- `RequiredAttribute` is auto-added for non-nullable primitives/enums; make the property nullable or `property.Attributes.Clear()` to allow null.
- When inheriting a **domain service** (no interface), `[ExposeServices(typeof(TheManager))]` is required — DI won't expose base classes by convention the way it does interfaces.
- Overriding a controller removes it from the `ApplicationModel` because it defines `ExposeServicesAttribute`; use `IncludeSelf = true` to remove the base instead, or add to `AbpAspNetCoreMvcOptions.IgnoredControllersOnModelExclusion` to keep both.
- If a method you need isn't `virtual`, report it to the ABP repo — they intend everything to be overridable.
