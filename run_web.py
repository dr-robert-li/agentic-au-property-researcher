#!/usr/bin/env python3
"""
Web Server Launcher for Australian Property Research

Starts the FastAPI web server and opens the browser.
"""
import sys
import webbrowser
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Launch the web server."""
    print("=" * 80)
    print("🏘️  AUSTRALIAN PROPERTY RESEARCH - WEB INTERFACE")
    print("=" * 80)
    print("\nStarting web server...")
    print("Server will be available at: http://127.0.0.1:8000")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 80 + "\n")

    # Import and run server
    try:
        import uvicorn
        from ui.web.server import app

        # Open browser after a short delay
        def open_browser():
            time.sleep(2)
            webbrowser.open("http://127.0.0.1:8000")

        import threading
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        # Run server
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    except KeyboardInterrupt:
        print("\n\n⏹️  Server stopped")
    except ImportError as e:
        print(f"\n❌ Error: Missing dependency - {e}")
        print("\nPlease install required packages:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
