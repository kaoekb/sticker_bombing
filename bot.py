import logging
import os
import time
import telebot
import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from random


# Загружаем переменные из .env файла
load_dotenv()

# Включаем логирование для удобства отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем конфигурацию из YAML файла
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

config = load_config()

# Извлекаем настройки из конфигурации
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')  # API токен из .env файла
MORNING_STICKER_ID = config['telegram']['morning_sticker_id']
EVENING_STICKER_ID = config['telegram']['evening_sticker_id']

MORNING_TIME = config['scheduler']['morning_time']
EVENING_TIME = config['scheduler']['evening_time']
TIMEZONE = config['scheduler']['timezone']

# Сообщения для команд
START_MESSAGE = config['bot']['messages']['start_message']
STOP_MESSAGE = config['bot']['messages']['stop_message']
STOP_FOLLOW_UP = config['bot']['messages']['stop_follow_up']
HELP_MESSAGE = config['bot']['messages']['help_message']

def load_memes():
    with open("memes.yaml", "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data['memes']

memes = load_memes()


# Состояние бота
bot_enabled = config['bot']['enabled']

# Создаем объект бота
bot = telebot.TeleBot(API_TOKEN)

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler_started = False  # Флаг, который будет указывать, что планировщик еще не запущен

# Команда для включения бота
@bot.message_handler(commands=['start'])
def cmd_start(message):
    global bot_enabled
    bot_enabled = True
    bot.reply_to(message, START_MESSAGE)
    schedule_jobs(message.chat.id)  # Передаем chat_id для планировщика

# Команда для отключения бота
@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    global bot_enabled
    bot_enabled = False
    bot.reply_to(message, STOP_MESSAGE)
    time.sleep(7)
    bot.reply_to(message, STOP_FOLLOW_UP)
    cancel_jobs()

def send_morning_sticker(chat_id):
    logger.info(f"Попытка отправить утренний стикер в чат {chat_id}...")
    if bot_enabled:
        try:
            bot.send_sticker(chat_id=chat_id, sticker=MORNING_STICKER_ID)
            logger.info(f"Утренний стикер успешно отправлен в чат {chat_id}!")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего стикера в чат {chat_id}: {e}")

def send_evening_sticker(chat_id):
    logger.info(f"Попытка отправить вечерний стикер в чат {chat_id}...")
    if bot_enabled:
        try:
            bot.send_sticker(chat_id=chat_id, sticker=EVENING_STICKER_ID)
            logger.info(f"Вечерний стикер успешно отправлен в чат {chat_id}!")
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего стикера в чат {chat_id}: {e}")

# Планирование задач (утренний и вечерний стикеры)
def schedule_jobs(chat_id):
    global scheduler_started

    if not scheduler_started:
        # Используем CronTrigger для задания времени
        morning_trigger = CronTrigger(hour=int(MORNING_TIME.split(':')[0]), 
                                      minute=int(MORNING_TIME.split(':')[1]), 
                                      second=int(MORNING_TIME.split(':')[2]), 
                                      timezone=TIMEZONE)  # Утренний стикер

        evening_trigger = CronTrigger(hour=int(EVENING_TIME.split(':')[0]), 
                                      minute=int(EVENING_TIME.split(':')[1]), 
                                      second=int(EVENING_TIME.split(':')[2]), 
                                      timezone=TIMEZONE)  # Вечерний стикер

        # Запускаем задачи с передачей chat_id
        scheduler.add_job(send_morning_sticker, morning_trigger, args=[chat_id])
        scheduler.add_job(send_evening_sticker, evening_trigger, args=[chat_id])

        scheduler.start()  # Запускаем планировщик, если еще не был запущен
        scheduler_started = True
        logger.info("Планировщик был запущен.")

# Отмена всех запланированных задач
def cancel_jobs():
    scheduler.remove_all_jobs()

# Обработчик сообщений, который получает chat_id
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id  # Получаем chat_id из сообщения
    if bot_enabled:
        bot.send_message(chat_id, HELP_MESSAGE)
    # Здесь можно добавить логику по обработке других типов сообщений

@bot.message_handler(commands=['quote'])
def cmd_quote(message):
    quote = random.choice(memes)
    bot.reply_to(message, quote)


# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
