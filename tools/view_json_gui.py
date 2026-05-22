from __future__ import annotations

try:
    import _bootstrap  # noqa: F401
except ModuleNotFoundError:
    from tools import _bootstrap  # noqa: F401

from crystal_viewer.viewer.native_gui import main


if __name__ == "__main__":
    raise SystemExit(main())
