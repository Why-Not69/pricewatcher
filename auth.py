# auth.py
# Маршруты регистрации/логина/логаута, интеграция с Flask-Login.
from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db, User, Plan
from flask_login import login_user, logout_user, login_required, current_user, LoginManager

auth_bp = Blueprint("auth", __name__)

login_manager = LoginManager()
login_manager.login_view = "auth.login"

@auth_bp.record_once
def init_login_manager(state):
    # ожидает, что login_manager.init_app(app) вызывается в app.py
    pass

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Форма регистрации (простая)
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Введите email и пароль.", "danger")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(email=email).first():
            flash("Пользователь с таким email уже существует.", "warning")
            return redirect(url_for("auth.register"))
        # по умолчанию даём бесплатный план (Plan с price_cents == 0)
        free_plan = Plan.query.filter_by(price_cents=0).first()
        user = User(email=email, plan=free_plan)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Регистрация успешна. Войдите в аккаунт.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Вход выполнен.", "success")
            return redirect(url_for("index"))
        flash("Неверный email или пароль.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
