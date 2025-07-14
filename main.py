import time, html, requests, logging, urllib.parse, re, feedparser
from bs4 import BeautifulSoup
from telegram import Bot
from langdetect import detect

# ─── Твоє (!) — заміні при потребі ──────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")  # TELEGRAM
NEWSKEY = os.environ.get("NEWSAPI_KEY")  # NewsAPI
MYMEMORY_KEY = os.environ.get("MYMEMORY_KEY")  # MyMemory
INTERVAL = 60 * 60                           # 1 година

# ─── Ключові / негативні слова ──────────────────────────────
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

bot  = Bot(TOKEN)
seen = set()

# ─── Простий переклад через MyMemory ────────────────────────
def translate(text: str, target="uk") -> str:
    if not text:
        return text
    try:
        src = detect(text)
        q   = urllib.parse.quote(text)

        # ▸ НЕ додаємо параметр key
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{target}"

        data = requests.get(url, timeout=10).json()
        return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        logging.error("Translate error: %s", e)
        return text


# ─── Фільтр «цікаво / ні» ───────────────────────────────────
def interesting(title: str, desc: str) -> bool:
    text = f"{title} {desc}".lower()
    if any(w in text for w in NEGATIVE):
        return False
    hits = 0
    for kw in KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            hits += 1
            if hits >= 2:
                return True
    return False

# ─── Надсилання ────────────────────────────────────────────
def send(title: str, link: str):
    if link in seen:
        return
    seen.add(link)
    bot.send_message(
        CHAT_ID,
        f"⚠️ <b>{html.escape(translate(title))}</b>\n🔗 {link}",
        parse_mode="HTML"
    )

# ─── Джерело 1 — NewsAPI ──────────────────────────────────
def fetch_newsapi():
    url = f"https://newsapi.org/v2/everything?q=%2A&pageSize=50&sortBy=publishedAt&apiKey={NEWSKEY}"
    for art in requests.get(url, timeout=15).json().get("articles", []):
        if interesting(art.get("title",""), art.get("description","")):
            send(art.get("title",""), art.get("url",""))

# ─── Джерело 2 — RSS‑стрічки ──────────────────────────────
RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rsshub.app/telegram/channel/liveuamap",
    "https://rsshub.app/telegram/channel/SouthAsiaIndex",
    "https://rsshub.app/telegram/channel/stratcomcentre",
]
def fetch_rss():
    for url in RSS_FEEDS:
        d = feedparser.parse(url)
        for e in d.entries:
            title = e.get("title","")
            body  = e.get("summary","") + (
                e["content"][0].value if "content" in e and isinstance(e["content"], list) else ""
            )
            link  = e.get("link","")
            if interesting(title, body):
                send(title, link)

# ─── Джерело 3 — TRT Global (HTML) ────────────────────────
def fetch_trt():
    soup = BeautifulSoup(
        requests.get("https://trt.global/russian", timeout=15).text,
        "html.parser"
    )
    for a in soup.select("a.card"):
        title = a.get("title") or a.text.strip()
        link  = a.get("href")
        if link and not link.startswith("http"):
            link = "https://trt.global" + link
        if interesting(title, ""):
            send(title, link)

# ─── Цикл ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

while True:
    logging.info("🔍 Перевірка новин…")
    try:
        fetch_newsapi()
        fetch_rss()
        fetch_trt()
    except Exception as e:
        logging.error("⚠️ Error: %s", e)
    logging.info("✅ Готово. Сплю 1 год…")
    time.sleep(INTERVAL)
