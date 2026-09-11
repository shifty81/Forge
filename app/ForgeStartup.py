#!/usr/bin/env python3
from __future__ import annotations
import queue, threading, time
from pathlib import Path
from typing import Any, Callable
from ForgeFirstRun import needed as first_run_needed, initialize as first_run_initialize
from ForgeVaultBootstrap import ensure_layout
from ForgeRepair import diagnose, repair_safe

STARTUP_VERSION='FORGEPY-STARTUP-0.2'

def checks(project_root: Path|None=None, emit: Callable[[str,str],None]|None=None) -> dict[str,Any]:
    emit=emit or (lambda _name,_state:None); phases=[]; repair_attempted=False
    def result_ok(detail: Any) -> bool:
        return not (isinstance(detail,dict) and detail.get('ok') is False)
    def phase(name, fn, *, required: bool=True):
        emit(name,'RUNNING')
        try:
            detail=fn(); ok=result_ok(detail); state='PASS' if ok else ('FAIL' if required else 'WARN')
        except Exception as exc:
            detail=str(exc); ok=False; state='FAIL' if required else 'WARN'
        phases.append({'name':name,'state':state,'required':required,'detail':detail}); emit(name,state); return ok
    phase('Runtime integrity', lambda: __import__('ForgePYVersion').BUILD)
    phase('Vault configuration', ensure_layout)
    if first_run_needed(): phase('First-time initialization', first_run_initialize)
    package_ok=phase('Package / repair health', diagnose)
    if not package_ok:
        repair_attempted=True; emit('Safe repair','RUNNING')
        try: repair_detail=repair_safe(); repair_ok=result_ok(repair_detail); repair_state='PASS' if repair_ok else 'FAIL'
        except Exception as exc: repair_detail=str(exc); repair_ok=False; repair_state='FAIL'
        phases.append({'name':'Safe repair','state':repair_state,'required':True,'detail':repair_detail}); emit('Safe repair',repair_state)
        if repair_ok: phase('Package / repair recheck', diagnose)
    phase('Project registry', lambda: len(__import__('PCCSurfaceCommon').ProjectRegistry().entries()))
    if project_root is not None: phase('Active project', lambda: __import__('PCCSurfaceCommon').ProjectContract.load(project_root).name, required=False)
    ok=all(row['state']=='PASS' for row in phases if row.get('required',True))
    return {'ok':ok,'repairAttempted':repair_attempted,'phases':phases}

def show_startup_screen(project_root: Path|None=None, *, minimum_ms:int=420, keep_root:bool=False) -> dict[str,Any] | tuple[dict[str,Any], Any]:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        result = checks(project_root)
        return (result, None) if keep_root else result
    root=tk.Tk(); root.title('ForgePY — Starting'); root.geometry('520x330'); root.resizable(False,False)
    root.configure(bg='#090b0e')
    try:
        from ForgePYBrand import apply_window_icon; apply_window_icon(root)
    except Exception: pass
    frame=tk.Frame(root,bg='#090b0e'); frame.pack(fill='both',expand=True,padx=24,pady=20)
    tk.Label(frame,text='FORGEPY',bg='#090b0e',fg='#00d9ff',font=('Segoe UI Semibold',20)).pack(anchor='w')
    tk.Label(frame,text='Startup self-test and machine initialization',bg='#090b0e',fg='#929aa3',font=('Segoe UI',9)).pack(anchor='w',pady=(2,15))
    status=tk.Label(frame,text='Preparing…',bg='#090b0e',fg='#edf2f5',font=('Segoe UI',10),anchor='w'); status.pack(fill='x')
    progress=ttk.Progressbar(frame,mode='indeterminate'); progress.pack(fill='x',pady=(10,12)); progress.start(12)
    detail=tk.Text(frame,height=9,bg='#11151a',fg='#929aa3',bd=0,font=('Consolas',8)); detail.pack(fill='both',expand=True); detail.configure(state='disabled')
    q:queue.Queue=queue.Queue(); result={}; started=time.monotonic(); finished={'done':False}
    def emit(name,state): q.put((name,state))
    def worker():
        try:
            result.update(checks(project_root,emit))
        finally:
            q.put(('__DONE__',''))
    threading.Thread(target=worker,daemon=True,name='ForgePYStartup').start()
    def poll():
        while True:
            try: name,state=q.get_nowait()
            except queue.Empty: break
            if name=='__DONE__':
                finished['done']=True
                status.configure(text='Ready' if result.get('ok') else 'Startup checks completed with warnings')
                continue
            status.configure(text=name)
            detail.configure(state='normal'); detail.insert('end',f'{state:<8} {name}\n'); detail.see('end'); detail.configure(state='disabled')
        if finished['done'] and (time.monotonic()-started)*1000 >= minimum_ms:
            progress.stop()
            if keep_root:
                # Reuse the Tk interpreter, but never reuse the splash widgets.
                # F60R66 quit the splash mainloop correctly but left `frame` packed
                # into the shared root, so ForgeGui rendered underneath the old
                # startup surface.  Tear down the splash UI before handing the root
                # to the main application.
                try:
                    frame.destroy()
                except Exception:
                    pass
                root.withdraw()
                root.quit()
            else:
                root.destroy()
            return
        root.after(40,poll)
    root.after(40,poll); root.mainloop(); return (result, root) if keep_root else result
