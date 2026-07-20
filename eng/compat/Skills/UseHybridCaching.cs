// Compile-smoke for skill: abp-runtime/use-hybrid-caching
// Exercises the ABP hybrid cache (L1 in-memory + L2 distributed) APIs the skill teaches.
using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Caching.Hybrid;
using Volo.Abp.Caching.Hybrid;

namespace AbpSkillsCompat.Skills;

internal class HybridCountryCacheItem
{
    public string? Name { get; set; }
}

internal static class UseHybridCaching
{
    internal static async Task Typed(IHybridCache<HybridCountryCacheItem> cache)
    {
        HybridCountryCacheItem? item = await cache.GetOrCreateAsync(
            "TR",
            factory: async () => await Task.FromResult(new HybridCountryCacheItem { Name = "Türkiye" }),
            optionsFactory: () => new HybridCacheEntryOptions { Expiration = TimeSpan.FromMinutes(5) },
            hideErrors: false,
            considerUow: false,
            token: CancellationToken.None);

        await cache.SetAsync("TR", new HybridCountryCacheItem { Name = "Türkiye" });
        await cache.RemoveAsync("TR");
    }

    internal static async Task Keyed(IHybridCache<HybridCountryCacheItem, Guid> cache, IEnumerable<Guid> keys)
    {
        await cache.RemoveManyAsync(keys);
    }

    internal static void Options(AbpHybridCacheOptions options)
    {
        options.HideErrors = true;
        options.GlobalHybridCacheEntryOptions = new HybridCacheEntryOptions();
    }
}
