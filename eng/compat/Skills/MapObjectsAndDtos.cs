// Compile-smoke for skill: abp-module-development/map-objects-and-dtos
// Exercises IObjectMapper, AutoMapper Profile + AbpAutoMapperOptions.AddMaps + MapExtraProperties,
// Mapperly MapperBase/TwoWayMapperBase, IObjectMapper<TSource,TDest>, and contextual mapper wiring.
using System;
using System.Collections.Generic;
using AutoMapper;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.AutoMapper;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Mapperly;
using Volo.Abp.Modularity;
using Volo.Abp.ObjectExtending;
using Volo.Abp.ObjectMapping;

namespace AbpSkillsCompat.Skills;

internal sealed class MapUser : ExtensibleObject, IHasExtraProperties
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
}

internal sealed class MapUserDto : ExtensibleObject, IHasExtraProperties
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
}

// AutoMapper profile + extra-property mapping.
internal sealed class MapUserProfile : Profile
{
    public MapUserProfile()
    {
        CreateMap<MapUser, MapUserDto>().MapExtraProperties();
    }
}

// Mapperly source-generated mapper.
[Riok.Mapperly.Abstractions.Mapper]
internal partial class MapUserToDtoMapper : MapperBase<MapUser, MapUserDto>
{
    public override partial MapUserDto Map(MapUser source);
    public override partial void Map(MapUser source, MapUserDto destination);
}

// Two-way Mapperly mapper (adds ReverseMap generation).
[Riok.Mapperly.Abstractions.Mapper]
internal partial class MapUserTwoWayMapper : TwoWayMapperBase<MapUser, MapUserDto>
{
    public override partial MapUserDto Map(MapUser source);
    public override partial void Map(MapUser source, MapUserDto destination);
    public override partial MapUser ReverseMap(MapUserDto source);
    public override partial void ReverseMap(MapUserDto source, MapUser destination);
}

// Custom typed mapper.
internal sealed class MapUserCustomMapper : IObjectMapper<MapUser, MapUserDto>, ITransientDependency
{
    public MapUserDto Map(MapUser source) => new MapUserDto { Id = source.Id, Name = source.Name };

    public MapUserDto Map(MapUser source, MapUserDto destination)
    {
        destination.Name = source.Name;
        return destination;
    }
}

internal sealed class MapObjectsModule : AbpModule
{
    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        Configure<AbpAutoMapperOptions>(options =>
        {
            options.AddMaps<MapObjectsModule>(validate: true);
        });

        // Contextual mapper pins this module to its own provider.
        context.Services.AddMapperlyObjectMapper<MapObjectsModule>();
    }
}

internal static class MapObjectsAndDtos
{
    internal static List<MapUserDto> UseMapper(IObjectMapper mapper, List<MapUser> users)
    {
        var single = mapper.Map<MapUser, MapUserDto>(users[0]);
        mapper.Map(users[0], single);
        return mapper.Map<List<MapUser>, List<MapUserDto>>(users);
    }
}
