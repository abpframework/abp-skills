---
name: test-angular-ui
description: >
  Write ABP Angular component/service unit tests using ABP's testing modules on the app's Vitest or Jest stack.
  USE FOR: CoreTestingModule.withConfig from @abp/ng.core/testing, ThemeSharedTestingModule.withConfig from @abp/ng.theme.shared/testing, ThemeBasicTestingModule.withConfig (takes no args) when the app uses theme.basic, the clearPage and wait helpers for body-level UI (modals, toasts, confirmation dialogs) jsdom doesn't tear down, TestBed.configureTestingModule with a standalone component placed in imports, mocking AuthService and other providers, and picking the runner per the target project (current template = Vitest; some packages still use Jest).
  DO NOT USE FOR: server-side/integration tests through the AbpIntegratedTest/*TestBase chain (test-abp-applications); MVC/Razor page or HTTP integration tests (test-mvc-razor-ui); building the components under test (build-angular-lists-and-forms, extend-angular-module-ui, angular-ui).
license: MIT
---

# Test Angular UI (ABP)

ABP ships Angular **testing modules** that stand in a config-provider-only version of the framework so a `TestBed` boots without a real backend. Use them instead of hand-wiring `RestService`/`PermissionService` fakes.

## When to Use

- Unit-testing an ABP Angular component or service with `TestBed`.
- A component that renders modals/toasts and needs the body cleaned up between tests.

## When Not to Use

- **Server-side integration tests** (app services, repositories, EF Core/Mongo) — use **test-abp-applications**.
- **MVC/Razor page or HTTP-level tests** — use **test-mvc-razor-ui**.
- **Writing the component itself** — use **build-angular-lists-and-forms** / **extend-angular-module-ui** / **angular-ui**.

## Set up the TestBed

Import `CoreTestingModule.withConfig()` (from `@abp/ng.core/testing`) — it swaps in a `CORE_OPTIONS` with `skipGetAppConfiguration: true` and mock `PermissionService`/`RestService`, so nothing calls a backend. Add `ThemeSharedTestingModule.withConfig()` (from `@abp/ng.theme.shared/testing`) when the component uses theme-shared pieces (validation, toasts). Standalone components go in `imports`.

```ts
import { CoreTestingModule } from '@abp/ng.core/testing';
import { ThemeSharedTestingModule } from '@abp/ng.theme.shared/testing';
import { AuthService } from '@abp/ng.core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { BooksComponent } from './books.component';

describe('BooksComponent', () => {
  let fixture: ComponentFixture<BooksComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        CoreTestingModule.withConfig(),
        ThemeSharedTestingModule.withConfig(),
        BooksComponent,        // standalone -> imports, not declarations
      ],
      providers: [
        { provide: AuthService, useValue: { isAuthenticated: false, navigateToLogin: vi.fn() } },
      ],
    }).compileComponents();
  });

  it('creates', () => {
    fixture = TestBed.createComponent(BooksComponent);
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });
});
```

`withConfig()` accepts overrides (`baseHref`, `routes`, `listQueryDebounceTime`, …); both testing modules also import `RouterTestingModule`, so routed components work. Add `ThemeBasicTestingModule.withConfig()` (from `@abp/ng.theme.basic/testing`, **no arguments**) only if the app uses `@abp/ng.theme.basic`.

## Body-level UI: `clearPage` and `wait`

Modals, toasts, and confirmation dialogs render into `document.body`, which jsdom doesn't tear down between tests. Both helpers come from `@abp/ng.core/testing`:

- `clearPage(fixture)` — removes leftover `abp-*` / `ngb-*` elements from the body. Call it in `afterEach` for components that open dialogs.
- `wait(fixture, timeout = 0)` — runs `detectChanges()` then resolves a `setTimeout`, to let body-level UI settle before asserting. Keep `timeout` at `0`.

## Runner

The **current generated app template** runs on **Vitest + jsdom** (test builder `@angular/build:unit-test`), and there's no Karma. But don't hard-code Vitest: some `@abp/ng.*` packages (e.g. `cms-kit`) still use an Nx **Jest** target, and existing apps may keep Jest. **First read the target project's `project.json` / `angular.json` / `package.json` scripts** to see which runner it uses, then match its API and mock syntax (`vi.*` for Vitest vs `jest.*` for Jest). Framework libraries additionally use `@ngneat/spectator`; app code uses plain `TestBed`.

## Validation

- Run the spec (`ng test` / the app's Vitest target) and confirm the component instantiates with no real HTTP calls.
- For a modal component, assert it opens, then confirm `clearPage` leaves the body empty for the next test.

## Common Pitfalls

- **Writing Jest config / Karma.** The current stack is Vitest + jsdom; copying old ABP Jest setup fights it.
- **Putting a standalone component in `declarations`.** Standalone components go in `imports`.
- **Skipping `clearPage`.** A modal from one test leaks into the next as stray `abp-*` body nodes and flakes assertions.
- **Adding `ThemeBasicTestingModule` unconditionally.** Only needed if the app actually uses `@abp/ng.theme.basic`; unlike the other two, its `withConfig()` takes no arguments.
