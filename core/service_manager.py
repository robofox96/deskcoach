"""
Service Manager - Start/Stop background monitoring service.

Manages the dev_runner.py subprocess with pidfile tracking and graceful shutdown.
PRIVACY: No frames saved, only process management.
"""

import os
import sys
import json
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


if hasattr(signal, "SIGKILL"):
    _TERM_SIGNAL = signal.SIGTERM
    _KILL_SIGNAL = signal.SIGKILL
else:
    _TERM_SIGNAL = signal.SIGTERM
    _KILL_SIGNAL = signal.SIGTERM

class ServiceManager:
    """
    Manages the background monitoring service (dev_runner.py).
    
    Single-instance enforcement via pidfile.
    Graceful shutdown with SIGTERM + timeout fallback to SIGKILL.
    """
    
    def __init__(
        self,
        pidfile: str = "storage/deskcoach.pid",
        service_info_file: str = "storage/service.json",
        log_file: str = "storage/deskcoach.log"
    ):
        """
        Initialize service manager.
        
        Args:
            pidfile: Path to PID file
            service_info_file: Path to service info JSON
            log_file: Path to log file for stdout/stderr
        """
        self.pidfile = Path(pidfile)
        self.service_info_file = Path(service_info_file)
        self.log_file = Path(log_file)
        
        # Ensure storage directory exists
        self.pidfile.parent.mkdir(parents=True, exist_ok=True)
    
    def is_running(self) -> bool:
        """
        Check if the background service is running.
        
        Returns:
            True if running, False otherwise
        """
        if not self.pidfile.exists():
            return False
        
        try:
            with open(self.pidfile, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 just checks existence
                return True
            except OSError:
                # Process doesn't exist, clean up stale pidfile
                self._cleanup()
                return False
        except (ValueError, FileNotFoundError):
            # Invalid pidfile
            self._cleanup()
            return False
    
    def get_pid(self) -> Optional[int]:
        """
        Get the PID of the running service.
        
        Returns:
            PID if running, None otherwise
        """
        if not self.is_running():
            return None
        
        try:
            with open(self.pidfile, 'r') as f:
                return int(f.read().strip())
        except (ValueError, FileNotFoundError):
            return None
    
    def get_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Get service information (started_at, cmdline, etc.).
        
        Returns:
            Service info dict or None if not running
        """
        if not self.is_running():
            return None
        
        if not self.service_info_file.exists():
            return None
        
        try:
            with open(self.service_info_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
    
    def start_background(
        self,
        camera_index: int = 0,
        target_fps: float = 8.0,
        diagnostics: bool = True,
        preset: str = "sensitive"
    ) -> Optional[int]:
        """
        Start the background monitoring service.
        
        Single-instance enforcement: if already running, returns existing PID.
        
        Args:
            camera_index: Camera device index
            target_fps: Target frames per second
            diagnostics: Enable diagnostic output
            preset: Sensitivity preset
            
        Returns:
            PID of the service, or None if failed to start
        """
        # Check if already running
        if self.is_running():
            print(f"[SERVICE] Already running (PID: {self.get_pid()})")
            return self.get_pid()
        
        # Build command line
        frozen = getattr(sys, "frozen", False)
        if frozen:
            # In a PyInstaller bundle, sys.executable points to the main launcher
            repo_root = Path(sys.executable).resolve().parent
        else:
            # When running from source, repo_root is the project root
            repo_root = Path(__file__).parent.parent.resolve()

        # Optional override for where storage/** files should live.
        # When running inside the macOS .app bundle, entry_launcher sets this
        # so that all storage is redirected under:
        #   ~/Library/Application Support/DeskCoach/
        storage_root_env = os.environ.get("DESKCOACH_STORAGE_ROOT")
        storage_cwd = Path(storage_root_env).expanduser() if storage_root_env else repo_root

        python_exe = sys.executable
        dev_runner = repo_root / "dev_runner.py"
        
        if frozen:
            # Inside the bundled app, re-invoke the same executable in service
            # mode. The entry launcher will detect the --service flag and
            # delegate to dev_runner.main(), so dev_runner does not need to
            # exist as a real file on disk in the bundle.
            cmd = [
                python_exe,
                "--service",
                "--camera", str(camera_index),
                "--fps", str(target_fps),
                "--preset", preset,
            ]
        else:
            if not dev_runner.exists():
                print(f"[SERVICE] Error: dev_runner.py not found at {dev_runner}")
                return None
            cmd = [
                python_exe,
                str(dev_runner),
                "--camera", str(camera_index),
                "--fps", str(target_fps),
                "--preset", preset,
            ]
        
        if diagnostics:
            cmd.append("--diagnostics")
        
        try:
            # Open log file for stdout/stderr
            log_handle = open(self.log_file, 'w')
            
            # Start subprocess (detached, logs to file)
            process = subprocess.Popen(
                cmd,
                # Use storage_cwd so that any relative storage/ paths in the
                # background service land under the configured storage root.
                cwd=str(storage_cwd),
                stdout=log_handle,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                start_new_session=True,  # Detach from parent
            )
            
            pid = process.pid
            
            # Write pidfile
            with open(self.pidfile, 'w') as f:
                f.write(str(pid))
            
            # Write service info
            service_info = {
                "pid": pid,
                "started_at": datetime.now().isoformat(),
                "cmdline": cmd,
                "camera_index": camera_index,
                "target_fps": target_fps,
                "diagnostics": diagnostics,
                "preset": preset
            }
            
            # Atomic write
            temp_file = self.service_info_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(service_info, f, indent=2)
            os.replace(temp_file, self.service_info_file)
            
            print(f"[SERVICE] Started background service (PID: {pid})")
            return pid
            
        except Exception as e:
            print(f"[SERVICE] Error starting service: {e}")
            self._cleanup()
            return None
    
    def stop_background(self, timeout: float = 5.0) -> bool:
        """
        Stop the background monitoring service.
        
        Graceful shutdown: SIGTERM with timeout, fallback to SIGKILL.
        
        Args:
            timeout: Seconds to wait for graceful shutdown
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_running():
            print("[SERVICE] Not running")
            return True
        
        pid = self.get_pid()
        if pid is None:
            return True
        
        try:
            print(f"[SERVICE] Stopping service (PID: {pid})...")
            
            # Send SIGTERM for graceful shutdown
            os.kill(pid, _TERM_SIGNAL)
            
            # Wait for process to exit
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)  # Check if still alive
                    time.sleep(0.1)
                except OSError:
                    # Process exited
                    print(f"[SERVICE] Stopped gracefully")
                    self._cleanup()
                    return True
            
            # Timeout: force kill
            print(f"[SERVICE] Timeout, force killing...")
            try:
                os.kill(pid, _KILL_SIGNAL)
                time.sleep(0.5)
            except OSError:
                pass
            
            self._cleanup()
            print(f"[SERVICE] Stopped (force)")
            return True
            
        except Exception as e:
            print(f"[SERVICE] Error stopping service: {e}")
            self._cleanup()
            return False
    
    def get_logs(self, lines: int = 100) -> str:
        """
        Get recent logs from the service.
        
        Args:
            lines: Number of lines to return (from end of file)
            
        Returns:
            Log contents as string
        """
        if not self.log_file.exists():
            return "No logs available (log file not found)"
        
        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return ''.join(recent_lines)
        except Exception as e:
            return f"Error reading logs: {e}"
    
    def tail_logs(self, lines: int = 20) -> str:
        """
        Get tail of logs (last N lines).
        
        Args:
            lines: Number of lines to return
            
        Returns:
            Last N lines of logs
        """
        return self.get_logs(lines=lines)
    
    def clear_logs(self):
        """Clear the log file."""
        try:
            if self.log_file.exists():
                self.log_file.unlink()
        except Exception:
            pass
    
    def _cleanup(self):
        """Clean up pidfile and service info."""
        try:
            if self.pidfile.exists():
                self.pidfile.unlink()
        except Exception:
            pass
        
        try:
            if self.service_info_file.exists():
                self.service_info_file.unlink()
        except Exception:
            pass


# Global instance
_service_manager = None

def get_service_manager() -> ServiceManager:
    """Get the global ServiceManager instance."""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
