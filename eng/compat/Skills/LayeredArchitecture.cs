// Compile-smoke for skill: abp-module-development/layered-architecture
// Exercises the per-layer building blocks: Entity/AggregateRoot/FullAuditedAggregateRoot,
// IRepository interfaces, DomainService, and the Application.Contracts DTO base types.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Application.Dtos;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Entities.Auditing;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Domain.Services;

namespace AbpSkillsCompat.Skills;

// *.Domain — a plain entity.
internal class LayeredOrderLine : Entity<Guid>
{
    public string ProductName { get; set; } = string.Empty;
    public int Quantity { get; set; }

    protected LayeredOrderLine() { }
}

// *.Domain — an aggregate root (consistency boundary).
internal class LayeredOrder : AggregateRoot<Guid>
{
    public string CustomerName { get; set; } = string.Empty;

    protected LayeredOrder() { }

    public LayeredOrder(Guid id, string customerName) : base(id)
    {
        CustomerName = customerName;
    }
}

// *.Domain — a full-audited aggregate root.
internal class LayeredBook : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; } = string.Empty;

    protected LayeredBook() { }

    public LayeredBook(Guid id, string name) : base(id)
    {
        Name = name;
    }
}

// *.Domain — custom repository interface.
internal interface ILayeredBookRepository : IRepository<LayeredBook, Guid>
{
    Task<List<LayeredBook>> GetListByAuthorAsync(Guid authorId);
}

// *.Domain — a domain service.
internal sealed class LayeredBookManager : DomainService
{
    private readonly IRepository<LayeredBook, Guid> _bookRepository;

    public LayeredBookManager(IRepository<LayeredBook, Guid> bookRepository)
    {
        _bookRepository = bookRepository;
    }

    public async Task<LayeredBook> CreateAsync(string name)
    {
        // Enforce cross-aggregate rules here, then return the new entity — the
        // application service persists it, so the domain service doesn't save.
        if (await _bookRepository.AnyAsync(b => b.Name == name))
        {
            throw new BusinessException("MyProject:DuplicateBookName");
        }

        return new LayeredBook(GuidGenerator.Create(), name);
    }
}

// *.Application.Contracts — DTO base types.
internal sealed class LayeredBookDto : FullAuditedEntityDto<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal static class LayeredArchitecture
{
    internal static PagedResultDto<LayeredBookDto> EmptyPage()
    {
        return new PagedResultDto<LayeredBookDto>(0, new List<LayeredBookDto>());
    }

    internal static PagedAndSortedResultRequestDto DefaultRequest()
    {
        return new PagedAndSortedResultRequestDto();
    }
}
