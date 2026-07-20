---
name: integrate-ai
description: "ABP AI workspaces with Microsoft.Extensions.AI, Microsoft Agent Framework, or Microsoft.SemanticKernel. USE FOR: choosing an ABP AI abstraction, AbpAIModule, AbpAIWorkspaceOptions, resolving IChatClient/IChatClientAccessor/IKernelAccessor, per-workspace provider/model config. DO NOT USE FOR: general .NET AI/ML outside ABP's workspace integration (out of scope); AI-call observability (out of scope); tenant-editable AI providers via the commercial AI Management module."
license: MIT
---

# Integrating AI with ABP

This integration is new and has active API/documentation movement. Re-check the target ABP version before copying these names or fallback rules.

## When to Use

- Give a reusable ABP module an optional AI dependency through accessors.
- Configure one default model/provider or isolated named workspaces.
- Build application agents on top of the configured `IChatClient`.
- Use Semantic Kernel through an ABP-configured `Kernel` accessor.

## When Not to Use

- **Select AI/ML technology without an ABP workspace requirement** — out of scope; choose the .NET AI library directly.
- **Configure traces, metrics, or AI telemetry** — out of scope here; ABP ships no OpenTelemetry framework module, so wire the OpenTelemetry .NET SDK directly.
- **Dynamically manage providers/models through the commercial AI Management UI** — that module is outside the framework abstractions covered here.

## Workflow

### 1. Choose the integration surface

ABP's `Volo.Abp.AI` package supports three related surfaces:

- **Microsoft.Extensions.AI** — use `IChatClient`; ABP recommends this minimal abstraction for reusable libraries.
- **Microsoft Agent Framework** — create agents from an `IChatClient` with `CreateAIAgent`; ABP recommends it for agent applications.
- **Microsoft.SemanticKernel** — use `IKernelAccessor` when Semantic Kernel-specific integration is required.

Agent Framework does not have a separate ABP workspace module. It runs on the `IChatClient` configured by the Microsoft.Extensions.AI path.

### 2. Add the module and a provider package

Depend on `AbpAIModule` from `Volo.Abp.AI`:

```csharp
[DependsOn(typeof(AbpAIModule))]
public class MyAppModule : AbpModule
{
}
```

Also add the provider/connector package used to construct the `ChatClientBuilder` or `IKernelBuilder`. ABP does not choose provider credentials, endpoint, or model for you.

### 3. Define a workspace when isolation is needed

```csharp
[WorkspaceName("CommentSummarization")]
public class CommentSummarizationWorkspace
{
}
```

`WorkspaceNameAttribute.GetWorkspaceName<T>()` returns the attribute value, or the type's full name when the attribute is absent. Treat workspace names as unique and case-sensitive; the docs also disallow spaces.

### 4. Pre-configure workspaces

Use `PreConfigure<AbpAIWorkspaceOptions>` before `AbpAIModule.ConfigureServices` consumes the configuration:

```csharp
public override void PreConfigureServices(ServiceConfigurationContext context)
{
    PreConfigure<AbpAIWorkspaceOptions>(options =>
    {
        options.Workspaces.ConfigureDefault(workspace =>
        {
            workspace.ConfigureChatClient(chat =>
            {
                chat.Builder = CreateChatClientBuilder();
            });
        });

        options.Workspaces.Configure<CommentSummarizationWorkspace>(workspace =>
        {
            workspace.ConfigureChatClient(chat =>
            {
                chat.Builder = CreateSummarizationChatClientBuilder();
            });
        });
    });
}
```

`WorkspaceConfiguration` always exposes `ChatClient` and `Kernel` configurations. Set each `Builder` once; use `ConfigureBuilder(...)` to append named or unnamed builder actions, which ABP applies in insertion order before registering services.

For Semantic Kernel, call `workspace.ConfigureKernel(kernel => kernel.Builder = ...)`. The ABP source consumes `AbpAIWorkspaceOptions`; do not copy documentation examples that use `PreConfigure<AbpAIOptions>` for kernel setup.

### 5. Resolve the narrowest service

For a required default chat client, inject Microsoft's `IChatClient`. For optional AI in a reusable module, inject ABP's `IChatClientAccessor` and null-check `ChatClient`.

For typed workspaces:

```csharp
public class CommentSummarizer
{
    private readonly IChatClientAccessor<CommentSummarizationWorkspace> _accessor;

    public CommentSummarizer(
        IChatClientAccessor<CommentSummarizationWorkspace> accessor)
    {
        _accessor = accessor;
    }

    public async Task<string?> SummarizeAsync(string comment)
    {
        var client = _accessor.ChatClient;
        return client is null
            ? null
            : (await client.GetResponseAsync(comment)).Text;
    }
}
```

Verified behavior:

- `IChatClientAccessor<TWorkspace>` falls back to the default chat client when the named client is absent.
- `IChatClient<TWorkspace>` also falls back to the default, but resolution fails if neither exists.
- `IKernelAccessor<TWorkspace>` does not fall back to the default kernel; it returns null when its keyed kernel is absent.
- `IChatClientAccessor` and `IKernelAccessor` for the default workspace return nullable values.
- Configuring only a chat client causes ABP to build a keyed Kernel containing that chat client. Configuring only a Kernel can expose the Kernel's required `IChatClient` under the workspace chat-client key.

For Agent Framework, obtain the configured `IChatClient`, call `CreateAIAgent(...)`, then run the returned `AIAgent`. Workspace configuration remains the same.

## Validation

- Start with no configured workspace and verify optional accessors return null.
- Configure the default workspace and verify untyped `IChatClient` resolves and sends a test request to the chosen provider.
- Configure two typed workspaces and verify each resolves its own keyed client/model.
- Verify typed chat fallback and typed kernel no-fallback behavior separately.
- Keep provider calls out of unit tests or replace the client with a deterministic test double; run one explicit integration test for credentials/network wiring.

## Common Pitfalls

- **Using `Configure<AbpAIWorkspaceOptions>` instead of `PreConfigure`** — the module executes pre-configured actions while registering services.
- **Copying the Semantic Kernel doc's `AbpAIOptions` example** — ABP source configuration uses `AbpAIWorkspaceOptions`; `AbpAIOptions` only tracks configured workspace names.
- **Assuming all typed accessors share fallback behavior** — chat accessors fall back to default; kernel accessors do not.
- **Injecting required `IChatClient` into an optional reusable module** — use `IChatClientAccessor` and handle null.
- **Treating Agent Framework as separate ABP configuration** — it is built on the configured Microsoft.Extensions.AI `IChatClient`.
- **Hard-coding secrets in module code** — obtain endpoints, keys, and model names from secure host configuration.
- **Freezing these APIs for future ABP versions** — this area is explicitly version-sensitive; re-verify after upgrading.
