---
name: angular-ui
description: >
  Build and debug ABP Angular UI — generated proxy services, routing/menu contribution, replaceable components, config/permission checks, and localization.
  USE FOR: calling app services through generated proxy services, adding routes/menu items with RoutesService, swapping components with ReplaceableComponentsService, reading config with ConfigStateService, checking permissions with PermissionService / *abpPermission, localizing with LocalizationService / the abpLocalization pipe.
  DO NOT USE FOR: generating or regenerating Angular service/model proxies with the NX-vs-plain generator (use abp-cli-commands), Blazor UI (use blazor-ui), MVC / Razor Pages UI (use mvc-razor-ui), defining localization resources and translating json (use menus-and-localization), backend permission definitions (use permissions-and-authorization).
license: MIT
---

# ABP Angular UI

Guidance for building UI on ABP's Angular stack. Core APIs live in `@abp/ng.core`; module-specific UI ships in `@abp/ng.*` and `@volo/abp.ng.*` packages.

## When to Use

- Calling your backend app services from components through the generated typed proxy services.
- Registering navigation/menu entries and lazy feature routes with `RoutesService`.
- Replacing a module's built-in component with `ReplaceableComponentsService`.
- Reading application config (user, features, settings) with `ConfigStateService` and checking policies with `PermissionService` / `*abpPermission`.
- Localizing with `LocalizationService` / the `abpLocalization` pipe.

## When Not to Use

- **Generating/regenerating ng-packs proxies, or the NX-vs-plain generator distinction** — use the **abp-cli-commands** skill (`abp generate-proxy -t ng` for a plain workspace, `npx nx g @abp/nx.generators:generate-proxy` for an NX workspace).
- **Blazor UI** — use the **blazor-ui** skill.
- **MVC / Razor Pages UI** — use the **mvc-razor-ui** skill.
- **Defining a localization resource and translating keys into every culture json** — use the **menus-and-localization** skill.
- **Defining backend permissions** — use the **permissions-and-authorization** skill.

## Package model

An ABP Angular app is composed from published npm packages, not hand-written module code:

- `@abp/ng.core` — the framework runtime: config state, permissions, localization, routing, HTTP proxy plumbing.
- `@abp/ng.theme.shared` / `@abp/ng.theme.basic` / `@abp/ng.theme.lepton-x` — layout + theming.
- `@abp/ng.identity`, `@abp/ng.setting-management`, `@abp/ng.tenant-management`, … — per-module UIs (equivalents live under `@volo/abp.ng.*`).

You import components/services from these packages and add your own feature code alongside generated proxies. The **ng-packs** monorepo (`packages/*`) is the source of the `@abp/ng.*` packages and is an NX workspace.

## Generated proxies

Proxies are the typed client for your backend app services. **Generating them is the CLI's job — use the abp-cli-commands skill** (`abp generate-proxy -t ng` for a plain workspace, `npx nx g @abp/nx.generators:generate-proxy` for an NX workspace). This skill covers *using* the result.

Know the output shape so you can consume it: per backend controller the generator writes a service (`*.service.ts`, `providedIn: 'root'`), DTO interfaces (`*.model.ts` / `models.ts`), separate enum files with ready-made option arrays, and `index.ts` barrels. Output typically lands under `src/app/proxy/` (aliased `@proxy` in generated apps).

## Calling application services

Inject the generated proxy service and call its methods; DTOs come from the generated models:

```typescript
import { Component, inject } from '@angular/core';
import { BookService, BookDto } from '@proxy/books';

@Component({ /* ... */ })
export class BookListComponent {
  private bookService = inject(BookService);
  books: BookDto[] = [];

  ngOnInit() {
    this.bookService.getList({ maxResultCount: 10 }).subscribe(res => {
      this.books = res.items ?? [];   // items is optional (ListResultDto<T>.items?: T[])
    });
  }
}
```

Proxy methods return `Observable`s and call the backend over the ABP dynamic API. No manual `HttpClient` wiring.

## Routing, lazy modules & menu contribution

Register navigation/menu entries with `RoutesService` (from `@abp/ng.core`, `providedIn: 'root'`). Call `.add([...])` with route config objects:

```typescript
import { RoutesService, eLayoutType } from '@abp/ng.core';
import { inject, provideAppInitializer } from '@angular/core';

// Register in your app config's providers so inject() runs in a valid injection context
export const BOOKS_ROUTE_PROVIDERS = [
  provideAppInitializer(() => {
    const routes = inject(RoutesService);
    routes.add([
      {
        path: '/books',
        name: '::Menu:Books',        // localization key or object
        iconClass: 'fas fa-book',
        order: 101,
        layout: eLayoutType.application,
        requiredPolicy: 'BookStore.Books',   // hides item unless granted
      },
    ]);
  }),
];
```

Route config supports `path`, `name`, `parentName` (for nesting), `order`, `iconClass`, `layout`, `requiredPolicy`. `eLayoutType` values: `application`, `account`, `empty`. Feature UIs are wired as lazy-loaded routes (`loadChildren` / standalone `loadComponent`) in the app's routing; protect them with `permissionGuard` (`data: { requiredPolicy: '...' }`).

## Replaceable components

Swap a module's built-in component for your own with `ReplaceableComponentsService` (from `@abp/ng.core`), keyed by the module's component-key enum:

```typescript
import { ReplaceableComponentsService } from '@abp/ng.core';
import { eIdentityComponents } from '@abp/ng.identity';
import { inject, provideAppInitializer } from '@angular/core';

// Register in your app config's providers so inject() runs in a valid injection context
export const IDENTITY_REPLACEMENT_PROVIDERS = [
  provideAppInitializer(() => {
    inject(ReplaceableComponentsService).add({
      component: MyRolesComponent,
      key: eIdentityComponents.Roles,
    });
  }),
];
```

Layout components use `eThemeSharedComponents` (`ApplicationLayoutComponent`, `AccountLayoutComponent`, `EmptyLayoutComponent`).

## Config state & permissions

`ConfigStateService` (`@abp/ng.core`) exposes the application configuration (current user, features, settings, localization) with `getOne(key)` / `getOne$(key)` and `getDeep(keys)` / `getDeep$(keys)`.

`PermissionService` (`@abp/ng.core`) checks granted policies. Call `inject()` in a
valid injection context (a component/service field or constructor):

```typescript
@Component({ /* ... */ })
export class BookListComponent {
  private readonly permissionService = inject(PermissionService);
  readonly canCreate = this.permissionService.getGrantedPolicy('BookStore.Books.Create');
}
```

Use `getGrantedPolicy$(key)` for the `Observable` form; combine keys with `&&` / `||`. In templates, the `*abpPermission` structural directive hides content unless granted:

```html
<button *abpPermission="'BookStore.Books.Create'">New book</button>
```

## Localization

`LocalizationService` (`@abp/ng.core`) resolves keys in `ResourceName::Key` form. `instant(key, ...params)` is synchronous; `get(key, ...params)` returns an `Observable`. In templates use the `abpLocalization` pipe:

```html
<h1>{{ '::Menu:Books' | abpLocalization }}</h1>
<span>{{ 'AbpAccount::PagerInfo' | abpLocalization:'20':'30':'50' }}</span>
```

Pass `{ key, defaultValue }` for a fallback. A leading `::` uses the app's default resource. Add new keys to the backend module's `Localization/**/*.json` for every culture — see the menus-and-localization skill.

## Validation

- Proxies generate only when the backend host is running; after `abp generate-proxy -t ng` (or the NX generator), the `src/app/proxy/` output compiles and `@proxy/...` imports resolve.
- A registered route appears in the menu (unless hidden by its `requiredPolicy`), and its lazy feature loads when navigated to.
- `*abpPermission` / `getGrantedPolicy` hides or shows content according to the current user's granted policies.
- The `abpLocalization` pipe renders the localized value; a raw `ResourceName::Key` on screen means the key is missing from the culture json.

## Common Pitfalls

- **Hand-editing generated proxy files as if permanent** — regenerating overwrites them. For (re)generating ng-packs proxies and the NX-vs-plain generator distinction, use the abp-cli-commands skill.
- **Running proxy generation before the backend host is up** — proxies are read from the running host's API definition; generate only after `dotnet run`.
- **Calling `inject()` outside a valid injection context** — register `RoutesService` / `ReplaceableComponentsService` setup in the app config's providers (e.g. `provideAppInitializer`) so `inject()` runs in a valid context.
- **Treating `ListResultDto<T>.items` as always present** — `items` is optional (`items?: T[]`); guard with `res.items ?? []`.
- **Missing a culture json entry** — a leading `::` uses the app's default resource; a key added to `en.json` but not the sibling culture files falls back to English or shows the raw key.
