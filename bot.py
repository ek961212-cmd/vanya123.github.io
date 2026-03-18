import json
import os
import datetime
import random
import string
import hashlib
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from telegram.request import HTTPXRequest
import logging

# ========== ТВОЙ ТОКЕН ==========
BOT_TOKEN = "8745261570:AAGG2UHvob2bE86hTh7DRBhAKQ1Piq-YbbU"
ADMIN_IDS = ["6579391458", "8745261570"]  # Твой ID
# ================================

# ========== ТВОЙ ПРОКСИ ==========
USE_PROXY = True
PROXY_URL = "socks5://qq.aezailoveyou.ru:443"  # SOCKS5 прокси
# ================================

# Состояния
LOGIN, PASSWORD, REG_LOGIN, REG_PASSWORD = range(4)

# Файлы
DATA_FILE = 'users_data.json'
ACCOUNTS_FILE = 'accounts.json'

# Отключаем логи
logging.basicConfig(level=logging.CRITICAL)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_all(users, accs):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accs, f, ensure_ascii=False)

users_data = load_data()
accounts = load_accounts()

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def gen_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def format_size(size):
    if size < 1024: return f"{size}B"
    elif size < 1024*1024: return f"{size/1024:.1f}KB"
    else: return f"{size/(1024*1024):.1f}MB"

# Клавиатуры
MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📁 Файлы", callback_data='list'),
     InlineKeyboardButton("📊 Стат", callback_data='stats')],
    [InlineKeyboardButton("👤 Аккаунт", callback_data='account'),
     InlineKeyboardButton("🚪 Выйти", callback_data='logout')]
])

BACK_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("◀️ Назад", callback_data='back')
]])

AUTH_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔐 Войти", callback_data='login'),
     InlineKeyboardButton("📝 Регистр", callback_data='register')]
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    
    for acc in accounts.values():
        if acc.get('telegram_id') == uid:
            context.user_data['current_account'] = acc
            files = users_data.get(acc['user_id'], {}).get('files', {})
            await update.message.reply_text(
                f"👋 {acc['username']} | 📁 {len(files)}",
                reply_markup=MAIN_KEYBOARD
            )
            return
    
    await update.message.reply_text("🚀 Облако", reply_markup=AUTH_KEYBOARD)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    data = q.data
    
    if data == 'back':
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            files = users_data.get(acc['user_id'], {}).get('files', {})
            await q.edit_message_text(f"👋 {acc['username']} | 📁 {len(files)}", reply_markup=MAIN_KEYBOARD)
        else:
            await q.edit_message_text("🚀 Облако", reply_markup=AUTH_KEYBOARD)
        return
    
    if data == 'login':
        await q.edit_message_text("🔐 Логин:")
        return LOGIN
    
    if data == 'register':
        await q.edit_message_text("📝 Логин (буквы/цифры):")
        return REG_LOGIN
    
    if 'current_account' not in context.user_data:
        await q.edit_message_text("❌ Нужен вход!", reply_markup=AUTH_KEYBOARD)
        return
    
    acc = context.user_data['current_account']
    uid = acc['user_id']
    
    if data == 'list':
        files = users_data.get(uid, {}).get('files', {})
        if not files:
            await q.edit_message_text("📭 Нет файлов", reply_markup=BACK_KEYBOARD)
            return
        
        text = f"📁 {len(files)}:\n"
        for name in list(files.keys())[:5]:
            text += f"\n📄 {name[:20]}"
        
        btns = []
        for name in list(files.keys())[:5]:
            btns.append([InlineKeyboardButton(f"📥 {name[:10]}", callback_data=f"g_{name}")])
        btns.append([InlineKeyboardButton("◀️ Назад", callback_data='back')])
        
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns))
    
    elif data == 'stats':
        files = users_data.get(uid, {}).get('files', {})
        total_size = sum(f.get('bytes', 0) for f in files.values())
        await q.edit_message_text(
            f"📊 Статистика\n📁 Файлов: {len(files)}\n💾 Места: {format_size(total_size)}",
            reply_markup=BACK_KEYBOARD
        )
    
    elif data == 'account':
        await q.edit_message_text(
            f"👤 Аккаунт\n📝 {acc['username']}\n🆔 {acc['user_id'][:6]}",
            reply_markup=BACK_KEYBOARD
        )
    
    elif data == 'logout':
        context.user_data.pop('current_account', None)
        await q.edit_message_text("✅ Вышел", reply_markup=AUTH_KEYBOARD)
    
    elif data.startswith('g_'):
        name = data[2:]
        files = users_data.get(uid, {}).get('files', {})
        if name in files:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=files[name]['file_id'],
                filename=name
            )
            await q.edit_message_text("✅ Отправлено", reply_markup=BACK_KEYBOARD)

async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'login_user' not in context.user_data:
        context.user_data['login_user'] = text
        await update.message.reply_text("🔑 Пароль:")
        return LOGIN
    else:
        username = context.user_data.pop('login_user')
        password = hash_password(text)
        
        found = None
        for acc in accounts.values():
            if acc['username'] == username and acc['password'] == password:
                found = acc
                break
        
        if found:
            found['telegram_id'] = str(update.effective_user.id)
            save_all(users_data, accounts)
            context.user_data['current_account'] = found
            files = users_data.get(found['user_id'], {}).get('files', {})
            await update.message.reply_text(
                f"✅ {username} | 📁 {len(files)}",
                reply_markup=MAIN_KEYBOARD
            )
        else:
            await update.message.reply_text("❌ Ошибка!", reply_markup=AUTH_KEYBOARD)
        return ConversationHandler.END

async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'reg_user' not in context.user_data:
        if len(text) < 3 or not text.isalnum():
            await update.message.reply_text("❌ Логин: буквы/цифры, мин 3")
            return REG_LOGIN
        
        for acc in accounts.values():
            if acc['username'] == text:
                await update.message.reply_text("❌ Занят!")
                return REG_LOGIN
        
        context.user_data['reg_user'] = text
        await update.message.reply_text("🔑 Пароль (мин 4):")
        return REG_PASSWORD
    else:
        if len(text) < 4:
            await update.message.reply_text("❌ Слишком короткий")
            return REG_PASSWORD
        
        uid = gen_id()
        username = context.user_data['reg_user']
        
        accounts[uid] = {
            'username': username,
            'password': hash_password(text),
            'user_id': uid,
            'telegram_id': str(update.effective_user.id),
            'created': str(datetime.datetime.now())[:10]
        }
        users_data[uid] = {'files': {}}
        save_all(users_data, accounts)
        
        context.user_data['current_account'] = accounts[uid]
        
        await update.message.reply_text(
            f"✅ {username}",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала /start", reply_markup=AUTH_KEYBOARD)
        return
    
    acc = context.user_data['current_account']
    uid = acc['user_id']
    
    if update.message.document:
        f = update.message.document
        name = f.file_name
        fid = f.file_id
        size = f.file_size
    elif update.message.photo:
        f = update.message.photo[-1]
        name = f"photo_{len(users_data.get(uid, {}).get('files', {})) + 1}.jpg"
        fid = f.file_id
        size = f.file_size
    else:
        await update.message.reply_text("❌ Не поддерживается")
        return
    
    if uid not in users_data:
        users_data[uid] = {'files': {}}
    
    users_data[uid]['files'][name] = {
        'file_id': fid,
        'size': format_size(size),
        'bytes': size,
        'date': str(datetime.datetime.now())[:10]
    }
    save_all(users_data, accounts)
    
    await update.message.reply_text(f"✅ {name}")

def main():
    # Создаем request с прокси
    if USE_PROXY:
        try:
            request = HTTPXRequest(
                proxy_url=PROXY_URL,
                connection_pool_size=8,
                connect_timeout=30,
                read_timeout=30
            )
            app = Application.builder().token(BOT_TOKEN).request(request).build()
            print(f"🌐 Прокси включен: {PROXY_URL}")
        except Exception as e:
            print(f"❌ Ошибка прокси: {e}")
            print("🚀 Запускаю без прокси...")
            app = Application.builder().token(BOT_TOKEN).build()
    else:
        app = Application.builder().token(BOT_TOKEN).build()
        print("🌐 Прокси выключен")
    
    login_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^login$')],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    register_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^register$')],
        states={
            REG_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_register)],
            REG_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_register)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(login_conv)
    app.add_handler(register_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    
    print("="*50)
    print("🚀 МЕГА-БОТ ЗАПУЩЕН!")
    print("="*50)
    print(f"👑 Твой ID: 6579391458")
    print(f"👥 Пользователей: {len(accounts)}")
    print(f"📁 Всего файлов: {sum(len(u.get('files', {})) for u in users_data.values())}")
    print(f"🌐 Прокси: {'ВКЛЮЧЕН' if USE_PROXY else 'ВЫКЛЮЧЕН'}")
    print("="*50)
    
    app.run_polling()

if __name__ == '__main__':
    # Устанавливаем библиотеку для прокси
    try:
        import socks
    except:
        os.system("pip install PySocks")
    
    main()
