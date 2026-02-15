"""
Input validation functions for security boundaries.

Validates user inputs (run IDs, cache paths, regions) against whitelists
and safe patterns to prevent path traversal, injection, and invalid data.
"""
import re
from pathlib import Path


def validate_run_id(run_id: str) -> str:
    """
    Validate run ID against safe character pattern.

    Run IDs must contain only letters, numbers, hyphens, and underscores.
    No path traversal characters, no special characters.

    Args:
        run_id: Run ID to validate

    Returns:
        Validated run ID (unchanged)

    Raises:
        ValueError: If run ID contains invalid characters or is wrong length
    """
    # Check length
    if not run_id or len(run_id) < 1 or len(run_id) > 100:
        raise ValueError(
            f"Run ID must be 1-100 characters, got {len(run_id)}"
        )

    # Check pattern: only alphanumeric, hyphen, underscore
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError(
            f"Run ID '{run_id}' contains invalid characters. "
            "Only letters, numbers, hyphens (-), and underscores (_) are allowed."
        )

    return run_id


def validate_cache_path(user_path: str, base_dir: Path) -> Path:
    """
    Validate that user-provided path is within allowed base directory.

    Uses pathlib.Path.resolve() to canonicalize paths (follows symlinks,
    collapses ../ sequences) and then verifies containment using is_relative_to().

    Args:
        user_path: User-provided path (relative or absolute)
        base_dir: Base directory that must contain the path

    Returns:
        Resolved absolute Path object within base_dir

    Raises:
        ValueError: If path attempts to escape base_dir
    """
    # Resolve both to absolute paths (collapses ../ and follows symlinks)
    base_absolute = base_dir.resolve()
    requested_absolute = Path(user_path).resolve()

    # Verify requested path is within base directory
    if not requested_absolute.is_relative_to(base_absolute):
        raise ValueError(
            f"Path traversal detected: '{user_path}' is outside allowed directory '{base_dir}'"
        )

    return requested_absolute


def validate_regions(regions: list[str]) -> list[str]:
    """
    Validate regions against predefined whitelist.

    Each region must exist in the REGIONS dict from config.regions_data.
    Uses case-insensitive matching with title-case normalization.

    Args:
        regions: List of region names to validate

    Returns:
        Normalized list of region names (title-cased)

    Raises:
        ValueError: If any region is not in the whitelist
    """
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = str(Path(__file__).parent.parent)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from config.regions_data import REGIONS

    validated = []
    invalid = []

    for region in regions:
        # Normalize: title case for matching
        normalized = region.strip().title()

        # Check if normalized version exists in REGIONS keys
        # Need to compare case-insensitively since REGIONS keys may vary
        found = False
        for valid_region in REGIONS.keys():
            if valid_region.lower() == normalized.lower():
                validated.append(valid_region)  # Use the canonical form from REGIONS
                found = True
                break

        if not found:
            invalid.append(region)

    if invalid:
        valid_options = ", ".join(sorted(REGIONS.keys()))
        raise ValueError(
            f"Invalid region(s): {', '.join(invalid)}. "
            f"Valid regions are: {valid_options}"
        )

    return validated
