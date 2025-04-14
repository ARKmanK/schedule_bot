import os
from dotenv import load_dotenv
from telebot import TeleBot

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Создание экземпляра бота
bot = TeleBot(TOKEN)
