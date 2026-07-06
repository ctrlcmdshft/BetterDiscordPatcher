$ErrorActionPreference = "Stop"

$AppName = "BetterDiscordPatcher"
$InstallDir = if ($env:BDI_INSTALL_DIR) { $env:BDI_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA $AppName }
$BinDir = if ($env:BDI_BIN_DIR) { $env:BDI_BIN_DIR } else { $InstallDir }
$BinPath = if ($env:BDI_BIN_PATH) { $env:BDI_BIN_PATH } else { Join-Path $BinDir "betterdiscord.cmd" }
$ConfigPath = if ($env:BDI_CONFIG_PATH) { $env:BDI_CONFIG_PATH } else { Join-Path $env:APPDATA "$AppName\config.json" }
$Repo = if ($env:BDI_REPO) { $env:BDI_REPO } else { "ctrlcmdshft/BetterDiscordPatcher" }
$Branch = if ($env:BDI_BRANCH) { $env:BDI_BRANCH } else { "main" }
$RawBase = if ($env:BDI_RAW_BASE) { $env:BDI_RAW_BASE } else { "https://raw.githubusercontent.com/$Repo/$Branch" }

function Download-File($Url, $Destination) {
    Write-Host "Downloading $Url"
    $tmp = "$Destination.tmp"
    Invoke-WebRequest -Uri $Url -OutFile $tmp
    Move-Item -Force $tmp $Destination
}

function Get-UserPathEntries() {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($current)) {
        return @()
    }
    return $current.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries)
}

function Add-UserPathEntry($Entry) {
    $resolved = [System.IO.Path]::GetFullPath($Entry)
    $entries = Get-UserPathEntries
    $alreadyPresent = $entries | Where-Object {
        [string]::Equals(
            [System.IO.Path]::GetFullPath($_),
            $resolved,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    }
    if ($alreadyPresent) {
        return $false
    }

    $updated = @($entries + $resolved) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    if ([string]::IsNullOrWhiteSpace($env:Path)) {
        $env:Path = $resolved
    }
    elseif (-not (($env:Path -split ";") | Where-Object {
        [string]::Equals(
            [System.IO.Path]::GetFullPath($_),
            $resolved,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    })) {
        $env:Path = "$env:Path;$resolved"
    }
    return $true
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Download-File "$RawBase/betterdiscord.py" (Join-Path $InstallDir "betterdiscord.py")
Download-File "$RawBase/README.md" (Join-Path $InstallDir "README.md")
Download-File "$RawBase/install.ps1" (Join-Path $InstallDir "install.ps1")

$Wrapper = "@echo off`r`npython `"$InstallDir\betterdiscord.py`" %*`r`n"
Set-Content -Path $BinPath -Value $Wrapper -Encoding ASCII

python -m py_compile (Join-Path $InstallDir "betterdiscord.py")

if (!(Test-Path $ConfigPath)) {
    python (Join-Path $InstallDir "betterdiscord.py") --config $ConfigPath --init-config
}
else {
    Write-Host "Config exists: $ConfigPath"
    python (Join-Path $InstallDir "betterdiscord.py") --config $ConfigPath --format-config
}

if ($env:BDI_EDIT_CONFIG -eq "1") {
    python (Join-Path $InstallDir "betterdiscord.py") --config $ConfigPath --edit-config
}

$PathAdded = Add-UserPathEntry $BinDir

Write-Host "Installed: $InstallDir"
Write-Host "Config: $ConfigPath"
Write-Host "Command: $BinPath"
if ($PathAdded) {
    Write-Host "Added to user PATH: $BinDir"
}
else {
    Write-Host "Already on user PATH: $BinDir"
}
