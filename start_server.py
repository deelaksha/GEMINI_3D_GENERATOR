#!/usr/bin/env python3
"""
==============================================================================
PuzzleCore 3D Physical Construction Workbench — Server Launcher
==============================================================================
Starts the Flask web server, binds to an available port, and automatically
opens the interactive 3D Workbench in your default web browser.

Usage:
    python start_server.py
    python start_server.py --port 8080 --no-browser
==============================================================================
"""

import sys
import socket
import argparse
import threading
import time
import webbrowser
from pathlib import Path

# Verify Python version
if sys.version_info < (3, 8):
    print("[ERROR] Python 3.8 or higher is required.")
    sys.exit(1)

# Verify Flask installation
try:
    from app import app
except ImportError as err:
    print("\n" + "=" * 60)
    print(" [ERROR] Required dependencies are missing:")
    print(f"         {err}")
    print(" Please install dependencies by running:")
    print("         pip install -r requirements.txt")
    print("=" * 60 + "\n")
    sys.exit(1)


def is_port_available(host: str, port: int) -> bool:
    """Check whether a network port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return True
        except (OSError, socket.error):
            return False


def find_available_port(host: str, preferred_port: int, max_attempts: int = 20) -> int:
    """Find an open port starting from preferred_port."""
    for port in range(preferred_port, preferred_port + max_attempts):
        if is_port_available(host, port):
            return port
    return preferred_port


def open_browser_delayed(url: str, delay_seconds: float = 0.8):
    """Open default browser after server initializes."""
    def _open():
        time.sleep(delay_seconds)
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Non-fatal if browser opening fails in headless/restricted env
    t = threading.Thread(target=_open, daemon=True)
    t.start()


# Configure UTF-8 encoding for Windows console compatibility
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

def print_banner(host: str, port: int):
    """Print clean terminal dashboard."""
    base_url = f"http://{host}:{port}"
    localhost_url = f"http://localhost:{port}"

    print("\n" + "=" * 68)
    print("   [+] PUZZLECORE 3D WORKBENCH & PHYSICAL FABRICATION PLATFORM")
    print("   [*] Flask Backend Server Active")
    print("=" * 68)
    print(f"   * Board Studio:         {localhost_url}/")
    print(f"   * Board API (AI agents): {localhost_url}/api/v1/   (keys: instance/api_keys.json)")
    print(f"   * Legacy 3D Workbench:  {localhost_url}/assembly")
    print(f"   * Part File Inspector:  {localhost_url}/inspector")
    print(f"   * 2D Laser Cut Sheets:  {localhost_url}/manufacturing")
    print(f"   * Fit Audit & Graph:    {localhost_url}/validation")
    print(f"   * Construction Guide:   {localhost_url}/guide")
    print(f"   * Backend REST API:     {localhost_url}/api/status")
    print("-" * 68)
    print(f"   Local IP URL:           {base_url}/")
    print("   Press CTRL + C at any time to gracefully shut down.")
    print("=" * 68 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="PuzzleCore 3D Physical Assembly Workbench Server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run server on (default: 5000, auto-finds next if busy)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not launch the default web browser automatically",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask in interactive debug mode",
    )

    args = parser.parse_args()

    # Find free port if preferred is busy
    port = args.port
    if not is_port_available(args.host, port):
        print(f"[!] Port {port} is currently in use.")
        port = find_available_port(args.host, port + 1)
        print(f"[✓] Selected next available port: {port}")

    url = f"http://localhost:{port}"

    # Auto open browser unless disabled
    if not args.no_browser:
        open_browser_delayed(url)

    print_banner(args.host, port)

    try:
        # Run Flask server
        app.run(
            host=args.host,
            port=port,
            debug=args.debug,
            use_reloader=False  # Avoid double startup when launched via start script
        )
    except KeyboardInterrupt:
        print("\n[✓] PuzzleCore server gracefully stopped. Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
