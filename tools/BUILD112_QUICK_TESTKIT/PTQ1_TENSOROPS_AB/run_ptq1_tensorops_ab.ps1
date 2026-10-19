$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root 'ptq1_tensorops_ab.py'
if (-not (Test-Path -LiteralPath $runner)) { throw 'Extract the complete PTQ1 TensorOps A/B kit first.' }
Write-Host 'Bonsai PTQ1_0 TensorOps A/B TestKit'
Write-Host 'This run measures ONE already-selected app arm. BASELINE and CANDIDATE must use the same IPA and model.'
$base = Read-Host 'API base URL (for example http://192.168.1.92:8080)'
if ([string]::IsNullOrWhiteSpace($base)) { throw 'API URL is required.' }
$arm = (Read-Host 'Current app arm: enter BASELINE or CANDIDATE').Trim().ToUpperInvariant()
if ($arm -notin @('BASELINE','CANDIDATE')) { throw 'Arm must be BASELINE or CANDIDATE.' }
$keySecure = Read-Host 'API Key (press Enter if authentication is disabled)' -AsSecureString
$key = ''
if ($keySecure.Length -gt 0) {
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($keySecure)
  try { $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
$previous = Read-Host 'Previous opposite-arm result ZIP (blank for first arm)'
$include8192 = (Read-Host 'Also measure 8192 input tokens? Only answer Y if you want the longer test').Trim().ToUpperInvariant() -eq 'Y'
$env:BONSAI_API_KEY = $key
$args = @('--base-url', $base, '--arm', $arm, '--output', (Join-Path $root 'RESULTS'))
if (-not [string]::IsNullOrWhiteSpace($previous)) { $args += @('--previous', $previous.Trim()) }
if ($include8192) { $args += '--include-8192' }
$python = $null
if (Get-Command 'py.exe' -ErrorAction SilentlyContinue) { $python = 'py.exe'; $pyArgs = @('-3','-u') }
elseif (Get-Command 'python.exe' -ErrorAction SilentlyContinue) { $python = 'python.exe'; $pyArgs = @('-u') }
else { throw 'Python 3 is required. Install Python 3 and rerun this launcher.' }
try { & $python @pyArgs $runner @args; exit $LASTEXITCODE }
finally { Remove-Item Env:BONSAI_API_KEY -ErrorAction SilentlyContinue; $key = $null }
