// Compile-smoke for skill: abp-module-development/extend-objects-with-extra-properties
// Exercises IHasExtraProperties/ExtraPropertyDictionary, ExtensibleObject, AggregateRoot,
// ObjectExtensionManager.AddOrUpdateProperty, and SetProperty/GetProperty helpers, plus the
// EF Core / MongoDB persistence and AutoMapper / Mapperly extra-property mapping surfaces.
using System;
using System.ComponentModel.DataAnnotations;
using AutoMapper;
using Microsoft.EntityFrameworkCore;
using MongoDB.Bson.Serialization;
using Volo.Abp.Application.Dtos;
using Volo.Abp.AutoMapper;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.EntityFrameworkCore.Modeling;
using Volo.Abp.Mapperly;
using Volo.Abp.MongoDB;
using Volo.Abp.ObjectExtending;

namespace AbpSkillsCompat.Skills;

internal class ExtProduct : AggregateRoot<Guid>
{
    public string Name { get; private set; }

    protected ExtProduct()
    {
        Name = string.Empty;
    }

    public ExtProduct(Guid id, string name) : base(id)
    {
        Name = name;
    }
}

internal sealed class ExtProductDto : ExtensibleObject, IEntityDto<Guid>
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;

    public string GetObjectKey() => Id.ToString();
}

internal static class ExtendObjectsWithExtraProperties
{
    public const string ManufacturerCode = "ManufacturerCode";

    internal static void Configure()
    {
        ObjectExtensionManager.Instance
            .AddOrUpdateProperty<ExtProduct, string>(
                ManufacturerCode,
                property => property.Attributes.Add(new StringLengthAttribute(32)))
            .AddOrUpdateProperty<ExtProductDto, string>(
                ManufacturerCode,
                property => property.Attributes.Add(new StringLengthAttribute(32)));
    }

    internal static string? ReadWrite(ExtProduct product)
    {
        product.SetProperty(ManufacturerCode, "ACME-42");
        var code = product.GetProperty<string>(ManufacturerCode);
        var has = product.HasProperty(ManufacturerCode);
        product.RemoveProperty(ManufacturerCode);

        // ExtraProperties is an ExtraPropertyDictionary (Dictionary<string, object?>).
        ExtraPropertyDictionary dict = product.ExtraProperties;
        return code;
    }

    // EF Core: ConfigureByConvention() installs the ExtraProperties JSON converter, and
    // MapEfCoreProperty promotes one entry to a dedicated column with HasColumnName.
    internal static void ConfigureEfCore(ModelBuilder builder)
    {
        builder.Entity<ExtProduct>().ConfigureByConvention();

        ObjectExtensionManager.Instance.MapEfCoreProperty<ExtProduct, string>(
            ManufacturerCode,
            (entityBuilder, propertyBuilder) =>
            {
                propertyBuilder.HasMaxLength(32);
                propertyBuilder.HasColumnName(ManufacturerCode);
            });
    }

    // MongoDB: ConfigureAbpConventions() maps the declared ExtraProperties as extra elements.
    internal static void ConfigureMongo(BsonClassMap classMap)
    {
        classMap.ConfigureAbpConventions();
    }
}

// AutoMapper: opt in to extra-property copying on the map. Both ends implement
// IHasExtraProperties (ExtProduct via AggregateRoot, ExtProductDto via ExtensibleObject).
internal sealed class ExtProductAutoMapperProfile : Profile
{
    public ExtProductAutoMapperProfile()
    {
        CreateMap<ExtProduct, ExtProductDto>()
            .MapExtraProperties();
    }
}

// Mapperly: the [MapExtraProperties] attribute on the mapper class drives extra-property mapping.
[Riok.Mapperly.Abstractions.Mapper]
[MapExtraProperties]
internal partial class ExtProductMapperlyMapper : MapperBase<ExtProduct, ExtProductDto>
{
    [Riok.Mapperly.Abstractions.MapperIgnoreSource(nameof(ExtProduct.ConcurrencyStamp))]
    public override partial ExtProductDto Map(ExtProduct source);

    [Riok.Mapperly.Abstractions.MapperIgnoreSource(nameof(ExtProduct.ConcurrencyStamp))]
    public override partial void Map(ExtProduct source, ExtProductDto destination);
}
