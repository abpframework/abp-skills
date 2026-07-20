// Compile-smoke for skill: abp-module-development/application-services
// Exercises IApplicationService/ApplicationService, the CrudAppService /
// AbstractKeyCrudAppService base, ObjectMapper, IValidationEnabled, and
// unit-of-work basics. Conventional-controller routing is a runtime MVC concern
// (not a compile surface) and is exercised by the eval, not here.
using System;
using System.ComponentModel.DataAnnotations;
using System.Threading.Tasks;
using Volo.Abp.Application.Dtos;
using Volo.Abp.Application.Services;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.ObjectMapping;
using Volo.Abp.Uow;
using Volo.Abp.Validation;

namespace AbpSkillsCompat.Skills;

internal sealed class AppSvcBook : Entity<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class AppSvcBookDto
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
}

internal sealed class AppSvcCreateBookDto
{
    [Required]
    [StringLength(128)]
    public string Name { get; set; } = string.Empty;

    [Range(typeof(decimal), "0", "999.99")]
    public decimal Price { get; set; }
}

internal interface IAppSvcBookAppService : IApplicationService
{
    Task<AppSvcBookDto> GetAsync(Guid id);
}

internal sealed class AppSvcBookAppService : ApplicationService, IAppSvcBookAppService
{
    private readonly IRepository<AppSvcBook, Guid> _bookRepository;

    public AppSvcBookAppService(IRepository<AppSvcBook, Guid> bookRepository)
    {
        _bookRepository = bookRepository;
    }

    public async Task<AppSvcBookDto> GetAsync(Guid id)
    {
        var book = await _bookRepository.GetAsync(id);
        return ObjectMapper.Map<AppSvcBook, AppSvcBookDto>(book);
    }

    [UnitOfWork(isTransactional: true)]
    public async Task DoWorkAsync()
    {
        await Task.CompletedTask;
    }
}

// Real AbstractKeyCrudAppService coverage: CrudAppService<...> derives from it, so a
// signature drift on the CRUD base breaks this compile-smoke.
internal sealed class AppSvcBookCrudAppService
    : CrudAppService<AppSvcBook, AppSvcBookDto, Guid, PagedAndSortedResultRequestDto, AppSvcCreateBookDto>
{
    public AppSvcBookCrudAppService(IRepository<AppSvcBook, Guid> repository)
        : base(repository)
    {
    }
}

internal static class ApplicationServices
{
    // IValidationEnabled marker + IObjectMapper overloads referenced for compile coverage.
    internal static void ReferenceTypes(IObjectMapper mapper, IUnitOfWorkManager uowManager)
    {
        IValidationEnabled marker = new AppSvcBookAppService(null!);
        var dto = mapper.Map<AppSvcBook, AppSvcBookDto>(new AppSvcBook());
        mapper.Map(new AppSvcBook(), dto);
        var current = uowManager.Current;
    }
}
