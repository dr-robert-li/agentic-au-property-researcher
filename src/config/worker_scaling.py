"""Adaptive worker count calculation based on CPU and memory."""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Caps to prevent runaway thread creation
MAX_DISCOVERY_WORKERS = 8
MAX_RESEARCH_WORKERS = 6

def calculate_worker_counts(
    override_discovery: Optional[int] = None,
    override_research: Optional[int] = None
) -> Tuple[int, int]:
    """Calculate optimal worker counts based on CPU count and available memory.

    For I/O-bound work (API calls), uses 3x CPU for discovery (lighter),
    2x CPU for research (heavier). Memory-aware: reserves 2GB for system,
    assumes 500MB per worker.

    Returns: (discovery_workers, research_workers)
    """
    from src.config.cpu_detection import detect_cpu_limit

    cpu_count = detect_cpu_limit()

    # Base: I/O-bound multipliers with caps
    base_discovery = min(cpu_count * 3, MAX_DISCOVERY_WORKERS)
    base_research = min(cpu_count * 2, MAX_RESEARCH_WORKERS)

    # Memory-aware adjustment using psutil
    try:
        import psutil
        available_gb = psutil.virtual_memory().available / (1024 ** 3)
        max_by_memory = max(1, int((available_gb - 2) / 0.5))
        base_discovery = min(base_discovery, max_by_memory)
        base_research = min(base_research, max_by_memory)
        logger.info(f"Worker scaling: CPU={cpu_count}, Memory={available_gb:.1f}GB available")
    except ImportError:
        logger.warning("psutil not available, skipping memory-based scaling")

    # Apply overrides
    discovery = override_discovery if override_discovery is not None else base_discovery
    research = override_research if override_research is not None else base_research

    # Ensure minimum 1
    discovery = max(1, discovery)
    research = max(1, research)

    logger.info(f"Worker counts: discovery={discovery}, research={research}")
    return discovery, research
