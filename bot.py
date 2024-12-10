import logging
import datetime
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.daily import DailyTrigger
from dotenv import load_dotenv  # Импортируем для работы с .env

# Загружаем переменные из .env файла
load_dotenv()

# Включаем логирование для удобства отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения из .env
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# ID стикеров для утреннего и вечернего времени
MORNING_STICKER_ID = 'CAACAgIAAxkBAAEBhNJg1DZH_G7ZB_cfwZDPOz5uxtGG2gAC2gAD6SK7Io_OwVmx5n7-VwQ'
EVENING_STICKER_ID = 'CAACAgIAAxkBAAEBhNpZ1DZH_G7_ZLcFb8t6E0MwHeQZ8gAC0QAD6SK7Io_OwVmx5n7-VwQ'

# Состояние бота
bot_enabled = False

# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Команда для включения бота
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    global bot_enabled
    bot_enabled = True
    await message.reply("Бот активирован! Я буду присылать стикеры каждое утро и вечер.")
    schedule_jobs()

# Команда для отключения бота
@dp.message_handler(commands=['stop'])
async def cmd_stop(message: types.Message):
    global bot_enabled
    bot_enabled = False
    await message.reply("Бот деактивирован. Я больше не буду присылать стикеры.")
    cancel_jobs()

# Функция отправки утреннего стикера
async def send_morning_sticker():
    if bot_enabled:
        # Отправляем стикер в группу
        await bot.send_sticker(chat_id=GROUP_CHAT_ID, sticker=MORNING_STICKER_ID)

# Функция отправки вечернего стикера
async def send_evening_sticker():
    if bot_enabled:
        # Отправляем стикер в группу
        await bot.send_sticker(chat_id=GROUP_CHAT_ID, sticker=EVENING_STICKER_ID)

# Планирование задач (утренний и вечерний стикеры)
def schedule_jobs():
    now = datetime.datetime.now()
    morning_trigger = DailyTrigger(hour=7, minute=0, second=0, timezone='UTC')
    evening_trigger = DailyTrigger(hour=19, minute=0, second=0, timezone='UTC')

    # Запускаем задачи
    scheduler.add_job(send_morning_sticker, morning_trigger)
    scheduler.add_job(send_evening_sticker, evening_trigger)
    scheduler.start()

# Отмена всех запланированных задач
def cancel_jobs():
    scheduler.remove_all_jobs()

# Основная функция
if __name__ == '__main__':
    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
