import os
import logging
import json
import openai
import difflib
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# Завантаження GPT ключа та промпта
openai.api_key = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ти — юридичний помічник. Відповідай лише згідно з базою шпори.")

# Завантаження бази шпори з JSON
with open("tdp_answers_full.json", "r", encoding="utf-8") as f:
    answers = json.load(f)

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Обробка вхідного повідомлення
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower().strip()

    # Пошук найближчого ключа у словнику
    possible_keys = list(answers.keys())
    best_match = difflib.get_close_matches(user_message, possible_keys, n=1, cutoff=0.5)

    if best_match:
        data = answers[best_match[0]]
        reply = f"\U00002753 *{data['питання']}*\n\n\U00002705 {data['відповідь']}"
        if data["закони"]:
            reply += "\n\n\U0001F4DC Закон(и): " + "; ".join(data["закони"])
    else:
        reply = "\U0001F50D Немає відповіді на це питання у шпорі."

    await update.message.reply_text(reply, parse_mode="Markdown")

# Запуск бота
if __name__ == '__main__':
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        raise ValueError("TELEGRAM_TOKEN не встановлений!")

    app = ApplicationBuilder().token(telegram_token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("\U0001F7E2 Бот запущено. Очікую на питання...")
    app.run_polling()
