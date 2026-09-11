#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from ForgeAdapterRegistry import resolve
from ForgeToolRegistry import load as load_tools
from ForgeToolRuntime import execute as execute_tool
from PCCAutoAdapter import ALIASES,status_payload
from PCCSurfaceCommon import ProjectContract
PROVIDER_VERSION='FORGEPY-GENERATED-ADAPTER-PROVIDER-1.0'
def _adapter(root:Path):
    contract=ProjectContract.load(root); matches=resolve(contract.project_id,contract.kind)
    if not matches: raise RuntimeError(f'No generated adapter matches {contract.project_id}:{contract.kind}')
    row=matches[0]
    if not isinstance(row.get('capabilities'),dict) or not row['capabilities']: raise RuntimeError('Generated adapter contains no executable capabilities')
    return contract,row
def _capability(command:str,caps:set[str])->str:
    if command in caps:return command
    for alias in ALIASES.get(command,()):
        if alias in caps:return alias
    raise RuntimeError(f'Generated adapter does not provide: {command}')
def run(root:Path,command:str)->int:
    contract,adapter=_adapter(root)
    if command=='status-json':
        payload=status_payload(root); payload['generatedAdapter']={'path':adapter.get('_path',''),'version':adapter.get('version',''),'capabilities':sorted((adapter.get('capabilities') or {}).keys()),'authority':'machine-local-generated'}
        print(json.dumps(payload)); return 0
    mapping=adapter.get('capabilities') or {}; capability=_capability(command,set(mapping)); tool_ids=[str(x) for x in mapping.get(capability) or []]
    tools={tool.tool_id:tool for tool in load_tools(contract.project_id)}
    for tool_id in tool_ids:
        tool=tools.get(tool_id)
        if tool is None:continue
        result=execute_tool(tool,emit=lambda line:print(line,end='')); return int(result.get('returncode') or 0)
    raise RuntimeError(f'Generated adapter capability {capability} has no available registered tool')
def main(argv=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument('command'); parser.add_argument('--root',required=True); args=parser.parse_args(argv)
    try:return run(Path(args.root).expanduser().resolve(),args.command)
    except Exception as exc:print(f'[FAIL] {exc}',file=sys.stderr); return 1
if __name__=='__main__':raise SystemExit(main())
