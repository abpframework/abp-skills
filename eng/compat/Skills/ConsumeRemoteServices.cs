using System;
using System.Reflection;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Http.Client;
using Volo.Abp.Http.Client.DynamicProxying;
using Volo.Abp.Http.Client.IdentityModel;
using Volo.Abp.Http.Client.IdentityModel.Web;

namespace AbpSkillsCompat.Skills;

internal static class ConsumeRemoteServices
{
    internal static void RegisterProxies(IServiceCollection services, Assembly assembly)
    {
        services.AddHttpClientProxies(assembly, "BookStore", asDefaultServices: true);
        services.AddStaticHttpClientProxies(assembly, "BookStore");
    }

    internal static void ConfigureEndpoints(AbpRemoteServiceOptions options)
    {
        RemoteServiceConfiguration config = new RemoteServiceConfiguration("https://localhost:44300", "1.0");
        options.RemoteServices["BookStore"] = config;
        string baseUrl = config.BaseUrl;
        _ = baseUrl;
    }

    internal static async Task ResolveAsync(
        IRemoteServiceConfigurationProvider provider,
        IHttpClientProxy<IProfileAppServiceMarker> proxy)
    {
        RemoteServiceConfiguration config = await provider.GetConfigurationOrDefaultAsync("BookStore");
        IProfileAppServiceMarker service = proxy.Service;
        _ = config;
        _ = service;
    }

    internal static void ConfigureRetry(AbpHttpClientBuilderOptions options)
    {
        _ = options.ProxyClientBuildActions;
    }

    // Authentication modules the skill documents (auth is NOT automatic by default).
    internal static void AuthModules()
    {
        Type clientCredentials = typeof(AbpHttpClientIdentityModelModule);      // server-to-server
        Type webTokenForwarding = typeof(AbpHttpClientIdentityModelWebModule);  // forward current user token
        _ = clientCredentials;
        _ = webTokenForwarding;
    }

    internal static void ForwardCurrentToken(RemoteServiceConfiguration config)
    {
        config.SetUseCurrentAccessToken(true);
    }
}

internal interface IProfileAppServiceMarker
{
}
