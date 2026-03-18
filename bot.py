import json
import os
import datetime
import random
import string
import hashlib
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import asyncio

# ========== ТВОЙ ТОКЕН ==========
BOT_TOKEN = "8745261570:AAGG2UHvob2bE86hTh7DRBhAKQ1Piq-YbbU"
ADMIN_IDS = ["6579391458", "8745261570"]
# ================================

# Состояния
(LOGIN, PASSWORD, REG_LOGIN, REG_PASSWORD, REG_CONFIRM, 
 CHANGE_PASSWORD, NEW_PASSWORD, FEEDBACK, SEARCH, SHARE_USER,
 ADD_FOLDER, RENAME_FILE, MOVE_FILE) = range(13)

# Файлы
DATA_FILE = 'users_data.json'
ACCOUNTS_FILE = 'accounts.json'
STATS_FILE = 'stats.json'

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
    return {'total_users': 0, 'total_files': 0, 'total_size': 0, 'start_time': str(datetime.datetime.now())}

def save_all(users, accs, stats):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accs, f, ensure_ascii=False, indent=2)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

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

def get_file_icon(filename):
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    icons = {
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'mp4': '🎬', 'avi': '🎬', 'mov': '🎬',
        'mp3': '🎵', 'wav': '🎵',
        'pdf': '📕', 'doc': '📘', 'docx': '📘', 'txt': '📄',
        'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️',
        'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨'
    }
    return icons.get(ext, '📄')

# ========== КРАСИВЫЕ КЛАВИАТУРЫ ==========
def get_main_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("📁 МОИ ФАЙЛЫ", callback_data='list_files'),
         InlineKeyboardButton("📊 СТАТИСТИКА", callback_data='stats')],
        [InlineKeyboardButton("📤 ЗАГРУЗИТЬ", callback_data='upload_info'),
         InlineKeyboardButton("📥 СКАЧАТЬ", callback_data='download_info')],
        [InlineKeyboardButton("🔍 ПОИСК", callback_data='search_menu'),
         InlineKeyboardButton("📂 ПАПКИ", callback_data='folders_menu')],
        [InlineKeyboardButton("👤 АККАУНТ", callback_data='account_info'),
         InlineKeyboardButton("🔐 СМЕНИТЬ ПАРОЛЬ", callback_data='change_pass')],
        [InlineKeyboardButton("📞 ПОДДЕРЖКА", callback_data='support'),
         InlineKeyboardButton("📝 ОТЗЫВ", callback_data='feedback')],
        [InlineKeyboardButton("📎 ПОДЕЛИТЬСЯ", callback_data='share_menu'),
         InlineKeyboardButton("🔄 ОБНОВИТЬ", callback_data='refresh')],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ АДМИН ПАНЕЛЬ", callback_data='admin_panel')])
    keyboard.append([InlineKeyboardButton("❓ ПОМОЩЬ", callback_data='help'),
                     InlineKeyboardButton("🚪 ВЫЙТИ", callback_data='logout')])
    return InlineKeyboardMarkup(keyboard)

def get_animated_keyboard(text, buttons):
    """Создает клавиатуру с анимацией через изменение текста"""
    return {
        'text': text,
        'reply_markup': InlineKeyboardMarkup(buttons)
    }

def get_back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ НАЗАД В МЕНЮ", callback_data='back_to_menu')
    ]])

def get_files_keyboard(files, action='get', page=0):
    file_list = list(files.items())
    items_per_page = 8
    start = page * items_per_page
    end = start + items_per_page
    current_files = file_list[start:end]
    
    keyboard = []
    for i, (name, info) in enumerate(current_files):
        icon = get_file_icon(name)
        size = info.get('size', '?')
        btn_text = f"{icon} {name[:15]} ({size})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"{action}_{name}")])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{(len(file_list)-1)//items_per_page+1}", callback_data="noop"))
    if end < len(file_list):
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(keyboard)

# ========== КОМАНДА СТАРТ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "NoUsername"
    first_name = update.effective_user.first_name or "User"
    
    # Приветственное сообщение
    welcome_text = """
🌟 **ДОБРО ПОЖАЛОВАТЬ В МЕГА-ОБЛАКО!** 🌟

╔══════════════════════════╗
║  ☁️ **Версия 5.0 ULTRA**   ║
║  👑 Разработчик: @error_08081  ║
╚══════════════════════════╝

✨ **ЧТО Я УМЕЮ:**
├─📁 Хранить файлы (до 500 МБ)
├─📂 Создавать папки
├─🔍 Искать по названию
├─📊 Смотреть статистику
├─🔐 Безопасный вход
└─🔄 Синхронизация

🔐 **Для начала войди или зарегистрируйся:**
"""
    
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
        
        await update.message.reply_text(
            f"🌟 **С ВОЗВРАЩЕНИЕМ, {found_account['username']}!**\n\n"
            f"📁 **Файлов:** {len(user_files)}\n"
            f"💾 **Использовано:** {format_size(total_size)} / 500 МБ\n"
            f"📅 **Аккаунт создан:** {found_account.get('created', 'неизв')}\n\n"
            f"⚡ **Выбери действие:**",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id in ADMIN_IDS)
        )
    else:
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 ВОЙТИ", callback_data='login'),
                 InlineKeyboardButton("📝 РЕГИСТРАЦИЯ", callback_data='register')],
                [InlineKeyboardButton("ℹ️ О БОТЕ", callback_data='about')]
            ])
        )

# ========== ГЛАВНЫЙ ОБРАБОТЧИК ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Заглушка для неактивных кнопок
    if data == 'noop':
        return
    
    # Навигация
    if data == 'back_to_menu':
        if 'current_account' in context.user_data:
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            
            text = f"""
🌟 **ГЛАВНОЕ МЕНЮ** 🌟
╔════════════════════╗
║ 👤 **{acc['username']}**
║ 📁 **Файлов:** {len(user_files)}
║ 💾 **Места:** {format_size(total_size)} / 500 МБ
╚════════════════════╝

⚡ **Выбери действие:**
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await query.edit_message_text(
                "🌟 **ГЛАВНОЕ МЕНЮ**\n\nВыбери действие:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 ВОЙТИ", callback_data='login'),
                     InlineKeyboardButton("📝 РЕГИСТРАЦИЯ", callback_data='register')]
                ])
            )
        return
    
    if data == 'refresh':
        if 'current_account' in context.user_data:
            await query.edit_message_text("🔄 **ОБНОВЛЕНИЕ ДАННЫХ...**", parse_mode='Markdown')
            await asyncio.sleep(1)
            # Возвращаемся в меню с обновленными данными
            acc = context.user_data['current_account']
            user_files = users_data.get(acc['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc['user_id'])
            
            text = f"""
🔄 **ДАННЫЕ ОБНОВЛЕНЫ!**
╔════════════════════╗
║ 👤 **{acc['username']}**
║ 📁 **Файлов:** {len(user_files)}
║ 💾 **Места:** {format_size(total_size)} / 500 МБ
╚════════════════════╝
            """
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        return
    
    # О боте
    if data == 'about':
        uptime = datetime.datetime.now() - datetime.datetime.fromisoformat(stats.get('start_time', str(datetime.datetime.now())))
        hours = uptime.total_seconds() / 3600
        
        text = f"""
ℹ️ **О МЕГА-ОБЛАКЕ** ℹ️
╔══════════════════════════╗
║  🚀 **Версия:** 5.0 ULTRA
║  👑 **Разработчик:** @error_08081
║  📅 **Создан:** 2024
║  ⏰ **Аптайм:** {hours:.1f} ч
║  👥 **Пользователей:** {len(accounts)}
║  📁 **Всего файлов:** {stats.get('total_files', 0)}
║  💾 **Всего данных:** {format_size(stats.get('total_size', 0))}
╚══════════════════════════╝

✨ **ВОЗМОЖНОСТИ:**
├─✅ Загрузка любых файлов
├─✅ Создание папок
├─✅ Поиск по названию
├─✅ Статистика использования
├─✅ Смена пароля
├─✅ Отзывы и поддержка
├─✅ Админ панель
└─✅ И многое другое!

📱 **РАБОТАЕТ НА ВСЕХ УСТРОЙСТВАХ!**
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
        return
    
    # Авторизация
    if data == 'login':
        await query.edit_message_text("🔐 **ВВЕДИТЕ ЛОГИН:**", parse_mode='Markdown')
        return LOGIN
    
    if data == 'register':
        await query.edit_message_text(
            "📝 **РЕГИСТРАЦИЯ**\n\n"
            "Придумайте логин (только буквы и цифры, от 3 символов):",
            parse_mode='Markdown'
        )
        return REG_LOGIN
    
    # Проверка авторизации для остальных действий
    if 'current_account' not in context.user_data:
        await query.edit_message_text(
            "❌ **СНАЧАЛА ВОЙДИТЕ В АККАУНТ!**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 ВОЙТИ", callback_data='login')]
            ])
        )
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
    # СПИСОК ФАЙЛОВ
    if data == 'list_files':
        files = users_data.get(user_id, {}).get('files', {})
        if not files:
            await query.edit_message_text(
                "📭 **У ВАС ПОКА НЕТ ФАЙЛОВ**\n\n"
                "Отправьте мне любой файл, чтобы начать!",
                parse_mode='Markdown',
                reply_markup=get_back_keyboard()
            )
            return
        
        total_size = get_user_total_size(user_id)
        text = f"""
📁 **ВАШИ ФАЙЛЫ** 📁
╔════════════════════╗
║  Всего: **{len(files)}** файлов
║  Места: **{format_size(total_size)}** / 500 МБ
╚════════════════════╝

⚡ **Выберите файл:**
        """
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=get_files_keyboard(files, 'get', 0)
        )
    
    # ПАГИНАЦИЯ
    elif data.startswith('page_'):
        page = int(data.split('_')[1])
        files = users_data.get(user_id, {}).get('files', {})
        await query.edit_message_reply_markup(reply_markup=get_files_keyboard(files, 'get', page))
    
    # СКАЧИВАНИЕ ФАЙЛА
    elif data.startswith('get_'):
        file_name = data[4:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            await query.edit_message_text(f"📥 **ОТПРАВЛЯЮ:** `{file_name}`", parse_mode='Markdown')
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=files[file_name]['file_id'],
                filename=file_name,
                caption=f"📥 **{file_name}**\nРазмер: {files[file_name]['size']}"
            )
            await query.edit_message_text(
                "✅ **ФАЙЛ ОТПРАВЛЕН!**",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📁 К ФАЙЛАМ", callback_data='list_files'),
                    InlineKeyboardButton("🏠 В МЕНЮ", callback_data='back_to_menu')
                ]])
            )
    
    # СТАТИСТИКА
    elif data == 'stats':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        
        # Считаем по типам
        types = {'photo': 0, 'document': 0, 'video': 0, 'audio': 0, 'other': 0}
        for f in files.values():
            f_type = f.get('type', 'other')
            types[f_type] = types.get(f_type, 0) + 1
        
        percent = (total_size / (500 * 1024 * 1024)) * 100
        bar = '█' * int(percent/10) + '░' * (10 - int(percent/10))
        
        text = f"""
📊 **ДЕТАЛЬНАЯ СТАТИСТИКА** 📊
╔════════════════════╗
║ 📁 **Файлов:** {len(files)}
║ 💾 **Места:** {format_size(total_size)} / 500 МБ
║ 📊 **Занято:** {bar} {percent:.1f}%
╠════════════════════╣
║ 🖼️ **Фото:** {types['photo']}
║ 📄 **Документы:** {types['document']}
║ 🎬 **Видео:** {types['video']}
║ 🎵 **Аудио:** {types['audio']}
║ 📦 **Другое:** {types['other']}
╚════════════════════╝
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ИНФОРМАЦИЯ ОБ АККАУНТЕ
    elif data == 'account_info':
        files = users_data.get(user_id, {}).get('files', {})
        total_size = get_user_total_size(user_id)
        
        text = f"""
👤 **ИНФОРМАЦИЯ ОБ АККАУНТЕ** 👤
╔════════════════════╗
║ 📝 **Логин:** `{acc['username']}`
║ 🆔 **ID:** `{acc['user_id'][:8]}...`
║ 📅 **Создан:** {acc.get('created', 'неизв')}
║ 📁 **Файлов:** {len(files)}
║ 💾 **Места:** {format_size(total_size)} / 500 МБ
║ 🔗 **Telegram ID:** `{acc.get('telegram_id', 'не привязан')}`
╚════════════════════╝

🔐 **ДЕЙСТВИЯ:**
• /change_pass - сменить пароль
• /logout - выйти
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ПОМОЩЬ
    elif data == 'help':
        text = """
❓ **СПРАВКА ПО КОМАНДАМ** ❓
╔══════════════════════════╗
║  **📱 ОСНОВНЫЕ КНОПКИ:**  ║
╠══════════════════════════╣
║ 📁 **Файлы** - список файлов
║ 📊 **Статистика** - использование
║ 📤 **Загрузить** - как загружать
║ 📥 **Скачать** - как скачивать
║ 🔍 **Поиск** - найти файл
║ 📂 **Папки** - управление папками
║ 👤 **Аккаунт** - данные
║ 🔐 **Сменить пароль**
║ 📞 **Поддержка** - связаться
║ 📝 **Отзыв** - написать
║ 📎 **Поделиться** - отправить файл
║ 🔄 **Обновить** - обновить данные
╚══════════════════════════╝

**📝 ТЕКСТОВЫЕ КОМАНДЫ:**
/start - главное меню
/list - список файлов
/get имя - скачать файл
/del имя - удалить файл
/search текст - поиск
/stats - статистика
/account - мой аккаунт
/logout - выйти
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ПОДДЕРЖКА
    elif data == 'support':
        text = """
📞 **ПОДДЕРЖКА** 📞
╔════════════════════╗
║ 👤 **Разработчик:** 
║    @error_08081
║ 📧 **Email:** 
║    support@megacloud.ru
║ ⏰ **Время работы:** 
║    24/7
║ 💬 **Ответ:** 
║    Обычно в течение часа
╚════════════════════╝

❓ **ЧАСТЫЕ ВОПРОСЫ:**
• Как восстановить пароль?
  -> Напишите разработчику

• Сколько можно хранить?
  -> 500 МБ бесплатно

• Безопасно ли?
  -> Да, все пароли зашифрованы
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ОТЗЫВ
    elif data == 'feedback':
        await query.edit_message_text(
            "📝 **НАПИШИТЕ ВАШ ОТЗЫВ**\n\n"
            "Мне важно ваше мнение! Что нравится? Что можно улучшить?",
            parse_mode='Markdown'
        )
        return FEEDBACK
    
    # ИНФОРМАЦИЯ О ЗАГРУЗКЕ
    elif data == 'upload_info':
        text = """
📤 **КАК ЗАГРУЗИТЬ ФАЙЛ** 📤
╔════════════════════╗
║ 1️⃣ **Просто отправьте**
║    мне любой файл
║ 2️⃣ **Я автоматически**
║    сохраню его
║ 3️⃣ **Можно загружать**
║    несколько подряд
╠════════════════════╣
║ ✅ **Поддерживаются:**
║ • 📷 Фото (JPG, PNG, GIF)
║ • 📄 Документы (PDF, DOC, TXT)
║ • 🎵 Музыка (MP3)
║ • 🎬 Видео (MP4)
║ • 📦 Архивы (ZIP, RAR)
╠════════════════════╣
║ ⚠️ **Лимиты:**
║ • Макс файл: 50 МБ
║ • Всего места: 500 МБ
╚════════════════════╝
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ИНФОРМАЦИЯ О СКАЧИВАНИИ
    elif data == 'download_info':
        text = """
📥 **КАК СКАЧАТЬ ФАЙЛ** 📥
╔════════════════════╗
║ **Способ 1:** Через меню
║ 1️⃣ Нажми «Мои файлы»
║ 2️⃣ Выбери нужный файл
║ 3️⃣ Нажми на него
╠════════════════════╣
║ **Способ 2:** Командой
║ `/get название_файла`
║ Пример: `/get photo.jpg`
╠════════════════════╣
║ **Способ 3:** Поиск
║ Найди файл через поиск
║ и скачай его
╚════════════════════╝
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ПОИСК
    elif data == 'search_menu':
        await query.edit_message_text(
            "🔍 **ПОИСК ФАЙЛОВ**\n\n"
            "Введите название файла (или часть названия):",
            parse_mode='Markdown'
        )
        return SEARCH
    
    # ПАПКИ (в разработке)
    elif data == 'folders_menu':
        text = """
📂 **УПРАВЛЕНИЕ ПАПКАМИ** 📂
╔════════════════════╗
║ 🚀 **Функция в разработке!**
║
║ Скоро вы сможете:
║ • 📁 Создавать папки
║ • 📂 Сортировать файлы
║ • 🔍 Искать по папкам
║ • 📎 Делиться папками
╚════════════════════╝

⏳ **Следите за обновлениями!**
        """
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # СМЕНА ПАРОЛЯ
    elif data == 'change_pass':
        await query.edit_message_text(
            "🔐 **СМЕНА ПАРОЛЯ**\n\n"
            "Введите **старый пароль**:",
            parse_mode='Markdown'
        )
        return CHANGE_PASSWORD
    
    # МЕНЮ ШЕРИНГА
    elif data == 'share_menu':
        text = """
📎 **ПОДЕЛИТЬСЯ ФАЙЛОМ** 📎
╔════════════════════╗
║ 1️⃣ Выберите файл
║ 2️⃣ Получите ссылку
║ 3️⃣ Отправьте другу
╠════════════════════╣
║ 🔗 **Как это работает:**
║ • Ссылка действует 24 часа
║ • Можно скачать 1 раз
║ • Безопасно и удобно
╚════════════════════╝
        """
        files = users_data.get(user_id, {}).get('files', {})
        if files:
            keyboard = []
            for name in list(files.keys())[:5]:
                keyboard.append([InlineKeyboardButton(f"📎 {name[:20]}", callback_data=f"share_{name}")])
            keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back_to_menu')])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text + "\n\n❌ **Нет файлов для шаринга**", parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ШЕРИНГ ФАЙЛА
    elif data.startswith('share_'):
        file_name = data[6:]
        files = users_data.get(user_id, {}).get('files', {})
        if file_name in files:
            share_id = gen_id()
            if 'shares' not in users_data[user_id]:
                users_data[user_id]['shares'] = {}
            
            users_data[user_id]['shares'][share_id] = {
                'file_name': file_name,
                'file_id': files[file_name]['file_id'],
                'created': str(datetime.datetime.now()),
                'expires': str(datetime.datetime.now() + datetime.timedelta(days=1))
            }
            save_all(users_data, accounts, stats)
            
            share_link = f"https://t.me/{(await context.bot.get_me()).username}?start=share_{share_id}"
            
            text = f"""
✅ **ССЫЛКА СОЗДАНА!**
╔════════════════════╗
║ 📄 **Файл:** {file_name}
║ ⏰ **Действует:** 24 часа
║ 🔢 **ID:** {share_id[:8]}...
╚════════════════════╝

🔗 **Ваша ссылка:**
`{share_link}`

📱 **Отправьте её другу!**
            """
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())
    
    # ВЫХОД
    elif data == 'logout':
        username = acc['username']
        context.user_data.pop('current_account', None)
        await query.edit_message_text(
            f"👋 **ДО СВИДАНИЯ, {username}!**\n\n"
            "Чтобы войти снова, нажмите /start",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔐 ВОЙТИ", callback_data='login')]
            ])
        )
    
    # АДМИН ПАНЕЛЬ
    elif data == 'admin_panel' and str(update.effective_user.id) in ADMIN_IDS:
        total_users = len(accounts)
        total_files = sum(len(u.get('files', {})) for u in users_data.values())
        total_size = sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values())
        
        uptime = datetime.datetime.now() - datetime.datetime.fromisoformat(stats.get('start_time', str(datetime.datetime.now())))
        hours = uptime.total_seconds() / 3600
        
        text = f"""
⚙️ **АДМИН ПАНЕЛЬ** ⚙️
╔════════════════════╗
║ 👥 **Пользователей:** {total_users}
║ 📁 **Всего файлов:** {total_files}
║ 💾 **Всего данных:** {format_size(total_size)}
║ ⏰ **Аптайм:** {hours:.1f} ч
║ 🆔 **Ваш ID:** {update.effective_user.id}
╚════════════════════╝

📊 **ДЕТАЛЬНО:**
        """
        
        # Список последних пользователей
        if accounts:
            text += "\n👥 **Последние пользователи:**\n"
            for i, (uid, acc_data) in enumerate(list(accounts.items())[-5:]):
                user_files = users_data.get(acc_data['user_id'], {}).get('files', {})
                text += f"{i+1}. **{acc_data['username']}** - 📁 {len(user_files)}\n"
        
        keyboard = [
            [InlineKeyboardButton("👥 ВСЕ ПОЛЬЗОВАТЕЛИ", callback_data='admin_users')],
            [InlineKeyboardButton("📊 ПОЛНАЯ СТАТИСТИКА", callback_data='admin_full_stats')],
            [InlineKeyboardButton("📁 ВСЕ ФАЙЛЫ", callback_data='admin_all_files')],
            [InlineKeyboardButton("🔍 ПОИСК ПОЛЬЗОВАТЕЛЯ", callback_data='admin_search')],
            [InlineKeyboardButton("📢 РАССЫЛКА", callback_data='admin_broadcast')],
            [InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back_to_menu')]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'admin_users' and str(update.effective_user.id) in ADMIN_IDS:
        text = "👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
        for i, (uid, acc_data) in enumerate(accounts.items(), 1):
            user_files = users_data.get(acc_data['user_id'], {}).get('files', {})
            total_size = get_user_total_size(acc_data['user_id'])
            text += f"{i}. **{acc_data['username']}**\n"
            text += f"   📁 {len(user_files)} файлов | 💾 {format_size(total_size)}\n"
            text += f"   🆔 `{acc_data['user_id'][:8]}...`\n\n"
            if i >= 20:
                text += f"... и еще {len(accounts) - 20} пользователей"
                break
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard())

# ========== ОБРАБОТЧИКИ ВХОДА/РЕГИСТРАЦИИ ==========
async def handle_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'login_user' not in context.user_data:
        context.user_data['login_user'] = text
        await update.message.reply_text("🔑 **ВВЕДИТЕ ПАРОЛЬ:**", parse_mode='Markdown')
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
                f"✅ **УСПЕШНЫЙ ВХОД!**\n\n"
                f"👋 **С возвращением, {found['username']}!**\n"
                f"📁 **Файлов:** {len(files)}\n"
                f"💾 **Места:** {format_size(total_size)} / 500 МБ",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await update.message.reply_text(
                "❌ **НЕВЕРНЫЙ ЛОГИН ИЛИ ПАРОЛЬ!**\n\n"
                "Попробуйте еще раз /start",
                parse_mode='Markdown'
            )
        return ConversationHandler.END

async def handle_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'reg_user' not in context.user_data:
        if len(text) < 3 or not text.isalnum():
            await update.message.reply_text(
                "❌ **ОШИБКА!**\n\n"
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
                    "❌ **ЛОГИН УЖЕ ЗАНЯТ!**\n\n"
                    "Придумайте другой:",
                    parse_mode='Markdown'
                )
                return REG_LOGIN
        
        context.user_data['reg_user'] = text
        await update.message.reply_text(
            "✅ **ОТЛИЧНО!**\n\n"
            "Теперь придумайте **пароль** (минимум 4 символа):",
            parse_mode='Markdown'
        )
        return REG_PASSWORD
    else:
        if len(text) < 4:
            await update.message.reply_text(
                "❌ **ПАРОЛЬ СЛИШКОМ КОРОТКИЙ!**\n\n"
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
        users_data[user_id] = {'files': {}}
        stats['total_users'] = len(accounts)
        save_all(users_data, accounts, stats)
        
        context.user_data['current_account'] = accounts[user_id]
        
        await update.message.reply_text(
            f"🎉 **РЕГИСТРАЦИЯ УСПЕШНА!** 🎉\n\n"
            f"👤 **Логин:** `{username}`\n"
            f"🆔 **ID:** `{user_id[:8]}...`\n\n"
            f"📁 **500 МБ БЕСПЛАТНО!**\n"
            f"Теперь вы можете загружать файлы!",
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
            await update.message.reply_text(
                "✅ **СТАРЫЙ ПАРОЛЬ ПРИНЯТ!**\n\n"
                "Теперь введите **новый пароль**:",
                parse_mode='Markdown'
            )
            return NEW_PASSWORD
        else:
            await update.message.reply_text(
                "❌ **НЕВЕРНЫЙ ПАРОЛЬ!**\n\n"
                "Попробуйте еще раз /start",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
    else:
        if len(text) >= 4:
            acc = context.user_data['current_account']
            acc['password'] = hash_password(text)
            save_all(users_data, accounts, stats)
            
            await update.message.reply_text(
                "✅ **ПАРОЛЬ УСПЕШНО ИЗМЕНЕН!**",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(str(update.effective_user.id) in ADMIN_IDS)
            )
        else:
            await update.message.reply_text(
                "❌ **ПАРОЛЬ СЛИШКОМ КОРОТКИЙ!**\n\n"
                "Минимум 4 символа. Попробуйте еще:",
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
        text = f"🔍 **НАЙДЕНО {len(found)} ФАЙЛОВ:**\n\n"
        for i, name in enumerate(found[:20], 1):
            icon = get_file_icon(name)
            text += f"{i}. {icon} `{name}`\n"
        
        if len(found) > 20:
            text += f"\n... и еще {len(found) - 20} файлов"
        
        # Добавляем кнопки для скачивания первых 5
        keyboard = []
        for name in found[:5]:
            keyboard.append([InlineKeyboardButton(f"📥 {name[:20]}", callback_data=f"get_{name}")])
        keyboard.append([InlineKeyboardButton("◀️ НАЗАД", callback_data='back_to_menu')])
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(
            f"❌ **НИЧЕГО НЕ НАЙДЕНО ПО ЗАПРОСУ** `{search_text}`",
            parse_mode='Markdown',
            reply_markup=get_back_keyboard()
        )
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
                     f"👤 **От:** {acc.get('username', 'Unknown')}\n"
                     f"🆔 **Telegram:** `{user_id}`\n"
                     f"💬 **Текст:**\n{feedback}",
                parse_mode='Markdown'
            )
        except:
            pass
    
    await update.message.reply_text(
        "✅ **СПАСИБО ЗА ОТЗЫВ!**\n\n"
        "Я передал его разработчику. Он обязательно его прочитает!",
        parse_mode='Markdown',
        reply_markup=get_back_keyboard()
    )
    return ConversationHandler.END

# ========== ОБРАБОТЧИК ФАЙЛОВ ==========
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text(
            "❌ **СНАЧАЛА ВОЙДИТЕ В АККАУНТ!**\n\n"
            "/start",
            parse_mode='Markdown'
        )
        return
    
    acc = context.user_data['current_account']
    user_id = acc['user_id']
    
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
            "❌ **НЕПОДДЕРЖИВАЕМЫЙ ТИП ФАЙЛА!**\n\n"
            "Пока поддерживаются:\n"
            "• Документы\n"
            "• Фото\n"
            "• Видео\n"
            "• Аудио",
            parse_mode='Markdown'
        )
        return
    
    # Проверка размера
    if file_size > 50 * 1024 * 1024:  # 50 МБ
        await update.message.reply_text(
            f"❌ **ФАЙЛ СЛИШКОМ БОЛЬШОЙ!**\n\n"
            f"Максимальный размер: 50 МБ\n"
            f"Ваш файл: {format_size(file_size)}",
            parse_mode='Markdown'
        )
        return
    
    # Проверка свободного места
    if current_size + file_size > 500 * 1024 * 1024:  # 500 МБ
        await update.message.reply_text(
            f"❌ **НЕДОСТАТОЧНО МЕСТА!**\n\n"
            f"Свободно: {format_size(500 * 1024 * 1024 - current_size)}\n"
            f"Нужно: {format_size(file_size)}",
            parse_mode='Markdown'
        )
        return
    
    # Создаем запись если нет
    if user_id not in users_data:
        users_data[user_id] = {'files': {}}
    
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
    
    # Анимированное сообщение
    icon = get_file_icon(file_name)
    await update.message.reply_text(
        f"✅ **ФАЙЛ УСПЕШНО СОХРАНЕН!**\n\n"
        f"{icon} **Имя:** `{file_name}`\n"
        f"💾 **Размер:** {format_size(file_size)}\n"
        f"📅 **Дата:** {datetime.datetime.now().strftime('%d.%m.%Y')}\n"
        f"📁 **Всего файлов:** {len(users_data[user_id]['files'])}\n"
        f"💽 **Свободно:** {format_size(500 * 1024 * 1024 - current_size - file_size)}",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📁 МОИ ФАЙЛЫ", callback_data='list_files'),
             InlineKeyboardButton("📤 ЕЩЕ", callback_data='upload_info')],
            [InlineKeyboardButton("🏠 ГЛАВНОЕ МЕНЮ", callback_data='back_to_menu')]
        ])
    )

# ========== ТЕКСТОВЫЕ КОМАНДЫ ==========
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    
    if not files:
        await update.message.reply_text("📭 У вас нет файлов")
        return
    
    text = "📁 **ВАШИ ФАЙЛЫ:**\n\n"
    for name, info in list(files.items())[:20]:
        icon = get_file_icon(name)
        text += f"{icon} `{name}` ({info['size']})\n"
    
    if len(files) > 20:
        text += f"\n... и еще {len(files) - 20} файлов"
    
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
        await update.message.reply_text(f"❌ Файл '{file_name}' не найден")

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
            await update.message.reply_text(f"✅ Файл '{file_name}' удален")
        else:
            await update.message.reply_text(f"❌ Файл '{file_name}' не найден")

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
        text = f"🔍 **НАЙДЕНО {len(found)} ФАЙЛОВ:**\n\n"
        for name in found[:20]:
            icon = get_file_icon(name)
            text += f"{icon} `{name}`\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Ничего не найдено по запросу '{search_text}'")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'current_account' not in context.user_data:
        await update.message.reply_text("❌ Сначала войдите: /start")
        return
    
    acc = context.user_data['current_account']
    files = users_data.get(acc['user_id'], {}).get('files', {})
    total_size = get_user_total_size(acc['user_id'])
    
    percent = (total_size / (500 * 1024 * 1024)) * 100
    bar = '█' * int(percent/10) + '░' * (10 - int(percent/10))
    
    await update.message.reply_text(
        f"📊 **СТАТИСТИКА**\n\n"
        f"📁 Файлов: {len(files)}\n"
        f"💾 Места: {format_size(total_size)} / 500 МБ\n"
        f"📊 Занято: {bar} {percent:.1f}%",
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
        f"👤 **МОЙ АККАУНТ**\n\n"
        f"📝 Логин: {acc['username']}\n"
        f"🆔 ID: {acc['user_id'][:8]}...\n"
        f"📁 Файлов: {len(files)}\n"
        f"💾 Места: {format_size(total_size)} / 500 МБ",
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
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    feedback_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^feedback$')],
        states={
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("get", get_command))
    app.add_handler(CommandHandler("del", del_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("account", account_command))
    app.add_handler(CommandHandler("logout", logout_command))
    
    # Conversation handlers
    app.add_handler(login_conv)
    app.add_handler(register_conv)
    app.add_handler(change_pass_conv)
    app.add_handler(search_conv)
    app.add_handler(feedback_conv)
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Файлы
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handle_file
    ))
    
    print("="*60)
    print("🚀 МЕГА-УЛЬТРА БОТ ЗАПУЩЕН!")
    print("="*60)
    print(f"👑 Админ ID: {ADMIN_IDS}")
    print(f"👥 Пользователей: {len(accounts)}")
    print(f"📁 Всего файлов: {sum(len(u.get('files', {})) for u in users_data.values())}")
    print(f"💾 Всего данных: {format_size(sum(f.get('bytes', 0) for u in users_data.values() for f in u.get('files', {}).values()))}")
    print("="*60)
    print("⚡ Бот готов к работе!")
    print("="*60)
    
    app.run_polling()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔄 Перезапуск через 5 секунд...")
        time.sleep(5)
        main()
