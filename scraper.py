# scraper.py
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "pricewatcher-bot/1.0 (+https://example.com)"
}

# Регулярка для поиска чисел с пробелами и запятыми
PRICE_RE = re.compile(r"(\d{1,3}(?:[ \u00A0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2}))")

def parse_price_text(text):
    """
    Преобразует строку цены в float.
    - Убираем пробелы (в том числе NBSP)
    - Определяем, какой символ десятичный
    """
    if not text:
        return None

    txt = text.replace('\xa0', ' ').replace('\u202f', ' ').strip()
    m = PRICE_RE.search(txt)
    if not m:
        return None

    s = m.group(1)

    # Определяем десятичный разделитель
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '')   # точки — тысячные
            s = s.replace(',', '.')  # запятая — десятичная
        else:
            s = s.replace(',', '')   # запятая — тысячные
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')      # запятая — десятичная

    # Убираем пробелы тысячные
    s = s.replace(' ', '')

    try:
        return float(s)
    except:
        return None

def extract_price_from_html(soup):
    """Ищем цену через meta, itemprop, класс/id или текст страницы"""
    # meta property
    meta = soup.find("meta", {"property": "product:price:amount"})
    if meta and meta.get("content"):
        p = parse_price_text(meta["content"])
        if p is not None:
            print(f"[extract_price] meta property: {p}")
            return p

    # itemprop
    meta = soup.find(attrs={"itemprop": "price"})
    if meta:
        content = meta.get("content") or meta.get_text()
        p = parse_price_text(content)
        if p is not None:
            print(f"[extract_price] itemprop: {p}")
            return p

    # meta name=price
    meta = soup.find("meta", {"name": "price"})
    if meta and meta.get("content"):
        p = parse_price_text(meta["content"])
        if p is not None:
            print(f"[extract_price] meta name: {p}")
            return p

    # span/div с классом/id содержащим 'price'
    candidates = soup.find_all(lambda tag: (
        tag.name in ["span", "div"] and
        (
            (tag.get("class") and any("price" in c.lower() for c in " ".join(tag.get("class")).split())) or
            (tag.get("id") and "price" in tag.get("id").lower())
        )
    ))
    for c in candidates:
        text = c.get_text(" ", strip=True)
        p = parse_price_text(text)
        if p is not None:
            print(f"[extract_price] class/id: {p}")
            return p

    # fallback — текст страницы
    body_text = soup.get_text(separator=' ', strip=True)
    p = parse_price_text(body_text)
    if p is not None:
        print(f"[extract_price] fallback: {p}")
        return p

    print("[extract_price] price not found")
    return None

def fetch_price(url, timeout=15):
    """Получаем страницу и возвращаем цену"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
    except Exception as e:
        print(f"[fetch_price] request error: {e}")
        return None, f"request error: {e}"

    if resp.status_code != 200:
        print(f"[fetch_price] status code: {resp.status_code}")
        return None, f"status {resp.status_code}"

    soup = BeautifulSoup(resp.text, "html.parser")
    price = extract_price_from_html(soup)
    if price is None:
        return None, "price not found"
    return price, None
