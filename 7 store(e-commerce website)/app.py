import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, session, request, send_from_directory
from config import Config
from werkzeug.utils import secure_filename
from flask_login import LoginManager
from flask_wtf import CSRFProtect
import stripe

# import models inside create_app to avoid circular import issues
def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static")
    app.config.from_object(config_class)

    # init extensions
    from models import db, User  # models must exist
    db.init_app(app)

    # CSRF
    csrf = CSRFProtect()
    csrf.init_app(app)

    # login manager
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    # inject a now() helper for templates
    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow}

    # inject cart quantity
    @app.context_processor
    def inject_cart_quantity():
        cart = session.get("cart", {}) or {}
        qty = sum(int(v) for v in cart.values())
        return {"cart_quantity": qty}

    # template filter for INR
    @app.template_filter("inr")
    def inr_format(value):
        try:
            return f"₹{float(value):,.2f}"
        except Exception:
            return value

    # stripe
    stripe.api_key = app.config.get("STRIPE_SECRET_KEY")

    # register blueprints (import here to avoid circular)
    from auth import auth_bp
    from shop import shop_bp
    from seller import seller_bp
    from admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(seller_bp)
    app.register_blueprint(admin_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    # Serve uploaded images from static/images via a friendly endpoint
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        # static/images is the folder we use for uploaded product images
        images_dir = os.path.join(app.root_path, "static", "images")
        return send_from_directory(images_dir, filename)
    
        # Stripe webhook endpoint (CSRF exempt)
    @app.route("/stripe/webhook", methods=["POST"])
    @csrf.exempt
    def stripe_webhook():
        payload = request.get_data()
        sig_header = request.headers.get("Stripe-Signature", None)
        webhook_secret = app.config.get("STRIPE_WEBHOOK_SECRET")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError as e:
            # Invalid payload
            current_app.logger.error("Invalid webhook payload: %s", e)
            return ("Bad payload", 400)
        except stripe.error.SignatureVerificationError as e:
            current_app.logger.error("Invalid signature: %s", e)
            return ("Bad signature", 400)

        # Handle the checkout.session.completed event
        if event["type"] == "checkout.session.completed":
            session_obj = event["data"]["object"]
            order_id = session_obj.get("metadata", {}).get("order_id")
            # mark order as paid
            if order_id:
                try:
                    from models import db, Order
                    o = Order.query.get(int(order_id))
                    if o:
                        o.status = "paid"
                        o.payment_intent = session_obj.get("payment_intent")
                        db.session.commit()
                        current_app.logger.info("Order %s marked as paid", order_id)
                        # optionally clear cart for this user (if stored server-side)
                except Exception as e:
                    current_app.logger.error("Webhook DB update failed: %s", e)

        return ("", 200)


    # create tables on first request if they don't exist (safe for dev)
    @app.before_first_request
    def create_tables():
        db.create_all()

    return app

# run
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", debug=True)
