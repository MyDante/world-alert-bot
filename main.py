import time, html, requests, logging, urllib.parse, re, feedparser, os, json, threading
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
from langdetect import detect
from keep_alive import keep_alive

# ─── Keep-alive для Render/Replit ────────────────────────────
keep_alive()

# ─── Ваші токени (з .env / Dashboard) ────────────────────────
TOKEN         = os.environ.get("BOT_TOKEN")          # TELEGRAM
NEWSKEY       = os.environ.get("NEWSAPI_KEY")        # NewsAPI
MYMEMORY_KEY  = os.environ.get("MYMEMORY_KEY")       # MyMemory
INTERVAL_H    = 1          # для APScheduler (години)
INTERVAL_SEC  = 3600       # для time.sleep()   (секунди)

# ─── Файли для стану ─────────────────────────────────────────
USERS_FILE = "chat_ids.json"
SEEN_FILE  = "seen.txt"
seen: set[str] = set()

# ─── Telegram-бот ────────────────────────────────────────────
bot      = Bot(TOKEN)
updater  = Updater(TOKEN)

# ─── Допоміжні ф-ції збереження стану ────────────────────────
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

# ─── Переклад ────────────────────────────────────────────────
def translate(text: str, target="uk") -> str:
    if not text: return text
    try:
        src = detect(text)
        q   = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{target}&key={MYMEMORY_KEY}"
        data = requests.get(url, timeout=10).json()
        return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        logging.error("Translate error: %s", e)
        return text

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

def interesting(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    if any(neg in text for neg in NEGATIVE):
        return False
    hits = sum(1 for kw in KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", text))
    return hits >= 2

# ─── Надсилання ──────────────────────────────────────────────
def send(title: str, link: str):
    if link in seen: return
    seen.add(link)
    msg = f"⚠️ <b>{html.escape(translate(title))}</b>\n🔗 {link}"
    for cid in load_chat_ids():
        try:
            bot.send_message(cid, msg, parse_mode="HTML")
        except Exception as e:
            logging.error("Send error: %s", e)

# ─── Завантаження джерел ─────────────────────────────────────
def fetch_newsapi():
    try:
        url = f"https://newsapi.org/v2/everything?q=%2A&pageSize=50&sortBy=publishedAt&apiKey={NEWSKEY}"
        for a in requests.get(url, timeout=15).json().get("articles", []):
            if interesting(a.get("title",""), a.get("description","")):
                send(a.get("title",""), a.get("url",""))
    except Exception as e:
        logging.error("NewsAPI error: %s", e)

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rsshub.app/telegram/channel/liveuamap",
    "https://rsshub.app/telegram/channel/SouthAsiaIndex",
    "https://rsshub.app/telegram/channel/stratcomcentre",
]

def fetch_rss():
    for u in RSS_FEEDS:
        d = feedparser.parse(u)
        for e in d.entries:
            title = e.get("title","")
            body  = (e.get("summary","") +
                     (e["content"][0].value if "content" in e and isinstance(e["content"], list) else ""))
            link  = e.get("link","")
            if interesting(title, body): send(title, link)

def fetch_trt():
    try:
        soup = BeautifulSoup(requests.get("https://trt.global/russian", timeout=15).text, "html.parser")
        for a in soup.select("a.card"):
            title = a.get("title") or a.text.strip()
            link  = a.get("href")
            if link and not link.startswith("http"):
                link = "https://trt.global" + link
            if interesting(title,""): send(title, link)
    except Exception as e:
        logging.error("TRT error: %s", e)

# ─── Планувальник (APS) ─────────────────────────────────────
def check_news_and_send():
    logging.info("🔍 Перевірка новин…")
    fetch_newsapi(); fetch_rss(); fetch_trt(); save_seen()
    logging.info("✅ Завершено.")

scheduler = BackgroundScheduler()
scheduler.add_job(check_news_and_send, 'interval', hours=INTERVAL_H)
scheduler.start()

# ─── Telegram-хендлер підписок ───────────────────────────────
def handler(update: Update, context: CallbackContext):
    save_chat_id(update.message.chat_id)
    update.message.reply_text("✅ Вас підписано на сповіщення. Дякуємо!")

updater.dispatcher.add_handler(MessageHandler(Filters.all, handler))

# ─── Запуск ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
load_seen()
check_news_and_send()               # перша перевірка одразу
updater.start_polling()
updater.idle()
