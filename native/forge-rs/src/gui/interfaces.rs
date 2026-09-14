use egui_dock::DockState;
use serde::{Deserialize, Serialize};

use super::model::ToolPanel;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SavedInterface {
    pub name: String,
    pub dock: DockState<ToolPanel>,
    pub locked: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct InterfaceLibrary {
    pub saved: Vec<SavedInterface>,
}

impl InterfaceLibrary {
    pub fn save(&mut self, name: impl Into<String>, dock: &DockState<ToolPanel>, locked: bool) -> String {
        let name = name.into().trim().to_string();
        let name = if name.is_empty() { "Custom Interface".to_string() } else { name };
        if let Some(existing) = self.saved.iter_mut().find(|row| row.name.eq_ignore_ascii_case(&name)) {
            existing.dock = dock.clone();
            existing.locked = locked;
        } else {
            self.saved.push(SavedInterface { name: name.clone(), dock: dock.clone(), locked });
        }
        name
    }

    pub fn get(&self, index: usize) -> Option<&SavedInterface> { self.saved.get(index) }

    pub fn delete(&mut self, index: usize) -> bool {
        if index >= self.saved.len() { return false; }
        self.saved.remove(index);
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn custom_interfaces_round_trip_layout_and_lock() {
        let dock = DockState::new(vec![ToolPanel::Overview]);
        let mut library = InterfaceLibrary::default();
        let name = library.save("My Interface", &dock, true);
        assert_eq!(name, "My Interface");
        let saved = library.get(0).unwrap();
        assert!(saved.locked);
        assert!(saved.dock.find_tab(&ToolPanel::Overview).is_some());
    }
}
