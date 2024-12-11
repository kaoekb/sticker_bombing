import logging
import os
import time
import json
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Включаем логирование для удобства отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения из .env
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

# ID стикеров для утреннего и вечернего времени
MORNING_STICKER_ID = os.getenv('MORNING_STICKER_ID')
EVENING_STICKER_ID = os.getenv('EVENING_STICKER_ID')

# Файл для хранения активных чатов
ACTIVE_CHATS_FILE = 'active_chats.json'

# Создаем объект бота
bot = TeleBot(API_TOKEN)

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler_started = False  # Флаг, который будет указывать, что планировщик уже запущен

# Функции для работы с активными чатами
def load_active_chats():
    if os.path.exists(ACTIVE_CHATS_FILE):
        with open(ACTIVE_CHATS_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_active_chats(chats):
    with open(ACTIVE_CHATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(chats), f)

active_chats = load_active_chats()

# Команда для отключения бота в конкретном чате
@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        active_chats.remove(chat_id)
        save_active_chats(active_chats)
        bot.reply_to(message, "Бот отключен в этом чате.")
        logger.info(f"Бот отключен в чате {chat_id}")
    else:
        bot.reply_to(message, "Бот уже отключен в этом чате.")

# Команда для включения бота в конкретном чате (если требуется)
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    if chat_id not in active_chats:
        active_chats.add(chat_id)
        save_active_chats(active_chats)
        bot.reply_to(message, "Бот активирован в этом чате.")
        logger.info(f"Бот активирован в чате {chat_id}")
    else:
        bot.reply_to(message, "Бот уже активен в этом чате.")

# Обработка события добавления бота в новый чат
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            chat_id = message.chat.id
            if chat_id not in active_chats:
                active_chats.add(chat_id)
                save_active_chats(active_chats)
                bot.send_message(chat_id, "Привет! Я активирован и готов работать.")
                logger.info(f"Бот добавлен и активирован в чате {chat_id}")
                # При необходимости автоматически включить планировщик
                if not scheduler_started:
                    schedule_jobs()
            break  # Предполагаем, что бот только один добавляется

def send_morning_stickers():
    for chat_id in active_chats:
        try:
            bot.send_sticker(chat_id=chat_id, sticker=MORNING_STICKER_ID)
            logger.info(f"Утренний стикер отправлен в чат {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего стикера в чат {chat_id}: {e}")

def send_evening_stickers():
    for chat_id in active_chats:
        try:
            bot.send_sticker(chat_id=chat_id, sticker=EVENING_STICKER_ID)
            logger.info(f"Вечерний стикер отправлен в чат {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего стикера в чат {chat_id}: {e}")

# Планирование задач (утренний и вечерний стикеры)
def schedule_jobs():
    global scheduler_started

    if not scheduler_started:
        # Используем CronTrigger для задания времени
        morning_trigger = CronTrigger(hour=7, minute=0, second=0, timezone='Europe/Moscow')  # Утренний стикер
        evening_trigger = CronTrigger(hour=18, minute=0, second=0, timezone='Europe/Moscow')  # Вечерний стикер

        # Запускаем задачи
        scheduler.add_job(send_morning_stickers, morning_trigger, id='morning_stickers')
        scheduler.add_job(send_evening_stickers, evening_trigger, id='evening_stickers')

        scheduler.start()  # Запускаем планировщик, если еще не был запущен
        scheduler_started = True
        logger.info("Планировщик был запущен.")

# Отмена всех запланированных задач (при необходимости)
def cancel_jobs():
    scheduler.remove_all_jobs()
    global scheduler_started
    scheduler_started = False
    logger.info("Все задачи планировщика отменены.")

# Основная функция для запуска бота
def main():
    if active_chats:
        schedule_jobs()
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
