#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
UI_METRICS_VERSION='FORGEPY-UI-METRICS-1.0'
@dataclass(frozen=True)
class WorkspaceMetrics:
    left_nav:int=150; right_rail:int=205; console_ratio:float=.32; min_controls:int=390; min_console:int=420
    def normalized(self,width:int)->dict[str,Any]:
        available=max(0,int(width)-self.left_nav-self.right_rail)
        console=max(self.min_console,int(available*self.console_ratio)); controls=max(self.min_controls,available-console)
        if controls+console>available and available>0:
            scale=available/max(1,controls+console);controls=int(controls*scale);console=available-controls
        return {'schema':'forgepy.workspace-metrics.v1','version':UI_METRICS_VERSION,'width':width,'controls':controls,'console':console,'rightRail':self.right_rail,'leftNav':self.left_nav}
