# admin.py
# Простая админ-панель для управления тарифами (CRUD в минимальном виде).
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Plan
from flask_login import login_required, current_user

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    # простой декоратор: проверяет флаг is_admin
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Доступ запрещён: требуется права администратора.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route("/plans", methods=["GET", "POST"])
@admin_required
def plans():
    if request.method == "POST":
        # либо создаём новый тариф, либо редактируем существующий
        plan_id = request.form.get("plan_id")
        name = request.form.get("name").strip()
        price_cents = int(request.form.get("price_cents") or 0)
        max_products = int(request.form.get("max_products") or 1)
        max_links_per_product = int(request.form.get("max_links_per_product") or 5)

        if plan_id:
            plan = Plan.query.get(int(plan_id))
            if plan:
                plan.name = name
                plan.price_cents = price_cents
                plan.max_products = max_products
                plan.max_links_per_product = max_links_per_product
        else:
            plan = Plan(name=name, price_cents=price_cents, max_products=max_products, max_links_per_product=max_links_per_product)
            db.session.add(plan)
        db.session.commit()
        flash("Тариф сохранён.", "success")
        return redirect(url_for("admin.plans"))

    plans = Plan.query.all()
    return render_template("admin_plans.html", plans=plans)
