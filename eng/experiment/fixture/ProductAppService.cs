using System;
using System.Threading.Tasks;
using Volo.Abp.Application.Services;

namespace Acme.Fixture;

public class ProductAppService : ApplicationService, IProductAppService
{
    public Task<string> GetNameAsync(Guid id) => Task.FromResult("sample");
}

public interface IProductAppService : IApplicationService
{
    Task<string> GetNameAsync(Guid id);
}
