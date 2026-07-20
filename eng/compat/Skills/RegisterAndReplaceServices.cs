// Compile-smoke for skill: abp-module-development/register-and-replace-services
// Exercises exposure/lifetime attributes, keyed services, and cached providers.
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.DependencyInjection;

namespace AbpSkillsCompat.Skills;

internal interface ISampleCalculator
{
    decimal Calculate(decimal value);
}

[Dependency(ReplaceServices = true)]
[ExposeServices(typeof(ISampleCalculator))]
internal sealed class SampleCalculator : ISampleCalculator, ITransientDependency
{
    public decimal Calculate(decimal value) => value;
}

[ExposeKeyedService<ISampleCalculator>("standard")]
internal sealed class KeyedCalculator : ISampleCalculator, ITransientDependency
{
    public decimal Calculate(decimal value) => value;
}

internal static class RegisterAndReplaceServices
{
    internal static void CachedProvider(ITransientCachedServiceProvider services)
    {
        var svc = services.GetService<ISampleCalculator>();
    }

    internal static void LazyProvider(IAbpLazyServiceProvider lazy)
    {
        var svc = lazy.LazyGetService<ISampleCalculator>();
    }

    internal static void ObjectAccessor(IServiceCollection services)
    {
        services.AddObjectAccessor<ISampleCalculator>();
    }
}
