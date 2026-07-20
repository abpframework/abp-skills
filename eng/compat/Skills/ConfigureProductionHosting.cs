// Compile-smoke for skill: abp-runtime/configure-production-hosting
// Exercises the ABP options the skill names for clustered/production hosting: shared
// cache/lock KeyPrefix, single-instance background job/worker toggles, the shared string
// encryption pass-phrase, and the ABP-specific health-endpoint registration through
// AbpEndpointRouterOptions. The purely ASP.NET Core parts it also documents
// (ForwardedHeadersOptions, Data Protection, SignalR scale-out) are not ABP surface and
// are not smoked here.
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.AspNetCore.Routing;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.BackgroundJobs;
using Volo.Abp.BackgroundWorkers;
using Volo.Abp.Caching;
using Volo.Abp.DistributedLocking;
using Volo.Abp.Security.Encryption;

namespace AbpSkillsCompat.Skills;

internal static class ConfigureProductionHosting
{
    internal static void HealthEndpoints(IServiceCollection services, AbpEndpointRouterOptions endpointOptions)
    {
        services.AddHealthChecks();

        // The one ABP-specific bit the skill teaches: register health endpoints through
        // AbpEndpointRouterOptions so they compose with ABP's endpoint routing.
        endpointOptions.EndpointConfigureActions.Add(context =>
        {
            context.Endpoints.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false });
            context.Endpoints.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = registration => registration.Tags.Contains("ready") });
        });
    }

    internal static void SharedRedisPrefixes(AbpDistributedCacheOptions cache, AbpDistributedLockOptions distLock)
    {
        cache.KeyPrefix = "MyApp";
        distLock.KeyPrefix = "MyApp";
    }

    internal static void SingleInstanceJobsAndWorkers(AbpBackgroundJobOptions jobs, AbpBackgroundWorkerOptions workers)
    {
        jobs.IsJobExecutionEnabled = false; // run jobs on one instance only
        workers.IsEnabled = false;          // run workers on one instance only
    }

    internal static void SharedEncryption(AbpStringEncryptionOptions encryption, string passPhrase)
    {
        encryption.DefaultPassPhrase = passPhrase;
    }
}
