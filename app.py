# app.py
# Основной файл — создаёт Flask приложение, регистрирует blueprints, запускает планировщик.
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from models import db, User, Product, ProductLink, PriceHistory, Plan
from auth import auth_bp, login_manager
from admin import admin_bp
from flask_login import login_required, current_user
from scraper import fetch_price
from scheduler import start_scheduler
import stripe
from datetime import datetime

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    # инициализируем расширения
    db.init_app(app)
    login_manager.init_app(app)

    # регистрируем blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    # инициализация базы при первом старте
    with app.app_context():
        db.create_all()
        # создать базовый бесплатный план если отсутствует
        free = Plan.query.filter_by(price_cents=0).first()
        if not free:
            free = Plan(name="Free", price_cents=0, max_products=1, max_links_per_product=5)
            db.session.add(free)
            db.session.commit()

    # главная страница — дашборд пользователя
    @app.route("/")
    @login_required
    def index():
        products = Product.query.filter_by(user_id=current_user.id).all()
        return render_template("index.html", products=products)

    # добавить продукт (до N ссылок)
    @app.route("/add_product", methods=["GET", "POST"])
    @login_required
    def add_product():
        if request.method == "POST":
            # проверка лимита по продуктам
            current_count = Product.query.filter_by(user_id=current_user.id).count()
            if current_count >= current_user.allowed_product_slots():
                flash(f"Достигнут лимит продуктов для вашего тарифа ({current_user.allowed_product_slots()}).", "warning")
                return redirect(url_for("index"))

            name = request.form.get("name", "").strip() or "Без названия"
            urls = []
            for i in range(1, 6):  # поля url1..url5
                u = request.form.get(f"url{i}", "").strip()
                if u:
                    urls.append(u)
            if not urls:
                flash("Добавьте хотя бы одну ссылку.", "warning")
                return redirect(url_for("add_product"))
            if len(urls) > current_user.allowed_links_per_product():
                flash(f"Для вашего тарифа доступно максимум {current_user.allowed_links_per_product()} ссылок на продукт.", "warning")
                return redirect(url_for("add_product"))

            prod = Product(name=name, owner=current_user)
            for u in urls:
                link = ProductLink(url=u)
                prod.links.append(link)
            db.session.add(prod)
            db.session.commit()
            flash("Продукт добавлен. Система начнёт отслеживать цены (первые значения появятся после проверки).", "success")
            return redirect(url_for("index"))
        # GET
        return render_template("add_product.html", max_links=current_user.allowed_links_per_product())

    # страница продукта — список ссылок и кнопка обновить сейчас
    @app.route("/product/<int:product_id>")
    @login_required
    def product_detail(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа к этому продукту.", "danger")
            return redirect(url_for("index"))
        return render_template("product_detail.html", product=prod)

    # ручное обновление цен для одного продукта
    @app.route("/product/<int:product_id>/update", methods=["POST"])
    @login_required
    def product_update_now(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа.", "danger")
            return redirect(url_for("index"))
        for ln in prod.links:
            price, err = fetch_price(ln.url)
            ln.last_checked = datetime.utcnow()
            if price is not None:
                ln.last_price = price
                hist = PriceHistory(link=ln, price=price)
                db.session.add(hist)
            db.session.commit()
        flash("Обновление выполнено.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    # маршрут: редактирование продукта
    @app.route("/product/<int:product_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_product(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа к этому продукту.", "danger")
            return redirect(url_for("index"))

        if request.method == "POST":
            name = request.form.get("name", "").strip() or "Без названия"

            # Собираем ссылки из полей url1..url5, но учитываем лимит тарифа
            urls = []
            for i in range(1, 6):
                u = request.form.get(f"url{i}", "").strip()
                if u:
                    urls.append(u)

            if len(urls) > current_user.allowed_links_per_product():
                flash(f"Для вашего тарифа доступно максимум {current_user.allowed_links_per_product()} ссылок на продукт.", "warning")
                return redirect(url_for("edit_product", product_id=product_id))

            # Удаляем старые ссылки и создаём новые из непустых полей
            for ln in list(prod.links):
                db.session.delete(ln)

            prod.name = name
            for u in urls:
                prod.links.append(ProductLink(url=u))

            db.session.commit()
            flash("Продукт обновлён.", "success")
            return redirect(url_for("product_detail", product_id=product_id))

        # GET
        return render_template("edit_product.html", product=prod, max_links=current_user.allowed_links_per_product())

    # маршрут: удаление продукта (POST, с проверкой прав)
    @app.route("/product/<int:product_id>/delete", methods=["POST"])
    @login_required
    def delete_product(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа.", "danger")
            return redirect(url_for("index"))
        # Удаляем продукт — cascades должны удалить ссылки и историю
        db.session.delete(prod)
        db.session.commit()
        flash("Продукт удалён.", "success")
        return redirect(url_for("index"))

    # пример простого Stripe Checkout (нужно заполнить ключи в окружении)
    @app.route("/create-checkout-session", methods=["POST"])
    @login_required
    def create_checkout_session():
        stripe.api_key = app.config["STRIPE_SECRET_KEY"]
        plan_id = request.form.get("plan_id")
        plan = Plan.query.get(int(plan_id))
        if not plan:
            flash("План не найден.", "danger")
            return redirect(url_for("index"))
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": plan.name},
                        "unit_amount": plan.price_cents,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=request.host_url + "stripe-success",
                cancel_url=request.host_url + "stripe-cancel",
            )
            return redirect(session.url, code=303)
        except Exception as e:
            flash(f"Stripe error: {e}", "danger")
            return redirect(url_for("index"))

    @app.route("/stripe-success")
    def stripe_success():
        flash("Платеж прошёл (пример). Нужно настроить webhook для автоматического переключения тарифов.", "success")
        return redirect(url_for("index"))

    @app.route("/stripe-cancel")
    def stripe_cancel():
        flash("Платёж отменён.", "info")
        return redirect(url_for("index"))

    return app

if __name__ == "__main__":
    app = create_app()
    # запускаем планировщик (интервал из конфигурации)
    start_scheduler(app, interval_seconds=int(os.environ.get("PRICE_UPDATE_INTERVAL", 600)))
    app.run(debug=True, host="127.0.0.1", port=5000)
