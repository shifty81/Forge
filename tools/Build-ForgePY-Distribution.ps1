param(
    [switch]$SkipInstaller,
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
$Cli = Join-Path $Root "app\ForgeUnifiedCli.py"

if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $Args = @("-3", $Cli, "executable", "build", "--root", $Root)
    if ($SkipInstaller) { $Args += "--skip-installer" }
    & py.exe @Args
    exit $LASTEXITCODE
}

if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
    throw "Python 3 was not found."
}
$Args = @($Cli, "executable", "build", "--root", $Root)
if ($SkipInstaller) { $Args += "--skip-installer" }
& python.exe @Args
exit $LASTEXITCODE
