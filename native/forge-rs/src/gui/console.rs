use eframe::egui::{self, RichText, ScrollArea, Ui};

use super::model::ConsoleChannel;
use super::theme;
use super::widgets::SharedUiState;

fn line_matches(channel: ConsoleChannel, line: &str) -> bool {
    if channel == ConsoleChannel::All { return true; }
    let value = line.to_ascii_lowercase();
    match channel {
        ConsoleChannel::All => true,
        ConsoleChannel::Project => !value.contains("forge native") && !value.contains("forgepy remains"),
        ConsoleChannel::Forge => value.contains("forge") || value.contains("native shell"),
        ConsoleChannel::Build => ["build", "cargo", "cmake", "compile", "link"].iter().any(|token| value.contains(token)),
        ConsoleChannel::Gate => ["gate", "certif", "full", "[pass]", "[fail]"].iter().any(|token| value.contains(token)),
        ConsoleChannel::Patch => ["patch", "update", "intake", "transport"].iter().any(|token| value.contains(token)),
        ConsoleChannel::Git => ["git", "branch", "commit", "push", "pull", "remote"].iter().any(|token| value.contains(token)),
        ConsoleChannel::Doctor => ["doctor", "depend", "toolchain", "hydrate", "asset"].iter().any(|token| value.contains(token)),
    }
}

fn line_color(line: &str) -> egui::Color32 {
    if line.contains("[PASS]") { theme::GREEN }
    else if line.contains("[FAIL]") || line.contains("[ERR]") { theme::RED }
    else if line.contains("[WARN]") { theme::YELLOW }
    else if line.contains("[QUEUED]") || line.contains("[RUNNING]") || line.starts_with('>') { theme::CYAN }
    else { theme::TEXT }
}

/// Permanent Forge Console shell region. This is deliberately not a DockArea tab.
pub fn draw(ui: &mut Ui, shared: &mut SharedUiState, channel: &mut ConsoleChannel) {
    ui.horizontal(|ui| {
        ui.label(RichText::new("FORGE CONSOLE").strong().color(theme::CYAN));
        if let Some(active) = shared.queue.active_label() {
            ui.label(RichText::new(format!("RUNNING · {active}")).size(10.0).color(theme::CYAN));
        } else {
            ui.label(RichText::new("IDLE").size(10.0).color(theme::MUTED));
        }
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.small_button("Clear").clicked() { shared.console.clear(); }
            ui.label(RichText::new(format!("{} lines", shared.console.len())).size(9.0).color(theme::MUTED));
        });
    });

    ui.horizontal_wrapped(|ui| {
        for candidate in ConsoleChannel::ALL {
            let selected = *channel == candidate;
            if ui.selectable_label(selected, RichText::new(candidate.title()).size(9.0)).clicked() {
                *channel = candidate;
            }
        }
    });

    ui.separator();
    let available = ui.available_height();
    let composer_height = 38.0;
    ScrollArea::vertical()
        .stick_to_bottom(true)
        .max_height((available - composer_height).max(80.0))
        .show(ui, |ui| {
            for line in shared.console.iter().filter(|line| line_matches(*channel, line)) {
                ui.label(RichText::new(line).monospace().size(11.0).color(line_color(line)));
            }
        });

    ui.separator();
    ui.horizontal(|ui| {
        ui.label(RichText::new(">").monospace().strong().color(theme::CYAN));
        let width = (ui.available_width() - 116.0).max(80.0);
        let edit = ui.add_sized(
            [width, 28.0],
            egui::TextEdit::singleline(&mut shared.console_input).hint_text("Forge command…"),
        );
        let send_enter = edit.lost_focus() && ui.input(|input| input.key_pressed(egui::Key::Enter));
        if ui.add_sized([54.0, 28.0], egui::Button::new("Send").fill(theme::CYAN)).clicked() || send_enter {
            shared.execute_console_command();
        }
        let stop = egui::Button::new("Stop").fill(if shared.queue.active_label().is_some() { theme::RED } else { theme::BG_PANEL_ALT });
        if ui.add_sized([54.0, 28.0], stop).clicked() && shared.queue.stop_active() {
            shared.push_console("[STOP] Cancellation requested for the active operation.");
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn channels_cover_operational_sources() {
        assert!(line_matches(ConsoleChannel::Patch, "[INFO] patch intake ready"));
        assert!(line_matches(ConsoleChannel::Git, "git push origin main"));
        assert!(line_matches(ConsoleChannel::Doctor, "dependency doctor pass"));
        assert!(!line_matches(ConsoleChannel::Build, "random message"));
    }
}
