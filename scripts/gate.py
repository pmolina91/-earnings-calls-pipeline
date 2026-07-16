#!/usr/bin/env python3
"""Gate: decide se este runner deve executar o job (call nas próximas 6h, não no passado)."""
import json, sys, os
from datetime import datetime, timezone
spec = json.load(open(sys.argv[1]))
call = datetime.fromisoformat(spec['call_datetime_utc'].replace('Z','+00:00'))
now = datetime.now(timezone.utc)
delta_h = (call - now).total_seconds()/3600
run = 'yes' if -0.5 <= delta_h <= 5.5 else 'no'
print(f"call={call.isoformat()} now={now.isoformat()} delta_h={delta_h:.2f} run={run}")
with open(os.environ['GITHUB_OUTPUT'],'a') as f: f.write(f"run={run}\n")
