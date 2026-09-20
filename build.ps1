$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath .\release .\Keye.spec
if ($LASTEXITCODE -ne 0) { throw '课页打包失败。' }
Copy-Item -LiteralPath .\README.md -Destination .\release\课页\使用说明.md -Force
$archive = Join-Path $projectRoot 'release\课页-Windows-x64.zip'
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path .\release\课页\* -DestinationPath $archive -CompressionLevel Optimal
Write-Host "打包完成：$projectRoot\release\课页\Keye.exe"
Write-Host "分享文件：$archive"
