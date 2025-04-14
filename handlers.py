import os
import json
from telebot import types
from io import BytesIO
from file_processing import process_excel_file, load_existing_data, save_data
from bot import bot

def handle_start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton('Добавить расписание')
    item2 = types.KeyboardButton('Показать расписание')
    markup.add(item1, item2)
    bot.reply_to(message, 'Выберите действие:', reply_markup=markup)

def handle_add_schedule(message: types.Message):
    bot.send_message(message.chat.id, 'Пожалуйста, отправьте Excel-файл с расписанием.')

def handle_show_schedule(message: types.Message):
    try:
        data = load_existing_data()
        
        if not data["schedule_data"]:
            bot.reply_to(message, 'Расписание не найдено. Пожалуйста, добавьте файлы с расписанием.')
            return
            
        # Отправляем первые 10 записей
        for item in data["schedule_data"][:10]:
            schedule_info = (
                f"📅 Дата: {item['date']}\n"
                f"📚 Предмет: {item['subject']}\n"
                f"👨‍🏫 Преподаватель: {item['teacher']}\n"
                f"⏰ Время: {item['time']}\n"
                f"🏫 Аудитория: {item['audience']}\n"
            )
            bot.send_message(message.chat.id, schedule_info)
            
        # Показываем статистику
        stats = f"\n📊 Показано: 10 из {len(data['schedule_data'])}"
        bot.send_message(message.chat.id, stats)
        
    except Exception as e:
        print(f"Error showing schedule: {e}")
        bot.reply_to(message, '❌ Произошла ошибка при загрузке расписания')

def handle_document(message: types.Message):
    try:
        file_name = message.document.file_name
        file_name_lower = file_name.lower()
        
        if not (file_name_lower.endswith('.xls') or file_name_lower.endswith('.xlsx')):
            bot.reply_to(message, 'Пожалуйста, отправьте файл в формате Excel (.xls или .xlsx)')
            return
            
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        result = process_excel_file(downloaded_file, file_name)
        
        if result["status"] == "error":
            bot.reply_to(message, f'❌ {result["message"]}')
            return
            
        if result["new_entries_count"] == 0:
            bot.reply_to(message, '✅ Файл обработан, но новых записей не найдено')
        else:
            save_data(result["data"])
            report = f"✅ Файл {file_name} успешно обработан"
            bot.reply_to(message, report)
            
    except Exception as e:
        print(f"Error handling document: {e}")
        bot.reply_to(message, '❌ Произошла ошибка при обработке файла. Пожалуйста, попробуйте снова.')