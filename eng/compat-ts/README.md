# TypeScript compile-smoke tests

The active smoke test covers `abp-ui/angular-ui` with the public `@abp/ng.core`
package (config state, permissions, routing, localization APIs, the route model,
layout enum, and the permission guard the skill uses).

Run it with:

```bash
npm ci
npm ls @abp/ng.core @angular/core   # fail on an invalid dependency tree
npm run build
```

The packages are pinned so a lockfile update is an explicit compatibility
change. The Angular smoke pins `@abp/ng.core` to **10.5.0**, matching the C#
compile-smoke's `<AbpVersion>` (`eng/compat/Directory.Packages.props`); bump both
together when moving to a new ABP release.

> `@abp/ng.theme.shared` is intentionally not part of the smoke: at 10.5.0 it
> pulls `@swimlane/ngx-datatable`, whose Angular peer range lags the Angular
> version the ABP template pins, which produces an invalid (`npm ls`-failing)
> tree. Keeping the smoke on `@abp/ng.core` keeps the dependency tree valid.

Only the Angular UI stack is covered by this smoke. React, React Native, and
MAUI are not covered here.
