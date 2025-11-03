# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from models import db, ProductLink, PriceHistory
from scraper import fetch_price
import traceback

scheduler = BackgroundScheduler()

def update_all_prices():
    """
    Обновляем цены для всех ProductLink в фоне.
    - Используем корректный Flask application context,
      который назначается в start_scheduler(app, ...).
    - Для каждой ссылки пытаемся получить цену через fetch_price,
      обновляем поля last_price/last_checked, добавляем запись в PriceHistory.
    - Коммитим изменения; при исключении делаем rollback и логируем трассировку.
    """
    # Правильный контекст приложения (scheduler.app устанавливается в start_scheduler)
    with scheduler.app.app_context():
        print(f"[scheduler] Начало обновления цен — {datetime.utcnow()}")
        links = ProductLink.query.all()

        for ln in links:
            try:
                price, err = fetch_price(ln.url)
                ln.last_checked = datetime.utcnow()

                if price is not None:
                    ln.last_price = price

                    # Сохраняем историю цен (используем backref 'link' или явно link_id)
                    hist = PriceHistory(link=ln, price=price)
                    db.session.add(hist)
                    db.session.commit()

                    print(f"[update_all_prices] ✅ {ln.url} — новая цена: {price}")
                else:
                    # fetch_price вернул ошибку — логируем
                    print(f"[update_all_prices] ⚠ {ln.url} — ошибка получения цены: {err}")

            except Exception as e:
                # Откатываем транзакцию и печатаем трассировку, чтобы не остановить цикл
                db.session.rollback()
                print(f"[update_all_prices] ❌ Ошибка при обновлении {ln.url}: {e}")
                traceback.print_exc()

        print(f"[scheduler] Завершено обновление — {datetime.utcnow()}\n")


def start_scheduler(app, interval_seconds=600):
    """
    Запускает фоновый планировщик.
    - Назначаем app в scheduler.app (чтобы update_all_prices мог получить context)
    - Добавляем job только если он ещё не создан, чтобы избежать дублирования
    - Запускаем планировщик
    """
    scheduler.app = app

    # Если job уже есть — не добавляем заново (replace_existing=True даёт дополнительную страховку)
    if not scheduler.get_job("update_prices_job"):
        scheduler.add_job(
            func=update_all_prices,
            trigger="interval",
            seconds=interval_seconds,
            id="update_prices_job",
            replace_existing=True
        )

    scheduler.start()
    print(f"[scheduler] Планировщик запущен. Интервал: {interval_seconds} секунд")
