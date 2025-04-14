import os
from dotenv import load_dotenv
from telebot import TeleBot
from handlers import handle_start, handle_add_schedule, handle_show_schedule, handle_document

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Создание экземпляра бота
bot = TeleBot(TOKEN)

# Регистрация обработчиков
bot.register_message_handler(handle_start, commands=['start'])
bot.register_message_handler(handle_add_schedule, func=lambda message: message.text == 'Добавить расписание')
bot.register_message_handler(handle_show_schedule, func=lambda message: message.text == 'Показать расписание')
bot.register_message_handler(handle_document, content_types=['document'])

# Запуск бота
if __name__ == '__main__':
    bot.polling(none_stop=True)