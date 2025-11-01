# scraper.py
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "pricewatcher-bot/1.0 (+https://example.com)"
}

PRICE_RE = re.compile(r"(\d{1,3}(?:[ \u00A0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2}))")

def parse_price_text(text):
    """
    Преобразует строку цены в float.
    - убираем пробелы (в том числе NBSP)
    - корректно определяем десятичный разделитель
    """
    if not text:
        return None

    txt = text.replace('\xa0', ' ').replace('\u202f', ' ').strip()
    m = PRICE_RE.search(txt)
    if not m:
        return None

    s = m.group(1)

    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')

    s = s.replace(' ', '')

    try:
        return float(s)
    except:
        return None

def extract_price_from_html(soup):
    """
    Ищем цену через:
    1) data-price атрибут (для Prestashop)
    2) meta property="product:price:amount"
    3) itemprop="price"
    4) meta name="price"
    5) span/div с классом/id содержащим 'price'
    6) fallback — текст страницы
    """
    # 1) data-price в элементах с классом, содержащим 'price'
    candidates = soup.find_all(lambda tag: (
        tag.name in ["span", "div"] and
        (tag.get("class") and any("price" in c.lower() for c in " ".join(tag.get("class")).split()))
    ))
    for c in candidates:
        data_price = c.get("data-price")
        if data_price:
            p = parse_price_text(data_price)
            if p is not None:
                print(f"[extract_price] data-price attribute: {p}")
                return p

    # 2) meta property="product:price:amount"
    meta = soup.find("meta", {"property": "product:price:amount"})
    if meta and meta.get("content"):
        p = parse_price_text(meta["content"])
        if p is not None:
            print(f"[extract_price] meta property: {p}")
            return p

    # 3) itemprop="price"
    meta = soup.find(attrs={"itemprop": "price"})
    if meta:
        content = meta.get("content") or meta.get_text()
        p = parse_price_text(content)
        if p is not None:
            print(f"[extract_price] itemprop: {p}")
            return p

    # 4) meta name="price"
    meta = soup.find("meta", {"name": "price"})
    if meta and meta.get("content"):
        p = parse_price_text(meta["content"])
        if p is not None:
            print(f"[extract_price] meta name: {p}")
            return p

    # 5) span/div с классом/id содержащим 'price'
    for c in candidates:
        text = c.get_text(" ", strip=True)
        p = parse_price_text(text)
        if p is not None:
            print(f"[extract_price] class/id text: {p}")
            return p

    # 6) fallback — текст страницы
    body_text = soup.get_text(separator=' ', strip=True)
    p = parse_price_text(body_text)
    if p is not None:
        print(f"[extract_price] fallback text: {p}")
        return p

    print("[extract_price] price not found")
    return None

def fetch_price(url, timeout=15):
    """Запрашиваем страницу и возвращаем цену"""
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
