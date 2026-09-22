$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath .\release .\Keye.spec
if ($LASTEXITCODE -ne 0) { throw '课页打包失败。' }
Copy-Item -LiteralPath .\README.md -Destination .\release\课页\使用说明.md -Force
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name KeyeUpdater --distpath .\build\updater-dist --workpath .\build\updater-work --specpath .\build\updater-spec .\updater_entry.py
if ($LASTEXITCODE -ne 0) { throw '课页更新助手打包失败。' }
Copy-Item -LiteralPath .\build\updater-dist\KeyeUpdater.exe -Destination .\release\课页\KeyeUpdater.exe -Force
$previous = Join-Path $projectRoot 'release\previous'
$updateArgs = @('.\tools\build_update.py', '.\release\课页', '.\release')
if (Test-Path -LiteralPath (Join-Path $previous 'update-manifest.json')) {
    $updateArgs += @('--previous', $previous)
}
& .\.venv\Scripts\python.exe @updateArgs
if ($LASTEXITCODE -ne 0) { throw '课页更新资源生成失败。' }
Write-Host "打包完成：$projectRoot\release\课页\Keye.exe"
Write-Host "分享文件：$projectRoot\release\Keye-Windows-x64.zip"
