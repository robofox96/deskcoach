"""
Calibration Runner - Subprocess calibration management.

Runs dev_runner_calibrate.py as a subprocess with lockfile enforcement.
PRIVACY: No frames saved, only subprocess management.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional


class CalibrationRunner:
    """
    Manages calibration subprocess.
    
    Single-instance enforcement via lockfile.
    Progress tracked via calibration_status.json.
    """
    
    def __init__(
        self,
        lockfile: str = "storage/calibration.lock",
        status_file: str = "storage/calibration_status.json"
    ):
        """
        Initialize calibration runner.
        
        Args:
            lockfile: Path to calibration lock file
            status_file: Path to calibration status JSON
        """
        self.lockfile = Path(lockfile)
        self.status_file = Path(status_file)
        
        # Ensure storage directory exists
        self.lockfile.parent.mkdir(parents=True, exist_ok=True)
        
        self._process: Optional[subprocess.Popen] = None
        self._pid: Optional[int] = None
    
    def is_calibrating(self) -> bool:
        """
        Check if calibration is running.
        
        Returns:
            True if calibrating, False otherwise
        """
        # First, prefer checking the tracked subprocess handle if available.
        # This avoids treating a completed-but-unreaped child as still running.
        if self._process is not None:
            try:
                retcode = self._process.poll()
            except Exception:
                retcode = None
            
            if retcode is not None:
                # Subprocess has exited; clean up lockfile and internal state.
                pid = self._pid
                print(f"[CALIBRATION] Completed (PID: {pid}, exit={retcode})")
                self._cleanup()
                return False
            
            # Subprocess still running
            return True
        
        # Fallback: check lockfile and PID directly (e.g. across processes)
        if not self.lockfile.exists():
            return False
        
        try:
            with open(self.lockfile, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                # Process doesn't exist, clean up stale lockfile
                self._cleanup()
                return False
        except (ValueError, FileNotFoundError):
            # Invalid lockfile
            self._cleanup()
            return False
    
    def get_pid(self) -> Optional[int]:
        """
        Get the PID of the calibration process.
        
        Returns:
            PID if calibrating, None otherwise
        """
        if not self.is_calibrating():
            return None
        
        try:
            with open(self.lockfile, 'r') as f:
                return int(f.read().strip())
        except (ValueError, FileNotFoundError):
            return None
    
    def start_calibration(
        self,
        duration_sec: float = 25.0,
        camera_index: int = 0,
        target_fps: float = 8.0
    ) -> bool:
        """
        Start calibration subprocess.
        
        Single-instance enforcement: if already calibrating, returns False.
        
        Args:
            duration_sec: Calibration duration in seconds
            camera_index: Camera device index
            target_fps: Target frames per second
            
        Returns:
            True if started successfully, False otherwise
        """
        # Check if already calibrating
        if self.is_calibrating():
            print(f"[CALIBRATION] Already running (PID: {self.get_pid()})")
            return False
        
        # Build command line
        repo_root = Path(__file__).parent.parent.resolve()
        python_exe = sys.executable
        calibrate_script = repo_root / "dev_runner_calibrate.py"
        
        if not calibrate_script.exists():
            print(f"[CALIBRATION] Error: dev_runner_calibrate.py not found at {calibrate_script}")
            return False
        
        cmd = [
            python_exe,
            str(calibrate_script),
            "--duration", str(int(duration_sec)),
            "--camera", str(camera_index),
            "--fps", str(target_fps),
            "--force"
        ]
        
        try:
            # Clear old status file
            if self.status_file.exists():
                self.status_file.unlink()
            
            # Start subprocess
            self._process = subprocess.Popen(
                cmd,
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
            
            self._pid = self._process.pid
            
            # Write lockfile
            with open(self.lockfile, 'w') as f:
                f.write(str(self._pid))
            
            print(f"[CALIBRATION] Started (PID: {self._pid})")
            return True
            
        except Exception as e:
            print(f"[CALIBRATION] Error starting: {e}")
            self._cleanup()
            return False
    
    def stop_calibration(self, timeout: float = 2.0) -> bool:
        """
        Stop calibration subprocess.
        
        Graceful shutdown: SIGTERM with timeout, fallback to SIGKILL.
        
        Args:
            timeout: Seconds to wait for graceful shutdown
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_calibrating():
            print("[CALIBRATION] Not running")
            return True
        
        pid = self.get_pid()
        if pid is None:
            return True
        
        try:
            print(f"[CALIBRATION] Stopping (PID: {pid})...")
            
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to exit
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except OSError:
                    # Process exited
                    print(f"[CALIBRATION] Stopped gracefully")
                    self._cleanup()
                    return True
            
            # Timeout: force kill
            print(f"[CALIBRATION] Timeout, force killing...")
            try:
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
            except OSError:
                pass
            
            self._cleanup()
            print(f"[CALIBRATION] Stopped (force)")
            return True
            
        except Exception as e:
            print(f"[CALIBRATION] Error stopping: {e}")
            self._cleanup()
            return False
    
    def _cleanup(self):
        """Clean up lockfile."""
        try:
            if self.lockfile.exists():
                self.lockfile.unlink()
        except Exception:
            pass
        
        self._process = None
        self._pid = None


# Global instance
_calibration_runner = None

def get_calibration_runner() -> CalibrationRunner:
    """Get the global CalibrationRunner instance."""
    global _calibration_runner
    if _calibration_runner is None:
        _calibration_runner = CalibrationRunner()
    return _calibration_runner
