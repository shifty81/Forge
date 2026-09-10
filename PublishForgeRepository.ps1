[CmdletBinding()]
param(
    [string]$Repository = 'https://github.com/shifty81/Forge.git',
    [string]$Branch = 'main'
)
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) { $Python = @('py.exe','-3') }
elseif (Get-Command python.exe -ErrorAction SilentlyContinue) { $Python = @('python.exe') }
if (-not $Python) { throw 'Python 3.11+ is required.' }
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw 'Git is required.' }

Write-Host '========================================================================'
Write-Host ' FORGE CANONICAL REPOSITORY REPLACEMENT'
Write-Host '========================================================================'
Write-Host " Source     : $Source"
Write-Host " Repository : $Repository"
Write-Host " Branch     : $Branch"
Write-Host '------------------------------------------------------------------------'
Write-Host 'This replaces the CURRENT repository tree. Existing Git history remains in'
Write-Host 'the repository behind the new commit, but all old working-tree content is'
Write-Host 'removed from the new main tree.'
$answer = Read-Host 'Type OVERWRITE to continue'
if ($answer -cne 'OVERWRITE') { Write-Host '[INFO] Cancelled.'; exit 2 }

Push-Location $Source
try {
    if ($Python.Count -eq 2) { & $Python[0] $Python[1] 'tools/ForgeGate.py' 'full' }
    else { & $Python[0] 'tools/ForgeGate.py' 'full' }
    if ($LASTEXITCODE -ne 0) { throw "Forge Full Gate failed with exit $LASTEXITCODE; publication blocked." }
} finally { Pop-Location }

$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ('forge-publish-' + [guid]::NewGuid().ToString('N'))
$Clone = Join-Path $TempRoot 'Forge'
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
try {
    & git clone --branch $Branch --single-branch $Repository $Clone
    if ($LASTEXITCODE -ne 0) { throw "git clone failed with exit $LASTEXITCODE" }

    Get-ChildItem -LiteralPath $Clone -Force | Where-Object { $_.Name -ne '.git' } | Remove-Item -Recurse -Force
    $excludeTop = @('.git','__pycache__','artifacts','.project_control','.project-control')
    Get-ChildItem -LiteralPath $Source -Force | Where-Object { $excludeTop -notcontains $_.Name } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Clone -Recurse -Force
    }
    Get-ChildItem -LiteralPath $Clone -Directory -Recurse -Force -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $Clone -File -Recurse -Force -Include '*.pyc','*.pyo' | Remove-Item -Force -ErrorAction SilentlyContinue

    Push-Location $Clone
    try {
        & git add -A
        if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
        $status = (& git status --porcelain=v1) -join "`n"
        if ([string]::IsNullOrWhiteSpace($status)) { Write-Host '[PASS] GitHub already matches this Forge source.'; exit 0 }
        & git commit -m 'Forge 0.4.5-F60R5 certified universal control center baseline'
        if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
        & git push origin $Branch
        if ($LASTEXITCODE -ne 0) { throw 'git push failed' }
        Write-Host '[PASS] shifty81/Forge now contains the certified Forge source.' -ForegroundColor Green
    } finally { Pop-Location }
} finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
