#!/usr/bin/env python3
from __future__ import annotations
import threading
from pathlib import Path
from typing import Any

DASHBOARD_VERSION = "FORGEPY-PROJECT-DASHBOARD-1.0-F700"
PANEL="#11151a"; PANEL2="#171c22"; BORDER="#28313a"
TEXT="#edf2f5"; MUTED="#929aa3"; CYAN="#00d9ff"; GREEN="#43f071"; YELLOW="#ffd44a"; RED="#ff5d68"

def _set(label: Any, text: str, color: str | None = None) -> None:
    try:
        kwargs={"text":text}
        if color: kwargs["fg"]=color
        label.configure(**kwargs)
    except Exception:
        pass

def _page(gui: Any, name: str) -> None:
    try:
        gui._show_page(name)
    except Exception:
        pass

def build(gui: Any, parent: Any) -> None:
    tk=gui.tk
    header=tk.Frame(parent,bg=PANEL); header.pack(fill="x",pady=(0,8))
    tk.Label(header,text="Dashboard",bg=PANEL,fg=TEXT,font=("Segoe UI Semibold",13),anchor="w").pack(anchor="w")
    tk.Label(header,text="Selected-project command center: state, attention, evidence and specialist workflows.",bg=PANEL,fg=MUTED,font=("Segoe UI",8),anchor="w").pack(anchor="w",pady=(2,0))

    metrics=tk.Frame(parent,bg=PANEL); metrics.pack(fill="x",pady=(0,8))
    gui._forge_dash_metrics={}
    for key,title in (("version","PROJECT VERSION"),("health","HEALTH"),("source","SOURCE"),("green","GREEN"),("updates","UPDATES")):
        card=tk.Frame(metrics,bg=PANEL2,highlightthickness=1,highlightbackground=BORDER)
        card.pack(side="left",fill="x",expand=True,padx=(0,6))
        tk.Label(card,text=title,bg=PANEL2,fg=MUTED,font=("Segoe UI Semibold",7),anchor="w").pack(fill="x",padx=10,pady=(7,1))
        value=tk.Label(card,text="…",bg=PANEL2,fg=TEXT,font=("Segoe UI Semibold",10),anchor="w")
        value.pack(fill="x",padx=10,pady=(0,7))
        gui._forge_dash_metrics[key]=value

    nav=tk.Frame(parent,bg=PANEL); nav.pack(fill="x",pady=(0,8))
    gui._button(nav,"UPDATES",lambda:_page(gui,"Updates"),compact=True).pack(side="left",padx=(0,4))
    gui._button(nav,"SOURCE & RECOVERY",lambda:_page(gui,"Source Control"),compact=True).pack(side="left",padx=4)
    gui._button(nav,"DIAGNOSTICS",lambda:_page(gui,"Diagnostics"),compact=True).pack(side="left",padx=4)
    gui._button(nav,"PROJECT TOOLS",lambda:_page(gui,"Tooling"),compact=True).pack(side="left",padx=4)
    gui._button(nav,"ADVANCED",lambda:_page(gui,"Advanced Commands"),compact=True).pack(side="left",padx=4)
    gui._button(nav,"REFRESH DASHBOARD",lambda:refresh(gui,force=True),compact=True).pack(side="right")

    body=tk.PanedWindow(parent,orient="horizontal",bg=PANEL,bd=0,sashwidth=5,sashrelief="flat",showhandle=False)
    body.pack(fill="both",expand=True)
    left=gui._panel(body,"Project Context")
    right=gui._panel(body,"Needs Attention / Evidence")
    body.add(left,minsize=390,stretch="always")
    body.add(right,minsize=300,width=360)

    gui._forge_dash_context=tk.Label(left,text="Loading…",bg=PANEL,fg=TEXT,font=("Consolas",9),justify="left",anchor="nw")
    gui._forge_dash_context.pack(fill="both",expand=True,padx=12,pady=(2,10))
    gui._forge_dash_attention=tk.Label(right,text="Loading…",bg=PANEL,fg=MUTED,font=("Segoe UI",9),justify="left",anchor="nw",wraplength=340)
    gui._forge_dash_attention.pack(fill="both",expand=True,padx=12,pady=(2,10))
    refresh(gui)

def refresh(gui: Any, *, force: bool=False) -> None:
    if not hasattr(gui,"_forge_dash_metrics"):
        return
    root=Path(gui.root_path).expanduser().resolve()
    key=str(root).casefold()
    generation=int(getattr(gui,"_forge_dash_generation",0) or 0)+1
    gui._forge_dash_generation=generation
    if not hasattr(gui,"_forge_dash_results"):
        gui._forge_dash_results={}
    for label in gui._forge_dash_metrics.values():
        _set(label,"…",MUTED)

    def worker() -> None:
        try:
            from ForgeProjectIdentity import resolve
            from ForgeStatusCache import fast_source_status
            identity=resolve(root)
            source=fast_source_status(root,force=force)
            green="STALE"
            try:
                from ForgeGreen import read_green
                marker=read_green(root) or {}
                gate_head=str(marker.get("gitHeadAtGate") or "")
                green="GREEN" if source.get("clean") and gate_head and gate_head==str(source.get("head") or "") else ("MISSING" if not marker else "STALE")
            except Exception:
                pass
            queued=0
            review=0
            try:
                from ForgePYIntake import available_globally, review_items
                ids={str(identity.get("projectId") or "").casefold(),str(identity.get("name") or "").casefold()}
                queued=sum(1 for x in (available_globally(compatible_only=True) or []) if str(x.get("target_project") or "").casefold() in ids)
                review=sum(1 for x in (review_items() or []) if str(x.get("target_project") or "").casefold() in ids)
            except Exception:
                pass
            gui._forge_dash_results[(generation,key)]=(True,{"identity":identity,"source":source,"green":green,"queued":queued,"review":review})
        except Exception as exc:
            gui._forge_dash_results[(generation,key)]=(False,str(exc))

    def poll(attempts:int=400) -> None:
        result=gui._forge_dash_results.pop((generation,key),None)
        if result is None:
            if attempts>0:
                gui.window.after(25,lambda:poll(attempts-1))
            return
        if generation!=getattr(gui,"_forge_dash_generation",0) or str(Path(gui.root_path).resolve()).casefold()!=key:
            return
        ok,payload=result
        if not ok:
            _set(gui._forge_dash_attention,f"Dashboard refresh failed:\n{payload}",RED)
            return
        identity=payload["identity"]
        source=payload["source"]
        version=str(identity.get("projectBuild") or identity.get("projectVersion") or "UNDECLARED")
        health="READY" if getattr(gui,"backend",None) is not None else "ADAPTER"
        dirty=not bool(source.get("clean"))
        sync="SYNC" if source.get("githubConfigured") and source.get("ahead") in {0,None} and source.get("behind") in {0,None} else ("LOCAL" if not source.get("githubConfigured") else "DIVERGED")
        _set(gui._forge_dash_metrics["version"],version,CYAN)
        _set(gui._forge_dash_metrics["health"],health,GREEN if health=="READY" else YELLOW)
        _set(gui._forge_dash_metrics["source"],f"{source.get('branch') or '-'} · {'DIRTY' if dirty else sync}",YELLOW if dirty else GREEN)
        _set(gui._forge_dash_metrics["green"],payload["green"],GREEN if payload["green"]=="GREEN" else YELLOW)
        _set(gui._forge_dash_metrics["updates"],f"{payload['queued']} queued",YELLOW if payload["queued"] else GREEN)
        context=(
            f"Project : {identity.get('name')}\n"
            f"ID      : {identity.get('projectId')}\n"
            f"Version : {identity.get('projectVersion') or '-'}\n"
            f"Build   : {identity.get('projectBuild') or '-'}\n"
            f"Kind    : {identity.get('kind') or getattr(gui.contract,'kind','-')}\n"
            f"Root    : {root}\n\n"
            f"Branch  : {source.get('branch') or '-'}\n"
            f"HEAD    : {str(source.get('head') or '-')[:16]}\n"
            f"GitHub  : {'configured' if source.get('githubConfigured') else 'not configured'}\n"
            f"Provider: {getattr(gui.contract,'provider','project-owned / adapter') or 'project-owned / adapter'}"
        )
        _set(gui._forge_dash_context,context,TEXT)
        attention=[]
        if dirty: attention.append("• Working tree has uncommitted changes.")
        if payload["green"]!="GREEN": attention.append("• Current source is not certified GREEN.")
        if payload["queued"]: attention.append(f"• {payload['queued']} compatible update(s) are queued.")
        if payload["review"]: attention.append(f"• {payload['review']} update item(s) need review.")
        if not source.get("githubConfigured"): attention.append("• GitHub remote is not configured.")
        if not attention:
            attention=[
                "• No immediate project attention items detected.",
                "• Use the quick bar for Full Gate / Build / Test / Run.",
                "• Use Dashboard navigation for evidence and specialist workflows.",
            ]
        _set(gui._forge_dash_attention,"\n".join(attention),GREEN if attention[0].startswith("• No immediate") else MUTED)

    threading.Thread(target=worker,daemon=True,name="ForgeDashboardRefresh").start()
    gui.window.after(25,poll)
