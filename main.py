import os
from dotenv import load_dotenv
from telebot import TeleBot
from handlers import (
    handle_start,
    handle_add_schedule,
    handle_show_schedule,
    handle_document,
    handle_clear_schedule,
    handle_show_command,
    handle_text
)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Создание экземпляра бота
bot = TeleBot(TOKEN)

# Регистрация обработчиков
bot.register_message_handler(handle_start, commands=['start'])
bot.register_message_handler(handle_show_command, commands=['show'])
bot.register_message_handler(handle_add_schedule, commands=['add'])
bot.register_message_handler(handle_clear_schedule, commands=['clear'])
bot.register_message_handler(handle_add_schedule, func=lambda message: message.text == 'Добавить расписание')
bot.register_message_handler(handle_show_schedule, func=lambda message: message.text == 'Показать расписание')
bot.register_message_handler(handle_clear_schedule, func=lambda message: message.text == 'Удалить файлы расписания')
bot.register_message_handler(handle_document, content_types=['document'])
bot.register_message_handler(handle_text, content_types=['text'])

# Запуск бота
if __name__ == '__main__':
    bot.polling(none_stop=True)