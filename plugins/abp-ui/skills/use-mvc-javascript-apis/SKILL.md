---
name: use-mvc-javascript-apis
description: >
  Use ABP's browser JavaScript APIs in an MVC / Razor Pages app: generated JS service proxies + the DataTables adapter, plus the client-side abp.* surface (auth, localization, settings/features, messages, busy/block, events).
  USE FOR: calling an app service from client JS (acme.bookStore.books.book.getList(...)) via the dynamic proxy (/Abp/ServiceProxyScript) or static proxies (abp generate-proxy -t js), feeding a proxy into abp.libs.datatables.createAjax with normalizeConfiguration / rowAction / dataFormat, and the page abp.* APIs — abp.auth.isGranted, abp.localization.localize, abp.setting/abp.features, abp.message/abp.notify, abp.ui.block/setBusy, abp.event, abp.ajax.
  DO NOT USE FOR: C# typed HTTP client proxies (use consume-remote-services), running the proxy-generation CLI itself / its flags (use abp-cli-commands), exposing app services as HTTP APIs on the server (use expose-http-apis), general MVC page/modal/tag-helper/bundling work (use mvc-razor-ui).
license: MIT
---

# Use ABP JavaScript APIs in MVC / Razor Pages

Call your server-side application services from browser JavaScript through ABP's **JavaScript API Client Proxies** instead of hand-writing `$.ajax`. A proxy function **corresponds to** the C# method — ABP drops the `Async` suffix and camelCases the name, DTOs are serialized to JSON, and the call returns a jQuery Deferred/Promise (with a trailing `ajaxParams` option), so `acme.bookStore.authors.author.getList({ maxResultCount: 10 })` maps to `IAuthorAppService.GetListAsync(...)`. This skill also covers wiring a proxy into ABP's DataTables adapter, and the rest of the client-side `abp.*` API surface (auth, localization, settings/features, messages, busy/block, events) that page code uses alongside the proxies.

## When to Use

- You need to call an app service (`getList`, `get`, `create`, `update`, `delete`, …) from page JS.
- You want a server-bound data grid using `abp-table` + DataTables.
- You are deciding between the runtime (dynamic) and build-time (static) proxy.

## Two proxy systems

Both give the identical `acme.bookStore.authors.author.get(...)` calling surface; they differ in *when* the proxy JS is produced.

- **Dynamic (default):** generated at runtime. The layout automatically pulls the script from the `/Abp/ServiceProxyScript` endpoint. Easiest dev experience — nothing to regenerate when the API changes. Visit `/Abp/ServiceProxyScript` in the browser to see the emitted functions.
- **Static:** generated at development time with `abp generate-proxy -t js -u https://localhost:53929/` (server must be running). Slight runtime perf gain because the API definition isn't fetched at runtime, but you must **re-generate whenever the API changes**. Output lands under `ClientProxies` (e.g. `app-proxy.js`); import it with `<abp-script src="/client-proxies/app-proxy.js"/>`.

### Static requires disabling the dynamic proxy for that module

Otherwise both proxies register and you get duplicate/racing definitions. In the module's `ConfigureServices`:

```csharp
Configure<DynamicJavaScriptProxyOptions>(options =>
{
    options.DisableModule("app");
});
```

`"app"` is the main application; for a module, pass that module's name. `abp generate-proxy` also assumes `app` as the module name unless you pass `-m` / `--module`.

## Calling a proxy

```js
acme.bookStore.authors.author.getList({ maxResultCount: 10 })
    .then(function (result) { console.log(result.items); });

acme.bookStore.authors.author.delete('7245a066-5457-4941-8aa7-3004778775f0')
    .then(function () { abp.notify.info('Successfully deleted!'); });
```

- Proxy functions run on `abp.ajax` under the hood, so you get **automatic error handling** for free.
- **Return value is a jQuery Deferred object** — chain `.then` (result), `.catch` (error), `.always` (finally). It is not a raw value.
- **The LAST argument is always `ajaxParams`, not a business parameter.** It's an object that overrides the underlying AJAX options — easy to mistake for a real method arg:

```js
acme.bookStore.authors.author
    .delete('7245a066-5457-4941-8aa7-3004778775f0', { timeout: 10000, headers: { 'X-Demo-Header': 'value' } })
    .then(function () { abp.notify.info('Successfully deleted!'); });
```

`ajaxParams` accepts [jQuery.ajax](https://api.jquery.com/jQuery.ajax/) options — but don't override the HTTP method, URL, content type, or data type the proxy generates (e.g. don't turn a `DELETE` into a `POST` or force an `xml` response); use it for `timeout`, extra headers, `beforeSend`, and similar.

## DataTables integration

The startup templates ship [DataTables.Net](https://datatables.net/) pre-installed and bundled. Add a table and call `.DataTable(...)` on it, wrapping the config in ABP's normalizer and feeding the proxy through ABP's AJAX adapter:

```html
<abp-table striped-rows="true" id="BooksTable"></abp-table>
```

```js
var dataTable = $('#BooksTable').DataTable(
    abp.libs.datatables.normalizeConfiguration({
        serverSide: true,
        paging: true,
        order: [[1, "asc"]],
        searching: false,
        ajax: abp.libs.datatables.createAjax(acme.bookStore.books.book.getList),
        columnDefs: [
            {
                title: l('Actions'),
                rowAction: {
                    items: [
                        { text: l('Edit'), action: function (data) { /* ... */ } }
                    ]
                }
            },
            { title: l('Name'), data: "name" },
            { title: l('CreationTime'), data: "creationTime", dataFormat: 'datetime' },
            { title: l('Price'), data: "price" }
        ]
    })
);
```

### `createAjax` — the adapter (do not skip it)

DataTables and ABP use **different request/response shapes** for paging and sorting. `abp.libs.datatables.createAjax(proxyFn)` translates between them and works with the proxy system. **Passing the proxy function straight into DataTables' `ajax` is NOT equivalent** — the paging/sorting params and the `{ items, totalCount }` response won't line up.

Customize request params and/or response with the optional 2nd/3rd args:

```js
var inputAction = function (requestData, dataTableSettings) {
    return { id: $('#Id').val(), name: $('#Name').val() };
};
var responseCallback = function (result) {
    return { recordsTotal: result.totalCount, recordsFiltered: result.totalCount, data: result.items };
};
ajax: abp.libs.datatables.createAjax(acme.bookStore.books.book.getList, inputAction, responseCallback)
```

If you only need to add fixed request params, pass a plain object as the 2nd arg:

```js
ajax: abp.libs.datatables.createAjax(acme.bookStore.books.book.getList, { id: $('#Id').val() })
```

### ABP extensions to the config (not native DataTables)

- **`normalizeConfiguration`** — sets `scrollX` (default `true` here), fills in column `targets` indexes, and sets `language` to localize the table. Defaults come from `abp.libs.datatables.defaultConfigurations` (`scrollX`, `dom`, `language`), which you can override.
- **`rowAction`** — a column-def option that renders a per-row actions dropdown. Each `items[]` entry supports: `text`, `action` (receives `data` with `data.record` = row object, `data.table` = DataTables instance), `confirmMessage` (function returning a confirmation string), `visible` (bool or function → bool; commonly `abp.auth.isGranted('BookStore.Books.Delete')`), `enabled` (function → bool), `iconClass`, `displayNameHtml`. If no item is visible, the actions column isn't rendered.
- **`dataFormat`** — column option for built-in rendering without a custom `render`: `boolean` (check/times icon), `date`, `datetime`. Register new formats via `abp.libs.datatables.defaultRenderers['name'] = function(value){ ... }`.

Reload after a mutating action:

```js
action: function (data) {
    acme.bookStore.books.book.delete(data.record.id)
        .then(function () { abp.notify.info("Successfully deleted!"); data.table.ajax.reload(); });
}
```

## Browser JS APIs (beyond proxies)

Alongside the service proxies, ABP injects a client-side `abp.*` object into every page. These values **mirror server-side configuration** — permissions, localization, settings, features, and the current user are resolved on the server and serialized into the page (via the application configuration), so on the client you read them **synchronously, no request needed**.

**Auth (permissions/policies)** — against the current user's granted policies:

```js
if (abp.auth.isGranted('BookStore.Books.Delete')) { /* ... */ }
abp.auth.isAnyGranted('A', 'B');   // any granted
abp.auth.areAllGranted('A', 'B');  // all granted
```

**Current user** — a plain object; check `isAuthenticated` first (anonymous → fields `null`, `roles` `[]`):

```js
if (abp.currentUser.isAuthenticated) { console.log(abp.currentUser.userName); }
// id, tenantId, userName, name, surName, email, roles, ...
```

**Localization** — reuses the server-side resources; an unlocalized key returns the key itself:

```js
var res = abp.localization.getResource('BookStore');
res('HelloWorld');                                  // localize
res('WelcomeMessage', 'John');                      // with {0} args
abp.localization.localize('HelloWorld', 'BookStore'); // shortcut (key, resource)
```

**Settings & features** — only those whose server definition allows client visibility are present:

```js
abp.setting.get('...'); abp.setting.getInt('...'); abp.setting.getBoolean('...');
abp.features.isEnabled('...'); abp.features.get('...');
abp.globalFeatures.isEnabled('...');
```

**AJAX (low-level)** — prefer proxies; `abp.ajax` wraps `$.ajax`, returns a promise, auto-handles+localizes errors, and auto-adds the anti-forgery (CSRF) token. Pass `abpHandleError: false` to opt out of the automatic error UI; a 401 auto-redirects to login.

**Messages (blocking) & notifications (toasts)** — `confirm`/`prompt` return **promises**:

```js
abp.message.confirm('Delete the "admin" role?')
   .then(function (confirmed) { if (confirmed) { /* ... */ } });
abp.message.success(msg, title);   // + info / warn / error
abp.notify.info(msg, title);       // auto-dismissing toast (+ success / warn / error)
```

**UI busy / block**, **events**, **DOM hooks**:

```js
abp.ui.block('#MySection'); abp.ui.unblock('#MySection'); abp.ui.setBusy('#MySection');
abp.event.on('basketUpdated', fn); abp.event.trigger('basketUpdated', basket); abp.event.off('basketUpdated', fn);
abp.dom.onNodeAdded(function (args) { /* init elements added after page load, e.g. via AJAX */ });
```

`abp.event` is **browser-only** pub/sub (unrelated to the server local/distributed event bus). `abp.dom` (backed by `MutationObserver`) fires for nodes added later — use it to initialize AJAX-inserted HTML. `abp.ResourceLoader.loadScript(url)` / `loadStyle(url)` fetch a file **once**.

## Validation

- **Dynamic proxy present:** open `/Abp/ServiceProxyScript` in the browser — your service's proxy functions appear there, and the object path (e.g. `acme.bookStore.books.book`) resolves in the JS console.
- **Static proxy present:** the `ClientProxies` / `app-proxy.js` file exists, is imported via `<abp-script>`, and — after `DisableModule` — the console shows exactly one definition of the proxy object (no dynamic one racing it).
- **Table works:** the grid pages/sorts server-side (network requests carry the translated paging/sort params) and the response `items` render; row actions run their `action` and `data.table.ajax.reload()` refreshes the grid.

## Common Pitfalls

- **Treating `ajaxParams` as a method parameter** — the trailing object overrides AJAX options; passing a business value there silently does nothing useful.
- **Awaiting the return as a plain value** — it's a jQuery Deferred; use `.then` / `.catch` / `.always`.
- **Enabling static proxies without `DisableModule`** — leaves the dynamic proxy live too, so both register. Disable the module in `DynamicJavaScriptProxyOptions`.
- **Forgetting to re-run `abp generate-proxy` after changing the API** — static proxies are frozen at generation time; dynamic ones update automatically.
- **Passing the proxy straight into DataTables `ajax`** — skips `createAjax`, so ABP's paging/sorting/response shape (`items`/`totalCount`) never gets adapted. Always wrap with `abp.libs.datatables.createAjax`.
- **Assuming `rowAction` / `dataFormat` / `normalizeConfiguration` are DataTables features** — they are ABP additions; they exist only when you go through ABP's adapter.
