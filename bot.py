import logging
import os
import telebot
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
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# ID стикеров для утреннего и вечернего времени
MORNING_STICKER_ID = os.getenv('MORNING_STICKER_ID')
EVENING_STICKER_ID = os.getenv('EVENING_STICKER_ID')

# Состояние бота
bot_enabled = False

# Создаем объект бота
bot = telebot.TeleBot(API_TOKEN)

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler_started = False  # Флаг, который будет указывать, что планировщик уже запущен

# Команда для включения бота
@bot.message_handler(commands=['start'])
def cmd_start(message):
    global bot_enabled
    bot_enabled = True
    bot.reply_to(message, "Бот активирован! Я буду присылать стикеры каждое утро и вечер.")
    schedule_jobs()

# Команда для отключения бота
@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    global bot_enabled
    bot_enabled = False
    bot.reply_to(message, "Бот деактивирован. Я больше не буду присылать стикеры.")
    cancel_jobs()

def send_morning_sticker():
    if bot_enabled:
        try:
            bot.send_sticker(chat_id=GROUP_CHAT_ID, sticker=MORNING_STICKER_ID)
            logger.info("Утренний стикер успешно отправлен!")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего стикера: {e}")

def send_evening_sticker():
    if bot_enabled:
        try:
            bot.send_sticker(chat_id=GROUP_CHAT_ID, sticker=EVENING_STICKER_ID)
            logger.info("Вечерний стикер успешно отправлен!")
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего стикера: {e}")

# Планирование задач (утренний и вечерний стикеры)
def schedule_jobs():
    global scheduler_started

    if not scheduler_started:
        # Используем CronTrigger для задания времени
        morning_trigger = CronTrigger(hour=7, minute=0, second=0, timezone='Europe/Moscow')  # Утренний стикер
        evening_trigger = CronTrigger(hour=20, minute=29, second=0, timezone='Europe/Moscow')  # Вечерний стикер

        # Запускаем задачи
        scheduler.add_job(send_morning_sticker, morning_trigger)
        scheduler.add_job(send_evening_sticker, evening_trigger)

        scheduler.start()  # Запускаем планировщик, если еще не был запущен
        scheduler_started = True
        logger.info("Планировщик был запущен.")

# Отмена всех запланированных задач
def cancel_jobs():
    scheduler.remove_all_jobs()

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
