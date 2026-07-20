// Compile-smoke for skill: abp-data-access/use-abp-repositories
// Exercises the IRepository consumption surface the skill teaches: standard methods
// (Get/Find/GetList/GetPagedList/GetCount), bulk operations, WithDetailsAsync eager loading of a
// real navigation, GetQueryableAsync + provider-neutral async LINQ via IAsyncQueryableExecuter,
// DisableTracking/EnableTracking + [DisableEntityChangeTracking], DeleteDirectAsync, HardDeleteAsync,
// and the read-only/basic repository variants.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Domain.ChangeTracking;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Linq;

namespace AbpSkillsCompat.Skills;

internal class Chapter : Entity<Guid>
{
    public string Title { get; set; } = string.Empty;
}

internal class Book : AggregateRoot<Guid>, ISoftDelete
{
    public string Name { get; set; } = string.Empty;
    public bool IsDeleted { get; set; }
    public List<Chapter> Chapters { get; set; } = new();
}

internal static class UseAbpRepositories
{
    internal static async Task StandardMethods(IRepository<Book, Guid> repository)
    {
        Book found = await repository.GetAsync(Guid.NewGuid());   // throws EntityNotFoundException if missing
        Book? maybe = await repository.FindAsync(Guid.NewGuid()); // null if missing
        List<Book> all = await repository.GetListAsync();
        List<Book> page = await repository.GetPagedListAsync(skipCount: 0, maxResultCount: 10, sorting: "Name");
        long count = await repository.GetCountAsync();
        _ = found; _ = maybe; _ = all; _ = page; _ = count;
    }

    internal static async Task Bulk(IRepository<Book, Guid> repository, IEnumerable<Book> books)
    {
        await repository.InsertManyAsync(books, autoSave: true);
        await repository.UpdateManyAsync(books);
        await repository.DeleteManyAsync(books);
        await repository.DeleteDirectAsync(b => b.Name == "x"); // bypasses the change-tracking pipeline
    }

    internal static async Task<Book?> EagerAndQueryable(
        IRepository<Book, Guid> repository, IAsyncQueryableExecuter asyncExecuter)
    {
        IQueryable<Book> withDetails = await repository.WithDetailsAsync(b => b.Chapters); // navigation, valid eager load
        IQueryable<Book> queryable = await repository.GetQueryableAsync();
        var query = queryable.Where(b => b.Name == "abp");
        _ = withDetails;
        return await asyncExecuter.FirstOrDefaultAsync(query); // provider-neutral async execution
    }

    internal static IDisposable NoTracking(IRepository<Book, Guid> repository)
    {
        using (repository.DisableTracking()) { }
        return repository.EnableTracking();
    }

    [DisableEntityChangeTracking]
    internal static async Task<long> ReadOnlyScope(IRepository<Book, Guid> repository)
    {
        return await repository.GetCountAsync();
    }

    internal static async Task Hard(IRepository<Book> repository)
    {
        await repository.HardDeleteAsync(b => b.Name == "x"); // ignores soft-delete, permanent
    }

    internal static void Variants(
        IReadOnlyRepository<Book, Guid> readOnly, IBasicRepository<Book, Guid> basic)
    {
        _ = readOnly; _ = basic;
    }
}
