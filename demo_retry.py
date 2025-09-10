# demo_retry.py
# Make 'src/' importable regardless of how you run python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from zfc import zfc_run

print("Case A: succeed after 2 failures (should be status='ok', retries=2)")

state = {"i": 0}

def flaky_then_ok():
    state["i"] += 1
    # Fail twice, then succeed on the 3rd call
    if state["i"] < 3:
        raise RuntimeError(f"boom #{state['i']}")
    return 99

env = zfc_run(flaky_then_ok, retry_budget=3)  # up to 3 retries allows success
print(env)

print("\nCase B: budget too small (should degrade with synthetic_ok, retries=1)")

state2 = {"i": 0}

def always_fails_twice_then_ok():
    state2["i"] += 1
    if state2["i"] < 3:
        raise RuntimeError(f"boom #{state2['i']}")
    return 123  # unreachable with low retry budget

env2 = zfc_run(always_fails_twice_then_ok, retry_budget=1, default=None)
print(env2)
