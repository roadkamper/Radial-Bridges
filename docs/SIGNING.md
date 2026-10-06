# Trusted Windows signing

**Current candidate: unsigned.** No trusted certificate or signing-service identity was supplied. Do not call icon/version resources, checksums, GitHub provenance, or a self-signed certificate a trusted Windows publisher signature.

You need a trusted code-signing identity with its key held in a supported token/HSM or signing service. Keep the private key out of this repository and chat. SignTool is supplied by the Windows SDK. This project supports certificate-store signing through the helper below; configure your certificate/token provider first.

## Order matters

1. Compile `payload/RadialBridges.exe` with `python build_windows.py --skip-installer`.
2. Sign and verify the launcher **before** NSIS packs it.
3. Build the installer using NSIS.
4. Sign and verify the installer.
5. Generate checksums after signing. Never edit signed bytes afterward.

Use `scripts/sign-release.ps1` with an explicitly selected certificate thumbprint and your certificate provider's RFC3161 timestamp URL. The script signs both layers in the correct order. It intentionally does not use `/a`, passwords in command arguments, or fake self-signed certificates.

```powershell
./scripts/sign-release.ps1 -CertificateThumbprint YOUR_CERTIFICATE_THUMBPRINT -TimestampUrl YOUR_PROVIDER_TIMESTAMP_URL -SignToolPath 'C:/path/to/signtool.exe' -MakeNsisPath 'C:/Program Files (x86)/NSIS/makensis.exe'
```

Managed/cloud signing providers may require their own SignTool plugin or identity workflow. Adapt only after selecting the provider; that integration is not preconfigured here. The script has been statically reviewed but not executed with a real certificate in this environment.

Signing can identify the publisher and detect tampering. **A valid signature does not guarantee SmartScreen will stop warning**, particularly for a new application. Do not ask users to disable Windows security.

Official references:

- https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
- https://learn.microsoft.com/en-us/windows/win32/seccrypto/time-stamping-authenticode-signatures
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
