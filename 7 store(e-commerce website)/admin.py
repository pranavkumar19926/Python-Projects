from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, User, Product, Order
from flask_login import login_required, current_user
from functools import wraps

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user and current_user.is_authenticated and current_user.is_admin):
            flash("Admin access required.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    users = User.query.all()
    products = Product.query.all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin_dashboard.html", users=users, products=products, orders=orders)

@admin_bp.route("/user/<int:uid>/toggle_seller", methods=["POST"])
@login_required
@admin_required
def toggle_seller(uid):
    u = User.query.get_or_404(uid)
    u.is_seller = not u.is_seller
    db.session.commit()
    flash("Seller flag toggled.", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/user/<int:uid>/toggle_admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(uid):
    u = User.query.get_or_404(uid)
    u.is_admin = not u.is_admin
    db.session.commit()
    flash("Admin flag toggled.", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/product/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def product_delete(pid):
    p = Product.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("Product removed.", "info")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/order/<int:oid>/set_status", methods=["POST"])
@login_required
@admin_required
def set_order_status(oid):
    o = Order.query.get_or_404(oid)
    status = request.form.get("status")
    if status:
        o.status = status
        db.session.commit()
        flash("Order status updated.", "info")
    return redirect(url_for("admin.dashboard"))
