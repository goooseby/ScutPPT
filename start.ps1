$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Missing .venv. Follow README.md to install the project environment first.'
}
& $projectPython (Join-Path $PSScriptRoot 'app.py')
exit $LASTEXITCODE
