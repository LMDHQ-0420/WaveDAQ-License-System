import sys
from pathlib import Path

# Support both documented module execution (``python -m src.main``) and
# launching this file directly from an IDE or an absolute path.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> int:
    from src.gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
