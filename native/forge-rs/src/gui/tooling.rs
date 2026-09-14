use eframe::egui::{self, RichText, ScrollArea, Ui};
use serde::{Deserialize, Serialize};

use super::theme;
use super::widgets::{status_color, SharedUiState};

pub const TOOLING_WORKBENCH_VERSION: &str = "FORGE-NATIVE-TOOLING-WORKBENCH-1.0-F950";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommandRisk {
    Read,
    Write,
    Governed,
}

impl CommandRisk {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Read => "READ",
            Self::Write => "WRITE",
            Self::Governed => "GOVERNED",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommandCategory {
    Quality,
    Build,
    Runtime,
    Source,
    Diagnostics,
    Assets,
    Updates,
    Native,
}

impl CommandCategory {
    pub const ALL: [Self; 8] = [
        Self::Quality,
        Self::Build,
        Self::Runtime,
        Self::Source,
        Self::Diagnostics,
        Self::Assets,
        Self::Updates,
        Self::Native,
    ];

    pub const fn label(self) -> &'static str {
        match self {
            Self::Quality => "QUALITY",
            Self::Build => "BUILD",
            Self::Runtime => "RUNTIME",
            Self::Source => "SOURCE",
            Self::Diagnostics => "DIAGNOSTICS",
            Self::Assets => "ASSETS",
            Self::Updates => "UPDATES",
            Self::Native => "NATIVE",
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub struct CommandDescriptor {
    pub id: &'static str,
    pub label: &'static str,
    pub alias: &'static str,
    pub category: CommandCategory,
    pub risk: CommandRisk,
    pub summary: &'static str,
    pub requires_internal_pcc: bool,
    pub favorite_default: bool,
}

macro_rules! cmd {
    ($id:expr,$label:expr,$alias:expr,$cat:ident,$risk:ident,$summary:expr,$pcc:expr,$favorite:expr) => {
        CommandDescriptor {
            id: $id,
            label: $label,
            alias: $alias,
            category: CommandCategory::$cat,
            risk: CommandRisk::$risk,
            summary: $summary,
            requires_internal_pcc: $pcc,
            favorite_default: $favorite,
        }
    };
}

pub static COMMANDS: [CommandDescriptor; 18] = [
    cmd!("gate.full", "Full Gate / Certify GREEN", "full", Quality, Governed, "Run the project authority's complete quality/certification gate.", false, true),
    cmd!("gate.quick", "Quick Gate", "quick", Quality, Governed, "Run the bounded fast validation lane when the project provides one.", false, false),
    cmd!("build", "Build", "build", Build, Write, "Build the selected project through the governed provider route.", false, true),
    cmd!("build.release", "Build Release", "build-release", Build, Write, "Build the project's release configuration through its provider.", false, false),
    cmd!("test", "Project Self Test", "project.self-test", Quality, Governed, "Run the project-owned self-test/certification surface.", false, true),
    cmd!("run", "Run / Launch GUI", "launch-gui", Runtime, Write, "Launch the selected project using its declared run provider.", false, true),
    cmd!("doctor", "Project Doctor", "doctor", Diagnostics, Read, "Inspect project health and provider/tooling readiness.", false, false),
    cmd!("debug.bundle", "Debug Bundle", "debug-bundle", Diagnostics, Write, "Package the governed diagnostic/debug handoff.", false, false),
    cmd!("git.status", "Git Status", "git-status", Source, Read, "Read source-control status for the selected project.", false, true),
    cmd!("git.review", "Git Review", "git-review", Source, Read, "Open the governed source review lane.", false, false),
    cmd!("asset.status", "Asset Status", "asset-status", Assets, Read, "Inspect hash/provenance-bound asset requirements.", false, false),
    cmd!("asset.diagnose", "Find Missing Assets", "asset-diagnose", Assets, Read, "Resolve missing project assets against known Vault/Artifact sources.", false, false),
    cmd!("asset.hydrate", "Hydrate Assets", "asset-hydrate", Assets, Governed, "Hydrate verified asset requirements before gate execution.", false, false),
    cmd!("native.status", "Rust Successor Status", "audit.rust-migration", Native, Read, "Inspect native successor status without changing authority.", false, false),
    cmd!("native.build", "Build Native Rust", "build.rust-forge", Native, Write, "Build the native Forge Rust candidate.", false, false),
    cmd!("native.test", "Test Native Rust", "test.rust-forge", Native, Read, "Run the native Rust successor test lane.", false, false),
    cmd!("native.run", "Run Native Rust", "run.rust-forge", Native, Read, "Launch the native Rust successor through its governed lane.", false, false),
    cmd!("native.shadow", "Rust SHADOW Gate", "gate.rust-shadow", Native, Governed, "Compile/test the native successor lane without changing authority.", false, true),
];

pub fn command_by_id(id: &str) -> Option<&'static CommandDescriptor> {
    COMMANDS.iter().find(|row| row.id == id)
}

pub fn command_by_alias(alias: &str) -> Option<&'static CommandDescriptor> {
    let normalized = alias.trim().to_ascii_lowercase();
    COMMANDS.iter().find(|row| row.alias == normalized)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolingHistoryEntry {
    pub label: String,
    pub alias: String,
    pub state: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ToolingUiState {
    pub search: String,
    pub selected_id: String,
    pub safe_alias_input: String,
    pub favorites: Vec<String>,
    pub favorites_only: bool,
    pub history: Vec<ToolingHistoryEntry>,
}

impl Default for ToolingUiState {
    fn default() -> Self {
        Self {
            search: String::new(),
            selected_id: "gate.full".into(),
            safe_alias_input: String::new(),
            favorites: COMMANDS.iter().filter(|row| row.favorite_default).map(|row| row.id.to_string()).collect(),
            favorites_only: false,
            history: Vec::new(),
        }
    }
}

impl ToolingUiState {
    pub fn selected(&self) -> &'static CommandDescriptor {
        command_by_id(&self.selected_id).unwrap_or(&COMMANDS[0])
    }

    pub fn is_favorite(&self, id: &str) -> bool { self.favorites.iter().any(|row| row == id) }

    pub fn toggle_favorite(&mut self, id: &str) {
        if let Some(index) = self.favorites.iter().position(|row| row == id) {
            self.favorites.remove(index);
        } else {
            self.favorites.push(id.to_string());
        }
    }

    pub fn execute(&mut self, descriptor: CommandDescriptor, shared: &mut SharedUiState) {
        if descriptor.requires_internal_pcc && !shared.has_internal_pcc() {
            shared.push_console(format!("[WARN] {} requires an Internal PCC for this project.", descriptor.label));
            self.history.insert(0, ToolingHistoryEntry { label: descriptor.label.into(), alias: descriptor.alias.into(), state: "UNAVAILABLE".into() });
            return;
        }
        shared.submit(descriptor.label, descriptor.alias);
        self.history.insert(0, ToolingHistoryEntry { label: descriptor.label.into(), alias: descriptor.alias.into(), state: "QUEUED".into() });
        self.history.truncate(24);
    }

    pub fn execute_safe_alias(&mut self, shared: &mut SharedUiState) {
        let alias = self.safe_alias_input.trim().to_ascii_lowercase();
        if alias.is_empty() { return; }
        if let Some(command) = command_by_alias(&alias) {
            self.selected_id = command.id.into();
            self.execute(*command, shared);
            self.safe_alias_input.clear();
        } else {
            shared.push_console(format!("[WARN] Unknown project alias '{alias}'. The visual CLI only runs registered commands; arbitrary shell execution remains disabled."));
        }
    }
}

fn command_available(command: &CommandDescriptor, shared: &SharedUiState) -> bool {
    if command.requires_internal_pcc && !shared.has_internal_pcc() { return false; }
    if command.category == CommandCategory::Native {
        return shared.root.join("native/forge-rs/Cargo.toml").is_file()
            || shared.root.join("tools/rust/ForgeRustLane.py").is_file();
    }
    true
}

fn risk_color(risk: CommandRisk) -> egui::Color32 {
    match risk {
        CommandRisk::Read => theme::GREEN,
        CommandRisk::Write => theme::YELLOW,
        CommandRisk::Governed => theme::CYAN,
    }
}

pub fn render_catalog(ui: &mut Ui, shared: &mut SharedUiState, tooling: &mut ToolingUiState) {
    ui.label(RichText::new("Tooling Catalog").size(18.0).strong().color(theme::TEXT));
    ui.label(RichText::new("Search and select governed CLI operations. The catalog is the visual front-end to project tooling, not a separate command authority.").size(10.0).color(theme::MUTED));
    ui.add_space(8.0);
    ui.horizontal(|ui| {
        ui.add_sized([ui.available_width() - 105.0, 27.0], egui::TextEdit::singleline(&mut tooling.search).hint_text("Search tools / commands…"));
        ui.checkbox(&mut tooling.favorites_only, "Favorites");
    });
    ui.add_space(6.0);

    let query = tooling.search.trim().to_ascii_lowercase();
    ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        for category in CommandCategory::ALL {
            let rows: Vec<_> = COMMANDS.iter().filter(|row| {
                row.category == category
                    && (!tooling.favorites_only || tooling.is_favorite(row.id))
                    && (query.is_empty()
                        || row.label.to_ascii_lowercase().contains(&query)
                        || row.alias.contains(&query)
                        || row.summary.to_ascii_lowercase().contains(&query))
            }).collect();
            if rows.is_empty() { continue; }
            ui.label(RichText::new(category.label()).size(9.0).strong().color(theme::MUTED));
            for command in rows {
                let selected = tooling.selected_id == command.id;
                let available = command_available(command, shared);
                theme::card_frame().show(ui, |ui| {
                    ui.horizontal(|ui| {
                        let star = if tooling.is_favorite(command.id) { "★" } else { "☆" };
                        if ui.small_button(star).clicked() { tooling.toggle_favorite(command.id); }
                        if ui.selectable_label(selected, command.label).clicked() { tooling.selected_id = command.id.into(); }
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.label(RichText::new(if available { command.risk.label() } else { "UNAVAILABLE" }).size(9.0).color(if available { risk_color(command.risk) } else { theme::RED }));
                        });
                    });
                    ui.label(RichText::new(format!("{} · {}", command.alias, command.summary)).size(9.0).color(theme::MUTED));
                });
                ui.add_space(3.0);
            }
            ui.add_space(5.0);
        }
        if !shared.intelligence.operations.is_empty() {
            ui.separator();
            ui.label(RichText::new("DETECTED PROJECT TOOLING").size(9.0).strong().color(theme::MUTED));
            ui.label(RichText::new("Project Intelligence discovered these native build-system operations. They are evidence for provider routing; execution remains governed by registered Forge commands.").size(9.0).color(theme::MUTED));
            for op in &shared.intelligence.operations {
                theme::card_frame().show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.strong(&op.label);
                        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                            ui.label(RichText::new(format!("{}%", op.confidence)).size(9.0).color(theme::CYAN));
                        });
                    });
                    ui.monospace(format!("{} {}", op.program, op.args.join(" ")));
                    ui.label(RichText::new(if op.read_only { "Detected read-only operation" } else { "Detected mutating operation" }).size(9.0).color(theme::MUTED));
                });
                ui.add_space(3.0);
            }
        }
    });
}

pub fn render_cli(ui: &mut Ui, shared: &mut SharedUiState, tooling: &mut ToolingUiState) {
    let command = *tooling.selected();
    let available = command_available(&command, shared);
    ui.label(RichText::new("Visual Project CLI").size(18.0).strong().color(theme::TEXT));
    ui.label(RichText::new("Select commands from Project Tools or enter a registered alias. Execution stays project-bound and uses the shared foreground queue.").size(10.0).color(theme::MUTED));
    ui.add_space(8.0);

    theme::card_frame().show(ui, |ui| {
        ui.horizontal(|ui| {
            ui.label(RichText::new(command.label).size(16.0).strong());
            ui.label(RichText::new(command.category.label()).size(9.0).color(theme::MUTED));
            ui.label(RichText::new(command.risk.label()).size(9.0).color(risk_color(command.risk)));
        });
        ui.label(RichText::new(command.summary).color(theme::MUTED));
        ui.separator();
        egui::Grid::new("forge-tooling-command-detail").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
            ui.label("Command ID"); ui.monospace(command.id); ui.end_row();
            ui.label("CLI alias"); ui.monospace(command.alias); ui.end_row();
            ui.label("Provider requirement"); ui.label(if command.requires_internal_pcc { "Internal PCC" } else { "Best available provider" }); ui.end_row();
            ui.label("Availability"); ui.label(RichText::new(if available { "READY" } else { "UNAVAILABLE" }).color(if available { theme::GREEN } else { theme::RED })); ui.end_row();
        });
        ui.add_space(6.0);
        ui.horizontal(|ui| {
            let execute = ui.add_enabled(available, egui::Button::new("Execute").fill(theme::CYAN));
            if execute.clicked() { tooling.execute(command, shared); }
            let favorite = if tooling.is_favorite(command.id) { "Remove Favorite" } else { "Add Favorite" };
            if ui.button(favorite).clicked() { tooling.toggle_favorite(command.id); }
        });
    });

    ui.add_space(8.0);
    ui.label(RichText::new("Safe Alias Runner").strong().color(theme::CYAN));
    ui.horizontal(|ui| {
        let response = ui.add_sized([ui.available_width() - 72.0, 28.0], egui::TextEdit::singleline(&mut tooling.safe_alias_input).hint_text("full | build | project.self-test | git-status | …"));
        if ui.button("Run").clicked() || (response.lost_focus() && ui.input(|input| input.key_pressed(egui::Key::Enter))) {
            tooling.execute_safe_alias(shared);
        }
    });
    ui.label(RichText::new("Only registered aliases are accepted. Arbitrary shell execution remains deliberately disabled in SHADOW.").size(9.0).color(theme::MUTED));

    ui.add_space(8.0);
    ui.label(RichText::new("Favorites").strong().color(theme::CYAN));
    ui.horizontal_wrapped(|ui| {
        let favorites = tooling.favorites.clone();
        for id in favorites {
            if let Some(row) = command_by_id(&id) {
                if ui.small_button(row.label).clicked() { tooling.selected_id = row.id.into(); }
            }
        }
    });
}

pub fn render_operations(ui: &mut Ui, shared: &mut SharedUiState, tooling: &mut ToolingUiState) {
    ui.label(RichText::new("Operation Queue").size(18.0).strong().color(theme::TEXT));
    ui.label(RichText::new("One project-bound execution lane. Visual CLI, quick actions and tool panels all converge here.").size(10.0).color(theme::MUTED));
    ui.add_space(8.0);

    theme::card_frame().show(ui, |ui| {
        ui.label(RichText::new("Active").size(10.0).strong().color(theme::CYAN));
        if let Some(active) = shared.queue.active_snapshot() {
            ui.label(RichText::new(&active.label).strong());
            ui.monospace(&active.command);
            ui.label(RichText::new(active.root.display().to_string()).size(9.0).color(theme::MUTED));
            ui.horizontal(|ui| {
                ui.label(format!("{}s", shared.queue.active_elapsed_secs().unwrap_or(0)));
                if ui.button("Stop").clicked() { let _ = shared.queue.stop_active(); }
            });
        } else {
            ui.label(RichText::new("IDLE").color(theme::MUTED));
        }
    });
    ui.add_space(6.0);

    theme::card_frame().show(ui, |ui| {
        ui.horizontal(|ui| {
            ui.label(RichText::new(format!("Queued ({})", shared.queue.pending_len())).strong().color(theme::CYAN));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if shared.queue.pending_len() > 0 && ui.small_button("Clear Pending").clicked() { shared.queue.clear_pending(); }
            });
        });
        for row in shared.queue.pending_snapshot() {
            ui.horizontal(|ui| {
                ui.label(format!("#{}", row.id));
                ui.strong(&row.label);
                ui.monospace(&row.command);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if ui.small_button("Cancel").clicked() { let _ = shared.queue.cancel_pending(row.id); }
                });
            });
        }
    });

    ui.add_space(6.0);
    theme::card_frame().show(ui, |ui| {
        ui.label(RichText::new("Last Completed").strong().color(theme::CYAN));
        if let Some(last) = &shared.queue.last_run {
            ui.horizontal(|ui| {
                ui.label(RichText::new(&last.state).color(status_color(&last.state)));
                ui.strong(&last.label);
                ui.label(format!("exit {}", last.exit_code));
            });
        } else {
            ui.label(RichText::new("No completed operation in this session.").color(theme::MUTED));
        }
    });

    ui.add_space(6.0);
    theme::card_frame().show(ui, |ui| {
        ui.label(RichText::new("Visual CLI History").strong().color(theme::CYAN));
        if tooling.history.is_empty() {
            ui.label(RichText::new("No visual tooling commands submitted this session.").color(theme::MUTED));
        }
        for row in tooling.history.iter().take(12) {
            ui.horizontal(|ui| {
                ui.label(RichText::new(&row.state).size(9.0).color(status_color(&row.state)));
                ui.strong(&row.label);
                ui.monospace(&row.alias);
            });
        }
    });
}
