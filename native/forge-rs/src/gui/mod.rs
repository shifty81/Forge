pub mod docking;
pub mod model;
pub mod operations;
pub mod theme;
pub mod widgets;

use std::path::PathBuf;

use eframe::egui::{self, Align, Color32, Layout, RichText, Stroke};
use egui_dock::{DockArea, DockState};

use crate::identity::NativeIdentity;
use crate::project::{probe_project, ProjectSnapshot};

use docking::{default_dock, ForgeDock};
use model::{LayoutPreset, PersistedShellState, PrimarySurface, ProjectSection, WorkspaceTab};
use widgets::{ForgeTabViewer, SharedUiState};

const DOCK_KEY: &str = "forge-native-dock-v2";
const SHELL_KEY: &str = "forge-native-shell-v2";

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
    dock: ForgeDock,
    shell: PersistedShellState,
    shared: SharedUiState,
    show_widgets: bool,
    widget_search: String,
}

impl ForgeNativeApp {
    fn new(cc: &eframe::CreationContext<'_>, root: PathBuf, project: ProjectSnapshot) -> Self {
        theme::install(&cc.egui_ctx);
        egui_extras::install_image_loaders(&cc.egui_ctx);
        let state: DockState<WorkspaceTab> = cc.storage
            .and_then(|storage| eframe::get_value(storage, DOCK_KEY))
            .unwrap_or_else(default_dock);
        let shell = cc.storage
            .and_then(|storage| eframe::get_value(storage, SHELL_KEY))
            .unwrap_or_default();
        Self {
            dock: ForgeDock::new(state),
            shell,
            shared: SharedUiState::new(root, project),
            show_widgets: false,
            widget_search: String::new(),
        }
    }

    fn activate_surface(&mut self, surface: PrimarySurface) {
        self.shell.active_surface = surface;
        if surface == PrimarySurface::Project {
            self.dock.open_or_focus(self.shell.active_project_section.tab());
        } else {
            self.dock.open_or_focus(surface.tab());
        }
    }

    fn activate_project_section(&mut self, section: ProjectSection) {
        self.shell.active_surface = PrimarySurface::Project;
        self.shell.active_project_section = section;
        self.dock.open_or_focus(section.tab());
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
        ui.add_space(3.0);
        ui.horizontal(|ui| {
            ui.label(RichText::new("FORGEPY").size(9.5).strong().color(theme::MUTED));
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| { ui.label(RichText::new("‹").color(theme::CYAN)); });
        });
        ui.add_space(10.0);
        for surface in PrimarySurface::ALL {
            let selected = self.shell.active_surface == surface;
            let button = egui::Button::new(RichText::new(surface.title()).strong().color(if selected { theme::CYAN } else { theme::TEXT }))
                .fill(if selected { theme::BG_SELECTED } else { theme::BG_PANEL });
            if ui.add_sized([96.0, 32.0], button).clicked() { self.activate_surface(surface); }
            ui.add_space(2.0);
        }
    }

    fn draw_project_rail(&mut self, ui: &mut egui::Ui) {
        let collapsed = self.shell.project_rail_collapsed;
        ui.horizontal(|ui| {
            if !collapsed {
                if let Some(icon) = self.shared.project.icon.as_ref() {
                    ui.add(egui::Image::new(widgets::project_icon_uri(icon)).fit_to_exact_size(egui::vec2(18.0, 18.0)));
                }
                ui.label(RichText::new(&self.shared.project.name).strong().color(theme::TEXT));
            }
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                let label = if collapsed { "›" } else { "‹" };
                if ui.small_button(label).on_hover_text(if collapsed { "Expand Project rail" } else { "Collapse Project rail" }).clicked() {
                    self.shell.project_rail_collapsed = !self.shell.project_rail_collapsed;
                }
            });
        });
        ui.add_space(8.0);
        ui.separator();
        ui.add_space(4.0);

        for section in ProjectSection::ALL {
            if section == ProjectSection::ProjectTools && !self.shared.has_internal_pcc() { continue; }
            let tab = section.tab();
            let selected = self.shell.active_project_section == section;
            let label = if collapsed { tab.icon().to_string() } else { format!("{}  {}", tab.icon(), section.title()) };
            let width = if collapsed { 34.0 } else { 142.0 };
            let response = ui.add_sized(
                [width, 30.0],
                egui::Button::new(RichText::new(label).color(if selected { theme::CYAN } else { theme::TEXT }))
                    .fill(if selected { theme::BG_SELECTED } else { theme::BG_PANEL })
            );
            let response = if collapsed { response.on_hover_text(section.title()) } else { response };
            if response.clicked() { self.activate_project_section(section); }
            ui.add_space(2.0);
        }
    }

    fn draw_quickbar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            theme::identity_chip(ui, &self.shared.project.name, self.shared.project.icon.as_ref());
            ui.separator();
            for label in ["FULL GATE", "BUILD", "TEST", "RUN", "REFRESH"] {
                let fill = if label == "FULL GATE" { theme::CYAN } else { theme::BG_PANEL_ALT };
                if ui.add(egui::Button::new(label).fill(fill)).clicked() { self.quick_action(label); }
            }
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if ui.button("PROJECT CLI").clicked() { self.dock.open_or_focus(WorkspaceTab::ProjectCli); }
                if ui.button("WIDGETS").clicked() { self.show_widgets = !self.show_widgets; }
                if ui.button(format!("QUEUE {}", self.shared.queue.pending_len())).clicked() { self.dock.open_or_focus(WorkspaceTab::OperationQueue); }
                if ui.button("INTEL").clicked() { self.activate_project_section(ProjectSection::Intelligence); }
            });
        });
    }

    fn draw_health(&mut self, ui: &mut egui::Ui) {
        ui.label(RichText::new("FORGEPY HEALTH").size(9.0).strong().color(theme::MUTED));
        ui.add_space(9.0);
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
        health_row(ui, "ForgeDock", "PASS", theme::GREEN);
        health_row(ui, "Intelligence", if self.shared.intelligence.confidence >= 75 { "PASS" } else { "SCAN" }, if self.shared.intelligence.confidence >= 75 { theme::GREEN } else { theme::YELLOW });
        health_row(ui, "Queue", if self.shared.queue.active_label().is_some() { "RUN" } else { "IDLE" }, if self.shared.queue.active_label().is_some() { theme::CYAN } else { theme::GREEN });
        widgets::divider(ui);
        ui.label(RichText::new("PROJECT CONTEXT").size(9.0).strong().color(theme::MUTED));
        ui.label(RichText::new(&self.shared.project.name).strong());
        ui.label(RichText::new(self.shell.active_project_section.title()).size(10.0).color(theme::CYAN));
        ui.label(RichText::new(NativeIdentity::current().build).size(9.0).color(theme::MUTED));
        ui.label(RichText::new(self.shared.root.display().to_string()).size(9.0).color(theme::TEXT));
        ui.with_layout(Layout::bottom_up(Align::Min), |ui| {
            ui.label(RichText::new("0.5.0-shadow").size(9.0).color(theme::MUTED));
            ui.label(RichText::new("Forge Native").size(10.0).strong());
        });
    }

    fn draw_statusbar(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label(RichText::new(format!("{} · {}", self.shared.project.name, NativeIdentity::current().build)).size(9.0).color(theme::TEXT));
            ui.separator();
            ui.label(RichText::new(self.shell.active_project_section.title()).size(9.0).color(theme::CYAN));
            ui.separator();
            widgets::queue_summary(ui, &self.shared);
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                ui.label(RichText::new("0.5.0-shadow · FORGE-NATIVE-F787").size(9.0).color(theme::MUTED));
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
        egui::Window::new("Widgets & Layout")
            .default_width(360.0)
            .min_width(320.0)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.label(RichText::new("ForgeDock Workspace").strong().color(theme::CYAN));
                ui.label(RichText::new("Only central tools dock. Forge/Project/Health rails, quickbar and status bar are protected shell regions.").size(10.0).color(theme::MUTED));
                ui.add_space(6.0);
                ui.horizontal_wrapped(|ui| {
                    for preset in LayoutPreset::ALL {
                        let selected = self.shell.preset == preset;
                        if ui.selectable_label(selected, preset.title()).clicked() {
                            self.shell.preset = preset;
                            self.dock.reset(preset);
                        }
                    }
                });
                ui.checkbox(&mut self.shell.layout_locked, "Lock dock layout");
                ui.checkbox(&mut self.shell.compact_health, "Compact Health rail");
                ui.checkbox(&mut self.shell.project_rail_collapsed, "Collapse Project rail");
                ui.separator();
                ui.add(egui::TextEdit::singleline(&mut self.widget_search).hint_text("Search widgets…"));
                ui.add_space(4.0);
                let query = self.widget_search.trim().to_ascii_lowercase();
                for category in ["Project", "Operations", "Workspace", "System"] {
                    let tabs: Vec<_> = WorkspaceTab::ALL.into_iter().filter(|tab| {
                        tab.category() == category && (query.is_empty() || tab.title().to_ascii_lowercase().contains(&query))
                    }).collect();
                    if tabs.is_empty() { continue; }
                    ui.label(RichText::new(category).size(9.0).strong().color(theme::MUTED));
                    ui.horizontal_wrapped(|ui| {
                        for tab in tabs {
                            if ui.button(format!("{} {}", tab.icon(), tab.title())).clicked() { self.dock.open_or_focus(tab); }
                        }
                    });
                    ui.add_space(5.0);
                }
                ui.separator();
                if ui.button("Reset ForgePY Layout").clicked() {
                    self.shell = PersistedShellState::default();
                    self.dock.reset(LayoutPreset::Forge);
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

        egui::Panel::left("forge-native-left-rail")
            .exact_size(108.0)
            .resizable(false)
            .frame(theme::rail_frame())
            .show(ui, |ui| self.draw_left_rail(ui));

        if self.shell.active_surface == PrimarySurface::Project {
            let width = if self.shell.project_rail_collapsed { 48.0 } else { 164.0 };
            egui::Panel::left("forge-native-project-context-rail")
                .exact_size(width)
                .resizable(false)
                .frame(theme::project_rail_frame())
                .show(ui, |ui| self.draw_project_rail(ui));
        }

        egui::Panel::right("forge-native-health")
            .exact_size(if self.shell.compact_health { 130.0 } else { 158.0 })
            .resizable(false)
            .frame(theme::rail_frame())
            .show(ui, |ui| self.draw_health(ui));

        egui::Panel::top("forge-native-quickbar")
            .exact_size(44.0)
            .resizable(false)
            .frame(theme::toolbar_frame())
            .show(ui, |ui| self.draw_quickbar(ui));

        egui::Panel::bottom("forge-native-status")
            .exact_size(25.0)
            .resizable(false)
            .frame(theme::status_frame())
            .show(ui, |ui| self.draw_statusbar(ui));

        egui::CentralPanel::no_frame().show(ui, |ui| {
            let mut viewer = ForgeTabViewer { shared: &mut self.shared };
            DockArea::new(self.dock.state_mut())
                .id(egui::Id::new("forge-native-forgedock"))
                .style(widgets::dock_style(ui))
                .show_close_buttons(!self.shell.layout_locked)
                .draggable_tabs(!self.shell.layout_locked)
                .tab_context_menus(true)
                .hidable_tab_bars(true)
                .show_tab_name_on_hover(true)
                .show_leaf_collapse_buttons(true)
                .show_inside(ui, &mut viewer);
        });
        self.widgets_window(ui.ctx());
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        eframe::set_value(storage, DOCK_KEY, self.dock.state());
        eframe::set_value(storage, SHELL_KEY, &self.shell);
    }
}
