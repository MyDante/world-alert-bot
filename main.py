

# ── 4. Переклад ────────────────────────
def translate(text: str, target="uk") -> str:
    if not text:
        return text
    try:
        src = detect(text)
        q   = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={q}&langpair={src}|{target}&key={MYMEMORY_KEY}"
        data = requests.get(url, timeout=10).json()
        return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        logging.error("Translate error: %s", e)
        return text

# ── 5. Фільтр слів ─────────────────────
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
    hits = sum(1 for kw in KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", text))
    return hits >= 2

# ── 6. Надсилання ──────────────────────
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

# ── 7. Джерела ─────────────────────────
def fetch_newsapi():
    try:
        url = f"https://newsapi.org/v2/everything?q=%2A&pageSize=50&sortBy=publishedAt&apiKey={NEWSKEY}"
        for a in requests.get(url, timeout=15).json().get("articles", []):
            if interesting(a.get("title", ""), a.get("description", "")):
                send(a.get("title", ""), a.get("url", ""))
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
    for url in RSS_FEEDS:
        d = feedparser.parse(url)
        for e in d.entries:
            title = e.get("title", "")
            body  = e.get("summary", "") + (e["content"][0].value if "content" in e and isinstance(e["content"], list) else "")
            link  = e.get("link", "")
            if interesting(title, body):
                send(title, link)

def fetch_trt():
    try:
        soup = BeautifulSoup(requests.get("https://trt.global/russian", timeout=15).text, "html.parser")
        for a in soup.select("a.card"):
            title = a.get("title") or a.text.strip()
            link  = a.get("href")
            if link and not link.startswith("http"):
                link = "https://trt.global" + link
            if interesting(title, ""):
                send(title, link)
    except Exception as e:
        logging.error("TRT error: %s", e)

# ── 8. Основна функція новин ────────────
def check_news_and_send():
    logging.info("🔍 Перевірка новин…")
    fetch_newsapi()
    fetch_rss()
    fetch_trt()
    save_seen()
    logging.info("✅ Завершено.")

# ── 9. Telegram підписка ───────────────
def handler(update: Update, context: CallbackContext):
    save_chat_id(update.message.chat_id)
    update.message.reply_text("✅ Вас підписано на сповіщення. Дякуємо!")

# ── 10. Запуск ─────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_seen()
    updater.dispatcher.add_handler(MessageHandler(Filters.all, handler))
    updater.start_polling()

    # Планувальник
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_news_and_send, 'interval', minutes=INTERVAL_MIN)
    scheduler.start()

    updater.idle()
