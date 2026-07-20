---
name: send-sms
description: "ABP provider-independent ISmsSender with a real provider package for delivery. USE FOR: ISmsSender; SmsMessage; SendAsync; provider-specific values via SmsMessage.Properties; NullSmsSender; a provider such as Volo.Abp.Sms.Twilio. DO NOT USE FOR: rendering email templates (render-text-templates) or sending email (send-emails); scheduling or retrying notification work (background-jobs-and-events); provider credentials as settings (manage-settings-and-features)."
license: MIT
---

# Send SMS in ABP

Use `ISmsSender` in application code so the provider can be replaced without changing callers. The `Volo.Abp.Sms` package supplies the abstraction and a logging-only fallback; actual delivery requires a provider implementation.

## When to Use

- Send a text message to a phone number from an application or domain service.
- Keep notification code independent of Twilio, Aliyun, Tencent Cloud, or a custom gateway.
- Pass optional provider-specific data without adding it to the common abstraction.

## When Not to Use

- **Render an email body** — use render-text-templates; **send email** — use send-emails.
- **Configure background jobs, retries, or event handlers** — use background-jobs-and-events.
- **Manage provider credentials through ABP settings** — use manage-settings-and-features.

## How it works

### Add the abstraction

Add `Volo.Abp.Sms` and depend on `AbpSmsModule` in the module that sends messages:

```csharp
using Volo.Abp.Modularity;
using Volo.Abp.Sms;

[DependsOn(typeof(AbpSmsModule))]
public class NotificationsModule : AbpModule
{
}
```

`ISmsSender` has one method:

```csharp
Task SendAsync(SmsMessage smsMessage);
```

The extension overload creates the message for the common case:

```csharp
public class VerificationCodeSender : ITransientDependency
{
    private readonly ISmsSender _smsSender;

    public VerificationCodeSender(ISmsSender smsSender)
    {
        _smsSender = smsSender;
    }

    public Task SendAsync(string phoneNumber, string code)
    {
        return _smsSender.SendAsync(
            phoneNumber,
            $"Your verification code is {code}");
    }
}
```

The interface has no `CancellationToken` parameter and does not return a provider message ID or delivery status.

### Use SmsMessage when properties are needed

`SmsMessage` requires non-empty `PhoneNumber` and `Text` values. Its `Properties` type is `IDictionary<string, object>` and starts empty:

```csharp
var message = new SmsMessage(phoneNumber, text);
message.Properties["TemplateCode"] = templateCode;

await _smsSender.SendAsync(message);
```

Only set property names documented by the selected provider. The common package does not interpret them.

### Install a delivery provider separately

`NullSmsSender` is the fallback registered by `Volo.Abp.Sms`. It logs the phone number and text and completes successfully; it does not contact an SMS gateway.

Install and configure a provider package for production. For example, Twilio support is the separate Pro package `Volo.Abp.Sms.Twilio`. ABP also contains separate `Volo.Abp.Sms.Aliyun` and `Volo.Abp.Sms.TencentCloud` provider packages. Keep injecting `ISmsSender` after selecting a provider.

Alternatively, implement `ISmsSender` in the application and register that implementation through ABP dependency injection.

## Validation

- Resolve `ISmsSender` and verify its concrete type is the intended provider, not `NullSmsSender`.
- In a unit test, replace `ISmsSender` with a recording fake and assert `PhoneNumber`, `Text`, and required `Properties`.
- For a real provider, send to a controlled test number and verify delivery in the provider dashboard.
- Confirm logs do not expose verification codes or phone numbers at an inappropriate level.

## Common Pitfalls

- **Treating a completed `NullSmsSender.SendAsync` call as delivery** — it only logs and returns `Task.CompletedTask`.
- **Installing only `Volo.Abp.Sms` in production** — the abstraction package does not send through a gateway.
- **Assuming `Properties` is `Dictionary<string, string>`** — the source declares `IDictionary<string, object>`.
- **Assuming cancellation or delivery tracking is part of `ISmsSender`** — neither is present in this abstraction.
- **Logging sensitive message content** — the fallback logs both destination and text; account for that in development and test environments.
