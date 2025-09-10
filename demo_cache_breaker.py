# demo_cache_breaker.py
# Makes 'src/' importable no matter how you run Python
import os, sys, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from zfc import zfc_run

# Build kwargs that match whatever version of zfc_run you currently have
kwargs = {}
sig = inspect.signature(zfc_run)
if "cb_key" in sig.parameters:
    kwargs["cb_key"] = "module:demo"
if "cache_key" in sig.parameters:
    kwargs["cache_key"] = "module:demo"

def ok():
    return 123

print("prime:", zfc_run(ok, **kwargs))

def boom():
    raise RuntimeError("x")

# Trip the breaker with repeated failures (no retries so it fails fast)
for _ in range(5):
    zfc_run(boom, default=None, retry_budget=0, **kwargs)

# If cache is supported, this should now serve from cache when CB is open.
# If cache isn't in your zfc yet, you'll still see a synthetic_ok due to the circuit breaker.
print("open:", zfc_run(boom, default=None, retry_budget=0, **kwargs))
