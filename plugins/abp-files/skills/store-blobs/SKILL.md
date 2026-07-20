---
name: store-blobs
description: >
  Save, read and delete named binary objects (BLOBs) in an ABP app through the storage-agnostic IBlobContainer abstraction.
  USE FOR: storing/reading profile pictures, uploads, attachments or other binary data via IBlobContainer (default or typed), defining typed containers, configuring providers (file system, database, Azure, AWS/S3, MinIO), per-tenant BLOB isolation.
  DO NOT USE FOR: embedding static js/css/image/localization assets into an assembly or overriding a module's embedded files (use manage-virtual-files); building a full file-management UI with folders/permissions/sharing (blob storing is intentionally not that).
license: MIT
---

# Storing BLOBs with ABP Blob Storing

ABP's Blob Storing system is a storage-agnostic abstraction for saving, reading and deleting named binary objects (BLOBs). You write against `IBlobContainer` and pick a provider (file system, database, Azure, AWS/S3, MinIO, ...) via configuration, so the application code never changes when you switch storage.

Package: `Volo.Abp.BlobStoring` (`AbpBlobStoringModule`). Add it with `abp add-package Volo.Abp.BlobStoring` or a `PackageReference` plus `[DependsOn(typeof(AbpBlobStoringModule))]`.

## When to Use

- Saving/reading/deleting binary files (profile pictures, uploads, attachments) without touching the file system or a provider SDK directly.
- Defining a typed container (`IBlobContainer<T>`) for a specific kind of BLOB.
- Selecting or switching a storage provider (file system, database, Azure, AWS/S3, MinIO) through configuration.
- Controlling per-tenant BLOB isolation.

## When Not to Use

- **Embedding static assets (js/css/images/localization) into an assembly** or overriding a depended-on module's embedded files — use the **manage-virtual-files** skill.
- **Building a file-management system with folders, permissions or sharing** — blob storing is deliberately not that; build such features on top.

## How it works

### The default container

Inject `IBlobContainer` to use the built-in **default** container (its name is `default`). `SaveAsync` takes a `Stream` by default; an extension method accepts `byte[]`.

```csharp
using Volo.Abp.BlobStoring;
using Volo.Abp.DependencyInjection;

public class MyService : ITransientDependency
{
    private readonly IBlobContainer _blobContainer;

    public MyService(IBlobContainer blobContainer)
    {
        _blobContainer = blobContainer;
    }

    public async Task SaveBytesAsync(byte[] bytes)
    {
        // overrideExisting defaults to false and throws BlobAlreadyExistsException on a name clash
        await _blobContainer.SaveAsync("my-blob-1", bytes, overrideExisting: true);
    }

    public async Task<byte[]?> GetBytesAsync()
    {
        return await _blobContainer.GetAllBytesOrNullAsync("my-blob-1");
    }
}
```

A BLOB name is an arbitrary string that must be **unique per container** (and per tenant, see below).

### Core methods (on `IBlobContainer`)

- `SaveAsync(name, stream, overrideExisting = false, cancellationToken)` — save/replace. With `overrideExisting: false` it throws if the name already exists. An extension overload takes `byte[]` instead of `Stream`.
- `GetAsync(name)` — returns a `Stream`; **throws** if the BLOB is missing. Always dispose the stream.
- `GetOrNullAsync(name)` — like `GetAsync` but returns `null` when missing.
- `GetAllBytesAsync(name)` — extension method returning `byte[]`; throws if missing.
- `GetAllBytesOrNullAsync(name)` — extension method returning `byte[]?`; `null` when missing.
- `DeleteAsync(name)` — returns `true` if it actually deleted something, `false` if the name was not found. Does not throw when missing.
- `ExistsAsync(name)` — returns `bool`.

### Typed containers

For anything beyond the default container — and always in reusable modules — define a typed container. Decorate a marker class with `[BlobContainerName]` and inject `IBlobContainer<T>`, which exposes the same methods.

```csharp
[BlobContainerName("profile-pictures")]
public class ProfilePictureContainer { }

[Authorize]
public class ProfileAppService : ApplicationService
{
    private readonly IBlobContainer<ProfilePictureContainer> _blobContainer;

    public ProfileAppService(IBlobContainer<ProfilePictureContainer> blobContainer)
    {
        _blobContainer = blobContainer;
    }

    public async Task SaveAsync(byte[] bytes)
    {
        await _blobContainer.SaveAsync(CurrentUser.GetId().ToString(), bytes, overrideExisting: true);
    }
}
```

Without `[BlobContainerName]` the container name falls back to the class full name, so always add the attribute to keep the name stable across renames. Typed containers are just named containers; `IBlobContainerFactory.Create("profile-pictures")` / `Create<ProfilePictureContainer>()` resolves the same thing by name or type.

### Configuring providers

`AbpBlobStoringOptions.Containers` holds per-container configuration. Configure it in `ConfigureServices`. Each container selects a provider through a `Use...` extension on `BlobContainerConfiguration`.

Every provider — including the file system one — lives in its own package. For `UseFileSystem` add `Volo.Abp.BlobStoring.FileSystem` and depend on `AbpBlobStoringFileSystemModule`; the extension is in the `Volo.Abp.BlobStoring.FileSystem` namespace:

```csharp
using Volo.Abp.BlobStoring;
using Volo.Abp.BlobStoring.FileSystem;

[DependsOn(
    typeof(AbpBlobStoringModule),
    typeof(AbpBlobStoringFileSystemModule)
)]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpBlobStoringOptions>(options =>
        {
            options.Containers.Configure<ProfilePictureContainer>(container =>
            {
                container.UseFileSystem(fileSystem =>
                {
                    fileSystem.BasePath = "C:\\my-files";
                });
            });
        });
    }
}
```

- `Configure<TContainer>(...)` / `Configure("name", ...)` — one specific container. Called again for the same container, it mutates the same configuration, so a later call can override an earlier one.
- `ConfigureDefault(...)` — the default container. A container **without its own configuration falls back to the default**, so this sets a baseline for all containers.
- `ConfigureAll((name, config) => ...)` — runs the action once over the containers **that already exist** at that moment. It is not a permanent global rule: it doesn't touch containers configured afterwards, and a later `Configure<T>(...)` still overrides what it set.

Provider is chosen by the `Use...` call. Each provider ships in its own package and is a variant of the same shape (add the package + configure credentials/endpoint):

- `UseFileSystem(...)` — `Volo.Abp.BlobStoring.FileSystem`
- `UseDatabase(...)` — `Volo.Abp.BlobStoring.Database`
- `UseAzure(...)` — `Volo.Abp.BlobStoring.Azure`
- `UseAws(...)` — `Volo.Abp.BlobStoring.Aws` (also S3-compatible: MinIO, R2, Spaces, ... via `ServiceURL`)
- `UseMinio(...)` — `Volo.Abp.BlobStoring.Minio`

Blob storing does nothing until a provider is configured for the container you use.

### Mainstream storage providers

Each provider ships in its own package: add the package, depend on its module, and select it with the matching `Use...` call on the container. The blocks below configure the **default** container (`ConfigureDefault`), so every container without its own configuration uses it. The File System example above shows the same shape for a typed container.

**Azure** — package `Volo.Abp.BlobStoring.Azure`:

```csharp
[DependsOn(typeof(AbpBlobStoringModule), typeof(AbpBlobStoringAzureModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        var configuration = context.Services.GetConfiguration();
        Configure<AbpBlobStoringOptions>(options =>
        {
            options.Containers.ConfigureDefault(container =>
            {
                container.UseAzure(azure =>
                {
                    // Read the connection string from configuration/a secret store — never hardcode it
                    azure.ConnectionString = configuration["Blob:Azure:ConnectionString"];
                    azure.ContainerName = "my-container";
                    azure.CreateContainerIfNotExists = true;
                });
            });
        });
    }
}
```

**AWS S3** — package `Volo.Abp.BlobStoring.Aws`. The S3 bucket is set via `ContainerName` (there is no `Bucket` property); point `ServiceURL` at an S3-compatible endpoint for MinIO/R2/Spaces:

```csharp
[DependsOn(typeof(AbpBlobStoringModule), typeof(AbpBlobStoringAwsModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        var configuration = context.Services.GetConfiguration();
        Configure<AbpBlobStoringOptions>(options =>
        {
            options.Containers.ConfigureDefault(container =>
            {
                container.UseAws(aws =>
                {
                    // Read credentials from configuration/env/a secret store — never hardcode them
                    aws.AccessKeyId = configuration["Aws:AccessKeyId"];
                    aws.SecretAccessKey = configuration["Aws:SecretAccessKey"];
                    aws.UseCredentials = true;
                    aws.Region = "us-east-1";
                    aws.ContainerName = "my-bucket";
                    aws.CreateContainerIfNotExists = true;
                });
            });
        });
    }
}
```

**Database** — package `Volo.Abp.BlobStoring.Database`; depend on the EF Core (`BlobStoringDatabaseEntityFrameworkCoreModule`) or MongoDB (`BlobStoringDatabaseMongoDbModule`) module. `UseDatabase()` takes no options — it stores BLOBs in your database (uses the `AbpBlobStoring` connection string if defined, otherwise `Default`). For EF Core also call `builder.ConfigureBlobStoring()` in your migration DbContext's `OnModelCreating`:

```csharp
[DependsOn(typeof(AbpBlobStoringModule), typeof(BlobStoringDatabaseEntityFrameworkCoreModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpBlobStoringOptions>(options =>
        {
            options.Containers.ConfigureDefault(container =>
            {
                container.UseDatabase();
            });
        });
    }
}
```

**MinIO** — package `Volo.Abp.BlobStoring.Minio`:

```csharp
[DependsOn(typeof(AbpBlobStoringModule), typeof(AbpBlobStoringMinioModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        var configuration = context.Services.GetConfiguration();
        Configure<AbpBlobStoringOptions>(options =>
        {
            options.Containers.ConfigureDefault(container =>
            {
                container.UseMinio(minio =>
                {
                    minio.EndPoint = "localhost:9000";
                    // Read credentials from configuration/env/a secret store — never hardcode them
                    minio.AccessKey = configuration["Minio:AccessKey"];
                    minio.SecretKey = configuration["Minio:SecretKey"];
                    minio.BucketName = "my-bucket";
                    minio.WithSSL = false;
                    minio.CreateBucketIfNotExists = true;
                });
            });
        });
    }
}
```

The remaining providers (Aliyun, Google Cloud, Bunny, Memory) follow the same `UseXxx` pattern and are configured per the ABP docs.

### Multi-tenancy

All providers isolate BLOBs per tenant automatically, so the same BLOB name can coexist across tenants. To share a container's BLOBs across all tenants, disable multi-tenancy for it:

```csharp
Configure<AbpBlobStoringOptions>(options =>
{
    options.Containers.Configure<ProfilePictureContainer>(container =>
    {
        container.IsMultiTenant = false;
    });
});
```

## Validation

- Call `SaveAsync` then `ExistsAsync`/`GetAllBytesOrNullAsync` for the same name and confirm the bytes round-trip. If no provider is registered/configured for that container, resolving the `IBlobContainer<T>` throws `AbpException` — the container factory runs the provider selector as it creates the container, so resolution fails before any blob operation runs, rather than silently succeeding.
- With the file system provider, check the configured `BasePath` on disk for the written file.
- To confirm per-tenant isolation, save the same BLOB name under two tenants and verify both coexist.

## Common Pitfalls

- Blob storing needs a provider registered and configured for the container you use — otherwise the provider selector **throws `AbpException`** while the container is being resolved/created (in the container factory), not silently no-op.
- **Don't hardcode provider credentials** (Azure connection strings, AWS/MinIO access keys and secrets). Read them from configuration, environment variables, or a secret store — keep them out of source control, command history, and logs.
- `SaveAsync` defaults `overrideExisting` to `false` and throws `BlobAlreadyExistsException` on a name clash; pass `overrideExisting: true` to replace.
- `GetAsync` / `GetAllBytesAsync` **throw** when the BLOB is missing; use the `...OrNull...` variants to get `null` instead.
- Always add `[BlobContainerName]` to a typed container's marker class — without it the name falls back to the class full name and breaks on rename.
- A container without its own configuration falls back to the default container's configuration.
- Blob storing is **not** a file management system (no folders, permissions or sharing) — build those on top if needed.
