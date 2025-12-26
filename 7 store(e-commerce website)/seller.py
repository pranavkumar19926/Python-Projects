import os, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, Product
from werkzeug.utils import secure_filename

seller_bp = Blueprint("seller", __name__, template_folder="templates", url_prefix="/seller")

def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".",1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())

@seller_bp.route("/")
@login_required
def dashboard():
    if not current_user.is_seller and not current_user.is_admin:
        flash("Seller access required.", "warning")
        return redirect(url_for("index"))
    products = Product.query.filter_by(seller_id=current_user.id).all()
    return render_template("seller_dashboard.html", products=products)

@seller_bp.route("/product/new", methods=["GET","POST"])
@login_required
def product_new():
    if not current_user.is_seller and not current_user.is_admin:
        flash("Seller access required.", "warning")
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name")
        slug = request.form.get("slug") or (name.lower().replace(" ", "-"))
        description = request.form.get("description")
        price = float(request.form.get("price") or 0)
        stock = int(request.form.get("stock") or 0)
        image = request.files.get("image")
        image_filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            unique = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "static/images")
            os.makedirs(upload_folder, exist_ok=True)
            image.save(os.path.join(upload_folder, unique))
            image_filename = unique
        p = Product(seller_id=current_user.id, name=name, slug=slug, description=description, price=price, stock=stock, image_filename=image_filename)
        db.session.add(p)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("seller.dashboard"))
    return render_template("seller_product_form.html", product=None)

@seller_bp.route("/product/<int:pid>/edit", methods=["GET","POST"])
@login_required
def product_edit(pid):
    p = Product.query.get_or_404(pid)
    if p.seller_id != current_user.id and not current_user.is_admin:
        flash("Not authorized.", "danger")
        return redirect(url_for("seller.dashboard"))
    if request.method == "POST":
        p.name = request.form.get("name")
        p.slug = request.form.get("slug") or p.slug
        p.description = request.form.get("description")
        p.price = float(request.form.get("price") or p.price)
        p.stock = int(request.form.get("stock") or p.stock)
        image = request.files.get("image")
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            unique = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "static/images")
            os.makedirs(upload_folder, exist_ok=True)
            image.save(os.path.join(upload_folder, unique))
            p.image_filename = unique
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("seller.dashboard"))
    return render_template("seller_product_form.html", product=p)

@seller_bp.route("/product/<int:pid>/delete", methods=["POST"])
@login_required
def product_delete(pid):
    p = Product.query.get_or_404(pid)
    if p.seller_id != current_user.id and not current_user.is_admin:
        flash("Not authorized.", "danger")
        return redirect(url_for("seller.dashboard"))
    db.session.delete(p)
    db.session.commit()
    flash("Product deleted.", "info")
    return redirect(url_for("seller.dashboard"))
