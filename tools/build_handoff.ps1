Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Out = Join-Path $Root "_handoff"
$Stage = Join-Path $Out "wavervanir-platform-handoff"
$Zip = Join-Path $Out "wavervanir-platform-handoff.zip"

function Say([string]$Message) {
    Write-Host "[handoff] $Message"
}

function Fail([string]$Message) {
    throw "[handoff] FAIL: $Message"
}

function Copy-RepoFile([string]$RelativePath) {
    $Source = Join-Path $Root $RelativePath
    $Target = Join-Path $Stage $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
}

function Copy-RepoDir([string]$RelativePath) {
    $Source = Join-Path $Root $RelativePath
    $Target = Join-Path $Stage $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Recurse -Force
}

function Get-TextFiles([string]$Path) {
    Get-ChildItem -LiteralPath $Path -Recurse -File -Force |
        Where-Object {
            $_.FullName -notmatch "\\(\.git|node_modules|\.venv|__pycache__|\.pytest_cache|dist|_handoff)(\\|$)" -and
            $_.Extension -in @(".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml", ".md", ".yml", ".yaml", ".html", ".css", ".example", ".txt", "")
        }
}

Set-Location $Root

Say "building landing"
Push-Location (Join-Path $Root "landing")
npm run test
npm run build
Pop-Location

Say "running source scans"
$SecretPattern = "sk_live_[A-Za-z0-9]+|whsec_live_[A-Za-z0-9]+|TASTYTRADE_REFRESH_TOKEN=[^\sR]+|TELEGRAM_BOT_TOKEN=[0-9]+|OPENAI_API_KEY=sk-[A-Za-z0-9]+"
$SecretHits = Get-TextFiles $Root | Select-String -Pattern $SecretPattern
if ($SecretHits) {
    $SecretHits | ForEach-Object { Write-Error $_.ToString() }
    Fail "secret-shaped values found"
}

$ImportPattern = "^\s*(from|import)\s+\S*(VOLANX|volanx|tastytrade|tastyworks|ib_insync|ibapi|alpaca_trade_api|broker_router|order_spec|place_order)"
$ImportHits = Get-TextFiles $Root |
    Where-Object { $_.Name -ne "test_no_private_imports.py" } |
    Select-String -Pattern $ImportPattern
if ($ImportHits) {
    $ImportHits | ForEach-Object { Write-Error $_.ToString() }
    Fail "forbidden private/broker imports found"
}

$Dist = Join-Path $Root "landing\dist"
$BundleHits = Get-ChildItem -LiteralPath $Dist -Recurse -File |
    Select-String -Pattern "sk_(test|live)_|whsec_" -ErrorAction SilentlyContinue
if ($BundleHits) {
    $BundleHits | ForEach-Object { Write-Error $_.ToString() }
    Fail "secret-shaped values found in landing/dist"
}

Say "staging package"
if (Test-Path $Out) {
    Remove-Item -LiteralPath $Out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-RepoFile "README.md"
Copy-RepoFile "LICENSE"
Copy-RepoDir "docs"
Copy-RepoDir ".github"

Copy-RepoFile "api\README.md"
Copy-RepoFile "api\pyproject.toml"
Copy-RepoFile "api\.env.example"
Copy-RepoDir "api\src"
Copy-RepoDir "api\tests"

Copy-RepoFile "landing\README.md"
Copy-RepoFile "landing\package.json"
Copy-RepoFile "landing\package-lock.json"
Copy-RepoFile "landing\tsconfig.json"
Copy-RepoFile "landing\vite.config.ts"
Copy-RepoFile "landing\postcss.config.cjs"
Copy-RepoFile "landing\index.html"
Copy-RepoFile "landing\.env.example"
Copy-RepoDir "landing\public"
Copy-RepoDir "landing\src"
Copy-RepoDir "landing\tests"
Copy-RepoDir "landing\dist"

Say "removing generated cache directories from staged package"
Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Force |
    Where-Object { $_.Name -in @("node_modules", ".venv", "__pycache__", ".pytest_cache") } |
    Sort-Object FullName -Descending |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

Say "verifying excluded content"
$ForbiddenDirs = Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Force |
    Where-Object { $_.Name -in @(".git", "node_modules", ".venv", "__pycache__", ".pytest_cache") }
if ($ForbiddenDirs) {
    $ForbiddenDirs | ForEach-Object { Write-Error $_.FullName }
    Fail "excluded directory found in staged package"
}

$ForbiddenFiles = Get-ChildItem -LiteralPath $Stage -Recurse -File -Force |
    Where-Object { $_.Name -eq ".env" -or $_.Name -match "\.sqlite($|-)|\.sqlite3$|\.db$|\.sqlite-shm$|\.sqlite-wal$" }
if ($ForbiddenFiles) {
    $ForbiddenFiles | ForEach-Object { Write-Error $_.FullName }
    Fail "excluded local state file found in staged package"
}

$FileCount = (Get-ChildItem -LiteralPath $Stage -Recurse -File -Force | Measure-Object).Count
$Commit = (git rev-parse HEAD).Trim()
$GeneratedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$Manifest = @"
{
  "package": "wavervanir-platform-handoff",
  "source_commit": "$Commit",
  "generated_at_utc": "$GeneratedAt",
  "file_count": $FileCount,
  "scans": {
    "source_secrets": "clean",
    "bundle_secrets": "clean",
    "private_imports": "clean"
  }
}
"@
Set-Content -LiteralPath (Join-Path $Stage "MANIFEST.json") -Value $Manifest -Encoding UTF8

Say "creating zip"
if (Test-Path $Zip) {
    Remove-Item -LiteralPath $Zip -Force
}
Compress-Archive -Path $Stage -DestinationPath $Zip -Force

if (-not (Test-Path $Zip)) {
    Fail "zip was not produced"
}

$Size = (Get-Item -LiteralPath $Zip).Length
Say "done: $Zip"
Say "files: $FileCount"
Say "size: $Size bytes"
