---
name: encrypt-strings
description: "ABP IStringEncryptionService with compatible passphrase, salt, IV, key-size options. USE FOR: reversible encryption used by ABP infra; AbpStringEncryptionOptions defaults and config keys; Encrypt/Decrypt null behavior; encrypted setting values. DO NOT USE FOR: password hashing, signing, token generation, or crypto protocol design; defining encrypted ABP settings (manage-settings-and-features)."
license: MIT
---

# Encrypt Strings in ABP

Use `IStringEncryptionService` when application code must interoperate with ABP's reversible string-encryption format. It is an AES-CBC compatibility service, not a password hasher, signature mechanism, token generator, or secret vault.

## When to Use

- Encrypt and later decrypt a string with the same ABP application configuration.
- Interoperate with ABP infrastructure such as encrypted setting values.
- Override the built-in passphrase, salt, initialization vector, and key size consistently across application instances.

## When Not to Use

- **Hash user passwords** — use the identity system's password hasher.
- **Generate or validate signed tokens, API keys, or cryptographic nonces** — use a protocol-specific primitive.
- **Define and manage encrypted ABP settings** — use manage-settings-and-features.

## How it works

### Call the service

`IStringEncryptionService` has synchronous nullable methods:

```csharp
string? Encrypt(string? plainText, string? passPhrase = null, byte[]? salt = null);
string? Decrypt(string? cipherText, string? passPhrase = null, byte[]? salt = null);
```

```csharp
public class ProtectedValueService : ITransientDependency
{
    private readonly IStringEncryptionService _encryptionService;

    public ProtectedValueService(IStringEncryptionService encryptionService)
    {
        _encryptionService = encryptionService;
    }

    public string Protect(string value)
    {
        return _encryptionService.Encrypt(value)!;
    }

    public string Unprotect(string value)
    {
        return _encryptionService.Decrypt(value)!;
    }
}
```

`Encrypt(null)` returns `null`. `Decrypt(null)` and `Decrypt("")` return `null`. The encrypted representation is Base64 text.

### Configure all application instances consistently

`AbpStringEncryptionOptions` ships with a **fixed, publicly-known default** passphrase,
init-vector, and salt (they're hard-coded in the ABP source). **Treat them as insecure
and always override them** for any real deployment — anything encrypted under the
defaults is effectively unprotected. `Keysize` defaults to `256`.

`AbpSecurityModule` reads these optional configuration keys (set the passphrase from a
secret-backed provider, not a committed file):

```json
{
  "StringEncryption": {
    "KeySize": "256",
    "DefaultPassPhrase": "replace-through-a-secret-provider",
    "InitVectorBytes": "replace-with-16b",
    "DefaultSalt": "replace-with-application-specific-salt"
  }
}
```

Do not commit a real passphrase in configuration files. Supply it through the deployment's secret-backed configuration provider. Every process that decrypts existing data must use compatible values. ABP ASCII-encodes `InitVectorBytes`, so it must be **exactly 16 characters** (the AES-CBC block size) — a wrong length throws at encrypt/decrypt time.

When passing `passPhrase` or `salt` directly to a method, that argument overrides the corresponding default for that call. The configured `InitVectorBytes` and `Keysize` still apply.

### Understand the compatibility format

`StringEncryptionService` derives a key with `Rfc2898DeriveBytes`, creates AES in CBC mode, and uses the configured fixed initialization vector. It does not append or verify an authentication tag. With the same passphrase, salt, and IV, identical plaintext produces identical ciphertext.

Use this format only where ABP compatibility is the requirement. For new security protocols, choose an authenticated-encryption design and a managed key lifecycle outside this abstraction.

## Validation

- Round-trip null, empty, ASCII, Unicode, and long values.
- Verify that independent application instances can decrypt each other's values with deployment configuration.
- Verify that changing passphrase, salt, IV, or key size makes old data unavailable unless a migration strategy exists.
- Test invalid Base64 and wrong-key behavior and handle the resulting exceptions at the correct boundary.
- Confirm the deployed passphrase comes from a secret provider and is not the built-in default.

## Common Pitfalls

- **Keeping the built-in `DefaultPassPhrase` in production** — ABP explicitly recommends replacing it.
- **Changing options after data has been encrypted** — decryption requires compatible key derivation and IV inputs.
- **Using the service for passwords** — reversible encryption is not password hashing.
- **Assuming ciphertext integrity is authenticated** — this AES-CBC implementation has no authentication tag.
- **Passing a new random salt only to `Encrypt` without storing it** — `Decrypt` needs the same salt.
- **Using an IV with an incompatible byte length** — AES key size and block-size requirements still apply.
