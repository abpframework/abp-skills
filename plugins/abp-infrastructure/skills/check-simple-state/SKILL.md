---
name: check-simple-state
description: "Composable ABP simple-state conditions on definitions and UI state objects. USE FOR: ISimpleStateChecker, ISimpleStateCheckerManager, permission/feature/authentication conditions on IHasSimpleStateCheckers. DO NOT USE FOR: tenant/edition feature values (manage-settings-and-features); permission authorization of a service call (permissions-and-authorization); startup-time module capabilities (toggle-global-features)."
license: MIT
---

# Checking Simple State in ABP

## When to Use

- Make an object implementing `IHasSimpleStateCheckers<TState>` conditionally enabled.
- Attach permission, authentication, feature, or global-feature requirements to menu/toolbar/permission-like state.
- Implement a reusable custom condition that needs scoped services.
- Evaluate many states together and use a batch checker to avoid repeated backend calls.

## When Not to Use

- **Define or read tenant/edition feature values** — use manage-settings-and-features.
- **Authorize a service method or controller action** — use permissions-and-authorization.
- **Enable or disable a module capability before startup** — use toggle-global-features.
- **Conditionally expose a setting definition** — `SettingDefinition` does not implement `IHasSimpleStateCheckers<TState>`.

## How it works

The state type must implement:

```csharp
public interface IHasSimpleStateCheckers<TState>
    where TState : IHasSimpleStateCheckers<TState>
{
    List<ISimpleStateChecker<TState>> StateCheckers { get; }
}
```

A checker receives `SimpleStateCheckerContext<TState>`, whose verified properties are `IServiceProvider ServiceProvider` and `TState State`:

```csharp
public class EnabledForEnvironmentChecker<TState> : ISimpleStateChecker<TState>
    where TState : IHasSimpleStateCheckers<TState>
{
    public Task<bool> IsEnabledAsync(SimpleStateCheckerContext<TState> context)
    {
        var environment = context.ServiceProvider.GetRequiredService<IHostEnvironment>();
        return Task.FromResult(!environment.IsProduction());
    }
}
```

Add the checker to the state's `StateCheckers` list, then evaluate with `ISimpleStateCheckerManager<TState>`:

```csharp
var enabled = await stateCheckerManager.IsEnabledAsync(state);
var results = await stateCheckerManager.IsEnabledAsync(states);
```

The single-state overload returns `Task<bool>`. The array overload returns `SimpleStateCheckerResult<TState>`, a `Dictionary<TState, bool>` initialized to `true` for each state.

The manager creates a service scope. It evaluates state-local checkers and then checker types registered in `AbpSimpleStateCheckerOptions<TState>.GlobalStateCheckers`. Evaluation uses AND semantics and returns `false` on the first failed non-batch checker. With no local or global checkers, a state is enabled.

### Built-in conditions

For any compatible `TState`, ABP provides extension methods:

- `RequireAuthenticated()`
- `RequirePermissions(params string[])`
- `RequirePermissions(bool requiresAll, params string[])`
- `RequirePermissions(bool requiresAll, bool batchCheck, params string[])`
- `RequireFeatures(...)` with the same overload pattern
- `RequireGlobalFeatures(...)` string-name and feature-type overloads from `Volo.Abp.GlobalFeatures`

The short permission and feature overloads use `requiresAll: true` and `batchCheck: true`. These conditions enable or disable the containing state; they do not define permission or feature values.

`PermissionDefinition` implements `IHasSimpleStateCheckers<PermissionDefinition>`. Framework UI types such as `ApplicationMenuItem` and `ToolbarItem` also implement the contract. `FeatureDefinition` and `SettingDefinition` do not implement it.

For bulk evaluation, implement `ISimpleBatchStateChecker<TState>` or derive from `SimpleBatchStateCheckerBase<TState>`. Its batch method receives `SimpleBatchStateCheckerContext<TState>` with `ServiceProvider` and `TState[] States`, and returns `SimpleStateCheckerResult<TState>`.

Register a global checker type when every state of a given type must satisfy it:

```csharp
Configure<AbpSimpleStateCheckerOptions<MyState>>(options =>
{
    options.GlobalStateCheckers.Add<EnabledForEnvironmentChecker<MyState>>();
});
```

## Validation

- Verify a state with no checkers returns `true`.
- Add two local checkers and verify one `false` result disables the state.
- Verify a checker can resolve a scoped dependency from `context.ServiceProvider`.
- Evaluate an array and verify every input state is present in the returned dictionary.
- For permission/feature extensions, test both `requiresAll: true` and `false` and verify the batch path does not change semantics.

## Common Pitfalls

- **Applying it to `SettingDefinition` or `FeatureDefinition`** — neither implements the contract; use simple state on a compatible containing object such as a menu item or permission definition.
- **Confusing state visibility with authorization** — a disabled menu item does not secure the underlying endpoint.
- **Resolving scoped services outside the provided context** — use `context.ServiceProvider`; the manager owns the scope.
- **Returning an incomplete batch result** — return a value for every state the checker receives.
- **Doing repeated remote checks in a non-batch checker** — use the batch contract when evaluating collections.
