"""Simple script to initialize the SQLite database."""
from pathlib import Path
import sys
import os

# Ensure project root is on sys.path so we can import app
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, app

if __name__ == '__main__':
    print('Creating database tables...')
    with app.app_context():
        db.create_all()
    print('Done')
