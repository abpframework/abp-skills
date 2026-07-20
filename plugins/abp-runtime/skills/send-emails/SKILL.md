---
name: send-emails
description: "Send/queue email in ABP via the provider-independent IEmailSender (MailKit). USE FOR: SendAsync/QueueAsync, CC/attachments via AdditionalEmailSendingArgs + EmailAttachment, Abp.Mailing.Smtp.* settings, MailKit (AbpMailKitModule/AbpMailKitOptions), NullEmailSender in dev, render-then-send. DO NOT USE FOR: rendering the body (render-text-templates); SMS (send-sms); background jobs (background-jobs-and-events); SMTP credentials as settings (manage-settings-and-features)."
license: MIT
---

# Send Emails in ABP

ABP's **emailing** system sends content through the provider-independent `IEmailSender`; MailKit is the recommended SMTP provider. Producing the body (from a template) is a separate concern — the **render-text-templates** skill — and a common flow is to render a body then send it here.

All APIs below are from `Volo.Abp.Emailing` (+ `Volo.Abp.MailKit`).

## When to Use

- Sending HTML/plain email through `IEmailSender`, including a `from`, CC, and attachments.
- Rendering a body then sending it (e.g. `StandardEmailTemplates.Message`).
- Switching the underlying SMTP sender to MailKit.
- Queuing email through the background job system to avoid blocking the request.

## When Not to Use

- **Defining and rendering the template body** (`TemplateDefinitionProvider`, `ITemplateRenderer`, Scriban/Razor, layouts) — use the **render-text-templates** skill.
- **SMS** — use the **send-sms** skill. **Push / in-app notifications** are out of scope (there is no ABP-framework notification skill here).
- **General background job configuration** — use the **background-jobs-and-events** skill (this skill only calls `QueueAsync`).
- **Managing SMTP credentials as encrypted settings** — use the **manage-settings-and-features** skill.

## Workflow

### 1. Send email with IEmailSender

Inject `IEmailSender` and call `SendAsync` (source: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.Emailing/Volo/Abp/Emailing/IEmailSender.cs`). `isBodyHtml` defaults to `true`.

```csharp
using Volo.Abp.Emailing;

await _emailSender.SendAsync(
    "target@domain.com",  // to
    "Email subject",      // subject
    body);                // body (HTML by default)
```

Overloads add a `from` address, accept a raw `System.Net.Mail.MailMessage`, or take `AdditionalEmailSendingArgs` for CC, `Attachments` (`List<EmailAttachment>`), and `ExtraProperties`.

### 2. Render then send

Render the body with the **render-text-templates** skill, then send it here:

```csharp
using Volo.Abp.Emailing.Templates;   // StandardEmailTemplates

var body = await _templateRenderer.RenderAsync(
    StandardEmailTemplates.Message,   // built-in "Abp.StandardEmailTemplates.Message"
    new { message = "This is the email body..." });

await _emailSender.SendAsync("target@domain.com", "Email subject", body);
```

`StandardEmailTemplates.Message` and `StandardEmailTemplates.Layout` are built-in templates you can override through the Virtual File System (paths `/Volo/Abp/Emailing/Templates/Message.tpl` and `Layout.tpl`).

### 3. MailKit provider

Install `Volo.Abp.MailKit` (`abp add-package Volo.Abp.MailKit`) and depend on `AbpMailKitModule`. Your code keeps using `IEmailSender` unchanged — MailKit just replaces the underlying SMTP sender. Configure `AbpMailKitOptions.SecureSocketOption` when the SMTP server needs a specific TLS mode:

```csharp
Configure<AbpMailKitOptions>(options =>
{
    options.SecureSocketOption = SecureSocketOptions.SslOnConnect;
});
```

SMTP host/port/credentials come from the standard email settings (`Abp.Mailing.Smtp.*`), set via the Setting Management UI, `ISettingManager`, or `appsettings.json` under `"Settings"`. Keep the SMTP password out of source control — prefer the Setting Management UI or a secret store / environment variable over committing it.

### 4. Queue email through background jobs

To avoid blocking the request, call `QueueAsync` instead of `SendAsync`. It takes the same arguments and enqueues the send onto the [background job system](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/background-jobs/index.md), which brings automatic retries for transient SMTP failures:

```csharp
await _emailSender.QueueAsync("target@domain.com", "Email subject", body);
```

Runtime caveat: `QueueAsync` only enqueues **when a background job manager is available** (`IBackgroundJobManager.IsAvailable()`). If none is registered, it silently falls back to sending **synchronously** on the calling thread — so don't assume queuing always defers the send.

## Validation

- In DEBUG, verify emails are logged (not sent) via `NullEmailSender` rather than expecting real delivery.
- For real sending, confirm `Abp.Mailing.Smtp.*` settings resolve and, if using MailKit, that `AbpMailKitModule` is depended on and the SMTP handshake succeeds.

## Common Pitfalls

- In DEBUG the layered startup template registers `NullEmailSender` (logs instead of sending), so no real emails go out during development.
- Prefer `IEmailSender` over provider-specific senders (`ISmtpEmailSender`, `IMailKitSmtpEmailSender`) to keep code provider-independent.
- `Abp.Mailing.Smtp.Password` is an encrypted setting (`isEncrypted: true`). A plaintext value set from `appsettings.json` is still read correctly by default — decryption fails and `AbpSettingOptions.ReturnOriginalValueIfDecryptFailed` (default `true`) returns the original value, logging a decrypt warning. Encrypting it via `ISettingEncryptionService.Encrypt` is recommended (and required if you set `ReturnOriginalValueIfDecryptFailed = false`), not a hard prerequisite for it to work.
- **Passing a template name as the body.** `IEmailSender` has no template overload — the `body` argument is the final content. `StandardEmailTemplates.Message` is a template *name* to hand to `ITemplateRenderer.RenderAsync` (step 2); passing it straight to `SendAsync` emails the literal string `Abp.StandardEmailTemplates.Message`. This skill takes an already-rendered body; defining/rendering it is the **render-text-templates** skill.
