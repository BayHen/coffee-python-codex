$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repositoryRoot ".env"

if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([^#][^=]*)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

if (-not $env:DATABASE_URL) {
    throw "DATABASE_URL is not configured. Add it to .env or the current process."
}
if (-not $env:JWT_SECRET_KEY) {
    throw "JWT_SECRET_KEY is not configured. Add it to .env or the current process."
}

$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
& $python -m uvicorn app.main:app --app-dir (Join-Path $repositoryRoot "backend") --reload
exit $LASTEXITCODE
