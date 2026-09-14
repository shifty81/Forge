use std::path::PathBuf;

use eframe::egui::{self, RichText};
use egui_dock::TabViewer;

use crate::project::{probe_project, ProjectSnapshot};

use super::model::{PersistedShellState, ToolPanel};
use super::registry;
use super::theme;
use super::tool_host::ToolHostKind;
use super::tooling::ToolingUiState;
use super::widgets::SharedUiState;
use super::{ForgePanelViewer, PanelIntent};

pub fn run_native_tool(root: PathBuf, panel: ToolPanel) -> eframe::Result {
    let project = probe_project(&root).unwrap_or_else(|_| ProjectSnapshot {
        root: root.clone(),
        name: root.file_name().and_then(|value| value.to_str()).unwrap_or("Project").to_string(),
        contract_ready: false,
        icon: None,
    });
    let descriptor = registry::descriptor(panel);
    let viewport = egui::ViewportBuilder::default()
        .with_title(format!("Forge Tool — {} — {}", descriptor.title, project.name))
        .with_inner_size(descriptor.preferred_size)
        .with_min_inner_size(descriptor.minimum_size)
        .with_resizable(true)
        .with_drag_and_drop(true);
    let options = eframe::NativeOptions {
        viewport,
        renderer: eframe::Renderer::Glow,
        persist_window: true,
        centered: true,
        ..Default::default()
    };
    eframe::run_native(
        "Forge.Tool",
        options,
        Box::new(move |cc| {
            theme::install(&cc.egui_ctx);
            egui_extras::install_image_loaders(&cc.egui_ctx);
            Ok(Box::new(StandaloneToolApp {
                panel,
                shell: PersistedShellState::default(),
                shared: SharedUiState::new(root.clone(), project.clone()),
                tooling: ToolingUiState::default(),
            }))
        }),
    )
}

struct StandaloneToolApp {
    panel: ToolPanel,
    shell: PersistedShellState,
    shared: SharedUiState,
    tooling: ToolingUiState,
}

impl eframe::App for StandaloneToolApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.shared.poll_operations();
        if self.shared.queue.active_label().is_some() {
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(50));
        }
        egui::Panel::top("forge-tool-project-bar")
            .exact_size(32.0)
            .resizable(false)
            .frame(theme::toolbar_frame())
            .show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(&self.shared.project.name).strong().color(theme::CYAN));
                    ui.separator();
                    ui.label(RichText::new(registry::descriptor(self.panel).title).strong());
                    ui.separator();
                    ui.label(RichText::new("STANDALONE TOOL HOST").size(9.0).color(theme::MUTED));
                });
            });
        let mut intents = Vec::new();
        egui::CentralPanel::no_frame().show(ui, |ui| {
            let mut viewer = ForgePanelViewer {
                shared: &mut self.shared,
                shell: &mut self.shell,
                intents: &mut intents,
                host_kind: ToolHostKind::Standalone,
                tooling: &mut self.tooling,
            };
            viewer.ui(ui, &mut self.panel);
        });
        for intent in intents {
            match intent {
                PanelIntent::Open(panel) | PanelIntent::Standalone(panel) => self.panel = panel,
                PanelIntent::ProjectSection(section) => self.panel = section.tab(),
                PanelIntent::Preset(_) => self.shared.push_console("[INFO] Interface presets are owned by the main Forge interface host."),
                PanelIntent::Locked(_) => {}
            }
        }
    }
}
