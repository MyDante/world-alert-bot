import os
import json
import logging
import time
import html
import re
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
from langdetect import detect
from keep_alive import keep_alive
from apscheduler.schedulers.background import BackgroundScheduler

from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ── Keep-alive (Flask)
keep_alive()

# ── Налаштування
TOKEN = "8104448357:AAHoIyZX-_z7sCxRYYWFsfL5jd1WNEhRYgA"
NEWSKEY = "15e117b2ecad4146a6a7d42400e6c268"
MYMEMORY_KEY = "bf82f06cb760de468651"
INTERVAL_MIN = 30

USERS_FILE = "chat_ids.json"
SEEN_FILE = "seen.json"
seen = set()
bot = Bot(TOKEN)

# ── Підписка користувачів
def load_chat_ids():
    if os.path.exists(USERS_FILE):
        return json.load(open(USERS_FILE, encoding="utf-8"))
    return []

def save_chat_id(chat_id: int):
    ids = load_chat_ids()
    if chat_id not in ids:
        ids.append(chat_id)
        json.dump(ids, open(USERS_FILE, "w", encoding="utf-8"))

# ── Translate
def translate(text: str, target="uk") -> str:
    try:
        src = detect(text)
        q = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{target}&key={MYMEMORY_KEY}"
        return requests.get(url, timeout=10).json().get("responseData", {}).get("translatedText", text)
    except:
        return text

# ── Seen-memory
def load_seen():
    global seen
    if os.path.exists(SEEN_FILE):
        seen = set(json.load(open(SEEN_FILE, encoding="utf-8")))

def save_seen():
    json.dump(list(seen), open(SEEN_FILE, "w", encoding="utf-8"))

# ── Фільтрація
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

def interesting(text: str) -> bool:
    t = text.lower()
    if any(n in t for n in NEGATIVE):
        return False
    hits = sum(1 for kw in KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", t))
    return hits >= 1

# ── Send
def send(title, link):
    if link in seen:
        return
    seen.add(link)
    for cid in load_chat_ids():
        bot.send_message(cid, f"⚠️ <b>{html.escape(translate(title))}</b>\n🔗 {link}", parse_mode="HTML")

# ── RSS
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.reutersagency.com/feed/?best-topics=top-news",
    "https://www.cnn.com/rss/cnn_latest.rss",
    "https://rsshub.app/telegram/channel/liveuamap",
    "https://rsshub.app/telegram/channel/WW3INFO",
]

def fetch():
    for url in RSS_FEEDS:
        d = feedparser.parse(url)
        for e in d.entries:
            title = e.get("title", "") or ""
            txt = (e.get("summary", "") or "") + " " + getattr(e, "content", [{}])[0].get("value", "")
            link = e.get("link", "") or ""
            if link and interesting(title + " " + txt):
                send(title, link)
    save_seen()

# ── Scheduler
def check_news_and_send():
    logging.info("🔍 Checking news…")
    fetch()
    logging.info("✅ Done.")

scheduler = BackgroundScheduler(timezone="UTC")  # ← Додали timezone
scheduler.add_job(check_news_and_send, "interval", minutes=INTERVAL_MIN)
scheduler.start()

# ── Telegram handler
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_id(update.message.chat_id)
    await update.message.reply_text("✅ Підписано!")

# ── Run бот
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_seen()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handler))
    app.run_polling()
