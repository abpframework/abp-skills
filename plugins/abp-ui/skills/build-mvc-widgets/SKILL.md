---
name: build-mvc-widgets
description: >
  Build reusable ABP MVC / Razor Pages widgets — a ViewComponent marked [Widget] that ships its own scripts, styles and bundle contributors, plus a client-side refresh lifecycle so consumers don't wire up dependencies by hand.
  USE FOR: turning a ViewComponent into a widget with [Widget] / AbpWidgetOptions, declaring a widget's StyleFiles/ScriptFiles/StyleTypes/ScriptTypes, server-side refresh via RefreshUrl, client refresh via abp.WidgetManager and abp.widgets (init/refresh/getFilters), AutoInitialize, dashboards with filter forms, and per-widget authorization (RequiresAuthentication / RequiredPolicies).
  DO NOT USE FOR: general MVC pages / modals / abp-* tag helpers / the bundling system itself (use mvc-razor-ui), overriding a built-in module's UI components (use customize-application-modules), Blazor or Angular UI (use blazor-ui / angular-ui).
license: MIT
---

# Building ABP MVC / Razor Pages Widgets

A **widget** is an ASP.NET Core ViewComponent extended by ABP so it can carry its own **script & style dependencies**, participate in the **bundling** and **authorization** systems, and be **refreshed** (server- or client-side) from a dashboard. The payoff is the non-obvious part: a page that renders a widget never has to include the widget's JS/CSS or its transitive libraries — the widget declares them and ABP injects them. Types live in `Volo.Abp.AspNetCore.Mvc.UI.Widgets`.

## When to Use

- You have (or want) a ViewComponent that owns script/style files and should not force consumers to manage those dependencies.
- You are building a **dashboard**: multiple widgets refreshed together, driven by a shared filter form.
- A widget must reload from the server (`RefreshUrl`) or update itself client-side from a JSON payload.
- A widget should only render for authenticated/authorized users.

## Workflow

### 1. Make a ViewComponent and mark it `[Widget]`

Start from a normal ViewComponent (inheriting `AbpViewComponent` is optional — plain `ViewComponent` works; `AbpViewComponent` just adds base properties). Add `[Widget]` to register it:

```csharp
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.AspNetCore.Mvc.UI.Widgets;

[Widget]
public class MySimpleWidgetViewComponent : AbpViewComponent
{
    public IViewComponentResult Invoke() => View();
}
```

The widget **name** is the type name minus the `ViewComponent` suffix (`MySimpleWidget`). Customize it with the standard `[ViewComponent(Name = "MyCustomNamedWidget")]` attribute — ABP respects it. `InvokeAsync(...)` may take arguments like any ViewComponent.

### 2. Render it

Standard ViewComponent rendering — by name or type, with an anonymous object for arguments:

```xml
@await Component.InvokeAsync("MySimpleWidget")
@await Component.InvokeAsync("CountersWidget", new { startDate = ..., endDate = ... })
```

### 3. Declare dependencies on the `[Widget]` attribute

This is what makes it a widget rather than a ViewComponent. Two ways:

```csharp
// Simple file paths (physical or virtual — integrated with the Virtual File System)
[Widget(
    StyleFiles = new[] { "/Pages/Components/MySimpleWidget/Default.css" },
    ScriptFiles = new[] { "/Pages/Components/MySimpleWidget/Default.js" })]

// Bundle contributors — full power of the bundling system (pull in libraries as deps)
[Widget(
    StyleTypes = new[] { typeof(MySimpleWidgetStyleBundleContributor) },
    ScriptTypes = new[] { typeof(MySimpleWidgetScriptBundleContributor) })]
```

A contributor is a `BundleContributor` overriding `ConfigureBundle`:

```csharp
public class MySimpleWidgetScriptBundleContributor : BundleContributor
{
    public override void ConfigureBundle(BundleConfigurationContext context)
    {
        context.Files.AddIfNotContains("/Pages/Components/MySimpleWidget/Default.js");
    }
}
```

Resources for all widgets used on a page are emitted as a **bundle**. Use contributors when the widget depends on a JS library — declare it once and it's added only if not already present. (For the bundling system itself, see the mvc-razor-ui skill.)

### 4. Optional: display name & authorization

```csharp
[Widget(
    DisplayName = "MySimpleWidgetDisplayName",              // localization key
    DisplayNameResource = typeof(DashboardDemoResource),    // localization resource
    RequiresAuthentication = true,                          // bool: logged-in users only
    RequiredPolicies = new[] { "MyPolicyName" })]           // string[] of policy names
```

### 5. Configure via `AbpWidgetOptions` instead of the attribute (optional)

Everything the `[Widget]` attribute does is also doable in a module's `ConfigureServices`:

```csharp
Configure<AbpWidgetOptions>(options =>
{
    options.Widgets
        .Add<MySimpleWidgetViewComponent>()
        .WithStyles("/Pages/Components/MySimpleWidget/Default.css");
});
```

`options.Widgets.Find` returns an existing `WidgetDefinition` so you can adjust a widget defined inside a module you depend on.

## Refresh: server-side vs client-side (two different mechanisms)

- **Server refresh — `RefreshUrl`.** Set `[Widget(RefreshUrl = "Widgets/Counters")]` and expose a matching endpoint (e.g. an `AbpController` action) that returns `ViewComponent("CountersWidget", ...)`. On refresh the widget is **re-rendered on the server** and the returned HTML replaces the old markup.
- **Client refresh.** The widget gets data (usually JSON) from the server and updates **itself in the browser** via its JavaScript API — no server re-render.

These are distinct: `RefreshUrl` triggers a full server re-render (the client `init` path); the client `refresh` function does in-place DOM updates. Pick one per widget.

## Client-side lifecycle: `abp.WidgetManager` + `abp.widgets`

A widget's JS API is registered on `abp.widgets` under the **exact server widget name**; all functions are optional:

```js
(function () {
    abp.widgets.NewUserStatisticWidget = function ($wrapper) {
        var getFilters = function () { return { /* widget's own filters */ }; };
        var init = function (filters) { /* first load / full re-load */ };
        var refresh = function (filters) { /* in-place update */ };
        return { getFilters: getFilters, init: init, refresh: refresh };
    };
})();
```

Drive one or more widgets with a `WidgetManager` (create it in `document.ready` — it touches the DOM):

```js
$(function () {
    var mgr = new abp.WidgetManager('#MyDashboardWidgetsArea');
    mgr.init();      // calls each widget's init
    mgr.refresh();   // calls each widget's refresh (or re-renders via RefreshUrl)
});
```

**Filter form** — link a form to a widgets area so submitting it refreshes all of them with the form fields as filters:

```xml
<div id="MyDashboardWidgetsArea" data-widget-filter="#MyDashboardFilterForm"> ...widgets </div>
```

Equivalent via the constructor options object: `{ wrapper, filterForm }`, or `filterCallback` for full control (return any object of fields; the default serializes the form via `serializeFormToObject()`). The returned filters are passed to every widget's `init` and `refresh`.

### `AutoInitialize`

`[Widget(AutoInitialize = true)]` (default `false`) makes ABP create a `WidgetManager` and `init` each instance automatically on page-ready **and whenever the widget is added to the DOM** — so it covers widgets loaded/refreshed via AJAX and **nested** widgets (a widget inside another). Use it when widgets work independently and don't need to be grouped under one `WidgetManager`; use an explicit `WidgetManager` when several widgets must init/refresh **together** (e.g. a shared dashboard filter).

## Validation

- The web project builds; the ViewComponent with `[Widget]` renders through `Component.InvokeAsync`.
- Rendering the widget on a page injects its `StyleFiles`/`ScriptFiles` (or the files added by its `StyleTypes`/`ScriptTypes` contributors) into the page bundle — you did **not** add them on the consuming page and they still appear.
- `RefreshUrl`: hitting the declared route returns the widget's re-rendered HTML.
- Client side: `new abp.WidgetManager(area)` with `init()` / `refresh()` invokes the matching `abp.widgets.<Name>` functions; submitting the `data-widget-filter` form refreshes the widgets with the form fields.
- With `RequiredPolicies` / `RequiresAuthentication`, an unauthorized user does not get the widget.

## Common Pitfalls

- **JS name mismatch.** `abp.widgets.<X>` must equal the **server widget name** (type name minus `ViewComponent`, or the `[ViewComponent(Name=...)]` override) — otherwise `WidgetManager` never calls your `init`/`refresh`.
- **Custom name but wrong view path.** If the widget name no longer matches its folder, render an explicit view path (e.g. `View("~/Pages/Components/MySimpleWidget/Default.cshtml")`).
- **Adding the widget's JS/CSS on the consuming page by hand.** Declare them on the widget (`StyleFiles`/`ScriptFiles` or `StyleTypes`/`ScriptTypes`) — the whole point is that consumers don't manage dependencies.
- **Confusing the two refresh paths.** `RefreshUrl` re-renders on the server and replaces the HTML; the client `refresh` function updates the DOM from data. They're separate mechanisms.
- **AJAX-inserted or nested widgets not initializing.** A one-shot manual `init` won't catch widgets added to the DOM later — use `AutoInitialize = true` (it also handles nesting), or re-run the manager after insertion.
- **`RefreshUrl` without an endpoint.** Declaring `RefreshUrl` requires a matching route that returns the widget (`ViewComponent(...)`); without it, refresh has nothing to fetch.

## See Also

- ABP docs: `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/ui/mvc-razor-pages/widgets.md`.
