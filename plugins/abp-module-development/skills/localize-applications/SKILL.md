---
name: localize-applications
description: "Framework-level ABP localization (resources, validation, exceptions, app services, text templating — not just UI). USE FOR: a LocalizationResource + [LocalizationResourceName], registering via AbpLocalizationOptions.Resources.Add(...).AddVirtualJson, sharing keys with AddBaseTypes / [InheritResource], per-culture embedded json, typed IStringLocalizer, culture fallback, localizing BusinessException codes and DataAnnotations. DO NOT USE FOR: navigation menus (menus-and-localization); Angular/Blazor client localization (angular-ui / blazor-ui); email templates (render-text-templates)."
license: MIT
---

# Localize ABP Applications

ABP's localization builds on `Microsoft.Extensions.Localization` and is used across every layer — validation messages, exception messages, application services, and any C#/Razor code — not just the UI. This skill covers the framework mechanism; sibling skills own the UI-specific wiring.

## When to Use

- Defining a `LocalizationResource` marker class and registering it with `AbpLocalizationOptions`.
- Storing translations in per-culture embedded json files loaded via `AddVirtualJson`.
- Reusing shared keys through inheritance (`AddBaseTypes` / `[InheritResource]`).
- Consuming strings with `IStringLocalizer<TResource>` or the `L` property on ABP base classes.
- Localizing `BusinessException` error codes and data-annotation validation messages.

## When Not to Use

- **Navigation menu items** — use menus-and-localization (this skill is the resource/json backend it points to).
- **Client-side UI pipes** — Angular `abpLocalization` pipe or Blazor localization → angular-ui / blazor-ui.
- **Text template definitions** (emails, etc.) → render-text-templates.

## Define a resource

A resource is a plain marker class. Give it a short client-facing name with `[LocalizationResourceName]` (namespace `Volo.Abp.Localization`):

```csharp
using Volo.Abp.Localization;

[LocalizationResourceName("MyProject")]
public class MyProjectResource
{
}
```

Register it in the module — by convention the `Domain.Shared` module. The json files are virtual (embedded) files, so also register the assembly with `AbpVirtualFileSystemOptions`:

```csharp
Configure<AbpVirtualFileSystemOptions>(options =>
{
    options.FileSets.AddEmbedded<MyProjectDomainSharedModule>("MyProject");
});

Configure<AbpLocalizationOptions>(options =>
{
    options.Resources
        .Add<MyProjectResource>("en")            // "en" is the default culture
        .AddVirtualJson("/Localization/MyProject"); // folder holding the *.json files
});
```

- `Resources.Add<TResource>(string? defaultCultureName = null)` registers the resource and returns a `LocalizationResource` for chaining. The string sets `DefaultCultureName` (the fallback culture — see below).
- `AddVirtualJson(string virtualPath)` and `AddBaseTypes(params Type[] types)` are extension methods on the resource; each returns the resource so you can keep chaining.

## The json files

One file per culture in the resource folder, e.g. `Localization/MyProject/en.json`:

```json
{
  "culture": "en",
  "texts": {
    "HelloWorld": "Hello World!",
    "HelloMessage": "Hello {0}, welcome!"
  }
}
```

- Every file must declare `"culture"` — the loader keys the dictionary off the json's own `"culture"` value, **not** the filename. ABP **skips** a file whose `"culture"` is missing. Keep the value aligned with the filename as a convention.
- `"texts"` is a flat key→value map (keys may contain spaces). Nested objects/arrays are supported and flattened with a double underscore: `{ "Hello": { "World": "..." } }` resolves as `L["Hello__World"]`.
- Multiple files of the same culture are merged (sorted by name, later file wins on duplicate keys) — useful to split a large resource by feature (`en.json`, `en_Books.json`, …).

## Resource inheritance

Inherit shared keys (e.g. validation strings) without copying them. Two equivalent forms:

```csharp
// Attribute form
[InheritResource(typeof(AbpValidationResource))]  // Volo.Abp.Localization
public class MyProjectResource { }
```

```csharp
// Fluent form
options.Resources
    .Add<MyProjectResource>("en")
    .AddVirtualJson("/Localization/MyProject")
    .AddBaseTypes(typeof(AbpValidationResource)); // Volo.Abp.Validation.Localization.AbpValidationResource
```

A resource may inherit from multiple resources; a key defined in the derived resource overrides the inherited one. To add keys to an *existing* resource instead of creating a new one, use `options.Resources.Get<TResource>().AddVirtualJson("/…/Extensions")`.

## Default resource

`AbpLocalizationOptions.DefaultResourceType` is used when no resource is specified. The layered startup template sets it to the application's resource:

```csharp
Configure<AbpLocalizationOptions>(options =>
{
    options.DefaultResourceType = typeof(MyProjectResource);
});
```

## Consuming localized strings

Inject `IStringLocalizer<TResource>` anywhere:

```csharp
public class BookManager : ITransientDependency
{
    private readonly IStringLocalizer<MyProjectResource> _localizer;

    public BookManager(IStringLocalizer<MyProjectResource> localizer)
    {
        _localizer = localizer;
    }

    public string Greet(string name)
    {
        return _localizer["HelloMessage", name]; // format args follow the key
    }
}
```

ABP base classes expose an `L` shortcut over the same localizer. `ApplicationService` (and `AbpController`, `AbpPageModel`) resolve `L` from their `LocalizationResource`:

```csharp
public class BookAppService : ApplicationService
{
    public BookAppService()
    {
        LocalizationResource = typeof(MyProjectResource);
    }

    public Task DoItAsync() => Task.FromResult(L["HelloWorld"]);
}
```

The startup templates set `LocalizationResource` on a shared base app-service class, so deriving services just use `L["Key"]`. In Razor views use `IHtmlLocalizer<TResource>`.

## Culture fallback

When a key is missing in the requested culture, `AbpDictionaryBasedStringLocalizer` falls back in order:

1. Requested culture (e.g. `de-DE`).
2. Base culture without country code (`de`) — when `AbpLocalizationOptions.TryToGetFromBaseCulture` is `true` (default).
3. `DefaultCultureName` (the `"en"` passed to `Add<T>("en")`) — when `TryToGetFromDefaultCulture` is `true` (default).

If still not found, the localizer returns the key itself with `ResourceNotFound = true` (which is why a missing key renders as the raw key string).

## Localizing validation (data annotations)

Inherit `AbpValidationResource` so ABP's built-in `[Required]` / `[StringLength]` messages resolve through your resource, then add your own display-name keys (e.g. `"DisplayName:Name": "Book name"`) to the same json — they flow into validation output for the current culture.

## Localizing business exceptions

`BusinessException` (and anything implementing `IHasErrorCode`) carries a `Code`. Map its **namespace** (the part before `:`) to a resource with `AbpExceptionLocalizationOptions.MapCodeNamespace`:

```csharp
Configure<AbpExceptionLocalizationOptions>(options =>
{
    options.MapCodeNamespace("MyProject", typeof(MyProjectResource));
});
```

```csharp
throw new BusinessException("MyProject:010001")
    .WithData("BookName", book.Name);
```

`DefaultExceptionToErrorInfoConverter` splits the code on `:`, takes `MyProject` as the namespace, resolves the mapped resource, then looks up the **full code** (`"MyProject:010001"`) as the localization key. So the json key is the whole code:

```json
{
  "culture": "en",
  "texts": {
    "MyProject:010001": "The book '{BookName}' already exists."
  }
}
```

`{BookName}` placeholders are replaced from the exception's `Data` (populated by `WithData`).

## Programmatic localizable strings

To pass "a string to be localized later" across layers (e.g. a display name resolved at render time), use `LocalizableString` / `ILocalizableString` (namespace `Volo.Abp.Localization`). Its `Localize(IStringLocalizerFactory)` method returns the resolved `LocalizedString`:

```csharp
ILocalizableString title = LocalizableString.Create<MyProjectResource>("HelloWorld");
// later: title.Localize(stringLocalizerFactory).Value
```

## Common Pitfalls

- **Adding a key only to `en.json`.** Add it to every culture file in the folder with a real translation; a missing key silently falls back to `en` (or renders the raw key), which reads as a bug.
- **Missing `"culture"` in a json file.** The file is skipped entirely — the loader keys off the json's `"culture"`, not the filename.
- **Expecting `AddVirtualJson` to find files without the virtual file system.** The json is embedded; register the assembly via `AbpVirtualFileSystemOptions.FileSets.AddEmbedded<TModule>(...)`.
- **Wrong exception key.** The localization key for an error code is the *entire* code (`"MyProject:010001"`), not just the number after the colon — and the namespace must be mapped with `MapCodeNamespace`.
- **`L` throws / returns the raw key in a service.** `ApplicationService` needs its `LocalizationResource` set (directly or via a base class); otherwise it has no resource to resolve against.
