# config.py
# Простая конфигурация — берёт важные секреты из переменных окружения.
import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")  # замените в продакшне
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(basedir, "db.sqlite"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Stripe (пример) - заполняйте в .env или окружении
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    # Планировщик: как часто обновлять цены (в секундах)
    PRICE_UPDATE_INTERVAL = int(os.environ.get("PRICE_UPDATE_INTERVAL", 600))  # 600 сек = 10 мин
