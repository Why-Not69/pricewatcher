# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from models import db, ProductLink, PriceHistory
from scraper import fetch_price
import traceback

scheduler = BackgroundScheduler()

def update_all_prices():
    """Обновляем цены для всех ProductLink"""
    with scheduler.app.app.app_context():
        links = ProductLink.query.all()
        for ln in links:
            try:
                price, err = fetch_price(ln.url)
                ln.last_checked = datetime.utcnow()

                if price is not None:
                    ln.last_price = price
                    hist = PriceHistory(link=ln, price=price)
                    db.session.add(hist)
                    db.session.commit()
                    print(f"[update_all_prices] {ln.url} — новая цена: {price}")
                else:
                    print(f"[update_all_prices] {ln.url} — ошибка: {err}")

            except Exception as e:
                db.session.rollback()
                print(f"[update_all_prices] Ошибка при обновлении {ln.url}: {e}")
                traceback.print_exc()

def start_scheduler(app, interval_seconds=600):
    """Запускаем планировщик"""
    scheduler.app = app
    scheduler.add_job(
        func=update_all_prices,
        trigger="interval",
        seconds=interval_seconds,
        id="update_prices_job",
        replace_existing=True
    )
    scheduler.start()
