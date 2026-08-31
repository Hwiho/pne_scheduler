# PowerShell wrapper: enable WSL (if needed) and run Cursor Cloud setup.
# Usage (Admin PowerShell, first time): .\scripts\setup_cursor_cloud.ps1
# After reboot: .\scripts\setup_cursor_cloud.ps1 -SkipWslInstall

param(
    [switch]$SkipWslInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WslScript = Join-Path $RepoRoot "scripts\setup_cursor_cloud.sh"

function Test-WslReady {
    try {
        $out = wsl -e echo ok 2>&1
        return ($LASTEXITCODE -eq 0) -and ($out -match "ok")
    } catch {
        return $false
    }
}

if (-not $SkipWslInstall) {
    Write-Host "==> Checking WSL..."
    if (-not (Test-WslReady)) {
        Write-Host "WSL not ready. Enabling Windows features..."
        $features = @(
            "Microsoft-Windows-Subsystem-Linux",
            "VirtualMachinePlatform"
        )
        foreach ($f in $features) {
            $state = (Get-WindowsOptionalFeature -Online -FeatureName $f).State
            if ($state -ne "Enabled") {
                Write-Host "  Enabling $f ..."
                dism.exe /online /enable-feature /featurename:$f /all /norestart | Out-Null
            }
        }
        Write-Host "==> Installing WSL + Ubuntu (if missing)..."
        winget install --id Microsoft.WSL --accept-package-agreements --accept-source-agreements 2>$null
        wsl --install -d Ubuntu --no-launch 2>$null
        if (-not (Test-WslReady)) {
            Write-Host ""
            Write-Host "REBOOT REQUIRED before WSL can run." -ForegroundColor Yellow
            Write-Host "After reboot, run:"
            Write-Host "  cd $RepoRoot"
            Write-Host "  .\scripts\setup_cursor_cloud.ps1 -SkipWslInstall"
            Write-Host ""
            $reboot = Read-Host "Reboot now? (y/N)"
            if ($reboot -eq "y" -or $reboot -eq "Y") {
                Restart-Computer
            }
            exit 0
        }
    }
}

Write-Host "==> Running Cursor Cloud setup in WSL..."
$WslPath = "/mnt/c" + ($RepoRoot -replace '\\', '/' -replace ':', '')
wsl -e bash -lc "cd '$WslPath' && sed -i 's/\r$//' scripts/setup_cursor_cloud.sh && bash scripts/setup_cursor_cloud.sh"
