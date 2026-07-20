// Compile-smoke for skill: abp-microservices/design-module-and-service-communication
// Exercises [IntegrationService] on an IApplicationService, ExposeIntegrationServices,
// [EventName] ETO + IDistributedEventBus.PublishAsync (useOutbox), IDistributedEventHandler,
// and AbpDistributedEventBusOptions.
// Outbox/inbox EF Core + MongoDB wiring in the skill is not compile-checked (provider packages).
using System;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Application.Services;
using Volo.Abp.AspNetCore.Mvc;
using Volo.Abp.DependencyInjection;
using Volo.Abp.EventBus;
using Volo.Abp.EventBus.Distributed;

namespace AbpSkillsCompat.Skills;

internal sealed class ProductDto
{
    public Guid Id { get; set; }
}

[IntegrationService]
internal interface IProductIntegrationService : IApplicationService
{
    Task<ProductDto> GetAsync(Guid id);
}

[EventName("MyApp.Product.StockChanged")]
internal sealed class StockCountChangedEto
{
    public Guid ProductId { get; set; }
    public int NewCount { get; set; }
}

internal sealed class StockChangedHandler
    : IDistributedEventHandler<StockCountChangedEto>, ITransientDependency
{
    public Task HandleEventAsync(StockCountChangedEto eventData) => Task.CompletedTask;
}

internal static class DesignModuleAndServiceCommunication
{
    internal static void ExposeIntegration(AbpAspNetCoreMvcOptions options)
    {
        options.ExposeIntegrationServices = true;
    }

    internal static async Task PublishAsync(IDistributedEventBus eventBus, Guid id, int newCount)
    {
        await eventBus.PublishAsync(
            new StockCountChangedEto { ProductId = id, NewCount = newCount },
            useOutbox: false);
    }

    internal static void ConfigureBoxes(AbpDistributedEventBusOptions options)
    {
        var outboxes = options.Outboxes;
        var inboxes = options.Inboxes;
    }
}
