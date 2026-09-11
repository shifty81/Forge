#!/usr/bin/env python3
from __future__ import annotations
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; APP=ROOT/'app'
if str(APP) not in sys.path:sys.path.insert(0,str(APP))
from ForgePatchBuilder import build

def main(argv=None)->int:
    p=argparse.ArgumentParser(description='Build a governed ForgePY patch transport without runtime/machine-local state.')
    p.add_argument('--base',required=True);p.add_argument('--target',required=True);p.add_argument('--out',required=True)
    p.add_argument('--base-build',default='');p.add_argument('--target-build',default='');p.add_argument('--target-version',default='')
    p.add_argument('--patch-id',default='');p.add_argument('--title',default='')
    a=p.parse_args(argv)
    result=build(Path(a.base),Path(a.target),Path(a.out),base_build=a.base_build,target_build=a.target_build,target_version=a.target_version,patch_id=a.patch_id,title=a.title)
    print(f"[PASS] {result['path']} ({result['files']} governed row(s))")
    return 0
if __name__=='__main__':raise SystemExit(main())
