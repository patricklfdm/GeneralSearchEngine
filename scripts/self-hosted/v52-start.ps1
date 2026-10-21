# Run in Windows PowerShell. Keeps only the dedicated distro alive and requests
# system wakefulness while this launcher is open; no permanent power-plan change.
$ErrorActionPreference = 'Stop'
$mutex = New-Object System.Threading.Mutex($false, 'Local\GSEV52RunnerLauncher')
if (-not $mutex.WaitOne(0)) { throw 'GSE Runner launcher is already running' }
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class GseRunnerAwake {
  [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
}
'@
$null = [GseRunnerAwake]::SetThreadExecutionState([uint32]2147483649)
try {
    $publish = "import json,sys; from pathlib import Path; v=json.load(sys.stdin); assert set(v)=={'drive','freeBytes','totalBytes','checkedAt'} and v['drive']=='D:'; p=Path('/run/gse-runner'); p.mkdir(mode=0o755,exist_ok=True); t=p/'host-space.tmp'; t.write_text(json.dumps(v)); t.chmod(0o644); t.replace(p/'host-space.json')"
    function Publish-HostSpace {
        $disk = Get-PSDrive D
        $value = @{drive='D:'; freeBytes=[long]$disk.Free; totalBytes=[long]($disk.Free+$disk.Used); checkedAt=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()} | ConvertTo-Json -Compress
        $value | & wsl.exe -d GSE-Runner -u root --cd / --exec /usr/bin/python3 -c $publish
        if ($LASTEXITCODE -ne 0) { throw 'Unable to publish D-drive space to the Runner' }
        return ($disk.Free / 1GB)
    }
    $null = Publish-HostSpace
    & wsl.exe -d GSE-Runner -u root --cd / --exec /bin/bash -lc 'set -e; cd /home/gse-runner/actions-runner; ./svc.sh start'
    if ($LASTEXITCODE -ne 0) { throw 'Runner service failed to start' }
    # systemd alone does not keep a WSL instance running.
    $keeper = Start-Process wsl.exe -ArgumentList '-d GSE-Runner -u gse-runner --cd / --exec /bin/sleep infinity' -PassThru -WindowStyle Hidden
    Write-Host 'GSE Runner is starting. Keep this window open during experiments. Ctrl+C exits the launcher.'
    while (-not $keeper.HasExited) {
        $free = Publish-HostSpace
        Write-Host ((Get-Date -Format o) + ' D: free=' + [math]::Round($free, 2) + ' GiB')
        if ($free -lt 20) { Write-Warning 'D: below 20 GiB free. Experiment is not interrupted.' }
        Start-Sleep -Seconds 60
        $keeper.Refresh()
    }
} finally {
    $null = [GseRunnerAwake]::SetThreadExecutionState([uint32]2147483648)
    Write-Host 'Wakefulness request released. Runner service was not forcibly stopped; check Actions before shutting down.'
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
