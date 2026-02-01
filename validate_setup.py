#!/usr/bin/env python3
"""
Setup Validation Script

Validates that the environment is correctly configured and all dependencies are available.
Run this before attempting to use the application.
"""
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    """Print formatted header."""
    print(f"\n{BLUE}{'='*80}")
    print(f"{text}")
    print(f"{'='*80}{RESET}\n")


def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def check_python_version():
    """Check if Python version meets requirements."""
    print("Checking Python version...")
    version = sys.version_info
    required = (3, 10)

    if version >= required:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} - Requires 3.10+")
        return False


def check_dependencies():
    """Check if all required packages are installed."""
    print("\nChecking dependencies...")

    dependencies = [
        "pydantic",
        "jinja2",
        "matplotlib",
        "seaborn",
        "dotenv",
        "perplexityai"
    ]

    all_installed = True
    for package in dependencies:
        try:
            if package == "dotenv":
                __import__("dotenv")
            else:
                __import__(package)
            print_success(f"{package}")
        except ImportError:
            print_error(f"{package} - NOT INSTALLED")
            all_installed = False

    return all_installed


def check_project_structure():
    """Check if project structure is correct."""
    print("\nChecking project structure...")

    base_dir = Path(__file__).parent
    required_paths = [
        "src",
        "src/config",
        "src/models",
        "src/research",
        "src/reporting",
        "src/ui/web/templates",
        "src/ui/web/static/css",
        "tests",
        ".env.example"
    ]

    all_exist = True
    for path_str in required_paths:
        path = base_dir / path_str
        if path.exists():
            print_success(f"{path_str}")
        else:
            print_error(f"{path_str} - NOT FOUND")
            all_exist = False

    return all_exist


def check_env_file():
    """Check if .env file exists and has required keys."""
    print("\nChecking environment configuration...")

    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    if not env_example.exists():
        print_error(".env.example not found")
        return False
    else:
        print_success(".env.example exists")

    if not env_file.exists():
        print_warning(".env file not found - copy from .env.example")
        return False
    else:
        print_success(".env file exists")

    # Check if API key is set
    try:
        with open(env_file, 'r') as f:
            content = f.read()
            if "PERPLEXITY_API_KEY=pplx-" in content:
                print_success("PERPLEXITY_API_KEY appears to be set")
                return True
            elif "PERPLEXITY_API_KEY=" in content:
                print_warning("PERPLEXITY_API_KEY exists but may not be set correctly")
                return False
            else:
                print_warning("PERPLEXITY_API_KEY not found in .env")
                return False
    except Exception as e:
        print_error(f"Error reading .env: {e}")
        return False


def check_imports():
    """Check if main modules can be imported."""
    print("\nChecking module imports...")

    sys.path.insert(0, str(Path(__file__).parent / "src"))

    modules = [
        ("config.settings", "Settings"),
        ("models.inputs", "UserInput"),
        ("models.suburb_metrics", "SuburbMetrics"),
        ("research.perplexity_client", "PerplexityClient"),
        ("app", "run_research_pipeline")
    ]

    all_imported = True
    for module_name, item_name in modules:
        try:
            module = __import__(module_name, fromlist=[item_name])
            getattr(module, item_name)
            print_success(f"{module_name}.{item_name}")
        except Exception as e:
            print_error(f"{module_name}.{item_name} - {e}")
            all_imported = False

    return all_imported


def check_output_directory():
    """Check if output directory can be created."""
    print("\nChecking output directory...")

    output_dir = Path(__file__).parent / "runs"

    try:
        output_dir.mkdir(exist_ok=True)
        print_success(f"Output directory: {output_dir}")

        # Check if writable
        test_file = output_dir / ".test"
        test_file.write_text("test")
        test_file.unlink()
        print_success("Output directory is writable")
        return True
    except Exception as e:
        print_error(f"Cannot create/write to output directory: {e}")
        return False


def main():
    """Run all validation checks."""
    print_header("🔍 SETUP VALIDATION")
    print("Validating Australian Property Research setup...\n")

    checks = {
        "Python Version": check_python_version(),
        "Dependencies": check_dependencies(),
        "Project Structure": check_project_structure(),
        "Environment File": check_env_file(),
        "Module Imports": check_imports(),
        "Output Directory": check_output_directory()
    }

    # Summary
    print_header("📊 VALIDATION SUMMARY")

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    for check_name, result in checks.items():
        status = f"{GREEN}✓ PASS{RESET}" if result else f"{RED}✗ FAIL{RESET}"
        print(f"{status}: {check_name}")

    print(f"\n{passed}/{total} checks passed")

    if passed == total:
        print(f"\n{GREEN}✅ Setup validation successful!{RESET}")

        # Add reminder about API credits
        print(f"\n{YELLOW}⚠️  IMPORTANT REMINDERS:{RESET}")
        print(f"  • Check your API credit balance before running large analyses:")
        print(f"    {BLUE}https://www.perplexity.ai/account/api/billing{RESET}")
        print(f"  • Research consumes significant API credits (deep-research preset)")
        print(f"  • Start with small runs (2-3 suburbs) to test")
        print(f"  • Each suburb takes 2-5 minutes and uses substantial API tokens")

        print("\nYou can now run the application:")
        print(f"{BLUE}  python demo.py{RESET}                    # Quick demo with 2 suburbs")
        print(f"{BLUE}  python run_web.py{RESET}                 # Web interface (recommended)")
        print(f"{BLUE}  python run_interactive.py{RESET}         # Interactive CLI")
        print(f"{BLUE}  python -m src.app --max-price 700000 --dwelling-type house{RESET}")
        return True
    else:
        print(f"\n{RED}❌ Setup validation failed{RESET}")
        print("\nPlease fix the issues above before running the application.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Copy .env.example to .env: cp .env.example .env")
        print("  - Add your Perplexity API key to .env")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
