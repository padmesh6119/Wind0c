"""
Wind0c - System Optimizer
Created by P. S. Padmesh
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_deps():
    missing = []
    for pkg in ["psutil"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"\n[Wind0c] Missing: {', '.join(missing)}")
        print(f"Fix: pip install {' '.join(missing)}\n")
        sys.exit(1)


def main():
    check_deps()
    from ui.main_window import main as run_ui
    run_ui()


if __name__ == "__main__":
    main()