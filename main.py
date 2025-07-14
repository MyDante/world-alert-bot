import time, html, requests, logging, urllib.parse, re, feedparser, os, json, threading
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from langdetect import detect
from keep_alive import keep_alive

keep_alive()

# ─── Ваші токени ─────────────────────────────────────────────
TOKEN = "8104448357:AAHoIyZX-_z7sCxRYYWFsfL5jd1WNEhRYgA"
NEWSKEY = "15e117b2ecad4146a6a7d42400e6c268"
MYMEMORY_KEY = "bf82f06cb760de468651"
INTERVAL = 1  # 1 година
scheduler.add_job(check_news_and_send, 'interval', hours=INTERVAL)

bot = Bot(TOKEN)
USERS_FILE = "chat_ids.json"
SEEN_FILE = "seen.txt"

seen: set[str] = set()


# ─── Збереження та завантаження ID ──────────────────────────
def save_chat_id(chat_id: int):
    ids = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            ids = json.load(f)
    if chat_id not in ids:
        ids.append(chat_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(ids, f)


def load_chat_ids():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ─── Переклад ────────────────────────────────────────────────
def translate(text: str, target="uk") -> str:
    if not text:
        return text
    try:
        source_lang = detect(text)
        q = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={source_lang}|{target}&key={MYMEMORY_KEY}"
        data = requests.get(url, timeout=10).json()
        trans = data.get("responseData", {}).get("translatedText")
        return trans if trans else text
    except Exception as e:
        logging.error("Translate error: %s", e)
        return text


# ─── Завантаження/збереження вже відправлених новин ──────────
def load_seen():
    global seen
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            seen = set(json.load(f))
    else:
        seen = set()


def save_seen():
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)

KEYWORDS = [
    "protest", "protests", "riot", "riots", "demonstration", "demonstrations",
    "mass rally", "mass rallies", "strike", "strikes", "attack", "attacks",
    "assault", "shooting", "mass shooting", "bomb", "bombing", "explosion",
    "explosions", "blast", "blasts", "terror", "terrorist", "terrorism", "war",
    "invasion", "conflict", "incursion", "clash", "clashes", "протест",
    "протести", "мітинг", "мітинги", "заворушення", "теракт", "терор", "вибух",
    "бомба", "атака", "удар", "напад", "стрілянина", "обстріл",
    "ракетний удар", "protesti", "neredi", "štrajk", "napad", "eksplozija",
    "bomba", "terorizam", "teroristički", "okupljanje", "mitinguri", "grevă",
    "greve", "atac", "explozie", "explozii", "bombă", "protesto", "gösteri",
    "eylem", "grev", "isyan", "saldırı", "patlama", "terör", "pradarshan",
    "hinsa", "danga", "hamla", "visfot", "aatankvad", "gompinga", "maandamano",
    "shambulio", "mlipuko", "bomu", "uvamizi", "protesta", "manifestación",
    "manifestations", "émeute", "attaque", "grève", "proteste",
    "demonstrationen", "anschlag", "explosionen", "streik", "intifada",
    "hujum", "tafwij", "tasfiyah", "muẓāhara", "iḥtijāj", "baozha", "kongbu",
    "zhengyi", "youxing"
]

NEGATIVE = [
    "greeting", "congratulate", "award", "birthday", "anniversary", "festival",
    "holiday", "visit", "meeting", "congrats", "speech", "celebration",
    "declaration", "message", "interview", "wishes", "statement", "calls for",
    "thank", "fish", "fishing", "economy", "sports", "game", "football",
    "match", "result", "weather", "coffee", "espresso", "trade", "deal",
    "museum", "history", "culture", "fashion", "recipe", "review"
]


# ─── Фільтрація новин ───────────────────────────────────────
def interesting(title: str, description: str) -> bool:
    text = f"{title or ''} {description or ''}".lower()
    if any(neg in text for neg in NEGATIVE):
        return False
    hits = 0
    for kw in KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            hits += 1
            if hits >= 2:
                return True
    return False


# ─── Надсилання всім підписникам ────────────────────────────
def send(title: str, link: str):
    if link in seen:
        return
    seen.add(link)
    title_ua = translate(title)
    text = f"⚠️ <b>{html.escape(title_ua)}</b>\n🔗 {link}"
    for chat_id in load_chat_ids():
        try:
            bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            logging.error("❗Send error: %s", e)


# ─── Джерело 1: NewsAPI ──────────────────────────────────────
def fetch_newsapi():
    try:
        url = f"https://newsapi.org/v2/everything?q=%2A&pageSize=50&sortBy=publishedAt&apiKey={NEWSKEY}"
        r = requests.get(url, timeout=15)
        articles = r.json().get("articles", [])
        for a in articles:
            title = a.get("title") or ""
            desc = a.get("description") or ""
            link = a.get("url") or ""
            if interesting(title, desc) and link not in seen:
                send(title, link)
    except Exception as e:
        logging.error("❗NewsAPI error: %s", e)


# ─── Джерело 2: RSS ──────────────────────────────────────────
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rsshub.app/telegram/channel/liveuamap",
    "https://rsshub.app/telegram/channel/SouthAsiaIndex",
    "https://rsshub.app/telegram/channel/stratcomcentre",
]


def fetch_rss():
    # Тестова новина для перевірки надсилання
    test_title = "🔥 TEST: тестова новина"
    test_link = "https://example.com/test-news-unique"
    if test_link not in seen:
        send(test_title, test_link)

    for feed_url in RSS_FEEDS:
        d = feedparser.parse(feed_url)
        for entry in d.entries:
            title = entry.get("title", "") or ""
            summary = entry.get("summary", "") or ""
            content_html = ""
            if "content" in entry and isinstance(entry["content"], list):
                content_html = entry["content"][0].value or ""
            text_raw = title + " " + summary + " " + content_html
            soup = BeautifulSoup(text_raw, "html.parser")
            clean_text = soup.get_text(separator=" ")
            link = entry.get("link", "") or ""
            if interesting(clean_text, "") and link not in seen:
                send(title.strip(), link)


# ─── Джерело 3: TRT Global ──────────────────────────────────
def fetch_trt():
    try:
        url = "https://trt.global/russian"
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for article in soup.select("a.card"):
            title = article.get("title") or article.text.strip()
            link = article.get("href")
            if link and not link.startswith("http"):
                link = "https://trt.global" + link
            if interesting(title, "") and link not in seen:
                send(title, link)
    except Exception as e:
        logging.error("❗TRT error: %s", e)


# ─── Цикл перевірки новин ───────────────────────────────────
def news_loop():
    while True:
        try:
            logging.info("🔍 Перевірка новин…")
            fetch_newsapi()
            fetch_rss()
            fetch_trt()
            save_seen()
            logging.info("✅ Завершено. Чекаю 1 год…")
        except Exception as e:
            logging.error("❗Loop error: %s", e)
        time.sleep(INTERVAL)


# ─── Обробка повідомлень користувачів ───────────────────────
def handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    save_chat_id(chat_id)
    update.message.reply_text("✅ Вас підписано на сповіщення. Дякуємо!")


# ─── Запуск ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
load_seen()

# Нитка для циклу новин
threading.Thread(target=news_loop, daemon=True).start()

# Запуск Telegram-бота
updater = Updater(TOKEN)
updater.dispatcher.add_handler(MessageHandler(Filters.all, handler))
updater.start_polling()
updater.idle()
