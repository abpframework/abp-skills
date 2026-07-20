// Compile-smoke for skill: abp-data-access/seed-application-data
// Exercises IDataSeedContributor, DataSeedContext.TenantId, IDataSeeder, DataSeederExtensions.
using System;
using System.Threading.Tasks;
using Volo.Abp.Data;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Guids;
using Volo.Abp.MultiTenancy;
using Volo.Abp.Uow;

namespace AbpSkillsCompat.Skills;

internal class SeedBook : AggregateRoot<Guid>
{
    public string Name { get; set; } = default!;
    public int Price { get; set; }

    public SeedBook(Guid id, string name, int price)
        : base(id)
    {
        Name = name;
        Price = price;
    }
}

internal class BookStoreDataSeedContributor
    : IDataSeedContributor, ITransientDependency
{
    private readonly IRepository<SeedBook, Guid> _bookRepository;
    private readonly IGuidGenerator _guidGenerator;
    private readonly ICurrentTenant _currentTenant;

    public BookStoreDataSeedContributor(
        IRepository<SeedBook, Guid> bookRepository,
        IGuidGenerator guidGenerator,
        ICurrentTenant currentTenant)
    {
        _bookRepository = bookRepository;
        _guidGenerator = guidGenerator;
        _currentTenant = currentTenant;
    }

    public async Task SeedAsync(DataSeedContext context)
    {
        using (_currentTenant.Change(context?.TenantId))
        {
            if (await _bookRepository.GetCountAsync() > 0)
            {
                return;
            }

            var book = new SeedBook(
                id: _guidGenerator.Create(),
                name: "The Hitchhiker's Guide to the Galaxy",
                price: 42);

            await _bookRepository.InsertAsync(book);
        }
    }
}

internal static class SeedApplicationData
{
    internal static async Task RunAsync(IDataSeeder dataSeeder, string adminEmail, string adminPassword)
    {
        // Read the admin credentials from configuration / a secret store — don't hardcode them.
        await dataSeeder.SeedAsync(
            new DataSeedContext()
                .WithProperty("AdminEmail", adminEmail)
                .WithProperty("AdminPassword", adminPassword));

        await dataSeeder.SeedAsync(tenantId: null);

        await dataSeeder.SeedInSeparateUowAsync(
            tenantId: null,
            options: new AbpUnitOfWorkOptions(),
            requiresNew: true);
    }
}
