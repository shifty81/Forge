#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from ForgeApplicationIdentity import DISPLAY_BUILD, DISPLAY_VERSION
from ForgeExeBuild import execute as build_nuitka
from ForgeStandaloneBuild import preflight as nuitka_preflight

EXECUTABLE_SYSTEM_VERSION = "FORGEPY-EXECUTABLE-SYSTEM-1.0-F740"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_sha_sidecar(path: Path) -> Path:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{_sha256(path)}  {path.name}\n", encoding="ascii")
    return sidecar


def _iscc() -> str:
    candidates = [
        shutil.which("ISCC.exe") or "",
        shutil.which("iscc") or "",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for value in candidates:
        if value and Path(value).is_file():
            return str(Path(value))
    return ""


def preflight(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    nuitka = nuitka_preflight(root)
    iscc = _iscc()
    return {
        "schema": "forgepy.executable.preflight.v1",
        "version": EXECUTABLE_SYSTEM_VERSION,
        "applicationVersion": DISPLAY_VERSION,
        "applicationBuild": DISPLAY_BUILD,
        "root": str(root),
        "windows": sys.platform.startswith("win"),
        "nuitka": nuitka,
        "innoSetup": {"available": bool(iscc), "compiler": iscc},
        "readyForExecutable": bool(nuitka.get("readyForWindowsBuild")),
        "readyForInstaller": bool(nuitka.get("readyForWindowsBuild") and iscc),
        "distribution": {
            "runtime": "Nuitka standalone/onedir",
            "portable": "ZIP + .forgepy-portable + local Data",
            "installer": "Inno Setup standard/portable mode selector",
        },
    }


def _runtime_identity_file(image: Path, mode: str) -> Path:
    path = image / "FORGEPY_RUNTIME_IDENTITY.json"
    payload = {
        "schema": "forgepy.runtime-identity.v1",
        "version": DISPLAY_VERSION,
        "build": DISPLAY_BUILD,
        "distributionMode": mode,
        "executable": "ForgePY.exe",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _copy_image(source: Path, destination: Path, *, portable: bool) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "Data", "Logs", "Cache", "Updates", "Rollback",
            "__pycache__", "*.pyc", ".forgepy-portable",
        ),
    )
    marker = destination / ".forgepy-portable"
    if portable:
        marker.write_text("ForgePY portable install\n", encoding="utf-8")
        (destination / "Data").mkdir(parents=True, exist_ok=True)
        _runtime_identity_file(destination, "portable")
    else:
        marker.unlink(missing_ok=True)
        _runtime_identity_file(destination, "installed")
    return destination


def prepare_images(root: Path, built_image: Path | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    source = (built_image or (root / "dist" / "ForgePY")).expanduser().resolve()
    exe = source / "ForgePY.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"built ForgePY.exe image not found: {source}")

    dist = root / "dist"
    installed = dist / "ForgePY-InstalledImage"
    portable = dist / "ForgePY-Portable"
    _copy_image(source, installed, portable=False)
    _copy_image(source, portable, portable=True)
    return {
        "installedImage": str(installed),
        "portableImage": str(portable),
        "installedExe": str(installed / "ForgePY.exe"),
        "portableExe": str(portable / "ForgePY.exe"),
    }


def build_portable_zip(root: Path, portable_image: Path | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    image = (portable_image or (root / "dist" / "ForgePY-Portable")).expanduser().resolve()
    if not (image / "ForgePY.exe").is_file():
        raise FileNotFoundError(image / "ForgePY.exe")
    output = root / "dist" / f"ForgePY-{DISPLAY_VERSION}-Portable-Windows-x64.zip"
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(image.rglob("*")):
            if path.is_file():
                archive.write(path, Path("ForgePY") / path.relative_to(image))
    _write_sha_sidecar(output)
    return {"path": str(output), "sha256": _sha256(output), "bytes": output.stat().st_size}


def generate_inno_script(root: Path, installed_image: Path | None = None) -> Path:
    root = root.expanduser().resolve()
    image = (installed_image or (root / "dist" / "ForgePY-InstalledImage")).expanduser().resolve()
    if not (image / "ForgePY.exe").is_file():
        raise FileNotFoundError(image / "ForgePY.exe")

    generated = root / "dist" / "installer"
    generated.mkdir(parents=True, exist_ok=True)
    script = generated / "ForgePY.iss"
    escaped = str(image).replace("\\", "\\\\")
    output_dir = str((root / "dist" / "installer-output").resolve()).replace("\\", "\\\\")

    body = f'''#define AppName "ForgePY"
#define AppVersion "{DISPLAY_VERSION}"
#define AppPublisher "ForgePY"
#define AppExeName "ForgePY.exe"

[Setup]
AppId=ForgePY.A9D014EC-4D77-4D66-90A2-F58B99BA80F0
AppName={{#AppName}}
AppVersion={{#AppVersion}}
AppPublisher={{#AppPublisher}}
DefaultDirName={{code:GetDefaultDirName}}
DefaultGroupName=ForgePY
OutputDir={output_dir}
OutputBaseFilename=ForgePY-{DISPLAY_VERSION}-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
Uninstallable={code:IsNotPortable}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={{app}}\\ForgePY.exe

[Files]
Source: "{escaped}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{userprograms}}\\ForgePY"; Filename: "{{app}}\\ForgePY.exe"; Check: not IsPortable
Name: "{{userdesktop}}\\ForgePY"; Filename: "{{app}}\\ForgePY.exe"; Tasks: desktopicon; Check: not IsPortable

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Check: not IsPortable

[Run]
Filename: "{{app}}\\ForgePY.exe"; Description: "Launch ForgePY"; Flags: nowait postinstall skipifsilent

[Code]
var
  InstallModePage: TInputOptionWizardPage;

function IsPortable(): Boolean;
begin
  Result := Assigned(InstallModePage) and (InstallModePage.SelectedValueIndex = 1);
end;

function IsNotPortable(): Boolean;
begin
  Result := not IsPortable();
end;

function GetDefaultDirName(Param: String): String;
begin
  if IsPortable() then
    Result := ExpandConstant('{{userdocs}}\\ForgePY-Portable')
  else
    Result := ExpandConstant('{{localappdata}}\\Programs\\ForgePY');
end;

procedure InitializeWizard();
begin
  InstallModePage := CreateInputOptionPage(
    wpWelcome,
    'ForgePY Install Mode',
    'Choose how ForgePY stores its application state.',
    'Standard uses AppData for mutable ForgePY state. Portable keeps a Data folder beside ForgePY.exe.',
    True,
    False
  );
  InstallModePage.Add('Standard install (recommended)');
  InstallModePage.Add('Portable install');
  InstallModePage.SelectedValueIndex := 0;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = InstallModePage.ID then
    WizardForm.DirEdit.Text := GetDefaultDirName('');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Marker: String;
begin
  if CurStep = ssPostInstall then
  begin
    Marker := ExpandConstant('{{app}}\\.forgepy-portable');
    if IsPortable() then
      SaveStringToFile(Marker, 'ForgePY portable install'#13#10, False)
    else if FileExists(Marker) then
      DeleteFile(Marker);
  end;
end;
'''
    script.write_text(body, encoding="utf-8")
    return script


def build_installer(root: Path, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("installer build requires explicit approval")
    root = root.expanduser().resolve()
    compiler = _iscc()
    script = generate_inno_script(root)
    if not compiler:
        return {
            "ok": False,
            "reason": "Inno Setup 6 compiler not installed",
            "script": str(script),
            "compiler": "",
        }
    cp = subprocess.run(
        [compiler, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    output_dir = root / "dist" / "installer-output"
    installers = sorted(output_dir.glob("ForgePY-*-Setup.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    output = installers[0] if installers else None
    if output is not None:
        _write_sha_sidecar(output)
    return {
        "ok": cp.returncode == 0 and output is not None,
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
        "script": str(script),
        "installer": str(output) if output else "",
        "sha256": _sha256(output) if output else "",
    }



def build_update_bundle(root: Path, installed_image: Path | None = None) -> dict[str, Any]:
    """Create the packaged-application update transport consumed by installed ForgePY."""
    root = root.expanduser().resolve()
    image = (installed_image or (root / "dist" / "ForgePY-InstalledImage")).expanduser().resolve()
    if not (image / "ForgePY.exe").is_file():
        raise FileNotFoundError(image / "ForgePY.exe")

    files: list[dict[str, Any]] = []
    for path in sorted(image.rglob("*")):
        if path.is_file():
            files.append({
                "path": path.relative_to(image).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })

    manifest = {
        "schema": "forgepy.application-update.v1",
        "systemVersion": EXECUTABLE_SYSTEM_VERSION,
        "applicationVersion": DISPLAY_VERSION,
        "applicationBuild": DISPLAY_BUILD,
        "entrypoint": "ForgePY.exe",
        "files": files,
    }

    bundle = root / "dist" / f"ForgePY-{DISPLAY_VERSION}-Windows-x64.forgeupdate"
    if bundle.exists():
        bundle.unlink()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("FORGEPY_UPDATE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        for row in files:
            archive.write(image / row["path"], "image/" + row["path"])
    _write_sha_sidecar(bundle)
    return {
        "path": str(bundle),
        "sha256": _sha256(bundle),
        "bytes": bundle.stat().st_size,
        "applicationVersion": DISPLAY_VERSION,
        "applicationBuild": DISPLAY_BUILD,
        "fileCount": len(files),
    }


def build_distribution(root: Path, *, approved: bool = False, build_installer_if_available: bool = True) -> dict[str, Any]:
    if not approved:
        raise PermissionError("ForgePY distribution build requires explicit approval")
    root = root.expanduser().resolve()
    result = build_nuitka(root, approved=True)
    if not result.get("ok"):
        return {"ok": False, "phase": "nuitka", "build": result}

    images = prepare_images(root, Path(str(result["output"])))
    portable = build_portable_zip(root, Path(images["portableImage"]))
    update_bundle = build_update_bundle(root, Path(images["installedImage"]))
    script = generate_inno_script(root, Path(images["installedImage"]))
    installer: dict[str, Any] = {"ok": False, "script": str(script), "reason": "not requested"}
    installer_compiler_available = bool(_iscc())
    if build_installer_if_available:
        installer = build_installer(root, approved=True)

    if build_installer_if_available and installer_compiler_available and not installer.get("ok"):
        return {
            "ok": False,
            "phase": "installer",
            "build": result,
            "images": images,
            "portableZip": portable,
            "applicationUpdate": update_bundle,
            "installer": installer,
        }

    manifest = root / "dist" / "ForgePY-Distribution.json"
    payload = {
        "schema": "forgepy.distribution.v1",
        "version": EXECUTABLE_SYSTEM_VERSION,
        "applicationVersion": DISPLAY_VERSION,
        "applicationBuild": DISPLAY_BUILD,
        "build": result,
        "images": images,
        "portableZip": portable,
        "applicationUpdate": update_bundle,
        "installer": installer,
    }
    manifest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return {**payload, "ok": True, "manifest": str(manifest)}
