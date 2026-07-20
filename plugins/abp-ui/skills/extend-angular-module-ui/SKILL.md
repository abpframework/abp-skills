---
name: extend-angular-module-ui
description: >
  Extend a shipped ABP Angular module's UI (Identity, etc.) through the extension system — add row/toolbar actions, columns, and create/edit form fields without forking.
  USE FOR: the five contributor buckets (entity/toolbar-action, entity-prop, create/edit-form-prop contributors) keyed by the module's component enum; the EntityAction/ToolbarAction/EntityProp/FormProp factories; ePropType; the LinkedList mutators addTail/addByIndex/addAfter/dropByIndex (there is no patch/remove/insertByIndex — patch is drop-plus-reconstruct); registering via createRoutes in a lazy loadChildren (or the deprecated Module.forLazy); EXTENSIONS_IDENTIFIER; the @abp/ng.components/extensible package.
  DO NOT USE FOR: building your own non-module list/form (build-angular-lists-and-forms); proxy consumption, menus, permission directives, replaceable components (angular-ui); adding server-side extra properties to the entity/DTO (extend-objects-with-extra-properties); component testing (test-angular-ui).
license: MIT
---

# Extend Angular Module UI (ABP)

ABP's shipped Angular modules (Identity, Tenant Management, …) expose their grids and create/edit forms to a **contributor** system so you can add actions, columns, and fields without forking the module. Models write these by hand or fork the component; the extension API is the supported path.

## When to Use

- Adding a row action, toolbar button, extra column, or extra create/edit field to a **shipped module's** page.
- Reordering or replacing an existing column/field on such a page.

## When Not to Use

- **Your own feature's list/form** (not a shipped module) — use **build-angular-lists-and-forms**.
- **Proxies, menus, permission directives, replaceable components** — use **angular-ui**.
- **Persisting the extra field on the backend** (the entity/DTO side) — use **extend-objects-with-extra-properties**; the UI contributor only renders it.
- **Testing** — use **test-angular-ui**.

## The five contributor buckets

Each module exposes a typed options object with five buckets, keyed by that module's **component enum**. Identity's, for example:

```ts
import { eIdentityComponents } from '@abp/ng.identity';
import { IdentityEntityActionContributors, IdentityEntityPropContributors } from '@abp/ng.identity';

export const identityEntityActionContributors: IdentityEntityActionContributors = {
  [eIdentityComponents.Users]: [ /* contributor callbacks */ ],
};
```

The buckets are `entityActionContributors` (row actions), `toolbarActionContributors` (page toolbar buttons), `entityPropContributors` (data-table columns), `createFormPropContributors` and `editFormPropContributors` (form fields — create and edit are separate). A contributor is a callback that receives the current list and mutates it.

## Building items and mutating the list

Items come from factories in `@abp/ng.components/extensible`: `EntityAction`, `ToolbarAction`, `EntityProp` (a column), `FormProp` (a field). Column/field types use the `ePropType` enum (`String`, `Boolean`, `Date`, `DateTime`, `Email`, `Enum`, `Number`, `Password`, `Text`, `Time`, `Typeahead`, …).

The list passed to a contributor is a **doubly-linked list**, so you position items explicitly:

```ts
import {
  EntityAction, EntityActionList,
  EntityProp, EntityPropList,
  FormProp, FormPropList, ePropType,
} from '@abp/ng.components/extensible';
import { IdentityUserDto } from '@abp/ng.identity/proxy';
import { Validators } from '@angular/forms';

// row action -> appended to the row dropdown
export function sayHi(actionList: EntityActionList<IdentityUserDto>) {
  actionList.addTail(new EntityAction<IdentityUserDto>({
    text: 'Say Hi',
    action: data => alert(data.record.userName),   // text + action are required
  }));
}

// custom column -> inserted right after userName
export function nameColumn(propList: EntityPropList<IdentityUserDto>) {
  propList.addAfter(
    new EntityProp<IdentityUserDto>({ type: ePropType.String, name: 'name', displayName: '::Name', sortable: true }),
    'userName',
    (value, name) => value.name === name,
  );
}

// create-form field -> inserted at index 4
export function birthday(propList: FormPropList<IdentityUserDto>) {
  propList.addByIndex(
    new FormProp<IdentityUserDto>({ type: ePropType.Date, name: 'birthday', displayName: '::Birthday', validators: () => [Validators.required] }),
    4,
  );
}
```

Mutators: `addTail` / `addHead` / `addByIndex(item, position)` / `addAfter(item, sibling, compareFn)` / `addBefore` / `add(item).byIndex(n)`, and the `dropByIndex` / `dropByValue` family. There is **no** `patch`, `remove`, or `insertByIndex` — to "patch" an existing column, `dropByIndex(i)` it, then re-add a `new EntityProp({ ...droppedNode.value, valueResolver })`.

## Registering the contributors

In the current standalone setup, pass the buckets to the module's `createRoutes(options)` in the lazy route:

```ts
{
  path: 'identity',
  loadChildren: () => import('@abp/ng.identity').then(c => c.createRoutes({
    entityActionContributors: identityEntityActionContributors,
    entityPropContributors: identityEntityPropContributors,
    createFormPropContributors: identityCreateFormPropContributors,
  })),
}
```

(The legacy NgModule path, `IdentityModule.forLazy(options)`, takes the same options object but is deprecated.) Each page binds its bucket via the `EXTENSIONS_IDENTIFIER` token it provides.

For `@volo/abp.ng.*` module UIs, follow that module's own documentation for its UI extension APIs.

## Validation

- Add a column and confirm it renders in the grid at the position you chose and sorts if `sortable`.
- Add a create-form field and confirm it appears in the modal, validates, and round-trips (with the backend extra-property wired separately).

## Common Pitfalls

- **Inventing `patch` / `remove` / `insertByIndex`.** They don't exist. Use `dropByIndex` + re-add for patch, the `drop*` family for remove, `addByIndex` / `add().byIndex()` for insert-at-index.
- **Wrong bucket for create vs edit.** Create and edit forms have separate buckets; adding to only one leaves the other unchanged.
- **Expecting the column to persist data.** The UI contributor renders a value; the entity/DTO extra property is a backend concern — see **extend-objects-with-extra-properties**.
- **Building your own feature's grid here.** That's **build-angular-lists-and-forms**; this skill is only for extending *shipped* modules' pages.
