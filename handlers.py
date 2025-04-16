import os
import json
from datetime import datetime, timedelta
from telebot import types
from file_processing import process_excel_file, load_existing_data, save_data
from bot import bot

# Словарь для отслеживания состояния
pending_users = {}

def create_main_keyboard():
    """Создает основную клавиатуру"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton('Добавить расписание')
    item2 = types.KeyboardButton('Показать расписание')
    item3 = types.KeyboardButton('Удалить файлы расписания')
    markup.add(item1, item2, item3)
    return markup

def handle_start(message: types.Message):
    """Обработчик команды /start"""
    bot.reply_to(message, 'Выберите действие:', reply_markup=create_main_keyboard())

def handle_add_schedule(message: types.Message):
    """Обработчик команды добавления расписания"""
    bot.send_message(message.chat.id, 'Пожалуйста, отправьте Excel-файл с расписанием.', reply_markup=create_main_keyboard())

def handle_show_command(message: types.Message):
    """Обработчик команды /show"""
    bot.send_message(message.chat.id, 'Введите фамилию преподавателя:', reply_markup=create_main_keyboard())
    pending_users[message.chat.id] = 'awaiting_teacher_name'

def handle_show_schedule(message: types.Message):
    """Обработчик кнопки 'Показать расписание'"""
    bot.send_message(message.chat.id, 'Введите фамилию преподавателя:', reply_markup=create_main_keyboard())
    pending_users[message.chat.id] = 'awaiting_teacher_name'

@bot.message_handler(content_types=['text'])
def handle_text(message: types.Message):
    chat_id = message.chat.id
    if chat_id in pending_users and pending_users[chat_id] == 'awaiting_teacher_name':
        del pending_users[chat_id]
        process_teacher_input(message)

def process_teacher_input(message: types.Message):
    """Обработка ввода фамилии преподавателя"""
    teacher_name = message.text.strip()

    data = load_existing_data()
    if not data or not data.get("schedule_data"):
        bot.send_message(message.chat.id, 'Расписание не найдено. Пожалуйста, добавьте файлы с расписанием.', reply_markup=create_main_keyboard())
        pending_users[message.chat.id] = 'awaiting_teacher_name'  # Ожидаем повторный ввод
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
        bot.send_message(message.chat.id, f'Преподаватель "{teacher_name}" не найден в расписании за указанный период.', reply_markup=create_main_keyboard())
        pending_users[message.chat.id] = 'awaiting_teacher_name'  # Ожидаем повторный ввод
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

    # Объединяем записи в сообщения, не превышая лимит Telegram (4096 символов)
    TELEGRAM_MESSAGE_LIMIT = 4096
    schedule_messages = []
    current_message = ""

    for item in unique_entries:  # Убрано ограничение на 10 записей
        schedule_info = (
            f"📅 Дата: {item['date']}\n"
            f"📚 Предмет: {item['subject']}\n"
            f"👨‍🏫 Преподаватель: {item['teacher']}\n"
            f"🔹 Тип: {item.get('type', '')}\n"
            f"⏰ Время: {item['time']}\n"
            f"🏫 Аудитория: {item['audience']}\n\n"
        )
        # Проверяем, не превысит ли добавление новой записи лимит
        if len(current_message) + len(schedule_info) > TELEGRAM_MESSAGE_LIMIT:
            schedule_messages.append(current_message)
            current_message = schedule_info
        else:
            current_message += schedule_info

    # Добавляем последнее сообщение, если оно не пустое
    if current_message:
        schedule_messages.append(current_message)

    # Отправляем сообщения
    for msg in schedule_messages:
        bot.send_message(message.chat.id, msg, reply_markup=create_main_keyboard())

    # После успешного вывода снова ожидаем ввод фамилии
    bot.send_message(message.chat.id, 'Введите фамилию преподавателя:', reply_markup=create_main_keyboard())
    pending_users[message.chat.id] = 'awaiting_teacher_name'

def handle_document(message: types.Message):
    """Обработчик загрузки документа"""
    file_name = message.document.file_name
    file_name_lower = file_name.lower()

    if not (file_name_lower.endswith('.xls') or file_name_lower.endswith('.xlsx')):
        bot.send_message(message.chat.id, 'Пожалуйста, отправьте файл в формате Excel (.xls или .xlsx)', reply_markup=create_main_keyboard())
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    result = process_excel_file(downloaded_file, file_name)

    if result["status"] == "error":
        bot.send_message(message.chat.id, f'❌ {result["message"]}', reply_markup=create_main_keyboard())
        return

    if result["new_entries_count"] == 0:
        bot.send_message(message.chat.id, '✅ Файл обработан, но новых записей не найдено', reply_markup=create_main_keyboard())
    else:
        save_data(result["data"])
        report = f"✅ Файл {file_name} успешно обработан"
        bot.send_message(message.chat.id, report, reply_markup=create_main_keyboard())

def handle_clear_schedule(message: types.Message):
    """Обработчик удаления расписания"""
    file_path = 'data/schedule.json'
    if os.path.exists(file_path):
        os.remove(file_path)
        bot.reply_to(message, '✅ Файл расписания успешно удален', reply_markup=create_main_keyboard())
    else:
        bot.reply_to(message, 'ℹ️ Файл расписания не найден (уже удален или не создавался)', reply_markup=create_main_keyboard())