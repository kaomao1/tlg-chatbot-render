import os
import logging
import json
import openai
import difflib
import re
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CommandHandler, CallbackQueryHandler

# Завантаження GPT ключа та промпта
openai.api_key = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Ти — юридичний помічник. Відповідай лише згідно з базою шпори.")

# Завантаження бази шпори з JSON
with open("tdp_answers_full_structured.json", "r", encoding="utf-8") as f1, \
     open("tdp_practical_answers.json", "r", encoding="utf-8") as f2:
    answers = json.load(f1)
    practicals = json.load(f2)
    answers.update(practicals)

# Список ключів
keys = list(answers.keys())

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["topics_page"] = 0
    await send_topics_page(update, context)

async def send_topics_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("topics_page", 0)
    topic_keys = [k for k in keys if not k.lower().startswith("практичне завдання №")]
    per_page = 10
    start = page * per_page
    end = start + per_page
    page_keys = topic_keys[start:end]

    keyboard = [[InlineKeyboardButton(text=k.title(), callback_data=str(keys.index(k)))] for k in page_keys]

    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Попередня", callback_data="topics_prev"))
    if end < len(topic_keys):
        nav_buttons.append(InlineKeyboardButton("➡️ Наступна", callback_data="topics_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Оберіть тему з шпори:", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Оберіть тему з шпори:", reply_markup=markup)

async def practice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["practice_page"] = 0
    await send_practice_page(update, context)

async def send_practice_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    page = context.user_data.get("practice_page", 0)
    practice_keys = [k for k in keys if k.lower().startswith("практичне завдання №")]
    per_page = 10
    start = page * per_page
    end = start + per_page
    page_keys = practice_keys[start:end]

    keyboard = [[InlineKeyboardButton(text=k.title(), callback_data=str(keys.index(k)))] for k in page_keys]

    nav_buttons = []
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Попередня", callback_data="practice_prev"))
    if end < len(practice_keys):
        nav_buttons.append(InlineKeyboardButton("➡️ Наступна", callback_data="practice_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Оберіть практичне завдання:", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Оберіть практичне завдання:", reply_markup=markup)

async def handle_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "practice_next":
        context.user_data["practice_page"] = context.user_data.get("practice_page", 0) + 1
        await send_practice_page(update, context)
        return
    elif query.data == "practice_prev":
        context.user_data["practice_page"] = max(context.user_data.get("practice_page", 0) - 1, 0)
        await send_practice_page(update, context)
        return
    elif query.data == "topics_next":
        context.user_data["topics_page"] = context.user_data.get("topics_page", 0) + 1
        await send_topics_page(update, context)
        return
    elif query.data == "topics_prev":
        context.user_data["topics_page"] = max(context.user_data.get("topics_page", 0) - 1, 0)
        await send_topics_page(update, context)
        return

    try:
        index = int(query.data)
        key = keys[index]
        data = answers[key]
        reply = f"""❓ <b>{data['питання']}</b>

✅ {data['відповідь']}"""
        
        if data['закони']:
            reply += f"\n\n📘 <b>Закон(и):</b> {'; '.join(data['закони'])}"
        
        await query.edit_message_text(reply, parse_mode='HTML')
    except (ValueError, IndexError):
        await query.edit_message_text("Помилка: не вдалося знайти відповідь")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    # Пошук найбільш схожого запитання
    matches = difflib.get_close_matches(user_input, keys, n=1, cutoff=0.5)
    
    if matches:
        key = matches[0]
        data = answers[key]
        reply = f"""❓ <b>{data['питання']}</b>

✅ {data['відповідь']}"""
        
        if data['закони']:
            reply += f"\n\n📘 <b>Закон(и):</b> {'; '.join(data['закони'])}"
        
        await update.message.reply_text(reply, parse_mode='HTML')
    else:
        # Якщо не знайдено у базі, використовуємо GPT
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ]
            )
            answer = response.choices[0].message.content
            await update.message.reply_text(answer)
        except Exception as e:
            logger.error(f"Error in GPT request: {e}")
            await update.message.reply_text("Не вдалося знайти відповідь у базі та згенерувати її через GPT.")

def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Додавання обробників
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("practice", practice_command))
    app.add_handler(CallbackQueryHandler(handle_topic_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()
