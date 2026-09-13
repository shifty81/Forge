#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import threading, uuid
from typing import Any

UI_VERSION="FORGEPY-SELF-MAINTENANCE-UI-2.0-F740"
BG="#090b0e"; PANEL="#11151a"; PANEL2="#171c22"; TEXT="#edf2f5"; MUTED="#929aa3"; CYAN="#00d9ff"

def install(gui:Any)->None:
    if getattr(gui,"_forge_self_maintenance_ui",False):
        return
    pages=getattr(gui,"_settings_pages",None)
    nav=getattr(gui,"_settings_nav",None)
    if not isinstance(pages,dict) or not isinstance(nav,dict) or not pages or not nav:
        return
    gui._forge_self_maintenance_ui=True
    tk=gui.tk
    parent=next(iter(pages.values())).master
    nav_parent=next(iter(nav.values())).master
    page=tk.Frame(parent,bg=BG)
    pages["ForgePY"]=page
    btn=tk.Button(nav_parent,text="ForgePY",command=lambda:gui._show_settings_page("ForgePY"),bg=PANEL,fg=TEXT,activebackground=PANEL2,activeforeground=CYAN,bd=0,relief="flat",anchor="w",font=("Segoe UI Semibold",9),padx=14,pady=9,cursor="hand2")
    btn.pack(fill="x",padx=5,pady=1,before=next(iter(nav.values())))
    nav["ForgePY"]=btn

    from ForgeApplicationIdentity import DISPLAY_VERSION,DISPLAY_BUILD
    from ForgeInstallLayout import application_root, resolve
    app_root=application_root()
    lay=resolve(app_root)

    panel=gui._panel(page,"ForgePY Application / Self-Maintenance")
    panel.pack(fill="x",pady=(0,9))
    label=tk.Label(panel,text="",bg=PANEL,fg=TEXT,font=("Consolas",9),anchor="w",justify="left")
    label.pack(fill="x",padx=12,pady=(2,8))

    def refresh()->None:
        from ForgeSelfMaintenance import queued
        count=len(queued(app_root,lay["mode"]))
        label.configure(text=f"Version : {DISPLAY_VERSION}\nBuild   : {DISPLAY_BUILD}\nMode    : {lay['mode'].upper()}\nApp     : {lay['appRoot']}\nData    : {lay['dataRoot']}\nUpdates : {count} queued")

    actions=tk.Frame(panel,bg=PANEL)
    actions.pack(fill="x",padx=12,pady=(0,10))

    def run_background(label:str, work, success_title:str, success_message, *, timeout_seconds:int=1800)->None:
        if getattr(gui,"_forge_self_maintenance_busy",False):
            gui._popup("ForgePY Maintenance","A ForgePY application-maintenance action is already running.",kind="info")
            return
        gui._forge_self_maintenance_busy=True
        token=uuid.uuid4().hex
        if not hasattr(gui,"_forge_self_maintenance_results"):
            gui._forge_self_maintenance_results={}
        def worker():
            try:
                gui._forge_self_maintenance_results[token]=(True,work())
            except Exception as exc:
                gui._forge_self_maintenance_results[token]=(False,str(exc))
        def poll(attempts:int|None=None):
            if attempts is None:
                attempts=max(1,int(timeout_seconds*10))
            result=gui._forge_self_maintenance_results.pop(token,None)
            if result is None:
                if attempts>0:
                    gui.window.after(100,lambda:poll(attempts-1))
                else:
                    gui._forge_self_maintenance_busy=False
                    gui._popup("ForgePY Maintenance",f"{label} timed out.",kind="warning")
                return
            gui._forge_self_maintenance_busy=False
            ok,payload=result
            if not ok:
                gui._popup("ForgePY Update",str(payload),kind="error")
                return
            gui._popup(success_title,success_message(payload),kind="success")
            refresh()
        threading.Thread(target=worker,daemon=True,name=f"ForgeSelfMaintenance-{label}").start()
        gui.window.after(100,poll)

    def select_update()->None:
        try:
            name=gui.filedialog.askopenfilename(title="Select ForgePY application update",filetypes=[("ForgePY application updates","*.forgeupdate"),("ForgePY source transports","*.patch *.zip"),("All files","*.*")])
        except Exception:
            name=""
        if not name:
            return
        source=Path(name)
        from ForgeSelfMaintenance import queue_update
        run_background(
            "queue",
            lambda:queue_update(source,app_root,lay["mode"]),
            "ForgePY Update Queued",
            lambda _payload:f"{source.name}\n\nQueued in the ForgePY application-maintenance lane.\nNo project source was changed.",
        )

    def stage_update()->None:
        try:
            from ForgeSelfMaintenance import queued, stage_first_queued
            rows=queued(app_root,lay["mode"])
        except Exception as exc:
            gui._popup("ForgePY Update",str(exc),kind="error")
            return
        if not rows:
            gui._popup("ForgePY Update","No ForgePY application update is queued.",kind="info")
            return
        if not gui._popup(
            "Stage ForgePY Update",
            "Stage the first queued ForgePY application update against a copied application image?\n\n"
            "The running ForgePY installation will not be modified.",
            kind="warning",
            confirm=True,
        ):
            return
        run_background(
            "stage",
            lambda:stage_first_queued(app_root,lay["mode"],approved=True),
            "ForgePY Update Staged",
            lambda plan:f"Staged application image:\n{plan.get('stagedRoot')}\n\n"
                        "Promotion occurs only after ForgePY exits; the live executable was not patched.",
        )

    def apply_staged_on_exit()->None:
        try:
            from ForgeSelfMaintenance import current_plan
            plan=current_plan(app_root,lay["mode"])
        except Exception as exc:
            gui._popup("ForgePY Update",str(exc),kind="error")
            return
        if not plan:
            gui._popup("ForgePY Update","No staged ForgePY application update is ready.",kind="info")
            return
        if str(plan.get("kind") or "")!="application-image":
            gui._popup(
                "ForgePY Update",
                "This staged item is a source transport. Build a new ForgePY executable distribution first.",
                kind="warning",
            )
            return
        if not gui._popup(
            "Apply ForgePY Update",
            "ForgePY will exit, replace the application directory transactionally, preserve portable Data when applicable, then restart the new ForgePY.exe.\n\nContinue?",
            kind="warning",
            confirm=True,
        ):
            return
        try:
            from ForgeSelfMaintenance import arm_current_plan
            arm_current_plan(app_root,lay["mode"],approved=True)
            gui.window.after(150,gui._on_close)
        except Exception as exc:
            gui._popup("ForgePY Update",str(exc),kind="error")

    gui._button(actions,"SELECT FORGEPY UPDATE",select_update,primary=True,compact=True).pack(side="left",padx=(0,5))
    gui._button(actions,"STAGE UPDATE",stage_update,compact=True).pack(side="left",padx=5)
    gui._button(actions,"APPLY STAGED ON EXIT",apply_staged_on_exit,compact=True).pack(side="left",padx=5)
    gui._button(actions,"REFRESH",refresh,compact=True).pack(side="left",padx=5)
    refresh()

    info=gui._panel(page,"Install / Packaging Model")
    info.pack(fill="x",pady=(0,9))
    tk.Label(info,text="Standard install → ForgePY application under LocalAppData Programs; mutable application state under AppData.\nPortable install → ForgePY.exe and a local Data folder travel together.\nBoth use the separate ForgePY update lane; project patches never mutate the ForgePY application image.",bg=PANEL,fg=MUTED,font=("Segoe UI",9),justify="left",anchor="w",wraplength=760).pack(fill="x",padx=12,pady=(2,10))


    build_panel=gui._panel(page,"Executable / Distribution")
    build_panel.pack(fill="x",pady=(0,9))
    build_status=tk.Label(
        build_panel,
        text="Nuitka standalone/onedir is the executable authority. Inno Setup is optional for the combined Standard/Portable installer.",
        bg=PANEL,fg=MUTED,font=("Segoe UI",9),justify="left",anchor="w",wraplength=760,
    )
    build_status.pack(fill="x",padx=12,pady=(2,8))
    build_actions=tk.Frame(build_panel,bg=PANEL)
    build_actions.pack(fill="x",padx=12,pady=(0,10))

    def executable_preflight()->None:
        try:
            from ForgeExecutableSystem import preflight
            result=preflight(app_root)
            n=result.get("nuitka") or {}
            i=result.get("innoSetup") or {}
            build_status.configure(
                text=(
                    f"Windows: {result.get('windows')} · Nuitka: {n.get('nuitkaAvailable')} · "
                    f"EXE ready: {result.get('readyForExecutable')} · Inno Setup: {i.get('available')}\n"
                    f"Version: {result.get('applicationVersion')} · Build: {result.get('applicationBuild')}"
                )
            )
        except Exception as exc:
            build_status.configure(text=str(exc))

    def build_distribution()->None:
        if not gui._popup(
            "Build ForgePY Distribution",
            "Build the Windows ForgePY.exe standalone image, portable ZIP, executable update bundle, and installer when Inno Setup is available?\n\n"
            "This can take several minutes and runs in the background.",
            kind="warning",
            confirm=True,
        ):
            return
        from ForgeExecutableSystem import build_distribution as build_all
        run_background(
            "distribution",
            lambda:build_all(app_root,approved=True,build_installer_if_available=True),
            "ForgePY Distribution Built",
            lambda result:(
                f"Portable ZIP:\n{(result.get('portableZip') or {}).get('path') or '-'}\n\n"
                f"Application update:\n{(result.get('applicationUpdate') or {}).get('path') or '-'}\n\n"
                f"Installer:\n{(result.get('installer') or {}).get('installer') or (result.get('installer') or {}).get('script') or '-'}"
            ),
            timeout_seconds=14400,
        )

    gui._button(build_actions,"PREFLIGHT",executable_preflight,compact=True).pack(side="left",padx=(0,5))
    gui._button(build_actions,"BUILD DISTRIBUTION",build_distribution,primary=True,compact=True).pack(side="left",padx=5)
    executable_preflight()
