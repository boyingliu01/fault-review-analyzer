#!/usr/bin/env python
"""CLI wrapper that loads .env before execution"""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Now run the actual CLI
from src.cli.main import app

if __name__ == "__main__":
    app()
