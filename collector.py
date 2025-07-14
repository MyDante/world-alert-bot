from telegram import Update, Bot
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
import json, os

TOKEN = "8104448357:AAHoIyZX-_z7sCxRYYWFsfL5jd1WNEhRYgA"
USERS_FILE = "chat_ids.json"

def save_chat_id(chat_id: int):
    ids = []
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            ids = json.load(f)
    if chat_id not in ids:
        ids.append(chat_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(ids, f)

def handler(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    save_chat_id(chat_id)
    update.message.reply_text("✅ Вас підписано на сповіщення. Дякуємо!")

updater = Updater(TOKEN)
updater.dispatcher.add_handler(MessageHandler(Filters.all, handler))
updater.start_polling()
updater.idle()
