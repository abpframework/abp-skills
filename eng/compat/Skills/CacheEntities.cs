using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Entities.Caching;

namespace AbpSkillsCompat.Skills;

internal sealed class CachedProduct : Entity<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class CachedProductDto
{
    public string Name { get; set; } = string.Empty;
}

internal static class CacheEntities
{
    internal static void Register(IServiceCollection services)
    {
        services.AddEntityCache<CachedProduct, Guid>();
        services.AddEntityCache<CachedProduct, CachedProductDto, Guid>(
            new DistributedCacheEntryOptions
            {
                SlidingExpiration = TimeSpan.FromMinutes(30)
            });
    }

    internal static async Task Read(IEntityCache<CachedProduct, Guid> cache)
    {
        CachedProduct? found = await cache.FindAsync(Guid.Empty);
        CachedProduct got = await cache.GetAsync(Guid.Empty);
        List<CachedProduct?> many = await cache.FindManyAsync(new[] { Guid.Empty });
        Dictionary<Guid, CachedProduct> dict = await cache.GetManyAsDictionaryAsync(new[] { Guid.Empty });
    }

    internal static void CustomMapper(EntityCacheWithObjectMapper<CachedProduct, CachedProductDto, Guid> mapper)
    {
        var wrapper = new EntityCacheItemWrapper<CachedProductDto>(new CachedProductDto());
    }
}
