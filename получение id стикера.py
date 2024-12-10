import telebot
import logging
from dotenv import load_dotenv
import os

# Загружаем переменные из .env файла
load_dotenv()

# Включаем логирование для удобства отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения из .env
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

# Создаем объект бота
bot = telebot.TeleBot(API_TOKEN)

# Хэндлер для стикеров
@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    try:
        # Получаем file_id стикера
        sticker_id = message.sticker.file_id
        # Записываем file_id в лог
        logger.info(f"Получен стикер с file_id: {sticker_id}")
        # Отправляем подтверждение пользователю
        bot.reply_to(message, "Стикер получен!")
    except Exception as e:
        logger.error(f"Ошибка при обработке стикера: {e}")
        bot.reply_to(message, "Произошла ошибка при обработке стикера.")

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
