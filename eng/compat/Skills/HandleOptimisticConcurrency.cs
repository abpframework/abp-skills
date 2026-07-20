// Compile-smoke for skill: abp-data-access/handle-optimistic-concurrency
// Exercises IHasConcurrencyStamp, aggregate-root base, stamp flow through DTOs, AbpDbConcurrencyException.
using System;
using System.Threading.Tasks;
using Volo.Abp.Application.Dtos;
using Volo.Abp.Data;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Entities.Auditing;
using Volo.Abp.Domain.Repositories;

namespace AbpSkillsCompat.Skills;

internal class ConcurrentBook : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; } = default!;
}

// Plain entity must implement IHasConcurrencyStamp and (for MongoDB) initialize the stamp itself.
internal class PlainConcurrentBook : Entity<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = Guid.NewGuid().ToString("N");
}

internal class ConcurrentBookDto : EntityDto<Guid>, IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = default!;
}

internal class UpdateConcurrentBookDto : IHasConcurrencyStamp
{
    public string ConcurrencyStamp { get; set; } = default!;
    public string Name { get; set; } = default!;
}

internal static class HandleOptimisticConcurrency
{
    internal static async Task<ConcurrentBook> UpdateAsync(
        IRepository<ConcurrentBook, Guid> repository,
        Guid id,
        UpdateConcurrentBookDto input)
    {
        var book = await repository.GetAsync(id);
        book.ConcurrencyStamp = input.ConcurrencyStamp;
        book.Name = input.Name;
        await repository.UpdateAsync(book, autoSave: true);
        return book;
    }

    internal static async Task HandleAsync(Func<Task> update)
    {
        try
        {
            await update();
        }
        catch (AbpDbConcurrencyException)
        {
            // Re-read the latest record and let the user retry.
        }
    }
}
