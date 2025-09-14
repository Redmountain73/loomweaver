# src/vm.py
from __future__ import annotations

# Optional backend "zfc": keep import non-fatal so CI/dev without it don't crash.
try:
    from zfc import zfc_run  # type: ignore
except Exception:
    def zfc_run(*args, **kwargs):  # noqa: D401
        """Placeholder backend: raise only if invoked without zfc installed."""
        raise RuntimeError(
            "The 'zfc' backend is not installed. "
            "Install the optional dependency or configure the VM to use a different backend."
        )

# Minimal placeholder so imports of VM type don't explode.
class VM:
    def __init__(self, *_, **__):
        pass
