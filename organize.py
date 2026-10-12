"""Kept for the old command line: `python organize.py [--apply] [--refresh]` -> astroflow.organize."""
import sys

from astroflow.organize import main

if __name__ == "__main__":
    sys.exit(main())
