# models.py
# SQLAlchemy-модели: User, Plan, Product, ProductLink, PriceHistory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class Plan(db.Model):
    __tablename__ = "plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    price_cents = db.Column(db.Integer, default=0)  # 0 = free
    max_products = db.Column(db.Integer, default=1)
    max_links_per_product = db.Column(db.Integer, default=5)

    def __repr__(self):
        return f"<Plan {self.name}>"

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=True)
    plan = db.relationship("Plan", backref="users")

    products = db.relationship("Product", backref="owner")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def allowed_product_slots(self):
        if self.plan:
            return self.plan.max_products
        return 1

    def allowed_links_per_product(self):
        if self.plan:
            return self.plan.max_links_per_product
        return 5

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))  # пользовательский заголовок (опционально)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    links = db.relationship("ProductLink", backref="product", cascade="all,delete-orphan")

    def min_price(self):
        """Возвращаем минимальную из последних цен по ссылкам (или None)."""
        prices = [ln.last_price for ln in self.links if ln.last_price is not None]
        return min(prices) if prices else None

class ProductLink(db.Model):
    __tablename__ = "product_links"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    url = db.Column(db.String(2000), nullable=False)
    last_price = db.Column(db.Float, nullable=True)
    last_checked = db.Column(db.DateTime, nullable=True)

    histories = db.relationship("PriceHistory", backref="link", cascade="all,delete-orphan")

class PriceHistory(db.Model):
    __tablename__ = "price_history"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("product_links.id"))
    price = db.Column(db.Float, nullable=True)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
