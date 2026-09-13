use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InstallMode {
    Development,
    Portable,
    Installed,
}

impl InstallMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Development => "development",
            Self::Portable => "portable",
            Self::Installed => "installed",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UpdateTransport {
    ApplicationImage,
    SourcePatch,
    Unknown,
}

impl UpdateTransport {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::ApplicationImage => "application-image",
            Self::SourcePatch => "source-patch",
            Self::Unknown => "unknown",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UpdateLayout {
    pub mode: InstallMode,
    pub application_root: PathBuf,
    pub data_root: PathBuf,
    pub maintenance_root: PathBuf,
    pub executable: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeUpdatePlan {
    pub state: String,
    pub mode: InstallMode,
    pub transport: PathBuf,
    pub transport_kind: UpdateTransport,
    pub current_root: PathBuf,
    pub staged_root: PathBuf,
    pub maintenance_root: PathBuf,
    pub rollback_root: PathBuf,
    pub entrypoint: String,
    pub application_version: String,
    pub application_build: String,
    pub plan_json: PathBuf,
}

fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn path_json(path: &Path) -> String {
    json_escape(&path.display().to_string())
}

impl UpdateLayout {
    pub fn to_json(&self) -> String {
        format!(
            "{{\"schema\":\"forge.native.update-layout.v1\",\"mode\":\"{}\",\"applicationRoot\":\"{}\",\"dataRoot\":\"{}\",\"maintenanceRoot\":\"{}\",\"executable\":\"{}\",\"promotionAuthority\":\"rust-helper\",\"archiveVerificationAuthority\":\"python-shadow-bridge\"}}",
            self.mode.as_str(),
            path_json(&self.application_root),
            path_json(&self.data_root),
            path_json(&self.maintenance_root),
            path_json(&self.executable),
        )
    }
}

impl NativeUpdatePlan {
    pub fn to_json(&self) -> String {
        format!(
            "{{\"schema\":\"forge.native.update-plan.v1\",\"state\":\"{}\",\"mode\":\"{}\",\"transport\":\"{}\",\"transportKind\":\"{}\",\"currentRoot\":\"{}\",\"stagedRoot\":\"{}\",\"maintenanceRoot\":\"{}\",\"rollbackRoot\":\"{}\",\"entrypoint\":\"{}\",\"applicationVersion\":\"{}\",\"applicationBuild\":\"{}\",\"planJson\":\"{}\"}}",
            json_escape(&self.state),
            self.mode.as_str(),
            path_json(&self.transport),
            self.transport_kind.as_str(),
            path_json(&self.current_root),
            path_json(&self.staged_root),
            path_json(&self.maintenance_root),
            path_json(&self.rollback_root),
            json_escape(&self.entrypoint),
            json_escape(&self.application_version),
            json_escape(&self.application_build),
            path_json(&self.plan_json),
        )
    }
}

pub fn classify_transport(path: &Path) -> UpdateTransport {
    match path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase()
        .as_str()
    {
        "forgeupdate" => UpdateTransport::ApplicationImage,
        "patch" | "zip" => UpdateTransport::SourcePatch,
        _ => UpdateTransport::Unknown,
    }
}

fn development_crate_root(executable: &Path) -> Option<PathBuf> {
    let profile = executable.parent()?;
    let target = profile.parent()?;
    let target_name = target.file_name()?.to_string_lossy();
    if !target_name.eq_ignore_ascii_case("target") {
        return None;
    }
    let crate_root = target.parent()?;
    crate_root.join("Cargo.toml").is_file().then(|| crate_root.to_path_buf())
}

fn local_app_data() -> Option<PathBuf> {
    env::var_os("LOCALAPPDATA").map(PathBuf::from)
}

pub fn detect_layout_for_executable(executable: &Path) -> Result<UpdateLayout, String> {
    let executable = fs::canonicalize(executable).unwrap_or_else(|_| executable.to_path_buf());
    let app_root = executable
        .parent()
        .ok_or_else(|| "native executable has no parent directory".to_string())?
        .to_path_buf();

    if app_root.join(".forge-portable").is_file() || app_root.join(".forgepy-portable").is_file() {
        let name = app_root
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("Forge");
        let parent = app_root.parent().unwrap_or_else(|| Path::new("."));
        return Ok(UpdateLayout {
            mode: InstallMode::Portable,
            application_root: app_root.clone(),
            data_root: app_root.join("Data"),
            maintenance_root: parent.join(format!(".{name}.ForgeMaintenance")),
            executable,
        });
    }

    if let Some(crate_root) = development_crate_root(&executable) {
        return Ok(UpdateLayout {
            mode: InstallMode::Development,
            application_root: crate_root.clone(),
            data_root: crate_root.join(".forge/native/data"),
            maintenance_root: crate_root.join(".forge/native/application-maintenance"),
            executable,
        });
    }

    let local = local_app_data().unwrap_or_else(|| {
        app_root
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join(".ForgeState")
    });
    Ok(UpdateLayout {
        mode: InstallMode::Installed,
        application_root: app_root,
        data_root: local.join("Forge/Data"),
        maintenance_root: local.join("Forge/ApplicationMaintenance"),
        executable,
    })
}

pub fn current_layout() -> Result<UpdateLayout, String> {
    let executable = env::current_exe().map_err(|err| format!("current executable: {err}"))?;
    detect_layout_for_executable(&executable)
}

fn is_within(child: &Path, parent: &Path) -> bool {
    let child = fs::canonicalize(child).unwrap_or_else(|_| child.to_path_buf());
    let parent = fs::canonicalize(parent).unwrap_or_else(|_| parent.to_path_buf());
    child.starts_with(parent)
}

fn bridge_path(project_root: &Path, executable: &Path) -> Result<PathBuf, String> {
    if let Some(value) = env::var_os("FORGE_NATIVE_UPDATE_BRIDGE") {
        let path = PathBuf::from(value);
        if path.is_file() {
            return Ok(path);
        }
    }

    let development = project_root.join("tools/rust/ForgeNativeUpdateBridge.py");
    if development.is_file() {
        return Ok(development);
    }

    if let Some(app_root) = executable.parent() {
        let packaged = app_root.join("support/ForgeNativeUpdateBridge.py");
        if packaged.is_file() {
            return Ok(packaged);
        }
    }

    Err("Forge native update verification bridge was not found".to_string())
}

fn python_executable() -> String {
    env::var("FORGE_PYTHON")
        .or_else(|_| env::var("FORGEPY_PYTHON"))
        .unwrap_or_else(|_| "python".to_string())
}

fn parse_kv(stdout: &str) -> std::collections::BTreeMap<String, String> {
    stdout
        .lines()
        .filter_map(|line| line.split_once('='))
        .map(|(key, value)| (key.trim().to_string(), value.trim().to_string()))
        .collect()
}

fn required_kv(
    values: &std::collections::BTreeMap<String, String>,
    key: &str,
) -> Result<String, String> {
    values
        .get(key)
        .cloned()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| format!("native update bridge did not return {key}"))
}

pub fn stage_native_update(
    project_root: &Path,
    transport: &Path,
    executable: &Path,
) -> Result<NativeUpdatePlan, String> {
    if classify_transport(transport) != UpdateTransport::ApplicationImage {
        return Err("packaged Forge Native self-update requires a .forgeupdate application image".to_string());
    }
    if !transport.is_file() {
        return Err(format!("native update transport does not exist: {}", transport.display()));
    }

    let layout = detect_layout_for_executable(executable)?;
    let bridge = bridge_path(project_root, executable)?;
    let entrypoint = executable
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "native executable has no file name".to_string())?
        .to_string();

    let output = Command::new(python_executable())
        .arg(&bridge)
        .arg("stage")
        .arg("--transport")
        .arg(transport)
        .arg("--current-root")
        .arg(&layout.application_root)
        .arg("--maintenance-root")
        .arg(&layout.maintenance_root)
        .arg("--mode")
        .arg(layout.mode.as_str())
        .arg("--entrypoint")
        .arg(&entrypoint)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|err| format!("launch native update bridge: {err}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        return Err(format!(
            "native update bridge failed ({}): {}{}{}",
            output.status,
            stdout.trim(),
            if !stdout.trim().is_empty() && !stderr.trim().is_empty() { " | " } else { "" },
            stderr.trim()
        ));
    }

    let values = parse_kv(&stdout);
    if values.get("OK").map(String::as_str) != Some("1") {
        return Err(format!("native update bridge did not certify staging: {}", stdout.trim()));
    }

    let staged_root = PathBuf::from(required_kv(&values, "STAGED_ROOT")?);
    if is_within(&staged_root, &layout.application_root) {
        return Err("native update staging must live outside the application image".to_string());
    }

    let maintenance_root = PathBuf::from(required_kv(&values, "MAINTENANCE_ROOT")?);
    let rollback_root = maintenance_root.join("Rollback/Forge.previous");
    Ok(NativeUpdatePlan {
        state: required_kv(&values, "STATE")?,
        mode: layout.mode,
        transport: transport.to_path_buf(),
        transport_kind: UpdateTransport::ApplicationImage,
        current_root: layout.application_root,
        staged_root,
        maintenance_root,
        rollback_root,
        entrypoint: required_kv(&values, "ENTRYPOINT")?,
        application_version: required_kv(&values, "APPLICATION_VERSION")?,
        application_build: required_kv(&values, "APPLICATION_BUILD")?,
        plan_json: PathBuf::from(required_kv(&values, "PLAN_JSON")?),
    })
}

pub fn build_native_update_bundle(
    project_root: &Path,
    image_root: &Path,
    output_path: &Path,
    entrypoint: &str,
    application_version: &str,
    application_build: &str,
) -> Result<PathBuf, String> {
    let executable = env::current_exe().map_err(|err| format!("current executable: {err}"))?;
    let bridge = bridge_path(project_root, &executable)?;
    let output = Command::new(python_executable())
        .arg(bridge)
        .arg("build")
        .arg("--image-root")
        .arg(image_root)
        .arg("--output")
        .arg(output_path)
        .arg("--entrypoint")
        .arg(entrypoint)
        .arg("--application-version")
        .arg(application_version)
        .arg("--application-build")
        .arg(application_build)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|err| format!("launch native update bridge: {err}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        return Err(format!("native update bundle build failed: {} {}", stdout.trim(), stderr.trim()));
    }
    let values = parse_kv(&stdout);
    if values.get("OK").map(String::as_str) != Some("1") {
        return Err(format!("native update bundle was not certified: {}", stdout.trim()));
    }
    Ok(PathBuf::from(required_kv(&values, "BUNDLE")?))
}

fn powershell_quote(path: &Path) -> String {
    format!("'{}'", path.display().to_string().replace('\'', "''"))
}

fn powershell_quote_text(value: &str) -> String {
    format!("'{}'", value.replace('\'', "''"))
}

pub fn write_promotion_helper(plan: &NativeUpdatePlan) -> Result<PathBuf, String> {
    if plan.mode == InstallMode::Development {
        return Err("development builds cannot replace their Cargo workspace; package a portable or installed image first".to_string());
    }
    if plan.state != "STAGED" {
        return Err(format!("native update plan is not staged: {}", plan.state));
    }
    if !plan.staged_root.join(&plan.entrypoint).is_file() {
        return Err(format!("staged native image is missing {}", plan.entrypoint));
    }
    if is_within(&plan.staged_root, &plan.current_root) {
        return Err("refusing to promote an update staged inside the live application root".to_string());
    }

    let helper_root = env::temp_dir().join("ForgeNative-UpdateHelpers");
    fs::create_dir_all(&helper_root).map_err(|err| format!("create update helper root: {err}"))?;
    let helper = helper_root.join(format!("Promote-ForgeNative-{}.ps1", std::process::id()));
    let portable = plan.mode == InstallMode::Portable;

    let mut lines = vec![
        "param([int]$PidToWait)".to_string(),
        "$ErrorActionPreference = \"Stop\"".to_string(),
        "while (Get-Process -Id $PidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 250 }".to_string(),
        format!("$current = {}", powershell_quote(&plan.current_root)),
        format!("$staged = {}", powershell_quote(&plan.staged_root)),
        format!("$rollback = {}", powershell_quote(&plan.rollback_root)),
        format!("$entrypoint = {}", powershell_quote_text(&plan.entrypoint)),
        "$rollbackParent = Split-Path -Parent $rollback".to_string(),
        "New-Item -ItemType Directory -Force -Path $rollbackParent | Out-Null".to_string(),
        "if (Test-Path $rollback) { Remove-Item -Recurse -Force $rollback }".to_string(),
        "try {".to_string(),
        "  if (Test-Path $current) { Move-Item -Force $current $rollback }".to_string(),
        "  Move-Item -Force $staged $current".to_string(),
    ];

    if portable {
        lines.extend([
            "  $oldData = Join-Path $rollback 'Data'".to_string(),
            "  $newData = Join-Path $current 'Data'".to_string(),
            "  if (Test-Path $oldData) {".to_string(),
            "    if (Test-Path $newData) { Remove-Item -Recurse -Force $newData }".to_string(),
            "    Move-Item -Force $oldData $newData".to_string(),
            "  }".to_string(),
            "  Set-Content -Path (Join-Path $current '.forge-portable') -Value 'Forge portable install' -Encoding UTF8".to_string(),
        ]);
    }

    lines.extend([
        "  $nextExe = Join-Path $current $entrypoint".to_string(),
        "  if (-not (Test-Path $nextExe)) { throw \"Promoted image is missing entrypoint: $nextExe\" }".to_string(),
        "  Start-Process $nextExe".to_string(),
        "} catch {".to_string(),
        "  if (Test-Path $current) { Remove-Item -Recurse -Force $current }".to_string(),
        "  if (Test-Path $rollback) { Move-Item -Force $rollback $current }".to_string(),
        "  throw".to_string(),
        "}".to_string(),
        String::new(),
    ]);

    fs::write(&helper, lines.join("\r\n")).map_err(|err| format!("write update helper: {err}"))?;
    Ok(helper)
}

#[cfg(windows)]
pub fn arm_promotion(plan: &NativeUpdatePlan) -> Result<PathBuf, String> {
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let helper = write_promotion_helper(plan)?;
    Command::new("powershell.exe")
        .arg("-NoProfile")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-File")
        .arg(&helper)
        .arg("-PidToWait")
        .arg(std::process::id().to_string())
        .creation_flags(CREATE_NO_WINDOW)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|err| format!("arm native update promotion: {err}"))?;
    Ok(helper)
}

#[cfg(not(windows))]
pub fn arm_promotion(_plan: &NativeUpdatePlan) -> Result<PathBuf, String> {
    Err("native application promotion is Windows-only".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_root(name: &str) -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        env::temp_dir().join(format!("forge-native-{name}-{}-{stamp}", std::process::id()))
    }

    #[test]
    fn transport_classification_is_fail_closed() {
        assert_eq!(classify_transport(Path::new("update.forgeupdate")), UpdateTransport::ApplicationImage);
        assert_eq!(classify_transport(Path::new("source.patch")), UpdateTransport::SourcePatch);
        assert_eq!(classify_transport(Path::new("notes.txt")), UpdateTransport::Unknown);
    }

    #[test]
    fn portable_layout_keeps_maintenance_outside_live_image() {
        let root = temp_root("portable");
        let app = root.join("ForgePortable");
        fs::create_dir_all(&app).unwrap();
        fs::write(app.join(".forge-portable"), b"portable\n").unwrap();
        let exe = app.join(if cfg!(windows) { "ForgeNative.exe" } else { "ForgeNative" });
        fs::write(&exe, b"fixture").unwrap();
        let layout = detect_layout_for_executable(&exe).unwrap();
        assert_eq!(layout.mode, InstallMode::Portable);
        assert!(!layout.maintenance_root.starts_with(&layout.application_root));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn cargo_target_is_development_and_cannot_be_promoted() {
        let root = temp_root("development");
        fs::create_dir_all(root.join("target/debug")).unwrap();
        fs::write(root.join("Cargo.toml"), b"[package]\nname='fixture'\nversion='0.1.0'\n").unwrap();
        let exe = root.join("target/debug/ForgeNative.exe");
        fs::write(&exe, b"fixture").unwrap();
        let layout = detect_layout_for_executable(&exe).unwrap();
        assert_eq!(layout.mode, InstallMode::Development);
        let _ = fs::remove_dir_all(root);
    }
}
