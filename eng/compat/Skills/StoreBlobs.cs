// Compile-smoke for skill: abp-files/store-blobs
// Exercises IBlobContainer / IBlobContainer<T>, [BlobContainerName], byte[] extensions,
// and AbpBlobStoringOptions container configuration.
using System.Threading.Tasks;
using Volo.Abp.BlobStoring;
using Volo.Abp.BlobStoring.Aws;
using Volo.Abp.BlobStoring.Azure;
using Volo.Abp.BlobStoring.Database;
using Volo.Abp.BlobStoring.Minio;
using Volo.Abp.DependencyInjection;

namespace AbpSkillsCompat.Skills;

[BlobContainerName("profile-pictures")]
internal sealed class ProfilePictureContainer
{
}

internal static class StoreBlobs
{
    internal sealed class DefaultUser : ITransientDependency
    {
        private readonly IBlobContainer _blobContainer;

        public DefaultUser(IBlobContainer blobContainer)
        {
            _blobContainer = blobContainer;
        }

        public async Task<byte[]?> RoundTripAsync(byte[] bytes)
        {
            await _blobContainer.SaveAsync("my-blob-1", bytes, overrideExisting: true);
            if (await _blobContainer.ExistsAsync("my-blob-1"))
            {
                return await _blobContainer.GetAllBytesOrNullAsync("my-blob-1");
            }

            await _blobContainer.DeleteAsync("my-blob-1");
            return null;
        }
    }

    internal sealed class TypedUser : ITransientDependency
    {
        private readonly IBlobContainer<ProfilePictureContainer> _blobContainer;
        private readonly IBlobContainerFactory _factory;

        public TypedUser(
            IBlobContainer<ProfilePictureContainer> blobContainer,
            IBlobContainerFactory factory)
        {
            _blobContainer = blobContainer;
            _factory = factory;
        }

        public async Task SaveAsync(string name, byte[] bytes)
        {
            await _blobContainer.SaveAsync(name, bytes, overrideExisting: true);
            var byName = _factory.Create("profile-pictures");
            var byType = _factory.Create<ProfilePictureContainer>();
        }
    }

    internal static void Configure(AbpBlobStoringOptions options)
    {
        options.Containers.Configure<ProfilePictureContainer>(container =>
        {
            container.IsMultiTenant = false;
        });

        options.Containers.ConfigureDefault(container =>
        {
            container.IsMultiTenant = true;
        });
    }

    // Mainstream storage providers the skill documents (Azure / AWS S3 / MinIO / Database).
    // Connection strings and credentials are passed in — read them from configuration or a
    // secret store, never hardcode them.
    internal static void Providers(
        BlobContainerConfiguration container, string azureConnectionString, string accessKey, string secretKey)
    {
        container.UseAzure(azure =>
        {
            azure.ConnectionString = azureConnectionString;
            azure.ContainerName = "my-container";
            azure.CreateContainerIfNotExists = true;
        });

        container.UseAws(aws =>
        {
            aws.AccessKeyId = accessKey;
            aws.SecretAccessKey = secretKey;
            aws.UseCredentials = true;
            aws.ContainerName = "my-bucket";
            aws.CreateContainerIfNotExists = true;
        });

        container.UseMinio(minio =>
        {
            minio.EndPoint = "localhost:9000";
            minio.AccessKey = accessKey;
            minio.SecretKey = secretKey;
            minio.BucketName = "my-bucket";
        });

        container.UseDatabase();
    }
}
