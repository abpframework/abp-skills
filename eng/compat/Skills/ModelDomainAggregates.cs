// Compile-smoke for skill: abp-module-development/model-domain-aggregates
// Exercises AggregateRoot/BasicAggregateRoot, ValueObject + GetAtomicValues, DomainService,
// Specification<T> + ToExpression, IGuidGenerator, Check, and AddLocalEvent/AddDistributedEvent.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using System.Threading.Tasks;
using Volo.Abp;
using Volo.Abp.Domain.Entities;
using Volo.Abp.Domain.Repositories;
using Volo.Abp.Domain.Services;
using Volo.Abp.Domain.Values;
using Volo.Abp.Guids;
using Volo.Abp.Specifications;

namespace AbpSkillsCompat.Skills;

internal class ModelOrderLine : Entity<Guid>
{
    public Guid OrderId { get; protected set; }
    public Guid ProductId { get; protected set; }
    public int Count { get; protected set; }

    protected ModelOrderLine() { }

    internal ModelOrderLine(Guid orderId, Guid productId, int count)
    {
        OrderId = orderId;
        ProductId = productId;
        Count = count;
    }

    internal void ChangeCount(int count) => Count = count;
}

internal class ModelOrder : AggregateRoot<Guid>
{
    public string ReferenceNo { get; protected set; }
    public int TotalItemCount { get; protected set; }
    public List<ModelOrderLine> OrderLines { get; protected set; }
    public bool IsCompleted { get; protected set; }

    protected ModelOrder()
    {
        ReferenceNo = string.Empty;
        OrderLines = new List<ModelOrderLine>();
    }

    public ModelOrder(Guid id, string referenceNo)
    {
        Check.NotNull(referenceNo, nameof(referenceNo));
        Id = id;
        ReferenceNo = referenceNo;
        OrderLines = new List<ModelOrderLine>();
    }

    public void SetAsCompleted()
    {
        IsCompleted = true;
        AddLocalEvent(new OrderCompletedEto { OrderId = Id });
        AddDistributedEvent(new OrderCompletedEto { OrderId = Id });
    }
}

internal sealed class OrderCompletedEto
{
    public Guid OrderId { get; set; }
}

// A lean aggregate without extra-properties/concurrency-stamp.
internal sealed class ModelTag : BasicAggregateRoot<Guid>
{
    public string Name { get; set; } = string.Empty;
}

internal sealed class ModelAddress : ValueObject
{
    public Guid CityId { get; private set; }
    public string Street { get; private set; }
    public int Number { get; private set; }

    private ModelAddress()
    {
        Street = string.Empty;
    }

    public ModelAddress(Guid cityId, string street, int number)
    {
        CityId = cityId;
        Street = street;
        Number = number;
    }

    protected override IEnumerable<object> GetAtomicValues()
    {
        yield return Street;
        yield return CityId;
        yield return Number;
    }
}

internal sealed class ModelCustomer : AggregateRoot<Guid>
{
    public int Age { get; set; }
}

internal sealed class Age18PlusCustomerSpecification : Specification<ModelCustomer>
{
    public override Expression<Func<ModelCustomer, bool>> ToExpression()
        => c => c.Age >= 18;
}

internal sealed class ModelOrderManager : DomainService
{
    private readonly IRepository<ModelOrder, Guid> _orderRepository;

    public ModelOrderManager(IRepository<ModelOrder, Guid> orderRepository)
    {
        _orderRepository = orderRepository;
    }

    public async Task<ModelOrder> CreateAsync(string referenceNo)
    {
        // Enforce cross-aggregate rules here, then return the new entity — the application
        // service persists it, so the domain service doesn't save.
        if (await _orderRepository.AnyAsync(o => o.ReferenceNo == referenceNo))
        {
            throw new BusinessException("MyProject:DuplicateReferenceNo");
        }

        return new ModelOrder(GuidGenerator.Create(), referenceNo);
    }
}

internal static class ModelDomainAggregates
{
    internal static bool UseValueObjectAndSpec(
        IGuidGenerator guidGenerator,
        ModelAddress a1,
        ModelAddress a2,
        ModelCustomer customer)
    {
        var id = guidGenerator.Create();
        var equal = a1.ValueEquals(a2);
        var spec = new Age18PlusCustomerSpecification();
        var expression = spec.ToExpression();
        return spec.IsSatisfiedBy(customer) && equal && id != Guid.Empty;
    }
}
