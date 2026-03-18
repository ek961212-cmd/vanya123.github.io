import json
import os
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ========== ТВОЙ ТОКЕН ==========
BOT_TOKEN = "8745261570:AAGG2UHvob2bE86hTh7DRBhAKQ1Piq-YbbU"
# ================================

# Файл для хранения
DATA_FILE = 'storage.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

users = load_data()

async def start(update, context):
    user_id = str(update.effective_user.id)
    name = update.effective_user.first_name
    
    if user_id not in users:
        users[user_id] = {'name': name, 'files': []}
        save_data(users)
    
    await update.message.reply_text(
        f"✅ Привет, {name}!\n"
        f"Отправь мне любой файл, и я сохраню его.\n"
        f"Для списка файлов напиши /list"
    )

async def get_file(update, context):
    user_id = str(update.effective_user.id)
    
    if user_id not in users:
        await update.message.reply_text("❌ Сначала напиши /start")
        return
    
    if update.message.document:
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name
    elif update.message.photo:
        file = update.message.photo[-1]
        file_id = file.file_id
        file_name = f"photo_{len(users[user_id]['files']) + 1}.jpg"
    else:
        await update.message.reply_text("❌ Пока принимаю только файлы и фото")
        return
    
    users[user_id]['files'].append({
        'name': file_name,
        'file_id': file_id
    })
    save_data(users)
    
    await update.message.reply_text(f"✅ Сохранено: {file_name}")

async def list_files(update, context):
    user_id = str(update.effective_user.id)
    
    if user_id not in users:
        await update.message.reply_text("❌ Сначала напиши /start")
        return
    
    files = users[user_id]['files']
    
    if not files:
        await update.message.reply_text("📭 У тебя пока нет файлов")
        return
    
    text = "📁 Твои файлы:\n\n"
    for f in files:
        text += f"• {f['name']}\n"
    
    await update.message.reply_text(text)

print("🚀 Запускаю бота...")

try:
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, get_file))
    
    print("✅ Бот запущен! Иди в Telegram и напиши /start")
    app.run_polling()
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("🔄 Нажми Ctrl+C и попробуй снова")
