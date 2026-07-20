// Compile-smoke for skill: abp-data-access/apply-data-filters
// Exercises IDataFilter scopes, AbpDataFilterOptions defaults, and EF Core / MongoDB custom filters.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Volo.Abp;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Domain.Repositories.MongoDB;
using Volo.Abp.EntityFrameworkCore;
using Volo.Abp.MultiTenancy;

namespace AbpSkillsCompat.Skills;

internal interface IIsActive
{
    bool IsActive { get; }
}

internal class FilteredBook : AggregateRoot<Guid>, ISoftDelete, IMultiTenant, IIsActive
{
    public string Name { get; set; } = default!;
    public bool IsDeleted { get; set; }
    public Guid? TenantId { get; set; }
    public bool IsActive { get; set; }
}

internal static class ApplyDataFilters
{
    internal static async Task<List<FilteredBook>> ToggleScopeAsync(
        IDataFilter dataFilter,
        IDataFilter<ISoftDelete> softDeleteFilter,
        IRepository<FilteredBook, Guid> repository)
    {
        using (dataFilter.Disable<ISoftDelete>())
        {
            var _ = dataFilter.IsEnabled<IMultiTenant>();
            using (dataFilter.Enable<IMultiTenant>())
            {
                using (softDeleteFilter.Disable())
                {
                    return await repository.GetListAsync();
                }
            }
        }
    }

    internal static async Task HardDeleteAsync(IRepository<FilteredBook, Guid> repository)
    {
        await repository.HardDeleteAsync(book => book.Name.StartsWith("old"), autoSave: true);
    }

    internal static void ChangeDefaultState()
    {
        var options = new AbpDataFilterOptions();
        options.DefaultStates[typeof(ISoftDelete)] = new DataFilterState(isEnabled: false);
    }
}

// EF Core custom filter via global query filters.
internal class FilterDemoDbContext : AbpDbContext<FilterDemoDbContext>
{
    public FilterDemoDbContext(DbContextOptions<FilterDemoDbContext> options)
        : base(options)
    {
    }

    protected bool IsActiveFilterEnabled => DataFilter?.IsEnabled<IIsActive>() ?? false;

    protected override bool ShouldFilterEntity<TEntity>(IMutableEntityType entityType)
    {
        if (typeof(IIsActive).IsAssignableFrom(typeof(TEntity)))
        {
            return true;
        }

        return base.ShouldFilterEntity<TEntity>(entityType);
    }

    protected override Expression<Func<TEntity, bool>>? CreateFilterExpression<TEntity>(
        ModelBuilder modelBuilder,
        EntityTypeBuilder<TEntity> entityTypeBuilder)
    {
        var expression = base.CreateFilterExpression<TEntity>(modelBuilder, entityTypeBuilder);
        if (typeof(IIsActive).IsAssignableFrom(typeof(TEntity)))
        {
            Expression<Func<TEntity, bool>> isActiveFilter =
                e => !IsActiveFilterEnabled || EF.Property<bool>(e, "IsActive");
            expression = expression == null
                ? isActiveFilter
                : QueryFilterExpressionHelper.CombineExpressions(expression, isActiveFilter);
        }

        return expression;
    }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);
        builder.Entity<FilteredBook>().HasAbpQueryFilter(e => e.Name.StartsWith("abp"));
    }
}

// MongoDB custom filter via MongoDbRepositoryFilterer.
[ExposeServices(typeof(IMongoDbRepositoryFilterer<FilteredBook, Guid>))]
internal class FilteredBookMongoDbRepositoryFilterer
    : MongoDbRepositoryFilterer<FilteredBook, Guid>, ITransientDependency
{
    public FilteredBookMongoDbRepositoryFilterer(IDataFilter dataFilter, ICurrentTenant currentTenant)
        : base(dataFilter, currentTenant)
    {
    }

    public override TQueryable FilterQueryable<TQueryable>(TQueryable query)
    {
        if (DataFilter.IsEnabled<IIsActive>())
        {
            return (TQueryable)query.Where(x => x.IsActive);
        }

        return base.FilterQueryable(query);
    }
}
