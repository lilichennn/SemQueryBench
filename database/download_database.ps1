$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ZipName = "SemQueryBench_database_full.zip"
$DownloadUrl = "https://github.com/lilichennn/SemQueryBench/releases/latest/download/SemQueryBench_database_full.zip"
$ZipPath = Join-Path $RepoRoot $ZipName
$DatabaseFullPath = Join-Path $RepoRoot "database\full"

Write-Host "Downloading SemQueryBench full database package..."
Write-Host "URL: $DownloadUrl"

Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath

Write-Host "Download completed: $ZipPath"

Write-Host "Extracting database package..."
Expand-Archive -Path $ZipPath -DestinationPath $RepoRoot -Force

if (Test-Path $DatabaseFullPath) {
    Write-Host "Database files are ready at: $DatabaseFullPath"
} else {
    Write-Host "Warning: database\full was not found after extraction."
    Write-Host "Please check the archive structure."
}

Write-Host "Done."