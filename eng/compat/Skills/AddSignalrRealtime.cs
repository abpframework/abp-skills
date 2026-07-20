// Compile-smoke for skill: abp-realtime/add-signalr-realtime
// Exercises AbpHub / AbpHub<TClient>, [HubRoute], [Authorize] + CurrentUser,
// and manual mapping via AbpSignalROptions + HubConfig.
// Razor/JS client wiring in the skill is not compile-checked here.
using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.SignalR;
using Microsoft.Extensions.Logging;
using Volo.Abp;
using Volo.Abp.AspNetCore.SignalR;
using Volo.Abp.DependencyInjection;

namespace AbpSkillsCompat.Skills;

[HubRoute("/my-messaging-hub")]
[Authorize]
internal sealed class MessagingHub : AbpHub
{
    public async Task SendPrivate(string toUserId, string message)
    {
        var senderId = CurrentUser.Id;
        var senderName = CurrentUser.UserName;
        var text = L["MessageSent"];
        Logger.LogInformation("Message from {User}", senderName);
        await Clients.User(toUserId).SendAsync("ReceiveMessage", senderName, message);
    }
}

internal interface IChatClient
{
    Task ReceiveMessage(string user, string message);
}

[Authorize]
internal sealed class ChatHub : AbpHub<IChatClient>
{
    public Task SendMessage(string message)
    {
        Check.NotNullOrWhiteSpace(message, nameof(message));   // validate untrusted input
        return Clients.All.ReceiveMessage(CurrentUser.UserName!, message);
    }
}

// Opt out of auto DI registration ([DisableConventionalRegistration]) and auto endpoint
// mapping ([DisableAutoHubMap]); the app then registers and maps this hub manually.
[DisableConventionalRegistration]
[DisableAutoHubMap]
internal sealed class ManualHub : AbpHub
{
    public Task Ping() => Clients.All.SendAsync("Pong");
}

internal static class AddSignalrRealtime
{
    internal static void MapManually(AbpSignalROptions options)
    {
        options.Hubs.Add(
            new HubConfig(
                typeof(MessagingHub),
                "/my-messaging/route",
                hubOptions =>
                {
                    hubOptions.LongPolling.PollTimeout = TimeSpan.FromSeconds(30);
                }));
    }

    // Tweak a hub from a depended module: AddOrUpdate with a config lambda that sets
    // RoutePattern and appends to ConfigureActions.
    internal static void MapWithAddOrUpdate(AbpSignalROptions options)
    {
        options.Hubs.AddOrUpdate<ManualHub>(config =>
        {
            config.RoutePattern = "/manual-hub/route";
            config.ConfigureActions.Add(dispatcherOptions =>
            {
                dispatcherOptions.LongPolling.PollTimeout = TimeSpan.FromSeconds(15);
            });
        });
    }

    // The SignalR module and the ICurrentUser-backed IUserIdProvider that powers Clients.User.
    internal static Type[] ModuleTypes()
    {
        return new[]
        {
            typeof(AbpAspNetCoreSignalRModule),
            typeof(AbpSignalRUserIdProvider)
        };
    }
}
