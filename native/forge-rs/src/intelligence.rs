use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

const MAX_ENTRIES: usize = 12_000;
const MAX_DEPTH: usize = 4;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DetectedMarker {
    pub kind: String,
    pub path: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SynthesizedOperation {
    pub key: String,
    pub label: String,
    pub program: String,
    pub args: Vec<String>,
    pub confidence: u8,
    pub read_only: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectCensus {
    pub scanned_entries: usize,
    pub truncated: bool,
    pub build_systems: Vec<String>,
    pub language_counts: Vec<(String, usize)>,
    pub markers: Vec<DetectedMarker>,
    pub nested_roots: Vec<PathBuf>,
    pub operations: Vec<SynthesizedOperation>,
    pub confidence: u8,
}

fn skipped_dir(name: &str) -> bool {
    matches!(
        name.to_ascii_lowercase().as_str(),
        ".git" | ".forge" | ".idea" | ".vs" | ".vscode" | "target" | "node_modules" | "build" | "builds" | "dist" | "out" | "bin" | "obj" | "logs" | "artifacts"
    )
}

fn marker_kind(name: &str) -> Option<&'static str> {
    let lower = name.to_ascii_lowercase();
    match lower.as_str() {
        "project.control.json" => Some("Forge project contract"),
        "cargo.toml" => Some("Cargo workspace/package"),
        "cmakelists.txt" => Some("CMake project"),
        "cmakepresets.json" => Some("CMake presets"),
        "package.json" => Some("Node package"),
        "pyproject.toml" => Some("Python project"),
        "requirements.txt" => Some("Python requirements"),
        "pom.xml" => Some("Maven project"),
        "build.gradle" | "build.gradle.kts" | "gradlew" | "gradlew.bat" => Some("Gradle project"),
        "project.godot" => Some("Godot project"),
        "makefile" => Some("Make project"),
        _ if lower.ends_with(".sln") => Some("Visual Studio solution"),
        _ if lower.ends_with(".csproj") => Some(".NET project"),
        _ if lower.ends_with(".vcxproj") => Some("Visual C++ project"),
        _ if lower.ends_with(".uproject") => Some("Unreal project"),
        _ => None,
    }
}

fn language_for(path: &Path) -> Option<&'static str> {
    match path.extension().and_then(|value| value.to_str()).unwrap_or("").to_ascii_lowercase().as_str() {
        "rs" => Some("Rust"),
        "py" => Some("Python"),
        "c" => Some("C"),
        "cc" | "cpp" | "cxx" | "h" | "hpp" | "hxx" => Some("C++"),
        "cs" => Some("C#"),
        "java" | "kt" | "kts" => Some("JVM"),
        "js" | "mjs" | "cjs" => Some("JavaScript"),
        "ts" | "tsx" => Some("TypeScript"),
        "gd" => Some("GDScript"),
        "lua" => Some("Lua"),
        "ps1" => Some("PowerShell"),
        "sh" | "bash" => Some("Shell"),
        _ => None,
    }
}

fn walk(root: &Path, current: &Path, depth: usize, state: &mut ScanState) -> io::Result<()> {
    if state.entries >= MAX_ENTRIES {
        state.truncated = true;
        return Ok(());
    }
    let mut rows: Vec<_> = fs::read_dir(current)?.filter_map(Result::ok).collect();
    rows.sort_by_key(|entry| entry.file_name().to_string_lossy().to_ascii_lowercase());
    for entry in rows {
        if state.entries >= MAX_ENTRIES {
            state.truncated = true;
            break;
        }
        state.entries += 1;
        let path = entry.path();
        let file_type = match entry.file_type() {
            Ok(value) => value,
            Err(_) => continue,
        };
        if file_type.is_dir() {
            let name = entry.file_name().to_string_lossy().to_string();
            if depth < MAX_DEPTH && !skipped_dir(&name) {
                walk(root, &path, depth + 1, state)?;
            }
            continue;
        }
        if !file_type.is_file() { continue; }
        let name = entry.file_name().to_string_lossy().to_string();
        if let Some(kind) = marker_kind(&name) {
            let relative = path.strip_prefix(root).unwrap_or(&path).to_path_buf();
            state.markers.push(DetectedMarker { kind: kind.to_string(), path: relative.clone() });
            state.build_systems.insert(kind.to_string());
            if let Some(parent) = relative.parent() {
                if parent != Path::new("") && parent != Path::new(".") {
                    state.nested_roots.insert(parent.to_path_buf());
                }
            }
        }
        if let Some(language) = language_for(&path) {
            *state.languages.entry(language.to_string()).or_insert(0) += 1;
        }
    }
    Ok(())
}

#[derive(Default)]
struct ScanState {
    entries: usize,
    truncated: bool,
    markers: Vec<DetectedMarker>,
    build_systems: BTreeSet<String>,
    nested_roots: BTreeSet<PathBuf>,
    languages: BTreeMap<String, usize>,
}

fn op(key: &str, label: &str, program: &str, args: &[&str], confidence: u8, read_only: bool) -> SynthesizedOperation {
    SynthesizedOperation {
        key: key.to_string(),
        label: label.to_string(),
        program: program.to_string(),
        args: args.iter().map(|value| (*value).to_string()).collect(),
        confidence,
        read_only,
    }
}

fn synthesize(markers: &[DetectedMarker]) -> Vec<SynthesizedOperation> {
    let kinds: BTreeSet<_> = markers.iter().map(|row| row.kind.as_str()).collect();
    let mut rows = Vec::new();
    if kinds.contains("Cargo workspace/package") {
        rows.push(op("build", "Cargo Build", "cargo", &["build"], 98, false));
        rows.push(op("test", "Cargo Test", "cargo", &["test", "--all-targets"], 98, true));
        rows.push(op("check", "Cargo Check", "cargo", &["check", "--all-targets"], 98, true));
    }
    if kinds.contains("CMake project") {
        rows.push(op("configure", "CMake Configure", "cmake", &["-S", ".", "-B", "build"], 88, false));
        rows.push(op("build", "CMake Build", "cmake", &["--build", "build"], 88, false));
        rows.push(op("test", "CTest", "ctest", &["--test-dir", "build", "--output-on-failure"], 82, true));
    }
    if kinds.contains("Visual Studio solution") {
        rows.push(op("build", "MSBuild Solution", "msbuild", &["/m"], 82, false));
    }
    if kinds.contains(".NET project") {
        rows.push(op("build", "dotnet build", "dotnet", &["build"], 92, false));
        rows.push(op("test", "dotnet test", "dotnet", &["test", "--no-restore"], 88, true));
    }
    if kinds.contains("Node package") {
        rows.push(op("build", "npm build", "npm", &["run", "build"], 78, false));
        rows.push(op("test", "npm test", "npm", &["test", "--", "--runInBand"], 68, true));
    }
    if kinds.contains("Python project") || kinds.contains("Python requirements") {
        rows.push(op("test", "Python tests", "python", &["-m", "pytest"], 78, true));
    }
    if kinds.contains("Gradle project") {
        rows.push(op("build", "Gradle Build", "gradlew", &["build"], 88, false));
        rows.push(op("test", "Gradle Test", "gradlew", &["test"], 88, true));
    }
    if kinds.contains("Maven project") {
        rows.push(op("build", "Maven Package", "mvn", &["package"], 88, false));
        rows.push(op("test", "Maven Test", "mvn", &["test"], 88, true));
    }
    if kinds.contains("Godot project") {
        rows.push(op("validate", "Godot Headless", "godot", &["--headless", "--editor", "--quit"], 86, true));
    }
    rows
}

pub fn census(root: &Path) -> io::Result<ProjectCensus> {
    let mut state = ScanState::default();
    walk(root, root, 0, &mut state)?;
    state.markers.sort_by(|a, b| a.path.cmp(&b.path));
    let mut languages: Vec<_> = state.languages.into_iter().collect();
    languages.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    let operations = synthesize(&state.markers);
    let marker_score = (state.markers.len().min(6) * 12) as u8;
    let language_score = (languages.len().min(4) * 5) as u8;
    let confidence = (30u8).saturating_add(marker_score).saturating_add(language_score).min(99);
    Ok(ProjectCensus {
        scanned_entries: state.entries,
        truncated: state.truncated,
        build_systems: state.build_systems.into_iter().collect(),
        language_counts: languages,
        markers: state.markers,
        nested_roots: state.nested_roots.into_iter().collect(),
        operations,
        confidence,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn scratch() -> PathBuf {
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("forge-native-intelligence-{stamp}"))
    }

    #[test]
    fn cargo_project_is_detected_without_forge_scripts() {
        let root = scratch();
        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("Cargo.toml"), "[package]\nname='demo'\nversion='0.1.0'\n").unwrap();
        fs::write(root.join("src/main.rs"), "fn main() {}\n").unwrap();
        let row = census(&root).unwrap();
        assert!(row.build_systems.iter().any(|value| value.contains("Cargo")));
        assert!(row.language_counts.iter().any(|(name, count)| name == "Rust" && *count == 1));
        assert!(row.operations.iter().any(|value| value.program == "cargo" && value.key == "build"));
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn generated_output_directories_are_not_descended() {
        let root = scratch();
        fs::create_dir_all(root.join("target/deep")).unwrap();
        fs::write(root.join("target/deep/Cargo.toml"), "ignored").unwrap();
        fs::write(root.join("pyproject.toml"), "[project]\nname='demo'\n").unwrap();
        let row = census(&root).unwrap();
        assert_eq!(row.markers.iter().filter(|value| value.kind.contains("Cargo")).count(), 0);
        let _ = fs::remove_dir_all(root);
    }
}
