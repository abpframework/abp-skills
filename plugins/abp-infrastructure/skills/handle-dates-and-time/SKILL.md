---
name: handle-dates-and-time
description: "ABP DateTime, UTC normalization, time zones, persistence. USE FOR: IClock and AbpClockOptions; Utc/Local/Unspecified; Clock.Normalize; EF Core DateTime converters and DisableDateTimeNormalization; per-request tenant/user timezone; ITimezoneProvider Windows/IANA. DO NOT USE FOR: timezone settings (manage-settings-and-features); audit-log persistence (configure-audit-logging); multi-tenancy resolution (configure-multi-tenancy)."
license: MIT
---

# Handling Dates and Time

Use `IClock` instead of calling `DateTime.Now` or `DateTime.UtcNow` in application/domain code. `AbpClockOptions.Kind` defines the application's normalization policy; UTC is the only mode that enables multiple-timezone conversion.

## When to Use

- Choose a single `DateTimeKind` policy for an application.
- Normalize inbound and persisted `DateTime` values.
- Understand how EF Core and auditing consume `IClock`.
- Convert UTC instants to the current request's timezone or local wall time back to UTC.
- Convert and enumerate Windows/IANA timezone identifiers through `ITimezoneProvider`.

## When Not to Use

- **Define general setting values/providers** — use manage-settings-and-features.
- **Configure which requests/actions/entities are audited** — use configure-audit-logging.
- **Configure tenant resolution, tenant switching, or data filters** — use configure-multi-tenancy.

## How it works

### Configure one clock policy

`AbpClockOptions.Kind` defaults to `DateTimeKind.Unspecified`. Configure UTC for applications that store instants and serve more than one timezone:

```csharp
using Volo.Abp.Timing;

Configure<AbpClockOptions>(options =>
{
    options.Kind = DateTimeKind.Utc;
});
```

The behavior is exact:

| Configured `Kind` | `IClock.Now` | `SupportsMultipleTimezone` | `Normalize` behavior |
| --- | --- | --- | --- |
| `Utc` | `DateTime.UtcNow` | `true` | Local converts with `ToUniversalTime`; Unspecified is relabeled UTC. |
| `Local` | `DateTime.Now` | `false` | UTC converts with `ToLocalTime`; Unspecified is relabeled Local. |
| `Unspecified` (default) | `DateTime.Now` | `false` | Returns the input unchanged. |

The default is intentionally permissive, but note the asymmetry: `IClock.Kind` reports `Unspecified` while `IClock.Now` comes from `DateTime.Now`. Do not infer that `Clock.Now.Kind` is unspecified.

### Normalize values deliberately

```csharp
public class BookingService : ITransientDependency
{
    private readonly IClock _clock;

    public BookingService(IClock clock)
    {
        _clock = clock;
    }

    public DateTime NormalizeStart(DateTime start)
    {
        return _clock.Normalize(start);
    }
}
```

`Normalize` converts only a Local/UTC pair. When the input is `Unspecified` and the configured kind is Local or UTC, it uses `DateTime.SpecifyKind`; it does not apply a timezone offset. An unspecified browser wall-clock value therefore needs an explicit timezone conversion, not just `Normalize`.

### Convert between UTC and the current timezone

`IClock.ConvertToUserTime` and `ConvertToUtc` operate only when the clock supports multiple timezones and `ICurrentTimezoneProvider.TimeZone` has a value.

```csharp
var localDisplayTime = _clock.ConvertToUserTime(utcDateTime);
var utcInstant = _clock.ConvertToUtc(localWallClockTime);
```

- `ConvertToUserTime(DateTime)` additionally requires an input whose kind is UTC.
- `ConvertToUserTime(DateTimeOffset)` preserves the instant and changes its offset.
- `ConvertToUtc(DateTime)` treats a non-UTC value as wall-clock time in the current timezone by first specifying `Unspecified`, then calling `TimeZoneInfo.ConvertTimeToUtc`.

For a known timezone independent of the current request, use `ITimezoneProvider`:

```csharp
var utc = _timezoneProvider.ConvertUnspecifiedToUtc(   // ConvertUnspecifiedToUtc: ABP 10.6+
    localWallClockTime,
    "Europe/Berlin");

var timeZoneInfo = _timezoneProvider.GetTimeZoneInfo("Europe/Berlin");
```

> `ITimezoneProvider.ConvertUnspecifiedToUtc(...)` is available from **ABP 10.6+**; on 10.5 convert with `TimeZoneInfo`/`ConvertToUtc` instead.

`ITimezoneProvider` also exposes Windows/IANA lists and `WindowsToIana` / `IanaToWindows`. The default `TZConvertTimezoneProvider` delegates to TimeZoneConverter.

### Establish the current timezone in ASP.NET Core

Add ABP's timezone middleware before endpoints, after authentication and tenant resolution when timezone settings depend on the current user/tenant:

```csharp
app.UseAuthentication();
app.UseMultiTenancy();
app.UseAbpTimeZone();
app.UseAuthorization();
app.UseConfiguredEndpoints();
```

When UTC mode is enabled, `AbpTimeZoneMiddleware` selects a timezone in this order:

1. `ISettingProvider` value for `Abp.Timing.TimeZone`.
2. The `__timezone` request header, query string, form field, or cookie.
3. The server local timezone converted to IANA when necessary.

It stores the selected value in `ICurrentTimezoneProvider` for the request through an `AsyncLocal` scope. If `SupportsMultipleTimezone` is false, it skips selection entirely.

### EF Core normalization

`AbpDbContext` applies `AbpDateTimeValueConverter` / `AbpNullableDateTimeValueConverter` to writable `DateTime` and `DateTime?` properties. The converters call `Clock.Normalize` both when writing and reading.

Opt out only for a property/entity that intentionally preserves its original kind semantics:

```csharp
[DisableDateTimeNormalization]
public DateTime ExternalWallClockTime { get; set; }
```

The attribute can be placed on the entity or property. ABP also skips this normalization setup for owned types and derived EF entity types. `DateTimeOffset` is not included in this automatic converter scan.

### Auditing and multi-tenancy

`AuditPropertySetter` uses `Clock.Now` for `CreationTime`, `LastModificationTime`, and `DeletionTime`. Changing `AbpClockOptions.Kind` therefore changes the kind policy used by automatic audit timestamps.

Tenant checks in the same setter protect creator/modifier/deleter user IDs when the entity tenant differs from the current user's tenant; they do not convert timestamps to a tenant-local value. Store audit instants under the global clock policy, then convert for display with the current timezone.

## Validation

- Assert `Clock.Kind`, `Clock.Now.Kind`, and `SupportsMultipleTimezone` for the configured mode; do not treat them as interchangeable in Unspecified mode.
- Test `Normalize` with Utc, Local, and Unspecified inputs.
- In UTC mode, set a current timezone and round-trip a normal wall-clock value through `ConvertToUtc` / `ConvertToUserTime`.
- Save/reload EF Core entities with `DateTime` and nullable `DateTime`; verify their kinds and values. Verify an opted-out property is unchanged.
- Create/update/delete an audited entity and confirm timestamps come from `IClock` under the selected policy.

## Common Pitfalls

- **Using `DateTime.Now` directly** — it bypasses the configured clock and makes tests/persistence inconsistent.
- **Assuming `Normalize(Unspecified)` converts from a user's timezone** — it only relabels the kind. Use `ConvertToUtc` or `ConvertUnspecifiedToUtc` with a timezone.
- **Expecting multi-timezone conversion in Local/Unspecified mode** — `SupportsMultipleTimezone` is true only for UTC mode.
- **Displaying stored UTC directly** — call `ConvertToUserTime` at the presentation boundary.
- **Persisting tenant-local audit timestamps** — audit setters use the global `Clock.Now`; timezone conversion belongs at input/output boundaries.
- **Adding `[DisableDateTimeNormalization]` broadly** — it removes both read and write normalization for matching EF Core properties.
