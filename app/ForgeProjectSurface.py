#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

SURFACE_VERSION="FORGEPY-PROJECT-SURFACE-1.2-F743"
BG="#090b0e"; PANEL="#11151a"; PANEL2="#171c22"; BORDER="#28313a"
TEXT="#edf2f5"; MUTED="#929aa3"; CYAN="#00d9ff"

_VISIBLE_NAV=(
    ("Dashboard","Dashboard"),
    ("Updates","Updates"),
    ("Source Control","Source & Recovery"),
    ("Diagnostics","Diagnostics"),
    ("Tooling","Project Tools"),
    ("Advanced Commands","Advanced"),
)
_ALL_PAGES=("Dashboard","ForgePY Self","Build & Run","Updates","Source Control","Diagnostics","Tooling","Advanced Commands")
_SCROLL={"Build & Run","Updates","Source Control","Diagnostics","Tooling"}

def build(gui:Any,parent:Any)->None:
    """Build only the Project shell + Dashboard. Specialist pages are lazy."""
    tk=gui.tk
    panes=tk.PanedWindow(parent,orient="horizontal",bg=BG,bd=0,sashwidth=5,sashrelief="flat",showhandle=False,opaqueresize=True)
    panes.pack(fill="both",expand=True,padx=0,pady=0)
    gui.workspace_panes=panes

    nav=gui._panel(panes)
    nav.configure(width=158)
    nav.pack_propagate(False)
    header=tk.Frame(nav,bg=PANEL)
    header.pack(fill="x",padx=10,pady=(11,5))
    tk.Label(header,text="PROJECT",bg=PANEL,fg=MUTED,font=("Segoe UI Semibold",8)).pack(anchor="w")

    for page,label in _VISIBLE_NAV:
        btn=tk.Button(
            nav,text=label,anchor="w",command=lambda p=page:gui._show_page(p),
            bg=PANEL,fg=TEXT,activebackground=PANEL2,activeforeground=CYAN,
            bd=0,relief="flat",font=("Segoe UI",9),cursor="hand2",padx=12,pady=7,
        )
        btn.pack(fill="x",padx=3,pady=1)
        gui._nav_buttons[page]=btn

    tk.Frame(nav,bg=BORDER,height=1).pack(fill="x",padx=10,pady=(10,8))
    gui.operation_label=tk.Label(nav,text="Idle",bg=PANEL,fg=MUTED,font=("Segoe UI",8),wraplength=132,justify="left")
    gui.operation_label.pack(anchor="w",padx=12,pady=(0,5))

    center=gui._panel(panes)
    gui.content=tk.Frame(center,bg=PANEL)
    gui.content.pack(fill="both",expand=True,padx=8,pady=6)

    gui._forge_project_page_builders={
        "Dashboard":gui._build_dashboard,
        "ForgePY Self":gui._build_forgepy_self_page,
        "Build & Run":gui._build_build_page,
        "Updates":gui._build_updates_page,
        "Source Control":gui._build_source_page,
        "Diagnostics":gui._build_diagnostics_page,
        "Tooling":gui._build_tooling_page,
        "Advanced Commands":gui._build_commands_page,
    }
    gui._forge_project_pages_built=set()

    for page in _ALL_PAGES:
        frame=tk.Frame(gui.content,bg=PANEL)
        gui._page_frames[page]=frame

    panes.add(nav,minsize=132,width=150)
    panes.add(center,minsize=390,width=760,stretch="always")

    ensure_page(gui,"Dashboard")

    # The base GUI can request Dashboard before this lazy Project surface exists.
    # Re-issue the request after materialization so the resolved ForgePY Self page
    # is actually packed instead of leaving the center host empty.
    def activate_initial_dashboard() -> None:
        try:
            gui._show_page("Dashboard")
        except Exception:
            actual=_resolved_page(gui,"Dashboard")
            frame=gui._page_frames.get(actual)
            if frame is not None and not frame.winfo_manager():
                frame.pack(fill="both",expand=True)
            gui._forge_current_project_page=actual
    gui.window.after(1,activate_initial_dashboard)
    try:
        gui.window.after(160,gui._set_workspace_sashes)
        panes.bind("<ButtonRelease-1>",lambda _e:gui._persist_workspace_layout(),add="+")
    except Exception:
        pass

def _resolved_page(gui:Any,page:str)->str:
    """Resolve Dashboard exactly the same way ForgeGui._show_page() does."""
    if page=="Dashboard":
        try:
            if bool(gui._is_forgepy_self_project()):
                return "ForgePY Self"
        except Exception:
            pass
    return page

def ensure_page(gui:Any,page:str)->None:
    actual=_resolved_page(gui,page)
    built=getattr(gui,"_forge_project_pages_built",set())
    if actual in built:
        return
    frame=(getattr(gui,"_page_frames",{}) or {}).get(actual)
    builder=(getattr(gui,"_forge_project_page_builders",{}) or {}).get(actual)
    if frame is None or builder is None:
        return
    body=gui._make_scrollable_page(frame) if actual in _SCROLL else frame
    gui._page_bodies[actual]=body
    builder(body)
    built=set(built); built.add(actual)
    gui._forge_project_pages_built=built
