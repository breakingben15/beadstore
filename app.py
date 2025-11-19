from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, abort, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import stripe
import os
import logging

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
# Load environment variables from .env if present
env_path = Path(__file__).parent / '.env'
if env_path.exists():
	load_dotenv(env_path)

BASE_DIR = Path(__file__).parent

app = Flask(__name__, static_folder='static', template_folder='templates')
# --- Database Configuration ---
# Check for the RENDER_DB_URL environment variable first
db_url = os.environ.get('RENDER_DB_URL')

if db_url:
    # This replacement is necessary because Render's URL uses 'postgres://' 
    # but SQLAlchemy 2.0+ requires 'postgresql://' for the driver.
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    print("Found and adapted RENDER_DB_URL for PostgreSQL.")
else:
    # Fallback to local SQLite for development
    sqlite_url = f'sqlite:///{BASE_DIR / "data.db"}'
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
    print("RENDER_DB_URL not found. Using local sqlite:// data.db")


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)

# configure simple logging to stderr
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Models ---

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

class Order(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	created_at = db.Column(db.DateTime, default=datetime.utcnow)
	# Customer Info
	customer_name = db.Column(db.String(256), nullable=False)
	customer_email = db.Column(db.String(256), nullable=False)
	customer_street1 = db.Column(db.String(256), nullable=False)
	customer_street2 = db.Column(db.String(256), nullable=True)
	customer_city = db.Column(db.String(100), nullable=False)
	customer_state = db.Column(db.String(100), nullable=False)
	customer_zip = db.Column(db.String(20), nullable=False)
	# Order Info
	subtotal = db.Column(db.Float, nullable=False)
	shipping_cost = db.Column(db.Float, nullable=False)
	total_price = db.Column(db.Float, nullable=False)
	items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

	def to_dict(self):
		return {
			'id': self.id,
			'createdAt': self.created_at.isoformat(),
			'customerName': self.customer_name,
			'customerEmail': self.customer_email,
			'totalPrice': self.total_price,
			'subtotal': self.subtotal,
			'shippingCost': self.shipping_cost,
			'items': [item.to_dict() for item in self.items]
		}

class OrderItem(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
	product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True) # Allow null if product is deleted
	product_name = db.Column(db.String(256), nullable=False) # Store name at time of purchase
	quantity = db.Column(db.Integer, nullable=False)
	price_at_purchase = db.Column(db.Float, nullable=False) # Store price at time of purchase

	def to_dict(self):
		return {
			'id': self.id,
			'productId': self.product_id,
			'productName': self.product_name,
			'quantity': self.quantity,
			'priceAtPurchase': self.price_at_purchase
		}

# --- Helper Functions ---

def is_admin_logged_in():
	return session.get('is_admin') is True

# --- Auth Routes ---
# --- Post-Payment Redirect Routes ---

@app.route('/payment/success')
def payment_success():
    # You would typically confirm payment via a webhook before showing this.
    return render_template('success.html') # Need to create this file

@app.route('/payment/cancel')
def payment_cancel():
    return render_template('cancel.html') # Need to create this file
	
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

# --- Main Page ---
# --- Health Check (For UptimeRobot) ---
@app.route('/health')
def health_check():
    # Returning a simple string and 200 status code
    return "Alive", 200

@app.route('/')
def index():
	return render_template('index.html')

# --- Product API ---

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

# --- Order API ---

# New route to create a Stripe Checkout Session
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    # Reuse your cart verification logic here (items, subtotal calculation, etc.)
    data = request.get_json()
    cart_items = data.get('cartItems')
    
    # Transform your cart items into Stripe's required format (line_items)
    line_items = []
    for item in cart_items:
        # Note: Stripe requires the price in cents (e.g., $19.99 is 1999)
        product = Product.query.get(item['id'])
        if product:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(product.price * 100),  # Convert to cents
                    'product_data': {
                        'name': product.name,
                    },
                },
                'quantity': item['quantity'],
            })
            
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.url_root + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.url_root + 'cancel',
        )
        return jsonify({'id': session.id})
    except Exception as e:
        return jsonify(error=str(e)), 403
		
		# Hardcoded shipping for this example
		shipping_cost = 5.00
		total_price = subtotal + shipping_cost

		# Create the order
		new_order = Order(
			customer_name=customer_info['name'],
			customer_email=customer_info['email'],
			customer_street1=customer_info['street1'],
			customer_street2=customer_info.get('street2'),
			customer_city=customer_info['city'],
			customer_state=customer_info['state'],
			customer_zip=customer_info['zip'],
			subtotal=subtotal,
			shipping_cost=shipping_cost,
			total_price=total_price
		)
		
		# Add order and items to session
		db.session.add(new_order)
		# This associates items with the order *after* new_order gets its ID
		for item in new_order_items:
			item.order = new_order
			db.session.add(item)
		
		db.session.commit()
		
		logger.info(f'Created new order {new_order.id} for {new_order.customer_email} with {len(new_order_items)} items.')

		return jsonify(new_order.to_dict()), 201

	except ValueError as e:
		logger.warning(f'Validation error creating order: {e}')
		db.session.rollback()
		return jsonify({'error': str(e)}), 400
	except Exception as e:
		logger.exception('Failed to create order')
		db.session.rollback()
		return jsonify({'error': 'internal server error', 'detail': str(e)}), 500

# You could also add an admin-only route to view orders
@app.route('/api/orders', methods=['GET'])
def list_orders():
	if not is_admin_logged_in():
		return jsonify({'error': 'unauthorized'}), 401
	
	orders = Order.query.order_by(Order.created_at.desc()).all()
	return jsonify([o.to_dict() for o in orders])


# --- App Start / DB Init ---

if __name__ == '__main__':
	# Ensure DB exists when running locally
	with app.app_context():
		try:
			db.create_all()
		except Exception:
			pass

	debug = os.environ.get('FLASK_DEBUG', '1') == '1'
	port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', 5000)))
	app.run(host='127.0.0.1', port=port, debug=debug)


# When running under a WSGI server (gunicorn / Render) the __main__ block
# won't execute. Prefer `before_serving` (newer Flask) which runs once when
# the server is ready; fall back to a guarded `before_request` that creates
# tables only the first time to avoid calling create_all() on every request.
if hasattr(app, 'before_serving'):
	@app.before_serving
	def ensure_tables_on_start():
		with app.app_context():
			try:
				db.create_all()
				logger.info('Database tables ensured (before_serving)')
			except Exception:
				logger.exception('Failed to create DB tables on startup (before_serving)')
else:
	# Fallback: run once on first request per process
	def _ensure_tables_once():
		if not getattr(app, '_tables_ensured', False):
			with app.app_context():
				try:
					db.create_all()
					app._tables_ensured = True
					logger.info('Database tables ensured (before_request fallback)')
				except Exception:
					logger.exception('Failed to create DB tables on startup (before_request fallback)')

	@app.before_request
	def ensure_tables():
		_ensure_tables_once()
