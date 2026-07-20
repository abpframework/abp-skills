---
name: map-objects-and-dtos
description: >
  Maps entities to DTOs (or object-to-object) in an ABP app through the IObjectMapper abstraction.
  USE FOR: IObjectMapper usage, defining AutoMapper profiles or Mapperly mappers, registering maps with AbpAutoMapperOptions.AddMaps, mapping extra properties, mapping collections, custom/contextual mappers, the mapping-direction rule (auto-map entity to output DTO; build rich domain entities explicitly) and input/output DTO design rules (one input DTO per use case).
  DO NOT USE FOR: designing the application service that calls the mapper (use application-services) or the standard CrudAppService workflow and its mapping paths (use build-crud-application-services); adding extra properties to a pre-built module's entities/DTOs (use customize-application-modules); implementing validation attributes, IValidatableObject or FluentValidation mechanics (use handle-validation-and-errors).
license: MIT
---

# Object-to-Object Mapping in ABP

ABP abstracts object mapping behind `IObjectMapper` (in the `Volo.Abp.ObjectMapping` package) and provides integrations for **AutoMapper** and **Mapperly**. Application code depends only on the abstraction; you pick the provider per module.

## When to Use

- Mapping an entity to a DTO (or any object-to-object) via `IObjectMapper`.
- Defining AutoMapper profiles or Mapperly mappers and registering them.
- Mapping extra properties between extensible objects.
- Mapping collections of a mapped type.
- Writing a custom typed mapper or pinning a module to its own mapping library.

## When Not to Use

- **Designing the application service** that performs the mapping — use application-services; the **standard CrudAppService workflow** (its default mapping paths, `MapToEntityAsync` overrides) — use build-crud-application-services. This skill is only the mapping mechanics.
- **Adding extra properties to a pre-built module's entities/DTOs** — use customize-application-modules; here `.MapExtraProperties()` / `[MapExtraProperties]` only covers mapping already-defined extra properties.

## IObjectMapper

`IObjectMapper` defines two `Map` overloads. `ApplicationService` exposes an `ObjectMapper` property; elsewhere inject `IObjectMapper` directly.

```csharp
// Create a new destination DTO from an entity
var userDto = ObjectMapper.Map<User, UserDto>(user);

// Map onto an existing destination object
ObjectMapper.Map<User, UserDto>(user, userDto);
```

The first generic argument is the source type, the second the destination type. You must define the mappings first (see below).

## Mapping direction: output DTOs auto-map, rich entities don't

ABP's DDD guidance is about *where* auto-mapping is safe:

- **Entity → output DTO** — auto-map freely. This is the common case (read an entity, return a DTO).
- **Input DTO → entity** — fine for a **simple CRUD entity** (public setters, no invariants); ABP's `CrudAppService` maps input onto the entity this way by default. For a **rich domain entity** (parameterized constructor, non-public setters, business rules), don't auto-map onto it — build and mutate it explicitly through its constructor and methods (or a domain service), or override `CrudAppService`'s `MapToEntityAsync` (see build-crud-application-services). Auto-mapping onto a rich entity fights the domain model:
  1. its parameterized constructor enforces a valid initial state, but auto-mapping typically needs an empty constructor;
  2. its non-public setters are meant to be changed through methods, not blindly overwritten;
  3. you should validate/process client input deliberately, not copy it straight onto the entity.

```csharp
// Output: map the entity to a DTO
return ObjectMapper.Map<Issue, IssueDto>(issue);

// Input to a rich entity: build it explicitly — NOT ObjectMapper.Map<CreateIssueDto, Issue>(input)
var issue = new Issue(GuidGenerator.Create(), input.RepositoryId, input.Title, input.Text);
```

### DTO design rules (ABP DDD guide)

- **A DTO holds no business logic** and never inherits from or references an entity; keep it serializable (parameterless constructor).
- **One input DTO per use case** — don't reuse or inherit input DTOs across methods. A shared DTO ends up with properties unused by some methods, which confuses callers; duplicating a DTO is better than coupling use cases.
- **Input DTOs carry only formal validation** (data-annotation attributes or `IValidatableObject`), never domain validation — e.g. don't check a unique-name rule in the DTO (that's domain logic — see handle-validation-and-errors and separate-domain-and-application-logic).
- **Return the entity's output DTO from Create/Update** methods so the client can refresh its state without another call. Keep the output DTO set small and reuse output DTOs where reasonable (but never reuse an input DTO as an output DTO).

## AutoMapper Integration

Add the `Volo.Abp.AutoMapper` package and depend on `AbpAutoMapperModule`.

### Define a Profile

```csharp
public class MyProfile : Profile
{
    public MyProfile()
    {
        CreateMap<User, UserDto>();
    }
}
```

### Register with AbpAutoMapperOptions

`AddMaps<TModule>()` registers all profiles (and attribute mappings) in the assembly of the given class — typically your module class:

```csharp
[DependsOn(typeof(AbpAutoMapperModule))]
public class MyModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpAutoMapperOptions>(options =>
        {
            options.AddMaps<MyModule>(validate: true);
        });
    }
}
```

- `validate` (default `false`) enables AutoMapper configuration validation; enabling it is a recommended best practice.
- To validate only specific profiles, call `AddMaps<MyModule>()` without validation, then `options.AddProfile<MyProfile>(validate: true)` per profile.

### Useful profile extensions

```csharp
CreateMap<User, UserDto>().MapExtraProperties();          // map extra properties (both must implement IHasExtraProperties)
CreateMap<ProductDto, Product>().IgnoreAuditedObjectProperties(); // also IgnoreFullAuditedObjectProperties(), IgnoreCreationAuditedObjectProperties()
CreateMap<SimpleClass1, SimpleClass2>().Ignore(x => x.CreationTime); // shorthand for ForMember(..., map => map.Ignore())
```

## Mapperly Integration

Add the `Volo.Abp.Mapperly` package and depend on `AbpMapperlyModule`. Mapperly is a source generator, so mapper classes and methods must be `partial`.

```csharp
[Mapper]
public partial class UserToUserDtoMapper : MapperBase<User, UserDto>
{
    public override partial UserDto Map(User source);
    public override partial void Map(User source, UserDto destination);
}
```

- Use `TwoWayMapperBase<User, UserDto>` to also generate `ReverseMap`.
- Override `BeforeMap` / `AfterMap` (and reverse variants) for pre/post logic.
- Add the `[MapExtraProperties]` attribute on the mapper class to map extra properties (both types must implement `IHasExtraProperties`).
- Source properties only need to be readable; the destination property needs a writable path — a setter (`protected set` / `private set` are fine when Mapperly's member visibility is configured to reach them), a constructor parameter, or an explicit mapping. Destination properties with no writable path are ignored.
- Mapperly respects nullable reference types — declare nullable properties as nullable or risk `NullReferenceException` at runtime.
- Nested types with separate mappers are not composed automatically; consolidate methods, implement multiple `IAbpMapperlyMapper<,>` interfaces on one class, or map nested objects manually in `AfterMap`.

## Mapping Extra Properties

Entities/DTOs that carry extra properties (implement `IHasExtraProperties`) should map them explicitly: `.MapExtraProperties()` (AutoMapper) or `[MapExtraProperties]` (Mapperly). Do this when both sides are extensible objects.

## Collections

Once a source→destination mapping exists, ABP maps collections automatically. Supported: `IEnumerable<T>`, `ICollection<T>`, `Collection<T>`, `IList<T>`, `List<T>`, and arrays.

```csharp
var dtos = ObjectMapper.Map<List<User>, List<UserDto>>(users);
```

## Custom & Contextual Mappers

**Custom typed mapper** — implement `IObjectMapper<TSource, TDestination>` to fully control a specific mapping. ABP auto-discovers and registers it, using it whenever that pair is mapped. It can inject other services.

```csharp
public class MyCustomUserMapper : IObjectMapper<User, UserDto>, ITransientDependency
{
    public UserDto Map(User source) { return new UserDto { /* build a new UserDto */ }; }
    public UserDto Map(User source, UserDto destination) { /* set on existing */ return destination; }
}
```

**Contextual mapper** — `IObjectMapper<TContext>` pins a module to its own mapping library, independent of the final application's default. Register it and use it just like `IObjectMapper`:

```csharp
context.Services.AddAutoMapperObjectMapper<MyModule>();   // or AddMapperlyObjectMapper<MyModule>()
```

Then inject `IObjectMapper<MyModule>`, or set `ObjectMapperContext = typeof(MyModule);` in an `ApplicationService` constructor to make the inherited `ObjectMapper` property use it. Reusable modules use this so they always map with the library they defined profiles for; final applications can ignore it and use the default `IObjectMapper`.

## Validation

- Enable `AddMaps<MyModule>(validate: true)` (or `AddProfile<MyProfile>(validate: true)`) and confirm the app starts without an AutoMapper configuration-validation error — this proves every declared map is complete.
- Call `ObjectMapper.Map<Source, Dest>(...)` for a defined pair and confirm the destination fields are populated as expected.
- For extensible types, confirm extra properties carry over after adding `.MapExtraProperties()` / `[MapExtraProperties]`.

## Common Pitfalls

- You must define the mapping first — `IObjectMapper.Map<TSource, TDestination>` needs a registered map for that exact pair or it fails.
- AutoMapper configuration `validate` defaults to `false`; enabling it is recommended so incomplete maps are caught at startup.
- Mapperly requires mapper classes and methods to be `partial` (it's a source generator); destination properties with no writable path are silently ignored, and it respects nullable reference types (a non-nullable destination fed a null source risks `NullReferenceException`).
- Mapperly does **not** compose nested types with separate mappers automatically — consolidate, implement multiple `IAbpMapperlyMapper<,>` on one class, or map nested objects in `AfterMap`.
- **Auto-mapping an input DTO onto a rich domain entity** — build/mutate it through its constructor and methods, or override `CrudAppService.MapToEntityAsync`; blanket input→entity auto-mapping is only safe for simple CRUD entities (entity → output DTO is always suitable for auto-mapping, once the map is defined).
- **Reusing one input DTO across several use cases** — define a specialized input DTO per application-service method so it carries only the properties that method needs.
- Extra properties are only mapped when explicitly requested and both sides implement `IHasExtraProperties`.
- AutoMapper 14.x has a known vulnerability (GHSA-rvv3-g6hj-g44x); ABP applies a `MaxDepth = 64` mitigation. Consider migrating to Mapperly or using the LuckyPenny patched package if relevant.
