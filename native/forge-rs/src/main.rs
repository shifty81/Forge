use std::env;
use std::io::{self, BufRead};
use std::path::{Path, PathBuf};

use forge_native::contracts::probe_project_contract;
use forge_native::identity::NativeIdentity;
use forge_native::parity::{foundation_matrix, takeover_ready};
use forge_native::paths::ForgePaths;
use forge_native::project::probe_project;
use forge_native::protocol::{parse_request_line, NativeEvent, NativeRequest};
use forge_native::shell::ShellModel;
use forge_native::evidence::{evidence_json, write_evidence};
use forge_native::gui::run_native_gui;
use forge_native::intelligence::census;
use forge_native::toolchains::{probe_all, ready_count};

fn root_from_args(args: &[String]) -> PathBuf {
    if let Some(index) = args.iter().position(|value| value == "--root") {
        if let Some(value) = args.get(index + 1) {
            return PathBuf::from(value);
        }
    }
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn print_probe(root: &Path) -> i32 {
    let identity = NativeIdentity::current();
    let contract = match probe_project_contract(root) {
        Ok(row) => row,
        Err(err) => {
            eprintln!("[FAIL] project contract probe: {err}");
            return 2;
        }
    };
    let paths_ready = ForgePaths::new(root).is_ok();
    println!("build={}", identity.build);
    println!("version={}", identity.version);
    println!("phase={}", identity.phase);
    println!("root={}", root.display());
    println!("project_contract={}", if contract.ready() { "ready" } else { "incomplete" });
    println!("paths={}", if paths_ready { "ready" } else { "invalid-root" });
    println!("python_authority={}", identity.python_authority);
    println!("takeover_ready=false");
    0
}

fn print_parity_json() -> i32 {
    let identity = NativeIdentity::current();
    let rows = foundation_matrix();
    println!("{{");
    println!("  \"schema\": \"forge.native.parity.v1\",");
    println!("  \"build\": \"{}\",", json_escape(identity.build));
    println!("  \"phase\": \"{}\",", identity.phase);
    println!("  \"pythonAuthority\": {},", identity.python_authority);
    println!("  \"takeoverReady\": {},", takeover_ready(&rows));
    println!("  \"rows\": [");
    for (index, row) in rows.iter().enumerate() {
        println!(
            "    {{\"capability\":\"{}\",\"state\":\"{}\",\"note\":\"{}\"}}{}",
            json_escape(row.capability),
            row.state.as_str(),
            json_escape(row.note),
            if index + 1 == rows.len() { "" } else { "," }
        );
    }
    println!("  ]");
    println!("}}");
    0
}

fn print_shell_model(root: &Path) -> i32 {
    match probe_project(root) {
        Ok(project) => { println!("{}", ShellModel::from_project(&project).to_json()); 0 }
        Err(err) => { eprintln!("[FAIL] shell model: {err}"); 2 }
    }
}


fn print_intelligence_json(root: &Path) -> i32 {
    let census = match census(root) {
        Ok(row) => row,
        Err(err) => { eprintln!("[FAIL] project intelligence: {err}"); return 2; }
    };
    let tools = probe_all();
    println!("{{");
    println!("  \"schema\": \"forge.native.project-intelligence.v1\",");
    println!("  \"root\": \"{}\",", json_escape(&root.display().to_string()));
    println!("  \"confidence\": {},", census.confidence);
    println!("  \"scannedEntries\": {},", census.scanned_entries);
    println!("  \"truncated\": {},", census.truncated);
    println!("  \"buildSystems\": {},", census.build_systems.len());
    println!("  \"languages\": {},", census.language_counts.len());
    println!("  \"nestedRoots\": {},", census.nested_roots.len());
    println!("  \"inferredOperations\": {},", census.operations.len());
    println!("  \"toolchainsReady\": {},", ready_count(&tools));
    println!("  \"toolchainsKnown\": {}", tools.len());
    println!("}}");
    0
}

fn serve_stdio(root: &Path) -> i32 {
    let stdin=io::stdin(); let mut sequence=0u64;
    for line in stdin.lock().lines().map_while(Result::ok) {
        sequence+=1;
        let request=parse_request_line(&line);
        let message=match request {
            NativeRequest::Ping => "pong".to_string(),
            NativeRequest::Identity => format!("{}", NativeIdentity::current().build),
            NativeRequest::Probe => match probe_project_contract(root) { Ok(row) => format!("contractReady={}", row.ready()), Err(err) => format!("error={err}") },
            NativeRequest::Parity => format!("rows={};takeoverReady={}", foundation_matrix().len(), takeover_ready(&foundation_matrix())),
            NativeRequest::ShellModel => match probe_project(root) { Ok(project) => ShellModel::from_project(&project).to_json(), Err(err) => format!("error={err}") },
            NativeRequest::Shutdown => { println!("{}", NativeEvent::new(sequence,"shutdown","forgepy","bye").to_json_line()); break; },
            NativeRequest::Unknown(value) => format!("unsupported={value}"),
        };
        println!("{}", NativeEvent::new(sequence,"response","forgepy",message).to_json_line());
    }
    0
}

fn self_test(root: &Path) -> i32 {
    let mut failed = false;
    match probe_project_contract(root) {
        Ok(row) if row.ready() => println!("PASS project-contract-marker-probe"),
        Ok(_) => {
            println!("FAIL project-contract-marker-probe");
            failed = true;
        }
        Err(err) => {
            println!("FAIL project-contract-marker-probe: {err}");
            failed = true;
        }
    }
    match ForgePaths::new(root) {
        Ok(paths) if paths.confined("app/ForgeGui.py").is_ok() && paths.confined("../escape").is_err() => {
            println!("PASS path-confinement");
        }
        Ok(_) => {
            println!("FAIL path-confinement");
            failed = true;
        }
        Err(err) => {
            println!("FAIL root-path: {err}");
            failed = true;
        }
    }
    match census(root) {
        Ok(row) if row.scanned_entries > 0 => println!("PASS project-intelligence-census"),
        Ok(_) => { println!("FAIL project-intelligence-census"); failed = true; },
        Err(err) => { println!("FAIL project-intelligence-census: {err}"); failed = true; },
    }
    let rows = foundation_matrix();
    if !takeover_ready(&rows) {
        println!("PASS fail-closed-takeover");
    } else {
        println!("FAIL fail-closed-takeover");
        failed = true;
    }
    if failed { 1 } else { 0 }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let root = root_from_args(&args);
    let identity = NativeIdentity::current();

    if args.iter().any(|arg| arg == "--version") {
        println!("{}", identity.build);
        return;
    }
    if args.iter().any(|arg| arg == "--probe") {
        std::process::exit(print_probe(&root));
    }
    if args.iter().any(|arg| arg == "--parity-json") {
        std::process::exit(print_parity_json());
    }
    if args.iter().any(|arg| arg == "--self-test") { std::process::exit(self_test(&root)); }
    if args.iter().any(|arg| arg == "--shell-model-json") { std::process::exit(print_shell_model(&root)); }
    if args.iter().any(|arg| arg == "--intelligence-json") { std::process::exit(print_intelligence_json(&root)); }
    if args.iter().any(|arg| arg == "--evidence-json") { println!("{}", evidence_json()); return; }
    if let Some(index)=args.iter().position(|arg| arg == "--write-evidence") {
        let path=args.get(index+1).map(PathBuf::from).unwrap_or_else(|| root.join(".forge/native/parity-latest.json"));
        match write_evidence(&path) { Ok(()) => { println!("[PASS] native evidence: {}",path.display()); return; }, Err(err) => { eprintln!("[FAIL] native evidence: {err}"); std::process::exit(2); } }
    }
    if args.iter().any(|arg| arg == "--serve-stdio") { std::process::exit(serve_stdio(&root)); }
    if args.iter().any(|arg| arg == "--headless") {
        println!("Forge Native Rust successor ({})", identity.build);
        println!("Root: {}", root.display());
        println!("Authority phase: {}", identity.phase);
        println!("Python ForgePY remains operational authority until native parity certification and explicit takeover.");
        return;
    }

    if let Err(err) = run_native_gui(root) {
        eprintln!("[FAIL] Forge Native GUI: {err}");
        std::process::exit(2);
    }
}
