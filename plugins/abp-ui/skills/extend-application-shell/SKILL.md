---
name: extend-application-shell
description: >
  Extend the ABP application shell/layout across MVC and Blazor with layout hooks, global/page toolbars, the page header, and branding — without copying the theme layout.
  USE FOR: injecting content into the layout via AbpLayoutHookOptions + LayoutHooks (MVC ViewComponent hooks; Blazor Razor Component hooks + the App.razor LayoutHook component for the head); adding global toolbar items with StandardToolbars.Main + IToolbarContributor; setting page title/breadcrumb/toolbar via IPageLayout (MVC) or the PageHeader component (Blazor); customizing app name/logo with IBrandingProvider / DefaultBrandingProvider.
  DO NOT USE FOR: replacing or overriding a built-in module's own pages/components (use customize-application-modules); adding navigation menu items (use menus-and-localization); general MVC or Blazor page building (use mvc-razor-ui / blazor-ui); Angular shell customization (use angular-ui).
license: MIT
---

# Extend the ABP Application Shell

Guidance for extending the ABP **application shell** — the layout, toolbar, page header, and branding — across ASP.NET Core MVC / Razor Pages and Blazor. The point of this skill is that ABP ships the layout inside the **theme NuGet packages**, so the shell has documented extension points that are *not* derivable from plain ASP.NET Core or Blazor.

## When to Use

- Injecting content (analytics script, banner, `<head>` tags) into every page via layout hooks.
- Adding a global item (notification bell, custom control) to the shell's main toolbar.
- Setting a page's title, breadcrumb, or page-level toolbar.
- Changing the application name / logo shown in the shell.

## When Not to Use

- **Replacing a module's own page/component** — use the **customize-application-modules** skill.
- **Adding menu items** — use the **menus-and-localization** skill.
- **Building ordinary MVC or Blazor pages** — use **mvc-razor-ui** / **blazor-ui**.
- **Angular shell customization** — use the **angular-ui** skill.

## The core non-obvious rule: don't copy the layout

ABP's theming system places the page layout into the theme NuGet packages. The final application does **not** contain a `Layout.cshtml` (MVC) or `MainLayout.razor` (Blazor). You *can* copy the theme code into your solution and edit it freely — **but then you lose automatic theme updates** when you upgrade the theme package. The supported way to add content to the layout is the **Layout Hook System**, which lets you inject a component at defined hook points that every theme's layout implements.

## Layout Hooks

Register hooks in your module's `ConfigureServices` via `AbpLayoutHookOptions` and the `LayoutHooks` constants. **The component type differs by stack**:

- **MVC**: the hooked component is a **ViewComponent** (e.g. deriving from `AbpViewComponent`).
- **Blazor**: the hooked component is a **Razor Component**.

**MVC** — add a `ViewComponent` at the last position of the `<head>`:

```csharp
Configure<AbpLayoutHookOptions>(options =>
{
    options.Add(
        LayoutHooks.Head.Last,             // the hook point
        typeof(GoogleAnalyticsViewComponent) // the component to add
    );
});
```

**Blazor** — add a Razor Component at the end of the `<body>`:

```csharp
Configure<AbpLayoutHookOptions>(options =>
{
    options.Add(
        LayoutHooks.Body.Last,
        typeof(AnnouncementComponent)
    );
});
```

### Hook points

- MVC: `LayoutHooks.Head.First`, `LayoutHooks.Head.Last`, `LayoutHooks.Body.First`, `LayoutHooks.Body.Last`, **plus** `LayoutHooks.PageContent.First` and `LayoutHooks.PageContent.Last` (just before/after `@RenderBody()`).
- Blazor: `LayoutHooks.Head.First`, `LayoutHooks.Head.Last`, `LayoutHooks.Body.First`, `LayoutHooks.Body.Last` (no `PageContent.*`).

### Scoping to a layout

By default a hook is added to **all** layouts. Pass `layout:` to target one, using the `StandardLayouts` constants:

```csharp
options.Add(LayoutHooks.Head.Last, typeof(GoogleAnalyticsViewComponent),
    layout: StandardLayouts.Application);
```

MVC defines four standard layouts on `StandardLayouts`: `Application` (main/default — header, menu, footer, toolbar), `Account` (login/register pages under `/Pages/Account`), `Public` (public-facing pages), and `Empty`. Blazor defines `Application`, `Account`, `Public`, and `Empty`. If you don't specify a layout, the component renders in all layouts.

### Multiple contributors

You (or the modules you use) can add **multiple items to the same hook point**; all of them render in the order they were added. This is why hooks (not layout copies) are the right extension point — several modules can extend the shell at once without conflicting.

### Blazor `<head>` hooks need a `LayoutHook` in `App.razor`

Blazor's `App.razor` is the entry point. To make `LayoutHooks.Head.*` actually render, you must place the `<LayoutHook>` component manually inside the `<head>` of `App.razor`:

```razor
@using Volo.Abp.AspNetCore.Components.Web.Theming.Components.LayoutHooks;
@using Volo.Abp.Ui.LayoutHooks;
@using Volo.Abp.AspNetCore.Components.Web.Theming.Layout;

<head>
    <LayoutHook Name="@LayoutHooks.Head.First" Layout="@StandardLayouts.Application" />
    <!-- your head content -->
    <LayoutHook Name="@LayoutHooks.Head.Last" Layout="@StandardLayouts.Application" />
</head>
```

After registering these, the components you added to those hook points render in place. (Body hooks work without this step.)

## Toolbars: global vs page-level

These are **two different mechanisms** — don't confuse them.

### Global toolbar (`StandardToolbars.Main`)

There is one standard toolbar named "Main", the `StandardToolbars.Main` constant. Modules and your app add items to it, and the theme renders it on the layout. To contribute an item globally, implement `IToolbarContributor`. As with hooks, the item is a **ViewComponent** in MVC and a **Razor Component** in Blazor:

```csharp
public class MyToolbarContributor : IToolbarContributor
{
    public Task ConfigureToolbarAsync(IToolbarConfigurationContext context)
    {
        if (context.Toolbar.Name == StandardToolbars.Main)
        {
            context.Toolbar.Items.Insert(0, new ToolbarItem(typeof(NotificationViewComponent)));
        }
        return Task.CompletedTask;
    }
}
```

Register the contributor via `AbpToolbarOptions`:

```csharp
Configure<AbpToolbarOptions>(options =>
{
    options.Contributors.Add(new MyToolbarContributor());
});
```

Gate items by permission with `context.IsGrantedAsync("MyPermissionName")`, or the `RequirePermissions("MyPermissionName")` extension on a `ToolbarItem` (more performant — ABP batches the checks). `IToolbarManager` returns items by toolbar name and is used by themes to render the toolbar; you rarely call it directly.

> A theme may define its own desktop/mobile toolbar constants (e.g. the LeptonX Lite theme's `LeptonXLiteToolbars.Main` / `LeptonXLiteToolbars.MainMobile`). Check `context.Toolbar.Name` against the one your theme uses.

### Page-level toolbar (Blazor only, via `PageHeader`)

A page's own toolbar is unrelated to the global Main toolbar. In Blazor, set it on the `PageHeader` component with a `PageToolbar` and its `AddButton` extension (see Page Header below).

## Page Header

### MVC — `IPageLayout`

Inject `IPageLayout` into any page/view to set header properties; the theme renders them:

```csharp
@inject IPageLayout PageLayout
@{
    PageLayout.Content.Title = "Book List";
    PageLayout.Content.BreadCrumb.Add("Language Management");
    PageLayout.Content.MenuItemName = "BookStore.Books";
}
```

- `Content.Title` also feeds the HTML `<title>` (alongside the brand name).
- `Content.BreadCrumb.Add(text, url?, icon?)`; toggle `BreadCrumb.ShowHome` / `BreadCrumb.ShowCurrent`.
- `Content.MenuItemName` must match a menu item name from the navigation system so the theme marks it active.

### Blazor — `PageHeader` component

Add the `PageHeader` component to a page and drive it with parameters. The namespace differs by UI library: `Volo.Abp.AspNetCore.Components.Web.Theming.Layout` (Blazorise) or `Volo.Abp.AspNetCore.Components.Web.Theming.MudBlazor.Layout` (MudBlazor).

```razor
<PageHeader Title="Book List"
            BreadcrumbItems="@BreadcrumbItems"
            Toolbar="@Toolbar" />
```

```csharp
protected List<BreadcrumbItem> BreadcrumbItems { get; } = new();
protected PageToolbar Toolbar { get; } = new();

protected override void OnInitialized()
{
    BreadcrumbItems.Add(new BreadcrumbItem("Language Management"));
    Toolbar.AddButton("New Item", () => Task.CompletedTask, icon: /* IconName.Add or MudBlazor.Icons.Material.Filled.Add */);
}
```

- The breadcrumb item type is `Volo.Abp.BlazoriseUI.BreadcrumbItem` (Blazorise) or `MudBlazor.BreadcrumbItem` (MudBlazor) — they are different types with different constructors.
- Toggle `BreadcrumbShowHome` / `BreadcrumbShowCurrent` parameters.
- Globally enable/disable sections with `PageHeaderOptions` (`RenderPageTitle`, `RenderBreadcrumbs`, `RenderToolbar` — all `true` by default).

> The Basic theme doesn't render breadcrumbs or (MVC) the selected menu item; LeptonX / LeptonX Lite do.

## Branding

Both stacks use `IBrandingProvider` (namespace `Volo.Abp.Ui.Branding`) for the app name and logo. Implement the interface or inherit `DefaultBrandingProvider`, and register it as a replacement service:

```csharp
[Dependency(ReplaceServices = true)]
public class MyProjectBrandingProvider : DefaultBrandingProvider
{
    public override string AppName => "Book Store";
    public override string? LogoUrl => "/logo.png";
    public override string? LogoReverseUrl => "/logo-reverse.png";
}
```

`IBrandingProvider` exposes `AppName`, `LogoUrl`, and `LogoReverseUrl` (logo for a reverse/dark theme). It's evaluated on every page refresh, so a multi-tenant app can return a tenant-specific name/logo.

## Validation

- The web/Blazor host builds and runs; the injected content appears on the layout at the chosen hook point across pages.
- A layout hook targeting `LayoutHooks.Body.*` renders without extra wiring; a `LayoutHooks.Head.*` hook in Blazor renders **only** after a matching `<LayoutHook>` is present in `App.razor`.
- A `StandardToolbars.Main` contributor's item shows in the shell toolbar; permission-gated items appear only when the permission is granted.
- `IPageLayout` (MVC) / `PageHeader` (Blazor) update the title/breadcrumb — verify against a theme that renders them (LeptonX), since the Basic theme skips breadcrumbs.
- The `IBrandingProvider` override changes the app name/logo shown in the shell after replacing the service.

## Common Pitfalls

- **Copying the theme layout to customize it** — you lose theme package upgrades. Use `AbpLayoutHookOptions` + `LayoutHooks` instead.
- **Blazor `<head>` hook does nothing** — you registered a `LayoutHooks.Head.*` component but didn't add the `<LayoutHook Name="..." Layout="..." />` to `App.razor`'s `<head>`.
- **Confusing the two toolbar mechanisms** — `StandardToolbars.Main` + `IToolbarContributor` is the *global shell* toolbar; a page's own buttons go on the Blazor `PageHeader`'s `PageToolbar`. They are unrelated.
- **Wrong component kind for a hook/toolbar item** — MVC hooks and toolbar items are **ViewComponents**; Blazor ones are **Razor Components**. They are not interchangeable.
- **Assuming `PageContent.*` hooks exist in Blazor** — those hook points are MVC-only; Blazor has `Head.*` and `Body.*` only.
- **Expecting breadcrumbs/selected-menu on the Basic theme** — those are rendered by LeptonX / LeptonX Lite, not the Basic theme.
- **Mixing Blazorise and MudBlazor breadcrumb types** — `Volo.Abp.BlazoriseUI.BreadcrumbItem` and `MudBlazor.BreadcrumbItem` are distinct; use the one matching the project's UI library and `PageHeader` namespace.
- **Forgetting `[Dependency(ReplaceServices = true)]`** on the branding provider — without it, `DefaultBrandingProvider` stays in effect.
