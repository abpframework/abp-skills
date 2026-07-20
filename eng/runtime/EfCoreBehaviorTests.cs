// DB-backed runtime behavior tests: these boot the ABP application over an in-memory SQLite
// database and assert semantics the compile-smoke cannot reach — the soft-delete data filter
// and unit-of-work rollback.
using System;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Autofac;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Testing;
using Volo.Abp.Uow;
using Xunit;

namespace AbpRuntimeTests;

public class EfCoreBehaviorTests : AbpIntegratedTest<EfCoreTestModule>
{
    private readonly IRepository<Widget, Guid> _widgets;
    private readonly IUnitOfWorkManager _uowManager;
    private readonly IDataFilter _dataFilter;

    public EfCoreBehaviorTests()
    {
        _widgets = GetRequiredService<IRepository<Widget, Guid>>();
        _uowManager = GetRequiredService<IUnitOfWorkManager>();
        _dataFilter = GetRequiredService<IDataFilter>();
    }

    protected override void SetAbpApplicationCreationOptions(AbpApplicationCreationOptions options)
    {
        options.UseAutofac();
    }

    [Fact]
    public async Task Soft_delete_hides_the_row_but_keeps_it()
    {
        var id = Guid.Empty;
        await WithUnitOfWorkAsync(async () =>
        {
            var inserted = await _widgets.InsertAsync(new Widget { Name = "gadget" }, autoSave: true);
            id = inserted.Id; // ABP generates the GUID on insert
        });

        await WithUnitOfWorkAsync(async () => await _widgets.DeleteAsync(id, autoSave: true));

        // Filtered out of normal queries...
        await WithUnitOfWorkAsync(async () => Assert.Null(await _widgets.FindAsync(id)));

        // ...but the row is still there with IsDeleted = true when the filter is disabled.
        await WithUnitOfWorkAsync(async () =>
        {
            using (_dataFilter.Disable<ISoftDelete>())
            {
                var widget = await _widgets.FindAsync(id);
                Assert.NotNull(widget);
                Assert.True(((ISoftDelete)widget!).IsDeleted);
            }
        });
    }

    [Fact]
    public async Task Insert_without_completing_the_unit_of_work_persists_nothing()
    {
        var id = Guid.Empty;

        using (var uow = _uowManager.Begin(requiresNew: true))
        {
            // autoSave is false by default, so nothing is flushed to the DB...
            var inserted = await _widgets.InsertAsync(new Widget { Name = "temp" });
            id = inserted.Id; // the GUID is still assigned on insert
            // ...and without CompleteAsync the unit of work never saves it.
        }

        await WithUnitOfWorkAsync(async () => Assert.Null(await _widgets.FindAsync(id)));
    }

    [Fact]
    public async Task GetAsync_throws_but_FindAsync_returns_null_for_a_missing_id()
    {
        var missing = Guid.NewGuid();

        await WithUnitOfWorkAsync(async () =>
        {
            Assert.Null(await _widgets.FindAsync(missing));
            // GetAsync throws EntityNotFoundException (the generic EntityNotFoundException<Widget>
            // derives from it), unlike FindAsync which returns null.
            await Assert.ThrowsAnyAsync<EntityNotFoundException>(() => _widgets.GetAsync(missing));
        });
    }

    [Fact]
    public async Task Direct_delete_physically_removes_even_a_soft_delete_entity()
    {
        var id = Guid.Empty;
        await WithUnitOfWorkAsync(async () =>
        {
            var inserted = await _widgets.InsertAsync(new Widget { Name = "doomed" }, autoSave: true);
            id = inserted.Id;
        });

        // DeleteDirectAsync on EF Core is a set-based physical delete that bypasses soft-delete.
        await WithUnitOfWorkAsync(async () => await _widgets.DeleteDirectAsync(w => w.Id == id));

        // Even with the soft-delete filter disabled the row is gone — unlike DeleteAsync above,
        // which keeps it with IsDeleted = true. This is the semantic the use-abp-repositories
        // skill documents as a provider-dependent hard delete on EF Core / MongoDB.
        await WithUnitOfWorkAsync(async () =>
        {
            using (_dataFilter.Disable<ISoftDelete>())
            {
                Assert.Null(await _widgets.FindAsync(id));
            }
        });
    }

    [Fact]
    public async Task Data_seeder_runs_its_contributors_and_seeds_the_row()
    {
        var seeder = GetRequiredService<IDataSeeder>();

        // IDataSeeder resolves and runs every IDataSeedContributor (WidgetSeedContributor here).
        await seeder.SeedAsync(new DataSeedContext());

        await WithUnitOfWorkAsync(async () =>
        {
            var seeded = await _widgets.FindAsync(w => w.Name == WidgetSeedContributor.SeededName);
            Assert.NotNull(seeded);
        });
    }

    [Fact]
    public async Task Extra_property_round_trips_through_the_database()
    {
        var id = Guid.Empty;
        await WithUnitOfWorkAsync(async () =>
        {
            var widget = new Widget { Name = "extensible" };
            widget.SetProperty("Tag", "vip");
            var inserted = await _widgets.InsertAsync(widget, autoSave: true);
            id = inserted.Id;
        });

        // Reload in a fresh UOW: the extra property is persisted (JSON) and comes back.
        await WithUnitOfWorkAsync(async () =>
        {
            var widget = await _widgets.GetAsync(id);
            Assert.Equal("vip", widget.GetProperty<string>("Tag"));
        });
    }

    [Fact]
    public async Task Entity_created_event_publishes_on_unit_of_work_completion()
    {
        WidgetCreatedEventHandler.Count = 0;
        int duringUow;

        using (var uow = _uowManager.Begin(requiresNew: true))
        {
            await _widgets.InsertAsync(
                new Widget { Name = WidgetCreatedEventHandler.EventedName }, autoSave: true);

            duringUow = WidgetCreatedEventHandler.Count; // the local event is deferred to completion
            await uow.CompleteAsync();
        }

        Assert.Equal(0, duringUow);
        Assert.True(WidgetCreatedEventHandler.Count > 0);
    }

    private async Task WithUnitOfWorkAsync(Func<Task> action)
    {
        using var uow = _uowManager.Begin(requiresNew: true);
        await action();
        await uow.CompleteAsync();
    }
}
