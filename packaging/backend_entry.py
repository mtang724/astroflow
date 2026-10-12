"""Entry point of the frozen backend (PyInstaller cannot start a package's __main__ with relative imports)."""
from astroflow.api.__main__ import main

if __name__ == "__main__":
    main()
