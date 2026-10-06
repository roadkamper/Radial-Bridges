param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$CertificateThumbprint,
    [Parameter(Mandatory=$true)][string]$TimestampUrl,
    [Parameter(Mandatory=$true)][string]$SignToolPath,
    [Parameter(Mandatory=$true)][string]$MakeNsisPath
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $SignToolPath -PathType Leaf)) { throw 'SignTool not found.' }
if (-not (Test-Path -LiteralPath $MakeNsisPath -PathType Leaf)) { throw 'NSIS not found.' }
$timestamp = [uri]$TimestampUrl
if (-not $timestamp.IsAbsoluteUri -or $timestamp.Scheme -notin @('http','https')) { throw 'Use your provider RFC3161 HTTP/HTTPS URL.' }
function Sign-And-Verify([string]$File) {
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { throw "Missing file: $File" }
    & $SignToolPath sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $File
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $File" }
    & $SignToolPath verify /pa /v $File
    if ($LASTEXITCODE -ne 0) { throw "Verification failed: $File" }
}
Push-Location $repo
try {
    Sign-And-Verify (Join-Path $repo 'payload/RadialBridges.exe')
    & $MakeNsisPath -V3 installer.nsi
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    Sign-And-Verify (Join-Path $repo 'RadialBridges-Setup.exe')
    $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath 'RadialBridges-Setup.exe').Hash.ToLowerInvariant()
    "$digest  RadialBridges-Setup.exe" | Set-Content -Encoding ascii -LiteralPath 'SHA256SUMS.txt'
} finally { Pop-Location }
