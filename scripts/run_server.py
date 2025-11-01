"""Run the Flask app via wsgiref simple server on a specified port to avoid Flask reloader issues."""
import os
from wsgiref.simple_server import make_server

# Ensure project root is in sys.path
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5002'))
    print(f'Starting WSGI server on http://127.0.0.1:{port}')
    with make_server('127.0.0.1', port, app) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('Server stopped')
