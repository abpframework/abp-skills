---
name: serialize-json
description: "ABP IJsonSerializer and its default System.Text.Json provider. USE FOR: Serialize/Deserialize overloads; camelCase and indented flags; AbpSystemTextJsonSerializerOptions.JsonSerializerOptions; AbpJsonOptions date formats; ABP converters and JSON contract modifiers. DO NOT USE FOR: ASP.NET Core MVC response JSON (out of scope); distributed cache entry serialization (distributed-caching-and-locking); encrypting serialized values (encrypt-strings)."
license: MIT
---

# Serialize JSON in ABP

Use `IJsonSerializer` in reusable application and infrastructure code. `Volo.Abp.Json` depends on `Volo.Abp.Json.SystemTextJson`, so System.Text.Json is the default provider while callers remain provider-independent.

## When to Use

- Serialize an object to a JSON string outside the ASP.NET Core formatter pipeline.
- Deserialize to a generic type or a runtime `Type`.
- Share ABP's converters, date handling, and extra-property contract behavior.
- Configure the default System.Text.Json provider for consumers of `IJsonSerializer`.

## When Not to Use

- **Configure controller response/request JSON** — configure ASP.NET Core `JsonOptions` separately; that is ASP.NET Core HTTP formatter configuration and is out of scope here.
- **Design distributed cache serialization and expiration policy** — use distributed-caching-and-locking.
- **Protect JSON as a secret** — use encrypt-strings only when ABP-compatible reversible encryption is the requirement.

## How it works

### Use the abstraction

`IJsonSerializer` is synchronous and exposes three operations:

```csharp
string Serialize(object obj, bool camelCase = true, bool indented = false);
T Deserialize<T>(string jsonString, bool camelCase = true);
object Deserialize(Type type, string jsonString, bool camelCase = true);
```

```csharp
public class PayloadStore : ITransientDependency
{
    private readonly IJsonSerializer _jsonSerializer;

    public PayloadStore(IJsonSerializer jsonSerializer)
    {
        _jsonSerializer = jsonSerializer;
    }

    public string Serialize(OrderPayload payload)
    {
        return _jsonSerializer.Serialize(payload);
    }

    public OrderPayload Deserialize(string json)
    {
        return _jsonSerializer.Deserialize<OrderPayload>(json);
    }
}
```

`camelCase` defaults to `true`; `indented` defaults to `false`. Pass `camelCase: false` when property names must retain their CLR names.

### Configure the default System.Text.Json provider

`AbpSystemTextJsonSerializerOptions.JsonSerializerOptions` starts with `JsonSerializerDefaults.Web`, skips comments, and allows trailing commas. The ABP module supplies an unsafe-relaxed encoder only when no encoder was explicitly set, then adds ABP converters and an `AbpDefaultJsonTypeInfoResolver`.

```csharp
using System.Text.Json.Serialization;
using Volo.Abp.Json.SystemTextJson;

Configure<AbpSystemTextJsonSerializerOptions>(options =>
{
    options.JsonSerializerOptions.DefaultIgnoreCondition =
        JsonIgnoreCondition.WhenWritingNull;
});
```

The serializer clones these global options for each `camelCase`/`indented` combination, overriding `PropertyNamingPolicy` and `WriteIndented` for the current call.

### Configure ABP DateTime formats

`AbpJsonOptions` has two properties:

- `InputDateTimeFormats`: an empty `List<string>` by default; add exact accepted input formats.
- `OutputDateTimeFormat`: `null` by default; null or empty uses the provider's default output format.

```csharp
using Volo.Abp.Json;

Configure<AbpJsonOptions>(options =>
{
    options.InputDateTimeFormats.Add("yyyy-MM-dd HH:mm:ss");
    options.OutputDateTimeFormat = "yyyy-MM-dd'T'HH:mm:ss'Z'";
});
```

The ABP DateTime converters use these values with `CultureInfo.CurrentUICulture`. Note the two layers behave differently. The default System.Text.Json provider registers its date converters with `SkipDateTimeNormalization()`, so the general path does **not** call `Clock.Normalize` — a value with a specified `Kind` passes through unchanged. The converter still handles specific cases: a `DateTime` with `Unspecified` kind, under a clock that supports multiple timezones and a current tenant timezone, is converted from that timezone to UTC. A literal `Z` format does not itself convert a value to UTC; choose the format together with the application's clock policy.

### Keep ASP.NET Core JSON configuration separate

Configuring `AbpSystemTextJsonSerializerOptions` or `AbpJsonOptions` does not configure ASP.NET Core MVC's input/output formatter. Configure Microsoft ASP.NET Core `JsonOptions` separately when HTTP contracts must change.

## Validation

- Round-trip representative payloads, including nulls, enums, GUIDs, `DateTime`, and extra properties.
- Assert both camel-case and CLR-name modes when consumers depend on property casing.
- Test malformed JSON, comments, and trailing commas according to the configured policy.
- Verify the runtime `Type` overload returns the expected concrete type.
- Test `IJsonSerializer` and ASP.NET Core endpoint JSON separately; they use separate option objects.

## Common Pitfalls

- **Calling `System.Text.Json.JsonSerializer` directly in provider-independent code** — it bypasses ABP's abstraction and converters.
- **Expecting ABP options to change MVC JSON** — ASP.NET Core formatter options are separate.
- **Assuming `indented` is a global setting** — it is a per-call argument on `IJsonSerializer.Serialize`.
- **Adding a date output suffix that misrepresents the value's timezone** — formatting does not replace correct clock normalization.
- **Mutating serializer options after first use** — configure options during module service configuration, before serializers cache cloned option sets.
