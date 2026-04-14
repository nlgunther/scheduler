"""
shared/locking.py
"""
import time
import os
from pathlib import Path
from contextlib import contextmanager

class LockTimeout(Exception): pass

def check_lock(filepath: Path) -> bool:
    """Check if a lock exists."""
    lock_path = filepath.with_suffix(filepath.suffix + ".lock")
    return lock_path.exists()

@contextmanager
def file_lock(
    filepath: Path,
    timeout: int = 5,
    poll_interval: float = 0.1,
    stale_threshold: int = 300
) -> None:
    """Context manager for exclusive file access.
    
    KNOWN LIMITATION: Stale lock cleanup has a race condition in multi-process
    scenarios. If concurrent processes both see an old lock, they may both delete
    it and create new locks simultaneously. This is low-risk for single-user tools
    but should be fixed before production multi-user deployment.
    
    Scheduled fix: Phase 5 (PID-based validation)
    Workaround: Manually delete .lock files if needed
    
    Args:
        filepath: File to lock
        timeout: Seconds to wait for lock (default: 5)
        poll_interval: Seconds between retry attempts (default: 0.1)
        stale_threshold: Age in seconds to consider lock stale (default: 300)
    
    Raises:
        LockTimeout: If lock cannot be acquired within timeout
    
    Example:
        with file_lock(Path("data.xml")):
            modify_data()
    """
    lock_path = filepath.with_suffix(filepath.suffix + ".lock")
    start = time.time()
    
    # Check for stale lock first
    if stale_threshold and lock_path.exists():
        try:
            mtime = lock_path.stat().st_mtime
            if time.time() - mtime > stale_threshold:
                try: os.remove(lock_path)
                except OSError: pass
        except OSError:
            pass 

    acquired = False
    try:
        while True:
            try:
                with open(lock_path, 'x'): pass
                acquired = True
                yield
                break
            except FileExistsError:
                if time.time() - start > timeout:
                    raise LockTimeout(f"Locked: {filepath}")
                time.sleep(0.1)
    finally:
        if acquired and lock_path.exists():
            try: os.remove(lock_path)
            except OSError: pass
