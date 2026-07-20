// EF Core (SQLite in-memory) test application: gives the DB-backed runtime tests a real
// database so soft-delete filtering and unit-of-work rollback actually execute.
using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp;
using Volo.Abp.Autofac;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Entities.Auditing;
using Volo.Abp.Domain.Entities.Events;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.EventBus;
using Volo.Abp.EntityFrameworkCore;
using Volo.Abp.EntityFrameworkCore.Modeling;
using Volo.Abp.EntityFrameworkCore.Sqlite;
using Volo.Abp.Modularity;
using Volo.Abp.MultiTenancy;

namespace AbpRuntimeTests;

public class Widget : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; } = string.Empty;
}

// A data-seed contributor so the IDataSeeder pipeline can be exercised end to end.
public class WidgetSeedContributor : IDataSeedContributor, ITransientDependency
{
    public const string SeededName = "seeded-widget";

    private readonly IRepository<Widget, Guid> _widgets;

    public WidgetSeedContributor(IRepository<Widget, Guid> widgets)
    {
        _widgets = widgets;
    }

    public async Task SeedAsync(DataSeedContext context)
    {
        if (await _widgets.FindAsync(w => w.Name == SeededName) == null)
        {
            await _widgets.InsertAsync(new Widget { Name = SeededName }, autoSave: true);
        }
    }
}

// Local handler for the entity-created event. Scoped to a unique name so concurrent
// tests that insert other widgets don't inflate the counter.
public class WidgetCreatedEventHandler : ILocalEventHandler<EntityCreatedEventData<Widget>>, ITransientDependency
{
    public const string EventedName = "evented-widget";

    public static int Count;

    public Task HandleEventAsync(EntityCreatedEventData<Widget> eventData)
    {
        if (eventData.Entity.Name == EventedName)
        {
            Interlocked.Increment(ref Count);
        }

        return Task.CompletedTask;
    }
}

public class TenantWidget : FullAuditedAggregateRoot<Guid>, IMultiTenant
{
    public Guid? TenantId { get; set; }
    public string Name { get; set; } = string.Empty;
}

[ConnectionStringName("Default")]
public class RuntimeDbContext : AbpDbContext<RuntimeDbContext>
{
    public DbSet<Widget> Widgets { get; set; } = null!;
    public DbSet<TenantWidget> TenantWidgets { get; set; } = null!;

    public RuntimeDbContext(DbContextOptions<RuntimeDbContext> options)
        : base(options)
    {
    }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);
        builder.Entity<Widget>(b =>
        {
            b.ToTable("Widgets");
            b.ConfigureByConvention();
        });
        builder.Entity<TenantWidget>(b =>
        {
            b.ToTable("TenantWidgets");
            b.ConfigureByConvention();
        });
    }
}

[DependsOn(
    typeof(AbpEntityFrameworkCoreSqliteModule),
    typeof(AbpMultiTenancyModule),
    typeof(AbpAutofacModule),
    typeof(AbpTestBaseModule)
)]
public class EfCoreTestModule : AbpModule
{
    private SqliteConnection? _sqliteConnection;

    public override void ConfigureServices(ServiceConfigurationContext context)
    {
        _sqliteConnection = CreateDatabaseAndGetConnection();

        Configure<AbpDbContextOptions>(options =>
        {
            options.Configure(ctx => ctx.DbContextOptions.UseSqlite(_sqliteConnection));
        });

        context.Services.AddAbpDbContext<RuntimeDbContext>(options =>
        {
            options.AddDefaultRepositories(includeAllEntities: true);
        });
    }

    public override void OnApplicationShutdown(ApplicationShutdownContext context)
    {
        _sqliteConnection?.Dispose();
    }

    private static SqliteConnection CreateDatabaseAndGetConnection()
    {
        var connection = new SqliteConnection("Data Source=:memory:");
        connection.Open();

        var options = new DbContextOptionsBuilder<RuntimeDbContext>()
            .UseSqlite(connection)
            .Options;

        using (var context = new RuntimeDbContext(options))
        {
            context.GetService<IRelationalDatabaseCreator>().CreateTables();
        }

        return connection;
    }
}
