from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, SellerProfile
from forms import RegisterForm, LoginForm
from werkzeug.security import generate_password_hash

auth_bp = Blueprint("auth", __name__, template_folder="templates", url_prefix="/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        # check existing
        existing = User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first()
        if existing:
            flash("User with that username/email already exists.", "warning")
            return redirect(url_for("auth.register"))
        u = User(username=form.username.data, email=form.email.data)
        u.set_password(form.password.data)
        # if they checked a "seller" box, you could set is_seller here. For now basic customer.
        db.session.add(u)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    form = LoginForm()
    if form.validate_on_submit():
        # Allow login with username or email
        user = User.query.filter((User.username == form.username.data) | (User.email == form.username.data)).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Logged in successfully.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("shop.home"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("shop.home"))
