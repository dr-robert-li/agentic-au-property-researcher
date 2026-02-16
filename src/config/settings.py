"""
Application settings and configuration.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def validate_api_key_format(var_name: str, value: str) -> bool:
    """
    Validate API key format without revealing the key.

    Args:
        var_name: Name of the environment variable
        value: API key value to validate

    Returns:
        True if format is valid, False otherwise
    """
    if var_name == "PERPLEXITY_API_KEY":
        # Format: pplx-<40+ hex chars>
        return value.startswith("pplx-") and len(value) >= 45
    elif var_name == "ANTHROPIC_API_KEY":
        # Format: sk-ant-<base62 string>
        return value.startswith("sk-ant-") and len(value) >= 50
    # Unknown key type, skip validation
    return True


def validate_environment():
    """
    Validate required environment variables on startup.

    Checks that at least one API key is present and properly formatted.
    Exits with clear error message if validation fails.
    """
    perplexity_key = os.getenv("PERPLEXITY_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    # At least one key must be present
    if not perplexity_key and not anthropic_key:
        print("\n" + "=" * 80)
        print("CONFIGURATION ERROR")
        print("=" * 80)
        print("\nMissing required environment variables:")
        print("  At least one API key must be set:")
        print("    - PERPLEXITY_API_KEY")
        print("    - ANTHROPIC_API_KEY")
        print("\nACTION REQUIRED:")
        print("  1. Create .env file in project root (see .env.example)")
        print("  2. Add valid API keys:")
        print("     - Perplexity: https://www.perplexity.ai/settings/api")
        print("     - Anthropic: https://console.anthropic.com/settings/keys")
        print("  3. Restart the application")
        print("\n" + "=" * 80 + "\n")
        sys.exit(1)

    # Validate format of present keys
    invalid_keys = []

    if perplexity_key and not validate_api_key_format("PERPLEXITY_API_KEY", perplexity_key):
        invalid_keys.append("PERPLEXITY_API_KEY")

    if anthropic_key and not validate_api_key_format("ANTHROPIC_API_KEY", anthropic_key):
        invalid_keys.append("ANTHROPIC_API_KEY")

    if invalid_keys:
        print("\n" + "=" * 80)
        print("CONFIGURATION ERROR")
        print("=" * 80)
        print("\nInvalid API key format:")
        for key_name in invalid_keys:
            if key_name == "PERPLEXITY_API_KEY":
                print(f"  {key_name}: must start with 'pplx-' and be at least 45 characters")
            elif key_name == "ANTHROPIC_API_KEY":
                print(f"  {key_name}: must start with 'sk-ant-' and be at least 50 characters")
        print("\nACTION REQUIRED:")
        print("  1. Verify API keys in .env file")
        print("  2. Check for copy/paste errors or truncation")
        print("  3. Generate new keys at provider websites if needed")
        print("\n" + "=" * 80 + "\n")
        sys.exit(1)


# Validate environment BEFORE setting any config variables
validate_environment()

# Install log sanitization globally
from security.sanitization import install_log_sanitization
install_log_sanitization()

# API Configuration (after validation)
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Determine available providers
AVAILABLE_PROVIDERS = []
if PERPLEXITY_API_KEY:
    AVAILABLE_PROVIDERS.append("perplexity")
if ANTHROPIC_API_KEY:
    AVAILABLE_PROVIDERS.append("anthropic")

# Default provider: prefer perplexity if available, otherwise anthropic
DEFAULT_PROVIDER = AVAILABLE_PROVIDERS[0]

# Model Configuration
DEFAULT_PERPLEXITY_MODEL = "anthropic/claude-sonnet-4-5"
DEFAULT_PERPLEXITY_PRESET = "deep-research"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"

# Application Configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "runs")
DEFAULT_PORT = int(os.getenv("DEFAULT_PORT", "8080"))

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# Research Configuration
DEFAULT_NUM_SUBURBS = 10
MAX_RECOMMENDED_SUBURBS = 25
DEFAULT_REGIONS = ["All Australia"]

# Timeout and retry settings
API_TIMEOUT = 300  # 5 minutes for deep research calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Parallel execution settings
# Adaptive worker scaling with fallback to hardcoded defaults if dependencies fail
try:
    from src.config.worker_scaling import calculate_worker_counts

    # Parse environment overrides (None if not set, int if set)
    _discovery_override = int(os.getenv("DISCOVERY_MAX_WORKERS")) if os.getenv("DISCOVERY_MAX_WORKERS") else None
    _research_override = int(os.getenv("RESEARCH_MAX_WORKERS")) if os.getenv("RESEARCH_MAX_WORKERS") else None

    DISCOVERY_MAX_WORKERS, RESEARCH_MAX_WORKERS = calculate_worker_counts(
        override_discovery=_discovery_override,
        override_research=_research_override,
    )
except (ImportError, Exception) as e:
    # Fallback to safe defaults if worker_scaling or dependencies fail
    import logging
    logging.warning(f"Failed to load adaptive worker scaling, using defaults: {e}")
    DISCOVERY_MAX_WORKERS = int(os.getenv("DISCOVERY_MAX_WORKERS", "4"))
    RESEARCH_MAX_WORKERS = int(os.getenv("RESEARCH_MAX_WORKERS", "3"))

DISCOVERY_TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "120"))   # 2 min per region
RESEARCH_TIMEOUT = int(os.getenv("RESEARCH_TIMEOUT", "240"))     # 4 min per suburb

# Pipeline multipliers: how many extra candidates to discover/research beyond what user requested
# Reduced from 5/3 to 2.0/1.5 per PERF-04: eliminates 60-80% of wasteful API calls
DISCOVERY_MULTIPLIER = float(os.getenv("DISCOVERY_MULTIPLIER", "2.0"))  # Down from 5
RESEARCH_MULTIPLIER = float(os.getenv("RESEARCH_MULTIPLIER", "1.5"))    # Down from 3

# Cache Configuration
CACHE_DIR = BASE_DIR / "cache"
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_DISCOVERY_TTL = int(os.getenv("CACHE_DISCOVERY_TTL", "86400"))  # 24 hours
CACHE_RESEARCH_TTL = int(os.getenv("CACHE_RESEARCH_TTL", "604800"))  # 7 days
CACHE_MAX_SIZE_MB = int(os.getenv("CACHE_MAX_SIZE_MB", "500"))  # 500 MB default
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)

# Ranking quality weights
RANKING_QUALITY_WEIGHTS = {
    "high": float(os.getenv("QUALITY_WEIGHT_HIGH", "1.0")),
    "medium": float(os.getenv("QUALITY_WEIGHT_MEDIUM", "0.95")),
    "low": float(os.getenv("QUALITY_WEIGHT_LOW", "0.85")),
    "fallback": float(os.getenv("QUALITY_WEIGHT_FALLBACK", "0.70")),
}
DEFAULT_RANKING_METHOD = os.getenv("DEFAULT_RANKING_METHOD", "quality_adjusted")
