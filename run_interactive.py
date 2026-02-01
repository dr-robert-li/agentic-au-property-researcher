#!/usr/bin/env python3
"""
Interactive CLI Launcher for Australian Property Research

Provides a user-friendly terminal interface with autocomplete and validation.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    try:
        from ui.cli.interactive import main
        main()
    except ImportError as e:
        print(f"\n❌ Error: Missing dependency - {e}")
        print("\nThe interactive CLI requires additional packages:")
        print("  pip install prompt-toolkit rich")
        print("\nAlternatively, use the basic CLI:")
        print("  python -m src.app --help")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
