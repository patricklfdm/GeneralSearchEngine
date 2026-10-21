# Native Windows PowerShell regression tests. No WSL launch, service change,
# cloud call, D-drive write, or real wakefulness request. No Pester dependency.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'v52-start.ps1')
function Assert-Gse($Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
}
$oldPublish = ${function:Publish-GseHostSpace}
$oldMessage = ${function:Write-GseMonitorMessage}
$oldCycle = ${function:Invoke-GseMonitorCycle}
$oldInvoke = ${function:Invoke-GseWsl}
$oldKeeper = ${function:Start-GseKeeper}
$oldWake = ${function:Set-GseWakefulness}
$oldWslenv = $env:WSLENV
try {
    $env:WSLENV = 'VSCODE_WSL_EXT_LOCATION/up:EXAMPLE/p'
    $info = New-GseWslStartInfo '-u root --exec /usr/bin/true'
    Assert-Gse ($info.EnvironmentVariables['WSLENV'] -eq '') 'child must not translate cross-distro paths'
    Assert-Gse ($env:WSLENV -eq 'VSCODE_WSL_EXT_LOCATION/up:EXAMPLE/p') 'parent environment must be unchanged'
    Assert-Gse ($info.WorkingDirectory -eq $env:SystemRoot) 'child working directory must be Windows local'
    Write-Host 'PASS scoped WSL environment and working directory'

    function Test-Child([string]$Code, [int]$Timeout=20, [string]$InputText='') {
        $info = New-GseWslStartInfo ''
        $info.FileName = Join-Path $PSHOME 'powershell.exe'
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Code))
        $info.Arguments = '-NoProfile -NonInteractive -EncodedCommand ' + $encoded
        Invoke-GseWsl -Info $info -TimeoutSeconds $Timeout -InputText $InputText
    }
    $result = Test-Child '[Console]::Error.Write("synthetic-management-failure"); exit 7'
    Assert-Gse (-not $result.Success -and $result.ExitCode -eq 7 -and $result.Detail -eq 'synthetic-management-failure') 'exit code and stderr must survive'
    $result = Test-Child '[Console]::Out.Write(("x"*100000)); [Console]::Error.Write(("y"*100000)); exit 0'
    Assert-Gse ($result.Success -and $result.Detail.Length -eq 2000) 'both full pipes must drain with bounded diagnostic'
    $result = Test-Child 'if ([Console]::ReadLine() -ne "small JSON input") {exit 9}' -InputText 'small JSON input'
    Assert-Gse $result.Success 'stdin must reach child unchanged'
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $result = Test-Child 'Start-Sleep -Seconds 30' -Timeout 1
    Assert-Gse (-not $result.Success -and $result.Code -eq 'TIMEOUT' -and $watch.Elapsed.TotalSeconds -lt 10) 'hung management child must stop promptly'
    Write-Host 'PASS native child error, full pipes, input and timeout'

    $script:tries = 0; $script:messages = @(); $script:sleeps = 0
    function Write-GseMonitorMessage($Level,$Message) { $script:messages += "$Level $Message" }
    function Start-Sleep($Seconds) { $script:sleeps++ }
    function Publish-GseHostSpace { $script:tries++; if ($script:tries -lt 3) {throw 'synthetic exit=7'}; return 86.2 }
    Assert-Gse (Invoke-GseMonitorCycle) 'transient publication failure must recover'
    Assert-Gse ($script:tries -eq 3 -and $script:sleeps -eq 2) 'retry count must be bounded'
    $script:tries = 0
    function Publish-GseHostSpace { $script:tries++; throw 'persistent synthetic failure' }
    Assert-Gse (-not (Invoke-GseMonitorCycle)) 'persistent failure must return a warning result'
    Assert-Gse ($script:tries -eq 3) 'persistent failure must stop retrying this cycle'
    function Publish-GseHostSpace {return 1.0}
    Assert-Gse (Invoke-GseMonitorCycle) 'following cycle must recover and low space is advisory'
    Assert-Gse (($script:messages -join ' ') -match 'below 20 GiB') 'low space warning'
    Write-Host 'PASS transient, exhausted and next-cycle recovery'

    # Run the real outer loop; stop at a synthetic caller interruption after a
    # failed periodic cycle. Wakefulness must remain on until that interruption.
    $script:cycles = 0; $script:wakes = @(); $script:starts = 0
    function New-Item {return $null}
    function Set-GseWakefulness($Enabled) { $script:wakes += $Enabled }
    function Invoke-GseWsl {return [pscustomobject]@{Success=$true}}
    function Start-GseKeeper {
        $script:starts++
        $p = [pscustomobject]@{HasExited=$false}
        $p | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
        return $p
    }
    function Invoke-GseMonitorCycle {
        $script:cycles++
        if ($script:cycles -eq 1) {return $true}
        Assert-Gse ($script:wakes.Count -eq 1 -and $script:wakes[0]) 'periodic failures must keep wakefulness'
        if ($script:cycles -eq 2) {return $false}
        throw 'synthetic caller stop'
    }
    try { Start-GseRunner; throw 'loop unexpectedly returned' }
    catch { Assert-Gse ($_.Exception.Message -eq 'synthetic caller stop') 'loop must continue past failed cycle' }
    Assert-Gse ($script:cycles -eq 3 -and $script:starts -eq 1) 'service/keeper must not be restarted on publication failure'
    Assert-Gse ($script:wakes.Count -eq 2 -and -not $script:wakes[1]) 'caller exit must release wakefulness'
    $script:wakes = @(); $script:starts = 0
    function Invoke-GseMonitorCycle {return $false}
    try { Start-GseRunner; throw 'initial failure unexpectedly admitted' }
    catch { Assert-Gse ($_.Exception.Message -like 'Initial disk publication failed*') 'startup still requires fresh telemetry' }
    Assert-Gse ($script:starts -eq 0 -and $script:wakes.Count -eq 2) 'failed startup must clean up without keeper'
    Write-Host 'PASS outer loop wakefulness, cleanup and startup guard'
    Write-Host 'v52WindowsLauncherTests=PASS'
} finally {
    $env:WSLENV = $oldWslenv
    Set-Item function:Publish-GseHostSpace $oldPublish
    Set-Item function:Write-GseMonitorMessage $oldMessage
    Set-Item function:Invoke-GseMonitorCycle $oldCycle
    Set-Item function:Invoke-GseWsl $oldInvoke
    Set-Item function:Start-GseKeeper $oldKeeper
    Set-Item function:Set-GseWakefulness $oldWake
    Remove-Item function:Start-Sleep,function:New-Item -ErrorAction SilentlyContinue
}
