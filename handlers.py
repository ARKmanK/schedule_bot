import os
import json
from datetime import datetime, timedelta
from telebot import types
from file_processing import process_excel_file, load_existing_data, save_data
from bot import bot
from cryptography.fernet import Fernet
import base64
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Словарь для отслеживания состояния
pending_users = {}
# Словарь для хранения ролей пользователей
user_roles = {}
# Словарь для отслеживания состояния ввода пароля
pending_password = {}

# Пароль по умолчанию для Admin (используется только если переменная не задана)
DEFAULT_ADMIN_PASSWORD = "admin123"

# Инициализация шифрования
def initialize_encryption():
    """Инициализация ключа шифрования и пароля, если они ещё не заданы в .env"""
    encryption_key = os.getenv("ENCRYPTION_KEY")
    encrypted_password = os.getenv("ENCRYPTED_ADMIN_PASSWORD")

    if not encryption_key or not encrypted_password:
        # Генерируем новый ключ шифрования
        key = Fernet.generate_key()
        cipher = Fernet(key)
        # Шифруем пароль по умолчанию
        encrypted_password = cipher.encrypt(DEFAULT_ADMIN_PASSWORD.encode())
        # Сохраняем ключ и зашифрованный пароль в .env
        update_env_file({
            "ENCRYPTION_KEY": base64.urlsafe_b64encode(key).decode(),
            "ENCRYPTED_ADMIN_PASSWORD": base64.urlsafe_b64encode(encrypted_password).decode()
        })

def update_env_file(new_values):
    """Обновляет .env файл с новыми значениями и синхронизирует os.environ"""
    env_path = ".env"
    env_vars = {}
    
    # Читаем существующий .env файл
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value

    # Обновляем значения
    env_vars.update(new_values)

    # Переписываем .env файл
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    # Синхронизируем os.environ с новыми значениями
    for key, value in new_values.items():
        os.environ[key] = value

def get_cipher():
    """Получение объекта шифрования Fernet"""
    key = base64.urlsafe_b64decode(os.getenv("ENCRYPTION_KEY"))
    return Fernet(key)

def update_admin_password(new_password):
    """Обновление пароля Admin"""
    cipher = get_cipher()
    encrypted_password = cipher.encrypt(new_password.encode())
    # Обновляем зашифрованный пароль в .env и os.environ
    update_env_file({
        "ENCRYPTED_ADMIN_PASSWORD": base64.urlsafe_b64encode(encrypted_password).decode()
    })

def check_admin_password(password):
    """Проверка введенного пароля"""
    cipher = get_cipher()
    encrypted_password = base64.urlsafe_b64decode(os.getenv("ENCRYPTED_ADMIN_PASSWORD"))
    decrypted_password = cipher.decrypt(encrypted_password).decode()
    return password == decrypted_password

def create_keyboard_for_role(role):
    """Создает клавиатуру в зависимости от роли"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if role == "Admin":
        item1 = types.KeyboardButton('Добавить расписание')
        item2 = types.KeyboardButton('Удалить файлы расписания')
        item3 = types.KeyboardButton('Сменить роль')
        item4 = types.KeyboardButton('Сменить пароль')
        markup.add(item1, item2, item3, item4)
    else:  # Teacher
        item1 = types.KeyboardButton('Показать расписание')
        item2 = types.KeyboardButton('Сменить роль')
        markup.add(item1, item2)
    return markup

def handle_start(message: types.Message):
    """Обработчик команды /start"""
    global pending_users, pending_password, user_roles

    chat_id = message.chat.id
    
    # Сбрасываем все состояния (перезагрузка бота)
    pending_users.clear()
    pending_password.clear()
    user_roles.clear()

    # Повторно инициализируем шифрование
    initialize_encryption()

    # Устанавливаем роль Teacher по умолчанию для текущего пользователя
    user_roles[chat_id] = "Teacher"
    role = user_roles[chat_id]

    # Отправляем сообщение о перезагрузке и начальном состоянии
    bot.reply_to(message, 'Бот перезапущен. Все состояния сброшены.', reply_markup=create_keyboard_for_role(role))
    bot.send_message(chat_id, f'Выберите действие (роль: {role}):', reply_markup=create_keyboard_for_role(role))

def handle_change_role(message: types.Message):
    """Обработчик смены роли"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    # Очищаем состояние пароля при смене роли
    if chat_id in pending_password:
        del pending_password[chat_id]
    
    if role == "Admin":
        # Если пользователь Admin, сразу меняем роль на Преподаватель
        user_roles[chat_id] = "Teacher"
        bot.send_message(chat_id, 'Роль изменена на Преподаватель.', reply_markup=create_keyboard_for_role("Teacher"))
    else:
        # Если пользователь Преподаватель, запрашиваем пароль для Admin
        bot.send_message(chat_id, 'Введите пароль для роли Admin:', reply_markup=create_keyboard_for_role(role))
        pending_password[chat_id] = 'awaiting_admin_password'

def handle_add_schedule(message: types.Message):
    """Обработчик команды добавления расписания"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    if role != "Admin":
        bot.send_message(chat_id, 'Эта команда доступна только для роли Admin.', reply_markup=create_keyboard_for_role(role))
        return
    bot.send_message(chat_id, 'Пожалуйста, отправьте Excel-файл с расписанием.', reply_markup=create_keyboard_for_role(role))

def handle_show_command(message: types.Message):
    """Обработчик команды /show"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    if role != "Teacher":
        bot.send_message(chat_id, 'Эта команда доступна только для роли Преподаватель.', reply_markup=create_keyboard_for_role(role))
        return
    bot.send_message(chat_id, 'Введите фамилию преподавателя:', reply_markup=create_keyboard_for_role(role))
    pending_users[chat_id] = 'awaiting_teacher_name'

def handle_show_schedule(message: types.Message):
    """Обработчик кнопки 'Показать расписание'"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    if role != "Teacher":
        bot.send_message(chat_id, 'Эта команда доступна только для роли Преподаватель.', reply_markup=create_keyboard_for_role(role))
        return
    bot.send_message(chat_id, 'Введите фамилию преподавателя:', reply_markup=create_keyboard_for_role(role))
    pending_users[chat_id] = 'awaiting_teacher_name'

@bot.message_handler(content_types=['text'])
def handle_text(message: types.Message):
    chat_id = message.chat.id

    # Обработка ввода пароля для Admin (при входе)
    if chat_id in pending_password and pending_password[chat_id] == 'awaiting_admin_password':
        del pending_password[chat_id]
        password = message.text
        if check_admin_password(password):
            user_roles[chat_id] = "Admin"
            bot.send_message(chat_id, 'Роль изменена на Admin.', reply_markup=create_keyboard_for_role("Admin"))
        else:
            bot.send_message(chat_id, 'Неверный пароль. Роль не изменена.', reply_markup=create_keyboard_for_role(user_roles[chat_id]))

    # Обработка смены пароля для Admin
    elif chat_id in pending_password and pending_password[chat_id] == 'awaiting_new_password':
        del pending_password[chat_id]
        new_password = message.text.strip()
        if not new_password:
            bot.send_message(chat_id, 'Пароль не может быть пустым. Попробуйте снова.', reply_markup=create_keyboard_for_role("Admin"))
            bot.send_message(chat_id, 'Введите новый пароль:', reply_markup=create_keyboard_for_role("Admin"))
            pending_password[chat_id] = 'awaiting_new_password'
            return
        update_admin_password(new_password)
        bot.send_message(chat_id, 'Пароль успешно изменен.', reply_markup=create_keyboard_for_role("Admin"))

    # Обработка кнопки "Сменить роль"
    elif message.text == "Сменить роль":
        handle_change_role(message)

    # Обработка кнопки "Сменить пароль"
    elif message.text == "Сменить пароль":
        role = user_roles.get(chat_id, "Teacher")
        if role != "Admin":
            bot.send_message(chat_id, 'Эта команда доступна только для роли Admin.', reply_markup=create_keyboard_for_role(role))
            return
        # Очищаем состояние перед запросом нового пароля
        if chat_id in pending_password:
            del pending_password[chat_id]
        bot.send_message(chat_id, 'Введите новый пароль:', reply_markup=create_keyboard_for_role("Admin"))
        pending_password[chat_id] = 'awaiting_new_password'

    # Обработка ввода фамилии преподавателя
    elif chat_id in pending_users and pending_users[chat_id] == 'awaiting_teacher_name':
        del pending_users[chat_id]
        process_teacher_input(message)

def process_teacher_input(message: types.Message):
    """Обработка ввода фамилии преподавателя"""
    teacher_name = message.text.strip()
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")

    data = load_existing_data()
    if not data or not data.get("schedule_data"):
        bot.send_message(chat_id, 'Расписание не найдено. Пожалуйста, добавьте файлы с расписанием.', reply_markup=create_keyboard_for_role(role))
        pending_users[chat_id] = 'awaiting_teacher_name'
        return

    # Получаем текущую дату и диапазон
    current_date = datetime.now()
    start_date = current_date - timedelta(days=14)  # -14 дней
    end_date = current_date + timedelta(days=28)    # +28 дней
    current_year = current_date.year

    teacher_entries = []
    search_name = teacher_name.lower()

    for item in data["schedule_data"]:
        teacher = item.get('teacher', '').lower()
        if not teacher:
            continue

        # Улучшенный поиск: извлекаем фамилию более надежно
        teacher_parts = teacher.split()
        teacher_clean = teacher_parts[-1] if teacher_parts else teacher
        if teacher.startswith('доц.') or teacher.startswith('ст.преп.'):
            teacher_clean = teacher_parts[1] if len(teacher_parts) > 1 else teacher_clean

        # Проверяем совпадение
        if (search_name in teacher or 
            search_name in teacher_clean or
            any(search_name in part for part in teacher_parts)):
            # Преобразуем дату из строки DD.MM в объект datetime для текущего года и следующих 3 лет
            try:
                schedule_date_str = item['date']
                entry_added = False
                for year_offset in range(4):  # 2025, 2026, 2027, 2028
                    year = current_year + year_offset
                    schedule_date = datetime.strptime(schedule_date_str + f".{year}", '%d.%m.%Y')
                    # Проверяем, попадает ли дата в диапазон
                    if start_date <= schedule_date <= end_date:
                        item['sort_date'] = schedule_date
                        teacher_entries.append(item)
                        entry_added = True
                        break
                if not entry_added:
                    continue
            except ValueError:
                continue  # Пропускаем, если дата в неправильном формате

    if not teacher_entries:
        bot.send_message(chat_id, f'Преподаватель "{teacher_name}" не найден в расписании за указанный период.', reply_markup=create_keyboard_for_role(role))
        pending_users[chat_id] = 'awaiting_teacher_name'
        return

    # Удаляем дубликаты
    unique_entries = []
    seen = set()
    for entry in teacher_entries:
        entry_tuple = (entry['date'], entry['teacher'], entry['subject'], entry['time'], entry['audience'], entry.get('type', ''))
        if entry_tuple not in seen:
            seen.add(entry_tuple)
            unique_entries.append(entry)

    # Сортируем записи по дате
    unique_entries.sort(key=lambda x: x['sort_date'])

    # Формируем сообщение с рамками и минимальной шириной
    TELEGRAM_MESSAGE_LIMIT = 4096
    schedule_messages = []
    current_message = ""
    min_width = 60  # Минимальная ширина для каждого поля

    for item in unique_entries:
        # Формируем содержимое блока
        date_str = f"{item['date']}".ljust(min_width)
        # Ограничиваем длину названия предмета и добавляем точку, если обрезается
        subject = item['subject']
        if len(subject) > min_width - 2:
            subject = f"{subject[:min_width-5]}..."
        subject_str = subject.ljust(min_width)
        type_str = f"{item.get('type', '')}"[:min_width-5].ljust(min_width)
        time_str = f"{item['time']}".ljust(min_width)
        audience_str = f"Ауд. {item['audience']}".ljust(min_width)

        # Создаем рамку для блока
        block = (
            f"╔{'═' * (min_width + 2)}╗\n"
            f"║ {date_str} ║\n"
            f"║ {subject_str} ║\n"
            f"║ {type_str} ║\n"
            f"║ {time_str} ║\n"
            f"║ {audience_str} ║\n"
            f"╚{'═' * (min_width + 2)}╝\n\n"
        )

        # Проверяем, не превысит ли добавление новой записи лимит
        if len(current_message) + len(block) > TELEGRAM_MESSAGE_LIMIT:
            schedule_messages.append(current_message)
            current_message = block
        else:
            current_message += block

    # Добавляем последнее сообщение, если оно не пустое
    if current_message:
        schedule_messages.append(current_message)

    # Отправляем сообщения
    for msg in schedule_messages:
        bot.send_message(chat_id, f"```\n{msg}\n```", parse_mode="Markdown", reply_markup=create_keyboard_for_role(role))

    # После вывода снова ожидаем ввод фамилии
    bot.send_message(chat_id, 'Введите фамилию преподавателя:', reply_markup=create_keyboard_for_role(role))
    pending_users[chat_id] = 'awaiting_teacher_name'

def handle_document(message: types.Message):
    """Обработчик загрузки документа"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    if role != "Admin":
        bot.send_message(chat_id, 'Эта команда доступна только для роли Admin.', reply_markup=create_keyboard_for_role(role))
        return

    file_name = message.document.file_name
    file_name_lower = file_name.lower()

    if not (file_name_lower.endswith('.xls') or file_name_lower.endswith('.xlsx')):
        bot.send_message(chat_id, 'Пожалуйста, отправьте файл в формате Excel (.xls или .xlsx)', reply_markup=create_keyboard_for_role(role))
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    result = process_excel_file(downloaded_file, file_name)

    if result["status"] == "error":
        bot.send_message(chat_id, f'❌ {result["message"]}', reply_markup=create_keyboard_for_role(role))
        return

    if result["new_entries_count"] == 0:
        bot.send_message(chat_id, '✅ Файл обработан, но новых записей не найдено', reply_markup=create_keyboard_for_role(role))
    else:
        save_data(result["data"])
        report = f"✅ Файл {file_name} успешно обработан"
        bot.send_message(chat_id, report, reply_markup=create_keyboard_for_role(role))

def handle_clear_schedule(message: types.Message):
    """Обработчик удаления расписания"""
    chat_id = message.chat.id
    role = user_roles.get(chat_id, "Teacher")
    if role != "Admin":
        bot.send_message(chat_id, 'Эта команда доступна только для роли Admin.', reply_markup=create_keyboard_for_role(role))
        return

    file_path = 'data/schedule.json'
    if os.path.exists(file_path):
        os.remove(file_path)
        bot.reply_to(message, '✅ Файл расписания успешно удален', reply_markup=create_keyboard_for_role(role))
    else:
        bot.reply_to(message, 'ℹ️ Файл расписания не найден (уже удален или не создавался)', reply_markup=create_keyboard_for_role(role))

# Инициализация шифрования при запуске
initialize_encryption()