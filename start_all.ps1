$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPython = Join-Path $root '.venv\Scripts\python.exe'
$frontendDir = Join-Path $root 'frontend'
$frontendPort = 3001

if (-not (Test-Path $backendPython)) {
    throw "Virtual environment not found at '$backendPython'."
}

if (-not (Test-Path (Join-Path $frontendDir 'package.json'))) {
    throw "Frontend directory not found at '$frontendDir'."
}

Get-ChildItem -Path (Join-Path $root 'src') -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path (Join-Path $root 'tests') -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

function Stop-PortListener {
    param(
        [int]$Port
    )

    $pids = netstat -ano | Select-String -Pattern (":$Port .*LISTENING") | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') {
            [int]$Matches[1]
        }
    }

    foreach ($processId in ($pids | Select-Object -Unique)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ProcessTree {
    param(
        [int]$ProcessId
    )

    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ProcessId }
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-ProcessesByCommandLinePattern {
    param(
        [string]$Pattern
    )

    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern } |
        ForEach-Object {
            Stop-ProcessTree -ProcessId $_.ProcessId
        }
}

Stop-ProcessesByCommandLinePattern 'uvicorn.*vigilador_tecnologico\.api\.main:app'
Stop-ProcessesByCommandLinePattern 'spawn_main'
Stop-ProcessesByCommandLinePattern 'next dev'
Stop-ProcessesByCommandLinePattern 'npm-cli\.js.*run dev'
Stop-PortListener -Port 8000
Stop-PortListener -Port $frontendPort
Start-Sleep -Seconds 2

Start-Process -FilePath $backendPython -ArgumentList @(
    '-m', 'uvicorn',
    'vigilador_tecnologico.api.main:app',
    '--host', '0.0.0.0',
    '--port', '8000'
) -WorkingDirectory $root -WindowStyle Minimized

Start-Process -FilePath 'npm.cmd' -ArgumentList @(
    'run', 'dev', '--', '--port', "$frontendPort", '--hostname', '127.0.0.1'
) -WorkingDirectory $frontendDir -WindowStyle Hidden

Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Frontend: http://127.0.0.1:$frontendPort"
