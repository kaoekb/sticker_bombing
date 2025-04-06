import os
import yaml
import logging
import asyncio
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Настройки
CONFIG_PATH = "config.yaml"
ADMIN_IDS = [273792356]  # Замените на свой Telegram ID

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка .env
load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
if not API_TOKEN:
    logger.error("Отсутствует TELEGRAM_API_TOKEN")
    exit(1)

# Загрузка конфигурации
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)

config = load_config()
bot = AsyncTeleBot(API_TOKEN)
scheduler = AsyncIOScheduler()
scheduler.start()

# Вспомогательные функции
def is_admin(user_id):
    return user_id in ADMIN_IDS

def schedule_sticker(chat_id, sticker_id, time_str, job_id, tz):
    h, m, s = map(int, time_str.split(":"))
    trigger = CronTrigger(hour=h, minute=m, second=s, timezone=tz)
    scheduler.add_job(send_sticker, trigger, args=[chat_id, sticker_id], id=job_id, replace_existing=True)

async def send_sticker(chat_id, sticker_id):
    try:
        await bot.send_sticker(chat_id, sticker_id)
        logger.info(f"Стикер отправлен в чат {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки стикера: {e}")

# Команды
@bot.message_handler(commands=["start"])
async def start_handler(msg):
    await bot.send_message(msg.chat.id, config["bot"]["messages"]["start_message"])
    schedule_sticker(msg.chat.id, config["telegram"]["morning_sticker_id"], config["scheduler"]["morning_time"], f"morning_{msg.chat.id}", config["scheduler"]["timezone"])
    schedule_sticker(msg.chat.id, config["telegram"]["evening_sticker_id"], config["scheduler"]["evening_time"], f"evening_{msg.chat.id}", config["scheduler"]["timezone"])

@bot.message_handler(commands=["help"])
async def help_handler(msg):
    await bot.send_message(msg.chat.id, config["bot"]["messages"]["help_message"])

@bot.message_handler(commands=["set_morning"])
async def set_morning_time(msg):
    if not is_admin(msg.from_user.id):
        return await bot.send_message(msg.chat.id, "Нет доступа.")
    try:
        parts = msg.text.split()
        if len(parts) != 2:
            return await bot.send_message(msg.chat.id, "Формат: /set_morning HH:MM:SS")
        config["scheduler"]["morning_time"] = parts[1]
        save_config(config)
        schedule_sticker(msg.chat.id, config["telegram"]["morning_sticker_id"], parts[1], f"morning_{msg.chat.id}", config["scheduler"]["timezone"])
        await bot.send_message(msg.chat.id, f"Утреннее время обновлено на {parts[1]}")
    except Exception as e:
        logger.error(e)
        await bot.send_message(msg.chat.id, "Ошибка обновления времени.")

@bot.message_handler(commands=["set_evening"])
async def set_evening_time(msg):
    if not is_admin(msg.from_user.id):
        return await bot.send_message(msg.chat.id, "Нет доступа.")
    try:
        parts = msg.text.split()
        if len(parts) != 2:
            return await bot.send_message(msg.chat.id, "Формат: /set_evening HH:MM:SS")
        config["scheduler"]["evening_time"] = parts[1]
        save_config(config)
        schedule_sticker(msg.chat.id, config["telegram"]["evening_sticker_id"], parts[1], f"evening_{msg.chat.id}", config["scheduler"]["timezone"])
        await bot.send_message(msg.chat.id, f"Вечернее время обновлено на {parts[1]}")
    except Exception as e:
        logger.error(e)
        await bot.send_message(msg.chat.id, "Ошибка обновления времени.")

@bot.message_handler(commands=["schedule"])
async def show_schedule(msg):
    if not is_admin(msg.from_user.id):
        return await bot.send_message(msg.chat.id, "Нет доступа.")
    morning = config["scheduler"]["morning_time"]
    evening = config["scheduler"]["evening_time"]
    tz = config["scheduler"]["timezone"]
    now = datetime.now(timezone(tz)).strftime("%H:%M:%S")
    await bot.send_message(msg.chat.id, f"Текущее время ({tz}): {now}\nУтро: {morning}\nВечер: {evening}")

# Запуск
if __name__ == "__main__":
    logger.info("Бот запущен.")
    asyncio.run(bot.polling())
