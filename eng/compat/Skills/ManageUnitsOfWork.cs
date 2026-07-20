// Compile-smoke for skill: abp-data-access/manage-units-of-work
// Exercises [UnitOfWork], IUnitOfWorkManager.Begin/Current, SaveChangesAsync, default options.
using System;
using System.Data;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Builder;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Uow;

namespace AbpSkillsCompat.Skills;

internal class UowCategory : AggregateRoot<Guid>
{
    public string Name { get; set; } = default!;
}

internal static class ManageUnitsOfWork
{
    internal static void ConfigureDefaults()
    {
        var options = new AbpUnitOfWorkDefaultOptions
        {
            TransactionBehavior = UnitOfWorkTransactionBehavior.Disabled,
            Timeout = 30000
        };
        options.IsolationLevel = IsolationLevel.ReadCommitted;
        IsolationLevel? isolationLevel = options.IsolationLevel;
        _ = isolationLevel;
    }

    internal static IApplicationBuilder UseUow(IApplicationBuilder app)
    {
        return app.UseUnitOfWork();
    }

    internal static async Task ReservedScopeAsync(IUnitOfWorkManager unitOfWorkManager)
    {
        IUnitOfWork reserved = unitOfWorkManager.Reserve("my-reservation", requiresNew: true);
        var uowOptions = new AbpUnitOfWorkOptions(isTransactional: true);
        unitOfWorkManager.BeginReserved("my-reservation", uowOptions);
        bool began = unitOfWorkManager.TryBeginReserved("my-reservation", uowOptions);
        _ = reserved;
        _ = began;
        await Task.CompletedTask;
    }
}

internal class UowService : ITransientDependency
{
    private readonly IUnitOfWorkManager _unitOfWorkManager;
    private readonly IRepository<UowCategory, Guid> _repository;

    public UowService(IUnitOfWorkManager unitOfWorkManager, IRepository<UowCategory, Guid> repository)
    {
        _unitOfWorkManager = unitOfWorkManager;
        _repository = repository;
    }

    [UnitOfWork(isTransactional: true)]
    public virtual async Task FooAsync()
    {
        using (var uow = _unitOfWorkManager.Begin(requiresNew: true, isTransactional: true))
        {
            var category = new UowCategory { Name = "abp" };
            await _repository.InsertAsync(category);

            var current = _unitOfWorkManager.Current;
            if (current != null)
            {
                await current.SaveChangesAsync();
                current.OnCompleted(() => Task.CompletedTask);
                if (current.IsReserved)
                {
                    await current.RollbackAsync();
                    return;
                }
            }

            await uow.CompleteAsync();
        }
    }

    [UnitOfWork(IsDisabled = true)]
    public virtual async Task NoUowAsync()
    {
        await Task.CompletedTask;
    }
}
