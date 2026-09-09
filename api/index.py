import sys
from pathlib import Path

# Ensure backend package is in system path for Vercel serverless functions
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

# Vercel Serverless Function entry point
handler = app
