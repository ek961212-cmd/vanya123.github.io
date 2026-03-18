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
import logging

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8745261570:AAGG2UHvob2bE86hTh7DRBhAKQ1Piq-YbbU"
ADMIN_IDS = ["8745261570", "123456789"]  # Добавь сюда ID админов
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ
MAX_STORAGE_PER_USER = 500 * 1024 * 1024  # 500 МБ
# ================================

# Состояния для разговоров
LOGIN, PASSWORD, REG_LOGIN, REG_PASSWORD, REG_CONFIRM, CHANGE_PASSWORD, NEW_PASSWORD, FEEDBACK, SEARCH, SHARE_USER = range(10)

# Файлы для хранения данных
DATA_FILE = 'users_data.json'
ACCOUNTS_FILE = 'accounts.json'
STATS_FILE = 'stats.json'

# Отключаем логирование (для скорости)
logging.basicConfig(level=logging.CRITICAL)

# ========== ФУНКЦИИ ЗАГРУЗКИ/СОХРАНЕНИЯ ==========
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
        json.dump(users, f)
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accs, f)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f)

# Загружаем данные
users_data = load_data()
accounts = load_accounts()
stats = load_stats()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def gen_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size/(1024*1024):.1f} MB"
    else:
        return f"{size/(1024*1024*1024):.1f} GB"

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
        [InlineKeyboardButton("🔍 Поиск файлов", callback_data='search_menu'),
         InlineKeyboardButton("📂 Папки", callback_data='folders_menu')],
        [InlineKeyboardButton("👤 Мой аккаунт", callback_data='account_info'),
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
        InlineKeyboardButton("◀️ Назад в меню", callback_data='back_to_menu')
    ]])

def get_files_keyboard(files, action='get', page=0):
    """Клавиатура со списком файлов (с пагинацией)"""
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
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{page-1}"))
    if end < len(file_list):
        nav_buttons.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

def get_folders_keyboard(user_id):
    """Клавиатура с папками"""
    folders = users_data.get(user_id, {}).get('folders', {})
    keyboard = []
    
    if folders:
        for folder in folders.keys():
            keyboard.append([InlineKeyboardButton(f"📁 {folder}", callback_data=f"folder_{folder}")])
    
    keyboard.append([InlineKeyboardButton("➕ Создать папку", callback_data='create_folder')])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

def get_share_keyboard():
    """Клавиатура для шаринга"""
    keyboard = [
        [InlineKeyboardButton("📤 Поделиться файлом", callback_data='share_file')],
        [InlineKeyboardButton("📥 Получить файл", callback_data='receive_file')],
        [InlineKeyboardButton("📋 Мои общие ссылки", callback_data='my_shares')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДА СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "NoUsername"
    first_name = update.effective_user.first_name or "User"
    
    # Проверяем есть ли аккаунт
    found_account = None
    for acc in accounts.values():
        if acc.get('telegram_id') == user_id:
            found_account = acc
            break
    
    if found_account:
        context.user_data['current_account'] = found_account
        user_files = users_data.get(found_account['user_id'], {}).get('files', {})
        total_size = get_user_total_size(found_account['user_id'])
        
        welcome_text = (
            f"🌟 **С возвращением, {found_account['username']}!**\n\n"
            f"📁 **Файлов:** {len(user_files)}\n"
            f"💾 **Использовано:** {format_size(total_size)} / {format_size(MAX_STORAGE_PER_USER)}\n"
            f"📅 **Аккаунт создан:** {found_account.get('created', 'неизв')}\n"
        )
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id in ADMIN_IDS)
        )
    else:
        # Приветствие для новых
        await update.message.reply_text(
            "🚀 **ДОБРО ПОЖАЛОВАТЬ В МЕГА-ОБЛАКО!**\n\n"
            "✨ **Что я умею:**\n"
            "✅ Хранить файлы (до 500 МБ)\n"
            "✅ Создавать папки\n"
            "✅ Делиться файлами\n"
            "✅ Искать по названию\n"
            "✅ Статистика использования\n\n"
            "🔐 **Для начала войди или зарегистрируйся:**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Войти", callback_data='login'),
                 InlineKeyboardButton("📝 Регистрация", callback_data='register')],
                [InlineKeyboardButton("ℹ️ О боте", callback_data='about')]
            ])
        )

# ========== ГЛАВНЫЙ ОБРАБОТЧИК КНОПОК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # ===== НАВИГАЦИЯ =====
    if data == 'back_to_menu':
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            await query.edit_message_text(
                f"🌟 **Главное меню**\n\n📁 {len(user_files)} файлов | 💾 {format_size(total_size)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await query.edit_message_text(
                "🚀 **Мега-Облако**\n\nВыбери действие:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Войти", callback_data='login'),
                     InlineKeyboardButton("📝 Регистрация", callback_data='register')]
                ])
            )
        return
    
    if data == 'refresh':
        await query.edit_message_text("🔄 Обновляю данные...")
        # Просто возвращаем в меню с обновленными данными
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            await query.edit_message_text(
                f"🌟 **Данные обновлены!**\n\n📁 {len(user_files)} файлов | 💾 {format_size(total_size)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        return
    
    # ===== АВТОРИЗАЦИЯ =====
    if data == 'login':
        await query.edit_message_text("🔐 **Введите ваш логин:**", parse_mode='Markdown')
        return LOGIN
    
    if data == 'register':
        await query.edit_message_text(
            "📝 **Регистрация**\n\n"
            "Придумайте логин (только буквы и цифры, минимум 3 символа):",
            parse_mode='Markdown'
        )
        return REG_LOGIN
    
    if data == 'about':
        await query.edit_message_text(
            "ℹ️ **О боте**\n\n"
            "**Версия:** 5.0 МЕГА-УЛЬТРА\n"
            "**Разработчик:** @error_08081\n"
            "**Создан:** 2024\n\n"
            "**Функции:**\n"
            "✅ Загрузка файлов\n"
            "✅ Папки\n"
            "✅ Поиск\n"
            "✅ Шеринг\n"
            "✅ Статистика\n"
            "✅ Админ панель\n\n"
            "**Лимиты:**\n"
            f"📦 Макс файл: {format_size(MAX_FILE_SIZE)}\n"
            f"💾 Всего места: {format_size(MAX_STORAGE_PER_USER)}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
        return
    
    # ===== ПРОВЕРКА АВТОРИЗАЦИИ =====
    if 'current_account' not in context.user_data:
        await query.edit_message_text(
            "❌ **Сначала нужно войти в аккаунт!**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Войти", callback_data='login')]
            ])
        )
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
    # ===== УПРАВЛЕНИЕ ФАЙЛАМИ =====
    if data == 'list_files':
        files = users_data.get(user_id, {}).get('files', {})
        if not files:
            await query.edit_message_text(
                "📭 **У вас пока нет файлов**\n\nОтправьте мне любой файл, чтобы начать!",
                parse_mode='Markdown',
                reply_markup=get_back_keyboard()
            )
            return
        
        total_size = get_user_total_size(user_id)
        await query.edit_message_text(
            f"📁 **Ваши файлы ({len(files)})**\n"
            f"💾 **Всего:** {format_size(total_size)}",
            parse_mode='Markdown',
            reply_markup=get_files_keyboard(files, 'get', 0)
        )
    
    elif data.startswith('page_'):
        page = int(data.split('_')[1])
        files = users_data.get(user_id, {}).get('files', {})
        await query.edit_message_reply_markup(
            reply_markup=get_files_keyboard(files, 'get', page)
        )
    
    elif data.startswith('get_'):
        file_name = data[4:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            try:
                await context.bot.send_document(
                    chat_id=update.effective_user.id,
                    document=files[file_name]['file_id'],
                    filename=file_name,
                    caption=f"📥 **{file_name}**\nРазмер: {files[file_name]['size']}"
                )
                await query.edit_message_text(
                    "✅ **Файл отправлен!**",
                    reply_markup=get_back_keyboard()
                )
            except Exception as e:
                await query.edit_message_text(
                    f"❌ **Ошибка при отправке:** {str(e)}",
                    reply_markup=get_back_keyboard()
                )
    
    elif data.startswith('del_'):
        file_name = data[4:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            del users_data[user_id]['files'][file_name]
            save_all(users_data, accounts, stats)
            await query.edit_message_text(
                f"✅ **Файл удален:** `{file_name}`",
                parse_mode='Markdown',
                reply_markup=get_back_keyboard()
            )
    
    # ===== ИНФОРМАЦИЯ =====
    elif data == 'upload_info':
        await query.edit_message_text(
            "📤 **Как загрузить файл:**\n\n"
            "1️⃣ Просто отправьте мне **любой файл**\n"
            "2️⃣ Я автоматически сохраню его\n"
            "3️⃣ Можно загружать несколько файлов подряд\n\n"
            "✅ **Поддерживаются:**\n"
            "• 📷 Фото (JPG, PNG, GIF)\n"
            "• 📄 Документы (PDF, DOC, TXT)\n"
            "• 🎵 Музыка (MP3)\n"
            "• 🎬 Видео (MP4)\n"
            "• 📦 Архивы (ZIP, RAR)\n\n"
            f"⚠️ **Лимиты:**\n"
            f"• Макс размер файла: {format_size(MAX_FILE_SIZE)}\n"
            f"• Всего места: {format_size(MAX_STORAGE_PER_USER)}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'download_info':
        await query.edit_message_text(
            "📥 **Как скачать файл:**\n\n"
            "**Способ 1:** Через меню\n"
            "1️⃣ Нажми «Мои файлы»\n"
            "2️⃣ Выбери файл\n"
            "3️⃣ Нажми на кнопку с именем\n\n"
            "**Способ 2:** Командой\n"
            "`/get название_файла`\n\n"
            "**Способ 3:** Поиск\n"
            "Найди файл через поиск и скачай",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'search_menu':
        await query.edit_message_text(
            "🔍 **Поиск файлов**\n\n"
            "Введите название файла (или часть названия):",
            parse_mode='Markdown'
        )
        return SEARCH
    
    elif data == 'folders_menu':
        await query.edit_message_text(
            "📂 **Управление папками**",
            reply_markup=get_folders_keyboard(user_id)
        )
    
    elif data == 'create_folder':
        await query.edit_message_text(
            "📁 **Введите название новой папки:**",
            parse_mode='Markdown'
        )
        return 100  # специальное состояние для создания папки
    
    elif data.startswith('folder_'):
        folder_name = data[7:]
        # Показываем файлы в папке (если реализовано)
        await query.edit_message_text(
            f"📁 **Папка: {folder_name}**\n\nФункция в разработке...",
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'account_info':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        folders = users_data.get(user_id, {}).get('folders', {})
        
        await query.edit_message_text(
            f"👤 **Мой аккаунт**\n\n"
            f"📝 **Логин:** `{acc['username']}`\n"
            f"🆔 **ID:** `{acc['user_id']}`\n"
            f"📅 **Создан:** {acc.get('created', 'неизв')}\n"
            f"📁 **Файлов:** {len(files)}\n"
            f"📂 **Папок:** {len(folders)}\n"
            f"💾 **Использовано:** {format_size(total_size)} / {format_size(MAX_STORAGE_PER_USER)}\n"
            f"📊 **Свободно:** {format_size(MAX_STORAGE_PER_USER - total_size)}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'stats':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        
        # Считаем по типам
        types = {'photo': 0, 'document': 0, 'video': 0, 'audio': 0, 'other': 0}
        for f in files.values():
            f_type = f.get('type', 'other')
            types[f_type] = types.get(f_type, 0) + 1
        
        percent = (total_size / MAX_STORAGE_PER_USER) * 100
        
        await query.edit_message_text(
            f"📊 **Детальная статистика**\n\n"
            f"📁 **Всего файлов:** {len(files)}\n"
            f"💾 **Всего места:** {format_size(total_size)}\n"
            f"📊 **Заполнено:** {percent:.1f}%\n\n"
            f"📷 **Фото:** {types['photo']}\n"
            f"📄 **Документы:** {types['document']}\n"
            f"🎬 **Видео:** {types['video']}\n"
            f"🎵 **Аудио:** {types['audio']}\n"
            f"📦 **Другое:** {types['other']}",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'support':
        await query.edit_message_text(
            "📞 **Поддержка**\n\n"
            "👤 **Разработчик:** @error_08081\n"
            "📧 **Email:** support@megacloud.ru\n"
            "⏰ **Время работы:** 24/7\n\n"
            "По всем вопросам обращайтесь к разработчику!",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'feedback':
        await query.edit_message_text(
            "📝 **Отзыв и предложения**\n\n"
            "Напишите ваш отзыв, пожелания или сообщите об ошибке:",
            parse_mode='Markdown'
        )
        return FEEDBACK
    
    elif data == 'share_menu':
        await query.edit_message_text(
            "📎 **Поделиться файлами**",
            reply_markup=get_share_keyboard()
        )
    
    elif data == 'share_file':
        files = users_data.get(user_id, {}).get('files', {})
        if not files:
            await query.edit_message_text(
                "📭 **Нет файлов для шаринга**",
                reply_markup=get_back_keyboard()
            )
            return
        
        await query.edit_message_text(
            "📤 **Выберите файл для публикации:**",
            reply_markup=get_files_keyboard(files, 'share', 0)
        )
    
    elif data.startswith('share_'):
        file_name = data[6:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            # Генерируем ссылку
            share_id = gen_id()
            if 'shares' not in users_data[user_id]:
                users_data[user_id]['shares'] = {}
            users_data[user_id]['shares'][share_id] = {
                'file_name': file_name,
                'file_id': files[file_name]['file_id'],
                'created': str(datetime.datetime.now()),
                'uses': 0
            }
            save_all(users_data, accounts, stats)
            
            share_link = f"https://t.me/{(await context.bot.get_me()).username}?start=share_{share_id}"
            
            await query.edit_message_text(
                f"✅ **Ссылка создана!**\n\n"
                f"📄 **Файл:** {file_name}\n"
                f"🔗 **Ссылка:**\n`{share_link}`\n\n"
                f"Отправьте эту ссылку другу!",
                parse_mode='Markdown',
                reply_markup=get_back_keyboard()
            )
    
    elif data == 'receive_file':
        await query.edit_message_text(
            "📥 **Введите код получения или ссылку:**",
            parse_mode='Markdown'
        )
        return SHARE_USER
    
    elif data == 'my_shares':
        shares = users_data.get(user_id, {}).get('shares', {})
        if not shares:
            await query.edit_message_text(
                "📭 **У вас нет активных ссылок**",
                reply_markup=get_back_keyboard()
            )
            return
        
        text = "📋 **Ваши общие ссылки:**\n\n"
        for sid, sinfo in shares.items():
            text += f"📄 {sinfo['file_name']} (использований: {sinfo['uses']})\n"
        
        await query.edit_message_text(text, reply_markup=get_back_keyboard())
    
    elif data == 'help':
        await query.edit_message_text(
            "❓ **Справка по командам**\n\n"
            "**Основные кнопки:**\n"
            "📁 Мои файлы - список файлов\n"
            "📊 Статистика - использование места\n"
            "📤 Загрузить - как загружать\n"
            "📥 Скачать - как скачивать\n"
            "🔍 Поиск - найти файл\n"
            "📂 Папки - создать/открыть папку\n"
            "👤 Аккаунт - информация\n"
            "🔐 Сменить пароль - изменить пароль\n"
            "📞 Поддержка - связаться\n"
            "📝 Отзыв - написать отзыв\n"
            "📎 Поделиться - поделиться файлом\n\n"
            "**Команды:**\n"
            "/start - главное меню\n"
            "/list - список файлов\n"
            "/get имя - скачать файл\n"
            "/del имя - удалить файл\n"
            "/search текст - поиск\n"
            "/stats - статистика\n"
            "/account - мой аккаунт\n"
            "/logout - выйти",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
    
    elif data == 'change_pass':
        await query.edit_message_text(
            "🔐 **Смена пароля**\n\n"
            "Введите **старый пароль**:",
            parse_mode='Markdown'
        )
        return CHANGE_PASSWORD
    
    elif data == 'logout':
        username = acc['username']
        context.user_data.pop('current_account', None)
        await query.edit_message_text(
            f"👋 **До свидания, {username}!**\n\n"
            "Чтобы войти снова, нажмите /start",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 Войти", callback_data='login')]
            ])
        )
    
    # ===== АДМИН ПАНЕЛЬ =====
    elif data == 'admin_panel' and str(update.effective_user.id) in ADMIN_IDS:
        total_users = len(accounts)
        total_files = sum(len(u.get('files', {})) for u in users_data.values())
        total_size = sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values())
        
        uptime = datetime.datetime.now() - datetime.datetime.fromisoformat(stats.get('bot_start', str(datetime.datetime.now())))
        hours = uptime.total_seconds() / 3600
        
        keyboard = [
            [InlineKeyboardButton("👥 Список пользователей", callback_data='admin_users')],
            [InlineKeyboardButton("📊 Полная статистика", callback_data='admin_full_stats')],
            [InlineKeyboardButton("📁 Все файлы", callback_data='admin_all_files')],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data='admin_search')],
            [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast')],
            [InlineKeyboardButton("⚙️ Настройки", callback_data='admin_settings')],
            [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')]
        ]
        
        await query.edit_message_text(
            f"⚙️ **АДМИН ПАНЕЛЬ**\n\n"
            f"👥 **Пользователей:** {total_users}\n"
            f"📁 **Всего файлов:** {total_files}\n"
            f"💾 **Всего данных:** {format_size(total_size)}\n"
            f"⏰ **Аптайм:** {hours:.1f} ч\n"
            f"🆔 **Ваш ID:** {update.effective_user.id}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == 'admin_users' and str(update.effective_user.id) in ADMIN_IDS:
        text = "👥 **Список пользователей:**\n\n"
        for i, (uid, acc) in enumerate(list(accounts.items())[:20], 1):
            files_count = len(users_data.get(acc['user_id'], {}).get('files', {}))
            total_size = get_user_total_size(acc['user_id'])
            text += f"{i}. **{acc['username']}**\n"
            text += f"   📁 {files_count} | 💾 {format_size(total_size)}\n"
            text += f"   🆔 `{acc['user_id'][:8]}`\n\n"
        
        if len(accounts) > 20:
            text += f"... и еще {len(accounts) - 20} пользователей"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())

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
            found['last_login'] = str(datetime.datetime.now())
            save_all(users_data, accounts, stats)
            context.user_data['current_account'] = found
            
            files = users_data.get(found['user_id'], {}).get('files', {})
            total_size = get_user_total_size(found['user_id'])
            
            await update.message.reply_text(
                f"✅ **Успешный вход!**\n\n"
                f"👋 **С возвращением, {found['username']}!**\n"
                f"📁 **Файлов:** {len(files)}\n"
                f"💾 **Использовано:** {format_size(total_size)}",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await update.message.reply_text(
                "❌ **Неверный логин или пароль!**\n\nПопробуйте еще раз /start",
                parse_mode='Markdown'
            )
        return ConversationHandler.END

async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'reg_user' not in context.user_data:
        if len(text) < 3 or not text.isalnum():
            await update.message.reply_text(
                "❌ **Ошибка!**\n\n"
                "Логин должен быть:\n"
                "• минимум 3 символа\n"
                "• только буквы и цифры\n\n"
                "Попробуйте еще:",
                parse_mode='Markdown'
            )
            return REG_LOGIN
        
        for acc in accounts.values():
            if acc['username'] == text:
                await update.message.reply_text(
                    "❌ **Этот логин уже занят!**\n\nПридумайте другой:",
                    parse_mode='Markdown'
                )
                return REG_LOGIN
        
        context.user_data['reg_user'] = text
        await update.message.reply_text(
            "✅ **Отлично!**\n\n"
            "Теперь придумайте **пароль** (минимум 4 символа):",
            parse_mode='Markdown'
        )
        return REG_PASSWORD
    
    else:
        if len(text) < 4:
            await update.message.reply_text(
                "❌ **Пароль слишком короткий!**\n\n"
                "Минимум 4 символа. Попробуйте еще:",
                parse_mode='Markdown'
            )
            return REG_PASSWORD
        
        user_id = gen_id()
        username = context.user_data['reg_user']
        
        accounts[user_id] = {
            'username': username,
            'password': hash_password(text),
            'user_id': user_id,
            'telegram_id': str(update.effective_user.id),
            'created': str(datetime.datetime.now())[:10],
            'last_login': str(datetime.datetime.now())
        }
        users_data[user_id] = {'files': {}, 'folders': {}}
        stats['total_users'] = len(accounts)
        save_all(users_data, accounts, stats)
        
        context.user_data['current_account'] = accounts[user_id]
        
        await update.message.reply_text(
            f"🎉 **Регистрация успешна!**\n\n"
            f"👤 **Логин:** `{username}`\n"
            f"🆔 **ID:** `{user_id}`\n\n"
            f"📁 **500 МБ бесплатно!**\n"
            f"Теперь вы можете загружать файлы!",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
        )
        return ConversationHandler.END

# ========== СМЕНА ПАРОЛЯ ==========
async def handle_change_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'old_pass' not in context.user_data:
        acc = context.user_data.get('current_account')
        if acc and acc['password'] == hash_password(text):
            context.user_data['old_pass'] = True
            await update.message.reply_text(
                "✅ **Старый пароль принят!**\n\n"
                "Теперь введите **новый пароль**:",
                parse_mode='Markdown'
            )
            return NEW_PASSWORD
        else:
            await update.message.reply_text(
                "❌ **Неверный пароль!**\n\nПопробуйте еще раз /start",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
    
    else:
        if len(text) >= 4:
            acc = context.user_data['current_account']
            acc['password'] = hash_password(text)
            save_all(users_data, accounts, stats)
            
            await update.message.reply_text(
                "✅ **Пароль успешно изменен!**",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await update.message.reply_text(
                "❌ **Пароль слишком короткий!**\n\nМинимум 4 символа. Попробуйте еще:",
                parse_mode='Markdown'
            )
            return NEW_PASSWORD
        
        context.user_data.pop('old_pass', None)
        return ConversationHandler.END

# ========== ОБРАБОТЧИК ПОИСКА ==========
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_text = update.message.text.lower()
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    found = []
    for name in files.keys():
        if search_text in name.lower():
            found.append(name)
    
    if found:
        text = f"🔍 **Найдено {len(found)} файлов:**\n\n"
        for name in found[:20]:
            text += f"📄 `{name}`\n"
        
        if len(found) > 20:
            text += f"\n... и еще {len(found) - 20} файлов"
    else:
        text = f"❌ **Ничего не найдено по запросу** `{search_text}`"
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    return ConversationHandler.END

# ========== ОБРАБОТЧИК ОТЗЫВОВ ==========
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    feedback = update.message.text
    user_id = str(update.effective_user.id)
    acc = context.user_data.get('current_account', {'username': 'Unknown'})
    
    # Отправляем всем админам
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📝 **НОВЫЙ ОТЗЫВ!**\n\n"
                     f"👤 От: {acc.get('username', 'Unknown')}\n"
                     f"🆔 Telegram: `{user_id}`\n"
                     f"💬 Текст:\n{feedback}",
                parse_mode='Markdown'
            )
        except:
            pass
    
    await update.message.reply_text(
        "✅ **Спасибо за отзыв!**\n\n"
        "Я передал его разработчику.",
        parse_mode='Markdown',
        reply_markup=get_back_keyboard()
    )
    return ConversationHandler.END

# ========== ОБРАБОТЧИК ПОЛУЧЕНИЯ ФАЙЛОВ ==========
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text(
            "❌ **Сначала войдите в аккаунт!**\n\n/start",
            parse_mode='Markdown'
        )
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
    # Проверяем место
    current_size = get_user_total_size(user_id)
    
    # Определяем тип файла
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
    elif update.message.video:
        file = update.message.video
        file_type = 'video'
        file_name = file.file_name or f"video_{int(time.time())}.mp4"
        file_id = file.file_id
        file_size = file.file_size
    elif update.message.audio:
        file = update.message.audio
        file_type = 'audio'
        file_name = file.file_name or f"audio_{int(time.time())}.mp3"
        file_id = file.file_id
        file_size = file.file_size
    else:
        await update.message.reply_text(
            "❌ **Неподдерживаемый тип файла!**\n\n"
            "Поддерживаются: документы, фото, видео, аудио",
            parse_mode='Markdown'
        )
        return
    
    # Проверка размера
    if file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ **Файл слишком большой!**\n\n"
            f"Максимальный размер: {format_size(MAX_FILE_SIZE)}",
            parse_mode='Markdown'
        )
        return
    
    # Проверка свободного места
    if current_size + file_size > MAX_STORAGE_PER_USER:
        await update.message.reply_text(
            f"❌ **Недостаточно места!**\n\n"
            f"Свободно: {format_size(MAX_STORAGE_PER_USER - current_size)}\n"
            f"Нужно: {format_size(file_size)}",
            parse_mode='Markdown'
        )
        return
    
    # Создаем запись если нет
    if user_id not in users_data:
        users_data[user_id] = {'files': {}, 'folders': {}}
    
    # Проверка дубликатов
    if file_name in users_data[user_id]['files']:
        base, ext = os.path.splitext(file_name)
        counter = 1
        while f"{base}_{counter}{ext}" in users_data[user_id]['files']:
            counter += 1
        file_name = f"{base}_{counter}{ext}"
    
    # Сохраняем
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
    
    # Клавиатура после загрузки
    keyboard = [
        [InlineKeyboardButton("📁 Мои файлы", callback_data='list_files'),
         InlineKeyboardButton("📤 Ещё", callback_data='upload_info')],
        [InlineKeyboardButton("🏠 Главное меню", callback_data='back_to_menu')]
    ]
    
    await update.message.reply_text(
        f"✅ **Файл сохранен!**\n\n"
        f"📄 **Имя:** `{file_name}`\n"
        f"💾 **Размер:** {format_size(file_size)}\n"
        f"📅 **Дата:** {datetime.datetime.now().strftime('%d.%m.%Y')}\n"
        f"📁 **Всего файлов:** {len(users_data[user_id]['files'])}\n"
        f"💽 **Свободно:** {format_size(MAX_STORAGE_PER_USER - current_size - file_size)}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== КОМАНДЫ ==========
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    if not files:
        await update.message.reply_text("📭 Нет файлов")
        return
    
    text = "📁 **Файлы:**\n\n"
    for name, info in list(files.items())[:20]:
        text += f"📄 `{name}` ({info['size']})\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Напишите: /get имя_файла")
        return
    
    acc = context.user_data['current_account']
    file_name = ' '.join(context.args)
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    if file_name in files:
        await update.message.reply_document(
            document=files[file_name]['file_id'],
            filename=file_name,
            caption=f"📥 {file_name}"
        )
    else:
        await update.message.reply_text(f"❌ Файл не найден")

async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Напишите: /del имя_файла")
        return
    
    acc = context.user_data['current_account']
    file_name = ' '.join(context.args)
    
    if acc['user_id'] in users_data:
        if file_name in users_data[acc['user_id']]['files']:
            del users_data[acc['user_id']]['files'][file_name]
            save_all(users_data, accounts, stats)
            await update.message.reply_text(f"✅ Файл удален: {file_name}")
        else:
            await update.message.reply_text("❌ Файл не найден")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Напишите: /search текст")
        return
    
    acc = context.user_data['current_account']
    search_text = ' '.join(context.args).lower()
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    found = [name for name in files.keys() if search_text in name.lower()]
    
    if found:
        text = f"🔍 **Найдено {len(found)}:**\n\n"
        for name in found[:20]:
            text += f"📄 {name}\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Ничего не найдено")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    total_size = get_user_total_size(acc['user_id'])
    
    await update.message.reply_text(
        f"📊 **Статистика:**\n\n"
        f"📁 Файлов: {len(files)}\n"
        f"💾 Места: {format_size(total_size)} / {format_size(MAX_STORAGE_PER_USER)}",
        parse_mode='Markdown'
    )

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    total_size = get_user_total_size(acc['user_id'])
    
    await update.message.reply_text(
        f"👤 **Аккаунт:**\n\n"
        f"📝 Логин: {acc['username']}\n"
        f"🆔 ID: {acc['user_id'][:8]}\n"
        f"📁 Файлов: {len(files)}\n"
        f"💾 Места: {format_size(total_size)}",
        parse_mode='Markdown'
    )

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' in context.user_data:
        username = context.user_data['current_account']['username']
        context.user_data.pop('current_account')
        await update.message.reply_text(f"👋 До свидания, {username}!")
    else:
        await update.message.reply_text("❌ Вы не в аккаунте")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation для входа
    login_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^login$')],
        states={
            LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Conversation для регистрации
    register_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^register$')],
        states={
            REG_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_register)],
            REG_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_register)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Смена пароля
    change_pass_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^change_pass$')],
        states={
            CHANGE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_password)],
            NEW_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_password)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Поиск
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^search_menu$')],
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Отзывы
    feedback_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^feedback$')],
        states={
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("get", get_command))
    app.add_handler(CommandHandler("del", del_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("account", account_command))
    app.add_handler(CommandHandler("logout", logout_command))
    
    app.add_handler(login_conv)
    app.add_handler(register_conv)
    app.add_handler(change_pass_conv)
    app.add_handler(search_conv)
    app.add_handler(feedback_conv)
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, handle_file))
    
    print("="*50)
    print("🚀 МЕГА-УЛЬТРА БОТ ЗАПУЩЕН!")
    print("="*50)
    print(f"🤖 Токен: {BOT_TOKEN[:15]}...")
    print(f"👥 Пользователей: {len(accounts)}")
    print(f"📁 Всего файлов: {sum(len(u.get('files', {})) for u in users_data.values())}")
    print(f"💾 Всего данных: {format_size(sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values()))}")
    print("="*50)
    print("✅ Бот готов к работе!")
    print("="*50)
    
    app.run_polling()

if __name__ == '__main__':
    main()
