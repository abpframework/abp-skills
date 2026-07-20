// Compile-smoke for skill: abp-data-access/query-with-dapper
// Exercises DapperRepository<TDbContext>, GetDbConnectionAsync/GetDbTransactionAsync, shared UoW.
using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Threading.Tasks;
using Dapper;
using Volo.Abp.DependencyInjection;
using Volo.Abp.Domain.Repositories.Dapper;
using Volo.Abp.EntityFrameworkCore;
using MyProjectDbContext = Volo.Abp.EntityFrameworkCore.IEfCoreDbContext;

namespace AbpSkillsCompat.Skills;

internal interface IPersonDapperRepository
{
    Task<List<string>> GetAllPersonNamesAsync();
}

internal class PersonDapperRepository :
    DapperRepository<MyProjectDbContext>, IPersonDapperRepository, ITransientDependency
{
    public PersonDapperRepository(IDbContextProvider<MyProjectDbContext> dbContextProvider)
        : base(dbContextProvider)
    {
    }

    public virtual async Task<List<string>> GetAllPersonNamesAsync()
    {
        var dbConnection = await GetDbConnectionAsync();
        return (await dbConnection.QueryAsync<string>(
            "select Name from People",
            transaction: await GetDbTransactionAsync())
        ).ToList();
    }

    public virtual async Task<int> UpdatePersonNameAsync(Guid id, string name)
    {
        var dbConnection = await GetDbConnectionAsync();
        IDbTransaction? transaction = await GetDbTransactionAsync();
        // Always scope a write with a WHERE clause — without it this updates every row.
        return await dbConnection.ExecuteAsync(
            "update People set Name = @NewName where Id = @Id",
            new { Id = id, NewName = name },
            transaction);
    }
}
