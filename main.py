import os, json, time, html, logging, re, urllib.parse, requests, feedparser
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from langdetect import detect
from keep_alive import keep_alive
from apscheduler.schedulers.background import BackgroundScheduler

# ── Keep alive для Replit ────────────────
keep_alive()

# ── Конфігурація ─────────────────────────
TOKEN = "8104448357:AAHoIyZX-_z7sCxRYYWFsfL5jd1WNEhRYgA"
NEWSKEY = "15e117b2ecad4146a6a7d42400e6c268"
MYMEMORY_KEY = "bf82f06cb760de468651"
INTERVAL_MIN = 60  # інтервал у хвилинах

USERS_FILE = "chat_ids.json"
SEEN_FILE = "seen.txt"
seen = set()

bot = Bot(TOKEN)
updater = Updater(TOKEN)


# ── Підписка ─────────────────────────────
def load_chat_ids():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_chat_id(chat_id: int):
    ids = load_chat_ids()
    if chat_id not in ids:
        ids.append(chat_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(ids, f)


# ── Переклад ─────────────────────────────
def translate(text: str, target="uk") -> str:
    if not text:
        return text
    try:
        src = detect(text)
        q = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{target}&key={MYMEMORY_KEY}"
        data = requests.get(url, timeout=10).json()
        return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        logging.error("Translate error: %s", e)
        return text


# ── Обробка вже надісланих ───────────────
def load_seen():
    global seen
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            seen = set(json.load(f))


def save_seen():
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)


# ── Фільтрація ───────────────────────────
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


def interesting(title: str, body: str) -> bool:
    text = f"{title} {body}".lower()
    if any(w in text for w in NEGATIVE):
        return False
    hits = sum(1 for kw in KEYWORDS
               if re.search(rf"\b{re.escape(kw)}\b", text))
    return hits >= 2


# ── Надсилання ───────────────────────────
def send(title: str, link: str):
    if link in seen:
        return
    seen.add(link)
    msg = f"⚠️ <b>{html.escape(translate(title))}</b>\n🔗 {link}"
    for cid in load_chat_ids():
        try:
            bot.send_message(cid, msg, parse_mode="HTML")
        except Exception as e:
            logging.error("Send error: %s", e)


# ── Джерела новин ────────────────────────
def fetch_newsapi():
    try:
        url = f"https://newsapi.org/v2/everything?q=%2A&pageSize=50&sortBy=publishedAt&apiKey={NEWSKEY}"
        for a in requests.get(url, timeout=15).json().get("articles", []):
            if interesting(a.get("title", ""), a.get("description", "")):
                send(a.get("title", ""), a.get("url", ""))
    except Exception as e:
        logging.error("NewsAPI error: %s", e)


RSS_FEEDS = [
    # 🌍 Західні ЗМІ
    "https://feeds.bbci.co.uk/news/world/rss.xml",  # BBC
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",  # NYT
    "https://www.aljazeera.com/xml/rss/all.xml",  # Al Jazeera
    "https://www.reutersagency.com/feed/?best-topics=top-news",  # Reuters
    "https://www.france24.com/en/rss",  # France24
    "https://www.cnn.com/rss/cnn_latest.rss",  # CNN

    # 🌍 Telegram через RSSHub (гарячі події)
    "https://rsshub.app/telegram/channel/liveuamap",  # Liveuamap (Україна / війна)
    "https://rsshub.app/telegram/channel/SouthAsiaIndex",  # Південна Азія, Ізраїль
    "https://rsshub.app/telegram/channel/stratcomcentre",  # StratCom (UA)
    "https://rsshub.app/telegram/channel/IntelPointAlert",  # IntelPoint (терористичні події, стрілянини)
    "https://rsshub.app/telegram/channel/WW3INFO",  # Світова військова ситуація
    "https://rsshub.app/telegram/channel/unian",  # УНІАН
    "https://rsshub.app/telegram/channel/spravdi",  # Справді (UA)
    "https://rsshub.app/telegram/channel/nexta_live",  # NEXTA (Білорусь, регіон)
    "https://rsshub.app/telegram/channel/visegrad24",  # Visegrad24 (Центр. Європа)
    "https://rsshub.app/telegram/channel/guardiannews"  # Guardian через RSSHub
]


def fetch_rss():
    for url in RSS_FEEDS:
        d = feedparser.parse(url)
        for e in d.entries:
            title = e.get("title", "")
            body = e.get("summary",
                         "") + (e["content"][0].value if "content" in e
                                and isinstance(e["content"], list) else "")
            link = e.get("link", "")
            if interesting(title, body):
                send(title, link)


def fetch_trt():
    try:
        soup = BeautifulSoup(
            requests.get("https://trt.global/russian", timeout=15).text,
            "html.parser")
        for a in soup.select("a.card"):
            title = a.get("title") or a.text.strip()
            link = a.get("href")
            if link and not link.startswith("http"):
                link = "https://trt.global" + link
            if interesting(title, ""):
                send(title, link)
    except Exception as e:
        logging.error("TRT error: %s", e)


# ── Автоматичний виклик перевірки ────────
def check_news_and_send():
    logging.info("🔍 Перевірка новин…")
    fetch_newsapi()
    fetch_rss()
    fetch_trt()
    save_seen()
    logging.info("✅ Завершено.")


import pytz

scheduler = BackgroundScheduler(timezone=pytz.UTC)
scheduler.add_job(check_news_and_send, 'interval', minutes=INTERVAL_MIN)
scheduler.start()


# ── Підписка користувачів ────────────────
def handler(update: Update, context: CallbackContext):
    save_chat_id(update.message.chat_id)
    update.message.reply_text("✅ Вас підписано на сповіщення. Дякуємо!")


# ── Запуск ───────────────────────────────
logging.basicConfig(level=logging.INFO)
load_seen()
updater.dispatcher.add_handler(MessageHandler(Filters.all, handler))
updater.start_polling()
updater.idle()
