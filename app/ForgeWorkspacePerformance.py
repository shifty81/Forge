#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

WORKSPACE_PERFORMANCE_VERSION = "FORGEPY-WORKSPACE-PERFORMANCE-2.0-F520"

@dataclass(frozen=True)
class WorkspacePerformancePolicy:
    file_scan_on_ui_thread: bool = False
    tree_batch_size: int = 0  # compatibility field; F520 uses lazy directories, not batches
    duplicate_refresh_coalescing: bool = True
    background_workers_touch_tk: bool = False
    first_paint_before_file_population: bool = True
    external_runtime_probe_on_open: bool = False
    monaco_pywebview_required: bool = False
    full_tree_population_on_open: bool = False
    lazy_directory_materialization: bool = True
    workspace_shell_prebuilt: bool = True
    cached_index_reused_on_tab_return: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "forgepy.workspace-performance.v2", "version": WORKSPACE_PERFORMANCE_VERSION, **asdict(self)}

def policy() -> dict[str, Any]:
    return WorkspacePerformancePolicy().to_dict()
