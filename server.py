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
with open("tdp_answers_full_structured.json", "r", encoding="utf-8") as f1, open("tdp_practical_answers.json", "r", encoding="utf-8") as f2 as f:
    answers = json.load(f1)
    practicals = json.load(f2)
    answers.update(practicals)

# Список ключів
keys = list(answers.keys())

# Налаштування логів
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Команда /topics
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

# Команда /practice — показує практичні завдання
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

# Додати підтримку пагінації для кнопок
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
    elif query.data == "practice_prev":
        context.user_data["practice_page"] = max(context.user_data.get("practice_page", 0) - 1, 0)
        await send_practice_page(update, context)
        return

    try:
        index = int(query.data)
        key = keys[index]
        data = answers[key]
        reply = f"❓ <b>{data['питання']}</b>

✅ {data['відповідь']}"
        if data["закони"]:
            reply += "

📘 <b>Закон(и):</b> " + "; ".join(data["закони"])
    except (ValueError, IndexError, KeyError):
        reply = "❗ Помилка при обробці кнопки."
    await query.message.reply_text(reply, parse_mode="HTML")

# Команда /laws — показує закони згруповано
async def laws_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = defaultdict(list)
    for value in answers.values():
        for law in value.get("закони", []):
            if "Конституц" in law:
                categories["Конституція України"].append(law)
            elif "Кодекс" in law:
                categories["Кодекси України"].append(law)
            elif "Закон" in law:
                categories["Закони України"].append(law)
            else:
                categories["Інші"].append(law)

    if categories:
        reply = "📘 <b>Законодавчі джерела, згруповані за типом:</b>\n"
        for group, items in categories.items():
            laws = sorted(set(items))
            reply += f"\n<b>{group}:</b>\n" + "\n".join(f"▪️ {law}" for law in laws) + "\n"
    else:
        reply = "⚠️ У шпорі не виявлено згадок про закони."
    await update.message.reply_text(reply, parse_mode="HTML")

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

# Витягання посилань на закони з GPT-відповіді
def extract_laws_from_text(text):
    pattern = r"ст\.\s?\d+[^.\n]*?(Конституц|Кодекс|Закон)[^.,\n]*"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    unique = sorted(set(matches))
    return unique

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
        # GPT fallback + пошук законів
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ]
            )
            gpt_text = response.choices[0].message.content
            laws = extract_laws_from_text(gpt_text)
            reply = f"✅ {gpt_text}"
            if laws:
                reply += "\n\n📘 <b>Згадано закон(и):</b> " + "; ".join(laws)
        except Exception as e:
            reply = "🔍 Немає відповіді у шпорі, і GPT не зміг відповісти."

    await update.message.reply_text(reply, parse_mode="HTML")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).lower()
    matches = [k for k in keys if query in k.lower()]

    if not matches:
        await update.message.reply_text("❌ Нічого не знайдено.")
        return

    keyboard = [[InlineKeyboardButton(text=m.title(), callback_data=str(keys.index(m)))] for m in matches[:30]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🔎 Знайдено {len(matches)} результатів:", reply_markup=markup)

# Запуск бота
if __name__ == '__main__':
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if not telegram_token:
        raise ValueError("TELEGRAM_TOKEN не встановлений!")

    app = ApplicationBuilder().token(telegram_token).build()
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("laws", laws_command))
    app.add_handler(CommandHandler("practice", practice_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(handle_topic_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🟢 Бот запущено. Очікую на питання...")
    app.run_polling()
