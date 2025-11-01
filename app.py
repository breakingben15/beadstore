from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, abort, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import logging

# Load environment variables from .env if present
env_path = Path(__file__).parent / '.env'
if env_path.exists():
	load_dotenv(env_path)

BASE_DIR = Path(__file__).parent

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "data.db"}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)

# configure simple logging to stderr
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple Product model
class Product(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(256), nullable=False)
	price = db.Column(db.Float, nullable=False)
	image_url = db.Column(db.String(1024), nullable=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)

	def to_dict(self):
		return {
			'id': self.id,
			'name': self.name,
			'price': self.price,
			'imageUrl': self.image_url,
			'createdAt': self.created_at.isoformat()
		}


def is_admin_logged_in():
	return session.get('is_admin') is True


@app.route('/api/login', methods=['POST'])
def api_login():
	data = request.get_json() or {}
	password = data.get('password')
	env_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
	if password and password == env_pass:
		session['is_admin'] = True
		return jsonify({'status': 'ok'})
	return jsonify({'error': 'invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
	session.pop('is_admin', None)
	return jsonify({'status': 'ok'})


@app.route('/api/me')
def api_me():
	return jsonify({'is_admin': is_admin_logged_in()})


@app.route('/')
def index():
	return render_template('index.html')


@app.route('/api/products', methods=['GET'])
def list_products():
	products = Product.query.order_by(Product.created_at.desc()).all()
	return jsonify([p.to_dict() for p in products])


@app.route('/api/products', methods=['POST'])
def create_product():
	if not is_admin_logged_in():
		return jsonify({'error': 'unauthorized'}), 401

	data = request.get_json() or {}
	name = data.get('name')
	price = data.get('price')
	image_url = data.get('imageUrl') or data.get('image_url')

	if not name or price is None:
		return jsonify({'error': 'name and price required'}), 400

	try:
		price_val = float(price)
	except ValueError:
		return jsonify({'error': 'invalid price'}), 400

	product = Product(name=name, price=price_val, image_url=image_url)
	db.session.add(product)
	try:
		db.session.commit()
	except Exception as e:
		logger.exception('Failed to create product')
		db.session.rollback()
		return jsonify({'error': 'internal error', 'detail': str(e)}), 500
	return jsonify(product.to_dict()), 201


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
	if not is_admin_logged_in():
		return jsonify({'error': 'unauthorized'}), 401

	product = Product.query.get_or_404(product_id)
	db.session.delete(product)
	try:
		db.session.commit()
	except Exception as e:
		logger.exception('Failed to delete product %s', product_id)
		db.session.rollback()
		return jsonify({'error': 'internal error', 'detail': str(e)}), 500
	return jsonify({'status': 'deleted'})


if __name__ == '__main__':
	# Ensure DB exists when running locally
	try:
		db.create_all()
	except Exception:
		pass

	debug = os.environ.get('FLASK_DEBUG', '1') == '1'
	port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', 5000)))
	app.run(host='127.0.0.1', port=port, debug=debug)


# When running under a WSGI server (gunicorn / Render) the __main__ block
# won't execute, so ensure tables exist before the first request.
@app.before_first_request
def ensure_tables():
	try:
		db.create_all()
		logger.info('Database tables ensured')
	except Exception:
		logger.exception('Failed to create DB tables on startup')
