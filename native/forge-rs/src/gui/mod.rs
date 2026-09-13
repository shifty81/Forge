pub mod model;
pub mod operations;
pub mod theme;
pub mod widgets;

use std::path::PathBuf;

use eframe::egui::{self, Align, Color32, Layout, RichText, Stroke};
use egui_dock::{DockArea, DockState};

use crate::identity::NativeIdentity;
use crate::project::{probe_project, ProjectSnapshot};

use model::{LayoutPreset, PersistedShellState, PrimarySurface, WorkspaceTab};
use widgets::{default_dock, dock_for_preset, ensure_tab, ForgeTabViewer, SharedUiState};

const DOCK_KEY: &str = "forge-native-dock-v1";
const SHELL_KEY: &str = "forge-native-shell-v1";

pub fn run_native_gui(root: PathBuf) -> eframe::Result {
    let project = probe_project(&root).unwrap_or_else(|_| ProjectSnapshot {
        root: root.clone(),
        name: root.file_name().and_then(|value| value.to_str()).unwrap_or("Project").to_string(),
        contract_ready: false,
        icon: None,
    });
    let mut viewport = egui::ViewportBuilder::default()
        .with_title(format!("ForgePY — {}", project.name))
        .with_inner_size([1850.0, 940.0])
        .with_min_inner_size([1180.0, 700.0])
        .with_resizable(true)
        .with_drag_and_drop(true);
    if let Some(icon_path) = project.icon.as_ref() {
        if let Ok(bytes) = std::fs::read(icon_path) {
            if let Ok(icon) = eframe::icon_data::from_png_bytes(&bytes) { viewport = viewport.with_icon(icon); }
        }
    }
    let native_options = eframe::NativeOptions {
        viewport,
        renderer: eframe::Renderer::Glow,
        persist_window: true,
        centered: true,
        ..Default::default()
    };
    eframe::run_native(
        "ForgePY.Native",
        native_options,
        Box::new(move |cc| Ok(Box::new(ForgeNativeApp::new(cc, root.clone(), project.clone())))),
    )
}

pub struct ForgeNativeApp {
    dock: DockState<WorkspaceTab>,
    shell: PersistedShellState,
    shared: SharedUiState,
    show_widgets: bool,
}

impl ForgeNativeApp {
    fn new(cc: &eframe::CreationContext<'_>, root: PathBuf, project: ProjectSnapshot) -> Self {
        theme::install(&cc.egui_ctx);
        egui_extras::install_image_loaders(&cc.egui_ctx);
        let dock = cc.storage.and_then(|storage| eframe::get_value(storage, DOCK_KEY)).unwrap_or_else(default_dock);
        let shell = cc.storage.and_then(|storage| eframe::get_value(storage, SHELL_KEY)).unwrap_or_default();
        Self { dock, shell, shared: SharedUiState::new(root, project), show_widgets: false }
    }

    fn activate_surface(&mut self, surface: PrimarySurface) {
        self.shell.active_surface = surface;
        ensure_tab(&mut self.dock, surface.tab());
    }

    fn quick_action(&mut self, label: &str) {
        match label {
            "FULL GATE" => self.shared.submit("Full Gate", "full"),
            "BUILD" => self.shared.submit("Build", "build"),
            "TEST" => self.shared.submit("Test", "project.self-test"),
            "RUN" => self.shared.submit("Run", "launch-gui"),
            "REFRESH" => self.shared.refresh_project_context(),
            _ => {}
        }
    }

    fn draw_left_rail(&mut self, ui: &mut egui::Ui) {
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.label(RichText::new("FORGEPY").size(9.5).color(theme::MUTED));
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| { ui.label(RichText::new("‹").color(theme::CYAN)); });
        });
        ui.add_space(12.0);
        for surface in PrimarySurface::ALL {
            let selected = self.shell.active_surface == surface;
            let button = egui::Button::new(RichText::new(surface.title()).strong().color(if selected { theme::CYAN } else { theme::TEXT }))
                .fill(if selected { Color32::from_rgb(14, 28, 35) } else { theme::BG_PANEL });
            if ui.add_sized([102.0, 32.0], button).clicked() { self.activate_surface(surface); }
            ui.add_space(2.0);
        }
    }

    fn draw_quickbar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            if let Some(icon) = self.shared.project.icon.as_ref() {
                ui.add(egui::Image::new(widgets::project_icon_uri(icon)).fit_to_exact_size(egui::vec2(16.0, 16.0)));
            } else {
                let initials: String = self.shared.project.name.chars().filter(|ch| ch.is_alphanumeric()).take(2).collect();
                ui.label(RichText::new(if initials.is_empty() { "PR".into() } else { initials }).strong().color(theme::CYAN));
            }
            ui.label(RichText::new(format!("{} · PROJECT", self.shared.project.name)).strong().color(theme::CYAN));
            ui.separator();
            for label in ["FULL GATE", "BUILD", "TEST", "RUN", "REFRESH"] {
                let fill = if label == "FULL GATE" { theme::CYAN } else { theme::BG_PANEL_ALT };
                if ui.add(egui::Button::new(label).fill(fill)).clicked() { self.quick_action(label); }
            }
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if ui.button("PROJECT CLI").clicked() { ensure_tab(&mut self.dock, WorkspaceTab::ProjectCli); }
                if ui.button("WIDGETS").clicked() { self.show_widgets = !self.show_widgets; }
                if ui.button(format!("QUEUE {}", self.shared.queue.pending_len())).clicked() { ensure_tab(&mut self.dock, WorkspaceTab::OperationQueue); }
                if ui.button("INTEL").clicked() { ensure_tab(&mut self.dock, WorkspaceTab::ProjectIntelligence); }
            });
        });
    }

    fn draw_health(&mut self, ui: &mut egui::Ui) {
        ui.label(RichText::new("FORGEPY HEALTH").size(9.0).color(theme::MUTED));
        ui.add_space(10.0);
        let score = widgets::health_score(&self.shared);
        let desired = egui::vec2(118.0, 78.0);
        let (rect, _) = ui.allocate_exact_size(desired, egui::Sense::hover());
        let center = egui::pos2(rect.center().x, rect.bottom() - 8.0);
        let radius = 48.0;
        let make_arc = |fraction: f32| -> Vec<egui::Pos2> {
            let steps = 48usize;
            (0..=steps).map(|index| {
                let t = index as f32 / steps as f32;
                let angle = std::f32::consts::PI + std::f32::consts::PI * t * fraction;
                egui::pos2(center.x + radius * angle.cos(), center.y + radius * angle.sin())
            }).collect()
        };
        ui.painter().add(egui::Shape::line(make_arc(1.0), Stroke::new(9.0, Color32::from_rgb(38, 47, 53))));
        let score_color = if score >= 75 { theme::GREEN } else if score >= 50 { theme::YELLOW } else { theme::RED };
        ui.painter().add(egui::Shape::line(make_arc(score as f32 / 100.0), Stroke::new(9.0, score_color)));
        ui.painter().text(center - egui::vec2(0.0, 24.0), egui::Align2::CENTER_CENTER, score.to_string(), egui::FontId::proportional(21.0), score_color);
        ui.painter().text(center - egui::vec2(0.0, 7.0), egui::Align2::CENTER_CENTER, "SHADOW", egui::FontId::proportional(9.0), score_color);
        ui.vertical_centered(|ui| { ui.strong(&self.shared.project.name); });
        widgets::divider(ui);
        health_row(ui, "Authority", "PYTHON", theme::YELLOW);
        health_row(ui, "Contract", if self.shared.project.contract_ready { "PASS" } else { "WARN" }, if self.shared.project.contract_ready { theme::GREEN } else { theme::YELLOW });
        health_row(ui, "Native GUI", "PASS", theme::GREEN);
        health_row(ui, "Docking", "PASS", theme::GREEN);
        health_row(ui, "Intelligence", if self.shared.intelligence.confidence >= 75 { "PASS" } else { "SCAN" }, if self.shared.intelligence.confidence >= 75 { theme::GREEN } else { theme::YELLOW });
        health_row(ui, "Queue", if self.shared.queue.active_label().is_some() { "RUN" } else { "IDLE" }, if self.shared.queue.active_label().is_some() { theme::CYAN } else { theme::GREEN });
        widgets::divider(ui);
        ui.label(RichText::new("PROJECT CONTEXT").size(9.0).color(theme::MUTED));
        ui.label(RichText::new(&self.shared.project.name).strong());
        ui.label(RichText::new(NativeIdentity::current().build).size(9.0).color(theme::MUTED));
        ui.label(RichText::new(self.shared.root.display().to_string()).size(9.0).color(theme::TEXT));
        ui.with_layout(Layout::bottom_up(Align::Min), |ui| {
            ui.label(RichText::new("0.5.0-shadow").size(9.0).color(theme::MUTED));
            ui.label(RichText::new("Forge Native").size(10.0).strong());
        });
    }

    fn draw_statusbar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label(RichText::new(format!("ForgePY · {}", NativeIdentity::current().build)).size(9.0).color(theme::TEXT));
            ui.separator();
            widgets::queue_summary(ui, &self.shared);
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                ui.label(RichText::new("0.5.0-shadow · FORGE-NATIVE-F776").size(9.0).color(theme::MUTED));
                if let Some(last) = &self.shared.queue.last_run {
                    ui.label(RichText::new(format!("Last: {} {}", last.label, last.state)).size(9.0).color(widgets::status_color(&last.state)));
                } else {
                    ui.label(RichText::new("Last: —").size(9.0).color(theme::MUTED));
                }
            });
        });
    }

    fn widgets_window(&mut self, ctx: &egui::Context) {
        if !self.show_widgets { return; }
        egui::Window::new("Widgets & Layout").default_width(300.0).collapsible(false).show(ctx, |ui| {
            ui.label(RichText::new("Docking Workspace").strong().color(theme::CYAN));
            ui.label(RichText::new("Widgets can be reopened, tabbed, split, resized and undocked. Lock freezes tab dragging/closing without changing the saved layout.").size(10.0).color(theme::MUTED));
            ui.add_space(6.0);
            ui.horizontal_wrapped(|ui| {
                for preset in LayoutPreset::ALL {
                    let selected = self.shell.preset == preset;
                    if ui.selectable_label(selected, preset.title()).clicked() {
                        self.shell.preset = preset;
                        self.dock = dock_for_preset(preset);
                    }
                }
            });
            ui.checkbox(&mut self.shell.layout_locked, "Lock dock layout");
            ui.checkbox(&mut self.shell.compact_health, "Compact Health rail");
            ui.separator();
            for category in ["Project", "Operations", "Workspace", "System"] {
                ui.label(RichText::new(category).size(9.0).strong().color(theme::MUTED));
                for tab in WorkspaceTab::ALL.into_iter().filter(|tab| tab.category() == category) {
                    if ui.button(format!("Open {}", tab.title())).clicked() { ensure_tab(&mut self.dock, tab); }
                }
                ui.add_space(4.0);
            }
            ui.separator();
            if ui.button("Reset ForgePY Layout").clicked() {
                self.shell.preset = LayoutPreset::Forge;
                self.dock = default_dock();
            }
            if ui.button("Clear Pending Queue").clicked() { self.shared.queue.clear_pending(); }
        });
    }
}

fn health_row(ui: &mut egui::Ui, name: &str, state: &str, color: Color32) {
    ui.horizontal(|ui| {
        ui.label(RichText::new(name).size(10.0).color(theme::MUTED));
        ui.with_layout(Layout::right_to_left(Align::Center), |ui| { ui.label(RichText::new(state).size(10.0).strong().color(color)); });
    });
}

impl eframe::App for ForgeNativeApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.shared.poll_operations();
        if self.shared.queue.active_label().is_some() { ui.ctx().request_repaint_after(std::time::Duration::from_millis(50)); }

        egui::Panel::left("forge-native-left-rail").exact_size(118.0).resizable(false).frame(theme::panel_frame()).show(ui, |ui| self.draw_left_rail(ui));
        egui::Panel::right("forge-native-health").exact_size(if self.shell.compact_health { 126.0 } else { 154.0 }).resizable(false).frame(theme::panel_frame()).show(ui, |ui| self.draw_health(ui));
        egui::Panel::top("forge-native-quickbar").exact_size(44.0).resizable(false).frame(theme::panel_frame()).show(ui, |ui| self.draw_quickbar(ui));
        egui::Panel::bottom("forge-native-status").exact_size(26.0).resizable(false).frame(theme::panel_frame()).show(ui, |ui| self.draw_statusbar(ui));
        egui::CentralPanel::no_frame().show(ui, |ui| {
            let mut viewer = ForgeTabViewer { shared: &mut self.shared };
            DockArea::new(&mut self.dock)
                .style(widgets::dock_style(ui))
                .show_close_buttons(!self.shell.layout_locked)
                .draggable_tabs(!self.shell.layout_locked)
                .show_inside(ui, &mut viewer);
        });
        self.widgets_window(ui.ctx());
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        eframe::set_value(storage, DOCK_KEY, &self.dock);
        eframe::set_value(storage, SHELL_KEY, &self.shell);
    }
}
