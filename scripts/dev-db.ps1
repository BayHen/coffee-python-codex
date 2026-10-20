$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$dataPath = Join-Path $repositoryRoot ".local_pg_eval\data"
$logDirectory = Join-Path $repositoryRoot ".local_pg_eval"
$postgres = "C:\Program Files\PostgreSQL\18\bin\postgres.exe"
$pgIsReady = "C:\Program Files\PostgreSQL\18\bin\pg_isready.exe"
$port = 55433

if (-not (Test-Path -LiteralPath $dataPath)) {
    throw "Local development cluster is missing at $dataPath."
}
if (-not (Test-Path -LiteralPath $postgres)) {
    throw "PostgreSQL 18 is not installed at $postgres."
}

& $pgIsReady -h 127.0.0.1 -p $port *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Output "Development PostgreSQL is already running on port $port."
    exit 0
}

$stdout = Join-Path $logDirectory "dev-55433.out.log"
$stderr = Join-Path $logDirectory "dev-55433.err.log"
Start-Process `
    -FilePath $postgres `
    -ArgumentList @("-D", $dataPath, "-p", "$port") `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    & $pgIsReady -h 127.0.0.1 -p $port *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Development PostgreSQL is ready on port $port."
        exit 0
    }
}

throw "PostgreSQL did not become ready. Check $stderr."
