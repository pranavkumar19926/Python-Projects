from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from models import Product, Order, OrderItem, db, Address
from flask_login import login_required, current_user
from sqlalchemy import or_
import stripe
from datetime import datetime
from sqlalchemy.exc import IntegrityError

shop_bp = Blueprint("shop", __name__)


@shop_bp.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).limit(24).all()
    return render_template("index.html", products=products)


@shop_bp.route("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug).first_or_404()
    return render_template("product.html", product=product)


# Add to cart — require login first
@shop_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    # require login
    if not (current_user and current_user.is_authenticated):
        prod = Product.query.get(product_id)
        next_url = request.referrer or (url_for("shop.product_detail", slug=prod.slug) if prod else url_for("shop.home"))
        flash("Please log in to add items to your cart.", "warning")
        return redirect(url_for("auth.login", next=next_url))

    try:
        qty = int(request.form.get("qty", 1))
    except Exception:
        qty = 1
    if qty < 1:
        qty = 1

    cart = session.get("cart", {}) or {}
    cart[str(product_id)] = cart.get(str(product_id), 0) + qty
    session["cart"] = cart
    flash("Added to cart!", "success")
    return redirect(request.referrer or url_for("shop.cart_view"))


@shop_bp.route("/cart")
def cart_view():
    cart = session.get("cart", {}) or {}
    items = []
    total = 0.0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            items.append({"product": product, "qty": int(qty)})
            total += product.price * int(qty)
    return render_template("cart.html", items=items, total=total)


@shop_bp.route("/cart/update", methods=["POST"])
def update_cart():
    cart = session.get("cart", {}) or {}
    new_cart = {}
    qty_fields_present = False
    for key, val in request.form.items():
        if not key.startswith("qty_"):
            continue
        qty_fields_present = True
        pid = key.split("qty_", 1)[1]
        try:
            q = int(val)
        except Exception:
            continue
        if q > 0:
            new_cart[str(pid)] = q
    if qty_fields_present:
        session["cart"] = new_cart
    # otherwise keep existing
    flash("Cart updated.", "success")
    return redirect(url_for("shop.cart_view"))


@shop_bp.route("/checkout")
@login_required
def checkout():
    cart = session.get("cart", {}) or {}
    items = []
    total = 0.0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            items.append({"product": product, "qty": int(qty)})
            total += product.price * int(qty)

    # If address was saved to session, we can fetch it for display
    address = None
    address_id = session.get("address_id")
    if address_id:
        address = Address.query.get(address_id)

    return render_template("checkout.html", items=items, total=total, address=address)


# Ensure stripe is configured each request
def _stripe_client():
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    return stripe


@shop_bp.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    """
    Creates a Stripe Checkout session and creates an Order in the DB (status='pending').
    The user is then redirected to stripe checkout.
    """
    cart = session.get("cart", {}) or {}
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("shop.cart_view"))

    # Build line items for Stripe and create Order + OrderItems locally
    stripe_items = []
    order = Order(user_id=current_user.id, status="pending", total_amount=0.0, created_at=datetime.utcnow())
    db.session.add(order)
    db.session.flush()  # so order.id exists

    total = 0.0
    try:
        for pid, qty in cart.items():
            product = Product.query.get(int(pid))
            if not product:
                continue

            unit_price_paisa = int(round(product.price * 100))  # rupees -> paise
            stripe_items.append({
                "price_data": {
                    "currency": "inr",
                    "product_data": {"name": product.name, "description": product.description or ""},
                    "unit_amount": unit_price_paisa,
                },
                "quantity": int(qty),
            })

            # ------------------------------
            # Robust ORDER ITEM CREATION
            # ------------------------------
            oi = OrderItem()  # create empty instance, set attributes manually
            cols = {c.name for c in getattr(OrderItem, "__table__").columns}

            # assign order foreign key
            if "order_id" in cols:
                setattr(oi, "order_id", order.id)
            elif "order" in cols:
                setattr(oi, "order", order.id)

            # assign product foreign key
            if "product_id" in cols:
                setattr(oi, "product_id", product.id)
            elif "prod_id" in cols:
                setattr(oi, "prod_id", product.id)

            # ensure product_name (or equivalent) is set for NOT NULL schemas
            if "product_name" in cols:
                setattr(oi, "product_name", product.name)
            elif "name" in cols:
                setattr(oi, "name", product.name)
            elif "title" in cols:
                setattr(oi, "title", product.name)

            # assign quantity using common column names
            qty_int = int(qty)
            for qname in ("quantity", "qty", "count", "amount", "qty_ordered", "quantity_ordered"):
                if qname in cols:
                    setattr(oi, qname, qty_int)
                    break
            else:
                # fallback: set 'quantity' if present, otherwise set 'qty' attribute for inspection
                if "quantity" in cols:
                    setattr(oi, "quantity", qty_int)
                else:
                    setattr(oi, "qty", qty_int)

            # assign unit/price using common column names
            for pname in ("unit_price", "price", "unit_amount", "amount", "item_price"):
                if pname in cols:
                    setattr(oi, pname, float(product.price))
                    break
            else:
                # fallback attribute
                setattr(oi, "unit_price", float(product.price))

            db.session.add(oi)
            total += product.price * qty_int

        # set order total
        order.total_amount = total
        db.session.commit()

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error("DB IntegrityError creating order/items: %s", e)
        flash("Failed to create order. Please try again or contact support.", "danger")
        return redirect(url_for("shop.cart_view"))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Unexpected error creating order/items: %s", e)
        flash("Unexpected error occurred. Please try again.", "danger")
        return redirect(url_for("shop.cart_view"))

    # Create Stripe Checkout session
    stripe_client = _stripe_client()
    domain = current_app.config.get("DOMAIN_URL", request.host_url.rstrip("/"))
    try:
        session_obj = stripe_client.checkout.Session.create(
            payment_method_types=["card"],
            line_items=stripe_items,
            mode="payment",
            success_url=f"{domain}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}&order_id={order.id}",
            cancel_url=f"{domain}/checkout",
            metadata={"order_id": str(order.id)},
        )
    except Exception as e:
        current_app.logger.error("Stripe session error: %s", e)
        flash("Payment initialization failed.", "danger")
        return redirect(url_for("shop.checkout"))

    # Redirect user to Stripe Checkout
    return redirect(session_obj.url, code=303)


@shop_bp.route("/orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)


@shop_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("search_results.html", products=[], query=query)
    products = Product.query.filter(
        or_(
            Product.name.ilike(f"%{query}%"),
            Product.description.ilike(f"%{query}%")
        )
    ).all()
    return render_template("search_results.html", products=products, query=query)


# Shipping address page
from forms import AddressForm


@shop_bp.route("/checkout/address", methods=["GET", "POST"])
@login_required
def checkout_address():
    form = AddressForm()
    if form.validate_on_submit():
        addr = Address(
            user_id=current_user.id,
            full_name=form.full_name.data,
            phone=form.phone.data,
            line1=form.line1.data,
            line2=form.line2.data,
            city=form.city.data,
            state=form.state.data,
            pincode=form.pincode.data
        )
        db.session.add(addr)
        db.session.commit()
        session["address_id"] = addr.id
        flash("Address saved!", "success")
        return redirect(url_for("shop.checkout"))
    return render_template("checkout_address.html", form=form)

@shop_bp.route("/stripe/success")
@login_required
def stripe_success():
    """
    Handle redirect from Stripe Checkout after payment.
    Verify the session with Stripe, update the Order if needed,
    clear the session cart, and prepare a safe items list for the template.
    """
    session_id = request.args.get("session_id")
    order_id = request.args.get("order_id")

    if not session_id or not order_id:
        flash("Missing payment information.", "warning")
        return redirect(url_for("shop.home"))

    stripe_client = _stripe_client()
    try:
        stripe_session = stripe_client.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except Exception as e:
        current_app.logger.exception("Failed to retrieve stripe session: %s", e)
        flash("Could not confirm payment with Stripe. If you were charged, check Orders later.", "warning")
        return redirect(url_for("shop.my_orders"))

    payment_status = stripe_session.get("payment_status")
    payment_intent = stripe_session.get("payment_intent")

    # Fetch our order
    order = Order.query.get(int(order_id))
    if not order:
        flash("Order not found.", "warning")
        return redirect(url_for("shop.home"))

    # If Stripe says the payment is paid, update order status
    if isinstance(payment_status, str) and payment_status.lower() == "paid":
        if order.status != "paid":
            order.status = "paid"
            try:
                order.payment_intent = payment_intent
            except Exception:
                pass
            db.session.commit()

        # Clear session cart (user returned and payment completed)
        session.pop("cart", None)
    else:
        # Not 'paid' yet — rely on webhook to update order later, but continue to show a page
        flash("Payment is processing. If it was successful it will appear in your Orders soon.", "info")

    # Build a safe items list for the template (normalize different column names)
    items_info = []
    for it in getattr(order, "items", []) or []:
        # quantity field (try common names)
        qty = None
        for qname in ("quantity", "qty", "count", "amount", "qty_ordered", "quantity_ordered"):
            qty = getattr(it, qname, None)
            if qty is not None:
                break
        if qty is None:
            qty = 1

        # unit price field
        unit_price = None
        for pname in ("unit_price", "price", "unit_amount", "amount", "item_price"):
            unit_price = getattr(it, pname, None)
            if unit_price is not None:
                break
        if unit_price is None:
            unit_price = 0.0

        # product name
        product_name = getattr(it, "product_name", None)
        if not product_name:
            # try to obtain from relationship
            try:
                product_obj = getattr(it, "product", None)
                product_name = getattr(product_obj, "name", None) if product_obj else None
            except Exception:
                product_name = None
        if not product_name:
            product_name = "Item"

        items_info.append({
            "quantity": int(qty),
            "unit_price": float(unit_price),
            "product_name": product_name
        })

    return render_template("payment_success.html", order=order, items_info=items_info)

@shop_bp.route("/order/<int:oid>")
@login_required
def order_detail(oid):
    # load order and check permissions
    o = Order.query.get_or_404(oid)

    # security: only owner or admin can view
    if o.user_id != current_user.id and not getattr(current_user, "is_admin", False):
        flash("Access denied.", "warning")
        return redirect(url_for("shop.my_orders"))

    # normalize items for display (safe attribute names)
    items_info = []
    for it in getattr(o, "items", []) or []:
        # quantity
        qty = None
        for qname in ("quantity", "qty", "count", "amount", "qty_ordered"):
            qty = getattr(it, qname, None)
            if qty is not None:
                break
        if qty is None:
            qty = 1

        # unit price
        unit_price = None
        for pname in ("unit_price", "price", "unit_amount", "amount", "item_price"):
            unit_price = getattr(it, pname, None)
            if unit_price is not None:
                break
        if unit_price is None:
            unit_price = 0.0

        # product name
        product_name = getattr(it, "product_name", None)
        if not product_name:
            product_obj = getattr(it, "product", None)
            product_name = getattr(product_obj, "name", None) if product_obj else None
        if not product_name:
            product_name = "Item"

        items_info.append({
            "quantity": int(qty),
            "unit_price": float(unit_price),
            "product_name": product_name
        })

    return render_template("order_detail.html", order=o, items_info=items_info)

