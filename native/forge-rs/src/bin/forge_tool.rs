use std::env;
use std::path::PathBuf;

use forge_native::gui::model::ToolPanel;
use forge_native::gui::run_native_tool;

fn value_after(args: &[String], flag: &str) -> Option<String> {
    args.iter().position(|value| value == flag).and_then(|index| args.get(index + 1)).cloned()
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let root = value_after(&args, "--root").map(PathBuf::from).unwrap_or_else(|| env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    let slug = value_after(&args, "--tool").unwrap_or_else(|| "overview".to_string());
    let Some(panel) = ToolPanel::from_slug(&slug) else {
        eprintln!("[FAIL] unknown Forge tool panel: {slug}");
        eprintln!("Available tool ids: {}", ToolPanel::ALL.map(|panel| panel.slug()).join(", "));
        std::process::exit(2);
    };
    if let Err(err) = run_native_tool(root, panel) {
        eprintln!("[FAIL] ForgeTool: {err}");
        std::process::exit(2);
    }
}
