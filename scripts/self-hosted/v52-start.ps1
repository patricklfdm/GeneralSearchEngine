# Windows PowerShell 5.1. Dot-source for tests; -CheckOnly publishes one observation
# without starting the service. Ordinary use keeps wakefulness until Ctrl+C.
[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$script:GseMonitorLog = $null

function Write-GseMonitorMessage {
    param([string]$Level, [string]$Message)
    $stamp = [DateTimeOffset]::UtcNow.ToString('o')
    Write-Host "$stamp [$Level] $Message"
    if ($script:GseMonitorLog) {
        try {
            @{time=$stamp; level=$Level; message=$Message} | ConvertTo-Json -Compress |
                Add-Content -LiteralPath $script:GseMonitorLog -Encoding UTF8
        } catch { Write-Warning 'Monitor log could not be written; monitoring continues.' }
    }
}

function New-GseWslStartInfo {
    param([string]$Arguments)
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = Join-Path $env:SystemRoot 'System32\wsl.exe'
    $info.Arguments = '-d GSE-Runner --cd / ' + $Arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WorkingDirectory = $env:SystemRoot
    # No cross-distro VS Code paths are needed by these fixed management calls.
    # Only this child's environment changes; automount/interop stay disabled.
    $info.EnvironmentVariables['WSLENV'] = ''
    return $info
}

function Invoke-GseWsl {
    param([System.Diagnostics.ProcessStartInfo]$Info, [string]$InputText = '',
          [ValidateRange(1,120)][int]$TimeoutSeconds = 20)
    $Info.RedirectStandardInput = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $Info
    try {
        $null = $process.Start()
        # Drain both pipes concurrently; a diagnostic must not deadlock publication.
        $out = $process.StandardOutput.ReadToEndAsync()
        $err = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.WriteLine($InputText)
        $process.StandardInput.Close()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            # Kill only our management client, never the distro, service or workload.
            $process.Kill()
            $null = $process.WaitForExit(3000)
            return [pscustomobject]@{Success=$false; Code='TIMEOUT'; ExitCode=$null; Detail='WSL management call timed out'}
        }
        if (-not ($out.Wait(3000) -and $err.Wait(3000))) {
            return [pscustomobject]@{Success=$false; Code='PIPE_TIMEOUT'; ExitCode=$process.ExitCode; Detail='WSL diagnostic pipe did not close'}
        }
        $detail = $err.Result.Trim()
        if ($detail.Length -gt 2000) { $detail = $detail.Substring(0,2000) }
        return [pscustomobject]@{Success=($process.ExitCode -eq 0); Code='EXIT'; ExitCode=$process.ExitCode; Detail=$detail}
    } catch {
        return [pscustomobject]@{Success=$false; Code='PROCESS_ERROR'; ExitCode=$null; Detail=$_.Exception.GetType().Name}
    } finally {
        # A broken stdin pipe/startup exception must not leak a management client.
        try { if (-not $process.HasExited) { $process.Kill(); $null = $process.WaitForExit(3000) } } catch {}
        $process.Dispose()
    }
}

function Publish-GseHostSpace {
    $disk = Get-PSDrive D
    $value = @{drive='D:'; freeBytes=[long]$disk.Free; totalBytes=[long]($disk.Free+$disk.Used)} | ConvertTo-Json -Compress
    # Timestamp at receipt on Linux: freshness checks use that same Linux clock.
    # Each writer has its own temporary file if a timed-out client exits late.
    $publish = @'
import json,os,sys,tempfile,time
from pathlib import Path
v=json.load(sys.stdin)
if set(v)!={'drive','freeBytes','totalBytes'} or v['drive']!='D:' or any(type(v[k]) is not int for k in ('freeBytes','totalBytes')) or not 0<=v['freeBytes']<=v['totalBytes']:
    raise ValueError('invalid host space observation')
v['checkedAt']=int(time.time())
p=Path('/run/gse-runner');p.mkdir(mode=0o755,exist_ok=True)
fd,name=tempfile.mkstemp(prefix='host-space-',dir=p)
try:
    with os.fdopen(fd,'w') as f: json.dump(v,f)
    os.chmod(name,0o644);os.replace(name,p/'host-space.json')
finally:
    Path(name).unlink(missing_ok=True)
'@
    # Base64 carries fixed reviewed code, not credentials; avoid nested Windows /
    # Python quoting and do not depend on the caller's UNC working directory.
    $code = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($publish))
    $info = New-GseWslStartInfo ('-u root --exec /usr/bin/python3 -c "import base64;exec(base64.b64decode(''' + $code + '''))"')
    $result = Invoke-GseWsl -Info $info -InputText $value
    if (-not $result.Success) {
        throw ('publish code={0} exit={1}: {2}' -f $result.Code,$result.ExitCode,$result.Detail)
    }
    if ($result.Detail) { Write-GseMonitorMessage 'WARNING' $result.Detail }
    return ($disk.Free / 1GB)
}

function Invoke-GseMonitorCycle {
    # Bounded retries per observation, followed by the next monitoring interval.
    # This retries only telemetry, never an experiment or a GitHub workflow.
    for ($attempt=1; $attempt -le 3; $attempt++) {
        try {
            $free = Publish-GseHostSpace
            Write-GseMonitorMessage 'INFO' ('D: free={0:N2} GiB' -f $free)
            if ($free -lt 20) { Write-GseMonitorMessage 'WARNING' 'D: below 20 GiB free. Experiment is not interrupted.' }
            return $true
        } catch {
            Write-GseMonitorMessage 'WARNING' ('Disk publication attempt {0}/3 failed: {1}' -f $attempt,$_.Exception.Message)
            if ($attempt -lt 3) { Start-Sleep -Seconds 2 }
        }
    }
    Write-GseMonitorMessage 'WARNING' 'Disk monitor unavailable. Keep this window open; wakefulness remains requested. A new job requires fresh telemetry.'
    return $false
}

function Start-GseKeeper {
    $info = New-GseWslStartInfo '-u gse-runner --exec /bin/sleep infinity'
    return [System.Diagnostics.Process]::Start($info)
}

function Set-GseWakefulness {
    param([bool]$Enabled)
    if (-not ('GseRunnerAwake' -as [type])) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GseRunnerAwake {
  [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
}
'@
    }
    $flags = if ($Enabled) { [uint32]2147483649 } else { [uint32]2147483648 }
    if ([GseRunnerAwake]::SetThreadExecutionState($flags) -eq 0) { throw 'Windows wakefulness request failed' }
}

function Start-GseRunner {
    param([switch]$CheckOnly)
    $mutex = New-Object System.Threading.Mutex($false, 'Local\GSEV52RunnerLauncher')
    $owned = $false; $awake = $false; $keeper = $null
    try {
        try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
        if (-not $owned) { throw 'GSE Runner launcher is already running' }
        $logs = 'D:\GSE-Runner\monitor-logs'
        $null = New-Item -ItemType Directory -Path $logs -Force
        $script:GseMonitorLog = Join-Path $logs ((Get-Date -Format 'yyyyMMddTHHmmss') + "-$PID.jsonl")
        if ($CheckOnly) {
            if (-not (Invoke-GseMonitorCycle)) { throw 'Disk monitor check failed; inspect monitor-logs' }
            return
        }
        Set-GseWakefulness $true; $awake = $true
        if (-not (Invoke-GseMonitorCycle)) { throw 'Initial disk publication failed; service was not started by this launcher' }
        $info = New-GseWslStartInfo '-u root --exec /usr/bin/systemctl start actions.runner.patricklfdm-GeneralSearchEngine.gse-v52-cloud-d-wsl.service'
        $result = Invoke-GseWsl -Info $info -TimeoutSeconds 60
        if (-not $result.Success) { throw ('Runner service start code={0} exit={1}: {2}' -f $result.Code,$result.ExitCode,$result.Detail) }
        Write-GseMonitorMessage 'INFO' 'Keep this window open during experiments. Ctrl+C exits only the launcher. Log contains management diagnostics, not job output.'
        while ($true) {
            try {
                if ($null -eq $keeper -or $keeper.HasExited) {
                    if ($keeper) { $keeper.Dispose() }
                    $keeper = $null
                    $keeper = Start-GseKeeper
                }
            } catch { Write-GseMonitorMessage 'WARNING' 'WSL keepalive could not start; wakefulness remains requested. Will retry next interval.' }
            Start-Sleep -Seconds 60
            $null = Invoke-GseMonitorCycle
        }
    } finally {
        if ($awake) {
            try { Set-GseWakefulness $false } catch { Write-Warning 'Unable to release Windows wakefulness request.' }
        }
        # Do not forcibly stop any Linux process, even when the user closes this window.
        if ($keeper) { $keeper.Dispose() }
        if ($owned) {
            if ($awake) { Write-Host 'Wakefulness request released. Runner service was not forcibly stopped; check Actions before shutting down.' }
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') { Start-GseRunner -CheckOnly:$CheckOnly }
