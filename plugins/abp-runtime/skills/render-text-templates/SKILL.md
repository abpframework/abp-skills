---
name: render-text-templates
description: "Render text templates (Scriban or Razor) in ABP. USE FOR: TemplateDefinitionProvider, TemplateDefinition + WithScribanEngine/WithRazorEngine, WithVirtualFilePath content, ITemplateRenderer.RenderAsync, per-culture localization, layouts, the Razor safety boundary. DO NOT USE FOR: sending the rendered body as email (send-emails); embedding .tpl files (manage-virtual-files); localization resources (localize-applications)."
license: MIT
---

# Render Text Templates in ABP

ABP's **text templating** system turns a named template + a model into rendered content (an HTML email body, an SMS text, a report fragment — anything). It is independent of what you do with the result: rendering is this skill; sending the output as email is the **send-emails** skill.

All APIs below are from `Volo.Abp.TextTemplating.*`.

## When to Use

- Defining named text templates and rendering them with Scriban or Razor.
- Localizing template content (inline, or one file per culture) and using layouts.
- Sourcing template content from the Virtual File System or a custom contributor.
- Rendering a template to a string to feed into email, SMS, a document, etc.

## When Not to Use

- **Sending the rendered body as email** (`IEmailSender`, MailKit, SMTP settings, queuing) — use the **send-emails** skill.
- **Setting up the Virtual File System for the `.tpl` files** (embedding, override, live-editing) — use the **manage-virtual-files** skill.
- **Defining the localization resource / keys** a template's `L` calls resolve against — use the **localize-applications** skill.

## Workflow

### 1. Define a template

Templates must be defined before they can be rendered. Create a class deriving from `TemplateDefinitionProvider` and register templates in `Define`. Pick an engine with `WithScribanEngine()` (from `Volo.Abp.TextTemplating.Scriban`) or `WithRazorEngine()` (from `Volo.Abp.TextTemplating.Razor`). Add the corresponding module dependency (`AbpTextTemplatingScribanModule` / `AbpTextTemplatingRazorModule`).

```csharp
using Volo.Abp.TextTemplating;
using Volo.Abp.TextTemplating.Scriban; // WithScribanEngine

public class DemoTemplateDefinitionProvider : TemplateDefinitionProvider
{
    public override void Define(ITemplateDefinitionContext context)
    {
        context.Add(
            new TemplateDefinition("Hello")                 // unique template name
                .WithScribanEngine()
                .WithVirtualFilePath(
                    "/Demos/Hello/Hello.tpl",               // content in the Virtual File System
                    isInlineLocalized: true
                )
        );
    }
}
```

Template content lives in the [Virtual File System](https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/virtual-file-system.md). Mark the `.tpl` file as an **embedded resource** and register the embedded file set in your module's `ConfigureServices`:

```csharp
Configure<AbpVirtualFileSystemOptions>(options =>
{
    options.FileSets.AddEmbedded<MyModule>("MyProject.Root.Namespace");
});
```

Scriban `Hello.tpl` (PascalCase C# properties map to snake_case in templates):

```text
Hello {{model.name}} :)
```

### 2. Render with ITemplateRenderer

`ITemplateRenderer.RenderAsync` is the primary entry point (source: `https://github.com/abpframework/abp/blob/rel-10.5/framework/src/Volo.Abp.TextTemplating.Core/Volo/Abp/TextTemplating/ITemplateRenderer.cs`):

```csharp
Task<string> RenderAsync(
    string templateName,
    object? model = null,
    string? cultureName = null,                       // defaults to CultureInfo.CurrentUICulture
    Dictionary<string, object>? globalContext = null);
```

```csharp
public class HelloDemo : ITransientDependency
{
    private readonly ITemplateRenderer _templateRenderer;

    public HelloDemo(ITemplateRenderer templateRenderer)
        => _templateRenderer = templateRenderer;

    public async Task<string> RunAsync()
    {
        return await _templateRenderer.RenderAsync(
            "Hello",
            new { Name = "John" });          // anonymous model is fine for simple cases
    }
}
```

Pass extra objects to the render context via `globalContext`, and force a culture with `cultureName`.

### 3. Localize template content

**Inline localization** — one template, texts localized through the localization system. Declare the localization resource on the `TemplateDefinition` and use the `L` helper in the template:

```csharp
context.Add(
    new TemplateDefinition("PasswordReset", typeof(DemoResource))  // localization resource
        .WithScribanEngine()
        .WithVirtualFilePath("/Demos/PasswordReset/PasswordReset.tpl", isInlineLocalized: true));
```

```html
<a href="{{model.link}}">{{ L "ResetMyPassword" model.name }}</a>
```

Defining `DemoResource` itself (the resource class, its json, culture fallback) is the **localize-applications** skill; here you only reference an existing resource.

**Multiple-content localization** — a separate file per culture (`en.tpl`, `tr.tpl`, ...). Point the definition at a folder, set a default culture, and use `isInlineLocalized: false`:

```csharp
context.Add(
    new TemplateDefinition(name: "WelcomeEmail", defaultCultureName: "en")
        .WithScribanEngine()
        .WithVirtualFilePath("/Demos/WelcomeEmail/Templates", isInlineLocalized: false));
```

**Layouts** — define a template with `isLayout: true` containing a `{{content}}` placeholder, then reference it via the `layout:` argument of another `TemplateDefinition`.

### 4. Where content comes from

A template's *definition* (name + engine) and its *content* are separate layers. Content is supplied by an `ITemplateContentContributor`; the default file contributor reads a `.tpl` from the Virtual File System (typically an embedded resource), but a custom contributor can source content from elsewhere (DB, config, a remote store).

## Choosing an engine: Scriban vs. Razor (security)

- **Scriban** is a sandboxed template language. It honors Scriban's safe-runtime boundaries by default, so it's the right choice when template content can be edited by non-developers (e.g. through the Text Template Management UI).
- **Razor** compiles template content into a **fully-trusted .NET assembly via Roslyn and executes it in the host process** — editing a Razor template at runtime is functionally equivalent to running arbitrary server-side code. `RazorTemplateRenderingEngine.IsSandboxed` is `false`. Use Razor only for templates authored and reviewed by trusted developers, never for content an untrusted user can edit. The Text Template Management module reflects this: editing non-sandboxed (Razor) content requires the extra `TextTemplateManagement.TextTemplates.EditNonSandboxedContents` permission — grant it only to fully trusted operators.

See `https://github.com/abpframework/abp/blob/rel-10.5/docs/en/framework/infrastructure/text-templating/razor.md`.

## Validation

- Render a template in isolation and assert the returned string matches the expected content (a quick way to confirm the template is defined and the engine module is wired).
- An "Undefined Template" error means the *definition* is missing — its `TemplateDefinitionProvider` isn't registered. This is separate from *content*: if the definition exists but no `ITemplateContentContributor` supplies content for it, the content lookup returns null instead (e.g. the default file contributor can't find the `.tpl` in the Virtual File System).

## Common Pitfalls

- A template must be defined (via a `TemplateDefinitionProvider`) before it can be rendered — that's a separate layer from its content. A missing definition throws "Undefined Template"; a defined template with no content contributor returns null.
- **Picking Razor for content that untrusted users can edit** — Razor executes as fully-trusted host-process code. Use Scriban for editor-facing templates; reserve Razor for developer-authored ones.
- Forgetting to embed the `.tpl` as a resource / register the embedded file set means the default file contributor can't find the content even though the definition exists.
- Referencing a localization resource in a template without that resource being defined and registered — define it via the **localize-applications** skill first.
