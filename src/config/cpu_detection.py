"""Container-aware CPU limit detection.

Detects CPU limits from cgroup v2 (/sys/fs/cgroup/cpu.max) and
cgroup v1 (/sys/fs/cgroup/cpu/cpu.cfs_quota_us) before falling
back to os.cpu_count().
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def detect_cpu_limit() -> int:
    """Detect available CPUs, respecting container cgroup limits. Returns min 1."""
    # Try cgroup v2 first (newer Docker)
    result = _read_cgroup_v2_cpu()
    if result is not None:
        logger.info(f"CPU limit detected via cgroup v2: {result}")
        return result

    # Try cgroup v1
    result = _read_cgroup_v1_cpu()
    if result is not None:
        logger.info(f"CPU limit detected via cgroup v1: {result}")
        return result

    # Fallback to os.cpu_count()
    count = os.cpu_count() or 1
    logger.info(f"CPU count from os.cpu_count(): {count}")
    return count

def _read_cgroup_v2_cpu() -> Optional[int]:
    """Read from /sys/fs/cgroup/cpu.max. Format: '$MAX $PERIOD' or 'max $PERIOD'."""
    try:
        with open('/sys/fs/cgroup/cpu.max', 'r') as f:
            parts = f.read().strip().split()
            if parts[0] == 'max':
                return None  # Unlimited
            return max(1, int(int(parts[0]) / int(parts[1])))
    except (FileNotFoundError, ValueError, IndexError):
        return None

def _read_cgroup_v1_cpu() -> Optional[int]:
    """Read from cgroup v1 quota/period files."""
    try:
        with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as f:
            quota = int(f.read().strip())
        if quota == -1:
            return None  # Unlimited
        with open('/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as f:
            period = int(f.read().strip())
        return max(1, int(quota / period))
    except (FileNotFoundError, ValueError):
        return None
