// Compile-smoke for skill: abp-microservices/integrate-dapr-services
// Exercises AbpDaprOptions, IAbpDaprClientFactory, AbpDaprEventBusOptions (PubSubName),
// AbpDistributedLockDaprOptions (StoreName), ValidateDaprAppApiToken /
// IDaprAppApiTokenValidator, and the standard IAbpDistributedLock usage.
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Volo.Abp.AspNetCore.Mvc.Dapr;
using Volo.Abp.Dapr;
using Volo.Abp.DependencyInjection;
using Volo.Abp.DistributedLocking;
using Volo.Abp.DistributedLocking.Dapr;
using Volo.Abp.EventBus.Dapr;

namespace AbpSkillsCompat.Skills;

internal static class IntegrateDaprServices
{
    internal static void ConfigureCore(AbpDaprOptions options)
    {
        options.HttpEndpoint = "http://localhost:3500/";
    }

    internal static void ConfigurePubSub(AbpDaprEventBusOptions options)
    {
        options.PubSubName = "pubsub";
    }

    internal static void ConfigureLock(AbpDistributedLockDaprOptions options)
    {
        options.StoreName = "mystore";
    }

    internal sealed class Sample : ITransientDependency
    {
        private readonly IAbpDaprClientFactory _daprClientFactory;
        private readonly IAbpDistributedLock _distributedLock;
        private readonly IDaprAppApiTokenValidator _tokenValidator;

        public Sample(
            IAbpDaprClientFactory daprClientFactory,
            IAbpDistributedLock distributedLock,
            IDaprAppApiTokenValidator tokenValidator)
        {
            _daprClientFactory = daprClientFactory;
            _distributedLock = distributedLock;
            _tokenValidator = tokenValidator;
        }

        public async Task LockAsync()
        {
            await using (var handle = await _distributedLock.TryAcquireAsync("MyLockName"))
            {
                if (handle != null)
                {
                    // exclusive access
                }
            }
        }

        public void Validate(HttpContext httpContext)
        {
            httpContext.ValidateDaprAppApiToken();
        }
    }
}
