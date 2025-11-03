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

        # === ЗДЕСЬ запускаем планировщик внутри app context ===
        # Это гарантирует, что планировщик стартует вне зависимости от способа запуска приложения
        try:
            start_scheduler(app, interval_seconds=int(os.environ.get("PRICE_UPDATE_INTERVAL", 600)))
        except Exception as _e:
            # Не фатал — но логируем для диагностики
            print(f"[app] не удалось запустить планировщик: {_e}")

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
            name = request.form.get("name")
            links = [request.form.get(f"link{i}") for i in range(1, 6)]
            links = [l.strip() for l in links if l and l.strip()]

            # проверка лимита по плану
            # (предполагается, что у current_user есть метод allowed_links_per_product)
            if len(links) > current_user.allowed_links_per_product():
                flash("Превышено максимальное количество ссылок для продукта по вашему плану.", "danger")
                return redirect(url_for("add_product"))

            product = Product(name=name, user_id=current_user.id, created_at=datetime.utcnow())
            db.session.add(product)
            db.session.commit()

            for url in links:
                price, err = fetch_price(url)
                link = ProductLink(product_id=product.id, url=url, last_price=price if price is not None else None, last_checked=datetime.utcnow())
                db.session.add(link)
                db.session.commit()

                if price is not None:
                    hist = PriceHistory(link=link, price=price)
                    db.session.add(hist)
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

    # ручное обновление цен для продукта (вызывается пользователем)
    @app.route("/product/<int:product_id>/update", methods=["POST"])
    @login_required
    def product_update(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа.", "danger")
            return redirect(url_for("index"))

        for link in prod.links:
            try:
                price, err = fetch_price(link.url)
                link.last_checked = datetime.utcnow()
                if price is not None:
                    link.last_price = price
                    db.session.add(PriceHistory(link=link, price=price))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[product_update] Ошибка при обновлении {link.url}: {e}")

        flash("Обновление завершено.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    # редактирование/удаление продукта (упрощённый пример)
    @app.route("/product/<int:product_id>/edit", methods=["GET", "POST"])
    @login_required
    def product_edit(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа.", "danger")
            return redirect(url_for("index"))

        if request.method == "POST":
            prod.name = request.form.get("name", prod.name)
            db.session.commit()
            flash("Изменения сохранены.", "success")
            return redirect(url_for("product_detail", product_id=product_id))
        return render_template("edit_product.html", product=prod)

    @app.route("/product/<int:product_id>/delete", methods=["POST"])
    @login_required
    def product_delete(product_id):
        prod = Product.query.get_or_404(product_id)
        if prod.user_id != current_user.id and not current_user.is_admin:
            flash("Нет доступа.", "danger")
            return redirect(url_for("index"))
        # удаление продукта и связанных ссылок/истории подразумевается через cascade в моделях
        db.session.delete(prod)
        db.session.commit()
        flash("Продукт удалён.", "success")
        return redirect(url_for("index"))

    @app.route("/create-checkout-session", methods=["POST"])
    def create_checkout_session():
        # Пример заглушки для Stripe Checkout (нужно настроить ключи и webhooks)
        try:
            # логика создания сессии Stripe...
            return redirect(url_for("index"))
        except Exception as e:
            flash("Ошибка при создании сессии платежа.", "danger")
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
    # при запуске через `python app.py` просто создаём приложение и запускаем сервер
    application = create_app()
    application.run(debug=True, host="127.0.0.1", port=5000)
