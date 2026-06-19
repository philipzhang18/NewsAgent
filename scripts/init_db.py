#!/usr/bin/env python3
"""Initialize local SQLite database for News Agent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.storage_service import storage_service


def main():
    if storage_service.connect():
        print("SQLite database initialized at", storage_service._db.db_path)
        return 0
    print("Failed to initialize SQLite database")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
