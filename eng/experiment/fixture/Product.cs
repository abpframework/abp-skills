using System;
using Volo.Abp.Domain.Entities.Auditing;

namespace Acme.Fixture;

public class Product : FullAuditedAggregateRoot<Guid>
{
    public string Name { get; set; } = string.Empty;
    public decimal Price { get; set; }

    protected Product() { }

    public Product(Guid id, string name, decimal price) : base(id)
    {
        Name = name;
        Price = price;
    }
}
