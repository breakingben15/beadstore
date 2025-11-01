"""Small API test: login, create product, list, delete."""
import requests
from pathlib import Path

import os

BASE = os.environ.get('BASE', 'http://127.0.0.1:5001')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')


def main():
    s = requests.Session()
    print('Logging in...')
    r = s.post(f'{BASE}/api/login', json={'password': ADMIN_PASS})
    print('login', r.status_code, r.text)
    if r.status_code != 200:
        return

    print('Creating product...')
    payload = {'name': 'Test Bead', 'price': 9.99, 'imageUrl': 'https://placehold.co/600x400'}
    r = s.post(f'{BASE}/api/products', json=payload)
    print('create', r.status_code, r.text)
    if r.status_code != 201:
        return
    created = r.json()

    print('Listing products...')
    r = s.get(f'{BASE}/api/products')
    print('list', r.status_code, r.text)

    print('Deleting product...')
    r = s.delete(f'{BASE}/api/products/{created["id"]}')
    print('delete', r.status_code, r.text)

    print('Done')


if __name__ == '__main__':
    main()
