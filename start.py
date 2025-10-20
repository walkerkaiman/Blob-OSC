#!/usr/bin/env python3
"""Convenience launcher for Blob OSC.

This script will:
- Create a local virtual environment in .venv (if missing)
- Ensure dependencies from requirements.txt are installed
- Launch the application via run_web.py, forwarding any CLI args
"""

import os
import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"


def is_windows() -> bool:
    return os.name == "nt"


def venv_python_path() -> Path:
    if is_windows():
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(cmd: list[str]) -> int:
    """Run a command, streaming output. Returns exit code."""
    try:
        completed = subprocess.run(cmd, check=False)
        return completed.returncode
    except KeyboardInterrupt:
        return 130


def ensure_venv() -> None:
    if venv_python_path().exists():
        return
    print("Creating virtual environment in .venv ...")
    rc = run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if rc != 0:
        print("Failed to create virtual environment.")
        sys.exit(rc)


def ensure_dependencies() -> None:
    py = str(venv_python_path())
    # Upgrade packaging tools first
    print("Upgrading pip/setuptools/wheel ...")
    rc = run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    if rc != 0:
        print("Failed to upgrade pip/setuptools/wheel.")
        sys.exit(rc)

    # Install project requirements
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        print("requirements.txt not found; nothing to install.")
        return
    print("Installing project requirements ...")
    rc = run([
        py,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--upgrade-strategy",
        "only-if-needed",
        "-r",
        str(req_file),
    ])
    if rc != 0:
        print("Dependency installation failed.")
        sys.exit(rc)


def launch_app(argv: list[str]) -> int:
    py = str(venv_python_path())
    run_web = PROJECT_ROOT / "run_web.py"
    if not run_web.exists():
        print("run_web.py not found.")
        return 1
    cmd = [py, str(run_web), *argv]
    print("Starting Blob OSC ...")
    return run(cmd)


def main() -> None:
    ensure_venv()
    ensure_dependencies()
    exit_code = launch_app(sys.argv[1:])
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


