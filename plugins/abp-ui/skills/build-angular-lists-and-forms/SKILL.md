---
name: build-angular-lists-and-forms
description: >
  Build ABP Angular list and form pages the framework way — server-side paged/sorted/filtered lists via ListService, and reactive forms with ABP's automatic validation.
  USE FOR: ListService with component-scoped providers, hookToQuery returning PagedResultDto, get() refresh, page/maxResultCount/filter/sortKey/sortOrder setters, requestStatus$ (isLoading$ is deprecated), totalCount, LIST_QUERY_DEBOUNCE_TIME, reactive forms validated automatically by @ngx-validate/core, DEFAULT_VALIDATION_BLUEPRINTS + withValidationBluePrint localization keys, abp-validation-error, the skipValidation opt-out, and config-driven abp-dynamic-form (DynamicFormComponent + FormFieldConfig).
  DO NOT USE FOR: proxy consumption, menus, permission directives (angular-ui); proxy generation/regeneration (abp-cli-commands); adding entity/table/toolbar/form-prop extensions to a shipped module (extend-angular-module-ui); component testing (test-angular-ui); server-side application-service or DTO design (build-crud-application-services).
license: MIT
---

# Build Angular Lists and Forms (ABP)

ABP's Angular UI ships two pieces of infrastructure that AI models routinely re-implement by hand: `ListService` for server-side paged data, and automatic reactive-form validation. Use them instead of hand-rolling paging state or manual error markup.

## When to Use

- A list/table page bound to a paged ABP endpoint (`GetListAsync(input)` returning `PagedResultDto<T>`).
- Server-side paging, sorting, and search whose subscriptions are cleaned up on component destroy (not leaked).
- A reactive create/edit form that should show ABP's localized validation messages automatically.
- An arbitrary (non-entity) form you want to drive from a config array rather than template markup.

## When Not to Use

- **Consuming generated proxies, menu routes, permission directives** — use **angular-ui**.
- **Generating/regenerating the proxies** (`abp generate-proxy -t ng` or the NX generator) — use **abp-cli-commands**.
- **Adding columns/actions/form fields to a *shipped* module's page** (Identity, etc.) — use **extend-angular-module-ui**; that's the extension system, a different API.
- **Testing these components** — use **test-angular-ui**.
- **Designing the server-side app service / DTOs** — use **build-crud-application-services**.

## Lists with `ListService`

`ListService` (from `@abp/ng.core`) owns the query state (page, size, filter, sort) and re-runs the request when any of it changes. It **must be component-scoped** — put it in the component's `providers`, never `providedIn: 'root'` — so its subscriptions are cleaned up on destroy.

```ts
import { ListService, PagedResultDto } from '@abp/ng.core';
import { Component, inject, OnInit } from '@angular/core';
import { BookService, BookDto } from '../proxy/books';

@Component({
  selector: 'app-books',
  templateUrl: './books.component.html',
  providers: [ListService],            // component-scoped — REQUIRED
})
export class BooksComponent implements OnInit {
  readonly list = inject(ListService);
  private bookService = inject(BookService);

  items: BookDto[] = [];
  count = 0;
  requestStatus$ = this.list.requestStatus$;   // 'idle' | 'loading' | 'success' | 'error'

  ngOnInit() {
    // callback receives the composed query, returns Observable<PagedResultDto<T>>
    this.list
      .hookToQuery(query => this.bookService.getList(query))
      .subscribe(res => {
        this.items = res.items ?? [];
        this.count = res.totalCount ?? 0;      // read the count off the response
      });
  }
}
```

The query object `hookToQuery` passes to your callback is `{ filter, maxResultCount, skipCount, sorting }` — `sorting` is `"field asc|desc"` and `skipCount = page * maxResultCount`, which matches ABP's `PagedAndSortedResultRequestDto`.

- **Search:** two-way-bind an input to `list.filter`; the setter re-runs the query.
- **Sort:** set `list.sortKey` / `list.sortOrder` (from a table header click).
- **Page/size:** set `list.page` / `list.maxResultCount`.
- **Refresh after create/update/delete:** call `list.get()` (or `list.getWithoutPageReset()` to stay on the current page).
- **Extra query params:** spread the query — `query => this.bookService.getList({ ...query, authorId })`.

Debounce is `LIST_QUERY_DEBOUNCE_TIME` (default 300 ms); provide the token alongside `ListService` to change it.

## Reactive forms with automatic validation

ABP validates reactive forms through **`@ngx-validate/core`** and renders localized helper text automatically — you do **not** write per-field error `*ngIf` markup. Build a normal `FormGroup` with Angular validators; ABP shows the messages.

```ts
form = this.fb.group({
  name: ['', [Validators.required, Validators.maxLength(128)]],
  price: [0, [Validators.required, Validators.min(0)]],
});
```

Message text comes from `DEFAULT_VALIDATION_BLUEPRINTS` (from `@abp/ng.theme.shared`), which maps validator keys (`required`, `email`, `minlength`, …) to localization keys like `AbpValidation::ThisFieldIsRequired`. Override or extend them with `withValidationBluePrint(...)` passed into `provideAbpThemeShared(...)`.

- **Custom error rendering:** subclass the `abp-validation-error` component (`ValidationErrorComponent` from `@abp/ng.theme.basic`) and provide `VALIDATION_ERROR_TEMPLATE`.
- **Opt out:** put `skipValidation` on a `<form>` (whole form) or on a single `formControlName` input.

## Config-driven dynamic forms

For arbitrary (non-entity) forms, drive `<abp-dynamic-form>` (`DynamicFormComponent` from `@abp/ng.components/dynamic-form`) with a `FormFieldConfig[]` array — field types, validators, conditional visibility, nested groups/arrays — instead of writing template markup.

This is a **separate validation path** from the reactive-form `@ngx-validate/core` story above: `abp-dynamic-form` does **not** read the theme-shared validation blueprints. It validates from each field's `FormFieldConfig.validators` and renders its own error text (per-field `message`, with an English fallback), so don't expect the automatic localized blueprint messages here — set the message on the field config.

## Validation

- Page a list and confirm the network request carries `MaxResultCount`/`SkipCount`/`Sorting` and the grid updates; navigate away and back and confirm no leaked subscriptions (that's the component-scoped provider doing its job).
- Submit an invalid form and confirm ABP's localized message appears with **no** hand-written error markup.

## Common Pitfalls

- **`ListService` provided in root.** Then it never tears down and leaks across pages. Always component-scoped.
- **Reaching for `totalCount$` or `isLoading$`.** `totalCount$` does not exist — read `res.totalCount`. `isLoading$` exists but is **deprecated**; use `requestStatus$`.
- **Hand-writing paging state** (page index, skipCount math, debounce). `ListService` already does all of it; wiring your own fights it.
- **Manual validation markup.** `@ngx-validate/core` renders messages automatically once the control has Angular validators; adding your own `*ngIf` error blocks duplicates them.
- **Confusing the two "dynamic form" APIs.** `abp-dynamic-form` (config-driven, here) is not the entity-extension form (`generateFormFromProps` / `abp-extensible-form`) — that belongs to **extend-angular-module-ui**.
