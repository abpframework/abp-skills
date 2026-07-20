---
name: menus-and-localization
description: >
  Contribute navigation menu items, and add/translate the localization json text a module's menus and UI display.
  USE FOR: adding or editing menu items (IMenuContributor, context.Menu.AddItem, StandardMenus.Main), adding keys to Localization/**/en.json and translating them into the other culture json files, using IStringLocalizer / L["Key"] to display those keys in C# and Razor.
  DO NOT USE FOR: defining and registering a framework localization resource — AbpLocalizationOptions.Resources.Add(...), AddVirtualJson, resource inheritance, culture fallback, business-exception / data-annotation localization (use localize-applications); Blazor components/render models (use blazor-ui); Angular routes and the abpLocalization pipe (use angular-ui); MVC tag helpers and bundling (use mvc-razor-ui); backend permission definitions (use permissions-and-authorization).
license: MIT
---

# ABP Menus & Localization

The shared, UI-agnostic mechanism ABP uses for navigation menus and localization resources/json. The Blazor, Angular, and MVC UI skills all point here for the menu contribution and json-translation rules.

## When to Use

- Adding or editing navigation menu items with `IMenuContributor` / `ApplicationMenuItem`.
- Adding keys to `Localization/**/en.json` and translating them into the sibling culture json files.
- Consuming localized strings via `IStringLocalizer<TResource>` in C# or `L["Key"]` in Razor.

## When Not to Use

- **Framework-specific UI wiring** — Blazor components/render models (**blazor-ui**), Angular routes and the `abpLocalization` pipe (**angular-ui**), MVC tag helpers and bundling (**mvc-razor-ui**). Those skills point here for the shared menu + localization backend.
- **Defining backend permissions** — use the **permissions-and-authorization** skill.

## Contributing menu items

Implement `IMenuContributor` (namespace `Volo.Abp.UI.Navigation`) and register it in your module's `AbpNavigationOptions`.

```csharp
public class MyProjectMenuContributor : IMenuContributor
{
    public async Task ConfigureMenuAsync(MenuConfigurationContext context)
    {
        if (context.Menu.Name != StandardMenus.Main)
        {
            return;
        }

        var l = context.GetLocalizer<MyProjectResource>();

        context.Menu.AddItem(
            new ApplicationMenuItem(
                name: "MyProject.Books",
                displayName: l["Menu:Books"],
                url: "/books",
                icon: "fas fa-book",
                order: 2)
        );

        await Task.CompletedTask;
    }
}
```

Register in `ConfigureServices`:

```csharp
Configure<AbpNavigationOptions>(options =>
{
    options.MenuContributors.Add(new MyProjectMenuContributor());
});
```

Key facts (verified against source):

- `MenuConfigurationContext.Menu` is an `ApplicationMenu`; `context.Menu.Name` tells you which menu is being built.
- Standard menu names live in `StandardMenus`: `StandardMenus.Main` (`"Main"`), `StandardMenus.User` (`"User"`), `StandardMenus.Shortcut` (`"Shortcut"`). Gate your contributions on the one you want.
- `AddItem(ApplicationMenuItem)` exists on both `ApplicationMenu` and `ApplicationMenuItem` (for nesting sub-items), and returns the parent for chaining.
- `ApplicationMenuItem` constructor params: `name` (unique), `displayName`, and optional `url`, `icon`, `order` (default `1000`, lower = earlier), `target`, `elementId`, `cssClass`, `groupName`, and a trailing, deprecated `requiredPermissionName` (its backing property is `[Obsolete]` — new code uses `RequirePermissions`). Nest children with `.AddItem(...)`.
- `context.GetLocalizer<TResource>()` / `context.GetLocalizer(type)` returns an `IStringLocalizer` for building localized display names. To conditionally hide items, use `context.IsGrantedAsync(policyName)` before adding.

## Localization

Defining the resource itself — the `[LocalizationResourceName]` marker class, registering it with `AbpLocalizationOptions.Resources.Add<T>()`, `AddVirtualJson`, resource inheritance (`AddBaseTypes` / `[InheritResource]`), culture fallback, and the `AbpVirtualFileSystemOptions.AddEmbedded<T>()` embedding — is the **localize-applications** skill. This skill assumes the resource already exists and covers the day-to-day work on top of it: adding a text key a menu or view needs, translating it across cultures, and displaying it.

### The json files

One file per culture in the resource folder, e.g. `Localization/MyProject/en.json`:

```json
{
  "culture": "en",
  "texts": {
    "Menu:Books": "Books",
    "BookName": "Book name"
  }
}
```

Each file has `"culture"` matching its filename and a `"texts"` map of key → translated string. `"texts"` is usually a flat map, but nested JSON objects are also supported: nested keys are flattened by joining the levels with `__` (so `{ "Menu": { "Books": "Books" } }` resolves as `Menu__Books`).

### Using localized strings in code

Inject `IStringLocalizer<TResource>` in C#, or use the `L` shortcut in ABP Blazor/MVC base classes:

```csharp
public class BookAppService
{
    private readonly IStringLocalizer<MyProjectResource> _localizer;
    public BookAppService(IStringLocalizer<MyProjectResource> localizer) => _localizer = localizer;
    // _localizer["BookName"]
}
```

In Razor (component inheriting an ABP base with `LocalizationResource` set, or an MVC page):

```razor
<h2>@L["Menu:Books"]</h2>
```

`L["Key"]` resolves to the value from the current culture's json (falling back to the resource's configured default culture — `en` in the templates, but it's whatever `DefaultCultureName` the resource sets). For HTML-encoded output in MVC Razor pages, ASP.NET Core's `IHtmlLocalizer<TResource>` is also available (`@inject IHtmlLocalizer<MyProjectResource> HtmlL`).

## Validation

- The added menu item appears under the targeted menu (`StandardMenus.Main` etc.), respecting `order` and any `IsGrantedAsync` gating.
- `L["Key"]` / `_localizer["Key"]` renders the translated value for the current culture and falls back to `en` when a culture is missing the key.
- If `@L["X"]` renders the raw key `X`, that key is missing from the json — add it to all culture files.

## Common Pitfalls

- **Adding a key only to `en.json`** — adding a key means adding it to *every* language file in the folder. A key present in `en.json` but missing elsewhere falls back to English (or shows the raw key), which reads as a bug. Add the same key to the sibling `zh-Hans.json`, `de.json`, `tr.json`, `fr.json`, etc. — with a real translation, not the English text.
- **Not gating on the menu name** — contributions run for every menu; return early unless `context.Menu.Name` matches the menu you want (e.g. `StandardMenus.Main`).
- **`"culture"` not matching the filename** — the loader builds each dictionary from the json's own `"culture"` (`CultureName`) value, not the filename (the filename is only used for enumeration/ordering). Keep the `"culture"` value aligned with the filename as a convention so the folder stays readable, but the `"culture"` inside the file is what actually determines the culture.
- **Reusing a non-unique menu item `name`** — `ApplicationMenuItem.name` must be unique.
