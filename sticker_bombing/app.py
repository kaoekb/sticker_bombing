from __future__ import annotations

import asyncio
import logging
import random
import time
from types import SimpleNamespace
from typing import Iterable

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telebot.async_telebot import AsyncTeleBot

from sticker_bombing.config import AppSettings
from sticker_bombing.content import PhraseBook
from sticker_bombing.store import ChatState, SubscriptionStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class StickerBombingApp:
    def __init__(
        self,
        settings: AppSettings,
        phrase_book: PhraseBook,
        store: SubscriptionStore,
    ) -> None:
        self.settings = settings
        self.phrase_book = phrase_book
        self.store = store
        self.bot = AsyncTeleBot(settings.token, parse_mode=None)
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler.tzinfo)
        self.chat_states = self.store.load_chat_states(self.phrase_book.default_mode())
        self.bot_user: SimpleNamespace | None = None
        self.state_lock = asyncio.Lock()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.bot.message_handler(commands=["start"])(self.cmd_start)
        self.bot.message_handler(commands=["stop"])(self.cmd_stop)
        self.bot.message_handler(commands=["status"])(self.cmd_status)
        self.bot.message_handler(commands=["meme"])(self.cmd_meme)
        self.bot.message_handler(commands=["modes"])(self.cmd_modes)
        self.bot.message_handler(commands=["mode"])(self.cmd_mode)
        self.bot.message_handler(commands=["bomb"])(self.cmd_bomb)
        self.bot.message_handler(commands=["help"])(self.cmd_help)
        self.bot.message_handler(content_types=["new_chat_members"])(self.on_new_chat_members)
        self.bot.message_handler(content_types=["text"], func=lambda _: True)(self.on_text_message)

    async def cmd_start(self, message) -> None:
        if not self.settings.bot.enabled:
            await self.bot.send_message(message.chat.id, "Бот сейчас выключен в конфиге.")
            return

        chat_id = message.chat.id
        activated = await self._activate_chat(chat_id)
        if not activated:
            await self.bot.send_message(chat_id, "Я уже на посту в этом чате.")
            return

        await self.bot.send_message(chat_id, self.settings.bot.messages.start_message)
        logger.info("Chat %s activated", chat_id)

    async def cmd_stop(self, message) -> None:
        if not self.settings.bot.enabled:
            await self.bot.send_message(message.chat.id, "Бот сейчас выключен в конфиге.")
            return

        chat_id = message.chat.id
        async with self.state_lock:
            if chat_id not in self.chat_states:
                await self.bot.send_message(chat_id, "В этом чате я и так молчу.")
                return

            del self.chat_states[chat_id]
            self.store.save_chat_states(self.chat_states)
            self._unschedule_chat(chat_id)

        await self.bot.send_message(chat_id, self.settings.bot.messages.stop_message)
        if self.settings.bot.messages.stop_follow_up:
            await asyncio.sleep(2)
            await self.bot.send_message(chat_id, self.settings.bot.messages.stop_follow_up)
        logger.info("Chat %s deactivated", chat_id)

    async def cmd_status(self, message) -> None:
        chat_id = message.chat.id
        chat_state = self.chat_states.get(chat_id)
        active = "активен" if chat_state else "спит"
        mode = self.phrase_book.get_mode(chat_state.mode if chat_state else self.phrase_book.default_mode())
        text = (
            f"Статус: {active}\n"
            f"Режим: {mode.title} ({mode.name})\n"
            f"Утренний стикер: {self.settings.scheduler.morning_time}\n"
            f"Вечерний стикер: {self.settings.scheduler.evening_time}\n"
            f"Часовой пояс: {self.settings.scheduler.timezone}\n"
            f"Шанс реплики: {int(self.settings.bot.reply_probability * 100)}%\n"
            f"Кулдаун реплик: {self.settings.bot.reply_cooldown_seconds} сек."
        )
        await self.bot.send_message(chat_id, text)

    async def cmd_meme(self, message) -> None:
        await self._send_random_phrase(message.chat.id, force=True)

    async def cmd_modes(self, message) -> None:
        lines = ["Доступные режимы:"]
        for mode in self.phrase_book.list_modes():
            lines.append(f"- {mode.name}: {mode.title}. {mode.description}")
        await self.bot.send_message(message.chat.id, "\n".join(lines))

    async def cmd_mode(self, message) -> None:
        chat_id = message.chat.id
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) == 1:
            current = self.chat_states.get(chat_id)
            mode = self.phrase_book.get_mode(current.mode if current else self.phrase_book.default_mode())
            await self.bot.send_message(
                chat_id,
                f"Сейчас режим {mode.name}: {mode.title}\nИспользуй /mode <имя> для переключения.",
            )
            return

        requested_mode = parts[1].strip().casefold()
        if not self.phrase_book.has_mode(requested_mode):
            await self.bot.send_message(chat_id, "Такого режима нет. Смотри список через /modes.")
            return

        async with self.state_lock:
            chat_state = self.chat_states.get(chat_id)
            if not chat_state:
                await self.bot.send_message(chat_id, "Сначала включи бота через /start.")
                return
            chat_state.mode = requested_mode
            self.store.save_chat_states(self.chat_states)

        mode = self.phrase_book.get_mode(requested_mode)
        await self.bot.send_message(chat_id, f"Переключился на режим {mode.title}.")

    async def cmd_bomb(self, message) -> None:
        chat_id = message.chat.id
        sticker_id = random.choice(
            [
                self.settings.telegram.morning_sticker_id,
                self.settings.telegram.evening_sticker_id,
            ]
        )
        await self.bot.send_sticker(chat_id, sticker_id)

    async def cmd_help(self, message) -> None:
        await self.bot.send_message(message.chat.id, self.settings.bot.messages.help_message)

    async def on_new_chat_members(self, message) -> None:
        me = await self._ensure_bot_user()
        if not any(member.id == me.id for member in message.new_chat_members):
            return

        activated = await self._activate_chat(message.chat.id)
        if not activated:
            return

        await self.bot.send_message(
            message.chat.id,
            "Я в чате. Расписание включено для этой группы автоматически. Команды: /status, /modes, /mode, /stop.",
        )
        logger.info("Chat %s auto-activated after bot was added", message.chat.id)

    async def on_text_message(self, message) -> None:
        text = (message.text or "").strip()
        if not text or text.startswith("/"):
            return

        if getattr(message.from_user, "is_bot", False):
            return

        chat_state = self.chat_states.get(message.chat.id)
        if not chat_state:
            return

        now = time.time()
        if await self._is_direct_ping(message, text):
            if not self._can_reply(chat_state, now):
                return
            await self._send_random_phrase(message.chat.id, chat_state=chat_state, timestamp=now)
            return

        if not self._can_reply(chat_state, now):
            return

        trigger_phrase = self.phrase_book.trigger_phrase(text)
        if trigger_phrase:
            await self._send_phrase(message.chat.id, trigger_phrase, chat_state, now)
            return

        if random.random() > self.settings.bot.reply_probability:
            return

        await self._send_random_phrase(message.chat.id, chat_state=chat_state, timestamp=now)

    async def _send_random_phrase(
        self,
        chat_id: int,
        force: bool = False,
        chat_state: ChatState | None = None,
        timestamp: float | None = None,
    ) -> None:
        active_state = chat_state or self.chat_states.get(chat_id)
        mode_name = active_state.mode if active_state else self.phrase_book.default_mode()
        phrase = self.phrase_book.random_phrase(mode_name)
        if not phrase:
            await self.bot.send_message(chat_id, "Контент закончился. Пора пополнить memes.yaml.")
            return
        await self._send_phrase(chat_id, phrase, active_state, timestamp, force=force)

    async def _send_phrase(
        self,
        chat_id: int,
        phrase: str,
        chat_state: ChatState | None,
        timestamp: float | None,
        force: bool = False,
    ) -> None:
        await self.bot.send_message(chat_id, phrase)
        if force or not chat_state:
            return
        chat_state.last_reply_at = timestamp or time.time()
        self.store.save_chat_states(self.chat_states)

    def _can_reply(self, chat_state: ChatState, now: float) -> bool:
        cooldown = self.settings.bot.reply_cooldown_seconds
        if cooldown == 0:
            return True
        return now - chat_state.last_reply_at >= cooldown

    async def _ensure_bot_user(self):
        if self.bot_user is None:
            self.bot_user = await self.bot.get_me()
        return self.bot_user

    async def _is_direct_ping(self, message, text: str) -> bool:
        bot_user = await self._ensure_bot_user()

        reply_to_message = getattr(message, "reply_to_message", None)
        reply_author = getattr(reply_to_message, "from_user", None)
        if reply_author and reply_author.id == bot_user.id:
            return True

        username = getattr(bot_user, "username", None)
        if username and f"@{username.casefold()}" in text.casefold():
            return True

        return False

    async def _activate_chat(self, chat_id: int) -> bool:
        async with self.state_lock:
            if chat_id in self.chat_states:
                return False

            self.chat_states[chat_id] = ChatState(mode=self.phrase_book.default_mode())
            self.store.save_chat_states(self.chat_states)
            self._schedule_chat(chat_id)
            return True

    def _schedule_chat(self, chat_id: int) -> None:
        self.scheduler.add_job(
            self._send_morning_sticker,
            trigger=self._build_trigger(self.settings.scheduler.morning_time),
            args=[chat_id],
            id=self._job_id("morning", chat_id),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self._send_evening_sticker,
            trigger=self._build_trigger(self.settings.scheduler.evening_time),
            args=[chat_id],
            id=self._job_id("evening", chat_id),
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def _unschedule_chat(self, chat_id: int) -> None:
        for job_id in self._job_ids(chat_id):
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                continue

    def _restore_jobs(self) -> None:
        for chat_id in self.chat_states:
            self._schedule_chat(chat_id)

    def _build_trigger(self, time_value: str) -> CronTrigger:
        hours, minutes, seconds = (int(part) for part in time_value.split(":"))
        return CronTrigger(
            hour=hours,
            minute=minutes,
            second=seconds,
            timezone=self.settings.scheduler.tzinfo,
        )

    @staticmethod
    def _job_id(kind: str, chat_id: int) -> str:
        return f"{kind}:{chat_id}"

    def _job_ids(self, chat_id: int) -> Iterable[str]:
        yield self._job_id("morning", chat_id)
        yield self._job_id("evening", chat_id)

    async def _send_morning_sticker(self, chat_id: int) -> None:
        await self.bot.send_sticker(chat_id, self.settings.telegram.morning_sticker_id)
        logger.info("Morning sticker sent to %s", chat_id)

    async def _send_evening_sticker(self, chat_id: int) -> None:
        await self.bot.send_sticker(chat_id, self.settings.telegram.evening_sticker_id)
        logger.info("Evening sticker sent to %s", chat_id)

    async def _run(self) -> None:
        if not self.settings.bot.enabled:
            logger.info("Bot disabled in config, skipping startup.")
            return

        self.bot_user = await self.bot.get_me()
        self.scheduler.start()
        self._restore_jobs()
        logger.info("Restored %s active chats", len(self.chat_states))

        try:
            await self.bot.polling(non_stop=True, timeout=30, request_timeout=30)
        finally:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            await self.bot.close_session()

    def run(self) -> None:
        asyncio.run(self._run())
