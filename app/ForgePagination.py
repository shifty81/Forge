#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Iterable, Sequence, TypeVar
T=TypeVar('T')
PAGINATION_VERSION='FORGEPY-PAGINATION-1.0'
@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T,...]; offset:int; limit:int; total:int
    @property
    def has_more(self)->bool: return self.offset+len(self.items)<self.total
    @property
    def next_offset(self)->int: return self.offset+len(self.items)
def paginate(rows:Sequence[T]|Iterable[T],offset:int=0,limit:int=200)->Page[T]:
    data=list(rows) if not isinstance(rows,Sequence) else rows
    o=max(0,int(offset)); l=max(1,min(5000,int(limit)))
    return Page(tuple(data[o:o+l]),o,l,len(data))
