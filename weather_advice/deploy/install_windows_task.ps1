<#
    Register the nightly window check on Windows.

    Modelled on mtgdeals/deploy/install_windows_task.ps1, and it exists for the
    same reason that one does. The deal tracker was once found CONFIGURED,
    BELIEVED LIVE, AND NOT RUNNING. A window advisor you have to remember to
    run is not an advisor, it is a command -- and the night you forget is the
    night you wanted it.

    Registers a Scheduled Task that runs `check` three times in the evening:
    8pm, 9pm and 10pm. Three runs, not one, because the forecast MOVES: being
    told "open them" at 8pm and never hearing about the rain that appeared in
    the 10pm forecast is the failure mode worth spending two extra runs on.
    Re-alerting is guarded in the program, not here -- an unchanged verdict
    stays quiet, and only a CHANGED one sends again.

    Runs under pythonw.exe so no console window appears, and only while you
    are logged on -- deliberately, because the alternative stores a password
    and nothing here is worth that.

    Idempotent: re-running replaces the task rather than duplicating it.

    Install:   powershell -ExecutionPolicy Bypass -File deploy\install_windows_task.ps1
    Remove:    powershell -ExecutionPolicy Bypass -File deploy\install_windows_task.ps1 -Uninstall
    Inspect:   Get-ScheduledTask weather-advice | Get-ScheduledTaskInfo
#>

param(
    [switch]$Uninstall,
    [string]$TaskName = "weather-advice",
    [string[]]$RunAt = @("20:00", "21:00", "22:00"),
    [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "removed scheduled task '$TaskName'"
    } catch {
        Write-Host "no scheduled task '$TaskName' to remove"
    }
    return
}

# Resolve the interpreter the way Python itself reports it. `where python` can
# return a Windows Store *alias* that resolves interactively and then fails
# under a scheduled task -- a difference that shows up only as a task that
# silently never runs.
$python = & python -c "import sys; print(sys.executable)"
if (-not $python -or -not (Test-Path $python)) {
    throw "could not resolve a python interpreter"
}
$pythonw = $python -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }

if (-not (Test-Path (Join-Path $ProjectDir "weather_advice\__main__.py"))) {
    throw "no weather_advice package under $ProjectDir"
}

# Prove it runs BEFORE scheduling it. A task that fails on first launch looks
# identical to a task that was never registered. Run it FROM $ProjectDir so
# the check does not depend on the caller's current directory.
Write-Host "checking the package imports..." -NoNewline
Push-Location $ProjectDir
try {
    & $python -c "import weather_advice" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "weather_advice failed to import under $python" }
} finally {
    Pop-Location
}
Write-Host " ok"

# And prove it is actually configured to tell you something. `doctor` exits
# non-zero when there is no way to send an alert; scheduling a task that can
# only ever talk to itself is the exact trap this script is guarding.
Write-Host "checking the alert setup..."
Push-Location $ProjectDir
try {
    & $python -m weather_advice doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "doctor reported problems (above). The task will still be"
        Write-Host "registered, but FIX THESE or it will decide correctly every"
        Write-Host "night and never manage to tell you."
    }
} finally {
    Pop-Location
}

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "-m weather_advice check" -WorkingDirectory $ProjectDir

$triggers = @()
foreach ($t in $RunAt) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $t
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
        -Settings $settings -Description "Nightly open-the-windows check" `
        -Force -ErrorAction Stop | Out-Null
    Write-Host ""
    Write-Host "registered scheduled task '$TaskName'"
    Write-Host "  interpreter : $pythonw"
    Write-Host "  working dir : $ProjectDir"
    Write-Host "  runs at     : $($RunAt -join ', ') daily"
    Write-Host ""
    Write-Host "Test it now without waiting for 8pm:"
    Write-Host "  python -m weather_advice preview"
}
catch {
    # Registering a task needs an elevated shell on some machines. Unlike the
    # deal tracker there is no Startup-folder fallback worth having here: this
    # is a TIMED job, and a shortcut that fires at logon would check the
    # forecast whenever you happened to log in, which is not the same thing
    # and would quietly be wrong.
    Write-Host ""
    Write-Host "Scheduled task registration was denied (needs an elevated shell)."
    Write-Host "Re-run this script from an ADMIN PowerShell."
    Write-Host ""
    Write-Host "There is no non-admin fallback on purpose: this job has to run"
    Write-Host "at a particular TIME of evening, and a logon-triggered"
    Write-Host "shortcut would check the forecast at whatever hour you signed"
    Write-Host "in -- which looks like it is working and is not."
    throw
}

Write-Host "It does NOT run while logged out - that would need a stored password."
