import os
import logging
import json
import openai
import difflib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CommandHandler, CallbackQueryHandler

# Завантаження GPT ключа та промпта
openai.api_key = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ти — юридичний помічник. Відповідай лише згідно з базою шпори.")

# Завантаження бази шпори з JSON
with open("tdp_answers_full.json", "r", encoding="utf-8") as f:
    answers = json.load(f)

# Список ключів
keys = list(answers.keys())

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Команда /topics
async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(text=keys[i].title(), callback_data=str(i))]
        for i in range(min(30, len(keys)))
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть тему з шпори:", reply_markup=markup)

# Обробка кнопок тем
async def handle_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data)
        key = keys[index]
        data = answers[key]
        reply = f"❓ <b>{data['питання']}</b>\n\n✅ {data['відповідь']}"
        if data["закони"]:
            reply += "\n\n📘 <b>Закон(и):</b> " + "; ".join(data["закони"])
    except (ValueError, IndexError, KeyError):
        reply = "❗ Помилка при обробці кнопки."
    await query.message.reply_text(reply, parse_mode="HTML")

# Обробка вхідного повідомлення
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower().strip()

    # Пошук найближчого ключа у словнику
    best_match = difflib.get_close_matches(user_message, keys, n=1, cutoff=0.5)

    if best_match:
        data = answers[best_match[0]]
        reply = f"❓ <b>{data['питання']}</b>\n\n✅ {data['відповідь']}"
        if data["закони"]:
            reply += "\n\n📘 <b>Закон(и):</b> " + "; ".join(data["закони"])
    else:
        # GPT fallback
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ]
            )
            reply = response.choices[0].message.content
        except Exception as e:
            reply = "🔍 Немає відповіді у шпорі, і GPT не зміг відповісти."

    await update.message.reply_text(reply, parse_mode="HTML")

# Запуск бота
if __name__ == '__main__':
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        raise ValueError("TELEGRAM_TOKEN не встановлений!")

    app = ApplicationBuilder().token(telegram_token).build()
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CallbackQueryHandler(handle_topic_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🟢 Бот запущено. Очікую на питання...")
    app.run_polling()
