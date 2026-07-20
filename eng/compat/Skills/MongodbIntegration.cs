// Compile-smoke for skill: abp-data-access/mongodb-integration
// Exercises AbpMongoDbContext, [MongoCollection], CreateModel, AddMongoDbContext, MongoDbRepository.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using MongoDB.Driver;
using MongoDB.Driver.Linq;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Domain.Repositories.MongoDB;
using Volo.Abp.MongoDB;

namespace AbpSkillsCompat.Skills;

internal class MongoBook : AggregateRoot<Guid>
{
    public string Name { get; set; } = default!;
    public Guid AuthorId { get; set; }
}

[ConnectionStringName("Default")]
internal class MyProjectMongoDbContext : AbpMongoDbContext
{
    [MongoCollection("AppBooks")]
    public IMongoCollection<MongoBook> Books => Collection<MongoBook>();

    protected override void CreateModel(IMongoModelBuilder modelBuilder)
    {
        base.CreateModel(modelBuilder);

        modelBuilder.Entity<MongoBook>(b =>
        {
            b.CollectionName = "AppBooks";
        });
    }
}

internal interface IMongoBookRepository : IRepository<MongoBook, Guid>
{
    Task<List<MongoBook>> GetListByAuthorAsync(Guid authorId);
}

internal class MongoDbBookRepository
    : MongoDbRepository<MyProjectMongoDbContext, MongoBook, Guid>, IMongoBookRepository
{
    public MongoDbBookRepository(IMongoDbContextProvider<MyProjectMongoDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public async Task<List<MongoBook>> GetListByAuthorAsync(Guid authorId)
    {
        var queryable = await GetQueryableAsync();
        var collection = await GetCollectionAsync();
        _ = collection;
        return await queryable.Where(b => b.AuthorId == authorId).ToListAsync();
    }
}

internal static class MongodbIntegration
{
    internal static void Register(IServiceCollection services)
    {
        services.AddMongoDbContext<MyProjectMongoDbContext>(options =>
        {
            options.AddDefaultRepositories(includeAllEntities: true);
            options.AddRepository<MongoBook, MongoDbBookRepository>();
        });
    }
}
