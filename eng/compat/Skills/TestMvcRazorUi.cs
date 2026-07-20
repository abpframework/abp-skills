// Compile-smoke for skill: abp-testing/test-mvc-razor-ui
// Exercises AbpWebApplicationFactoryIntegratedTest<TProgram> (Program = SUT entry point),
// the Client (AllowAutoRedirect = false), GetRequiredService/GetUrl, and the per-solution
// GetResponseAs* helpers copied into the WebTestBase (Shouldly-based, not shipped in the package).
using System;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.AspNetCore.TestBase;

namespace AbpSkillsCompat.Skills;

// Stand-in for the SUT's Program entry-point class.
internal sealed class SampleWebProgram
{
}

internal abstract class SampleWebTestBase : AbpWebApplicationFactoryIntegratedTest<SampleWebProgram>
{
    protected virtual async Task<string> GetResponseAsStringAsync(
        string url, HttpStatusCode expectedStatusCode = HttpStatusCode.OK)
    {
        var response = await Client.GetAsync(url);
        if (response.StatusCode != expectedStatusCode)
        {
            throw new Exception($"Unexpected status: {response.StatusCode}");
        }

        return await response.Content.ReadAsStringAsync();
    }

    protected virtual async Task<T?> GetResponseAsObjectAsync<T>(
        string url, HttpStatusCode expectedStatusCode = HttpStatusCode.OK)
    {
        var str = await GetResponseAsStringAsync(url, expectedStatusCode);
        return JsonSerializer.Deserialize<T>(str, new JsonSerializerOptions(JsonSerializerDefaults.Web));
    }

    public async Task Exercise()
    {
        var provider = GetRequiredService<IServiceProvider>();
        var loginUrl = GetUrl<SampleWebTestBase>("Index");
        var html = await GetResponseAsStringAsync("/");
        var redirected = (await Client.GetAsync("/Identity/Users")).StatusCode == HttpStatusCode.Redirect;
    }
}
