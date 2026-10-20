<#
.SYNOPSIS
  Start Floppy Image Mounter elevated at logon WITHOUT a UAC prompt each time.

.DESCRIPTION
  A program that requires administrator rights cannot be launched from the normal
  Startup folder / Run key without a UAC prompt. A scheduled task with "Run with
  highest privileges" can. Run this script once from an elevated PowerShell.

.EXAMPLE
  .\startup-task.ps1                          # install, using FloppyMounter.exe next to this script
  .\startup-task.ps1 -ExePath "C:\Tools\FloppyMounter.exe"
  .\startup-task.ps1 -Remove                  # uninstall the task
#>
param(
    [string]$ExePath = (Join-Path $PSScriptRoot "FloppyMounter.exe"),
    [switch]$Visible,      # show the window at logon instead of starting in the tray
    [switch]$Remove
)

$TaskName = "FloppyImageMounter"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run this script from an elevated (Administrator) PowerShell."
    exit 1
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'."
    exit 0
}

if (-not (Test-Path $ExePath)) {
    Write-Error "Executable not found: $ExePath"
    exit 1
}
$ExePath = (Resolve-Path $ExePath).Path

$arguments = if ($Visible) { "" } else { "--hidden" }
$action    = New-ScheduledTaskAction -Execute $ExePath -Argument $arguments -WorkingDirectory (Split-Path $ExePath)
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Installed scheduled task '$TaskName' for $($identity.Name). It will start at next logon."
