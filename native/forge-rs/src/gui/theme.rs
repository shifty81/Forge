use std::path::PathBuf;

use eframe::egui::{self, Align, Color32, Layout, RichText, Stroke, Theme, Visuals};

pub const BG_ROOT: Color32 = Color32::from_rgb(8, 12, 16);
pub const BG_PANEL: Color32 = Color32::from_rgb(12, 18, 23);
pub const BG_PANEL_ALT: Color32 = Color32::from_rgb(15, 22, 28);
pub const BG_SELECTED: Color32 = Color32::from_rgb(14, 31, 39);
pub const BG_INPUT: Color32 = Color32::from_rgb(6, 10, 13);
pub const BORDER: Color32 = Color32::from_rgb(30, 43, 52);
pub const BORDER_STRONG: Color32 = Color32::from_rgb(39, 58, 69);
pub const TEXT: Color32 = Color32::from_rgb(219, 230, 236);
pub const MUTED: Color32 = Color32::from_rgb(130, 151, 162);
pub const CYAN: Color32 = Color32::from_rgb(0, 208, 231);
pub const GREEN: Color32 = Color32::from_rgb(39, 224, 116);
pub const YELLOW: Color32 = Color32::from_rgb(238, 194, 69);
pub const RED: Color32 = Color32::from_rgb(244, 74, 89);

pub fn install(ctx: &egui::Context) {
    ctx.set_theme(Theme::Dark);
    let mut style = (*ctx.style_of(Theme::Dark)).clone();
    let mut visuals = Visuals::dark();
    visuals.panel_fill = BG_ROOT;
    visuals.window_fill = BG_PANEL;
    visuals.extreme_bg_color = BG_INPUT;
    visuals.faint_bg_color = BG_PANEL_ALT;
    visuals.selection.bg_fill = CYAN;
    visuals.selection.stroke = Stroke::new(1.0, CYAN);
    visuals.widgets.noninteractive.bg_fill = BG_PANEL;
    visuals.widgets.noninteractive.bg_stroke = Stroke::new(1.0, BORDER);
    visuals.widgets.inactive.bg_fill = BG_PANEL_ALT;
    visuals.widgets.inactive.bg_stroke = Stroke::new(1.0, BORDER);
    visuals.widgets.hovered.bg_fill = Color32::from_rgb(21, 37, 45);
    visuals.widgets.hovered.bg_stroke = Stroke::new(1.0, CYAN);
    visuals.widgets.active.bg_fill = Color32::from_rgb(0, 79, 91);
    visuals.widgets.active.bg_stroke = Stroke::new(1.0, CYAN);
    visuals.override_text_color = Some(TEXT);
    style.visuals = visuals;
    style.spacing.item_spacing = egui::vec2(6.0, 6.0);
    style.spacing.button_padding = egui::vec2(10.0, 6.0);
    style.spacing.window_margin = egui::Margin::same(8);
    ctx.set_style_of(Theme::Dark, style);
}

pub fn rail_frame() -> egui::Frame {
    egui::Frame::new().fill(BG_PANEL).stroke(Stroke::new(1.0, BORDER_STRONG)).inner_margin(egui::Margin::same(8))
}

pub fn project_rail_frame() -> egui::Frame {
    egui::Frame::new().fill(Color32::from_rgb(10, 16, 21)).stroke(Stroke::new(1.0, BORDER)).inner_margin(egui::Margin::same(8))
}

pub fn toolbar_frame() -> egui::Frame {
    egui::Frame::new().fill(Color32::from_rgb(10, 16, 21)).stroke(Stroke::new(1.0, BORDER_STRONG)).inner_margin(egui::Margin::symmetric(8, 7))
}

pub fn status_frame() -> egui::Frame {
    egui::Frame::new().fill(Color32::from_rgb(7, 11, 15)).stroke(Stroke::new(1.0, BORDER)).inner_margin(egui::Margin::symmetric(8, 4))
}

pub fn panel_frame() -> egui::Frame {
    egui::Frame::new().fill(BG_PANEL).stroke(Stroke::new(1.0, BORDER)).inner_margin(egui::Margin::same(8))
}

pub fn card_frame() -> egui::Frame {
    egui::Frame::new().fill(BG_PANEL_ALT).stroke(Stroke::new(1.0, BORDER)).inner_margin(egui::Margin::same(10))
}

pub fn identity_chip(ui: &mut egui::Ui, project_name: &str, icon: Option<&PathBuf>) {
    egui::Frame::new().fill(BG_SELECTED).stroke(Stroke::new(1.0, BORDER_STRONG)).inner_margin(egui::Margin::symmetric(8, 5)).show(ui, |ui| {
        ui.horizontal(|ui| {
            if let Some(icon) = icon {
                let normalized = icon.display().to_string().replace('\\', "/");
                ui.add(egui::Image::new(format!("file://{normalized}")).fit_to_exact_size(egui::vec2(16.0, 16.0)));
            } else {
                let initials: String = project_name.chars().filter(|ch| ch.is_alphanumeric()).take(2).collect();
                ui.label(RichText::new(if initials.is_empty() { "PR".into() } else { initials }).strong().color(CYAN));
            }
            ui.label(RichText::new(format!("{} · PROJECT", project_name)).strong().color(CYAN));
            ui.with_layout(Layout::right_to_left(Align::Center), |_ui| {});
        });
    });
}
