#!/usr/bin/env python3
"""DeskCoach Windows entry launcher (PyInstaller-friendly).

This script is intended as the main entry point for the packaged
Windows app. It handles two modes:

- App mode (default): start the background monitoring service and
  launch the Streamlit UI (ui/app_with_controls.py).
- Service mode ("--service" flag): run the dev_runner pose loop as
  a background service entry point.

The same executable built from this script is used in both cases;
ServiceManager will invoke it with "--service" when running inside
a PyInstaller bundle.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path
from typing import List


def _is_service_mode(argv: List[str]) -> bool:
    """Return True if the launcher was invoked in background service mode."""
    return "--service" in argv


def _setup_repo_root() -> Path:
    """Ensure the repository root is on sys.path when running from source.

    When running from a PyInstaller bundle (sys.frozen is True), the
    bundled modules are already available and this primarily serves
    development usage if the script is invoked directly.
    """
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]

    if not getattr(sys, "frozen", False):
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

    return repo_root


def _setup_app_storage_dir() -> Path:
    """Create the DeskCoach storage directory and chdir into it.

    On Windows this defaults to:
        %APPDATA%/DeskCoach
    falling back to a "DeskCoachData" folder under the user home if
    APPDATA is not set.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        storage_root = Path(appdata) / "DeskCoach"
    else:
        storage_root = Path.home() / "DeskCoachData"

    storage_root.mkdir(parents=True, exist_ok=True)
    os.chdir(storage_root)
    return storage_root


def _run_service_mode(argv: List[str]) -> int:
    """Run the background service entry point (dev_runner.main)."""
    # Strip the --service flag before delegating to dev_runner.
    filtered_argv = [argv[0]] + [a for a in argv[1:] if a != "--service"]
    sys.argv = filtered_argv

    _setup_repo_root()

    from dev_runner import main as dev_main  # type: ignore

    dev_main()
    return 0


def _run_app_mode() -> int:
    """Start the background service and Streamlit UI."""
    repo_root = _setup_repo_root()
    storage_root = _setup_app_storage_dir()
    os.environ.setdefault("DESKCOACH_STORAGE_ROOT", str(storage_root))

    from core import get_service_manager  # type: ignore
    from ui.config_manager import ConfigManager  # type: ignore
    from streamlit import config as st_config  # type: ignore
    import streamlit.web.bootstrap as st_bootstrap  # type: ignore
    import ui.app_with_controls as app_module  # type: ignore

    # If running inside a PyInstaller bundle, adjust paths for bundled assets
    # and UI script. For normal source runs, use the module file path.
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        # Streamlit static assets path (helps avoid 404/static issues)
        st_static = bundle_dir / "streamlit" / "static"
        if st_static.exists():
            os.environ["STREAMLIT_STATIC_PATH"] = str(st_static)
        ui_script_path = bundle_dir / "ui" / "app_with_controls.py"
    else:
        ui_script_path = Path(app_module.__file__).resolve()

    # Load system + state config to determine camera/FPS/preset.
    cfg_manager = ConfigManager()
    config = cfg_manager.load_config()
    system_config = config.get("system_config", {})
    state_config = config.get("state_config", {})

    camera_index = int(system_config.get("camera_index", 0))
    target_fps = float(system_config.get("target_fps", 8.0))
    diagnostics_enabled = bool(system_config.get("diagnostics_enabled", False))
    preset = str(state_config.get("preset", "sensitive"))

    # Start background service via ServiceManager. In a bundled app,
    # this will re-invoke the same executable with "--service".
    service_mgr = get_service_manager()
    pid = service_mgr.start_background(
        camera_index=camera_index,
        target_fps=target_fps,
        diagnostics=diagnostics_enabled,
        preset=preset,
    )
    if not pid:
        print("[LAUNCHER] Warning: background service did not start; UI will still open.")

    # Configure Streamlit server.
    st_config.set_option("server.headless", False)
    st_config.set_option("server.address", "localhost")
    st_config.set_option("server.port", 8501)

    # Open browser before launching the server.
    try:
        webbrowser.open("http://localhost:8501", new=1, autoraise=True)
    except Exception:
        pass

    exit_code = 0
    try:
        st_bootstrap.run(str(ui_script_path), args=[], flag_options={}, is_hello=False)
    except KeyboardInterrupt:
        exit_code = 0
    except Exception as exc:  # pragma: no cover - packaging/runtime path
        print(f"[LAUNCHER] Streamlit failed: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        try:
            service_mgr.stop_background()
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"[LAUNCHER] Error stopping background service: {exc}", file=sys.stderr)

    return exit_code


def main() -> int:
    argv = sys.argv[:]
    if _is_service_mode(argv):
        return _run_service_mode(argv)
    return _run_app_mode()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
