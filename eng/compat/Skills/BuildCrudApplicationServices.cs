// Compile-smoke for skill: abp-module-development/build-crud-application-services
// Exercises ICrudAppService/CrudAppService overloads, DTO base types, policy names,
// CreateFilteredQueryAsync, and MapToEntityAsync overrides.
using System;
using System.Linq;
using System.Threading.Tasks;
using Volo.Abp.Application.Dtos;
using Volo.Abp.Application.Services;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;

namespace AbpSkillsCompat.Skills;

internal sealed class CrudBook : Entity<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class CrudBookDto : EntityDto<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class CrudBookListDto : EntityDto<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class CrudGetBookListInput : PagedAndSortedResultRequestDto
{
    public string? Filter { get; set; }
}

internal sealed class CrudCreateBookDto
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class CrudUpdateBookDto : IEntityDto<Guid>
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;

    public string GetObjectKey() => Id.ToString();
}

internal interface ICrudBookAppService : ICrudAppService<
    CrudBookDto,
    CrudBookListDto,
    Guid,
    CrudGetBookListInput,
    CrudCreateBookDto,
    CrudUpdateBookDto>
{
}

internal sealed class CrudBookAppService : CrudAppService<
    CrudBook,
    CrudBookDto,
    CrudBookListDto,
    Guid,
    CrudGetBookListInput,
    CrudCreateBookDto,
    CrudUpdateBookDto>, ICrudBookAppService
{
    public CrudBookAppService(IRepository<CrudBook, Guid> repository)
        : base(repository)
    {
        GetPolicyName = "Books.Default";
        GetListPolicyName = "Books.Default";
        CreatePolicyName = "Books.Create";
        UpdatePolicyName = "Books.Update";
        DeletePolicyName = "Books.Delete";
    }

    protected override async Task<IQueryable<CrudBook>> CreateFilteredQueryAsync(
        CrudGetBookListInput input)
    {
        var query = await base.CreateFilteredQueryAsync(input);
        if (!string.IsNullOrWhiteSpace(input.Filter))
        {
            query = query.Where(b => b.Name.Contains(input.Filter));
        }

        return query;
    }

    protected override Task<CrudBook> MapToEntityAsync(CrudCreateBookDto createInput)
    {
        return Task.FromResult(new CrudBook { Name = createInput.Name });
    }

    protected override Task MapToEntityAsync(CrudUpdateBookDto updateInput, CrudBook entity)
    {
        entity.Name = updateInput.Name;
        return Task.CompletedTask;
    }
}

internal static class BuildCrudApplicationServices
{
    // The shortest ICrudAppService overload uses PagedAndSortedResultRequestDto implicitly.
    internal static Type ShortestOverload()
    {
        return typeof(ICrudAppService<CrudBookDto, Guid>);
    }

    // Call all five documented CRUD methods through the interface with explicit result
    // types, so a rename or return-type change on ICrudAppService/CrudAppService breaks
    // the build (inheritance alone would not catch a signature drift).
    internal static async Task ConsumeContract(ICrudBookAppService service, Guid id)
    {
        CrudBookDto detail = await service.GetAsync(id);

        PagedResultDto<CrudBookListDto> page = await service.GetListAsync(
            new CrudGetBookListInput());

        CrudBookDto created = await service.CreateAsync(
            new CrudCreateBookDto { Name = detail.Name });

        CrudBookDto updated = await service.UpdateAsync(
            id,
            new CrudUpdateBookDto { Id = id, Name = created.Name });

        await service.DeleteAsync(updated.Id);

        _ = page.TotalCount;
    }
}
