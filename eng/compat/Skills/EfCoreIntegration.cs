// Compile-smoke for skill: abp-data-access/ef-core-integration
// Exercises AbpDbContext, ConfigureByConvention, AddAbpDbContext, EfCoreRepository, IDbContextProvider.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Domain.Repositories.EntityFrameworkCore;
using Volo.Abp.EntityFrameworkCore;
using Volo.Abp.EntityFrameworkCore.Modeling;

namespace AbpSkillsCompat.Skills;

internal class EfBook : AggregateRoot<Guid>
{
    public string Name { get; set; } = default!;
    public Guid AuthorId { get; set; }
}

[ConnectionStringName("Default")]
internal class MyProjectDbContext : AbpDbContext<MyProjectDbContext>
{
    public DbSet<EfBook> Books { get; set; } = default!;

    public MyProjectDbContext(DbContextOptions<MyProjectDbContext> options)
        : base(options)
    {
    }

    protected override void OnModelCreating(ModelBuilder builder)
    {
        base.OnModelCreating(builder);

        builder.Entity<EfBook>(b =>
        {
            b.ToTable("AppBooks");
            b.ConfigureByConvention();
            b.Property(x => x.Name).IsRequired().HasMaxLength(128);
        });
    }
}

internal interface IEfBookRepository : IRepository<EfBook, Guid>
{
    Task<List<EfBook>> GetListByAuthorAsync(Guid authorId);
}

internal class EfCoreBookRepository
    : EfCoreRepository<MyProjectDbContext, EfBook, Guid>, IEfBookRepository
{
    public EfCoreBookRepository(IDbContextProvider<MyProjectDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public async Task<List<EfBook>> GetListByAuthorAsync(Guid authorId)
    {
        var dbSet = await GetDbSetAsync();
        var queryable = await GetQueryableAsync();
        var dbContext = await GetDbContextAsync();
        _ = dbContext.Books;
        return await queryable.Where(b => b.AuthorId == authorId).ToListAsync();
    }
}

internal static class EfCoreIntegration
{
    internal static void Register(IServiceCollection services)
    {
        services.AddAbpDbContext<MyProjectDbContext>(options =>
        {
            options.AddDefaultRepositories(includeAllEntities: true);
            options.AddRepository<EfBook, EfCoreBookRepository>();
        });
    }

    internal static void ConfigureProvider()
    {
        var options = new AbpDbContextOptions();
        options.UseSqlServer();
    }
}
