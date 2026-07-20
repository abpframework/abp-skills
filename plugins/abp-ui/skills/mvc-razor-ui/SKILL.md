---
name: mvc-razor-ui
description: >
  Build and debug ABP MVC / Razor Pages UI — pages on AbpPageModel, abp-* tag helpers, the modal system, the bundling system, and per-page CSS/JS.
  USE FOR: writing pages on AbpPageModel, using abp-* tag helpers (abp-button, abp-modal, abp-dynamic-form, abp-input/select, …), the modal system (abp-modal + abp.ModalManager JS), bundling with AbpBundlingOptions / abp-script(-bundle) / abp-style(-bundle), co-locating page-specific CSS/JS.
  DO NOT USE FOR: Blazor UI (use blazor-ui), Angular UI (use angular-ui), the IMenuContributor menu pattern and translating localization json (use menus-and-localization), backend permission definitions (use permissions-and-authorization).
license: MIT
---

# ABP MVC / Razor Pages UI

Guidance for building UI on ABP's ASP.NET Core MVC / Razor Pages stack. Framework code lives under `Volo.Abp.AspNetCore.Mvc*` and the `Volo.Abp.AspNetCore.Mvc.UI.*` packages (tag helpers, bundling, theming).

## When to Use

- Writing Razor Page models on `AbpPageModel`.
- Rendering UI with `abp-*` tag helpers instead of raw Bootstrap markup.
- Building modals (a Razor Page wrapped in `abp-modal`, opened via `abp.ModalManager`).
- Configuring bundles with `AbpBundlingOptions` and emitting them with the bundle tag helpers.
- Co-locating and registering page-specific CSS/JS with `abp-script` / `abp-style`.

## When Not to Use

- **Blazor UI** — use the **blazor-ui** skill.
- **Angular UI** — use the **angular-ui** skill.
- **Contributing menu items or translating localization json** — use the **menus-and-localization** skill (the menu section below only points there).
- **Defining backend permissions** — use the **permissions-and-authorization** skill.

## Page base class

Derive Razor Page models from `AbpPageModel` (namespace `Volo.Abp.AspNetCore.Mvc.UI.RazorPages`). It extends ASP.NET Core's `PageModel` and gives you framework services (resolved lazily through `LazyServiceProvider`) instead of re-injecting them:

- `L` — an `IStringLocalizer`; set `LocalizationResourceType` to bind it to your module's resource.
- `CurrentUser`, `CurrentTenant`, `AuthorizationService`, `SettingProvider`
- `ObjectMapper` (set `ObjectMapperContext` to pick a profile), `GuidGenerator`, `Clock`, `Logger`
- `Alerts` / `AlertManager`, `UnitOfWorkManager` / `CurrentUnitOfWork`
- `CheckPolicyAsync(policyName)`, `ValidateModel()`, `RedirectSafelyAsync(returnUrl)`

```csharp
public class CreateModalModel : AbpPageModel
{
    public CreateModalModel()
    {
        LocalizationResourceType = typeof(MyProjectResource);
    }

    public async Task OnGetAsync() { /* L["Key"], CurrentUser, ... */ }
}
```

## Where pages live

Razor Pages live under `Pages/` in the web project, grouped by feature (e.g. `Pages/Books/Index.cshtml` + `Index.cshtml.cs`, `CreateModal.cshtml` + `.cs`). Module UIs ship their own `Pages/` inside their `*.Web` packages. Each page pairs a `.cshtml` view with a `.cshtml.cs` model deriving from `AbpPageModel`.

## Tag helpers

ABP ships `abp-*` tag helpers (namespace `Volo.Abp.AspNetCore.Mvc.UI.Bootstrap.TagHelpers`) that render Bootstrap markup and honor the active theme. Verified examples:

```html
<abp-button button-type="Primary" text="@L["Save"]" icon="check" />
<abp-dynamic-form abp-model="@Model.Book" />   <!-- builds a form from a model + data annotations -->
```

- `<abp-button>` — attrs include `button-type` (`AbpButtonType`), `size`, `text`, `icon`, `icon-type`, `busy-text`, `disabled`.
- `<abp-dynamic-form>` — renders a full form from a bound model; skip properties with `[DynamicFormIgnore]`.
- Layout/form helpers also exist: `<abp-card>`, `<abp-row>`/`<abp-column>`, `<abp-input>`, `<abp-select>`, `<abp-modal>` (below). Match the tag helpers already used in the project rather than reaching for raw Bootstrap HTML.

## Modal system

A modal is a normal Razor Page (its own `.cshtml` + `AbpPageModel`) whose body is wrapped in the `abp-modal` tag helpers. The submit happens by posting a form, so wrap the **entire** `<abp-modal>` in a single `<form>` (matching modules like TenantManagement's `CreateModal.cshtml`) and put the fields in the body with `<abp-input>` / `<abp-select>` — the footer's Save button then submits that form:

```html
<form method="post" asp-page="/Books/CreateModal">
    <abp-modal size="Large">
        <abp-modal-header title="@L["NewBook"]" />
        <abp-modal-body>
            <abp-input asp-for="Book.Name" />
            <abp-input asp-for="Book.Price" />
        </abp-modal-body>
        <abp-modal-footer buttons="@(AbpModalButtons.Cancel | AbpModalButtons.Save)" />
    </abp-modal>
</form>
```

To build the whole form from a model instead of listing inputs, use `<abp-dynamic-form>` — it **renders as the `<form>` itself**, so make it the outermost element wrapping the modal and place the fields with `<abp-form-content />` (see the Docs module's `Create.cshtml`). Never nest an `<abp-dynamic-form>` inside another `<form>`. (It only emits its own submit button when `submit-button="true"`; the default does not, so it won't duplicate a footer Save.)

`<abp-modal>` attrs: `size` (`AbpModalSize`), `centered`, `scrollable`, `static`. On the calling page, open it from JS with the `abp.ModalManager` global (defined in `.../Theme.Shared/.../bootstrap/modal-manager.js`):

```js
var createModal = new abp.ModalManager(abp.appPath + 'Books/CreateModal');
createModal.open();       // loads the page's HTML into a Bootstrap modal
createModal.onResult(function () { dataTable.ajax.reload(); });
```

`new abp.ModalManager(viewUrl)` (or an options object) returns a manager with `open`, `close`, `reopen`, `onOpen`, `onResult`. It posts the modal form and raises the result callback on success.

## Bundling

ABP has its own bundling system configured via `AbpBundlingOptions` (namespace `Volo.Abp.AspNetCore.Mvc.UI.Bundling`) in your module's `ConfigureServices`:

```csharp
Configure<AbpBundlingOptions>(options =>
{
    options.ScriptBundles
        .Configure(StandardBundles.Scripts.Global, bundle =>
        {
            bundle.AddFiles("/global-scripts.js");
        });
});
```

`AbpBundlingOptions` exposes `ScriptBundles` / `StyleBundles`, plus `Mode` (`BundlingMode`), `DeferScriptsByDefault`, `PreloadStylesByDefault`. Reusable bundle content is added via an `IBundleContributor` / `BundleContributor`. Bundles are emitted with the bundle tag helpers `<abp-script-bundle name="...">` and `<abp-style-bundle name="...">`.

## Page-specific CSS/JS

Convention: co-locate a page's assets next to the `.cshtml` (e.g. `Index.cshtml` + `Index.cshtml.js` + `Index.cshtml.css`) and register them per page inside `@section scripts` / `@section styles` using the single-file tag helpers `<abp-script>` / `<abp-style>` (verified `[HtmlTargetElement("abp-script")]`):

```cshtml
@section scripts {
    <abp-script src="/Pages/Books/Index.cshtml.js" />
}
@section styles {
    <abp-style src="/Pages/Books/Index.cshtml.css" />
}
```

These minify/version the file and slot it into the right bundle. Prefer them over raw `<script>`/`<link>` so ABP's minification and cache-busting apply.

## Menu contribution

MVC/Razor navigation uses the same `IMenuContributor` mechanism as the rest of ABP (`context.Menu.AddItem(new ApplicationMenuItem(...))`, gated on `StandardMenus.Main`), registered through `AbpNavigationOptions`. See the menus-and-localization skill for the full pattern and the rule about translating any new localization keys into every culture's json.

## Validation

- The web project builds and the page renders; a model deriving from `AbpPageModel` compiles and its lazily-resolved services (`L`, `CurrentUser`, `Alerts`, …) are available without manual injection.
- `abp-*` tag helpers emit themed Bootstrap markup; a modal opened via `abp.ModalManager` loads the page's HTML and fires `onResult` after a successful post.
- `abp-script` / `abp-style` and the bundle tag helpers produce versioned (cache-busted) output rather than raw asset tags — the output is minified only when minification is enabled (`BundleAndMinify`, or `Auto` outside Development).

## Common Pitfalls

- **Inventing tag helper names** — verify a tag helper exists first (`Volo.Abp.AspNetCore.Mvc.UI.Bootstrap/TagHelpers/**`). A tag helper maps to its element via an explicit `[HtmlTargetElement("abp-…")]` or, absent that, via Razor's class-name naming convention (e.g. `AbpModalTagHelper` has no `[HtmlTargetElement]` yet still binds to `<abp-modal>`).
- **Nesting `<abp-dynamic-form>` inside another `<form>`** — it renders as the `<form>` itself; make it the outermost element wrapping the modal and place fields with `<abp-form-content />`.
- **Wrapping only part of the modal in the form** — wrap the *entire* `<abp-modal>` in a single `<form>` so the footer Save button submits it.
- **Using raw `<script>` / `<link>` / raw Bootstrap HTML** — prefer `abp-script` / `abp-style` and `abp-*` tag helpers so cache-busting and theming apply (and minification when it's enabled, i.e. `BundleAndMinify` or `Auto` outside Development); match the tag helpers already used in the project.
