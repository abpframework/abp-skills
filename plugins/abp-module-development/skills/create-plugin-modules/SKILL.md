---
name: create-plugin-modules
description: >
  Load ABP modules at runtime as plug-ins instead of referencing their assemblies directly, via AbpApplicationCreationOptions.PlugInSources.
  USE FOR: configuring options.PlugInSources with AddFolder / AddFiles / AddTypes (or a custom IPlugInSource), building a class-library plug-in module deriving from AbpModule, wiring MVC/Razor Pages plug-ins with AssemblyPart / CompiledRazorAssemblyPart application parts.
  DO NOT USE FOR: defining ordinary referenced modules, [DependsOn], or DI registration (use define-application-modules); overall solution layering (use layered-architecture); building the actual UI pages inside a plug-in (use blazor-ui, mvc-razor-ui, or angular-ui).
license: MIT
---

# ABP Plug-In Modules

An ABP module can be loaded as a **plug-in**: instead of adding a project/assembly reference, you point the application at assemblies (or types) to load at startup. ABP discovers the module classes, configures and initializes them exactly like referenced modules.

## When to Use

- Loading modules at runtime from a folder or explicit assemblies rather than a compile-time reference.
- Configuring `options.PlugInSources` with `AddFolder`, `AddFiles`, `AddTypes`, or a custom `IPlugInSource`.
- Building a class-library plug-in module that derives from `AbpModule`.
- Wiring an MVC/Razor Pages plug-in so ASP.NET Core discovers its controllers/pages.

## When Not to Use

- **Defining an ordinary referenced module, `[DependsOn]`, or DI registration** — use the define-application-modules skill.
- **Overall solution layering** — use the layered-architecture skill.
- **Building the actual UI pages inside a plug-in** — use the blazor-ui, mvc-razor-ui, or angular-ui skill.

## How it works

### Configuring Plug-In Sources

Configure `options.PlugInSources` when creating the application. In an ASP.NET Core app this is the options callback of `AddApplicationAsync<T>`:

```csharp
await builder.AddApplicationAsync<MyPlugInDemoWebModule>(options =>
{
    options.PlugInSources.AddFolder(@"D:\Temp\MyPlugIns");
});
```

`PlugInSources` is a list of `IPlugInSource`. There are three built-in shortcuts:

- **`AddFolder(path)`** — loads assemblies (`.dll`) in the given folder. It does **not** recurse by default; pass `SearchOption.AllDirectories` as a second argument to include sub-folders. Shortcut for `PlugInSources.Add(new FolderPlugInSource(path))`.
- **`AddFiles(...)`** — loads a specific list of assembly files. Shortcut for `FilePlugInSource`.
- **`AddTypes(...)`** — takes module class types directly; you must load their assemblies yourself, but it gives full control. Shortcut for `TypePlugInSource`.

```csharp
options.PlugInSources.Add(new FolderPlugInSource(@"D:\Temp\MyPlugIns"));
// or
options.PlugInSources.AddFolder(@"D:\Temp\MyPlugIns", SearchOption.AllDirectories);
```

You can also implement your own `IPlugInSource` and add it to `options.PlugInSources`.

`PlugInSources` is exposed on `AbpApplicationCreationOptions`, so it is available anywhere you create the application via `AbpApplicationFactory.CreateAsync<T>(options => ...)` as well, not only ASP.NET Core.

### Building a Simple Plug-In

A plug-in is an ordinary class library. Add at least `Volo.Abp.Core` (`abp add-package Volo.Abp.Core`) and define a module class deriving from `AbpModule`.

```csharp
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.Modularity;

namespace MyPlugIn
{
    public class MyPlugInModule : AbpModule
    {
        public override void OnApplicationInitialization(ApplicationInitializationContext context)
        {
            var myService = context.ServiceProvider.GetRequiredService<MyService>();
            myService.Initialize();
        }
    }
}
```

Any service the plug-in registers (e.g. via `ITransientDependency`) is available through DI once the plug-in is loaded:

```csharp
using Microsoft.Extensions.Logging;
using Volo.Abp.DependencyInjection;

namespace MyPlugIn
{
    public class MyService : ITransientDependency
    {
        private readonly ILogger<MyService> _logger;

        public MyService(ILogger<MyService> logger) => _logger = logger;

        public void Initialize() => _logger.LogInformation("MyService has been initialized");
    }
}
```

Build the project, then copy the produced `MyPlugIn.dll` into the plug-in folder (e.g. `D:\Temp\MyPlugIns`).

### Plug-Ins with Razor Pages / MVC

UI plug-ins need extra wiring. Change the csproj `Sdk` to `Microsoft.NET.Sdk.Web`, set `<OutputType>Library</OutputType>` and `<IsPackable>true</IsPackable>`, and reference a suitable package such as `Volo.Abp.AspNetCore.Mvc.UI.Theme.Shared`. Then register the assembly as an MVC application part in `PreConfigureServices`:

```csharp
[DependsOn(typeof(AbpAspNetCoreMvcUiThemeSharedModule))]
public class MyMvcUIPlugInModule : AbpModule
{
    public override void PreConfigureServices(ServiceConfigurationContext context)
    {
        PreConfigure<IMvcBuilder>(mvcBuilder =>
        {
            mvcBuilder.PartManager.ApplicationParts.Add(
                new AssemblyPart(typeof(MyMvcUIPlugInModule).Assembly));

            // Required if the plug-in contains compiled razor views:
            mvcBuilder.PartManager.ApplicationParts.Add(
                new CompiledRazorAssemblyPart(typeof(MyMvcUIPlugInModule).Assembly));
        });
    }
}
```

Without registering the `AssemblyPart` (and `CompiledRazorAssemblyPart` for views), ASP.NET Core will not discover the plug-in's controllers or pages. Build, copy the resulting `.dll` into the plug-in folder, and the pages become reachable once the application loads the plug-in.

### Practical Notes

- **Library dependencies**: copy the plug-in's dependent DLLs into the plug-in folder too — ABP loads all assemblies in the folder.
- **Database schema**: a plug-in with its own tables must get them created/migrated — e.g. run EF Core migrations on startup, or teach your `DbMigrator` to include plug-in migrations.
- What a module does internally is up to you; ABP's only job is discovering and initializing the module at startup.

## Validation

- Choose the right source: `AddFolder` (a directory of DLLs), `AddFiles` (explicit files), or `AddTypes` (known module types).
- Plug-in = class library with an `AbpModule` class; reference at least `Volo.Abp.Core`.
- For MVC/Razor plug-ins, register `AssemblyPart` (+ `CompiledRazorAssemblyPart`) via `PreConfigure<IMvcBuilder>`.
- Copy the plug-in DLL (and its dependencies) into the plug-in folder; on startup confirm the module's `OnApplicationInitialization` runs and its services resolve — for UI plug-ins, that the controllers/pages become reachable.

## Common Pitfalls

- **Loading from a raw build output folder** — copy the plug-in DLLs into a dedicated plug-in/staging folder and remove `*.deps.json` (e.g. `MyPlugIn.deps.json`) *there*; don't delete files in place in the build output or repo. Better, exclude `*.deps.json` when you publish the plug-in.
- **Expecting `AddFolder` to recurse** — it does not by default; pass `SearchOption.AllDirectories` for sub-folders.
- **Forgetting `CompiledRazorAssemblyPart`** for a plug-in with compiled razor views — `AssemblyPart` alone won't surface the views.
- **Not copying dependent DLLs** into the plug-in folder — ABP loads all assemblies there, so missing dependencies fail at load.
- **Ignoring the plug-in's database schema** — its own tables still need creation/migration.
