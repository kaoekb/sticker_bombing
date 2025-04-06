import logging
import os
import random
import asyncio
from typing import Dict, Any

import telebot
from telebot.async_telebot import AsyncTeleBot
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Функция для загрузки YAML файлов
def load_yaml_file(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"Файл {filepath} не найден.")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Ошибка при загрузке YAML файла {filepath}: {e}")
        return {}

# Загрузка конфигураций
config = load_yaml_file("config.yaml")
memes = load_yaml_file("memes.yaml").get('memes', [])

# Проверка наличия необходимых разделов в config.yaml
required_config_keys = ['telegram', 'scheduler', 'bot']
for key in required_config_keys:
    if key not in config:
        logger.error(f"Отсутствует раздел '{key}' в config.yaml.")
        exit(1)

telegram_config = config['telegram']
scheduler_config = config['scheduler']
bot_config = config['bot']

# Получение API токена
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
if not API_TOKEN:
    logger.error("Отсутствует TELEGRAM_API_TOKEN в .env файле.")
    exit(1)

# Получение настроек из config.yaml
MORNING_STICKER_ID = telegram_config.get('morning_sticker_id')
EVENING_STICKER_ID = telegram_config.get('evening_sticker_id')
MORNING_TIME = scheduler_config.get('morning_time', "07:00:00")
EVENING_TIME = scheduler_config.get('evening_time', "23:35:00")
TIMEZONE = scheduler_config.get('timezone', "Europe/Moscow")

START_MESSAGE = bot_config.get('messages', {}).get('start_message')
STOP_MESSAGE = bot_config.get('messages', {}).get('stop_message')
STOP_FOLLOW_UP = bot_config.get('messages', {}).get('stop_follow_up')
HELP_MESSAGE = bot_config.get('messages', {}).get('help_message')

# Проверка наличия всех необходимых сообщений
if not all([START_MESSAGE, STOP_MESSAGE, STOP_FOLLOW_UP, HELP_MESSAGE]):
    logger.error("Некоторые сообщения отсутствуют в config.yaml.")
    exit(1)

# Проверка глобального статуса бота
BOT_ENABLED = bot_config.get('enabled', False)

class TelegramBot:
    def __init__(self, token: str):
        self.bot = AsyncTeleBot(token, parse_mode=None)
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self.user_jobs: Dict[int, Dict[str, Any]] = {}  # chat_id -> job_ids

        # Регистрируем обработчики
        self.bot.message_handler(commands=['start'])(self.cmd_start)
        self.bot.message_handler(commands=['stop'])(self.cmd_stop)
        self.bot.message_handler(commands=['help'])(self.cmd_help)
        self.bot.message_handler(func=lambda message: True)(self.handle_message)

    async def cmd_start(self, message):
        if not BOT_ENABLED:
            await self.bot.send_message(message.chat.id, "Бот в данный момент отключен.")
            return

        chat_id = message.chat.id
        if chat_id in self.user_jobs:
            await self.bot.send_message(chat_id, "Бот уже запущен.")
            return

        await self.bot.send_message(chat_id, START_MESSAGE)
        self.schedule_jobs(chat_id)
        logger.info(f"Бот запущен для чата {chat_id}.")

    async def cmd_stop(self, message):
        if not BOT_ENABLED:
            await self.bot.send_message(message.chat.id, "Бот в данный момент отключен.")
            return

        chat_id = message.chat.id
        if chat_id not in self.user_jobs:
            await self.bot.send_message(chat_id, "Бот не запущен.")
            return

        self.cancel_jobs(chat_id)
        await self.bot.send_message(chat_id, STOP_MESSAGE)
        await asyncio.sleep(7)
        await self.bot.send_message(chat_id, STOP_FOLLOW_UP)
        logger.info(f"Бот остановлен для чата {chat_id}.")

    async def cmd_help(self, message):
        if not BOT_ENABLED:
            await self.bot.send_message(message.chat.id, "Бот в данный момент отключен.")
            return

        chat_id = message.chat.id
        if chat_id in self.user_jobs:
            await self.bot.send_message(chat_id, HELP_MESSAGE)
        else:
            await self.bot.send_message(chat_id, "Бот не запущен. Используйте /start для запуска.")

    async def handle_message(self, message):
        if not BOT_ENABLED:
            return  # Игнорируем все сообщения, если бот отключен

        chat_id = message.chat.id
        if chat_id in self.user_jobs:
            if memes:
                random_meme = random.choice(memes)
                await self.bot.send_message(chat_id, random_meme)
            else:
                await self.bot.send_message(chat_id, "Мемы отсутствуют.")
        else:
            await self.bot.send_message(chat_id, "Бот не запущен. Используйте /start для запуска.")

    def schedule_jobs(self, chat_id: int):
        morning_hour, morning_minute, morning_second = map(int, MORNING_TIME.split(':'))
        evening_hour, evening_minute, evening_second = map(int, EVENING_TIME.split(':'))

        morning_trigger = CronTrigger(
            hour=morning_hour,
            minute=morning_minute,
            second=morning_second,
            timezone=TIMEZONE
        )
        evening_trigger = CronTrigger(
            hour=evening_hour,
            minute=evening_minute,
            second=evening_second,
            timezone=TIMEZONE
        )

        morning_job = self.scheduler.add_job(
            self.send_morning_sticker,
            morning_trigger,
            args=[chat_id],
            id=f"morning_sticker_{chat_id}"
        )
        evening_job = self.scheduler.add_job(
            self.send_evening_sticker,
            evening_trigger,
            args=[chat_id],
            id=f"evening_sticker_{chat_id}"
        )

        self.user_jobs[chat_id] = {
            'morning_job': morning_job,
            'evening_job': evening_job
        }
        logger.info(f"Запланированы утренний и вечерний стикеры для чата {chat_id}.")

    def cancel_jobs(self, chat_id: int):
        jobs = self.user_jobs.get(chat_id)
        if jobs:
            for job in jobs.values():
                job.remove()
            del self.user_jobs[chat_id]
            logger.info(f"Запланированные задачи отменены для чата {chat_id}.")

    async def send_morning_sticker(self, chat_id: int):
        logger.info(f"Отправка утреннего стикера в чат {chat_id}...")
        try:
            await self.bot.send_sticker(chat_id, MORNING_STICKER_ID)
            logger.info(f"Утренний стикер отправлен в чат {chat_id}.")
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего стикера в чат {chat_id}: {e}")

    async def send_evening_sticker(self, chat_id: int):
        logger.info(f"Отправка вечернего стикера в чат {chat_id}...")
        try:
            await self.bot.send_sticker(chat_id, EVENING_STICKER_ID)
            logger.info(f"Вечерний стикер отправлен в чат {chat_id}.")
        except Exception as e:
            logger.error(f"Ошибка при отправке вечернего стикера в чат {chat_id}: {e}")

    def run(self):
        if not BOT_ENABLED:
            logger.info("Бот отключен в конфигурации и не будет запущен.")
            return

        logger.info("Бот запускается...")
        asyncio.run(self.bot.polling())

if __name__ == '__main__':
    telegram_bot = TelegramBot(API_TOKEN)
    telegram_bot.run()
