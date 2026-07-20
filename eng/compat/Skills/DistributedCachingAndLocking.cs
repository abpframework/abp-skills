using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Caching.Distributed;
using Volo.Abp;
using Volo.Abp.Caching;
using Volo.Abp.Data;
using Volo.Abp.DistributedLocking;
using Volo.Abp.Features;
using Volo.Abp.Settings;

namespace AbpSkillsCompat.Skills;

[CacheName("Product")]
internal sealed class ProductCacheItem
{
    public string Name { get; set; } = string.Empty;
    public decimal Price { get; set; }
}

internal static class DistributedCachingAndLocking
{
    internal static async Task Cache(IDistributedCache<ProductCacheItem> cache, CancellationToken cancellationToken)
    {
        ProductCacheItem? item = await cache.GetOrAddAsync(
            "k",
            () => Task.FromResult(new ProductCacheItem()),
            () => new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(30)
            },
            hideErrors: true,
            considerUow: false,
            token: cancellationToken);

        ProductCacheItem? got = await cache.GetAsync(
            "k",
            hideErrors: true,
            considerUow: false,
            token: cancellationToken);

        await cache.SetAsync(
            "k",
            new ProductCacheItem(),
            hideErrors: true,
            considerUow: false,
            token: cancellationToken);

        await cache.RefreshAsync("k", hideErrors: true, token: cancellationToken);

        await cache.RemoveAsync(
            "k",
            hideErrors: true,
            considerUow: false,
            token: cancellationToken);

        _ = item;
        _ = got;
    }

    internal static async Task TypedKeyCache(IDistributedCache<ProductCacheItem, Guid> cache)
    {
        ProductCacheItem? item = await cache.GetAsync(Guid.NewGuid());
        _ = item;
    }

    internal static void CacheOptions(AbpDistributedCacheOptions options)
    {
        options.KeyPrefix = "app:";
        options.HideErrors = true;
        DistributedCacheEntryOptions global = options.GlobalCacheEntryOptions;
        global.SlidingExpiration = TimeSpan.FromMinutes(5);
    }

    internal static async Task Lock(IAbpDistributedLock distributedLock, CancellationToken cancellationToken)
    {
        await using (IAbpDistributedLockHandle? handle =
            await distributedLock.TryAcquireAsync(
                "daily-report",
                timeout: TimeSpan.FromSeconds(10),
                cancellationToken: cancellationToken))
        {
            if (handle is null)
            {
                return;
            }
        }
    }

    internal static void DataFilter(IDataFilter dataFilter)
    {
        using (dataFilter.Disable<ISoftDelete>())
        {
        }
    }

    internal static async Task SettingsAndFeatures(
        ISettingProvider settingProvider,
        IFeatureChecker featureChecker)
    {
        string? s = await settingProvider.GetOrNullAsync("MySetting");
        bool enabled = await featureChecker.IsEnabledAsync("MyFeature");
    }
}
