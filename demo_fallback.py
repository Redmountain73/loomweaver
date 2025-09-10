# demo_fallback.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from zfc import zfc_run

def primary():
    raise RuntimeError("nope")

def fallback():
    return 555

print(
    zfc_run(
        primary,
        default=None,
        cb_key="module:fallback-demo",
        cache_key="module:fallback-demo",
        retry_budget=0,
        prefer_cache=False,   # try fallback before cache for this demo
        fallback_fn=fallback, # our side door
    )
)
