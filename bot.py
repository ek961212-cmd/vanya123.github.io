import json
import os
import datetime
import random
import string
import hashlib
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from telegram.request import HTTPXRequest
import logging

# ========== ТВОЙ ТОКЕН ==========
BOT_TOKEN = "8745261570:AAGG2UHvob2bE86hTh7DRBhAKQ1Piq-YbbU"
ADMIN_IDS = ["6579391458", "8745261570"]  # Твой ID добавлен!
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ
MAX_STORAGE_PER_USER = 500 * 1024 * 1024  # 500 МБ
# ================================

# ========== НАСТРОЙКИ ПРОКСИ ==========
USE_PROXY = True
PROXY_URL = "socks5://109.120.190.5:443"  # Твой прокси
# ====================================

# Состояния
LOGIN, PASSWORD, REG_LOGIN, REG_PASSWORD, REG_CONFIRM, CHANGE_PASSWORD, NEW_PASSWORD, FEEDBACK, SEARCH, SHARE_USER = range(10)

# Файлы
DATA_FILE = 'users_data.json'
ACCOUNTS_FILE = 'accounts.json'
STATS_FILE = 'stats.json'

# Отключаем логи
logging.basicConfig(level=logging.CRITICAL)

# ========== ФУНКЦИИ ЗАГРУЗКИ ==========
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

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'total_users': 0, 'total_files': 0, 'total_size': 0, 'bot_start': str(datetime.datetime.now())}

def save_all(users, accs, stats):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False)
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accs, f, ensure_ascii=False)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False)

users_data = load_data()
accounts = load_accounts()
stats = load_stats()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def gen_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def format_size(size):
    if size < 1024: return f"{size} B"
    elif size < 1024*1024: return f"{size/1024:.1f} KB"
    elif size < 1024*1024*1024: return f"{size/(1024*1024):.1f} MB"
    else: return f"{size/(1024*1024*1024):.1f} GB"

def get_user_total_size(user_id):
    total = 0
    for f in users_data.get(user_id, {}).get('files', {}).values():
        total += f.get('bytes', 0)
    return total

# ========== МЕГА-КЛАВИАТУРЫ ==========
def get_main_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("📁 Мои файлы", callback_data='list_files'),
         InlineKeyboardButton("📊 Статистика", callback_data='stats')],
        [InlineKeyboardButton("📤 Загрузить", callback_data='upload_info'),
         InlineKeyboardButton("📥 Скачать", callback_data='download_info')],
        [InlineKeyboardButton("🔍 Поиск", callback_data='search_menu'),
         InlineKeyboardButton("📂 Папки", callback_data='folders_menu')],
        [InlineKeyboardButton("👤 Аккаунт", callback_data='account_info'),
         InlineKeyboardButton("🔐 Сменить пароль", callback_data='change_pass')],
        [InlineKeyboardButton("📞 Поддержка", callback_data='support'),
         InlineKeyboardButton("📝 Отзыв", callback_data='feedback')],
        [InlineKeyboardButton("📎 Поделиться", callback_data='share_menu'),
         InlineKeyboardButton("🔄 Обновить", callback_data='refresh')],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ АДМИН ПАНЕЛЬ", callback_data='admin_panel')])
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data='help'),
                     InlineKeyboardButton("🚪 Выйти", callback_data='logout')])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')
    ]])

def get_files_keyboard(files, action='get', page=0):
    file_list = list(files.items())
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page
    current_files = file_list[start:end]
    
    keyboard = []
    for name, info in current_files:
        size = info.get('size', '?')
        keyboard.append([
            InlineKeyboardButton(f"📄 {name[:20]} ({size})", callback_data=f"{action}_{name}"),
            InlineKeyboardButton(f"🗑", callback_data=f"del_{name}")
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page-1}"))
    if end < len(file_list):
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДА СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    found_account = None
    for acc in accounts.values():
        if acc.get('telegram_id') == user_id:
            found_account = acc
            break
    
    if found_account:
        context.user_data['current_account'] = found_account
        user_files = users_data.get(found_account['user_id'], {}).get('files', {})
        total_size = get_user_total_size(found_account['user_id'])
        
        await update.message.reply_text(
            f"🌟 **С возвращением, {found_account['username']}!**\n\n"
            f"📁 **Файлов:** {len(user_files)}\n"
            f"💾 **Использовано:** {format_size(total_size)} / {format_size(MAX_STORAGE_PER_USER)}",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id in ADMIN_IDS)
        )
    else:
        await update.message.reply_text(
            "🚀 **МЕГА-ОБЛАКО**\n\n"
            "🔐 Войди или зарегистрируйся:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Войти", callback_data='login'),
                 InlineKeyboardButton("📝 Регистрация", callback_data='register')]
            ])
        )

# ========== ГЛАВНЫЙ ОБРАБОТЧИК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    data = q.data
    
    # Навигация
    if data == 'back_to_menu':
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            await q.edit_message_text(
                f"🌟 **Главное меню**\n\n📁 {len(user_files)} файлов | 💾 {format_size(total_size)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await q.edit_message_text(
                "🚀 **Мега-Облако**",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Войти", callback_data='login'),
                     InlineKeyboardButton("📝 Регистрация", callback_data='register')]
                ])
            )
        return
    
    if data == 'refresh':
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            await q.edit_message_text(
                f"🔄 **Данные обновлены!**\n\n📁 {len(user_files)} файлов | 💾 {format_size(total_size)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        return
    
    # Авторизация
    if data == 'login':
        await q.edit_message_text("🔐 **Введите логин:**", parse_mode='Markdown')
        return LOGIN
    
    if data == 'register':
        await q.edit_message_text("📝 **Придумайте логин** (буквы и цифры, мин 3):", parse_mode='Markdown')
        return REG_LOGIN
    
    # Проверка авторизации
    if 'current_account' not in context.user_data:
        await q.edit_message_text("❌ **Сначала войдите!**", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Войти", callback_data='login')
        ]]))
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
    # Список файлов
    if data == 'list_files':
        files = users_data.get(user_id, {}).get('files', {})
        if not files:
            await q.edit_message_text("📭 **Нет файлов**", reply_markup=get_back_keyboard())
            return
        
        await q.edit_message_text(
            f"📁 **Ваши файлы ({len(files)})**",
            parse_mode='Markdown',
            reply_markup=get_files_keyboard(files, 'get', 0)
        )
    
    elif data.startswith('page_'):
        page = int(data.split('_')[1])
        files = users_data.get(user_id, {}).get('files', {})
        await q.edit_message_reply_markup(reply_markup=get_files_keyboard(files, 'get', page))
    
    elif data.startswith('get_'):
        file_name = data[4:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=files[file_name]['file_id'],
                filename=file_name
            )
            await q.edit_message_text("✅ **Файл отправлен!**", reply_markup=get_back_keyboard())
    
    elif data.startswith('del_'):
        file_name = data[4:]
        if file_name in users_data.get(user_id, {}).get('files', {}):
            del users_data[user_id]['files'][file_name]
            save_all(users_data, accounts, stats)
            await q.edit_message_text(f"✅ **Файл удален:** `{file_name}`", parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # Информация
    elif data == 'upload_info':
        await q.edit_message_text(
            f"📤 **Загрузка файлов**\n\n"
            f"Просто отправь мне любой файл!\n\n"
            f"📦 Макс размер: {format_size(MAX_FILE_SIZE)}\n"
            f"💾 Всего места: {format_size(MAX_STORAGE_PER_USER)}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'download_info':
        await q.edit_message_text(
            "📥 **Скачивание**\n\n"
            "Нажми на файл в списке и он придет тебе!",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'search_menu':
        await q.edit_message_text("🔍 **Введите название для поиска:**", parse_mode='Markdown')
        return SEARCH
    
    elif data == 'stats':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        percent = (total_size / MAX_STORAGE_PER_USER) * 100
        
        await q.edit_message_text(
            f"📊 **Статистика**\n\n"
            f"📁 Файлов: {len(files)}\n"
            f"💾 Места: {format_size(total_size)} / {format_size(MAX_STORAGE_PER_USER)}\n"
            f"📈 Заполнено: {percent:.1f}%",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'account_info':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        
        await q.edit_message_text(
            f"👤 **Мой аккаунт**\n\n"
            f"📝 Логин: `{acc['username']}`\n"
            f"🆔 ID: `{acc['user_id'][:8]}`\n"
            f"📁 Файлов: {len(files)}\n"
            f"💾 Места: {format_size(total_size)}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'support':
        await q.edit_message_text(
            "📞 **Поддержка**\n\n"
            "Разработчик: @error_08081\n"
            "По всем вопросам пишите!",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'feedback':
        await q.edit_message_text("📝 **Напишите ваш отзыв:**", parse_mode='Markdown')
        return FEEDBACK
    
    elif data == 'help':
        await q.edit_message_text(
            "❓ **Помощь**\n\n"
            "📁 Файлы - список файлов\n"
            "📊 Статистика - использование\n"
            "📤 Загрузить - как загружать\n"
            "📥 Скачать - как скачивать\n"
            "🔍 Поиск - найти файл\n"
            "👤 Аккаунт - данные\n"
            "🔐 Сменить пароль\n"
            "📞 Поддержка - связаться\n"
            "📝 Отзыв - написать",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'change_pass':
        await q.edit_message_text("🔐 **Введите старый пароль:**", parse_mode='Markdown')
        return CHANGE_PASSWORD
    
    elif data == 'logout':
        context.user_data.pop('current_account', None)
        await q.edit_message_text(
            "✅ **Вы вышли**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Войти", callback_data='login')]
            ])
        )
    
    # АДМИН ПАНЕЛЬ
    elif data == 'admin_panel' and str(update.effective_user.id) in ADMIN_IDS:
        total_users = len(accounts)
        total_files = sum(len(u.get('files', {})) for u in users_data.values())
        total_size = sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values())
        
        keyboard = [
            [InlineKeyboardButton("👥 Список пользователей", callback_data='admin_users')],
            [InlineKeyboardButton("📊 Общая статистика", callback_data='admin_stats')],
            [InlineKeyboardButton("📁 Все файлы", callback_data='admin_files')],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data='admin_search')],
            [InlineKeyboardButton("🏠 Назад", callback_data='back_to_menu')]
        ]
        
        await q.edit_message_text(
            f"⚙️ **АДМИН ПАНЕЛЬ**\n\n"
            f"👥 Пользователей: {total_users}\n"
            f"📁 Всего файлов: {total_files}\n"
            f"💾 Всего данных: {format_size(total_size)}\n"
            f"🆔 Ваш ID: {update.effective_user.id}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'admin_users' and str(update.effective_user.id) in ADMIN_IDS:
        text = "👥 **Пользователи:**\n\n"
        for i, (uid, acc) in enumerate(list(accounts.items())[:20], 1):
            files_count = len(users_data.get(acc['user_id'], {}).get('files', {}))
            text += f"{i}. **{acc['username']}** - 📁 {files_count}\n"
        await q.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())

# ========== ОБРАБОТЧИКИ ВХОДА/РЕГИСТРАЦИИ ==========
async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'login_user' not in context.user_data:
        context.user_data['login_user'] = text
        await update.message.reply_text("🔑 **Введите пароль:**", parse_mode='Markdown')
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
            save_all(users_data, accounts, stats)
            context.user_data['current_account'] = found
            await update.message.reply_text(
                f"✅ **Добро пожаловать, {found['username']}!**",
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await update.message.reply_text("❌ **Неверный логин или пароль!**")
        return ConversationHandler.END

async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'reg_user' not in context.user_data:
        if len(text) < 3 or not text.isalnum():
            await update.message.reply_text("❌ **Логин должен быть >2 символов и только буквы/цифры**")
            return REG_LOGIN
        
        for acc in accounts.values():
            if acc['username'] == text:
                await update.message.reply_text("❌ **Логин занят!**")
                return REG_LOGIN
        
        context.user_data['reg_user'] = text
        await update.message.reply_text("🔑 **Придумайте пароль** (мин 4 символа):", parse_mode='Markdown')
        return REG_PASSWORD
    
    else:
        if len(text) < 4:
            await update.message.reply_text("❌ **Пароль слишком короткий!**")
            return REG_PASSWORD
        
        user_id = gen_id()
        username = context.user_data['reg_user']
        
        accounts[user_id] = {
            'username': username,
            'password': hash_password(text),
            'user_id': user_id,
            'telegram_id': str(update.effective_user.id),
            'created': str(datetime.datetime.now())[:10]
        }
        users_data[user_id] = {'files': {}}
        stats['total_users'] = len(accounts)
        save_all(users_data, accounts, stats)
        
        context.user_data['current_account'] = accounts[user_id]
        
        await update.message.reply_text(
            f"🎉 **Регистрация успешна!**\n\nЛогин: `{username}`",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
        )
        return ConversationHandler.END

# ========== ОБРАБОТЧИК СМЕНЫ ПАРОЛЯ ==========
async def handle_change_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'old_pass' not in context.user_data:
        acc = context.user_data.get('current_account')
        if acc and acc['password'] == hash_password(text):
            context.user_data['old_pass'] = True
            await update.message.reply_text("✅ **Введите новый пароль:**", parse_mode='Markdown')
            return NEW_PASSWORD
        else:
            await update.message.reply_text("❌ **Неверный пароль!**")
            return ConversationHandler.END
    else:
        if len(text) >= 4:
            acc = context.user_data['current_account']
            acc['password'] = hash_password(text)
            save_all(users_data, accounts, stats)
            await update.message.reply_text("✅ **Пароль изменен!**", reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS))
        else:
            await update.message.reply_text("❌ **Пароль слишком короткий!**")
            return NEW_PASSWORD
        
        context.user_data.pop('old_pass', None)
        return ConversationHandler.END

# ========== ОБРАБОТЧИК ПОИСКА ==========
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text.lower()
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    found = [name for name in files.keys() if search_text in name.lower()]
    
    if found:
        text = f"🔍 **Найдено {len(found)}:**\n\n"
        for name in found[:20]:
            text += f"📄 `{name}`\n"
    else:
        text = f"❌ **Ничего не найдено**"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    return ConversationHandler.END

# ========== ОБРАБОТЧИК ОТЗЫВОВ ==========
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    feedback = update.message.text
    acc = context.user_data.get('current_account', {'username': 'Unknown'})
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📝 **ОТЗЫВ**\n\nОт: {acc.get('username')}\nТекст:\n{feedback}"
            )
        except:
            pass
    
    await update.message.reply_text("✅ **Спасибо за отзыв!**", reply_markup=get_back_keyboard())
    return ConversationHandler.END

# ========== ОБРАБОТЧИК ФАЙЛОВ ==========
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ **Сначала войдите!** /start")
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
    current_size = get_user_total_size(user_id)
    
    if update.message.document:
        file = update.message.document
        file_type = 'document'
        file_name = file.file_name
        file_id = file.file_id
        file_size = file.file_size
    elif update.message.photo:
        file = update.message.photo[-1]
        file_type = 'photo'
        file_name = f"photo_{int(time.time())}.jpg"
        file_id = file.file_id
        file_size = file.file_size
    else:
        await update.message.reply_text("❌ **Неподдерживаемый тип файла**")
        return
    
    if file_size > MAX_FILE_SIZE:
        await update.message.reply_text(f"❌ **Файл слишком большой!** Макс {format_size(MAX_FILE_SIZE)}")
        return
    
    if current_size + file_size > MAX_STORAGE_PER_USER:
        await update.message.reply_text(f"❌ **Недостаточно места!**")
        return
    
    if user_id not in users_data:
        users_data[user_id] = {'files': {}}
    
    if file_name in users_data[user_id]['files']:
        base, ext = os.path.splitext(file_name)
        counter = 1
        while f"{base}_{counter}{ext}" in users_data[user_id]['files']:
            counter += 1
        file_name = f"{base}_{counter}{ext}"
    
    users_data[user_id]['files'][file_name] = {
        'file_id': file_id,
        'size': format_size(file_size),
        'bytes': file_size,
        'type': file_type,
        'date': str(datetime.datetime.now())[:10]
    }
    
    stats['total_files'] = sum(len(u.get('files', {})) for u in users_data.values())
    stats['total_size'] = sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values())
    save_all(users_data, accounts, stats)
    
    await update.message.reply_text(f"✅ **Файл сохранен:** `{file_name}`", parse_mode='Markdown')

# ========== ЗАПУСК ==========
def main():
    if USE_PROXY:
        request = HTTPXRequest(proxy_url=PROXY_URL, connection_pool_size=8)
        app = Application.builder().token(BOT_TOKEN).request(request).build()
        print(f"🌐 Прокси включен: {PROXY_URL}")
    else:
        app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handlers
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
    
    change_pass_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^change_pass$')],
        states={
            CHANGE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_password)],
            NEW_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_password)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^search_menu$')],
        states={SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)]},
        fallbacks=[CommandHandler("start", start)],
    )
    
    feedback_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^feedback$')],
        states={FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)]},
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(login_conv)
    app.add_handler(register_conv)
    app.add_handler(change_pass_conv)
    app.add_handler(search_conv)
    app.add_handler(feedback_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))
    
    print("="*50)
    print("🚀 МЕГА-БОТ ЗАПУЩЕН!")
    print("="*50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"👥 Пользователей: {len(accounts)}")
    print(f"📁 Файлов: {sum(len(u.get('files', {})) for u in users_data.values())}")
    print(f"🌐 Прокси: {'ВКЛ' if USE_PROXY else 'ВЫКЛ'}")
    print("="*50)
    
    app.run_polling()

if __name__ == '__main__':
    try:
        import socks
    except:
        os.system("pip install PySocks")
    
    main()
