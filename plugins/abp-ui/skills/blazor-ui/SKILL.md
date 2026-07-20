---
name: blazor-ui
description: >
  Build and debug ABP Blazor UI — pages/components, base classes, render/hosting models, theming, and the Blazorise vs MudBlazor choice.
  USE FOR: creating Blazor pages/components, choosing a base class (AbpComponentBase / AbpCrudPageBase), calling application services from Blazor, picking a hosting/render model (Server / WebAssembly / WebApp / Auto), working with the LeptonX/Basic theme, deciding between Blazorise and MudBlazor components.
  DO NOT USE FOR: Angular UI (use angular-ui), MVC / Razor Pages UI (use mvc-razor-ui), menu contribution and localization resources/json (use menus-and-localization), permission definitions on the backend (use permissions-and-authorization).
license: MIT
---

# ABP Blazor UI

Guidance for building UI on top of ABP's Blazor stack. The core component APIs (e.g. `AbpComponentBase`) come from `Volo.Abp.AspNetCore.Components.*`; the Blazorise CRUD base classes (`AbpCrudPageBase`) come from `Volo.Abp.BlazoriseUI`.

## When to Use

- Creating or debugging Blazor pages/components in an ABP app.
- Choosing a base class (`AbpComponentBase` for custom pages, `AbpCrudPageBase` for CRUD screens).
- Calling application services from Blazor (in-process or over the dynamic HTTP client proxies).
- Picking a hosting/render model: Blazor Server, WebAssembly, or the .NET 8+ Blazor WebApp / Auto render modes.
- Working with the LeptonX or Basic theme, or deciding between the Blazorise and MudBlazor component libraries.

## When Not to Use

- **Angular UI** — use the **angular-ui** skill.
- **MVC / Razor Pages UI** (`abp-*` tag helpers, `AbpPageModel`) — use the **mvc-razor-ui** skill.
- **Contributing menu items or defining localization resources/json** — use the **menus-and-localization** skill.
- **Defining backend permissions** — use the **permissions-and-authorization** skill.

## Component base classes

Inherit your `.razor` components / code-behind from ABP base classes to get injected framework services for free.

`AbpComponentBase` (namespace `Volo.Abp.AspNetCore.Components`) is the root base. It derives from `OwningComponentBase`, so it owns a DI scope. It exposes protected members you should reuse instead of re-injecting:

- `L` — an `IStringLocalizer` (see `LocalizationResource`, below).
- `Logger`, `LoggerFactory`
- `CurrentUser` (`ICurrentUser`), `CurrentTenant` (`ICurrentTenant`)
- `AuthorizationService` (`IAuthorizationService`)
- `Message` (`IUiMessageService`), `Notify` (`IUiNotificationService`), `Alerts`
- `ObjectMapper`, `Clock`
- `HandleErrorAsync(Exception)` — routes exceptions through `IUserExceptionInformer`.

Set `LocalizationResource` in your constructor / `OnInitialized` so `L["Key"]` resolves against your module's resource:

```csharp
public partial class BookList : AbpComponentBase
{
    public BookList()
    {
        LocalizationResource = typeof(MyProjectResource);
    }
}
```

`AbpCrudPageBase<TAppService, TEntityDto, TKey, ...>` (in `Volo.Abp.BlazoriseUI`, derives from `AbpComponentBase`) is a generic base for list/create/edit/delete pages backed by an `ICrudAppService`. It wires up `GetListAsync`, paging, create/update modals, and delete. Use it when the page is a straightforward CRUD screen over a crud app service; drop to `AbpComponentBase` for custom pages.

## Calling application services

Inject the application service **interface** (from the `.Application.Contracts` package) and call it directly. ABP resolves it either in-process (Blazor Server, or a monolith where the app layer runs in the same process) or over HTTP via the auto-generated dynamic C# client proxies (Blazor WebAssembly, or any client that references the HTTP API client package). Your component code is identical either way:

```razor
@inject IBookAppService BookAppService

@code {
    protected override async Task OnInitializedAsync()
    {
        var books = await BookAppService.GetListAsync(new GetBookListInput());
    }
}
```

The dynamic HTTP client proxies are registered by `AddHttpClientProxies` in the WebAssembly/client module — you don't hand-write an HTTP client.

## Hosting / render models

ABP supports three Blazor models; the framework packages map to them:

- **Blazor Server** — `Volo.Abp.AspNetCore.Components.Server.*`. Runs on the server over a SignalR circuit.
- **Blazor WebAssembly (WASM)** — `Volo.Abp.AspNetCore.Components.WebAssembly.*`. Runs in the browser; talks to the backend through the dynamic HTTP client proxies.
- **Blazor WebApp / Auto render modes** — the .NET 8+ unified "Blazor Web App" host that can mix `InteractiveServer`, `InteractiveWebAssembly`, and `InteractiveAuto` render modes. ABP Studio offers this as a template option.

Shared, host-agnostic pieces live in `Volo.Abp.AspNetCore.Components.Web.*`. There is also a MAUI Blazor host (`...Components.MauiBlazor.*`) for desktop/mobile.

When a component must run only on the server (e.g. direct DbContext access), keep it out of WASM-rendered paths; prefer app-service calls that work under any render mode.

## Theming: LeptonX vs Basic

ABP ships a **Basic** theme and the **LeptonX** theme (available as LeptonX Lite and the full LeptonX). Themes provide the layout, toolbar, menu rendering, and branding. Theme-specific Blazor bundling/theming packages live under `...Components.*.Theming` and `...Components.*.Theming.MudBlazor`. Menu items you contribute (see the menus-and-localization skill) are rendered by whichever theme is active.

## Blazorise vs MudBlazor

ABP Studio's Blazor templates offer **two component libraries**:

- **Blazorise** — the long-standing default; `AbpCrudPageBase` lives in `Volo.Abp.BlazoriseUI`.
- **MudBlazor** — the alternative option; framework support is under the `...Components.*.Theming.MudBlazor` packages.

They are not interchangeable at the markup level — component tags, layout primitives, and dialog/modal APIs differ. Before editing or generating a Blazor screen, confirm which library the project uses, and match existing components in that library rather than mixing the two.

## Where pages/components live

Pages and components live in the Blazor host/UI project (e.g. `*.Blazor`, or the `.Client` project for WebApp/WASM-rendered components), typically under `Pages/` and `Components/`. Reusable module UI ships in module `*.Blazor` packages. Follow the existing folder layout of the project.

## Validation

- The Blazor host builds and runs; a page inheriting `AbpComponentBase` compiles and its injected members (`L`, `CurrentUser`, `Message`, …) resolve at runtime without manual injection.
- `L["Key"]` renders the localized value (not the raw key) once `LocalizationResource` is set to your module's resource.
- App-service calls return data under any render mode — the same component works whether resolved in-process (Server) or over the dynamic HTTP client proxies (WASM).

## Common Pitfalls

- **Mixing Blazorise and MudBlazor** — the two libraries are not markup-compatible; component tags, layout primitives, and dialog/modal APIs differ. Confirm which library the project uses and match existing components rather than mixing the two.
- **Running server-only code in a WASM-rendered path** — a component that needs direct DbContext access must stay out of WASM-rendered paths; prefer app-service calls that work under any render mode.
- **Forgetting to set `LocalizationResource`** — without it, `L["Key"]` won't resolve against your module's resource.
- **Re-injecting framework services** — reuse the protected members on the base class (`L`, `Logger`, `CurrentUser`, `Message`, `Notify`, `ObjectMapper`, `Clock`, …) instead of injecting them again.
