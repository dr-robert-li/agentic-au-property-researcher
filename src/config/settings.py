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
if not PERPLEXITY_API_KEY:
    raise ValueError("PERPLEXITY_API_KEY must be set in .env file")

# Model Configuration
DEFAULT_MODEL = "anthropic/claude-sonnet-4-5"
DEFAULT_PRESET = "deep-research"

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
