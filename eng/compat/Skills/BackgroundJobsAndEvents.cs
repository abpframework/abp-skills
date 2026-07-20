// Compile-smoke for skill: abp-runtime/background-jobs-and-events
// Exercises the local/distributed event bus, entity change events, background jobs
// (typed + dynamic), and periodic background workers the skill teaches.
using System;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.BackgroundJobs;
using Volo.Abp.BackgroundWorkers;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Entities.Events;
using Volo.Abp.EventBus;
using Volo.Abp.EventBus.Distributed;
using Volo.Abp.EventBus.Local;
using Volo.Abp.Threading;

namespace AbpSkillsCompat.Skills;

internal sealed class BjSampleEvent
{
    public int ProductId { get; set; }
    public int NewCount { get; set; }
}

[EventName("MyApp.Stock.Changed")]
internal sealed class BjSampleEto
{
    public Guid ProductId { get; set; }
    public int NewCount { get; set; }
}

internal sealed class BjSampleEntity : Entity<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class BjSampleJobArgs
{
    public string To { get; set; } = string.Empty;
    public string Subject { get; set; } = string.Empty;
}

internal sealed class BjSampleLocalHandler
    : ILocalEventHandler<BjSampleEvent>
{
    public Task HandleEventAsync(BjSampleEvent eventData) => Task.CompletedTask;
}

internal sealed class BjSampleEntityHandler
    : ILocalEventHandler<EntityCreatedEventData<BjSampleEntity>>,
      ILocalEventHandler<EntityUpdatedEventData<BjSampleEntity>>,
      ILocalEventHandler<EntityDeletedEventData<BjSampleEntity>>
{
    public Task HandleEventAsync(EntityCreatedEventData<BjSampleEntity> e) => Handle(e.Entity);
    public Task HandleEventAsync(EntityUpdatedEventData<BjSampleEntity> e) => Handle(e.Entity);
    public Task HandleEventAsync(EntityDeletedEventData<BjSampleEntity> e) => Handle(e.Entity);
    private static Task Handle(BjSampleEntity entity) => Task.CompletedTask;
}

internal sealed class BjSampleDistributedHandler
    : IDistributedEventHandler<BjSampleEto>
{
    public Task HandleEventAsync(BjSampleEto eventData) => Task.CompletedTask;
}

internal sealed class BjSampleJob : AsyncBackgroundJob<BjSampleJobArgs>
{
    public override Task ExecuteAsync(BjSampleJobArgs args) => Task.CompletedTask;
}

internal sealed class BjSampleWorker : AsyncPeriodicBackgroundWorkerBase
{
    public BjSampleWorker(AbpAsyncTimer timer, IServiceScopeFactory scopeFactory)
        : base(timer, scopeFactory)
    {
        Timer.Period = 60_000;
    }

    protected override Task DoWorkAsync(PeriodicBackgroundWorkerContext workerContext)
    {
        IServiceProvider provider = workerContext.ServiceProvider;
        return Task.CompletedTask;
    }
}

internal static class BackgroundJobsAndEvents
{
    internal static async Task PublishLocal(ILocalEventBus localEventBus)
    {
        await localEventBus.PublishAsync(new BjSampleEvent { ProductId = 42, NewCount = 10 });
    }

    internal static async Task PublishDistributed(IDistributedEventBus distributedEventBus)
    {
        await distributedEventBus.PublishAsync(new BjSampleEto { ProductId = Guid.NewGuid(), NewCount = 10 });
    }

    internal static async Task EnqueueJob(IBackgroundJobManager backgroundJobManager)
    {
        string jobId = await backgroundJobManager.EnqueueAsync(
            new BjSampleJobArgs { To = "a@b.com", Subject = "Hi" },
            BackgroundJobPriority.Normal,
            delay: TimeSpan.FromSeconds(30));

        string jobName = BackgroundJobNameAttribute.GetName<BjSampleJobArgs>();
    }

    internal static async Task EnqueueDynamic(IDynamicBackgroundJobManager dynamicJobManager)
    {
        string jobId = await dynamicJobManager.EnqueueAsync(
            "emails", new { To = "a@b.com", Subject = "Hi" });

        dynamicJobManager.RegisterHandler("ProcessOrder", (context, cancellationToken) => Task.CompletedTask);
    }

    internal static async Task RegisterWorker(ApplicationInitializationContext context)
    {
        await context.AddBackgroundWorkerAsync<BjSampleWorker>();
    }
}
