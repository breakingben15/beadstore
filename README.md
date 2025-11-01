# Beaded Baubles (Flask)

This project serves a static front-end from `templates/index.html` using Flask.

Quick start (macOS, zsh):

```bash
# Activate your virtualenv (adjust path if different)
source "/Users/joshuahughes/bead store/.venv/bin/activate"

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py

# Or run with gunicorn
gunicorn "app:app" --bind 0.0.0.0:8000
```

Place any static assets in the `static/` folder. Rename `.env.example` to `.env` to customize environment variables.

Deploying to Render (free web service):

1. Create a new Web Service on Render and connect your GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn "app:app" --bind 0.0.0.0:$PORT`
4. Environment variables (set on Render):
	- `ADMIN_PASSWORD` (required for admin create/delete via X-ADMIN-PASS header)
	- `SECRET_KEY` (recommended)
	- `DATABASE_URL` (optional; if not set the app uses a local SQLite `data.db`)

Notes:
- The frontend calls `/api/products` to list products. Use the admin endpoints with the `X-ADMIN-PASS` header to create or delete products.
- The included `.gitignore` excludes `.env`, `.venv`, and `*.db` so local files won't be pushed.
