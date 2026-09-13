use std::collections::VecDeque;
use std::path::{Path, PathBuf};

use eframe::egui::{self, Color32, RichText, ScrollArea, Stroke, Ui};
use egui_dock::{DockState, NodeIndex, Style, TabViewer};

use crate::identity::NativeIdentity;
use crate::intelligence::{census, ProjectCensus};
use crate::parity::foundation_matrix;
use crate::project::{probe_project, ProjectSnapshot};
use crate::settings;
use crate::toolchains::{probe_all, ready_count, ToolchainProbe};

use super::model::{LayoutPreset, WorkspaceTab};
use super::operations::{ForegroundQueue, OperationEvent};
use super::theme;

const MAX_CONSOLE_LINES: usize = 8000;

pub struct SharedUiState {
    pub root: PathBuf,
    pub project: ProjectSnapshot,
    pub queue: ForegroundQueue,
    pub console: VecDeque<String>,
    pub console_input: String,
    pub last_notice: String,
    pub project_cli_input: String,
    pub intelligence: ProjectCensus,
    pub toolchains: Vec<ToolchainProbe>,
}

impl SharedUiState {
    pub fn new(root: PathBuf, project: ProjectSnapshot) -> Self {
        let mut console = VecDeque::new();
        console.push_back(format!("[PASS] Forge Native GUI ready: {}", NativeIdentity::current().build));
        console.push_back(format!("[INFO] Root: {}", root.display()));
        console.push_back("[INFO] Python ForgePY remains operational authority during SHADOW migration.".into());
        let intelligence = census(&root).unwrap_or_else(|_| ProjectCensus {
            scanned_entries: 0,
            truncated: false,
            build_systems: Vec::new(),
            language_counts: Vec::new(),
            markers: Vec::new(),
            nested_roots: Vec::new(),
            operations: Vec::new(),
            confidence: 0,
        });
        let toolchains = probe_all();
        Self {
            root,
            project,
            queue: ForegroundQueue::default(),
            console,
            console_input: String::new(),
            last_notice: "Native shell ready".into(),
            project_cli_input: String::new(),
            intelligence,
            toolchains,
        }
    }

    pub fn push_console(&mut self, line: impl Into<String>) {
        self.console.push_back(line.into());
        while self.console.len() > MAX_CONSOLE_LINES { self.console.pop_front(); }
    }

    pub fn refresh_project_context(&mut self) {
        if let Ok(project) = probe_project(&self.root) { self.project = project; }
        match census(&self.root) {
            Ok(row) => {
                let systems = row.build_systems.len();
                let operations = row.operations.len();
                self.intelligence = row;
                self.push_console(format!("[PASS] Project Intelligence refreshed: {systems} build-system marker family(s), {operations} inferred operation(s)."));
            }
            Err(err) => self.push_console(format!("[WARN] Project Intelligence refresh failed: {err}")),
        }
        self.toolchains = probe_all();
    }

    pub fn poll_operations(&mut self) {
        for event in self.queue.poll() {
            match event {
                OperationEvent::Started { label, .. } => self.push_console(format!("[RUNNING] {label}")),
                OperationEvent::Output { line, stderr, .. } => {
                    self.push_console(if stderr { format!("[ERR] {line}") } else { line });
                }
                OperationEvent::Finished { label, exit_code, stopped, .. } => {
                    let state = if stopped { "STOPPED" } else if exit_code == 0 { "PASS" } else { "FAIL" };
                    self.last_notice = format!("{label}: {state}");
                    self.push_console(format!("[{state}] {label} (exit {exit_code})"));
                }
            }
        }
    }

    pub fn submit(&mut self, label: &str, command: &str) {
        let project_id = super::operations::project_id(&self.root);
        if self.queue.enqueue(project_id, label, command, self.root.clone()).is_some() {
            self.push_console(format!("[QUEUED] {label}"));
        } else {
            self.push_console(format!("[INFO] Duplicate request coalesced: {label}"));
        }
    }

    pub fn execute_console_command(&mut self) {
        let command = self.console_input.trim().to_string();
        self.console_input.clear();
        if command.is_empty() { return; }
        self.push_console(format!("> {command}"));
        match command.to_ascii_lowercase().as_str() {
            "full" | "gate" | "full gate" => self.submit("Full Gate", "full"),
            "build" => self.submit("Build", "build"),
            "test" | "self-test" => self.submit("Test", "project.self-test"),
            "refresh" | "scan" => self.refresh_project_context(),
            "stop" | "cancel" | "interrupt" => {
                if self.queue.stop_active() { self.push_console("[STOP] Cancellation requested."); }
                else { self.push_console("[INFO] No active operation to stop."); }
            }
            "clear" => self.console.clear(),
            "status" => {
                self.push_console(format!(
                    "[STATUS] Project={} Contract={} Confidence={} Queue={} Active={}",
                    self.project.name,
                    if self.project.contract_ready { "ready" } else { "incomplete" },
                    self.intelligence.confidence,
                    self.queue.pending_len(),
                    self.queue.active_label().unwrap_or("idle"),
                ));
            }
            other => self.push_console(format!("[WARN] Unknown Forge Console command: {other}. Allowed: full, build, test, refresh, status, stop, clear.")),
        }
    }
}

pub fn dock_for_preset(preset: LayoutPreset) -> DockState<WorkspaceTab> {
    match preset {
        LayoutPreset::Forge => {
            let mut dock = DockState::new(vec![WorkspaceTab::Dashboard]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.64, vec![WorkspaceTab::ForgeConsole]);
            dock
        }
        LayoutPreset::Operations => {
            let mut dock = DockState::new(vec![WorkspaceTab::OperationQueue]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.58, vec![WorkspaceTab::ForgeConsole]);
            dock
        }
        LayoutPreset::Intelligence => {
            let mut dock = DockState::new(vec![WorkspaceTab::ProjectIntelligence]);
            dock.main_surface_mut().split_right(NodeIndex::root(), 0.66, vec![WorkspaceTab::Dashboard]);
            dock
        }
    }
}

pub fn default_dock() -> DockState<WorkspaceTab> { dock_for_preset(LayoutPreset::Forge) }

pub fn ensure_tab(dock: &mut DockState<WorkspaceTab>, tab: WorkspaceTab) {
    if dock.iter_all_tabs().any(|(_, existing)| *existing == tab) { return; }
    dock.push_to_focused_leaf(tab);
}

pub struct ForgeTabViewer<'a> {
    pub shared: &'a mut SharedUiState,
}

impl TabViewer for ForgeTabViewer<'_> {
    type Tab = WorkspaceTab;

    fn id(&mut self, tab: &mut Self::Tab) -> egui::Id { egui::Id::new(*tab) }
    fn title(&mut self, tab: &mut Self::Tab) -> egui::WidgetText { tab.title().into() }

    fn ui(&mut self, ui: &mut Ui, tab: &mut Self::Tab) {
        match tab {
            WorkspaceTab::Dashboard => dashboard(ui, self.shared),
            WorkspaceTab::ForgeConsole => forge_console(ui, self.shared),
            WorkspaceTab::OperationQueue => operation_queue(ui, self.shared),
            WorkspaceTab::ProjectIntelligence => project_intelligence(ui, self.shared),
            WorkspaceTab::NativeMigration => native_migration(ui, self.shared),
            WorkspaceTab::ProjectCli => project_cli(ui, self.shared),
            WorkspaceTab::Vault => vault(ui, self.shared),
            WorkspaceTab::Workspace => workspace(ui, self.shared),
            WorkspaceTab::Settings => settings_page(ui, self.shared),
        }
    }
}

pub fn dock_style(ui: &Ui) -> Style { Style::from_egui(ui.style().as_ref()) }

fn heading(ui: &mut Ui, title: &str, subtitle: &str) {
    ui.label(RichText::new(title).size(19.0).strong().color(theme::TEXT));
    ui.label(RichText::new(subtitle).size(11.0).color(theme::MUTED));
    ui.add_space(8.0);
}

fn section(ui: &mut Ui, title: &str, add: impl FnOnce(&mut Ui)) {
    theme::card_frame().show(ui, |ui| {
        ui.label(RichText::new(title).strong().color(theme::CYAN));
        ui.add_space(5.0);
        add(ui);
    });
    ui.add_space(8.0);
}

fn dashboard(ui: &mut Ui, shared: &mut SharedUiState) {
    ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        heading(ui, "ForgePY Control", "Native project operations shell with Python ForgePY retained as certified backend authority during SHADOW.");
        section(ui, "Application Authority", |ui| {
            let id = NativeIdentity::current();
            egui::Grid::new("native-authority-grid").num_columns(2).spacing([12.0, 3.0]).show(ui, |ui| {
                ui.label("Native candidate"); ui.label(RichText::new(id.build).color(theme::TEXT)); ui.end_row();
                ui.label("Authority phase"); ui.label(RichText::new(id.phase.as_str()).color(theme::YELLOW)); ui.end_row();
                ui.label("Project root"); ui.label(shared.root.display().to_string()); ui.end_row();
                ui.label("Contract"); ui.label(if shared.project.contract_ready { "Ready" } else { "Inferred / no Forge contract" }); ui.end_row();
                ui.label("Intelligence confidence"); ui.label(format!("{}%", shared.intelligence.confidence)); ui.end_row();
                ui.label("Toolchains available"); ui.label(format!("{} / {}", ready_count(&shared.toolchains), shared.toolchains.len())); ui.end_row();
            });
        });
        section(ui, "Primary Operations", |ui| {
            ui.horizontal_wrapped(|ui| {
                if ui.add(egui::Button::new("Full Gate / Certify GREEN").fill(theme::CYAN)).clicked() { shared.submit("Full Gate", "full"); }
                if ui.button("Build").clicked() { shared.submit("Build", "build"); }
                if ui.button("Test").clicked() { shared.submit("Test", "project.self-test"); }
                if ui.button("Rust SHADOW Gate").clicked() { shared.submit("Rust SHADOW Gate", "gate.rust-shadow"); }
            });
        });
        section(ui, "Project Intelligence", |ui| {
            ui.label(format!("{} build-system family(s), {} language family(s), {} inferred operation(s), {} nested root hint(s).",
                shared.intelligence.build_systems.len(), shared.intelligence.language_counts.len(), shared.intelligence.operations.len(), shared.intelligence.nested_roots.len()));
            ui.horizontal_wrapped(|ui| {
                if ui.button("Refresh Intelligence").clicked() { shared.refresh_project_context(); }
                if ui.button("Show Detection Evidence").clicked() {
                    for marker in shared.intelligence.markers.clone() {
                        shared.push_console(format!("[INTEL] {} · {}", marker.kind, marker.path.display()));
                    }
                }
            });
        });
        section(ui, "Self Update / Source Authority", |ui| {
            ui.horizontal_wrapped(|ui| {
                if ui.button("Check Downloads").clicked() { shared.push_console("[INFO] Download intake remains Python-authority during native SHADOW."); }
                if ui.button("Patch Review / Route").clicked() { shared.push_console("[INFO] Patch intelligence will consume the same project fingerprints in a later native wave."); }
                if ui.button("Source Control").clicked() { shared.push_console("[INFO] Native Source Control widget remains parity-pending."); }
                if ui.button("Artifact Central").clicked() { shared.push_console("[INFO] Artifact Central is Python-owned during SHADOW."); }
            });
        });
        section(ui, "Forge Native Rust Migration · SHADOW", |ui| {
            ui.label("The graphical shell, docking/widget model, console and foreground queue are native. Backend authority moves only after parity evidence is GREEN.");
            ui.horizontal_wrapped(|ui| {
                if ui.button("Parity Matrix").clicked() {
                    for row in foundation_matrix() { shared.push_console(format!("[PARITY] {} = {} · {}", row.capability, row.state.as_str(), row.note)); }
                }
                if ui.button("Build Native").clicked() { shared.submit("Build Native", "build.rust-forge"); }
                if ui.button("Rust SHADOW Gate").clicked() { shared.submit("Rust SHADOW Gate", "gate.rust-shadow"); }
            });
        });
    });
}

fn forge_console(ui: &mut Ui, shared: &mut SharedUiState) {
    let available = ui.available_height();
    let composer_height = 34.0;
    ScrollArea::vertical().stick_to_bottom(true).max_height((available - composer_height).max(80.0)).show(ui, |ui| {
        for line in &shared.console {
            let color = if line.contains("[PASS]") { theme::GREEN }
                else if line.contains("[FAIL]") || line.contains("[ERR]") { theme::RED }
                else if line.contains("[WARN]") { theme::YELLOW }
                else if line.contains("[QUEUED]") || line.contains("[RUNNING]") || line.starts_with('>') { theme::CYAN }
                else { theme::TEXT };
            ui.label(RichText::new(line).monospace().size(11.0).color(color));
        }
    });
    ui.separator();
    ui.horizontal(|ui| {
        ui.label(RichText::new(">").monospace().color(theme::CYAN));
        let edit = ui.add_sized([ui.available_width() - 110.0, 26.0], egui::TextEdit::singleline(&mut shared.console_input).hint_text("Forge command…"));
        let send_enter = edit.lost_focus() && ui.input(|input| input.key_pressed(egui::Key::Enter));
        if ui.add_sized([52.0, 26.0], egui::Button::new("Send").fill(theme::CYAN)).clicked() || send_enter { shared.execute_console_command(); }
        let stop = egui::Button::new("Stop").fill(if shared.queue.active_label().is_some() { theme::RED } else { theme::BG_PANEL_ALT });
        if ui.add_sized([52.0, 26.0], stop).clicked() {
            if shared.queue.stop_active() { shared.push_console("[STOP] Cancellation requested for the active operation."); }
        }
    });
}

fn operation_queue(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Foreground Operations", "One active project-bound operation; subsequent work is queued, duplicates coalesce, and Stop interrupts the active process tree.");
    ScrollArea::vertical().show(ui, |ui| {
        section(ui, "Active", |ui| {
            if let Some(active) = shared.queue.active_snapshot() {
                ui.horizontal(|ui| {
                    ui.label(RichText::new("RUNNING").strong().color(theme::CYAN));
                    ui.label(RichText::new(active.label).strong());
                    ui.label(RichText::new(format!("{}s", shared.queue.active_elapsed_secs().unwrap_or(0))).color(theme::MUTED));
                    if ui.button("Stop").clicked() { shared.queue.stop_active(); }
                });
                ui.label(RichText::new(active.root.display().to_string()).size(10.0).color(theme::MUTED));
            } else {
                ui.label(RichText::new("No active operation").color(theme::MUTED));
            }
        });
        section(ui, "Queued", |ui| {
            let pending = shared.queue.pending_snapshot();
            if pending.is_empty() {
                ui.label(RichText::new("Queue empty").color(theme::MUTED));
            }
            for row in pending {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(format!("#{}", row.id)).monospace().color(theme::MUTED));
                    ui.label(RichText::new(&row.label).strong());
                    ui.label(RichText::new(&row.command).monospace().size(10.0).color(theme::MUTED));
                    if ui.button("Cancel queued").clicked() { shared.queue.cancel_pending(row.id); }
                });
            }
            if shared.queue.pending_len() > 0 && ui.button("Clear Pending Queue").clicked() { shared.queue.clear_pending(); }
        });
        section(ui, "Last Run", |ui| {
            if let Some(last) = &shared.queue.last_run {
                ui.label(RichText::new(format!("{} · {} · exit {}", last.label, last.state, last.exit_code)).color(status_color(&last.state)));
            } else {
                ui.label(RichText::new("No completed native-shell operation yet").color(theme::MUTED));
            }
        });
    });
}

fn project_intelligence(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Project Intelligence", "Zero-tooling census: infer project structure, build systems, languages, nested roots, toolchains and safe candidate operations from evidence.");
    if ui.button("Refresh Project Intelligence").clicked() { shared.refresh_project_context(); }
    ui.add_space(8.0);
    ScrollArea::vertical().show(ui, |ui| {
        section(ui, "Census", |ui| {
            ui.label(format!("Confidence: {}%", shared.intelligence.confidence));
            ui.label(format!("Entries inspected: {}{}", shared.intelligence.scanned_entries, if shared.intelligence.truncated { " (bounded/truncated)" } else { "" }));
            ui.label(format!("Build-system families: {}", shared.intelligence.build_systems.len()));
            ui.label(format!("Nested project-root hints: {}", shared.intelligence.nested_roots.len()));
        });
        section(ui, "Build Systems", |ui| {
            if shared.intelligence.build_systems.is_empty() { ui.label(RichText::new("No known build-system marker found yet").color(theme::MUTED)); }
            for value in &shared.intelligence.build_systems { ui.label(format!("• {value}")); }
        });
        section(ui, "Languages", |ui| {
            for (name, count) in shared.intelligence.language_counts.iter().take(12) { ui.label(format!("{name}: {count} source file(s)")); }
        });
        section(ui, "Toolchains", |ui| {
            egui::Grid::new("forge-native-toolchains").striped(true).num_columns(3).spacing([12.0, 5.0]).show(ui, |ui| {
                ui.strong("Tool"); ui.strong("State"); ui.strong("Resolved path"); ui.end_row();
                for row in &shared.toolchains {
                    ui.label(row.label);
                    ui.label(RichText::new(if row.ready() { "READY" } else { "MISSING" }).color(if row.ready() { theme::GREEN } else { theme::MUTED }));
                    ui.label(RichText::new(row.path.as_ref().map(|value| value.display().to_string()).unwrap_or_else(|| row.program.to_string())).size(10.0).color(theme::MUTED));
                    ui.end_row();
                }
            });
        });
        section(ui, "Synthesized Operations", |ui| {
            if shared.intelligence.operations.is_empty() { ui.label(RichText::new("No safe operation candidates inferred").color(theme::MUTED)); }
            for row in &shared.intelligence.operations {
                ui.horizontal_wrapped(|ui| {
                    ui.label(RichText::new(&row.label).strong());
                    ui.label(RichText::new(format!("{}%", row.confidence)).color(theme::CYAN));
                    ui.label(RichText::new(format!("{} {}", row.program, row.args.join(" "))).monospace().size(10.0).color(theme::MUTED));
                });
            }
            ui.label(RichText::new("Inferred operations are evidence only in this wave; execution remains governed by existing PCC/project commands until direct-operation policy is certified.").size(10.0).color(theme::MUTED));
        });
        section(ui, "Evidence", |ui| {
            for marker in shared.intelligence.markers.iter().take(30) { ui.label(format!("{} · {}", marker.kind, marker.path.display())); }
        });
    });
}

fn native_migration(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Native Migration", "Parity is explicit. A Rust subsystem does not become authoritative until its row is certified.");
    ScrollArea::vertical().show(ui, |ui| {
        egui::Grid::new("native-parity-grid").striped(true).num_columns(3).spacing([14.0, 6.0]).show(ui, |ui| {
            ui.strong("Capability"); ui.strong("State"); ui.strong("Evidence"); ui.end_row();
            for row in foundation_matrix() {
                ui.label(row.capability);
                let color = match row.state.as_str() { "PASS" => theme::GREEN, "MISSING" => theme::RED, _ => theme::YELLOW };
                ui.label(RichText::new(row.state.as_str()).color(color).strong());
                ui.label(row.note);
                ui.end_row();
            }
        });
        ui.add_space(10.0);
        if ui.button("Queue Rust SHADOW Gate").clicked() { shared.submit("Rust SHADOW Gate", "gate.rust-shadow"); }
    });
}

fn project_cli(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Project CLI", "Safe project-operation aliases. Arbitrary shell execution is deliberately not enabled in SHADOW.");
    ui.horizontal(|ui| {
        let response = ui.add_sized([ui.available_width() - 80.0, 28.0], egui::TextEdit::singleline(&mut shared.project_cli_input).hint_text("full | build | test | refresh | status"));
        if ui.button("Run").clicked() || (response.lost_focus() && ui.input(|input| input.key_pressed(egui::Key::Enter))) {
            shared.console_input = std::mem::take(&mut shared.project_cli_input);
            shared.execute_console_command();
        }
    });
    ui.add_space(8.0);
    ui.label(RichText::new("All project operations flow through the same foreground queue and retain the project/root they were created for.").color(theme::MUTED));
}

fn vault(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Vault", "Native Vault catalog/storage is not authoritative yet; this surface is the migration landing zone.");
    let snapshot = settings::snapshot(&shared.root);
    section(ui, "Storage Authority", |ui| {
        ui.label(format!("Vault root: {}", snapshot.vault_root.display()));
        ui.label(format!("Project registry: {}", snapshot.registry_path.display()));
        ui.label(format!("Resolution source: {}", snapshot.source));
    });
}

fn workspace(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Workspace", "Dockable project work surface. Widgets can be tabbed, split, resized, closed, reopened and undocked.");
    section(ui, "Selected Project", |ui| {
        ui.label(format!("Name: {}", shared.project.name));
        ui.label(format!("Root: {}", shared.root.display()));
        ui.label(format!("Icon: {}", shared.project.icon.as_ref().map(|p| p.display().to_string()).unwrap_or_else(|| "No icon discovered".into())));
        ui.label(format!("Project Intelligence: {}% confidence", shared.intelligence.confidence));
    });
}

fn settings_page(ui: &mut Ui, shared: &mut SharedUiState) {
    heading(ui, "Settings", "Native settings authority is intentionally read-mostly until schema migration is certified.");
    section(ui, "Native Shell", |ui| {
        ui.label("Dock layout persistence: enabled");
        ui.label("Layout presets + lock: enabled");
        ui.label("Project-aware icon loading: enabled");
        ui.label("Foreground operation queue: enabled");
        ui.label("Project Intelligence census: enabled");
        ui.label("Python authority bridge: enabled");
        ui.label(format!("Root: {}", shared.root.display()));
    });
}

pub fn health_score(shared: &SharedUiState) -> u8 {
    let mut score = 40u8;
    if shared.root.is_dir() { score += 10; }
    if shared.project.contract_ready { score += 10; }
    if shared.project.icon.is_some() { score += 5; }
    if shared.root.join(".git").exists() { score += 10; }
    if shared.root.join("FORGEPY_PACKAGE_MANIFEST.json").is_file() { score += 10; }
    if shared.intelligence.confidence >= 75 { score += 10; }
    if ready_count(&shared.toolchains) >= 3 { score += 5; }
    score.min(100)
}

pub fn status_color(state: &str) -> Color32 {
    match state { "PASS" => theme::GREEN, "FAIL" | "STOPPED" => theme::RED, _ => theme::YELLOW }
}

pub fn divider(ui: &mut Ui) { ui.add(egui::Separator::default().spacing(6.0)); }

pub fn queue_summary(ui: &mut Ui, shared: &SharedUiState) {
    if let Some(active) = shared.queue.active_label() {
        ui.label(RichText::new(format!("RUNNING · {active} · {}s", shared.queue.active_elapsed_secs().unwrap_or(0))).color(theme::CYAN));
    } else {
        ui.label(RichText::new("IDLE").color(theme::MUTED));
    }
    if shared.queue.pending_len() > 0 {
        ui.label(RichText::new(format!("{} queued", shared.queue.pending_len())).color(theme::YELLOW));
    }
}

pub fn border_stroke() -> Stroke { Stroke::new(1.0, theme::BORDER) }

pub fn project_icon_uri(path: &Path) -> String {
    let normalized = path.display().to_string().replace('\\', "/");
    format!("file://{normalized}")
}
