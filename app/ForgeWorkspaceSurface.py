#!/usr/bin/env python3
from __future__ import annotations

import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

WORKSPACE_SURFACE_VERSION = "FORGEPY-WORKSPACE-SURFACE-2.0-F700"

BG = "#090b0e"
PANEL = "#11151a"
TEXT = "#edf2f5"
MUTED = "#929aa3"
CYAN = "#00d9ff"
GREEN = "#43f071"
YELLOW = "#ffd44a"
RED = "#ff5d68"


def _status(gui: Any, text: str, color: str = MUTED) -> None:
    try:
        gui.ide_status_label.configure(text=text, fg=color)
    except Exception:
        pass


def _root(gui: Any) -> Path:
    return Path(gui.root_path).expanduser().resolve()


def _root_key(gui: Any) -> str:
    try:
        return str(_root(gui)).casefold()
    except Exception:
        return str(getattr(gui, 'root_path', '')).casefold()


def _parts(rel: str) -> tuple[str, ...]:
    return tuple(part for part in str(rel).replace('\\', '/').split('/') if part)


def _build_index(files: list[str]) -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    dirs: dict[str, set[str]] = defaultdict(set)
    direct_files: dict[str, list[str]] = defaultdict(list)
    for rel in files:
        parts = _parts(rel)
        if not parts:
            continue
        parent = ''
        for part in parts[:-1]:
            dirs[parent].add(part)
            parent = f'{parent}/{part}' if parent else part
        direct_files[parent].append(rel)
    for rows in direct_files.values():
        rows.sort(key=str.casefold)
    return dict(dirs), dict(direct_files)


def _clear_tree(gui: Any) -> None:
    try:
        gui.ide_tree.delete(*gui.ide_tree.get_children())
    except Exception:
        pass
    gui._ide_paths = {}
    gui._forge_workspace_node_dirs = {}
    gui._forge_workspace_loaded_dirs = set()


def _populate_level(gui: Any, parent_iid: str, rel_dir: str) -> None:
    loaded = getattr(gui, '_forge_workspace_loaded_dirs', set())
    if rel_dir in loaded:
        return
    loaded.add(rel_dir)
    gui._forge_workspace_loaded_dirs = loaded

    try:
        for child in list(gui.ide_tree.get_children(parent_iid)):
            if str(child).startswith('ph'):
                gui.ide_tree.delete(child)
    except Exception:
        pass

    dirs = getattr(gui, '_forge_workspace_dirs', {}) or {}
    direct_files = getattr(gui, '_forge_workspace_direct_files', {}) or {}

    for name in sorted(dirs.get(rel_dir, set()), key=str.casefold):
        child_dir = f'{rel_dir}/{name}' if rel_dir else name
        child_iid = f'd{len(gui._forge_workspace_node_dirs) + 1}'
        try:
            gui.ide_tree.insert(parent_iid, 'end', iid=child_iid, text=name, open=False, values=('Folder',))
            gui._ide_paths[child_iid] = ''
            gui._forge_workspace_node_dirs[child_iid] = child_dir
            if dirs.get(child_dir) or direct_files.get(child_dir):
                placeholder = f'ph{len(gui._forge_workspace_node_dirs)}_{len(gui.ide_tree.get_children(child_iid))}'
                gui.ide_tree.insert(child_iid, 'end', iid=placeholder, text='…', values=('',))
        except Exception:
            continue

    for rel in direct_files.get(rel_dir, []):
        parts = _parts(rel)
        name = parts[-1] if parts else rel
        file_iid = f'f{len(gui._ide_paths) + 1}'
        try:
            gui.ide_tree.insert(parent_iid, 'end', iid=file_iid, text=name, values=('File',))
            gui._ide_paths[file_iid] = rel
        except Exception:
            pass


def _render_index(gui: Any, files: list[str], *, root_key: str) -> None:
    dirs, direct_files = _build_index(files)
    gui._forge_workspace_dirs = dirs
    gui._forge_workspace_direct_files = direct_files
    gui._forge_workspace_files = list(files)
    gui._forge_workspace_index_root = root_key

    _clear_tree(gui)
    try:
        gui.ide_tree.insert('', 'end', iid='ide-root', text=gui.contract.name, open=True, values=('Project',))
        gui._ide_paths['ide-root'] = ''
        gui._forge_workspace_node_dirs['ide-root'] = ''
    except Exception:
        return
    _populate_level(gui, 'ide-root', '')
    _status(gui, f'{len(files):,} editable files · lazy tree ready', GREEN)


def _on_tree_open(gui: Any, _event: Any = None) -> None:
    try:
        iid = gui.ide_tree.focus()
        if not iid:
            selected = gui.ide_tree.selection()
            iid = selected[0] if selected else ''
    except Exception:
        return
    rel_dir = getattr(gui, '_forge_workspace_node_dirs', {}).get(iid)
    if rel_dir is None:
        return
    _populate_level(gui, iid, rel_dir)


def refresh_files(gui: Any, *, force: bool = False) -> None:
    """Enumerate in a coordinated worker; render only one tree level on Tk."""
    if not hasattr(gui, 'ide_tree'):
        return

    root = _root(gui)
    root_key = str(root).casefold()

    if not force and str(getattr(gui, '_forge_workspace_index_root', '')).casefold() == root_key:
        files = list(getattr(gui, '_forge_workspace_files', []) or [])
        if files:
            try:
                if gui.ide_tree.get_children():
                    _status(gui, f'{len(files):,} editable files · lazy tree ready', GREEN)
                    return
            except Exception:
                pass
            _render_index(gui, files, root_key=root_key)
            return

    if (
        getattr(gui, '_forge_workspace_scan_running', False)
        and str(getattr(gui, '_forge_workspace_scan_root', '')).casefold() == root_key
    ):
        _status(gui, 'Scanning project files…', MUTED)
        return

    generation = int(getattr(gui, '_forge_workspace_scan_generation', 0) or 0) + 1
    gui._forge_workspace_scan_generation = generation
    gui._forge_workspace_scan_running = True
    gui._forge_workspace_scan_root = str(root)
    if not hasattr(gui, '_forge_workspace_scan_results'):
        gui._forge_workspace_scan_results = {}

    _clear_tree(gui)
    try:
        gui.ide_tree.insert('', 'end', iid='ide-root', text=gui.contract.name, open=True, values=('Project',))
        gui._ide_paths['ide-root'] = ''
    except Exception:
        pass
    _status(gui, 'Scanning project files…', MUTED)

    def worker() -> None:
        try:
            from VaultIde import list_files
            from ForgeLoadCoordinator import COORDINATOR
            files = list(COORDINATOR.run_scan(
                f'workspace-index:{root.name}',
                lambda: list_files(root),
                wait_for_idle=2.0,
            ))
            result = (generation, str(root), files, '')
        except Exception as exc:
            result = (generation, str(root), [], str(exc))
        gui._forge_workspace_scan_results[(generation, root_key)] = result

    def poll(attempts: int = 2400) -> None:
        token = (generation, root_key)
        result = getattr(gui, '_forge_workspace_scan_results', {}).pop(token, None)
        current_generation = int(getattr(gui, '_forge_workspace_scan_generation', 0) or 0)
        if generation != current_generation:
            return
        if result is None:
            if attempts > 0:
                gui.window.after(25, lambda: poll(attempts - 1))
            else:
                gui._forge_workspace_scan_running = False
                _status(gui, 'Workspace file scan timed out.', YELLOW)
            return
        result_generation, scanned_root, files, error = result
        gui._forge_workspace_scan_running = False
        if result_generation != generation or scanned_root.casefold() != _root_key(gui):
            return
        if error:
            _status(gui, f'File scan failed: {error}', RED)
            return
        _render_index(gui, files, root_key=scanned_root.casefold())

    threading.Thread(target=worker, daemon=True, name='ForgeWorkspaceLazyScan').start()
    gui.window.after(25, poll)


def _read_file_async(gui: Any, rel: str) -> None:
    generation = int(getattr(gui, '_forge_workspace_read_generation', 0) or 0) + 1
    gui._forge_workspace_read_generation = generation
    if not hasattr(gui, '_forge_workspace_read_results'):
        gui._forge_workspace_read_results = {}
    root = _root(gui)
    root_key = str(root).casefold()
    _status(gui, f'Opening {rel}…', MUTED)

    def worker() -> None:
        try:
            from VaultIde import read_file
            data = read_file(root, rel)
            result = (generation, root_key, rel, data, '')
        except Exception as exc:
            result = (generation, root_key, rel, {}, str(exc))
        gui._forge_workspace_read_results[(generation, root_key)] = result

    def poll(attempts: int = 400) -> None:
        token = (generation, root_key)
        result = getattr(gui, '_forge_workspace_read_results', {}).pop(token, None)
        if generation != int(getattr(gui, '_forge_workspace_read_generation', 0) or 0):
            return
        if result is None:
            if attempts > 0:
                gui.window.after(25, lambda: poll(attempts - 1))
            return
        result_generation, result_root, result_rel, data, error = result
        if result_generation != generation or result_root != _root_key(gui):
            return
        if error:
            _status(gui, error, RED)
            return
        try:
            gui._ide_current_path = result_rel
            gui.ide_editor.configure(state='normal')
            gui.ide_editor.delete('1.0', 'end')
            gui.ide_editor.insert('1.0', data.get('text', ''))
            _status(gui, result_rel, TEXT)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name='ForgeWorkspaceFileRead').start()
    gui.window.after(25, poll)


def selection_changed(gui: Any, _event: Any = None) -> None:
    try:
        selected = gui.ide_tree.selection()
        if not selected:
            return
        rel = gui._ide_paths.get(selected[0], '')
    except Exception:
        return
    if rel:
        _read_file_async(gui, rel)


def save_current(gui: Any) -> None:
    rel = str(getattr(gui, '_ide_current_path', '') or '')
    if not rel:
        return
    if getattr(gui, '_forge_workspace_save_running', False):
        _status(gui, 'Save already in progress…', MUTED)
        return

    # Reading Text widget state is a Tk operation, so capture it on the UI thread;
    # the filesystem write itself happens in a worker.
    try:
        text = gui.ide_editor.get('1.0', 'end-1c')
    except Exception as exc:
        _status(gui, str(exc), RED)
        return
    root = _root(gui)
    root_key = str(root).casefold()
    generation = int(getattr(gui, '_forge_workspace_save_generation', 0) or 0) + 1
    gui._forge_workspace_save_generation = generation
    gui._forge_workspace_save_running = True
    if not hasattr(gui, '_forge_workspace_save_results'):
        gui._forge_workspace_save_results = {}
    _status(gui, f'Saving {rel}…', MUTED)

    def worker() -> None:
        try:
            from VaultIde import write_file
            info = write_file(root, rel, text)
            result = (True, info, '')
        except Exception as exc:
            result = (False, {}, str(exc))
        gui._forge_workspace_save_results[(generation, root_key, rel)] = result

    def poll(attempts: int = 800) -> None:
        token = (generation, root_key, rel)
        result = getattr(gui, '_forge_workspace_save_results', {}).pop(token, None)
        if result is None:
            if attempts > 0:
                gui.window.after(25, lambda: poll(attempts - 1))
            else:
                gui._forge_workspace_save_running = False
                _status(gui, f'Save timed out: {rel}', YELLOW)
            return
        gui._forge_workspace_save_running = False
        ok, info, error = result
        if not ok:
            try:
                gui._popup('ForgePY Workspace', error, kind='error')
            except Exception:
                _status(gui, error, RED)
            return
        if _root_key(gui) == root_key and str(getattr(gui, '_ide_current_path', '') or '') == rel:
            _status(gui, f"Saved · {rel} · {info.get('bytes', 0)} bytes", GREEN)

    threading.Thread(target=worker, daemon=True, name='ForgeWorkspaceFileSave').start()
    gui.window.after(25, poll)


def invalidate(gui: Any) -> None:
    """Invalidate old-project view without doing any I/O."""
    gui._forge_workspace_scan_generation = int(getattr(gui, '_forge_workspace_scan_generation', 0) or 0) + 1
    gui._forge_workspace_read_generation = int(getattr(gui, '_forge_workspace_read_generation', 0) or 0) + 1
    gui._forge_workspace_save_generation = int(getattr(gui, '_forge_workspace_save_generation', 0) or 0) + 1
    try:
        if str(getattr(gui, '_forge_workspace_index_root', '')).casefold() != _root_key(gui):
            _clear_tree(gui)
            _status(gui, 'Project changed · Workspace will index on open', MUTED)
    except Exception:
        pass



def _workspace_overview(gui: Any) -> None:
    try:
        from ForgeProjectIdentity import resolve
        row=resolve(_root(gui))
        source=""
        try:
            from ForgeStatusCache import fast_source_status
            status=fast_source_status(_root(gui))
            source=f"{status.get('branch') or '-'} · {'CLEAN' if status.get('clean') else 'DIRTY'}"
        except Exception:
            pass
        text=(
            f"{row.get('name')}\n\n"
            f"Version : {row.get('projectVersion') or '-'}\n"
            f"Build   : {row.get('projectBuild') or '-'}\n"
            f"Root    : {_root(gui)}\n"
            f"Source  : {source}\n\n"
            "Select a file from Project Files to edit it.\n"
            "Use Quick Open to filter the cached project index without rescanning.\n"
            "Build / Run / Full Gate remain in the Workspace quick bar.\n"
            "Execution output remains in Forge Console."
        )
        gui.ide_editor.configure(state="normal")
        gui.ide_editor.delete("1.0","end")
        gui.ide_editor.insert("1.0",text)
        gui.ide_editor.configure(state="disabled")
    except Exception:
        pass

def quick_filter(gui: Any) -> None:
    var=getattr(gui,"_forge_workspace_filter_var",None)
    query=str(var.get() if var is not None else "").strip().casefold()
    files=list(getattr(gui,"_forge_workspace_files",[]) or [])
    if not query:
        if str(getattr(gui,"_forge_workspace_index_root","")).casefold()==_root_key(gui):
            _render_index(gui,files,root_key=_root_key(gui))
        return
    matches=[rel for rel in files if query in str(rel).casefold()][:500]
    _clear_tree(gui)
    try:
        gui.ide_tree.insert("","end",iid="ide-root",text=f"Search · {len(matches)} result(s)",open=True,values=("Search",))
        gui._ide_paths["ide-root"]=""
        for rel in matches:
            iid=f"f{len(gui._ide_paths)+1}"
            gui.ide_tree.insert("ide-root","end",iid=iid,text=rel,values=("File",))
            gui._ide_paths[iid]=rel
        _status(gui,f"Quick Open · {len(matches)} match(es)",CYAN)
    except Exception:
        pass

def build(gui: Any, parent: Any) -> None:
    """Cheap native Workspace shell with no external runtime readiness work."""
    tk = gui.tk
    ttk = gui.ttk

    shell = tk.Frame(parent, bg=BG)
    shell.pack(fill='both', expand=True, padx=8, pady=6)

    header = tk.Frame(shell, bg=BG)
    header.pack(fill='x', pady=(0, 5))
    tk.Label(header, text='Workspace', bg=BG, fg=TEXT, font=('Segoe UI Semibold', 13), anchor='w').pack(side='left')
    gui.ide_status_label = tk.Label(header, text='Ready', bg=BG, fg=MUTED, font=('Segoe UI', 8), anchor='e')
    gui.ide_status_label.pack(side='right')

    toolbar = tk.Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground='#28313a')
    toolbar.pack(fill='x', pady=(0, 6))
    inner=tk.Frame(toolbar,bg=PANEL)
    inner.pack(fill='x',padx=8,pady=5)
    gui._button(inner, 'SAVE', lambda: save_current(gui), primary=True, compact=True).pack(side='left', padx=(0, 5))
    gui._button(inner, 'REFRESH FILES', lambda: refresh_files(gui, force=True), compact=True).pack(side='left', padx=5)
    gui._forge_workspace_filter_var=tk.StringVar()
    search=tk.Entry(inner,textvariable=gui._forge_workspace_filter_var,bg='#090c10',fg=TEXT,insertbackground=TEXT,relief='flat',font=('Segoe UI',9),width=34)
    search.pack(side='right',ipady=5)
    tk.Label(inner,text='QUICK OPEN',bg=PANEL,fg=MUTED,font=('Segoe UI Semibold',7)).pack(side='right',padx=(8,6))
    search.bind('<Return>',lambda _e:quick_filter(gui))
    search.bind('<Escape>',lambda _e:(gui._forge_workspace_filter_var.set(''),quick_filter(gui)))

    panes = tk.PanedWindow(shell, orient='horizontal', bg=BG, bd=0, sashwidth=5, sashrelief='flat', showhandle=False, opaqueresize=True)
    panes.pack(fill='both', expand=True)

    left = tk.Frame(panes, bg=PANEL)
    right = tk.Frame(panes, bg='#07090b')

    gui.ide_tree = ttk.Treeview(left, columns=('type',), show='tree headings', selectmode='browse')
    gui.ide_tree.heading('#0', text='Project Files')
    gui.ide_tree.heading('type', text='')
    gui.ide_tree.column('#0', width=260, stretch=True)
    gui.ide_tree.column('type', width=62, stretch=False, anchor='e')
    tree_scroll = ttk.Scrollbar(left, orient='vertical', command=gui.ide_tree.yview)
    gui.ide_tree.configure(yscrollcommand=tree_scroll.set)
    gui.ide_tree.pack(side='left', fill='both', expand=True, padx=(6, 0), pady=6)
    tree_scroll.pack(side='right', fill='y', padx=(0, 6), pady=6)

    gui.ide_editor_host = tk.Frame(right, bg='#07090b')
    gui.ide_editor_host.pack(fill='both', expand=True, padx=6, pady=6)
    gui.ide_editor = tk.Text(
        gui.ide_editor_host, bg=BG, fg=TEXT, insertbackground=CYAN,
        selectbackground='#21404a', selectforeground=TEXT, bd=0, relief='flat',
        font=('Consolas', 10), undo=True, wrap='none'
    )
    y = ttk.Scrollbar(gui.ide_editor_host, command=gui.ide_editor.yview)
    x = ttk.Scrollbar(gui.ide_editor_host, command=gui.ide_editor.xview, orient='horizontal')
    gui.ide_editor.configure(yscrollcommand=y.set, xscrollcommand=x.set)
    gui.ide_editor.grid(row=0, column=0, sticky='nsew')
    y.grid(row=0, column=1, sticky='ns')
    x.grid(row=1, column=0, sticky='ew')
    gui.ide_editor_host.grid_rowconfigure(0, weight=1)
    gui.ide_editor_host.grid_columnconfigure(0, weight=1)

    panes.add(left, minsize=190, width=290)
    panes.add(right, minsize=420, width=760, stretch='always')

    gui._ide_paths = {}
    gui._forge_workspace_node_dirs = {}
    gui._forge_workspace_loaded_dirs = set()
    gui._ide_current_path = ''

    gui.ide_tree.bind('<<TreeviewOpen>>', lambda event: _on_tree_open(gui, event), add='+')
    gui.ide_tree.bind('<<TreeviewSelect>>', lambda event: selection_changed(gui, event), add='+')
    gui.ide_editor.bind('<Control-s>', lambda _e: (save_current(gui), 'break')[1])
    gui.window.after(1, lambda: _workspace_overview(gui))
