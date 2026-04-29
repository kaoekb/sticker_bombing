from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from dotenv import load_dotenv


DEFAULT_START_MESSAGE = "Бот включился. Начинаем аккуратную стикер-бомбёжку."
DEFAULT_STOP_MESSAGE = "Остановился. Стикеры временно под замком."
DEFAULT_STOP_FOLLOW_UP = ""
DEFAULT_HELP_MESSAGE = (
    "Команды: /start, /stop, /status, /meme, /help. "
    "После /start бот шлёт утренний и вечерний стикеры, а иногда отвечает репликой в чате."
)


@dataclass(frozen=True)
class TelegramSettings:
    morning_sticker_id: str
    evening_sticker_id: str


@dataclass(frozen=True)
class SchedulerSettings:
    morning_time: str
    evening_time: str
    timezone: str

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class MessageSettings:
    start_message: str
    stop_message: str
    stop_follow_up: str
    help_message: str


@dataclass(frozen=True)
class BotSettings:
    enabled: bool
    reply_probability: float
    reply_cooldown_seconds: int
    storage_path: Path
    messages: MessageSettings


@dataclass(frozen=True)
class AppSettings:
    token: str
    telegram: TelegramSettings
    scheduler: SchedulerSettings
    bot: BotSettings


def load_settings(config_path: str = "config.yaml", env_path: str = ".env") -> AppSettings:
    load_dotenv(env_path)
    raw_config = _load_yaml(config_path)

    telegram = raw_config.get("telegram", {})
    scheduler = raw_config.get("scheduler", {})
    bot = raw_config.get("bot", {})
    messages = bot.get("messages", {})

    token = os.getenv("TELEGRAM_API_TOKEN")
    if not token:
        raise ValueError("В .env отсутствует TELEGRAM_API_TOKEN.")

    morning_sticker_id = str(telegram.get("morning_sticker_id", "")).strip()
    evening_sticker_id = str(telegram.get("evening_sticker_id", "")).strip()
    if not morning_sticker_id or not evening_sticker_id:
        raise ValueError("В config.yaml должны быть указаны morning_sticker_id и evening_sticker_id.")

    morning_time = _validate_time_string(str(scheduler.get("morning_time", "07:00:00")))
    evening_time = _validate_time_string(str(scheduler.get("evening_time", "20:00:00")))
    timezone_name = str(scheduler.get("timezone", "Europe/Moscow"))
    _validate_timezone(timezone_name)

    reply_probability = float(bot.get("reply_probability", 0.35))
    if not 0 <= reply_probability <= 1:
        raise ValueError("reply_probability должен быть числом от 0 до 1.")

    reply_cooldown_seconds = int(bot.get("reply_cooldown_seconds", 900))
    if reply_cooldown_seconds < 0:
        raise ValueError("reply_cooldown_seconds должен быть неотрицательным числом.")

    storage_path = Path(str(bot.get("storage_path", "data/subscriptions.json")))

    return AppSettings(
        token=token,
        telegram=TelegramSettings(
            morning_sticker_id=morning_sticker_id,
            evening_sticker_id=evening_sticker_id,
        ),
        scheduler=SchedulerSettings(
            morning_time=morning_time,
            evening_time=evening_time,
            timezone=timezone_name,
        ),
        bot=BotSettings(
            enabled=bool(bot.get("enabled", True)),
            reply_probability=reply_probability,
            reply_cooldown_seconds=reply_cooldown_seconds,
            storage_path=storage_path,
            messages=MessageSettings(
                start_message=str(messages.get("start_message", DEFAULT_START_MESSAGE)),
                stop_message=str(messages.get("stop_message", DEFAULT_STOP_MESSAGE)),
                stop_follow_up=str(messages.get("stop_follow_up", DEFAULT_STOP_FOLLOW_UP)),
                help_message=str(messages.get("help_message", DEFAULT_HELP_MESSAGE)),
            ),
        ),
    )


def _load_yaml(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} должен содержать YAML-объект верхнего уровня.")
    return loaded


def _validate_time_string(value: str) -> str:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Некорректное время '{value}'. Ожидается HH:MM:SS.")

    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as error:
        raise ValueError(f"Некорректное время '{value}'. Ожидаются только числа.") from error

    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
        raise ValueError(f"Некорректное время '{value}'.")

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Неизвестный timezone '{value}'.") from error
