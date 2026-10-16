# Exercise the actual GUI parameter-selection block in Windows PowerShell 5.1.
# No WinForms, network, API key, model or iPad required.
$ErrorActionPreference = 'Stop'
$source = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot '..\RUN_B16_TESTKIT_GUI.ps1'), [System.Text.Encoding]::UTF8)
$start = $source.IndexOf('$resumeArgs=@(')
$end = $source.IndexOf('$form.Dispose()', $start)
if ($start -lt 0 -or $end -le $start) {
    throw 'Cannot isolate the GUI CLI argument-selection code'
}
$selection = [scriptblock]::Create($source.Substring($start, $end - $start))

function Capture-Arguments {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Values)
    $script:captured = @($Values)
}

foreach ($case in @(
    @{ Name='Quick resume'; Mode=0; Fresh=$false; Expected=@('--resume-latest') },
    @{ Name='Quick fresh'; Mode=0; Fresh=$true; Expected=@() },
    @{ Name='Full resume'; Mode=1; Fresh=$false; Expected=@('--resume-latest') },
    @{ Name='Full fresh'; Mode=1; Fresh=$true; Expected=@() }
)) {
    $mode = [pscustomobject]@{ SelectedIndex = $case.Mode }
    $fresh = [pscustomobject]@{ Checked = $case.Fresh }
    $previous = [pscustomobject]@{ Text = '' }
    $resumeArgs = $null
    $modeArgs = $null
    . $selection
    if ($resumeArgs -isnot [array]) {
        throw "$($case.Name): resumeArgs must remain an array; got $($resumeArgs.GetType().FullName)"
    }
    $script:captured = @()
    Capture-Arguments @resumeArgs
    if (($captured -join [char]0) -cne ($case.Expected -join [char]0)) {
        throw "$($case.Name): wrong native CLI splat: $($captured -join ',')"
    }
    if ($case.Mode -eq 0 -and (($modeArgs -join ' ') -cne '--mode quick --direction prefill-batch')) {
        throw "$($case.Name): Quick mode arguments changed"
    }
    Write-Host "PASS $($case.Name)"
}
Write-Host 'GUI_ARGV_CONTRACT=PASS'
