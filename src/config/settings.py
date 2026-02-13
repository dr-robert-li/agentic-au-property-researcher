"""
Application settings and configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# At least one API key must be set
if not PERPLEXITY_API_KEY and not ANTHROPIC_API_KEY:
    raise ValueError(
        "At least one API key must be set in .env file: "
        "PERPLEXITY_API_KEY or ANTHROPIC_API_KEY"
    )

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
