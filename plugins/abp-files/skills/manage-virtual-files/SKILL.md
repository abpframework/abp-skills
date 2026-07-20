---
name: manage-virtual-files
description: >
  Embed static assets into assemblies and read/override them at runtime through the ABP Virtual File System.
  USE FOR: embedding js/css/image/localization files as Embedded Resources, registering them with AbpVirtualFileSystemOptions.FileSets, reading embedded files via IVirtualFileProvider, overriding an embedded file shipped by a depended-on module, dev-time live editing with ReplaceEmbeddedByPhysical.
  DO NOT USE FOR: storing user uploads / profile pictures / large binary objects in a pluggable storage backend (use store-blobs); the resource/key/translation semantics of localization files (use localize-applications for resources and fallback; menus-and-localization for menu display text).
license: MIT
---

# Managing the ABP Virtual File System

The Virtual File System (VFS) lets you treat files that are **embedded into assemblies** (or otherwise not on disk) as if they were physical files at runtime. It's how reusable ABP modules ship their js/css/image and localization assets, and how an application overrides those assets without editing the module.

Package: `Volo.Abp.VirtualFileSystem` (`AbpVirtualFileSystemModule`). It usually comes pre-installed via the startup templates; otherwise `abp add-package Volo.Abp.VirtualFileSystem` + `[DependsOn(typeof(AbpVirtualFileSystemModule))]`.

## When to Use

- Embedding js/css/image/localization assets into an assembly as Embedded Resources.
- Registering an assembly's embedded files with `AbpVirtualFileSystemOptions.FileSets`.
- Reading embedded files at runtime via `IVirtualFileProvider`.
- Overriding an embedded file that a depended-on ABP module ships.
- Live-editing a module's embedded files during development.

## When Not to Use

- **Storing user-generated binary content** (uploads, profile pictures, attachments) in a pluggable storage backend — use the **store-blobs** skill.
- **The resource/key/translation semantics of localization files** — use the **localize-applications** skill (resources, json format, inheritance, culture fallback); menu display text lives in **menus-and-localization**. VFS only carries the *files*, not their meaning.

## How it works

### Embedding files into an assembly

Mark files as **Embedded Resource** (Build Action in the IDE, or edit the `.csproj`). To embed a whole folder recursively:

```xml
<ItemGroup>
  <EmbeddedResource Include="MyResources\**\*.*" />
  <Content Remove="MyResources\**\*.*" />
</ItemGroup>
```

Strongly recommended (avoids problems with special characters in file names): add the `Microsoft.Extensions.FileProviders.Embedded` package and set `<GenerateEmbeddedFilesManifest>true</GenerateEmbeddedFilesManifest>` in a `<PropertyGroup>`.

### Registering embedded files

Register the assembly's embedded files with `AbpVirtualFileSystemOptions.FileSets.AddEmbedded<TModule>()` in your module's `ConfigureServices`. Pass any type from the target assembly — `AddEmbedded` scans the **assembly of that type**.

```csharp
public override void ConfigureServices(ServiceConfigurationContext context)
{
    Configure<AbpVirtualFileSystemOptions>(options =>
    {
        options.FileSets.AddEmbedded<MyModule>();
    });
}
```

`AddEmbedded<T>` takes two optional arguments:

- `baseNamespace` — only needed if you skipped `GenerateEmbeddedFilesManifest` and your root namespace is non-empty; set it to the root namespace.
- `baseFolder` — expose only a subfolder (and its children) instead of the whole project.

```csharp
options.FileSets.AddEmbedded<MyModule>(
    baseNamespace: "Acme.BookStore",
    baseFolder: "/MyResources"
);
```

### Reading files at runtime

Inject `IVirtualFileProvider` (it implements `Microsoft.Extensions.FileProviders.IFileProvider`) to read the unified virtual tree. Paths are virtual (start at `/`), not physical disk paths.

```csharp
using Microsoft.Extensions.FileProviders;
using Volo.Abp.DependencyInjection;
using Volo.Abp.VirtualFileSystem;

public class MyService : ITransientDependency
{
    private readonly IVirtualFileProvider _virtualFileProvider;

    public MyService(IVirtualFileProvider virtualFileProvider)
    {
        _virtualFileProvider = virtualFileProvider;
    }

    public string ReadJs()
    {
        // single file — IFileInfo
        IFileInfo file = _virtualFileProvider.GetFileInfo("/MyResources/js/test.js");
        var content = file.ReadAsString(); // ABP extension; ReadAsStringAsync also available

        // everything under a directory
        var dir = _virtualFileProvider.GetDirectoryContents("/MyResources/js");

        return content;
    }
}
```

Check `file.Exists` before reading if the path may be absent.

### Overriding / replacing embedded files

The VFS merges files from every module into one tree. When two modules register a file at the **same virtual path** (e.g. `my-path/my-file.css`), the one added **later wins** — and module dependency order determines that order. Because a depending module is registered after the modules it depends on, this is how you override an asset shipped by a module you depend on:

> To replace a file from a depended-on module, put a file at the **exact same virtual path** in your own module/application.

Two important rules:

- Precedence follows **file-set registration order, not file type** — there is no special "physical always beats embedded" rule. The provider is built from `FileSets` in reverse registration order, so the last file set registered for a given virtual path wins. To override a module's asset, register a file set (embedded or physical) at the same virtual path after that module — dependency order already puts your module later.
- ASP.NET Core integration means embedded js/css/images are served like static files, and static content is also allowed next to `Pages`, `Views`, `Components` and `Themes` folders (not just `wwwroot`).

### Development-time live editing

Recompiling to see an embedded-file change is tedious while developing a module. Use `ReplaceEmbeddedByPhysical<TModule>(physicalPath)` (guarded to development only) so the app reads the module's files directly from disk and a browser refresh reflects edits:

```csharp
[DependsOn(typeof(MyModule))]
public class MyWebAppModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        var env = context.Services.GetHostingEnvironment();
        if (env.IsDevelopment())
        {
            Configure<AbpVirtualFileSystemOptions>(options =>
            {
                options.FileSets.ReplaceEmbeddedByPhysical<MyModule>(
                    Path.Combine(env.ContentRootPath,
                        $"..{Path.DirectorySeparatorChar}MyModuleProject"));
            });
        }
    }
}
```

The startup templates already use this technique for localization files.

## Validation

- Build and confirm the files are compiled as Embedded Resources (they show up in `Assembly.GetManifestResourceNames()`); if they're missing there, the `EmbeddedResource` item isn't set. `GenerateEmbeddedFilesManifest` is optional — without it ABP falls back to `AbpEmbeddedFileProvider`, so leaving it unset does not stop resources from being embedded or served.
- At runtime, call `IVirtualFileProvider.GetFileInfo("/...")` and check `file.Exists` / `ReadAsString()` returns the embedded content.
- To confirm an override, register a file at the same virtual path in the depending module and verify the served content is yours, not the base module's.
- With `ReplaceEmbeddedByPhysical`, edit a file on disk in development and confirm a browser refresh shows the change without recompiling.

## Common Pitfalls

- Set `<GenerateEmbeddedFilesManifest>true</GenerateEmbeddedFilesManifest>` (plus the `Microsoft.Extensions.FileProviders.Embedded` package) to avoid problems with special characters in file names; if you skip it and have a non-empty root namespace, you must pass `baseNamespace` to `AddEmbedded<T>`.
- Precedence is by **file-set registration order, not file type** — there is no "physical always beats embedded" rule; the last file set registered for a virtual path wins.
- To override a module's asset your file must be at the **exact same virtual path**; dependency order already puts your module later so its file set wins.
- Virtual paths start at `/` and are not physical disk paths.
- `ReplaceEmbeddedByPhysical` is a development-only technique — keep it guarded behind `IsDevelopment()`.
