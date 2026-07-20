// HTTP behavior tests over a real booted ABP MVC app (the RuntimeWebApp SUT project) — the
// T2 coverage the test-mvc-razor-ui / configure-cors / configure-production-hosting skills need.
// A compile-smoke can only prove the APIs exist; these prove a request actually round-trips.
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading.Tasks;
using RuntimeWebApp;
using Volo.Abp.AspNetCore.TestBase;
using Xunit;

namespace AbpRuntimeTests;

public class WebBehaviorTests : AbpWebApplicationFactoryIntegratedTest<Program>
{
    [Fact]
    public async Task Anonymous_request_to_an_open_endpoint_returns_200()
    {
        var response = await Client.GetAsync("/api/ping");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("pong", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Application_service_is_auto_exposed_as_a_conventional_controller()
    {
        // GreetingAppService has no [Route]/controller attribute — ABP's conventional
        // controllers create the /api/app/greeting endpoint from the app service.
        var response = await Client.GetAsync("/api/app/greeting");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("hi", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Anonymous_request_to_a_protected_endpoint_redirects_with_302()
    {
        // Client uses AllowAutoRedirect = false, so the cookie challenge surfaces as a 302
        // (to the LoginPath) instead of being followed — the semantic the skill documents.
        var response = await Client.GetAsync("/api/secure");

        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
    }

    [Fact]
    public async Task Cors_policy_exposes_the_abp_error_headers()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/ping");
        request.Headers.Add("Origin", "https://example.com");

        var response = await Client.SendAsync(request);

        Assert.Equal("https://example.com", response.Headers.GetValues("Access-Control-Allow-Origin").Single());
        // WithAbpExposedHeaders() adds _AbpErrorFormat to Access-Control-Expose-Headers.
        Assert.Contains("_AbpErrorFormat", response.Headers.GetValues("Access-Control-Expose-Headers").Single());
    }

    [Fact]
    public async Task Forwarded_headers_restore_the_client_scheme_and_host()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/api/scheme");
        request.Headers.Add("X-Forwarded-Proto", "https");
        request.Headers.Add("X-Forwarded-Host", "forwarded.example.com");

        var response = await Client.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();

        // XForwardedProto restores the scheme; XForwardedHost restores the external host.
        Assert.Contains("https", body);
        Assert.Contains("forwarded.example.com", body);
    }

    [Fact]
    public async Task Health_liveness_endpoint_returns_200()
    {
        var response = await Client.GetAsync("/health/live");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task Health_readiness_endpoint_returns_503_when_a_ready_check_is_unhealthy()
    {
        var response = await Client.GetAsync("/health/ready");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
    }
}
