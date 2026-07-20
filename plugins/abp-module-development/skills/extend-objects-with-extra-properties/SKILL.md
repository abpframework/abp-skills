---
name: extend-objects-with-extra-properties
description: >
  Add framework-level dynamic properties to any ABP entity or DTO that implements IHasExtraProperties.
  USE FOR: IHasExtraProperties and ExtraPropertyDictionary; ExtensibleObject and extensible aggregate roots/DTOs; ObjectExtensionManager definitions; GetProperty/SetProperty; EF Core JSON or dedicated-column persistence; MongoDB extra elements; mapping extra properties between entities and DTOs.
  DO NOT USE FOR: extending an installed Identity, Account, or other pre-built module through its module-specific extension configurator (use customize-application-modules); ordinary object mapping without extra properties (use map-objects-and-dtos); designing aggregate invariants and entity relationships (use model-domain-aggregates).
license: MIT
---

# Extending Objects with Extra Properties

`IHasExtraProperties` gives an object an `ExtraPropertyDictionary`, while `ObjectExtensionManager` defines the names, types, defaults, validation metadata, and persistence/mapping metadata for those entries. This is framework-level object extension, not the module-specific extension API for installed ABP modules.

## When to Use

- Add runtime-defined properties to your own entity, aggregate root, command DTO, or result DTO.
- Read and write typed values without adding CLR properties.
- Persist the dictionary as JSON with EF Core or as MongoDB extra elements.
- Promote selected EF Core extra properties to dedicated columns.
- Copy explicitly defined extra properties between an entity and DTO.

## When Not to Use

- **Customize an installed pre-built module** — use customize-application-modules and its module extension configurator.
- **Map ordinary CLR members** — use map-objects-and-dtos.
- **Design entities, value objects, or aggregate invariants** — use model-domain-aggregates.

## How it works

### Make both ends extensible

`IHasExtraProperties` exposes a read-only `ExtraProperties` property of type `ExtraPropertyDictionary`, which derives from `Dictionary<string, object?>`. ABP aggregate roots already implement it. For a standalone DTO or object, derive from `ExtensibleObject` or implement the interface and initialize the dictionary yourself.

```csharp
using Volo.Abp.Application.Dtos;
using Volo.Abp.Domain.Entities;
using Volo.Abp.ObjectExtending;

public class Product : AggregateRoot<Guid>
{
    public string Name { get; private set; }

    protected Product()
    {
        Name = string.Empty;
    }

    public Product(Guid id, string name) : base(id)
    {
        Name = name;
    }
}

public class ProductDto : ExtensibleObject, IEntityDto<Guid>
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
}
```

`ExtensibleObject` initializes the dictionary and, by default, fills defaults registered in `ObjectExtensionManager`. `AggregateRoot` and `AggregateRoot<TKey>` do the same.

### Define properties before objects are created or mapped

Define the property for every participating type. Default extra-property mapping checks the source/destination pair, so defining only the entity is not enough for a DTO mapping.

```csharp
using System.ComponentModel.DataAnnotations;
using Volo.Abp.ObjectExtending;

public static class ProductObjectExtensions
{
    public const string ManufacturerCode = "ManufacturerCode";

    public static void Configure()
    {
        ObjectExtensionManager.Instance
            .AddOrUpdateProperty<Product, string>(
                ManufacturerCode,
                property => property.Attributes.Add(new StringLengthAttribute(32)))
            .AddOrUpdateProperty<ProductDto, string>(
                ManufacturerCode,
                property => property.Attributes.Add(new StringLengthAttribute(32)));
    }
}
```

Run this configuration once during startup and before creating instances that need registered defaults. `ObjectExtensionManager.Instance` is global process state; keep names in constants and make repeated configuration deterministic.

### Read and write values

```csharp
product.SetProperty(ProductObjectExtensions.ManufacturerCode, "ACME-42");

var code = product.GetProperty<string>(
    ProductObjectExtensions.ManufacturerCode);
```

- `SetProperty` validates by default through `ExtensibleObjectValidator`; pass `validate: false` only for a deliberate trusted-data path.
- `GetProperty<TProperty>` converts primitive-compatible values through ABP's type helper and returns the supplied/default value when absent.
- `HasProperty` checks dictionary membership; `RemoveProperty` deletes an entry.

### EF Core persistence

`ConfigureByConvention()` includes `TryConfigureExtraProperties()`. For an `IHasExtraProperties` entity, EF Core maps `ExtraProperties` to a column of the same name, converts the dictionary to JSON, and installs a value comparer.

```csharp
builder.ConfigureByConvention();
```

To map one entry to a real column, configure it before model creation:

```csharp
ObjectExtensionManager.Instance.MapEfCoreProperty<Product, string>(
    ProductObjectExtensions.ManufacturerCode,
    (entityBuilder, propertyBuilder) =>
    {
        propertyBuilder.HasMaxLength(32);
        propertyBuilder.HasColumnName("ManufacturerCode");
    });
```

The EF Core JSON converter removes properties mapped to fields/columns from the JSON copy, so the promoted property is not duplicated there. Add a migration after changing the model.

### MongoDB persistence

`BsonClassMap.ConfigureAbpConventions()` calls `AutoMap()` and `TryConfigureExtraProperties()`. For a class that directly declares `ExtraProperties`, ABP maps it as MongoDB extra elements rather than a nested JSON field.

```csharp
classMap.ConfigureAbpConventions();
```

Keep this convention in the MongoDB class-map setup for the entity. The MongoDB implementation deliberately checks the declaring type, so inherited mappings are configured on the declaring class rather than repeatedly on derived maps.

### Map entity extra properties to DTOs

For AutoMapper, opt in on the map:

```csharp
CreateMap<Product, ProductDto>()
    .MapExtraProperties();
```

Both types must implement `IHasExtraProperties`. With the default definition checks, the property must be registered for both types unless its `CheckPairDefinitionOnMapping` metadata explicitly relaxes the pair check. Mapperly uses `[MapExtraProperties]` on the mapper class and supports definition checks, ignored names, and mapping to regular CLR properties.

## Validation

- Assert a new extensible object has a non-null `ExtraProperties` dictionary.
- Set and get each property using the expected generic type; verify invalid values fail validation.
- With EF Core, save/reload and inspect the `ExtraProperties` JSON column; for promoted properties, verify the dedicated column and confirm the JSON does not duplicate it.
- With MongoDB, save/reload and verify entries are stored as extra BSON elements.
- Map entity to DTO and back; verify only properties allowed by the definition checks are copied.

## Common Pitfalls

- **Defining the property after constructing objects** — constructor default filling has already run. Configure extensions early.
- **Defining only the entity property** — default entity-to-DTO mapping requires compatible definitions on both sides.
- **Writing directly to the dictionary** — this bypasses `SetProperty` validation. Prefer `SetProperty` for application input.
- **Forgetting `ConfigureByConvention()` in EF Core** — the dictionary converter and object-extension mappings are not applied by that entity configuration.
- **Expecting every extra property to become an EF Core column** — the default is one JSON `ExtraProperties` column; call `MapEfCoreProperty` and add a migration for a dedicated column.
- **Using this generic workflow for a packaged ABP module** — module-specific entity/DTO/UI propagation belongs to customize-application-modules.
